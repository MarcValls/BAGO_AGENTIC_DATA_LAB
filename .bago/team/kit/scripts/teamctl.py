#!/usr/bin/env python3
"""ADL team coordination: managed evidence, scoped handoffs and dependency gates.

Adapted from the attributed Suite derivation; see ../SOURCE_LOCK.json and LICENSE.

Local integrity and execution provenance are observable, not host authentication.
Native-host interrupts are requests requiring a host response. Arbitrary authorized
child processes may be non-cooperative; pause does not pretend to kill or undo them.
"""
from __future__ import annotations
import argparse
import contextlib
import copy
import datetime as dt
import fnmatch
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import uuid

KIT = Path(__file__).resolve().parents[1]
PROJECT = KIT.parents[2]
sys.path.insert(0, str(KIT / 'scripts'))
from team_safety import read_json, reject_links, safe_rel

VERSION = '0.3.0-adl-integrity'
IDENTITY_PATHS = (
    '.bago/team/kit/scripts/teamctl.py',
    '.bago/team/kit/scripts/team_safety.py',
    '.bago/team/kit/protocol/handoff.schema.json',
    '.bago/team/kit/protocol/work_item.schema.json',
    '.bago/team/kit/protocol/mission.schema.json',
    '.bago/team/kit/protocol/TEAM_PROTOCOL.md',
    '.bago/team/kit/protocol/COMMUNICATION.md',
    '.bago/team/kit/missions/agent-decision-inspector.json',
    '.bago/team/kit/templates/handoff-draft.example.json',
    '.bago/team/kit/SOURCE_LOCK.json',
    '.bago/team/kit/LICENSE',
    '.bago/team/kit/requirements.txt',
    'plugins/bago-agent-decision-engineering-team/scripts/teamctl.py',
)
STATE_DIR = '.bago/team/runtime'
IDENTIFIER = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,99}\Z')


class PauseRequested(RuntimeError):
    pass


def now_iso():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def canonical_bytes(data):
    return json.dumps(data, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                      allow_nan=False).encode('utf-8')


def sha256_obj(data):
    return hashlib.sha256(canonical_bytes(data)).hexdigest()


def sha256_file(path):
    reject_links(path)
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def candidate_manifest():
    rows = []
    for rel in sorted(IDENTITY_PATHS):
        path = PROJECT / rel
        reject_links(path)
        before = path.stat()
        digest = sha256_file(path)
        after = path.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise ValueError('candidate changed while hashing: ' + rel)
        rows.append({'path': rel, 'sha256': digest})
    return rows


def candidate_identity():
    return sha256_obj(candidate_manifest())


def _identifier(value):
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value) or value in ('.', '..'):
        raise ValueError('invalid identifier')
    return value


def root_path(value):
    reject_links(Path(value))
    root = Path(value).expanduser().resolve(strict=True)
    if not root.is_dir():
        raise ValueError('control root must be an existing directory')
    return root


def local_path(root, rel, *, exists=False):
    value = safe_rel(rel).as_posix()
    path = root.joinpath(*value.split('/'))
    reject_links(path)
    if not path.resolve().is_relative_to(root):
        raise ValueError('path escaped control root')
    if exists and not path.is_file():
        raise ValueError('declared file does not exist: ' + value)
    return path


def state_path(root):
    return local_path(root, STATE_DIR + '/state.json')


def write_json(path, data):
    reject_links(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    blob = canonical_bytes(data) + b'\n'
    try:
        with temp.open('xb') as stream:
            stream.write(blob)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
        if path.read_bytes() != blob:
            raise RuntimeError('persistent readback mismatch: ' + str(path))
    finally:
        if temp.exists():
            temp.unlink()


@contextlib.contextmanager
def locked(root, *, initialize=False):
    directory = local_path(root, STATE_DIR)
    if initialize:
        directory.mkdir(parents=True, exist_ok=True)
    if not directory.is_dir():
        raise ValueError('STATE_MISSING: init is required')
    path = local_path(root, STATE_DIR + '/.lock')
    with path.open('a+b') as stream:
        if os.name == 'nt':
            import msvcrt
            stream.seek(0, 2)
            if stream.tell() == 0:
                stream.write(b'0'); stream.flush()
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            if os.name == 'nt':
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def append_event(root, kind, **payload):
    path = local_path(root, STATE_DIR + '/events.jsonl')
    with path.open('ab') as stream:
        stream.write(canonical_bytes({'at': now_iso(), 'kind': kind, **payload}) + b'\n')
        stream.flush(); os.fsync(stream.fileno())


def load_state(root):
    return read_json(state_path(root))


def save_state(root, state):
    state['updated_at'] = now_iso()
    write_json(state_path(root), state)


def work_map(state):
    return {work['id']: work for work in state['mission']['work_items']}


def wildcard_prefix(pattern):
    idx = min([pattern.find(char) for char in '*?[' if char in pattern] or [len(pattern)])
    return pattern[:idx].rstrip('/')


def scopes_overlap(a, b):
    pa, pb = wildcard_prefix(a), wildcard_prefix(b)
    return not pa or not pb or pa == pb or pa.startswith(pb + '/') or pb.startswith(pa + '/')


def item_conflict(a, b):
    return any(scopes_overlap(sa, sb) for sa in a.get('write_scopes', []) for sb in b.get('write_scopes', []))


def path_matches_scope(path, scope):
    if fnmatch.fnmatchcase(path, scope):
        return True
    return not any(char in scope for char in '*?[') and path.startswith(scope.rstrip('/') + '/')


def _scope_patterns(values):
    if not isinstance(values, list) or any(not isinstance(v, str) for v in values):
        raise ValueError('scopes must be arrays of relative patterns')
    for value in values:
        safe_rel(value, glob=True)
    return values


def _allowed(work, path):
    safe_rel(path)
    if path == STATE_DIR or path.startswith(STATE_DIR + '/'):
        return False
    return any(path_matches_scope(path, scope) for scope in
               work.get('write_scopes', []) + work.get('output_scopes', []))


def _mission(mission):
    import jsonschema
    schema = read_json(KIT / 'protocol/mission.schema.json')
    jsonschema.Draft202012Validator(schema).validate(mission)
    if not isinstance(mission, dict):
        raise ValueError('mission must be an object')
    _identifier(mission.get('mission_id'))
    if mission.get('operation') not in ('AUDIT', 'REPAIR', 'VERIFICATION', 'PROMOTION'):
        raise ValueError('mission operation must be AUDIT, REPAIR, VERIFICATION or PROMOTION')
    items = mission.get('work_items')
    if not isinstance(items, list) or not items:
        raise ValueError('mission requires finite nonempty work_items')
    ids = [_identifier(work.get('id')) for work in items]
    if len(ids) != len(set(ids)):
        raise ValueError('duplicate work identifiers')
    by_id = {work['id']: work for work in items}
    for work in items:
        _identifier(work.get('role'))
        for key in ('write_scopes', 'output_scopes'):
            _scope_patterns(work.get(key, []))
        if not isinstance(work.get('depends_on', []), list):
            raise ValueError('depends_on must be a list')
        if any(dep not in by_id for dep in work.get('depends_on', [])):
            raise ValueError('unknown dependency')
        required = work.get('required_checks', [])
        if not isinstance(required, list) or len(required) != len(set(required)):
            raise ValueError('required_checks must be distinct identifiers')
        for check in required:
            _identifier(check)
        if mission['operation'] != 'AUDIT' and not required:
            raise ValueError('repair/verification/promotion work requires an execution check')
    visiting, visited = set(), set()
    def visit(wid):
        if wid in visiting:
            raise ValueError('dependency cycle')
        if wid not in visited:
            visiting.add(wid)
            for dep in by_id[wid].get('depends_on', []):
                visit(dep)
            visiting.remove(wid); visited.add(wid)
    for wid in ids:
        visit(wid)
    terminal = mission.get('terminal_work_items', [])
    if not terminal or any(wid not in by_id for wid in terminal):
        raise ValueError('terminal_work_items must identify known work')
    if mission.get('max_concurrency', 1) not in range(1, 65):
        raise ValueError('invalid max_concurrency')
    return mission


def _freeze_scope(root, mission):
    scope = mission.get('audit_scope', {})
    include = _scope_patterns(scope.get('include', []))
    exclude = _scope_patterns(scope.get('exclude', []))
    categories = {}
    for key in ('evidence_roots', 'preserved_roots', 'fixture_roots'):
        values = scope.get(key, [])
        _scope_patterns(values)
        if any(any(char in value for char in '*?[') for value in values):
            raise ValueError('evidence/preservation/fixture roots must be literal directories')
        categories[key] = values
    excluded_roots = [STATE_DIR, *sum(categories.values(), [])]
    candidates = []
    for path in sorted(root.rglob('*')):
        rel = path.relative_to(root).as_posix()
        if any(rel == prefix or rel.startswith(prefix + '/') for prefix in excluded_roots):
            continue
        if any(path_matches_scope(rel, pat) for pat in include) and not any(path_matches_scope(rel, pat) for pat in exclude):
            reject_links(path)
            if path.is_file():
                candidates.append({'path': rel, 'sha256': sha256_file(path)})
    if mission['operation'] == 'AUDIT' and not candidates:
        raise ValueError('AUDIT requires a nonempty frozen candidate scope')
    return {'include': include, 'exclude': exclude, **categories, 'candidates': candidates,
            'round': 1, 'automatic_rounds': False}


def _identity(state):
    if state.get('protocol_version') != VERSION:
        raise ValueError('LEGACY_UNVERIFIED: historical state is readable but cannot satisfy modern gates; initialize a new explicit mission')
    if sha256_obj(state['mission']) != state['mission_contract_sha256']:
        raise ValueError('mission contract identity changed')
    if set(work_map(state)) != set(state['work_status']):
        raise ValueError('work status identity mismatch')
    _mission(state['mission'])
    if sha256_obj(state['frozen_scope']) != state['scope_sha256']:
        raise ValueError('frozen scope identity changed')
    if state['candidate_id'] != candidate_identity():
        raise ValueError('candidate identity changed; use a new explicitly initialized mission')


def _active(state):
    if state['lifecycle'] == 'PAUSED':
        raise PauseRequested('mission is persistently paused; explicit resume is required')
    if state['lifecycle'] != 'ACTIVE':
        raise ValueError('mission is closed')
    _identity(state)


def handoff_payload_hash(handoff):
    data = copy.deepcopy(handoff)
    data.pop('payload_sha256', None)
    return sha256_obj(data)


def _validate_execution(root, state, wid, entry):
    if entry['result'] == 'NOT_RUN':
        return
    eid = entry.get('execution_id')
    saved = state['executions'].get(eid)
    if not saved or saved.get('work_id') != wid or saved.get('state') != 'COMPLETED':
        raise ValueError('verification has no completed managed execution')
    matching = [(key, item) for key, item in state['executions'].items()
                if item.get('work_id') == wid and item.get('check_id') == entry['id']]
    if matching and max(matching, key=lambda pair: pair[1]['started_at'])[0] != eid:
        raise ValueError('verification is superseded by a later execution of this check')
    path = local_path(root, saved['path'], exists=True)
    if sha256_file(path) != saved['sha256']:
        raise ValueError('managed execution receipt changed')
    receipt = read_json(path)
    expected = {'execution_id': eid, 'mission_id': state['mission']['mission_id'],
                'candidate_id': state['candidate_id'], 'scope_sha256': state['scope_sha256'],
                'work_id': wid, 'check_id': entry['id'], 'command_text': entry['command']}
    if any(receipt.get(key) != value for key, value in expected.items()):
        raise ValueError('managed execution identity or command mismatch')
    if canonical_bytes(receipt['command_argv']).decode('utf-8') != receipt['command_text']:
        raise ValueError('execution argv/text mismatch')
    if saved.get('result') != receipt.get('result'):
        raise ValueError('execution result registration mismatch')
    if entry['evidence'] != saved['path'] or entry['result'] != receipt.get('result'):
        raise ValueError('verification does not match its managed receipt')
    if receipt['result'] == 'PASS' and (receipt['returncode'] != 0 or receipt['paused_during_execution'] or receipt['timed_out'] or receipt['spawn_error'] or receipt['output_errors']):
        raise ValueError('false successful execution receipt')
    if receipt['candidate_before'] != state['candidate_id'] or receipt['candidate_after'] != state['candidate_id']:
        raise ValueError('execution candidate changed')
    for item in receipt['logs'] + receipt['outputs']:
        path = local_path(root, item['path'], exists=True)
        if sha256_file(path) != item['sha256']:
            raise ValueError('execution output or log changed: ' + item['path'])


def validate_handoff_evidence(root, handoff, *, state, wid):
    work = work_map(state)[wid]
    for output in handoff['outputs']:
        if not _allowed(work, output['path']):
            raise ValueError('output outside declared work scope')
        path = local_path(root, output['path'], exists=True)
        if sha256_file(path) != output['sha256']:
            raise ValueError('output sha256 mismatch: ' + output['path'])
    ids = []
    for entry in handoff['verification']:
        if entry['result'] == 'FAIL':
            raise ValueError('verification contains FAIL')
        ids.append(entry['id'])
        _validate_execution(root, state, wid, entry)
    if len(ids) != len(set(ids)):
        raise ValueError('duplicate verification identifiers')
    entries = {entry['id']: entry for entry in handoff['verification']}
    for check in work.get('required_checks', []):
        if check not in entries or entries[check]['result'] != 'PASS':
            raise ValueError('required execution did not PASS: ' + check)


def _handoff(root, state, wid, handoff):
    import jsonschema
    schema = read_json(Path(__file__).resolve().parents[1] / 'protocol/handoff.schema.json')
    jsonschema.Draft202012Validator(schema).validate(handoff)
    work = work_map(state)[wid]
    expected = {'work_id': wid, 'role': work['role'], 'status': 'DONE',
                'mission_id': state['mission']['mission_id'], 'candidate_id': state['candidate_id'],
                'scope_sha256': state['scope_sha256']}
    if any(handoff[key] != value for key, value in expected.items()):
        raise ValueError('handoff mission/candidate/work/scope identity mismatch')
    if handoff['payload_sha256'] != handoff_payload_hash(handoff):
        raise ValueError('payload_sha256 mismatch')
    for path in handoff['changed_files']:
        local_path(root, path)
        if path == STATE_DIR or path.startswith(STATE_DIR + '/'):
            raise ValueError('changed file targets reserved control storage')
        if not any(path_matches_scope(path, scope) for scope in work.get('write_scopes', [])):
            raise ValueError('changed file outside writable scope')
    known = work_map(state)
    if any(consumer not in known or wid not in known[consumer].get('depends_on', []) for consumer in handoff['next_consumers']):
        raise ValueError('next consumer is not a declared dependent work')
    frozen = {row['path'] for row in state['frozen_scope']['candidates']}
    if any(path not in frozen for path in handoff.get('reviewed_paths', [])):
        raise ValueError('reviewed path not in frozen candidates')
    validate_handoff_evidence(root, handoff, state=state, wid=wid)


def validate_handoff(root, state, wid):
    saved = state['work_status'][wid].get('handoff')
    if not saved:
        raise ValueError('completed work has no registered handoff')
    path = local_path(root, saved['path'], exists=True)
    if sha256_file(path) != saved['sha256']:
        raise ValueError('persisted handoff file changed')
    handoff = read_json(path)
    _handoff(root, state, wid, handoff)
    return handoff


def _dependencies(root, state, wid):
    for dep in work_map(state)[wid].get('depends_on', []):
        if state['work_status'][dep]['status'] != 'DONE':
            raise ValueError('dependency is not DONE: ' + dep)
        validate_handoff(root, state, dep)
        _dependencies(root, state, dep)


def refresh_ready(state):
    for work in state['mission']['work_items']:
        status = state['work_status'][work['id']]
        if status['status'] in ('PENDING', 'READY'):
            status['status'] = 'READY' if all(state['work_status'][dep]['status'] == 'DONE'
                for dep in work.get('depends_on', [])) else 'PENDING'


def _ready(root, state):
    refresh_ready(state)
    ready = []
    for work in state['mission']['work_items']:
        if state['work_status'][work['id']]['status'] == 'READY':
            _dependencies(root, state, work['id'])
            ready.append(work)
    return ready


def safe_batches(ready, max_concurrency):
    remaining, batches = list(ready), []
    while remaining:
        batch, kept = [], []
        for work in remaining:
            (batch if len(batch) < max_concurrency and all(not item_conflict(work, other) for other in batch) else kept).append(work)
        batches.append([work['id'] for work in batch]); remaining = kept
    return batches


def checkpoint(root, work_id, stage):
    root = root_path(root)
    with locked(root):
        state = load_state(root)
        if work_id not in work_map(state):
            raise ValueError('unknown checkpoint work')
        if state['lifecycle'] == 'PAUSED':
            for execution in state['executions'].values():
                if execution['work_id'] == work_id and execution['state'] == 'RUNNING':
                    execution['pause_observed'] = True
            state['work_status'][work_id]['last_paused_stage'] = str(stage)
            save_state(root, state)
            raise PauseRequested('paused before stage ' + str(stage))
        _active(state)
        if state['work_status'][work_id]['status'] != 'CLAIMED':
            raise ValueError('checkpoint requires CLAIMED work')
        _dependencies(root, state, work_id)


def _verify(root, state):
    _identity(state)
    _mission(state['mission'])
    if any(item['state'] in ('STARTING', 'RUNNING') for item in state['executions'].values()):
        raise ValueError('a managed execution is in-flight or its termination is unconfirmed')
    for wid, status in state['work_status'].items():
        if status['status'] in ('CLAIMED', 'DONE'):
            _dependencies(root, state, wid)
        if status['status'] == 'DONE':
            validate_handoff(root, state, wid)
    if state['mission']['operation'] in ('AUDIT', 'VERIFICATION'):
        for row in state['frozen_scope']['candidates']:
            if sha256_file(local_path(root, row['path'], exists=True)) != row['sha256']:
                raise ValueError('frozen candidate changed: ' + row['path'])
    claimed = [wid for wid, status in state['work_status'].items() if status['status'] == 'CLAIMED']
    wm = work_map(state)
    for idx, wid in enumerate(claimed):
        for other in claimed[idx + 1:]:
            if item_conflict(wm[wid], wm[other]):
                raise ValueError('active writable scope conflict')


def _run_check(root, args):
    with locked(root):
        state = load_state(root); _active(state)
        wid = args.work_id
        work = work_map(state).get(wid)
        if not work or state['work_status'][wid]['status'] != 'CLAIMED':
            raise ValueError('run-check requires CLAIMED work')
        _dependencies(root, state, wid)
        _identifier(args.check_id)
        if not args.allow_execute:
            raise ValueError('run-check requires explicit --allow-execute')
        argv = json.loads(args.command_json)
        if not isinstance(argv, list) or not argv or any(not isinstance(s, str) or not s or '\x00' in s for s in argv):
            raise ValueError('command-json must be a nonempty argv array')
        if not 1 <= args.timeout <= 3600:
            raise ValueError('timeout must be between 1 and 3600 seconds')
        for output in args.output:
            local_path(root, output)
            if not _allowed(work, output):
                raise ValueError('execution output outside work scope')
        if len(args.output) != len(set(args.output)):
            raise ValueError('duplicate declared execution outputs')
        if any(e['work_id'] == wid and e['state'] in ('STARTING', 'RUNNING') for e in state['executions'].values()):
            raise ValueError('work already has an in-flight managed execution')
        eid = uuid.uuid4().hex
        directory = STATE_DIR + '/executions/' + eid
        local_path(root, directory).mkdir(parents=True)
        receipt_rel = directory + '/receipt.json'
        before = candidate_identity()
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONIOENCODING='utf-8')
        for key in ('PYTHONPATH', 'PYTHONHOME', 'PYTHONSTARTUP'):
            env.pop(key, None)
        # Spawn while holding the short control lock: a pause committed first
        # prevents spawning. The lock is released during the long operation.
        # Persist the attempt before starting any child. Storage failure here
        # must produce zero child operations, rather than an unregistered run.
        state['executions'][eid] = {'state': 'STARTING', 'work_id': wid, 'pid': None,
            'check_id': args.check_id, 'path': receipt_rel, 'started_at': now_iso(), 'pause_observed': False}
        save_state(root, state)
        spawn_error = None
        try:
            process = subprocess.Popen(argv, cwd=root, env=env, stdin=subprocess.DEVNULL,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False)
        except OSError as exc:
            process = None
            spawn_error = f'{type(exc).__name__}: {exc}'
        state['executions'][eid].update(state='RUNNING', pid=process.pid if process else None)
        try:
            save_state(root, state)
        except Exception as exc:
            # A child may already have effects. Stop only the actual immediate
            # child if possible, report its real PID/outcome, and never report
            # PASS, guaranteed descendant cancellation or rollback.
            outcome = 'NO_CHILD_STARTED'
            if process is not None:
                try:
                    process.terminate()
                    process.communicate(timeout=5)
                    outcome = 'IMMEDIATE_CHILD_EXITED:' + str(process.returncode)
                except Exception:
                    outcome = 'CHILD_STOP_NOT_CONFIRMED'
            state['executions'][eid].update(state='REGISTRATION_FAILED',
                registration_error=str(exc), child_stop_outcome=outcome)
            try:
                save_state(root, state)
            except Exception:
                pass  # The persisted STARTING intent remains an explicit blocker.
            raise RuntimeError(f'execution registration persistence failed; execution_id={eid}; '
                               f'pid={process.pid if process else None}; stop={outcome}; '
                               'prior effects and descendants are not rolled back') from exc
        append_event(root, 'EXECUTION_STARTED' if process else 'EXECUTION_SPAWN_FAILED',
                     execution_id=eid, work_id=wid, pid=process.pid if process else None)
    timed_out = False
    if process is None:
        stdout, stderr = b'', spawn_error.encode('utf-8')
    else:
        try:
            stdout, stderr = process.communicate(timeout=args.timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            process.kill()
            stdout, stderr = process.communicate()
    with locked(root):
        state = load_state(root)
        saved = state['executions'][eid]
        paused = state['lifecycle'] != 'ACTIVE' or saved.get('pause_observed', False) or saved.get('pause_requested', False)
        logs = []
        for name, blob in (('stdout', stdout), ('stderr', stderr)):
            rel = directory + '/' + name + '.log'
            path = local_path(root, rel)
            with path.open('xb') as stream:
                stream.write(blob); stream.flush(); os.fsync(stream.fileno())
            logs.append({'path': rel, 'sha256': sha256_file(path)})
        outputs, errors = [], []
        for rel in args.output:
            try:
                outputs.append({'path': rel, 'sha256': sha256_file(local_path(root, rel, exists=True))})
            except (OSError, ValueError) as exc:
                errors.append(str(exc))
        after = candidate_identity()
        returncode = process.returncode if process else None
        result = 'PASS' if returncode == 0 and not timed_out and not errors and not paused and before == after == state['candidate_id'] else 'FAIL'
        receipt = {'execution_id': eid, 'mission_id': state['mission']['mission_id'],
            'candidate_id': state['candidate_id'], 'scope_sha256': state['scope_sha256'],
            'candidate_before': before, 'candidate_after': after, 'work_id': wid,
            'check_id': args.check_id, 'command_argv': argv, 'command_text': canonical_bytes(argv).decode('utf-8'),
            'returncode': returncode, 'spawn_error': spawn_error, 'result': result, 'timed_out': timed_out,
            'paused_during_execution': paused, 'logs': logs, 'outputs': outputs,
            'output_errors': errors, 'started_at': saved['started_at'], 'finished_at': now_iso(),
            'non_cooperative_boundary': 'pause requests do not automatically kill arbitrary child processes'}
        write_json(local_path(root, receipt_rel), receipt)
        saved.update(state='COMPLETED', sha256=sha256_file(local_path(root, receipt_rel)), result=result)
        save_state(root, state)
        append_event(root, 'EXECUTION_COMPLETED', execution_id=eid, result=result)
        entry = {'id': args.check_id, 'command': receipt['command_text'], 'result': result,
                 'evidence': receipt_rel, 'execution_id': eid}
        return {'status': 'INCONCLUSIVE' if paused else result, 'verification': entry,
                'execution_id': eid, 'receipt': receipt_rel, 'returncode': returncode,
                'outputs': outputs, 'paused_during_execution': paused}


def _dispatch(args):
    root = root_path(args.root)
    if args.cmd == 'identity':
        return {'status': 'PASS', 'candidate_id': candidate_identity(),
                'manifest': candidate_manifest(), 'identity_kind': 'ADL_TEAMCTL_IMPLEMENTATION'}
    if args.cmd in ('status', 'inspect'):
        # Passive historical inspection must not create a lock or rewrite state.
        state = load_state(root)
        legacy = state.get('protocol_version') != VERSION
        label = 'LEGACY_UNVERIFIED' if legacy else 'INTEGRITY_NOT_REQUESTED'
        if args.cmd == 'status':
            return {'status': 'PASS', 'state': state, 'evidence_classification': label,
                    'candidate_current': candidate_identity(), 'read_only': True}
        work = work_map(state).get(args.work_id)
        if not work:
            raise ValueError('unknown work id')
        if not legacy:
            _identity(state)
            _dependencies(root, state, args.work_id)
            if state['work_status'][args.work_id]['status'] == 'DONE':
                validate_handoff(root, state, args.work_id)
        return {'status': 'PASS', 'work': work, 'runtime': state['work_status'][args.work_id],
                'mission_id': state['mission']['mission_id'],
                'candidate_id': state.get('candidate_id'), 'scope_sha256': state.get('scope_sha256'),
                'evidence_classification': label, 'read_only': True}
    if args.cmd != 'init':
        preliminary = load_state(root)
        if preliminary.get('protocol_version') != VERSION:
            _identity(preliminary)  # Reject legacy gates before even creating a lock.
    if args.cmd == 'run-check':
        return _run_check(root, args)
    with locked(root, initialize=args.cmd == 'init'):
        if args.cmd == 'init':
            if state_path(root).exists():
                raise ValueError('STATE_EXISTS: init never overwrites a mission')
            mission_path = Path(args.mission).resolve(strict=True)
            mission = _mission(read_json(mission_path))
            frozen = _freeze_scope(root, mission)
            status = {work['id']: {'status': 'READY' if not work.get('depends_on') else 'PENDING',
                                  'agent': None, 'claimed_at': None, 'done_at': None}
                      for work in mission['work_items']}
            state = {'protocol_version': VERSION, 'created_at': now_iso(),
                'mission_source': str(mission_path), 'mission_sha256': sha256_file(mission_path),
                'mission': mission, 'work_status': status, 'terminal_gate': 'OPEN',
                'candidate_id': candidate_identity(), 'candidate_manifest': candidate_manifest(),
                'mission_contract_sha256': sha256_obj(mission), 'scope_sha256': sha256_obj(frozen),
                'frozen_scope': frozen, 'lifecycle': 'ACTIVE', 'task_state': 'ACTIVE',
                'product_state': 'UNASSESSED', 'evidence_state': 'PENDING',
                'executions': {}, 'interruptions': [], 'pause_history': []}
            save_state(root, state)
            append_event(root, 'MISSION_INIT', mission_id=mission['mission_id'])
            return {'status': 'PASS', 'state': state}
        state = load_state(root)
        _identity(state)
        if args.cmd == 'status':
            return {'status': 'PASS', 'state': state, 'candidate_current': candidate_identity()}
        if args.cmd == 'verify':
            _verify(root, state)
            return {'status': 'PASS', 'lifecycle': state['lifecycle'], 'terminal_gate': state['terminal_gate'],
                    'claim': 'registered evidence integrity and dependency contract only'}
        if args.cmd == 'inspect':
            work = work_map(state).get(args.work_id)
            if not work:
                raise ValueError('unknown work id')
            return {'status': 'PASS', 'work': work, 'runtime': state['work_status'][args.work_id],
                    'mission_id': state['mission']['mission_id'], 'candidate_id': state['candidate_id'],
                    'scope_sha256': state['scope_sha256']}
        if args.cmd == 'pause':
            if state['lifecycle'] == 'CLOSED':
                raise ValueError('closed mission cannot be paused')
            if state['lifecycle'] != 'PAUSED':
                state['lifecycle'] = 'PAUSED'; state['task_state'] = 'PAUSED'
                request_id = uuid.uuid4().hex
                request = {'id': request_id, 'at': now_iso(), 'reason': args.reason, 'requests': []}
                for wid, status in state['work_status'].items():
                    if status['status'] == 'CLAIMED':
                        item = {'work_id': wid, 'host_handle': status.get('host_handle'),
                                'status': 'INTERRUPTION_REQUESTED', 'outcome': None}
                        request['requests'].append(item)
                state['interruptions'].append(request)
                state['pause_history'].append(request_id)
                for execution in state['executions'].values():
                    if execution['state'] in ('STARTING', 'RUNNING'):
                        execution['pause_requested'] = True
                save_state(root, state); append_event(root, 'PAUSED', request_id=request_id)
            return {'status': 'PASS', 'lifecycle': 'PAUSED', 'interruptions': state['interruptions'],
                    'inflight_operations': [{'execution_id': eid, 'work_id': item['work_id'],
                                             'pid': item.get('pid'), 'interruption': 'NOT_GUARANTEED'}
                                            for eid, item in state['executions'].items() if item['state'] in ('STARTING', 'RUNNING')],
                    'host_interrupts': 'REQUESTED_NOT_EXECUTED_BY_THIS_PACK', 'effects_rolled_back': False}
        if args.cmd == 'resume':
            if not args.explicit or state['lifecycle'] != 'PAUSED':
                raise ValueError('resume requires --explicit and PAUSED state')
            _identity(state)
            state['lifecycle'] = 'ACTIVE'; state['task_state'] = 'ACTIVE'
            save_state(root, state); append_event(root, 'EXPLICIT_RESUME')
            return {'status': 'PASS', 'lifecycle': 'ACTIVE'}
        if args.cmd == 'ack-stop':
            if state['lifecycle'] != 'PAUSED':
                raise ValueError('stop acknowledgement requires PAUSED state')
            path = local_path(root, args.evidence, exists=True)
            found = False
            for interruption in state['interruptions']:
                for item in interruption['requests']:
                    if item['work_id'] == args.work_id and item['outcome'] is None:
                        item.update(outcome=args.outcome, status='HOST_ACKNOWLEDGED',
                                    evidence={'path': args.evidence, 'sha256': sha256_file(path)})
                        found = True
            if not found:
                raise ValueError('no pending interruption request for work')
            save_state(root, state)
            return {'status': 'PASS', 'outcome': args.outcome, 'host_authentication': 'NOT_PROVIDED'}
        _active(state)
        if args.cmd in ('ready', 'pair', 'continue'):
            ready = _ready(root, state)
            return {'status': 'PASS', 'ready': [w['id'] for w in ready],
                    'batches': safe_batches(ready, state['mission'].get('max_concurrency', 1)),
                    'round': state['frozen_scope']['round'], 'automatic_rounds': False}
        if args.cmd == 'note':
            agents = {v.get('agent') for v in state['work_status'].values()}
            if args.from_agent not in agents:
                raise ValueError('UNKNOWN_FROM_AGENT')
            append_event(root, 'COORDINATION_NOTE', from_agent=args.from_agent, to_agent=args.to_agent, note_kind=args.kind, text=args.text)
            return {'status': 'PASS'}
        if args.cmd == 'claim':
            ready = {work['id']: work for work in _ready(root, state)}
            if args.work_id not in ready:
                raise ValueError('work is not READY')
            _identifier(args.agent)
            claimed = [wid for wid, status in state['work_status'].items() if status['status'] == 'CLAIMED']
            if len(claimed) >= state['mission'].get('max_concurrency', 1):
                raise ValueError('mission concurrency bound reached')
            wm = work_map(state)
            if any(item_conflict(ready[args.work_id], wm[wid]) for wid in claimed):
                raise ValueError('writable scopes overlap active work')
            state['work_status'][args.work_id].update(status='CLAIMED', agent=args.agent,
                claimed_at=now_iso(), host_handle=args.host_handle)
            save_state(root, state); append_event(root, 'CLAIM', work_id=args.work_id, agent=args.agent)
            return {'status': 'PASS', 'work_id': args.work_id}
        if args.cmd == 'handoff':
            wid = args.work_id
            if wid not in work_map(state) or state['work_status'][wid]['status'] != 'CLAIMED':
                raise ValueError('handoff requires CLAIMED work')
            _dependencies(root, state, wid)
            handoff = read_json(Path(args.file).resolve(strict=True))
            _handoff(root, state, wid, handoff)
            rel = STATE_DIR + '/handoffs/' + wid + '.json'
            path = local_path(root, rel)
            if path.exists():
                raise ValueError('handoff identity already exists; silent replacement forbidden')
            write_json(path, handoff)
            state['work_status'][wid].update(status='DONE', done_at=now_iso(),
                                            handoff={'path': rel, 'sha256': sha256_file(path)})
            refresh_ready(state)
            state['terminal_gate'] = 'ADMINISTRATIVE_DONE' if all(
                state['work_status'][item]['status'] == 'DONE' for item in state['mission']['terminal_work_items']) else 'OPEN'
            save_state(root, state); append_event(root, 'HANDOFF_DONE', work_id=wid)
            return {'status': 'PASS', 'work_id': wid, 'terminal_gate': state['terminal_gate'],
                    'product_validation': 'NOT_IMPLIED'}
        if args.cmd == 'close':
            _verify(root, state)
            if any(item['status'] != 'DONE' for item in state['work_status'].values()):
                raise ValueError('all mission work must be DONE before closure')
            handoffs = [validate_handoff(root, state, wid) for wid in work_map(state)]
            findings = [finding for handoff in handoffs for finding in handoff.get('findings', [])]
            operation = state['mission']['operation']
            blocking = [f for f in findings if f['status'] == 'OPEN' and f['severity'] in ('P0', 'P1') and
                        (f['scope'] in ('EVIDENCE', 'COVERAGE') or operation != 'AUDIT' and f.get('affects_correction', True))]
            if blocking:
                raise ValueError('applicable findings block closure: ' + ','.join(f['id'] for f in blocking))
            if operation == 'AUDIT':
                reviewed = {p for handoff in handoffs for p in handoff.get('reviewed_paths', [])}
                expected = {row['path'] for row in state['frozen_scope']['candidates']}
                if reviewed != expected:
                    raise ValueError('frozen audit coverage is incomplete')
            if operation == 'PROMOTION' and not state['mission'].get('destination'):
                raise ValueError('promotion requires an explicit destination and its applicable gates')
            state.update(lifecycle='CLOSED', task_state='CLOSED', evidence_state='VERIFIED',
                         product_state='FINDINGS_REPORTED' if operation == 'AUDIT' else 'SCOPED_ACCEPTANCE_PASSED',
                         terminal_gate='VALIDATED_AUDIT_SCOPE' if operation == 'AUDIT' else 'VALIDATED_SCOPED_TASK')
            save_state(root, state); append_event(root, 'MISSION_CLOSED', operation=operation)
            return {'status': 'PASS', 'task_state': state['task_state'], 'product_state': state['product_state'],
                    'terminal_gate': state['terminal_gate'], 'deployment': 'NOT_RUN'}
        raise ValueError('unsupported command')


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', default='.')
    sub = p.add_subparsers(dest='cmd', required=True)
    init = sub.add_parser('init'); init.add_argument('--mission', required=True)
    for name in ('identity', 'status', 'ready', 'pair', 'continue', 'verify', 'close'):
        sub.add_parser(name)
    note = sub.add_parser('note')
    note.add_argument('--from-agent', required=True); note.add_argument('--to-agent', required=True)
    note.add_argument('--kind', choices=('INFO', 'BLOCKER', 'CONTRACT', 'RISK', 'QUESTION'), required=True)
    note.add_argument('--text', required=True)
    claim = sub.add_parser('claim'); claim.add_argument('work_id'); claim.add_argument('--agent', required=True)
    claim.add_argument('--host-handle')
    handoff = sub.add_parser('handoff'); handoff.add_argument('work_id'); handoff.add_argument('--file', required=True)
    inspect = sub.add_parser('inspect'); inspect.add_argument('work_id')
    pause = sub.add_parser('pause'); pause.add_argument('--reason', required=True)
    resume = sub.add_parser('resume'); resume.add_argument('--explicit', action='store_true')
    check = sub.add_parser('run-check'); check.add_argument('work_id'); check.add_argument('--check-id', required=True)
    check.add_argument('--command-json', required=True); check.add_argument('--output', action='append', default=[])
    check.add_argument('--allow-execute', action='store_true'); check.add_argument('--timeout', type=int, default=60)
    ack = sub.add_parser('ack-stop'); ack.add_argument('work_id')
    ack.add_argument('--outcome', choices=('STOPPED', 'NON_INTERRUPTIBLE'), required=True)
    ack.add_argument('--evidence', required=True)
    return p


def run(argv):
    try:
        return _dispatch(parser().parse_args(argv))
    except PauseRequested as exc:
        return {'status': 'INCONCLUSIVE', 'lifecycle': 'PAUSED', 'reason': str(exc)}
    except (Exception, SystemExit) as exc:
        return {'status': 'FAIL', 'reason': str(exc), 'exception': type(exc).__name__}


def main(argv=None):
    result = run(sys.argv[1:] if argv is None else argv)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['status'] == 'PASS' else 3 if result['status'] == 'INCONCLUSIVE' else 1


if __name__ == '__main__':
    raise SystemExit(main())
