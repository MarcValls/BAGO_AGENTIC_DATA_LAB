"""Copilot revise proposals keep bodies and use exactly the bounded path adapter."""
import asyncio
import copy
import sys
from types import ModuleType, SimpleNamespace
import pytest
from src.providers import github_copilot

@pytest.fixture
def capture(monkeypatch):
    calls={}
    class Value:
        def __init__(self,**kwargs):self.__dict__.update(kwargs)
    class Session:
        async def send_and_wait(self,*args,**kwargs):
            calls['session']['tools'][0].handler(SimpleNamespace(arguments=calls['args']))
            await asyncio.Event().wait()
        async def abort(self):calls['abort']=True
        async def destroy(self):calls['destroy']=True
    class Client:
        def __init__(self,config):pass
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def create_session(self,**kwargs):calls['session']=kwargs;return Session()
    sdk=ModuleType('copilot');sdk.CopilotClient=Client;sdk.SubprocessConfig=Value
    session=ModuleType('copilot.session');session.PermissionRequestResult=Value
    tools=ModuleType('copilot.tools');tools.Tool=Value;tools.ToolResult=Value
    for name,module in [('copilot',sdk),('copilot.session',session),('copilot.tools',tools)]:monkeypatch.setitem(sys.modules,name,module)
    def run(args):
        original=copy.deepcopy(args);calls['args']=args
        result=github_copilot.chat_turn('fake',[],tools=[{'type':'function','function':{'name':'development_revise','parameters':{'type':'object'}}}],binding=SimpleNamespace(auth_mode='copilot_cli',credential=None))
        assert args==original and calls['abort'] and calls['destroy']
        assert calls['session']['on_permission_request'](None,None).kind=='reject'
        return result['tool_calls'][0]['function']['arguments']
    return run

def test_sdk_revision_capture_only_translates_designated_paths(capture):
    args={'change_id':'dev_'+'a'*32,'expected_sha256':'b'*64,'allow_source_rebase':True,'changes':[
        {'path':r'src\example.py','old_sha256':'c'*64,'replacements':[{'old':r'old\body','new':r'new\body'}]},
        {'path':r'src\created.py','old_sha256':None,'content':r'unchanged\body'}]}
    result=capture(args)
    assert [c['path'] for c in result['changes']]==['src/example.py','src/created.py']
    for original,converted in zip(args['changes'],result['changes']):
        assert {k:v for k,v in converted.items() if k!='path'}=={k:v for k,v in original.items() if k!='path'}
    assert result['change_id']==args['change_id'] and result['expected_sha256']==args['expected_sha256']
    assert result['allow_source_rebase'] is True

@pytest.mark.parametrize('path',[r'C:\outside.py',r'\\host\share.py',r'src\..\escape.py',r'src\.hidden.py',r'src\\double.py',r'src\x.py:stream'])
def test_revision_capture_does_not_wash_invalid_paths(capture,path):
    args={'change_id':'dev_'+'a'*32,'expected_sha256':'b'*64,'changes':[{'path':path,'old_sha256':None,'content':'not executed'}]}
    assert capture(args)==args
