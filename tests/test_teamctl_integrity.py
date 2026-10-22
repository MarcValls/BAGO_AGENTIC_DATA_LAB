"""Actual-entry integration checks; also runnable without pytest via --candidate.

Only fresh synthetic coordination roots are written. No service/model is used.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import traceback


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical(value) + b'\n')


class Harness:
    def __init__(self, candidate, artifacts):
        self.candidate = Path(candidate).resolve()
        self.artifacts = Path(artifacts).resolve()
        self.artifacts.mkdir(parents=True, exist_ok=False)
        self.cli = self.candidate / '.bago/team/kit/scripts/teamctl.py'
        self.calls = []
        self.cases = []
        self.identity = self.call(self.artifacts, 'identity')['candidate_id']

    def call(self, root, *args, success=True, wrapper=False):
        cli = self.candidate / 'plugins/bago-agent-decision-engineering-team/scripts/teamctl.py' if wrapper else self.cli
        argv = [sys.executable, '-B', str(cli), '--root', str(root), *args]
        result = subprocess.run(argv, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=40)
        row = {'argv': argv, 'exit_code': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr}
        self.calls.append(row)
        value = json.loads(result.stdout)
        assert (result.returncode == 0) is success, row
        assert (value['status'] == 'PASS') is success, row
        return value

    def state(self, root):
        return json.loads((root / '.bago/team/runtime/state.json').read_bytes())

    def setup(self, name):
        root = self.artifacts / name
        root.mkdir()
        mission = {'mission_id': 'CLI_' + name, 'operation': 'REPAIR', 'max_concurrency': 2,
                   'terminal_work_items': ['C'], 'work_items': []}
        for wid, deps in [('P', []), ('C', ['P'])]:
            mission['work_items'].append({'id': wid, 'role': 'local-reviewer', 'title': wid,
                'depends_on': deps, 'write_scopes': [f'products/{wid}/**'],
                'output_scopes': [f'products/{wid}/**'], 'required_checks': ['acceptance']})
        write_json(root / 'mission.json', mission)
        self.call(root, 'init', '--mission', str(root / 'mission.json'))
        self.call(root, 'claim', 'P', '--agent', 'producer')
        self.call(root, 'note', '--from-agent', 'producer', '--to-agent', 'root', '--kind', 'INFO', '--text', 'synthetic local check')
        return root

    def run_check(self, root, wid='P', code=None, success=True):
        rel = f'products/{wid}/result.txt'
        if code is None:
            code = f"from pathlib import Path;p=Path({rel!r});p.parent.mkdir(parents=True,exist_ok=True);p.write_text('observed bytes',encoding='utf-8');print('executed')"
        return self.call(root, 'run-check', wid, '--check-id', 'acceptance', '--command-json',
                         json.dumps([sys.executable, '-B', '-c', code]), '--output', rel, '--allow-execute', success=success)

    def draft(self, root, check, wid='P'):
        view = self.call(root, 'inspect', wid)
        value = {'work_id': wid, 'role': 'local-reviewer', 'status': 'DONE',
                 'mission_id': view['mission_id'], 'candidate_id': view['candidate_id'], 'scope_sha256': view['scope_sha256'],
                 'changed_files': [f'products/{wid}/result.txt'],
                 'outputs': [{'id': wid + '-output', 'path': f'products/{wid}/result.txt',
                              'sha256': digest(root / f'products/{wid}/result.txt'), 'frozen': True}],
                 'verification': [check['verification']], 'residual_risks': [], 'next_consumers': ['C'] if wid == 'P' else []}
        return value

    def handoff(self, root, draft, success=True):
        value = copy.deepcopy(draft)
        value.pop('payload_sha256', None)
        value['payload_sha256'] = hashlib.sha256(canonical(value)).hexdigest()
        write_json(root / 'draft.json', value)
        before = (root / '.bago/team/runtime/state.json').read_bytes()
        result = self.call(root, 'handoff', value.get('work_id', 'P'), '--file', str(root / 'draft.json'), success=success)
        if not success:
            assert before == (root / '.bago/team/runtime/state.json').read_bytes(), 'rejected handoff changed state'
            assert not (root / '.bago/team/runtime/handoffs' / (value.get('work_id', 'P') + '.json')).exists()
        return result

    def record(self, name, function):
        start = len(self.calls)
        try:
            details = function()
            self.cases.append({'case': name, 'result': 'PASS', 'details': details, 'calls': self.calls[start:]})
        except Exception:
            self.cases.append({'case': name, 'result': 'FAIL', 'traceback': traceback.format_exc(), 'calls': self.calls[start:]})

    def positive(self):
        root = self.setup('positive')
        check = self.run_check(root)
        self.handoff(root, self.draft(root, check))
        self.call(root, 'verify')  # Every call is a new coordinator process.
        self.call(root, 'claim', 'C', '--agent', 'consumer', wrapper=True)
        check = self.run_check(root, 'C')
        self.handoff(root, self.draft(root, check, 'C'))
        self.call(root, 'verify', wrapper=True)
        self.call(root, 'close')
        return {'accepted_and_consumed': True, 'fresh_cli_processes': True}

    def negative_handoffs(self):
        root = self.setup('invalid_drafts')
        check = self.run_check(root)
        draft = self.draft(root, check)
        mutations = {}
        def add(name, mutator):
            value = copy.deepcopy(draft); mutator(value); mutations[name] = value
        add('missing_output', lambda v: v['outputs'][0].update(path='products/P/absent.txt'))
        add('wrong_hash', lambda v: v['outputs'][0].update(sha256='0' * 64))
        add('uppercase_hash', lambda v: v['outputs'][0].update(sha256=v['outputs'][0]['sha256'].upper()))
        add('null_hash', lambda v: v['outputs'][0].update(sha256=None))
        outside = root / 'other/result.txt'; outside.parent.mkdir(); outside.write_bytes(b'observed bytes')
        add('outside_scope', lambda v: v['outputs'][0].update(path='other/result.txt'))
        add('output_directory', lambda v: v['outputs'][0].update(path='products/P'))
        for name, path in [('traversal', '../outside.txt'), ('absolute', str(root / 'products/P/result.txt')),
                           ('unc', '//server/share/file'), ('backslash', 'products\\P\\result.txt'),
                           ('ads', 'products/P/result.txt:stream'), ('device', 'products/P/NUL'),
                           ('dot', './products/P/result.txt'), ('emptysegment', 'products//P/result.txt')]:
            add(name, lambda v, path=path: v['outputs'][0].update(path=path))
        for key in ('work_id', 'role', 'status', 'mission_id', 'candidate_id', 'scope_sha256', 'changed_files', 'outputs', 'verification', 'residual_risks', 'next_consumers'):
            add('missing_' + key, lambda v, key=key: v.pop(key))
        for key in ('command', 'result', 'evidence', 'execution_id', 'id'):
            add('verification_missing_' + key, lambda v, key=key: v['verification'][0].pop(key))
        add('extra_field', lambda v: v.update(unexpected=True))
        add('wrong_type', lambda v: v.update(outputs={}))
        add('empty_command', lambda v: v['verification'][0].update(command=' '))
        add('other_mission', lambda v: v.update(mission_id='OTHER_MISSION'))
        add('other_candidate', lambda v: v.update(candidate_id='1' * 64))
        add('other_scope', lambda v: v.update(scope_sha256='2' * 64))
        add('not_run', lambda v: v['verification'][0].update(result='NOT_RUN', evidence=None, execution_id=None))
        add('typed_without_receipt', lambda v: v['verification'][0].update(execution_id='invented', evidence='products/P/result.txt'))
        add('typed_wrong_command', lambda v: v['verification'][0].update(command='python never-executed.py'))
        add('wrong_check_id', lambda v: v['verification'][0].update(id='different'))
        add('changed_outside_scope', lambda v: v.update(changed_files=['other/file.txt']))
        add('output_missing_digest', lambda v: v['outputs'][0].pop('sha256'))
        add('output_extra_field', lambda v: v['outputs'][0].update(extra='forbidden'))
        for name, value in mutations.items():
            self.handoff(root, value, success=False)
        # Strict JSON rejects duplicate keys before even accepting the structure.
        raw = canonical(draft).decode()
        (root / 'duplicate.json').write_text(raw[:-1] + ',"work_id":"P"}', encoding='utf-8')
        self.call(root, 'handoff', 'P', '--file', str(root / 'duplicate.json'), success=False)
        # A link remains forbidden even when its target is the correct allowed file.
        link = root / 'products/P/link.txt'
        link_status = 'NOT_AVAILABLE'
        try:
            link.symlink_to(root / 'products/P/result.txt')
        except (OSError, NotImplementedError) as exc:
            link_status = type(exc).__name__ + ': ' + str(exc)
        else:
            value = copy.deepcopy(draft); value['outputs'][0]['path'] = 'products/P/link.txt'
            self.handoff(root, value, success=False); link_status = 'REJECTED'
        reparse_status = 'NOT_APPLICABLE'
        if os.name == 'nt':
            junction = root / 'products/P/junction'
            command = ['cmd', '/d', '/c', 'mklink', '/J', str(junction), str(outside.parent)]
            result = subprocess.run(command, capture_output=True, text=True, errors='replace')
            self.calls.append({'argv': command, 'exit_code': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr})
            assert result.returncode == 0, 'Windows junction fixture could not be created: ' + result.stderr
            value = copy.deepcopy(draft); value['outputs'][0]['path'] = 'products/P/junction/result.txt'
            self.handoff(root, value, success=False); reparse_status = 'REJECTED'
        else:
            assert link_status == 'REJECTED', 'symlink rejection must be exercised on this platform'
        self.handoff(root, draft)
        self.call(root, 'verify')
        return {'rejected_variants': list(mutations), 'link': link_status, 'windows_reparse': reparse_status, 'valid_after_rejections': True}

    def stale(self, name, kind, claimed=False):
        root = self.setup(name)
        check = self.run_check(root)
        self.handoff(root, self.draft(root, check))
        if claimed:
            self.call(root, 'claim', 'C', '--agent', 'consumer')
        output = root / 'products/P/result.txt'
        original = output.read_bytes()
        receipt = json.loads((root / check['receipt']).read_bytes())
        path = root / receipt['logs'][0]['path'] if kind == 'log' else root / check['receipt'] if kind == 'receipt' else output
        restored = path.read_bytes()
        if kind == 'delete':
            path.unlink()
        else:
            path.write_bytes(b'changed after accepted')
        self.call(root, 'verify', success=False)
        self.call(root, 'inspect', 'P', success=False)
        if claimed:
            self.run_check(root, 'C', success=False)
            # Dependency check occurs before loading any submitted consumer draft.
            self.call(root, 'handoff', 'C', '--file', str(root / 'absent.json'), success=False)
            assert self.state(root)['work_status']['C']['status'] == 'CLAIMED'
        else:
            for gate in [('ready',), ('pair',), ('continue',), ('claim', 'C', '--agent', 'consumer')]:
                self.call(root, *gate, success=False)
            assert self.state(root)['work_status']['C']['status'] != 'CLAIMED'
        path.write_bytes(restored)
        self.call(root, 'verify')
        assert output.read_bytes() == original
        return {'tamper': kind, 'consumer_already_claimed': claimed, 'exact_byte_recovery': True, 'restart_rechecked': True}

    def foreign_receipt(self):
        one = self.setup('receipt_owner')
        two = self.setup('receipt_foreign')
        first = self.run_check(one)
        second = self.run_check(two)
        draft = self.draft(two, second)
        draft['verification'] = [first['verification']]
        self.handoff(two, draft, success=False)
        return {'foreign_receipt_rejected': True}

    def failed_execution_recovery(self):
        root = self.setup('retry_execution')
        self.run_check(root, code='raise SystemExit(7)', success=False)
        first = list(self.state(root)['executions'].values())[0]
        assert first['result'] == 'FAIL'
        passed = self.run_check(root)
        self.handoff(root, self.draft(root, passed))
        self.call(root, 'verify')
        assert len(self.state(root)['executions']) == 2
        return {'failed_receipt_preserved': True, 'new_real_execution_passed': True}

    def unsafe_execution_not_started(self):
        root = self.setup('unsafe_execution')
        argv = [sys.executable, '-c', "from pathlib import Path;Path('sentinel.txt').write_text('unexpected')"]
        for tail in [[], ['--allow-execute']]:
            self.call(root, 'run-check', 'P', '--check-id', 'acceptance', '--command-json', json.dumps(argv),
                      '--output', '../outside.txt', *tail, success=False)
            assert not (root / 'sentinel.txt').exists()
            assert not self.state(root)['executions']
        return {'no_unauthorized_or_unsafe_child_spawned': True}

    def legacy(self):
        root = self.artifacts / 'legacy'; root.mkdir()
        state = {'mission': {'mission_id': 'HISTORICAL', 'work_items': [{'id': 'P', 'role': 'historical', 'depends_on': []}]},
                 'work_status': {'P': {'status': 'DONE', 'agent': 'old'}}, 'terminal_gate': 'DONE'}
        path = root / '.bago/team/runtime/state.json'; write_json(path, state)
        before = path.read_bytes()
        self.call(root, 'status'); view = self.call(root, 'inspect', 'P')
        assert view['candidate_id'] is None and view['scope_sha256'] is None
        for args in [('verify',), ('ready',), ('claim', 'P', '--agent', 'new'), ('close',)]:
            self.call(root, *args, success=False)
        assert before == path.read_bytes()
        assert set(p.name for p in path.parent.iterdir()) == {'state.json'}
        return {'history_readable_without_mutation': True, 'identity_not_invented': True, 'modern_gates_rejected': True}

    def published_contracts(self):
        import jsonschema
        kit = self.candidate / '.bago/team/kit'
        plugin = self.candidate / 'plugins/bago-agent-decision-engineering-team'
        for directory in ('protocol', 'missions', 'templates'):
            for path in (kit / directory).iterdir():
                assert path.read_bytes() == (plugin / directory / path.name).read_bytes()
        schema = json.loads((kit / 'protocol/mission.schema.json').read_bytes())
        mission = json.loads((kit / 'missions/agent-decision-inspector.json').read_bytes())
        jsonschema.Draft202012Validator(schema).validate(mission)
        root = self.artifacts / 'default_mission'; root.mkdir()
        self.call(root, 'init', '--mission', str(kit / 'missions/agent-decision-inspector.json'))
        self.call(root, 'verify')
        schema = json.loads((kit / 'protocol/handoff.schema.json').read_bytes())
        jsonschema.Draft202012Validator(schema).validate(json.loads((kit / 'templates/handoff-draft.example.json').read_bytes()))
        return {'published_copies_identical': True, 'default_mission_initializes': True, 'example_schema_valid_template_only': True}

    def pause(self):
        root = self.setup('pause_resume')
        self.call(root, 'pause', '--reason', 'explicit synthetic pause')
        self.run_check(root, success=False)
        self.call(root, 'resume', '--explicit')
        check = self.run_check(root)
        self.handoff(root, self.draft(root, check))
        self.call(root, 'verify')
        return {'pause_blocks_execution': True, 'explicit_resume': True}

    def finish(self):
        after = self.call(self.artifacts, 'identity')['candidate_id']
        assert after == self.identity, 'test changed candidate implementation'
        result = {'result': 'PASS' if all(case['result'] == 'PASS' for case in self.cases) else 'FAIL',
                  'candidate_id': self.identity, 'candidate_id_after': after, 'python': sys.version,
                  'scope': 'actual controller and wrapper subprocess CLI, fresh isolated roots',
                  'cases': self.cases, 'bootstrap_calls': self.calls[:1], 'final_identity_call': self.calls[-1]}
        write_json(self.artifacts / 'result.json', result)
        return result


def run_suite(candidate, artifacts):
    harness = Harness(candidate, artifacts)
    harness.record('valid_accepted_consumed_wrapper_restart', harness.positive)
    harness.record('schema_scope_identity_receipt_negatives', harness.negative_handoffs)
    harness.record('modified_output_blocks_consumer_and_recovers', lambda: harness.stale('changed', 'modify'))
    harness.record('deleted_output_blocks_consumer_and_recovers', lambda: harness.stale('deleted', 'delete'))
    harness.record('claimed_consumer_rechecks_dependency', lambda: harness.stale('claimed', 'modify', True))
    harness.record('receipt_log_mutation_blocks_and_recovers', lambda: harness.stale('log_changed', 'log'))
    harness.record('receipt_mutation_blocks_and_recovers', lambda: harness.stale('receipt_changed', 'receipt'))
    harness.record('foreign_receipt_rejected', harness.foreign_receipt)
    harness.record('failed_execution_preserved_real_retry', harness.failed_execution_recovery)
    harness.record('unsafe_execution_rejected_before_spawn', harness.unsafe_execution_not_started)
    harness.record('legacy_passive_read_current_gate_rejection', harness.legacy)
    harness.record('published_contracts_default_mission', harness.published_contracts)
    harness.record('pause_explicit_resume', harness.pause)
    return harness.finish()


def test_teamctl_cli_integrity(tmp_path):
    result = run_suite(Path(__file__).resolve().parents[1], tmp_path / 'controller-cases')
    assert result['result'] == 'PASS', json.dumps(result, ensure_ascii=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--artifacts', type=Path, required=True)
    arguments = parser.parse_args()
    result = run_suite(arguments.candidate, arguments.artifacts)
    print(json.dumps({'result': result['result'], 'cases': len(result['cases']), 'candidate_id': result['candidate_id'],
                      'failed': [c['case'] for c in result['cases'] if c['result'] != 'PASS']}))
    raise SystemExit(0 if result['result'] == 'PASS' else 1)
