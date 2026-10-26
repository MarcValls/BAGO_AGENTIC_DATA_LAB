"""Real API dispatch and assignment boundaries for the external development bridge."""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.development_routes import create_development_router


class HostService:
    def __init__(self):
        self.applied = []

    def list_changes(self):
        return [{'change_id': 'candidate-1', 'status': 'PREPARED'}]

    def inspect(self, change_id):
        return {'change_id': change_id, 'apply_eligible': False}

    def apply(self, change_id, expected_sha256, confirmed):
        if not confirmed:
            raise ValueError('confirmation_required')
        self.applied.append(change_id)
        return {'change_id': change_id, 'status': 'APPLIED'}


def test_host_review_requires_exact_confirmation_and_rejects_foreign_origin():
    service = HostService()
    app = FastAPI()
    app.include_router(create_development_router(lambda: service))
    client = TestClient(app)
    assert client.get('/api/development/changes').json()['changes'][0]['status'] == 'PREPARED'
    assert client.get('/api/development/changes/candidate-1').json()['apply_eligible'] is False
    url = '/api/development/changes/candidate-1/apply'
    body = {'expected_sha256': 'a'*64, 'confirmed': True}
    assert client.post(url, json=body, headers={'origin':'http://foreign.invalid'}).status_code == 403
    assert client.post(url, json={**body, 'confirmed':'true'}).status_code == 422
    assert client.post(url, json={**body, 'command':'arbitrary'}).status_code == 422
    assert client.post(url, json={**body, 'confirmed':False}).status_code == 409
    assert not service.applied
    assert client.post(url, json=body).json()['status'] == 'APPLIED'
    assert service.applied == ['candidate-1']


def test_development_assignment_and_reviewer_separation(tmp_path, monkeypatch):
    from src.agent_tools.agent_services import AgentServiceSession, SERVICE_TOOL_IDS
    from src.development import TOOL_IDS, DevelopmentService
    assert TOOL_IDS <= SERVICE_TOOL_IDS
    assert 'development_apply' not in SERVICE_TOOL_IDS
    session = AgentServiceSession(workspace=tmp_path,root=tmp_path,owner_id='author',conversation_id='conv',communications=None)
    def forbidden(*args, **kwargs):
        raise AssertionError('unauthorized service must not be invoked')
    monkeypatch.setattr(DevelopmentService, 'invoke', forbidden)
    for name, assigned in [('development_check', []), ('development_review', ['development_review','development_prepare'])]:
        result, receipt = session.invoke(name, {}, assigned)
        assert not result['ok'] and receipt['decision'] == 'DENY' and receipt['executed'] is False


def test_dev_tool_chat_without_document_grant(tmp_path, monkeypatch):
    import asyncio
    import json
    import sys
    from types import SimpleNamespace
    from fastapi import Response
    from src.api import server
    from src.agent_tools.agent_services import development_chat_session
    from src.conversations import ConversationStore

    monkeypatch.delenv('BAGO_DEVELOPMENT_PROFILE',raising=False)
    assert development_chat_session(owner_id='agent-1',conversation_id='conversation-1',assigned=['development_read']) is None
    root=tmp_path/'target';root.mkdir()
    source='def summarize(value):\n    return value.strip()\n'
    (root/'sample_a.py').write_text(source,encoding='utf8')
    profile=tmp_path/'profile.json'
    profile.write_text(json.dumps({'root':str(root),'state_root':str(tmp_path/'state'),
        'allowed_paths':['sample_a.py'],'checks':{'unit':[sys.executable,'-B','-c','print("bounded fixture check")']},
        'required_checks':['unit']}),encoding='utf8')
    monkeypatch.setenv('BAGO_DEVELOPMENT_PROFILE',str(profile))
    assert development_chat_session(owner_id='agent-1',conversation_id='conversation-1',assigned=[]) is None
    session=development_chat_session(owner_id='agent-1',conversation_id='conversation-1',assigned=['development_read'])
    assert session is not None
    reviewer_guard=development_chat_session(owner_id='author',conversation_id='conversation-2',
        assigned=['development_review','development_prepare'])
    assert {item['function']['name'] for item in reviewer_guard.schemas()}=={'development_prepare'}
    denied,denial=reviewer_guard.invoke('development_review',{})
    assert denied['ok'] is False and denial['decision']=='DENY' and denial['executed'] is False
    actor=SimpleNamespace(id='agent-1',config=SimpleNamespace(system_prompt='Use only the tool result.',
        provider_id='ollama-cloud',model_id='fixture-model',tools=['development_read']))
    conversations=ConversationStore(tmp_path/'conversations.sqlite3')
    conversation=conversations.create('agent',actor.id)
    monkeypatch.setattr(server,'CONVERSATIONS',conversations)
    monkeypatch.setattr(server,'_load_model_enabled_agent',lambda _:actor)
    monkeypatch.setattr(server,'current_workspace_root',lambda:root.resolve())
    monkeypatch.setattr(server,'AGENT_CHAT_TRACE_DIR',tmp_path/'traces')
    monkeypatch.setattr(server,'export_local_trace_to_otlp',lambda *args,**kwargs:None)
    monkeypatch.setenv('BAGO_OTEL_EXPORTER_OTLP_ENDPOINT','')
    turns=[]

    def provider_turn(provider_id,model_id,messages,**kwargs):
        turns.append(kwargs.get('tools',[]))
        if len(turns)==1:
            tool_names=[item['function']['name'] for item in kwargs['tools']]
            assert tool_names==['development_read']
            return {'tool_calls':[{'id':'read-1','function':{'name':'development_read','arguments':{'path':'sample_a.py'}}}]}
        tool_reply=json.loads(messages[-1]['content'])
        assert messages[-1]['role']=='tool' and tool_reply['content']==source.rstrip('\n')
        return {'content':'sample_a.py defines summarize(value), which trims surrounding whitespace; it contains 2 lines.'}

    monkeypatch.setattr(server.provider_runtime,'chat_turn',provider_turn)
    result=asyncio.run(server.chat_with_agent(actor.id,server.AgentChatRequest(
        message='Summarize sample_a.py.',conversation_id=conversation['id'],revision=0),Response()))
    assert result['assistant_message'].endswith('2 lines.')
    assert result['sources']==[]
    events=result['read_events']
    assert len(events)==1 and events[0]['kind']=='development_tool'
    assert events[0]['tool_name']=='development_read' and events[0]['decision']=='ALLOW' and events[0]['executed'] is True
    assert (root/'sample_a.py').read_text(encoding='utf8')==source
    trace=json.loads((tmp_path/'traces'/f"{result['trace']['trace_id']}.json").read_text(encoding='utf8'))
    service_spans=[event for event in trace['events'] if event['name']=='service.tool']
    assert service_spans and service_spans[0]['kind']=='tool' and service_spans[0]['status']=='ALLOW'
