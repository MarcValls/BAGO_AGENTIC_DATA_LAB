"""Synthetic lifetime stress; does not change ADL implementation or real data."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
import gc,sqlite3,json,time,sys
sys.path.insert(0,'/workspace/scratch/54b1628604af/BAGO_AGENTIC_DATA_LAB')
from src.conversations.library import ConversationStore
native_connect=sqlite3.connect
class ClosingConnection(sqlite3.Connection):
    def __exit__(self,*args):
        try:return super().__exit__(*args)
        finally:self.close()
def closing_connect(*args,**kwargs):
    kwargs.setdefault('factory',ClosingConnection)
    return native_connect(*args,**kwargs)
def run(location,closing,number):
    sqlite3.connect=closing_connect if closing else native_connect
    with TemporaryDirectory(prefix='adl-store-audit-',dir=location) as td:
        db=Path(td)/'store.sqlite3';store=ConversationStore(db);cid=store.create('assistant','app-assistant')['id'];done=Event();failure=None
        initial=db.stat();steps=[]
        def reader():
            n=0
            while not done.is_set():
                store.get(cid);store.list();store.work_history_metadata();gc.collect();n+=1
            return n
        started=time.monotonic()
        with ThreadPoolExecutor(max_workers=5) as pool:
            readers=[pool.submit(reader) for _ in range(4)]
            try:
                for i in range(500):
                    reply=store.append_message(cid,i,'assistant' if i%2 else 'user',str(i),references={'test':True})
                    got=store.get(cid)
                    stat=db.stat()
                    with sqlite3.connect('file:'+str(db)+'?mode=ro',uri=True) as conn:
                        observed=conn.execute('SELECT revision,(SELECT count(*) FROM messages) FROM conversations').fetchone()
                    steps.append({'expected':i+1,'reply':reply['revision'],'got':got['revision'],'messages':len(got['messages']),'ro':observed,'stat':[stat.st_dev,stat.st_ino,stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns]})
                    if (got['revision'],len(got['messages']))!=(i+1,i+1) or observed!=(i+1,i+1):failure=steps[-1];break
            except Exception as error:failure={'expected':i+1,'type':type(error).__name__,'detail':str(error)}
            finally:done.set()
            counts=[]
            for task in readers:
                try:counts.append(task.result())
                except Exception as error:counts.append({'type':type(error).__name__,'detail':str(error)})
        final=store.get(cid)
        check=native_connect('file:'+str(db)+'?mode=ro',uri=True)
        try:finalro=check.execute('SELECT revision,(SELECT count(*) FROM messages) FROM conversations').fetchone()
        finally:check.close()
        report={'case':number,'location':location,'closing_connection_factory':closing,'python':sys.version.split()[0],'sqlite':sqlite3.sqlite_version,'status':'FAIL' if failure else 'PASS','failure':failure,'final':final['revision'],'final_messages':len(final['messages']),'final_ro':finalro,'reader_iterations':counts,'seconds':round(time.monotonic()-started,3),'initial_inode':[initial.st_dev,initial.st_ino],'last_steps':steps[-4:] if failure else []}
        print(json.dumps(report),flush=True)
        return report
if __name__=='__main__':
    for n in range(12):run('/tmp' if n%4<2 else '/workspace/scratch/54b1628604af',n%2==1,n)
