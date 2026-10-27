"""Actual Chat handlers and exact-file IO; model responses are controlled fixtures.

Server import runs only in a subprocess with BAGO_DATA_ROOT set beforehand.
No real provider, user store, or source runtime is imported in the pytest host.
"""
import os
from pathlib import Path
import subprocess
import sys


def test_chat_and_saved_agent_read_without_turn_ticket_under_current_policy(tmp_path):
    script = r'''
import asyncio, hashlib, json
from pathlib import Path
from types import SimpleNamespace
import pytest
from fastapi import Response
from src.api import server
from src.project_folders import ProjectFolders, binding_identity

synthetic = Path(__import__('os').environ['BAGO_DATA_ROOT']).parent
a, b = synthetic/'project-a', synthetic/'project-b'
for root in (a, b):
    (root/'notes').mkdir(parents=True)
    (root/'notes/evidence.txt').write_bytes(b'Synthetic saved-policy evidence\nSecond line\n')
    (root/'outside.txt').write_bytes(b'Never expose synthetic out-of-scope content\n')

def register(root):
    server._set_workspace_root(root)
    owner = ProjectFolders(state_directory=server._WORKSPACE_CONFIG_DIR/'project-folders-v1',
        workspace_root=server.current_workspace_root, set_workspace_root=server._set_workspace_root,
        pick_directory=server._pick_workspace_directory,
        binding_identity=lambda: binding_identity(server._WORKSPACE_CONFIG_PATH, server.current_workspace_root()),
        legacy_parent=lambda: None, binding_lock=server._WORKSPACE_LOCK)
    plan = owner.prepare(mode='existing',path=str(root),name=root.name,title=root.name,expected_workspace_root=str(root))
    owner.apply(plan['plan_id'],plan_sha256=plan['plan_sha256'],confirmed=True)

def save(reads=('notes',)):
    policy=server._current_project_permissions()
    old=policy.snapshot()
    return policy.save(expected_project_id=old['project_id'],expected_binding=old['binding'],
        expected_revision=old['revision'],read_directories=reads,write_directories=(),confirmed=True)

register(b); save()
register(a); save()
patch=pytest.MonkeyPatch()
patch.setenv('BAGO_OTEL_EXPORTER_OTLP_ENDPOINT','')
patch.setattr(server,'export_local_trace_to_otlp',lambda *args,**kwargs: None)
patch.setattr(server.provider_runtime,'active_selection',lambda: {'provider_id':'synthetic-provider','model_id':'synthetic-model'})
patch.setattr(server,'development_chat_session',lambda **kwargs: None)
agent=SimpleNamespace(id='synthetic-agent',config=SimpleNamespace(system_prompt='Use only returned file evidence.',
    provider_id='synthetic-provider',model_id='synthetic-model',tools=[]))
patch.setattr(server,'_load_model_enabled_agent',lambda _: agent)
patch.setattr(server.provider_runtime,'chat',lambda *args,**kwargs: (_ for _ in ()).throw(AssertionError('must use tool loop')))
def no_new_grant(*args, **kwargs):
    raise AssertionError('Saved READ must not issue any transport/document/scan grant')
for authorities in (server.WORKSPACE_READ_AUTHORIZATIONS,server.WORKSPACE_DIRECTORY_AUTHORIZATIONS,server.DOCUMENT_AUTHORIZATIONS):
    patch.setattr(authorities,'issue',no_new_grant)

def turn_fixture(*, route=False, mutate=None, attempt_unassigned=False):
    observed=[]
    def provider(*args,**kwargs):
        names={item['function']['name'] for item in kwargs['tools']}
        observed.append(names)
        if route and len(observed)==1:
            assert names=={'resolve_control_request'}
            return {'tool_calls':[{'function':{'name':'resolve_control_request','arguments':{'decision':'workspace_read','reply':'Inspect the requested file.'}}}]}
        read_index=2 if route else 1
        if len(observed)==read_index:
            assert names=={'read_workspace_file'}, names
            if mutate: mutate()
            calls=[
                {'id':'read-safe','function':{'name':'read_workspace_file','arguments':{'path':'notes/evidence.txt','start_line':1,'end_line':1}}},
                {'id':'read-denied','function':{'name':'read_workspace_file','arguments':{'path':'outside.txt'}}}]
            if attempt_unassigned:
                calls.extend([
                    {'function':{'name':'document_inventory','arguments':{}}},
                    {'function':{'name':'development_check','arguments':{'change_id':'synthetic','check_id':'synthetic'}}}])
            return {'tool_calls':calls}
        tool_messages=[item for item in args[2] if item.get('role')=='tool' and item.get('tool_name')=='read_workspace_file']
        assert len(tool_messages)==2
        assert 'Never expose' not in str(tool_messages)
        return {'content':'Synthetic answer based on actual tool receipts.'}
    patch.setattr(server.provider_runtime,'chat_turn',provider)
    return observed

summary=[]
# Two turns in the same assistant conversation and a fresh second conversation
# all read under the one saved grant, with no authorization request or token.
assistant=server.CONVERSATIONS.create('assistant','app-assistant')
revision=0
for index in range(3):
    if index==2:
        assistant=server.CONVERSATIONS.create('assistant','app-assistant'); revision=0
    observed=turn_fixture(route=(index!=0))
    result=asyncio.run(server.control_chat(server.ControlChatRequest(operation='chat',
        message='Lee notes/evidence.txt con read_workspace_file' if index==0 else 'Resume el archivo notes/evidence.txt del proyecto',
        conversation_id=assistant['id'],revision=revision)))
    assert [e['decision'] for e in result['read_events']]==['ALLOW','DENY'], result
    source=next(s for s in result['sources'] if s.get('path')=='notes/evidence.txt')
    assert source['file_sha256']==hashlib.sha256((a/'notes/evidence.txt').read_bytes()).hexdigest()
    assert source['policy_revision']==server._current_project_permissions().snapshot()['revision']
    revision=result['conversation']['revision']
    summary.append({'handler':'control_chat','case':index,'decisions':['ALLOW','DENY']})

# Saved-agent turns use the actual native handler and receipt/trace pipeline.
for scenario in ('current','unassigned-tools','revoked-during-model','regrant-during-model','a-to-b-during-model','a-to-b-to-a-during-model'):
    server._set_workspace_root(a); save()
    conversation=server.CONVERSATIONS.create('agent','synthetic-agent')
    def mutate():
        if scenario=='revoked-during-model': save(())
        elif scenario=='regrant-during-model': save(()); save()
        elif scenario=='a-to-b-during-model': server._set_workspace_root(b)
        elif scenario=='a-to-b-to-a-during-model': server._set_workspace_root(b); server._set_workspace_root(a)
    turn_fixture(mutate=mutate,attempt_unassigned=(scenario=='unassigned-tools'))
    result=asyncio.run(server.chat_with_agent('synthetic-agent',server.AgentChatRequest(
        message='Read notes/evidence.txt',conversation_id=conversation['id'],revision=0),Response()))
    expected=['ALLOW','DENY'] if scenario in {'current','unassigned-tools'} else ['DENY','DENY']
    if scenario=='unassigned-tools': expected.extend(['DENY','DENY'])
    assert [e['decision'] for e in result['read_events']]==expected, (scenario,result)
    assert scenario in {'current','unassigned-tools'} or not result.get('sources'), (scenario,result.get('sources'))
    assert agent.config.tools==[]
    if scenario=='unassigned-tools':
        extra=result['read_events'][2:]
        assert {item['reason_code'] for item in extra}=={'DOCUMENT_AUTHORIZATION_REQUIRED','DEVELOPMENT_AUTHORIZATION_REQUIRED'}
        assert all(item['executed'] is False for item in extra)
    if scenario=='current':
        trace=json.loads((server.AGENT_CHAT_TRACE_DIR/(result['trace']['trace_id']+'.json')).read_text(encoding='utf-8'))
        assert any(event['name']=='workspace.read' and event['status']=='ALLOW' for event in trace['events'])
    summary.append({'handler':'agent_chat','case':scenario,'decisions':expected})

print(json.dumps({'synthetic_only':True,'per_turn_ticket':False,'handler_cases':summary},sort_keys=True))
'''
    environment = os.environ.copy()
    environment.update(BAGO_DATA_ROOT=str(tmp_path / "isolated-appdata"), BAGO_OTEL_EXPORTER_OTLP_ENDPOINT="")
    result = subprocess.run([sys.executable, "-B", "-c", script], cwd=Path(__file__).resolve().parents[3],
        env=environment, capture_output=True, text=True, encoding="utf-8", timeout=150)
    print(result.stdout)
    assert result.returncode == 0, result.stdout + result.stderr
