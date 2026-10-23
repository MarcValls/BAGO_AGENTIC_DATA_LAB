"""Completed control turns produce their own real LocalTrace, without live models."""
import asyncio,json
from types import SimpleNamespace
import pytest
from fastapi.testclient import TestClient
from src.api import server
from src.conversations import ConversationStore

@pytest.mark.parametrize('operation',['navigate','help','chat','draft_agent'])
def test_completed_control_turn_has_persisted_scoped_trace(monkeypatch,tmp_path,operation):
    store=ConversationStore(tmp_path/'library.sqlite3')
    conversation=store.create('assistant','app-assistant')
    traces=tmp_path/'traces';traces.mkdir()
    monkeypatch.setattr(server,'CONVERSATIONS',store)
    monkeypatch.setattr(server,'AGENT_CHAT_TRACE_DIR',traces)
    monkeypatch.setattr(server,'current_workspace_root',lambda:tmp_path)
    monkeypatch.setenv('BAGO_OTEL_EXPORTER_OTLP_ENDPOINT','')
    monkeypatch.setattr(server.provider_runtime,'active_selection',lambda:{'provider_id':'fixture','model_id':'fixture-model'})
    monkeypatch.setattr(server.provider_runtime,'chat_turn',lambda *_a,**_k:{'content':'Fixture response'})
    monkeypatch.setattr(server,'_record_chat_cognition_trace',lambda **_:{})
    async def draft(*_):return SimpleNamespace(model_dump=lambda:{'name':'Fixture only','type':'tool'})
    monkeypatch.setattr(server,'_generate_agent_draft',draft)
    request=server.ControlChatRequest(operation=operation,message='hola ayuda' if operation=='help' else 'Synthetic turn',
        view='inspector' if operation=='navigate' else None,conversation_id=conversation['id'],revision=0)
    result=asyncio.run(server.control_chat(request))
    saved=store.get(conversation['id'])
    reference=saved['messages'][-1]['references']['trace']
    assert result['trace']==reference
    raw=json.loads((traces/(reference['trace_id']+'.json')).read_bytes())
    event=raw['events'][0]
    assert event['name']=='assistant.control'
    assert event['attributes']['conversation_id']==conversation['id']
    assert event['attributes']['operation']==result['operation']
    assert event['attributes']['model_invoked']==(operation in ('chat','draft_agent'))
    inspected=TestClient(server.app).get(f"/api/conversations/{conversation['id']}/inspection").json()
    assert inspected['state']=='selected'
    assert inspected['selected']['trace_id']==reference['trace_id']
    assert inspected['selected']['integrity']=='hash_verified'
    assert inspected['selected']['trace']['run_id']==reference['execution_id']

def test_inspection_defaults_to_latest_even_if_unavailable_without_falling_back(tmp_path):
    from src.observability.chat_inspection import inspection
    conversation=dict(id='fixture-conversation',revision=4,messages=[
        dict(id='old',role='assistant',references={'trace':{'trace_id':'trace-1111111111111111','execution_id':'old-run'}}),
        dict(id='new',role='assistant',references={'trace':{'trace_id':'trace-2222222222222222','execution_id':'new-run'}})])
    observed=inspection(conversation,[tmp_path])
    assert observed['state']=='selected' and observed['total']==2
    assert observed['selected']['trace_id']=='trace-2222222222222222'
    assert observed['selected']['state']=='unavailable'
    assert observed['executions'][0]['message_id']=='new'
