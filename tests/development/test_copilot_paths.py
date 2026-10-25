"""Capture-only path syntax adaptation followed by the unchanged ADL guard."""
import asyncio
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import pytest
from src.development import DevelopmentService
from src.providers import github_copilot, registration

@pytest.fixture
def capture(monkeypatch):
    calls={}
    class Value:
        def __init__(self,**kwargs):self.__dict__.update(kwargs)
    class Session:
        async def send_and_wait(self,*args,**kwargs):
            calls['session']['tools'][0].handler(SimpleNamespace(arguments=calls['arguments']))
            await asyncio.Event().wait()
        async def abort(self):calls['aborted']=True
        async def destroy(self):calls['destroyed']=True
    class Client:
        def __init__(self,config):calls['config']=config
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def create_session(self,**kwargs):calls['session']=kwargs;return Session()
    sdk=ModuleType('copilot');sdk.CopilotClient=Client;sdk.SubprocessConfig=Value
    session=ModuleType('copilot.session');session.PermissionRequestResult=Value
    tools=ModuleType('copilot.tools');tools.Tool=Value;tools.ToolResult=Value
    for name,module in [('copilot',sdk),('copilot.session',session),('copilot.tools',tools)]:monkeypatch.setitem(sys.modules,name,module)
    def run(name,arguments):
        calls['arguments']=arguments
        before=copy.deepcopy(arguments)
        result=github_copilot.chat_turn('fake-model',[],tools=[{'type':'function','function':{'name':name,'parameters':{'type':'object'}}}],binding=SimpleNamespace(auth_mode='copilot_cli',credential=None))
        assert arguments==before
        assert calls['aborted'] and calls['destroyed']
        assert calls['session']['on_permission_request'](None,None).kind=='reject'
        return result['tool_calls'][0]['function']['arguments']
    return run

@pytest.fixture
def service(tmp_path):
    root=tmp_path/'target';(root/'src').mkdir(parents=True);(root/'src/existing.py').write_bytes(b'VALUE = 1\n')
    profile=tmp_path/'profile.json';profile.write_text(json.dumps({'root':str(root),'state_root':str(tmp_path/'state'),
        'allowed_paths':['src/existing.py','src/new.py'],'checks':{'fixed':[sys.executable,'-c','pass']},'required_checks':['fixed']}))
    return DevelopmentService(profile)

def invoke(service,name,args):return service.invoke(name,args,'author','conversation',service.root)[0]

def test_read_windows_separator_captured_then_real_scope_guard_allows(capture,service):
    args=capture('development_read',{'path':r'src\existing.py','start_line':1,'max_lines':1})
    assert args=={'path':'src/existing.py','start_line':1,'max_lines':1}
    result=invoke(service,'development_read',args)
    assert result['ok'] and result['content']=='VALUE = 1'

def test_prepare_only_paths_change_source_and_replacement_bytes_stay_identical(capture,service):
    body="raw = r'C:\\DO_NOT_TOUCH\\.env'\n"
    source={'changes':[{'path':r'src\new.py','old_sha256':None,'content':body},
        {'path':r'src\existing.py','old_sha256':hashlib.sha256(b'VALUE = 1\n').hexdigest(),
         'replacements':[{'old':'VALUE = 1','new':"VALUE = r'C:\\DO_NOT_TOUCH'"}]}]}
    args=capture('development_prepare',source)
    assert args['changes'][0]['content']==body and args['changes'][0]['old_sha256'] is None
    assert args['changes'][1]['replacements']==source['changes'][1]['replacements']
    result=invoke(service,'development_prepare',args)
    assert result['ok'],result
    directory=service._directory(result['change']['change_id'])/'source'
    assert (directory/'src/new.py').read_bytes()==body.encode()
    assert (directory/'src/existing.py').read_text()=="VALUE = r'C:\\DO_NOT_TOUCH'\n"
    assert not (service.root/'src/new.py').exists()

@pytest.mark.parametrize('path',[r'C:\src\new.py',r'C:src\new.py',r'\\server\share\new.py',r'\src\new.py','/src/new.py',
    r'src\..\new.py',r'src\.\new.py',r'src\.hidden\new.py',r'src\\new.py','src//new.py',r'src\new.py:stream','src\new\x00.py',
    'src\\bad\nfile.py','src\\new.py ','src\\new?.py','src\\new.'])
def test_invalid_paths_are_not_cleaned_and_real_adl_still_denies(capture,service,path):
    args=capture('development_prepare',{'changes':[{'path':path,'old_sha256':None,'content':'never written'}]})
    assert args['changes'][0]['path']==path
    result=invoke(service,'development_prepare',args)
    assert not result['ok'] and result['reason_code']=='change_scope_denied'
    assert not service.list_changes()

def test_unknown_scope_stays_denied_after_separator_adaptation(capture,service):
    args=capture('development_prepare',{'changes':[{'path':r'src\unknown.py','old_sha256':None,'content':'never written'}]})
    assert args['changes'][0]['path']=='src/unknown.py'
    result=invoke(service,'development_prepare',args)
    assert not result['ok'] and result['reason_code']=='change_scope_denied'

def test_duplicates_after_conversion_are_denied_not_deduplicated(capture,service):
    args=capture('development_prepare',{'changes':[{'path':r'src\new.py','old_sha256':None,'content':'one'},
                                                 {'path':'src/new.py','old_sha256':None,'content':'two'}]})
    assert len(args['changes'])==2
    result=invoke(service,'development_prepare',args)
    assert not result['ok'] and result['reason_code']=='duplicate_change_path'
    assert not service.list_changes()

@pytest.mark.parametrize('name',['read_workspace_file','propose_workspace_write','sandbox.run','development_check','development_inspect','development_review'])
def test_no_other_tool_or_path_named_nested_argument_is_rewritten(capture,name):
    original={'path':r'src\leave.py','nested':{'path':r'src\leave.py'},'content':r'C:\unchanged'}
    assert capture(name,original)==original

@pytest.mark.parametrize('path',[None,[],{},1])
def test_nonstring_path_not_coerced(capture,service,path):
    args=capture('development_prepare',{'changes':[{'path':path,'old_sha256':None,'content':'not written'}]})
    assert args['changes'][0]['path']==path
    assert invoke(service,'development_prepare',args)['reason_code']=='nonstring_path'

def test_unknown_tool_still_rejected(capture):
    with pytest.raises(registration.RegistrationError,match='not available'):capture('development_apply',{'path':r'src\new.py'})

def test_hardlink_guard_is_still_enforced_after_capture(capture,service,tmp_path):
    os.link(service.root/'src/existing.py',tmp_path/'alias.py')
    args=capture('development_read',{'path':r'src\existing.py'})
    assert invoke(service,'development_read',args)['reason_code']=='hardlink_denied'
