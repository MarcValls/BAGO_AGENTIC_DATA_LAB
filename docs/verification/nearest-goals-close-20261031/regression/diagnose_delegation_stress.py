from pathlib import Path
import json
import subprocess
import uuid

ROOT=Path(__file__).resolve().parents[4]
OUT=Path(__file__).resolve().parent/'delegation-stress'
JOB=r'''
from pathlib import Path
import functools,importlib.util,json,os,shutil,sys,tarfile,traceback
root=Path('/workspace');root.mkdir(exist_ok=True)
with tarfile.open(fileobj=sys.stdin.buffer,mode='r|') as archive:archive.extractall(root,filter='data')
os.chdir(root);sys.path.insert(0,str(root));os.environ['BAGO_DATA_ROOT']=str(root/'stress-data')
import pytest
spec=importlib.util.spec_from_file_location('fixture_module',root/'tests/test_agent_delegation.py');test=importlib.util.module_from_spec(spec);spec.loader.exec_module(test)
events=[]
def observe(owner,name):
    fn=getattr(owner,name)
    @functools.wraps(fn)
    def recorded(*args,**kwargs):
        try:
            result=fn(*args,**kwargs)
            if name=='_finalize_native_agent_chat_trace' and result.get('local_state')=='failed':events.append({'method':name,'returned':result})
            return result
        except Exception as error:
            events.append({'method':name,'error':repr(error),'traceback':traceback.format_exc()})
            raise
    setattr(owner,name,recorded)
for name in ('_finalize_native_agent_chat_trace','_native_chat_compatibility_evidence'):observe(test.server,name)
for name in ('_observe_child','_finish'):observe(test.AgentDelegations,name)
out=root/'stress-results';out.mkdir();failures=[]
for index in range(100):
    case=root/'cases'/str(index);case.mkdir(parents=True);start=len(events)
    with pytest.MonkeyPatch.context() as patch:
        fixture=test.setup.__wrapped__(case,patch)
        desired='NEEDS_AUTHORIZATION' if index%2 else 'PASSED'
        if index%2:fixture['delegation_outcome']='needs_authorization'
        test.propose(fixture)
        response=test.execute(fixture).json();record=response['agent_delegation']
        if record['state']!=desired:
            failures.append({'index':index,'expected':desired,'response':response,'events':events[start:]})
            shutil.copytree(case,out/('case-'+str(index)))
        fixture['client'].close()
    if len(failures)>=4:break
result={'status':'FAIL' if failures else 'PASS','iterations':index+1,'failures':failures,'all_events':events,'source':'original current fixture/API; diagnostic wrappers rethrow exceptions unchanged'}
(out/'result.json').write_text(json.dumps(result,indent=2,default=str)+'\n')
shutil.copytree(out,'/results',dirs_exist_ok=True)
print(json.dumps({'status':result['status'],'iterations':index+1,'failures':len(failures)}))
raise SystemExit(1 if failures else 0)
'''

if __name__=='__main__':
    OUT.mkdir(exist_ok=False)
    image=subprocess.check_output(['docker','image','inspect','bago-nearest-goals-tests:20261031','--format','{{.Id}}'],text=True).strip()
    name='bago-delegation-diag-'+uuid.uuid4().hex[:10]
    argv=['docker','run','--rm','-i','--name',name,'--network','none','--mount',f'type=bind,source={OUT},target=/results','--entrypoint','python',image,'-B','-c',JOB]
    (OUT/'launch.json').write_text(json.dumps({'image_id':image,'argv':argv},indent=2)+'\n',encoding='utf-8')
    with (ROOT/'output/ng-complete-v2.tar').open('rb') as stdin:p=subprocess.run(argv,stdin=stdin,cwd=ROOT,timeout=300)
    raise SystemExit(p.returncode)
