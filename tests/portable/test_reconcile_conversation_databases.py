import hashlib
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.reconcile_conversation_databases import ReconciliationError, reconcile
import scripts.reconcile_conversation_databases as reconciliation
from src.conversations.library import ConversationStore, reset_project_scope, set_project_scope


def make_db(path: Path, identifier: str, *, labels: bool = False):
    with sqlite3.connect(path) as db:
        db.executescript('''
          CREATE TABLE conversations (id TEXT PRIMARY KEY, project_id TEXT NOT NULL,
            owner_kind TEXT NOT NULL CHECK (owner_kind IN ('assistant', 'agent')),
            owner_id TEXT NOT NULL, title TEXT NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('active', 'archived', 'deleted')),
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            revision INTEGER NOT NULL DEFAULT 0);
          CREATE TABLE messages (id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL
            REFERENCES conversations(id), sequence INTEGER NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
            content TEXT NOT NULL, created_at TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'complete',
            references_json TEXT NOT NULL DEFAULT '{}', UNIQUE(conversation_id, sequence));
        ''')
        if labels:
            db.execute("ALTER TABLE conversations ADD COLUMN labels_json TEXT NOT NULL DEFAULT '[]'")
        db.execute('INSERT INTO conversations (id,project_id,owner_kind,owner_id,title,status,created_at,updated_at,revision) VALUES (?,?,?,?,?,?,?,?,?)',
                   (identifier, 'project-' + identifier, 'assistant', 'app-assistant', identifier, 'active', 'created', 'updated', 1))
        db.execute('INSERT INTO messages VALUES (?,?,?,?,?,?,?,?)',
                   ('m-' + identifier, identifier, 1, 'user', 'private fixture', 'created', 'complete', '{}'))


def test_merge_legacy_and_new_into_distinct_candidate_without_changing_sources(tmp_path):
    a, b, out = (tmp_path / x for x in ('a.db', 'b.db', 'out.db'))
    make_db(a, 'a'); make_db(b, 'b', labels=True)
    before = [hashlib.sha256(p.read_bytes()).hexdigest() for p in (a, b)]
    assert reconcile(a, b, out)['incoming_messages'] == 1
    assert [hashlib.sha256(p.read_bytes()).hexdigest() for p in (a, b)] == before
    with sqlite3.connect(out) as db:
        assert db.execute('SELECT id,project_id,labels_json FROM conversations ORDER BY id').fetchall() == [('a', 'project-a', '[]'), ('b', 'project-b', '[]')]
        assert db.execute('SELECT id,conversation_id FROM messages ORDER BY id').fetchall() == [('m-a', 'a'), ('m-b', 'b')]
    store = ConversationStore(out)
    for project, expected in [('project-a', 'a'), ('project-b', 'b')]:
        token = set_project_scope(project)
        try:
            assert [row['id'] for row in store.list(owner_kind='assistant', owner_id='app-assistant')] == [expected]
            assert store.get(expected)['messages'][0]['id'] == 'm-' + expected
        finally:
            reset_project_scope(token)


def test_conflict_and_existing_destination_never_change_inputs(tmp_path):
    a, b, out = (tmp_path / x for x in ('a.db', 'b.db', 'out.db'))
    make_db(a, 'a'); make_db(b, 'a')
    before = [p.read_bytes() for p in (a, b)]
    with pytest.raises(ReconciliationError, match='conflict'):
        reconcile(a, b, out, allow_shared_projects=frozenset({'project-a'}))
    assert [p.read_bytes() for p in (a, b)] == before
    assert not out.exists()
    out.write_bytes(b'existing')
    existing = out.read_bytes()
    with pytest.raises(ReconciliationError, match='already_exists'):
        reconcile(a, b, out)
    assert out.read_bytes() == existing


def test_rejects_extra_tables_and_same_path(tmp_path):
    a, b, out = (tmp_path / x for x in ('a.db', 'b.db', 'out.db'))
    make_db(a, 'a'); make_db(b, 'b')
    with sqlite3.connect(b) as db:
        db.execute('CREATE TABLE unexpected (secret TEXT)')
    with pytest.raises(ReconciliationError, match='unsupported_tables'):
        reconcile(a, b, out)
    assert not out.exists()
    with pytest.raises(ReconciliationError, match='distinct'):
        reconcile(a, a, out)


def test_refuses_live_sidecars_and_triggers(tmp_path):
    a, b, out = (tmp_path / x for x in ('a.db', 'b.db', 'out.db'))
    make_db(a, 'a'); make_db(b, 'b')
    sidecar = Path(str(a) + '-wal')
    sidecar.write_bytes(b'active')
    with pytest.raises(ReconciliationError, match='not_quiescent'):
        reconcile(a, b, out)
    assert not out.exists()
    sidecar.unlink()
    with sqlite3.connect(b) as db:
        db.execute('CREATE TRIGGER no_import AFTER INSERT ON conversations BEGIN DELETE FROM messages; END')
    with pytest.raises(ReconciliationError, match='unsupported_schema_objects'):
        reconcile(a, b, out)
    assert not out.exists()


def test_rejects_orphaned_messages_before_creating_output(tmp_path):
    a, b, out = (tmp_path / x for x in ('a.db', 'b.db', 'out.db'))
    make_db(a, 'a'); make_db(b, 'b')
    with sqlite3.connect(b) as db:
        db.execute("UPDATE messages SET conversation_id='missing'")
    with pytest.raises(ReconciliationError, match='orphaned_message'):
        reconcile(a, b, out)
    assert not out.exists()


@pytest.mark.parametrize(('source', 'column', 'value'), [
    ('base', 'labels_json', 'INVALID'), ('incoming', 'labels_json', '{}'),
    ('base', 'references_json', '['), ('incoming', 'references_json', '[]'),
    ('incoming', 'references_json', '{"value": NaN}'),
])
def test_invalid_json_is_rejected_in_both_inputs(tmp_path, source, column, value):
    a, b, out = (tmp_path / x for x in ('a.db', 'b.db', 'out.db'))
    make_db(a, 'a', labels=True); make_db(b, 'b', labels=True)
    with sqlite3.connect(a if source == 'base' else b) as db:
        table = 'conversations' if column == 'labels_json' else 'messages'
        db.execute(f'UPDATE {table} SET {column}=?', (value,))
    with pytest.raises(ReconciliationError, match='invalid_json_payload'):
        reconcile(a, b, out)
    assert not out.exists()


def test_shared_project_requires_explicit_exact_confirmation(tmp_path):
    a, b, out = (tmp_path / x for x in ('a.db', 'b.db', 'out.db'))
    make_db(a, 'a'); make_db(b, 'b')
    with sqlite3.connect(b) as db:
        db.execute("UPDATE conversations SET project_id='project-a'")
    with pytest.raises(ReconciliationError, match='shared_project_identity_requires_confirmation'):
        reconcile(a, b, out)
    assert not out.exists()
    with pytest.raises(ReconciliationError, match='unknown_shared_project_authorization'):
        reconcile(a, b, out, allow_shared_projects=frozenset({'project-a', 'wrong-project'}))
    result = reconcile(a, b, out, allow_shared_projects=frozenset({'project-a'}))
    assert result['shared_projects_explicitly_approved'] == 1
    assert result['shared_project_ids'] == ['project-a']
    token = set_project_scope('project-a')
    try:
        assert {row['id'] for row in ConversationStore(out).list()} == {'a', 'b'}
    finally:
        reset_project_scope(token)


def test_empty_legacy_labels_are_accepted_like_product(tmp_path):
    a, b, out = (tmp_path / x for x in ('a.db', 'b.db', 'out.db'))
    make_db(a, 'a', labels=True); make_db(b, 'b', labels=True)
    with sqlite3.connect(b) as db:
        db.execute("UPDATE conversations SET labels_json=''")
    reconcile(a, b, out)
    token = set_project_scope('project-b')
    try:
        assert ConversationStore(out).list()[0]['labels'] == []
    finally:
        reset_project_scope(token)


def test_message_id_conflict_rolls_back_incoming_conversations(tmp_path):
    a, b, out = (tmp_path / x for x in ('a.db', 'b.db', 'out.db'))
    make_db(a, 'a'); make_db(b, 'b')
    with sqlite3.connect(b) as db:
        db.execute("UPDATE messages SET id='m-a'")
    with pytest.raises(ReconciliationError, match='conflict'):
        reconcile(a, b, out)
    assert not out.exists()
    staged = next(tmp_path.glob('.bago-reconcile-*/candidate.sqlite3'))
    with sqlite3.connect(staged) as db:
        assert db.execute('SELECT id FROM conversations').fetchall() == [('a',)]


def test_destination_created_during_promotion_is_not_overwritten(tmp_path, monkeypatch):
    a, b, out = (tmp_path / x for x in ('a.db', 'b.db', 'out.db'))
    make_db(a, 'a'); make_db(b, 'b')
    original = reconciliation._promote_without_overwrite

    def race(staged, output):
        output.write_bytes(b'concurrent output')
        original(staged, output)

    monkeypatch.setattr(reconciliation, '_promote_without_overwrite', race)
    with pytest.raises(ReconciliationError, match='candidate_failed'):
        reconcile(a, b, out)
    assert out.read_bytes() == b'concurrent output'


def test_cleanup_failure_reports_promoted_output_as_prepared(tmp_path, monkeypatch):
    a, b, out = (tmp_path / x for x in ('a.db', 'b.db', 'out.db'))
    make_db(a, 'a'); make_db(b, 'b')
    original = Path.rmdir

    def fail_stage_removal(path):
        if path.name.startswith('.bago-reconcile-'):
            raise PermissionError('simulated cleanup failure')
        return original(path)

    monkeypatch.setattr(Path, 'rmdir', fail_stage_removal)
    result = reconcile(a, b, out)
    assert result['status'] == 'prepared' and out.is_file()
    assert Path(result['staging_retained']).is_dir()


def test_missing_sequence_constraint_is_rejected(tmp_path):
    a, b, out = (tmp_path / x for x in ('a.db', 'b.db', 'out.db'))
    make_db(a, 'a'); make_db(b, 'b')
    with sqlite3.connect(b) as db:
        db.executescript('''
          ALTER TABLE messages RENAME TO old_messages;
          CREATE TABLE messages (id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL
            REFERENCES conversations(id), sequence INTEGER NOT NULL, role TEXT NOT NULL,
            content TEXT NOT NULL, created_at TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'complete',
            references_json TEXT NOT NULL DEFAULT '{}');
          INSERT INTO messages SELECT * FROM old_messages;
          DROP TABLE old_messages;
        ''')
    with pytest.raises(ReconciliationError, match='missing_message_sequence_constraint'):
        reconcile(a, b, out)
    assert not out.exists()


def test_refuses_existing_writer_without_modifying_source(tmp_path):
    a, b, out = (tmp_path / x for x in ('a.db', 'b.db', 'out.db'))
    make_db(a, 'a'); make_db(b, 'b')
    with sqlite3.connect(a, timeout=0) as writer:
        writer.execute('BEGIN IMMEDIATE')
        with pytest.raises(ReconciliationError, match='source_lock_unavailable'):
            reconcile(a, b, out)
        writer.rollback()
    assert not out.exists()


def test_source_locks_block_other_sqlite_writers_during_reconciliation(tmp_path, monkeypatch):
    a, b, out = (tmp_path / x for x in ('a.db', 'b.db', 'out.db'))
    make_db(a, 'a'); make_db(b, 'b')
    before = [p.read_bytes() for p in (a, b)]
    original = reconciliation._schema
    seen = []

    def check_lock(db):
        for p in (a, b):
            with sqlite3.connect(p, timeout=0) as writer:
                with pytest.raises(sqlite3.OperationalError, match='locked'):
                    writer.execute('BEGIN IMMEDIATE')
                seen.append(p.name)
            child = subprocess.run([sys.executable, '-B', '-c',
                                    "import sqlite3,sys; c=sqlite3.connect(sys.argv[1],timeout=0); c.execute('BEGIN IMMEDIATE')",
                                    str(p)], capture_output=True, text=True, timeout=10)
            assert child.returncode != 0 and 'locked' in child.stderr
        return original(db)

    monkeypatch.setattr(reconciliation, '_schema', check_lock)
    assert reconcile(a, b, out)['activated'] is False
    assert len(seen) == 4
    assert [p.read_bytes() for p in (a, b)] == before
