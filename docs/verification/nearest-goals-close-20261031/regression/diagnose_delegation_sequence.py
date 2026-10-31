from pathlib import Path
import json
import subprocess
import uuid

ROOT=Path(__file__).resolve().parents[4]
OUT=Path(__file__).resolve().parent/'delegation-sequence'
JOB=r'''
from pathlib import Path
import functools,importlib.util,json,os,shutil,sys,tarfile,traceback
root=Path('/workspace');root.mkdir(exist_ok=True)
with tarfile.open(fileobj=sys.stdin.buffer,mode='r|') as archive:archive.extractall(root,filter='data')
os.chdir(root);sys.path.insert(0,str(root));os.environ['BAGO_DATA_ROOT']=str(root/'stress-data')
import pytest
spec=importlib.util.spec_from_file_location('fixture_module',root/'tests/test_agent_delegation.py');test=importlib.util.module_from_spec(spec);spec.loader.exec_module(test)
events=[]
import threading
def exception_trace(frame,event,arg):
    if event=='exception' and frame.f_code.co_name in {'_finalize_native_agent_chat_trace','publish','cached_metadata','_native_chat_compatibility_evidence','_observe_child','_finish','_verify_trace'}:
        kind,error,tb=arg
        if isinstance(error,(OSError,ValueError)):
            events.append({'function':frame.f_code.co_name,'line':frame.f_lineno,'error':repr(error),'metadata':str(frame.f_locals.get('metadata'))})
    return exception_trace
threading.settrace(exception_trace)
sys.settrace(exception_trace)

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
names=['test_control_proposes_saved_agent_and_native_grant_executes_real_plan_with_parent_child_receipts','test_general_orchestrator_dispatches_clear_in_scope_task_without_a_review_card','test_explicit_saved_agent_file_task_uses_selected_project_and_stops_for_tool_review','test_out_of_scope_return_is_persisted_and_not_reported_as_success','test_needs_authorization_return_does_not_expand_tool_or_workspace_grants','test_no_parent_grant_is_inherited_and_replay_different_scope_never_invokes_again']
for index in range(240):
    case=root/'cases'/str(index);case.mkdir(parents=True);start=len(events);name=names[index%len(names)]
    with pytest.MonkeyPatch.context() as patch:
        fixture=test.setup.__wrapped__(case,patch)
        try:getattr(test,name)(fixture)
        except Exception as error:
            frames=[];tb=error.__traceback__
            while tb:
                selected={k:repr(v)[:2500] for k,v in tb.tb_frame.f_locals.items() if k in {'result','data','delegation','record','response'}}
                frames.append({'function':tb.tb_frame.f_code.co_name,'locals':selected});tb=tb.tb_next
            failures.append({'index':index,'test':name,'exception':repr(error),'frames':frames,'events':events[start:]})
            shutil.copytree(case,out/('case-'+str(index)))
        fixture['client'].close()
    if len(failures)>=3:break
sys.settrace(None);threading.settrace(None)
result={'status':'FAIL' if failures else 'PASS','iterations':index+1,'failures':failures,'all_events':events,'source':'original current fixture/API; diagnostic wrappers rethrow exceptions unchanged'}
(out/'result.json').write_text(json.dumps(result,indent=2,default=str)+'\n')
shutil.copytree(out,'/results',dirs_exist_ok=True)
print(json.dumps({'status':result['status'],'iterations':index+1,'failures':len(failures)}))
raise SystemExit(1 if failures else 0)
'''

if __name__=='__main__':
    OUT.mkdir(exist_ok=False)
    image=subprocess.check_output(['docker','image','inspect','bago-nearest-goals-tests:20261031','--format','{{.Id}}'],text=True).strip()
    name='bago-delegation-sequence-'+uuid.uuid4().hex[:10]
    argv=['docker','run','--rm','-i','--name',name,'--network','none','--mount',f'type=bind,source={OUT},target=/results','--entrypoint','python',image,'-B','-c',JOB]
    (OUT/'launch.json').write_text(json.dumps({'image_id':image,'argv':argv},indent=2)+'\n',encoding='utf-8')
    with (ROOT/'output/ng-complete-v2.tar').open('rb') as stdin:p=subprocess.run(argv,stdin=stdin,cwd=ROOT,timeout=300)
    raise SystemExit(p.returncode)
