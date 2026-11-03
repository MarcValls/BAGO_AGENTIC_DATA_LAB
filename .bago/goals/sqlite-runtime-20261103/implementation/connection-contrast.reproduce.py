import json,types,sys,sqlite3,tempfile,hashlib,subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(root))
results=[]
for name,ref in [('main','6173ade56d64051b40586b80386faff79e22a119'),('pr116','8b6e48b5cc9243b4884af90b5db876dba09ecc73')]:
 source=subprocess.check_output(['git','show',ref+':src/conversations/library.py'],cwd=root);file=ref+':src/conversations/library.py';module=types.ModuleType('src.conversations.compare');module.__package__='src.conversations';exec(compile(source,file,'exec'),module.__dict__)
 class Tracked(module.ConversationStore):
  def _connect(self):
   connection=super()._connect();self.seen.append(connection);return connection
 with tempfile.TemporaryDirectory(prefix='adl-close-contrast-') as directory:
  store=Tracked(Path(directory)/'synthetic.sqlite3');store.seen=[]
  cid=store.create('assistant','synthetic')['id'];reply=store.append_message(cid,0,'user','synthetic');got=store.get(cid)
  states=[]
  for connection in store.seen:
   try:connection.execute('SELECT 1');states.append('OPEN')
   except sqlite3.ProgrammingError:states.append('CLOSED')
   finally:connection.close()
  results.append(dict(source=name,source_sha256=hashlib.sha256(source).hexdigest(),connections_after_context=states,reply_revision=reply['revision'],get_revision=got['revision'],messages=len(got['messages'])))
print(json.dumps(results,indent=2))
