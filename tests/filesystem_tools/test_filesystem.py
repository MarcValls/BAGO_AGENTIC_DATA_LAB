import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

BASE = Path(__file__).resolve().parents[2]
FILE = BASE / 'tools/filesystem-toolkit/bago_filesystem.py'
SPEC = importlib.util.spec_from_file_location('filesystem_under_test', FILE)
fs = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fs)


class FilesystemTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.tool = fs.FilesystemToolkit(self.root)
        (self.root / 'original.txt').write_text('contenido sintético', encoding='utf-8')

    def approval(self, plan, **changes):
        value = {'root': str(self.root.resolve()), 'plan_sha256': plan['sha256'],
                 'operations': [plan['operation']], 'actor': 'fixture-user', 'expires_at': time.time() + 60}
        value.update(changes)
        return value

    def execute(self, op, **kwargs):
        plan = self.tool.plan(op, **kwargs)
        receipt = self.tool.execute(plan['id'], approval=self.approval(plan))
        self.assertEqual(receipt['status'], 'VERIFIED', receipt)
        stored = json.loads((self.tool.state / 'receipts' / (plan['id'] + '.json')).read_text())
        self.assertEqual(stored, receipt)
        self.assertEqual(receipt['sha256'], fs.digest({k:v for k,v in receipt.items() if k != 'sha256'}))
        return plan, receipt

    def test_lifecycle_all_operations_and_restart_restore(self):
        self.execute('mkdir', target='folder')
        self.execute('write', target='folder/new.txt', content='nuevo')
        self.execute('copy', source='original.txt', target='copy.txt')
        self.execute('move', source='copy.txt', target='folder/moved.txt')
        self.execute('rename', source='folder/moved.txt', target='folder/renamed.txt')
        plan, _ = self.execute('trash', source='folder/renamed.txt')
        self.assertFalse((self.root / 'folder/renamed.txt').exists())
        self.assertTrue((self.root / plan['target']).is_file())
        self.tool = fs.FilesystemToolkit(self.root)
        self.execute('restore', trash_id=plan['id'])
        self.assertEqual((self.root / 'folder/renamed.txt').read_text(encoding='utf-8'), 'contenido sintético')
        self.assertFalse((self.root / plan['target']).exists())
        self.assertEqual(len(self.tool.inventory()['entries']), 2)

    def test_plan_is_not_execution_and_survives_new_process(self):
        plan = self.tool.plan('write', target='new.txt', content='demo')
        self.assertFalse((self.root / 'new.txt').exists())
        approval_file = self.root / 'approval.json'
        approval_file.write_text(json.dumps(self.approval(plan)))
        result = subprocess.run([sys.executable, str(FILE), '--root', str(self.root),
                                 'execute', plan['id'], '--approval-file', str(approval_file)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)['status'], 'VERIFIED')

    def test_authorization_missing_expired_wrong_root_hash_operation(self):
        plan = self.tool.plan('write', target='new.txt', content='demo')
        for approval in ({}, self.approval(plan, expires_at=0), self.approval(plan, root='other'),
                         self.approval(plan, plan_sha256='bad'), self.approval(plan, operations=[]),
                         self.approval(plan, operations='write'), self.approval(plan, expires_at=float('nan')),
                         self.approval(plan, actor='')):
            with self.subTest(approval=approval), self.assertRaises(fs.FilesystemError):
                self.tool.execute(plan['id'], approval=approval)
        self.assertFalse((self.root / 'new.txt').exists())

    def test_unsafe_paths(self):
        for name in ('../escape', '/absolute', 'C:/x', 'x:y', 'x\\y', 'x/../y', 'x//y',
                     'NUL.txt', 'CON', 'ends.', 'ends ', 'bad?name', '.bago-filesystem/x', 'trash/x'):
            with self.subTest(name=name), self.assertRaises(fs.FilesystemError):
                self.tool.plan('write', target=name, content='x')

    def test_case_collisions(self):
        with self.assertRaises(fs.FilesystemError):
            self.tool.plan('write', target='ORIGINAL.txt', content='x')
        with self.assertRaises(fs.FilesystemError):
            self.tool.plan('rename', source='original.txt', target='ORIGINAL.txt')

    def test_existing_target_and_missing_parent(self):
        for target in ('original.txt', 'absent/new.txt'):
            with self.assertRaises(fs.FilesystemError):
                self.tool.plan('write', target=target, content='x')

    def test_change_after_plan_fails_and_receipt_persists(self):
        plan = self.tool.plan('move', source='original.txt', target='moved.txt')
        (self.root / 'original.txt').write_text('changed')
        receipt = self.tool.execute(plan['id'], approval=self.approval(plan))
        self.assertEqual(receipt['status'], 'FAILED')
        self.assertFalse((self.root / 'moved.txt').exists())
        with self.assertRaises(fs.FilesystemError):
            self.tool.execute(plan['id'], approval=self.approval(plan))

    def test_collision_after_plan_never_overwrites(self):
        plan = self.tool.plan('copy', source='original.txt', target='copy.txt')
        (self.root / 'copy.txt').write_text('protected')
        receipt = self.tool.execute(plan['id'], approval=self.approval(plan))
        self.assertEqual(receipt['status'], 'FAILED')
        self.assertEqual((self.root / 'copy.txt').read_text(), 'protected')

    def test_partial_copy_failure_is_auditable(self):
        plan = self.tool.plan('move', source='original.txt', target='copy.txt')
        def fail(source, destination, length):
            destination.write(b'partial')
            raise OSError('injected fixture failure')
        with patch.object(fs.shutil, 'copyfileobj', fail):
            receipt = self.tool.execute(plan['id'], approval=self.approval(plan))
        self.assertEqual(receipt['status'], 'PARTIAL')
        self.assertTrue((self.root / 'original.txt').exists())
        self.assertEqual((self.root / 'copy.txt').read_bytes(), b'partial')
        self.assertIn('injected fixture failure', receipt['error'])

    def test_restore_collision_and_payload_corruption(self):
        plan, _ = self.execute('trash', source='original.txt')
        (self.root / 'original.txt').write_text('new protected')
        with self.assertRaises(fs.FilesystemError):
            self.tool.plan('restore', trash_id=plan['id'])
        (self.root / 'original.txt').unlink()
        (self.root / plan['target']).write_text('corrupt')
        with self.assertRaises(fs.FilesystemError):
            self.tool.plan('restore', trash_id=plan['id'])

    def test_directories_mutation_unsupported_and_limits(self):
        (self.root / 'folder').mkdir()
        with self.assertRaises(fs.FilesystemError):
            self.tool.plan('move', source='folder', target='new-folder')
        with self.assertRaises(fs.FilesystemError):
            self.tool.inventory(max_entries=1)
        with self.assertRaises(fs.FilesystemError):
            self.tool.plan('write', target='big', content='x' * (fs.MAX_BYTES + 1))
        with self.assertRaises(fs.FilesystemError):
            self.tool.plan('delete', source='original.txt')

    def test_hardlinks_and_symlinks_fail_closed(self):
        os.link(self.root / 'original.txt', self.root / 'hard.txt')
        with self.assertRaises(fs.FilesystemError):
            self.tool.plan('copy', source='hard.txt', target='copy.txt')
        try:
            (self.root / 'link').symlink_to(self.root / 'original.txt')
        except OSError:
            return  # Windows may deny symlink creation; hardlink case still executed.
        with self.assertRaises(fs.FilesystemError):
            self.tool.plan('copy', source='link', target='copy.txt')

    def test_pending_receipt_blocks_replay_after_restart(self):
        plan = self.tool.plan('write', target='new', content='x')
        (self.tool.state / 'receipts' / (plan['id'] + '.pending.json')).write_text('{"status":"STARTED"}')
        with self.assertRaises(fs.FilesystemError):
            fs.FilesystemToolkit(self.root).execute(plan['id'], approval=self.approval(plan))

    def test_plan_tampering_and_bad_record_id(self):
        plan = self.tool.plan('write', target='new', content='x')
        path = self.tool.state / 'plans' / (plan['id'] + '.json')
        plan['content'] = 'tampered'
        path.write_text(json.dumps(plan))
        with self.assertRaises(fs.FilesystemError):
            self.tool.execute(plan['id'], approval=self.approval(plan))
        with self.assertRaises(fs.FilesystemError):
            self.tool.execute('../escape', approval={})

    def test_model_adapter_has_no_execution_schema(self):
        spec = importlib.util.spec_from_file_location('fs_adapter', BASE / 'src/agent_tools/filesystem_tools.py')
        adapter = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(adapter)
        session = adapter.FilesystemSession()
        grant = {'root': str(self.root), 'tools': sorted(adapter.FS_TOOL_IDS)}
        self.assertEqual({x['function']['name'] for x in session.tool_schemas(grant)}, adapter.FS_TOOL_IDS)
        result, receipt = session.invoke('filesystem_plan', {'operation':'write','target':'new','content':'x'}, grant)
        self.assertEqual(receipt['status'], 'PREPARED')
        self.assertFalse((self.root / 'new').exists())
        with self.assertRaises(adapter.FilesystemError):
            session.invoke('filesystem_execute', {}, grant)
        with self.assertRaises(adapter.FilesystemError):
            session.invoke('filesystem_inventory', {}, {'root':str(self.root),'tools':[]})

    def test_empty_inventory_and_read_grant_create_no_paths(self):
        empty = self.root / 'empty'
        empty.mkdir()
        before = list(empty.rglob('*'))
        toolkit = fs.FilesystemToolkit(empty)
        self.assertEqual(toolkit.inventory()['entries'], [])
        self.assertEqual(list(empty.rglob('*')), before)
        spec = importlib.util.spec_from_file_location('fs_read_adapter', BASE / 'src/agent_tools/filesystem_tools.py')
        adapter = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(adapter)
        result, receipt = adapter.FilesystemSession().invoke(
            'filesystem_inventory', {}, {'root':str(empty), 'tools':['filesystem_inventory']})
        self.assertEqual(result['entries'], [])
        self.assertEqual(receipt['effect_status'], 'read_only')
        self.assertEqual(list(empty.rglob('*')), before)
        self.assertFalse((empty / '.bago-filesystem').exists())

    def test_inventory_preserves_existing_paths_and_bytes(self):
        def snapshot():
            return {p.relative_to(self.root).as_posix(): p.read_bytes() if p.is_file() else None
                    for p in self.root.rglob('*')}
        before = snapshot()
        self.tool.inventory()
        self.assertEqual(snapshot(), before)
        self.assertFalse(self.tool.state.exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
