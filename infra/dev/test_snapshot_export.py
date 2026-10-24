import hashlib,json,tempfile,unittest
from pathlib import Path
from prepare_context import snapshot_paths
class SnapshotExport(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.source=self.root/'frontend/src/New.tsx';self.source.parent.mkdir(parents=True);self.source.write_text('export default 1');self.snapshot=self.root/'phase.json';self.write('frontend/src/New.tsx')
 def tearDown(self):self.tmp.cleanup()
 def write(self,name):self.snapshot.write_text(json.dumps({'files':[{'path':name,'sha256':hashlib.sha256(self.source.read_bytes()).hexdigest()}]}))
 def test_reviewed_new_source(self):
  names,ids=snapshot_paths(self.root,[self.snapshot]);self.assertEqual({'frontend/src/New.tsx'},names);self.assertEqual('phase.json',ids[0]['path'])
 def test_changed_source_rejected(self):
  self.source.write_text('changed')
  with self.assertRaises(ValueError):snapshot_paths(self.root,[self.snapshot])
 def test_traversal_rejected(self):
  for name in ('../outside','frontend/../secret','C:/secret','frontend\\src\\New.tsx','./frontend/src/New.tsx'):
   self.write(name)
   with self.subTest(name=name),self.assertRaises(ValueError):snapshot_paths(self.root,[self.snapshot])
 def test_private_source_not_admitted(self):
  private=self.root/'.env';private.write_bytes(self.source.read_bytes());self.write('.env');self.assertEqual(set(),snapshot_paths(self.root,[self.snapshot])[0])
 def test_foreign_snapshot_rejected(self):
  source=self.root/'different';source.mkdir()
  with self.assertRaises(ValueError):snapshot_paths(source,[self.snapshot])

 def test_exact_history_requires_snapshot(self):
  from prepare_context import allowed
  name='src/contacts_service/history/UPSTREAM_SOURCE.py';history=self.root/name;history.parent.mkdir(parents=True);history.write_bytes(self.source.read_bytes());self.write(name)
  self.assertFalse(allowed(name));self.assertEqual({name},snapshot_paths(self.root,[self.snapshot])[0]);history.write_text('changed')
  with self.assertRaises(ValueError):snapshot_paths(self.root,[self.snapshot])
 def test_snapshot_does_not_expand_other_history(self):
  for name in ['src/contacts_service/history/other.py','src/other/history/UPSTREAM_SOURCE.py','src/contacts_service/history/private.json']:
   path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(self.source.read_bytes());self.write(name)
   with self.subTest(name=name):self.assertEqual(set(),snapshot_paths(self.root,[self.snapshot])[0])
