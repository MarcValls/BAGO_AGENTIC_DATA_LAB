"""Synthetic-only persistence probe. Never opens an existing user's database.

Requires an explicit output file and explicit trial parent. Shared-directory
labels describe placement, not proof of a synchronization service.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import gc
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import types

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from src.conversations.library import ConversationStore
from src.conversations.diagnostics import ConversationDiagnostics


def run(parent, output, *, messages=500, trials=1, source=None, injection='none'):
    source_bytes = Path(source or REPO/'src/conversations/library.py').read_bytes()
    if source:
        module = types.ModuleType('src.conversations.probe_source')
        module.__package__ = 'src.conversations'
        exec(compile(source_bytes, str(source), 'exec'), module.__dict__)
        store_class = module.ConversationStore
    else:
        store_class = ConversationStore
    parent, output = Path(parent).resolve(), Path(output).resolve()
    parent.mkdir(parents=True, exist_ok=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive output prevents a later PASS from overwriting prior FAIL evidence.
    with output.open('x', encoding='utf8') as stream:
        for trial in range(trials):
            temporary = tempfile.mkdtemp(prefix='adl-sqlite-probe-', dir=parent)
            db = Path(temporary)/'synthetic.sqlite3'
            diag = None if source else ConversationDiagnostics(output.parent/'diagnostics')
            store = store_class(db) if source else store_class(db, diagnostics=diag)
            cid = store.create('assistant', 'synthetic')['id']
            snapshot = Path(temporary)/'snapshot.sqlite3'
            # Backup through SQLite; no raw read of an active database.
            with closing(sqlite3.connect(db)) as live, closing(sqlite3.connect(snapshot)) as backup:
                live.backup(backup)
            stop = threading.Event()
            errors = []
            steps = []
            step_log = output.with_name(output.name + f'.trial-{trial}.steps.jsonl').open('x', encoding='utf8')
            actor = None
            started = time.monotonic()
            initial = ConversationDiagnostics._stat(db)
            def reader():
                count = 0
                try:
                    while not stop.is_set():
                        store.get(cid); store.list(); store.work_history_metadata(); gc.collect()
                        count += 1
                except Exception as error:
                    errors.append({'reader_error_type': type(error).__name__})
                return count
            with ThreadPoolExecutor(max_workers=4) as pool:
                readers = [pool.submit(reader) for _ in range(4)] if injection == 'none' else []
                try:
                    for index in range(messages):
                        reply = store.append_message(cid, index, 'user' if index % 2 == 0 else 'assistant', 'SYNTHETIC')
                        if injection != 'none' and index == messages//2:
                            # Known child actor only. This does not model/identify the historic actor.
                            code = ('import os,sys,shutil; shutil.copy2(sys.argv[1],sys.argv[2]+".old"); os.replace(sys.argv[2]+".old",sys.argv[2])'
                                    if injection == 'replace' else
                                    'import sys,shutil; shutil.copyfile(sys.argv[1],sys.argv[2])')
                            child = subprocess.Popen([sys.executable, '-c', code, str(snapshot), str(db)])
                            actor = {'pid': child.pid, 'operation': injection, 'exit_code': child.wait(), 'expected': True}
                        got = store.get(cid)
                        with closing(sqlite3.connect(db.as_uri()+'?mode=ro', uri=True)) as check:
                            ro = tuple(check.execute('SELECT revision,(SELECT count(*) FROM messages WHERE conversation_id=?) FROM conversations WHERE id=?', (cid,cid)).fetchone())
                        steps.append({'expected': index+1, 'reply': reply['revision'], 'get': got['revision'],
                                      'messages': len(got['messages']), 'ro': ro, 'stat': ConversationDiagnostics._stat(db)})
                        step_log.write(json.dumps(steps[-1])+'\n'); step_log.flush()
                        if (got['revision'], len(got['messages'])) != (index+1,index+1) or ro != (index+1,index+1):
                            errors.append({'mismatch_step': index+1});break
                except Exception as error:
                    errors.append({'writer_error_type': type(error).__name__})
                finally:
                    stop.set()
                reader_counts = [future.result() for future in readers]
            final, integrity = None, None
            try:
                with closing(sqlite3.connect(db.as_uri()+'?mode=ro', uri=True)) as check:
                    final_row = check.execute('SELECT revision,(SELECT count(*) FROM messages WHERE conversation_id=?) FROM conversations WHERE id=?', (cid,cid)).fetchone()
                    final = tuple(final_row) if final_row else None
                    integrity = check.execute('PRAGMA integrity_check').fetchone()[0]
                    if integrity != 'ok':
                        errors.append({'integrity_check_failed': True})
            except Exception as error:
                errors.append({'final_error_type': type(error).__name__})
            step_log.close()
            if diag:
                diag.close()
            previous = initial
            replacements = []
            for step in steps:
                st = step['stat']
                if (st['st_dev'],st['st_ino']) != (previous['st_dev'],previous['st_ino']):
                    replacements.append(step['expected'])
                previous = st
            report = dict(trial=trial, parent=str(parent), python=platform.python_version(), sqlite=sqlite3.sqlite_version,
                          source_sha256=hashlib.sha256(source_bytes).hexdigest(), source_variant='supplied' if source else 'instrumented',
                          retained_fixture=temporary if errors else None,
                          injection=injection, actor=actor, status='FAIL' if errors else 'PASS', errors=errors,
                          final=final, integrity_check=integrity, initial_stat=initial, replacements=replacements,
                          reader_iterations=reader_counts, seconds=round(time.monotonic()-started,3), steps=steps,
                          diagnostics=str(diag.path.relative_to(output.parent)) if diag else None)
            stream.write(json.dumps(report)+'\n');stream.flush();os.fsync(stream.fileno())
            print(json.dumps({k:v for k,v in report.items() if k not in ('steps',)}),flush=True)
            if not errors:
                shutil.rmtree(temporary)
    return 0

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parent', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--messages', type=int, default=500)
    parser.add_argument('--trials', type=int, default=3)
    parser.add_argument('--source')
    parser.add_argument('--injection', choices=['none','replace','in-place'], default='none')
    args = parser.parse_args()
    if not 1 <= args.messages <= 1000 or not 1 <= args.trials <= 12:
        parser.error('bounded: messages 1..1000 and trials 1..12')
    sys.exit(run(args.parent,args.output,messages=args.messages,trials=args.trials,source=args.source,injection=args.injection))
