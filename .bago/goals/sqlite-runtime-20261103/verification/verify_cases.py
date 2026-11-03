"""Independent diagnostics verification; synthetic fixtures only."""
from contextlib import closing
import gc
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[4]
EVIDENCE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from src.conversations.diagnostics import ConversationDiagnostics
from src.conversations.library import ConversationStore, ConversationNotFound


def rows(diag):
    return [json.loads(line) for line in diag.path.read_text().splitlines()]


def copy_database(source, destination):
    with closing(sqlite3.connect(source)) as src, closing(sqlite3.connect(destination)) as dest:
        src.backup(dest)


def missing_after_restore(directory):
    db = directory/'missing.sqlite3'
    diag = ConversationDiagnostics(directory/'observations')
    store = ConversationStore(db,diagnostics=diag)
    store.create('assistant','synthetic','anchor')
    snapshot = directory/'before-conversation.sqlite3'
    copy_database(db,snapshot)
    cid = store.create('assistant','synthetic','SENSITIVE_TITLE')['id']
    store.append_message(cid,0,'user','SENSITIVE_CONTENT',references={'private':'SENSITIVE_REF'})
    gc.collect()
    os.replace(snapshot,db)
    try:
        store.get(cid)
    except ConversationNotFound:
        pass
    else:
        raise AssertionError('replaced database unexpectedly contains target conversation')
    diag.close()
    events=rows(diag)
    assert any('path_identity_changed' in e['flags'] for e in events)
    assert any(e['phase']=='get_missing' and 'confirmed_conversation_missing' in e['flags'] for e in events)
    text=diag.path.read_text()
    for private in (cid,'SENSITIVE_TITLE','SENSITIVE_CONTENT','SENSITIVE_REF'):
        assert private not in text
    return {'status':'PASS','observed':'physical replacement and confirmed conversation missing; payload absent'}


def mtime_without_replacement(directory):
    db=directory/'mtime.sqlite3'
    diag=ConversationDiagnostics(directory/'observations')
    store=ConversationStore(db,diagnostics=diag)
    cid=store.create('assistant','synthetic')['id']
    store.append_message(cid,0,'user','synthetic')
    store.get(cid)
    before=db.stat()
    os.utime(db,ns=(before.st_atime_ns,before.st_mtime_ns-10_000_000_000))
    store.get(cid)
    diag.close()
    events=rows(diag)
    assert any('mtime_regressed' in e['flags'] for e in events)
    assert not any('path_identity_changed' in e['flags'] for e in events)
    assert not any('below_confirmed_revision' in e['flags'] for e in events)
    return {'status':'PASS','observed':'mtime regression is distinguished from identity change and data loss'}


def short_writes(directory):
    diag=ConversationDiagnostics(directory/'observations')
    actual=os.write
    def partial(fd,data):
        return actual(fd,data[:max(1,len(data)//2)])
    os.write=partial
    try:
        diag.record(directory/'uncreated.sqlite3','connect_before')
    finally:
        os.write=actual
        diag.close()
    data=rows(diag)
    assert len(data)==1 and data[0]['event_number']==0
    return {'status':'PASS','observed':'short writes complete one valid JSON event'}


def main():
    manifest=json.loads((EVIDENCE.parent/'implementation/source-manifest.json').read_text())
    for relative,expected in manifest['files'].items():
        assert hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()==expected, relative
    checks={'source_manifest':{'status':'PASS'}}
    command=[sys.executable,'-m','pytest','tests/test_conversation_diagnostics.py','tests/test_conversation_library.py','-q']
    result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True)
    (EVIDENCE/'focused-tests.log').write_text(result.stdout+result.stderr)
    checks['focused_tests']={'status':'PASS' if result.returncode==0 else 'FAIL','returncode':result.returncode,'command':command}
    assert result.returncode==0
    with tempfile.TemporaryDirectory(prefix='adl-independent-sqlite-',dir='/tmp') as temporary:
        directory=Path(temporary)
        for name,case in [('missing_after_restore',missing_after_restore),('mtime_without_replacement',mtime_without_replacement),('short_writes',short_writes)]:
            child=directory/name;child.mkdir()
            checks[name]=case(child)
    report={'status':'PASS','scope':'diagnostic implementation and preserved evidence; no repair verdict',
            'checks':checks,
            'historical_failures':{'status':'FAIL','cases':[3,7],'preserved':True},
            'new_malformed_failure':{'status':'FAIL','evidence':'../implementation/attempt-01-failure.json','replacement_proven':False,'actor_identified':False},
            'implementation_findings':[],
            'product_findings':[{'id':'SQLITE-PERSISTENCE-UNRESOLVED','severity':'P1','scope':'PRODUCT','status':'OPEN','affects_correction':True,'description':'Observed historical conversation rollback and shared-directory failures remain unresolved; no repair attribution to PR116'}],
            'not_run':['Original mobile route in original environment','Windows installation','Host-wide syscall attribution: ptrace denied','Cross-process/restart high-water durability'],
            'limitations':['Path stat samples do not identify the SQLite open file descriptor or replacing process','Observation timing and concurrent reads may require independent read verification before concluding loss','HMAC correlation and high-water marks are per observer session; caps evict old state and stop logging after declared limit','Temporary and workspace trials here share overlay device; placement is not equivalent to original synchronization semantics','First new malformed trial lost detailed steps/fixture; retained traceback proves only query failure']}
    (EVIDENCE/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'status':'PASS','product':'UNRESOLVED','independent_controls':3}))

if __name__=='__main__':
    main()
