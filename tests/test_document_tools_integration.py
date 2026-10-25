"""Synthetic corpus and real handlers; provider doubles are explicitly scoped."""
import asyncio
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, Response
from fastapi.testclient import TestClient

from src.agent_tools import document_tools as dt
from src.api import server
from src.api.document_tools_routes import create_document_tools_router
from src.capabilities.manager import agent_tool_catalog
from src.conversations import ConversationStore


@pytest.fixture
def corpus(tmp_path, monkeypatch):
    root=tmp_path/'corpus';root.mkdir()
    (root/'invoice.txt').write_text('FAC-2025001 EUR 120.00\n',encoding='utf8')
    (root/'payment.txt').write_text('FAC-2025001 EUR 120.00\n',encoding='utf8')
    monkeypatch.setenv('BAGO_DOCUMENT_OUTPUT_ROOT',str(tmp_path/'reports'))
    monkeypatch.delenv('BAGO_DOCUMENT_ALLOWED_ROOTS',raising=False)
    return root


def grant(store, root, tmp_path, *, assigned=None, export=False, confirmed=True):
    assigned=assigned if assigned is not None else list(dt.DOCUMENT_TOOL_IDS)
    info=store.issue(workspace=root,owner_id='agent-docs',conversation_id='conv-docs',revision=0,
        root=root,assigned=assigned,confirmed=confirmed,allow_export=export,evidence_root=tmp_path/'receipts')
    permit=store.consume(info['authorization_id'],owner_id='agent-docs',conversation_id='conv-docs',revision=0,
        workspace=root,assigned=assigned)
    return info,permit


def test_assignment_consent_expiry_scope_and_single_use(corpus,tmp_path):
    store=dt.DocumentAuthorizations()
    with pytest.raises(dt.DocumentAccessError,match='CONSENT_OR_ASSIGNMENT'):
        grant(store,corpus,tmp_path,confirmed=False)
    with pytest.raises(dt.DocumentAccessError,match='CONSENT_OR_ASSIGNMENT'):
        grant(store,corpus,tmp_path,assigned=[])
    info,permit=grant(store,corpus,tmp_path,assigned=['document_inventory'])
    with pytest.raises(dt.DocumentAccessError,match='AUTHORIZATION_REQUIRED'):
        store.consume(info['authorization_id'],owner_id='agent-docs',conversation_id='conv-docs',revision=0,workspace=corpus,assigned=['document_inventory'])
    denied,receipt=permit['session'].invoke('document_extract',{'paths':['invoice.txt']},permit)
    assert denied['reason_code']=='DOCUMENT_TOOL_NOT_ASSIGNED' and not receipt['executed']
    issued=store.issue(workspace=corpus,owner_id='agent-docs',conversation_id='conv-docs',revision=1,root=corpus,assigned=['document_inventory'],confirmed=True)
    with pytest.raises(dt.DocumentAccessError,match='SCOPE_MISMATCH'):
        store.consume(issued['authorization_id'],owner_id='other',conversation_id='conv-docs',revision=1,workspace=corpus,assigned=['document_inventory'])
    store.grants[issued['authorization_id']]['expires_at']=0
    with pytest.raises(dt.DocumentAccessError,match='AUTHORIZATION_EXPIRED'):
        store.consume(issued['authorization_id'],owner_id='agent-docs',conversation_id='conv-docs',revision=1,workspace=corpus,assigned=['document_inventory'])


def test_metadata_browse_contains_scope_and_snapshot_changes(corpus,tmp_path):
    assert dt.browse(None,corpus)['roots'][0]['path']==str(corpus.resolve())
    with pytest.raises(dt.DocumentAccessError,match='ROOT_NOT_ALLOWED'):
        dt.browse(str(tmp_path),corpus)
    _,permit=grant(dt.DocumentAuthorizations(),corpus,tmp_path)
    (corpus/'invoice.txt').write_text('modified',encoding='utf8')
    result,receipt=permit['session'].invoke('document_extract',{'paths':['invoice.txt']},permit)
    assert result['reason_code']=='DOCUMENT_SNAPSHOT_CHANGED' and not receipt['executed']


def test_inventory_cursor_no_silent_truncation(corpus,tmp_path):
    for index in range(103):
        (corpus/f'{index:03}.txt').write_text(str(index),encoding='utf8')
    _,permit=grant(dt.DocumentAuthorizations(),corpus,tmp_path)
    one,r1=permit['session'].invoke('document_inventory',{},permit)
    assert len(one['records'])==100 and not one['corpus_coverage']['complete']
    two,r2=permit['session'].invoke('document_inventory',{'cursor':one['next_cursor']},permit)
    assert len(two['records'])==5 and two['corpus_coverage']['complete']
    assert not ({r['source']['path'] for r in one['records']} & {r['source']['path'] for r in two['records']})
    assert r1['executed'] and r2['executed']


def test_opaque_bundles_output_opt_in_and_receipt_hashes(corpus,tmp_path):
    store=dt.DocumentAuthorizations();_,permit=grant(store,corpus,tmp_path)
    result,receipt=permit['session'].invoke('document_extract',{'paths':['invoice.txt','payment.txt']},permit)
    assert result['state']=='EXECUTED' and receipt['executed']
    assert hashlib.sha256(json.dumps(result,sort_keys=True).encode()).hexdigest()==receipt['result_sha256']
    evidence=Path(receipt['evidence_path']); assert hashlib.sha256(evidence.read_bytes()).hexdigest()==receipt['evidence_sha256']
    bad,_=permit['session'].invoke('document_relate',{'bundle_id':'forged','bundle':result},permit)
    assert bad['reason_code']=='INVALID_DOCUMENT_ARGUMENTS'
    relationships,_=permit['session'].invoke('document_relate',{'bundle_id':result['bundle_id']},permit)
    assert relationships['relations'] and not relationships['conclusions_confirmed']
    refused,r=permit['session'].invoke('document_export',{'bundle_id':result['bundle_id']},permit)
    assert refused['reason_code']=='DOCUMENT_OUTPUT_CONSENT_REQUIRED' and not r['executed']
    permit['allow_export']=True
    exported,r=permit['session'].invoke('document_export',{'bundle_id':result['bundle_id'],'format':'csv'},permit)
    assert exported['state']=='EXECUTED' and r['decision']=='ALLOW'
    assert store.report(r['receipt_id'],owner_id='agent-docs',conversation_id='conv-docs').exists()
    Path(exported['output']['path']).write_bytes(b'changed')
    with pytest.raises(dt.DocumentAccessError,match='REPORT_INTEGRITY'):
        store.report(r['receipt_id'],owner_id='agent-docs',conversation_id='conv-docs')


def test_missing_receipt_is_failure_after_execution(corpus,tmp_path):
    _,permit=grant(dt.DocumentAuthorizations(),corpus,tmp_path)
    evidence=tmp_path/'not-a-directory';evidence.write_text('x')
    permit['session'].evidence_root=evidence
    result,receipt=permit['session'].invoke('document_extract',{'paths':['invoice.txt']},permit)
    assert result['state']=='FAILED' and receipt['decision']=='FAIL' and receipt['executed']


def test_agent_chat_real_handler_citation_and_trace_with_provider_double(corpus,tmp_path,monkeypatch):
    actor=SimpleNamespace(id='agent-docs',config=SimpleNamespace(system_prompt='Use only returned evidence.',provider_id='ollama-cloud',model_id='gemma4:31b',tools=['document_extract']))
    conversations=ConversationStore(tmp_path/'conversations.sqlite3');conversation=conversations.create('agent','agent-docs')
    monkeypatch.setattr(server,'CONVERSATIONS',conversations)
    monkeypatch.setattr(server,'_load_model_enabled_agent',lambda _:actor)
    monkeypatch.setattr(server,'current_workspace_root',lambda:corpus.resolve())
    monkeypatch.setattr(server,'AGENT_CHAT_TRACE_DIR',tmp_path/'traces')
    monkeypatch.setattr(server,'export_local_trace_to_otlp',lambda *a,**k:None)
    store=dt.DocumentAuthorizations();monkeypatch.setattr(server,'DOCUMENT_AUTHORIZATIONS',store)
    info=store.issue(workspace=corpus,owner_id=actor.id,conversation_id=conversation['id'],revision=0,root=corpus,assigned=actor.config.tools,confirmed=True,evidence_root=tmp_path/'receipts')
    turns=[]
    def turn(provider,model,messages,**kwargs):
        turns.append((messages.copy(),kwargs))
        if len(turns)==1:
            assert [t['function']['name'] for t in kwargs['tools']]==['document_extract']
            return {'tool_calls':[{'id':'call-doc','function':{'name':'document_extract','arguments':{'paths':['invoice.txt']}}}]}
        tool=json.loads([m for m in messages if m['role']=='tool'][-1]['content'])
        assert tool['records'][0]['segments'][0]['text']=='FAC-2025001 EUR 120.00'
        return {'content':'Leído invoice.txt, línea 1, EUR 120.00; pago no confirmado.'}
    monkeypatch.setattr(server.provider_runtime,'chat_turn',turn)
    response=Response()
    result=asyncio.run(server.chat_with_agent(actor.id,server.AgentChatRequest(message='Lee invoice.txt.',conversation_id=conversation['id'],revision=0,document_authorization_id=info['authorization_id']),response))
    assert result['sources'][0]['file_sha256']==hashlib.sha256((corpus/'invoice.txt').read_bytes()).hexdigest()
    assert result['sources'][0]['locations']==[{'line':1}]
    assert result['read_events'][0]['executed'] and result['read_events'][0]['decision']=='ALLOW'
    trace=json.loads((tmp_path/'traces'/f"{result['trace']['trace_id']}.json").read_text(encoding='utf8'))
    events=[e for e in trace['events'] if e['name']=='document_extract']
    assert events and events[0]['kind']=='tool'
    assert 'FAC-2025001' not in json.dumps(trace)


def test_agent_without_grant_receives_no_document_tools(corpus,monkeypatch):
    captured=[]
    def turn(*args,**kwargs):captured.extend(kwargs['tools']);return {'content':'No se han autorizado documentos.'}
    monkeypatch.setattr(server.provider_runtime,'chat_turn',turn)
    asyncio.run(server._chat_with_workspace_read('model',[{'role':'system','content':'review'}],[],workspace_root=corpus))
    assert not any(t['function']['name'].startswith('document_') for t in captured)


def test_routes_require_explicit_review_and_registry_owns_ui(corpus,tmp_path):
    actor=SimpleNamespace(config=SimpleNamespace(tools=['document_extract']))
    app=FastAPI();app.include_router(create_document_tools_router(workspace_root=lambda:corpus,load_agent=lambda _:actor,
        owned_conversation=lambda *a:{'revision':0,'status':'active'},evidence_root=lambda:tmp_path/'receipt'))
    client=TestClient(app)
    assert client.get('/api/document-tools/folders').status_code==200
    assert client.get('/api/document-tools/folders',params={'path':str(tmp_path)}).status_code==422
    body={'owner_id':'a','conversation_id':'c','revision':0,'root':str(corpus),'confirmed':False}
    assert client.post('/api/document-tools/authorizations',json=body).status_code==422
    body['confirmed']=True
    assert client.post('/api/document-tools/authorizations',json=body).status_code==200
    assert client.post('/api/document-tools/authorizations',json={**body,'confirmed':'true'}).status_code==422
    assert client.post('/api/document-tools/authorizations',json={**body,'allow_export':True,'expected_output_directory':str(tmp_path/'other')}).status_code==422
    actor.config.tools.append('document_export')
    assert client.post('/api/document-tools/authorizations',json={**body,'allow_export':True,'expected_output_directory':str(tmp_path/'reports')}).status_code==200
    assert client.post('/api/document-tools/authorizations',json=body,headers={'Origin':'https://other.invalid'}).status_code==403
    registered={item['id'] for item in agent_tool_catalog()}
    assert dt.DOCUMENT_TOOL_IDS<=registered
    source=(Path(__file__).resolve().parents[1]/'frontend/src/components/AgentBuilder.tsx').read_text(encoding='utf8')
    assert 'value={agent.type}' in source and 'value={agentStateLabel(agent.type)}' not in source
    assert 'TOOL_OPTIONS' not in source and "fetch('/api/capabilities'" in source
