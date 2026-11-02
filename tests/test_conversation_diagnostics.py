from contextlib import closing
import json
import os
from pathlib import Path
import shutil
import sqlite3
import pytest
from src.conversations.library import ConversationStore
from src.conversations.diagnostics import ConversationDiagnostics


def events(diag):
    return [json.loads(line) for line in diag.path.read_text().splitlines()]


def backup(db, target):
    with closing(sqlite3.connect(db)) as source, closing(sqlite3.connect(target)) as dest:
        source.backup(dest)


def test_commit_and_read_are_correlated_without_private_payload(tmp_path):
    diag = ConversationDiagnostics(tmp_path/'observations')
    store = ConversationStore(tmp_path/'private-database.sqlite3', diagnostics=diag)
    cid = store.create('assistant', 'private-owner', 'SECRET_TITLE')['id']
    store.append_message(cid, 0, 'user', 'SECRET_CONTENT', references={'secret': 'SECRET_REF'})
    store.get(cid)
    diag.close()
    rows = events(diag)
    commit = next(row for row in rows if row['phase'] == 'append_committed')
    read = [row for row in rows if row['phase'] == 'get'][-1]
    assert commit['conversation'] == read['conversation']
    assert read['confirmed_revision'] == read['revision'] == 1
    assert read['message_count'] == 1 and read['flags'] == []
    text = diag.path.read_text()
    for value in (cid, 'SECRET_TITLE', 'SECRET_CONTENT', 'SECRET_REF', 'private-owner', 'private-database'):
        assert value not in text
    if os.name != 'nt':
        assert diag.path.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize('replacement', [True, False], ids=['replace-inode','in-place-rollback'])
def test_detects_loss_after_confirmed_commit(tmp_path, replacement):
    diag = ConversationDiagnostics(tmp_path/'observations')
    db = tmp_path/'db.sqlite3'
    store = ConversationStore(db, diagnostics=diag)
    cid = store.create('assistant', 'test')['id']
    snapshot = tmp_path/'before.sqlite3'
    backup(db,snapshot)
    store.append_message(cid,0,'user','synthetic')
    # Ensure no leaked baseline connection interferes with the synthetic control.
    import gc
    gc.collect()
    before = db.stat()
    if replacement:
        shutil.copy2(snapshot,tmp_path/'restore.sqlite3')
        os.replace(tmp_path/'restore.sqlite3', db)
    else:
        shutil.copyfile(snapshot,db)
    result = store.get(cid)
    assert result['revision'] == 0 and result['messages'] == []
    diag.close()
    rows = events(diag)
    read = [row for row in rows if row['phase'] == 'get'][-1]
    assert 'below_confirmed_revision' in read['flags']
    changed = any('path_identity_changed' in row['flags'] for row in rows)
    assert changed == replacement
    if replacement:
        assert before.st_ino != db.stat().st_ino


def test_diagnostics_bounded_and_disabled_by_default(tmp_path):
    store = ConversationStore(tmp_path/'plain.sqlite3')
    assert store.diagnostics is None
    cid = store.create('assistant', 'test')['id']
    diag = ConversationDiagnostics(tmp_path/'observations',max_events=3)
    store.diagnostics = diag
    store.get(cid);store.get(cid)
    diag.close()
    assert len(events(diag)) == 3
    assert events(diag)[-1]['diagnostic_limit_reached'] is True


def test_observer_failure_does_not_change_write(tmp_path):
    class BrokenObserver:
        def record(self,*args,**kwargs):
            raise OSError('PRIVATE_EXCEPTION')
    store = ConversationStore(tmp_path/'db.sqlite3',diagnostics=BrokenObserver())
    cid = store.create('assistant','test')['id']
    assert store.append_message(cid,0,'user','synthetic')['revision'] == 1
    assert store.get(cid)['revision'] == 1


def test_sink_failure_does_not_change_commit(tmp_path,monkeypatch):
    diag = ConversationDiagnostics(tmp_path/'observations')
    store = ConversationStore(tmp_path/'db.sqlite3',diagnostics=diag)
    cid = store.create('assistant','test')['id']
    def fail(*args):
        raise OSError('private error')
    monkeypatch.setattr(os,'write',fail)
    assert store.append_message(cid,0,'user','synthetic')['revision'] == 1
    assert store.get(cid)['revision'] == 1
    assert diag._fd is None


def test_shared_observer_keeps_database_identities_separate(tmp_path):
    diag = ConversationDiagnostics(tmp_path/'observations')
    first = ConversationStore(tmp_path/'a.sqlite3',diagnostics=diag)
    second = ConversationStore(tmp_path/'b.sqlite3',diagnostics=diag)
    a = first.create('assistant','test')['id']
    b = second.create('assistant','test')['id']
    first.append_message(a,0,'user','synthetic')
    second.get(b);first.get(a)
    diag.close()
    assert not any(row['flags'] for row in events(diag))


def test_revision_is_not_assumed_to_equal_message_count(tmp_path):
    diag = ConversationDiagnostics(tmp_path/'observations')
    store = ConversationStore(tmp_path/'db.sqlite3',diagnostics=diag)
    cid = store.create('assistant','test')['id']
    store.rename(cid,0,'synthetic')
    store.append_message(cid,1,'user','synthetic')
    assert store.get(cid)['revision'] == 2
    diag.close()
    read = [row for row in events(diag) if row['phase'] == 'get'][-1]
    assert read['message_count'] == 1 and read['flags'] == []
