"""Fake SDK exercises the real Copilot transport; capture never runs ADL tools."""
import asyncio
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import pytest
from src.development import TOOL_IDS, DevelopmentService
from src.providers import github_copilot, registration

BASELINE={'sandbox.run','read_workspace_file','scan_code_duplicates','public_web_read','propose_workspace_write'}

def schema(name):
    return {'type':'function','function':{'name':name,'description':'Bounded proposal','parameters':{'type':'object','properties':{'payload':{'type':'object'}},'required':['payload'],'additionalProperties':False}}}

@pytest.fixture
def sdk(monkeypatch):
    observed={'local_effects':0,'clients':0}
    class Value:
        def __init__(self,**kwargs):self.__dict__.update(kwargs)
    class Session:
        async def send_and_wait(self,prompt,**kwargs):
            observed['prompt']=prompt
            for tool in observed['session']['tools']:
                name='sandbox.run' if tool.name=='adl_sandbox_run' else tool.name
                observed.setdefault('callback_results',[]).append(tool.handler(SimpleNamespace(arguments=observed['arguments'][name])))
            await asyncio.Event().wait()
        async def abort(self):observed['aborted']=True
        async def destroy(self):observed['destroyed']=True
    class Client:
        def __init__(self,config):observed['config']=config;observed['clients']+=1
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def create_session(self,**kwargs):observed['session']=kwargs;return Session()
    copilot=ModuleType('copilot');copilot.CopilotClient=Client;copilot.SubprocessConfig=Value
    session=ModuleType('copilot.session');session.PermissionRequestResult=Value
    tools=ModuleType('copilot.tools');tools.Tool=Value;tools.ToolResult=Value
    monkeypatch.setitem(sys.modules,'copilot',copilot)
    monkeypatch.setitem(sys.modules,'copilot.session',session)
    monkeypatch.setitem(sys.modules,'copilot.tools',tools)
    def forbidden(*args,**kwargs):
        observed['local_effects']+=1
        raise AssertionError('Transport must never invoke tools or spawn effects')
    monkeypatch.setattr(DevelopmentService,'invoke',forbidden)
    monkeypatch.setattr(github_copilot.subprocess,'Popen',forbidden)
    return observed

def run(sdk,names):
    sdk['arguments']={name:{'payload':{'name':name,'nested':[1,{'unchanged':True}],'path':'never-written.py'}} for name in names}
    return github_copilot.chat_turn('fake-model',[{'role':'system','content':'ADL owns effects.'},{'role':'user','content':'Propose only.'}],
        tools=[schema(n) for n in names],binding=SimpleNamespace(auth_mode='copilot_cli',credential=None))

@pytest.mark.parametrize('name',sorted(TOOL_IDS|BASELINE))
def test_each_known_development_and_baseline_tool_is_capture_only(sdk,name):
    result=run(sdk,[name])
    assert result=={'content':'','tool_calls':[{'id':'copilot-1','type':'function','function':{'name':name,'arguments':sdk['arguments'][name]}}]}
    tool=sdk['session']['tools'][0]
    assert tool.parameters==schema(name)['function']['parameters']
    assert tool.skip_permission is True
    assert 'No effect was executed' in sdk['callback_results'][0].text_result_for_llm
    assert sdk['local_effects']==0 and sdk['aborted'] and sdk['destroyed']
    assert not Path(sdk['config'].cwd).exists()  # temporary SDK directory cleaned
    assert sdk['session']['on_permission_request'](SimpleNamespace(kind='shell'),{}).kind=='reject'
    assert sdk['session']['available_tools']==[tool.name]
    assert sdk['session']['mcp_servers']=={} and sdk['session']['skill_directories']==[]
    assert sdk['session']['disabled_skills']==['*'] and sdk['session']['enable_config_discovery'] is False

def test_all_five_development_tools_roundtrip_without_aliasing_or_effects(sdk):
    names=sorted(TOOL_IDS);result=run(sdk,names)
    assert [call['function'] for call in result['tool_calls']]==[{'name':name,'arguments':sdk['arguments'][name]} for name in names]
    assert sdk['local_effects']==0

@pytest.mark.parametrize('name',['development_apply','development_rollback','shell','mcp.execute','arbitrary_tool'])
def test_unknown_and_effectful_names_reject_before_sdk_start(sdk,name):
    with pytest.raises(registration.RegistrationError) as failure:run(sdk,[name])
    assert failure.value.code=='invalid_tool_name'
    assert sdk['clients']==0 and sdk['local_effects']==0

def test_existing_environment_credential_policy_is_preserved(sdk,monkeypatch):
    names=['COPILOT_GITHUB_TOKEN','GH_TOKEN','GITHUB_TOKEN','GITHUB_COPILOT_API_TOKEN','COPILOT_API_URL']
    for name in names:monkeypatch.setenv(name,'SYNTHETIC_TEST_VALUE')
    run(sdk,['development_inspect'])
    assert all(name not in sdk['config'].env for name in names)
    assert sdk['config'].github_token is None and sdk['config'].use_logged_in_user is True
