"""Host-owned producer evidence. The model cannot register checks or a PASS."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib
import json
import os
import subprocess
import sys
import threading
import uuid

from src.services.delivery_review import ReceiptEvidenceProvider,_hash

_LOCK=threading.RLock()
PRODUCER_ID='adl-agent-tool-host-v1'
RELATIVE='.bago/traces/agent-tools/producers'


def file_hash(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path,value,*,new=True):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    for p in (path.parent,*path.parent.parents):
        info=p.lstat()
        if p.is_symlink() or getattr(info,'st_file_attributes',0)&1024:raise ValueError('evidence link rejected')
    raw=json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False).encode('utf8')
    if new:
        with path.open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
    else:
        temporary=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
        with temporary.open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,path)
    if path.read_bytes()!=raw:raise ValueError('evidence readback failed')


class ProducerStore:
    def __init__(self,workspace,*,acceptance_profile=None):
        if acceptance_profile not in {None,'synthetic-fixture-v1'}:raise ValueError('unknown host acceptance validator')
        self.acceptance_profile=acceptance_profile
        self.root=Path(workspace).resolve();self.directory=self.root/RELATIVE
        self.registry=self.directory/'registry.json'

    def _registry(self):
        if not self.registry.exists():return {'producer_id':PRODUCER_ID,'runs':{}}
        data=json.loads(self.registry.read_text(encoding='utf8'))
        if data.get('producer_id')!=PRODUCER_ID:raise ValueError('producer registry mismatch')
        return data

    def register(self,*,owner_id,conversation_id,source_root,outputs,receipt,sources=None):
        """Called only after a real handler produced outputs, never from a tool schema."""
        if not 1<=len(outputs)<=5:raise ValueError('producer requires one to five outputs')
        run='production_'+uuid.uuid4().hex;directory=self.directory/run;directory.mkdir(parents=True,exist_ok=False)
        artifacts=[];checksources=list(sources or [])
        for index,rawpath in enumerate(outputs):
            path=Path(rawpath).absolute()
            for part in (path,*path.parents):
                info=part.lstat()
                if part.is_symlink() or getattr(info,'st_file_attributes',0)&1024:raise ValueError('producer source link')
            before=path.stat();payload=path.read_bytes();after=path.stat()
            if len(payload)>16*1024*1024 or (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):raise ValueError('producer source changed/too large')
            dest=directory/(str(index)+'_'+path.name)
            with dest.open('xb') as stream:stream.write(payload);stream.flush();os.fsync(stream.fileno())
            sha=hashlib.sha256(payload).hexdigest()
            if file_hash(dest)!=sha:raise ValueError('artifact copy readback failed')
            artifacts.append({'path':dest.relative_to(self.root).as_posix(),'sha256':sha})
            checksources.extend([{'path':str(path),'sha256':sha},{'path':str(dest),'sha256':sha}])
        call=directory/'operation-receipt.json';write(call,receipt)
        manifest=directory/'integrity-input.json';write(manifest,{'files':checksources,'artifact_paths':[str(self.root/a['path']) for a in artifacts],
            'scope':'source/output byte integrity only','host_acceptance_profile':self.acceptance_profile})
        candidate_files=artifacts+[{'path':p.relative_to(self.root).as_posix(),'sha256':file_hash(p)} for p in (call,manifest)]
        candidate=_hash(sorted(candidate_files,key=lambda x:x['path']));scopes=[directory.relative_to(self.root).as_posix()+'/*'];scope=_hash(scopes)
        started=datetime.now(timezone.utc).isoformat()
        argv=[sys.executable,'-m','src.services.producer_checks','--manifest',str(manifest)]
        env={k:v for k,v in os.environ.items() if k not in {'PYTHONPATH','PYTHONHOME','PYTHONSTARTUP'}}
        timeout=False;spawn_error=None
        try:
            child=subprocess.run(argv,cwd=Path(__file__).resolve().parents[2],env=env,capture_output=True,timeout=15)
            stdout,stderr,returncode=child.stdout,child.stderr,child.returncode
        except subprocess.TimeoutExpired as error:
            stdout,stderr,returncode=error.stdout or b'',error.stderr or b'',None;timeout=True
        except OSError as error:
            stdout,stderr,returncode=b'',str(error).encode(),None;spawn_error=type(error).__name__
        logs=[]
        for name,payload in [('stdout.log',stdout),('stderr.log',stderr)]:
            path=directory/name
            with path.open('xb') as stream:stream.write(payload);stream.flush();os.fsync(stream.fileno())
            logs.append({'path':path.relative_to(self.root).as_posix(),'sha256':file_hash(path)})
        after=_hash(sorted([{'path':r['path'],'sha256':file_hash(self.root/r['path'])} for r in candidate_files],key=lambda x:x['path']))
        passed=returncode==0 and not timeout and spawn_error is None and candidate==after
        common={'producer_id':PRODUCER_ID,'run_id':run,'work_id':run,'mission_id':'agent-output/'+conversation_id,
                'candidate_id':candidate,'scope_sha256':scope}
        check={**common,'id':'artifact_integrity','executed':spawn_error is None,'result':'PASS' if passed else 'FAIL',
               'returncode':returncode,'timed_out':timeout,'spawn_error':spawn_error,'command_argv':argv,
               'started_at':started,'finished_at':datetime.now(timezone.utc).isoformat(),'logs':logs,
               'candidate_before':candidate,'candidate_after':after,'validation_scope':'source/output byte integrity, not business acceptance'}
        acceptance=None
        if self.acceptance_profile is not None:
            accepted_argv=argv+['--check',self.acceptance_profile]
            started_acceptance=datetime.now(timezone.utc).isoformat();error=None
            try:
                executed=subprocess.run(accepted_argv,cwd=Path(__file__).resolve().parents[2],env=env,capture_output=True,timeout=15)
                accepted_stdout,accepted_stderr,accepted_code=executed.stdout,executed.stderr,executed.returncode
            except (OSError,subprocess.TimeoutExpired) as exc:
                accepted_stdout,accepted_stderr,accepted_code=b'',str(exc).encode(),None;error=type(exc).__name__
            accepted_logs=[]
            for name,payload in [('acceptance.stdout.log',accepted_stdout),('acceptance.stderr.log',accepted_stderr)]:
                p=directory/name
                with p.open('xb') as stream:stream.write(payload);stream.flush();os.fsync(stream.fileno())
                accepted_logs.append({'path':p.relative_to(self.root).as_posix(),'sha256':file_hash(p)})
            final_candidate=_hash(sorted([{'path':r['path'],'sha256':file_hash(self.root/r['path'])} for r in candidate_files],key=lambda x:x['path']))
            acceptance={**common,'id':'business_acceptance','executed':error is None,'result':'PASS' if accepted_code==0 and error is None and candidate==final_candidate else 'FAIL',
                'returncode':accepted_code,'timed_out':error=='TimeoutExpired','spawn_error':error if error and error!='TimeoutExpired' else None,'command_argv':accepted_argv,
                'started_at':started_acceptance,'finished_at':datetime.now(timezone.utc).isoformat(),'logs':accepted_logs,
                'candidate_before':candidate,'candidate_after':final_candidate,'validation_scope':'synthetic fixed fixture content only; not accounting'}
        value={**common,'owner_id':owner_id,'conversation_id':conversation_id,'source_root':str(source_root),
               'candidate_files':candidate_files,'output_scopes':scopes,'artifacts':artifacts,
               'required_checks':['artifact_integrity','business_acceptance'],'checks':[check]+([acceptance] if acceptance is not None else []),
               'pending':['Falta revisión de contenido.'] if acceptance is None else [],
               'risks':[],'findings':[],'integrity_check':check['result'],'business_acceptance':acceptance['result'] if acceptance is not None else 'NOT_RUN',
               'acceptance_scope':'synthetic fixed fixture content only; not accounting' if acceptance is not None else 'NOT_RUN'}
        target=directory/'producer-receipt.json';write(target,value)
        with _LOCK:
            registry=self._registry();registry['runs'][run]={'path':target.relative_to(self.root).as_posix(),'sha256':file_hash(target),'run_id':run}
            write(self.registry,registry,new=False)
        return self.summary(value)

    @staticmethod
    def summary(value):
        return {k:value[k] for k in ('work_id','owner_id','conversation_id','source_root','mission_id','candidate_id','scope_sha256','artifacts','integrity_check','business_acceptance')}

    def load_registered(self,work_id):
        with _LOCK:
            row=self._registry()['runs'][work_id]
            path=self.root/row['path']
            if file_hash(path)!=row['sha256']:raise ValueError('producer receipt changed')
            value=json.loads(path.read_text(encoding='utf8'))
            if value['work_id']!=work_id or value['producer_id']!=PRODUCER_ID:raise ValueError('producer binding mismatch')
            return value

    def list(self):
        return [self.summary(self.load_registered(key)) for key in self._registry()['runs']]

    def provider(self):
        return ReceiptEvidenceProvider(self.root,self.registry.relative_to(self.root).as_posix(),PRODUCER_ID)
