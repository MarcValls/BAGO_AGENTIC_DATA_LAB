"""Real synthetic effects/checks; provider and transport doubles never send."""
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI,Response
from fastapi.testclient import TestClient

from src.agent_tools.document_tools import DocumentAuthorizations
from src.agent_tools.agent_services import AgentServiceSession,SERVICE_TOOL_IDS,review_filesystem,execute_filesystem
from src.api import server
from src.api.agent_services_routes import create_agent_services_router,REVIEW_TEMPLATE
from src.communications.service import CommunicationService
from src.conversations import ConversationStore
from src.services.agent_producers import ProducerStore


@pytest.fixture
def fixture(tmp_path,monkeypatch):
    workspace=tmp_path/'workspace';workspace.mkdir();root=workspace/'corpus';root.mkdir()
    monkeypatch.delenv('BAGO_DOCUMENT_ALLOWED_ROOTS',raising=False)
    monkeypatch.setenv('BAGO_DOCUMENT_OUTPUT_ROOT',str(tmp_path/'reports'))
    class NoSend:
        def send(self,*a,**k):pytest.fail('No real or simulated sending is authorized')
    comms=CommunicationService(tmp_path/'communications',session=NoSend(),workspace_root=workspace)
    contact=comms.create_contact('Contacto sintético','+34911000000')
    return workspace,root,comms,contact


def services(fixture,*,owner='producer',conversation='producer-conv',run=None):
    workspace,root,comms,contact=fixture
    return AgentServiceSession(workspace=workspace,root=root,owner_id=owner,conversation_id=conversation,
        communications=comms,review_work_id=run,contact_id=contact['id'],allow_draft=True)


def produce(fixture,*,accepted=False):
    workspace,root,_,_=fixture;session=services(fixture)
    result,receipt=session.invoke('filesystem_plan',{'operation':'write','target':'delivery.txt','content':'SYNTHETIC DELIVERY ACCEPTANCE V1\n'},SERVICE_TOOL_IDS)
    assert receipt['decision']=='ALLOW'
    proposal=result['proposal_id']
    review=review_filesystem(workspace=workspace,proposal_id=proposal,owner_id='producer',conversation_id='producer-conv',revision=2)
    executed=execute_filesystem(workspace=workspace,proposal_id=proposal,owner_id='producer',conversation_id='producer-conv',revision=2,
        review_token=review['review_token'],plan_sha256=review['plan_sha256'],confirmed=True)
    assert executed['status']=='VERIFIED'
    if accepted:
        return ProducerStore(workspace,acceptance_profile='synthetic-fixture-v1').register(owner_id='producer',conversation_id='producer-conv',
            source_root=root,outputs=[root/'delivery.txt'],receipt=executed['receipt'])
    return executed['production']


def test_filesystem_plan_has_no_user_effect_and_human_exec_requires_current_binding(fixture):
    workspace,root,_,_=fixture;session=services(fixture)
    planned,receipt=session.invoke('filesystem_plan',{'operation':'write','target':'result.txt','content':'hello'},SERVICE_TOOL_IDS)
    assert not (root/'result.txt').exists() and receipt['filesystem_proposal']['status']=='PROPOSED'
    with pytest.raises(ValueError,match='foreign'):
        review_filesystem(workspace=workspace,proposal_id=planned['proposal_id'],owner_id='foreign',conversation_id='producer-conv',revision=2)
    review=review_filesystem(workspace=workspace,proposal_id=planned['proposal_id'],owner_id='producer',conversation_id='producer-conv',revision=2)
    with pytest.raises(ValueError,match='exact current'):
        execute_filesystem(workspace=workspace,proposal_id=planned['proposal_id'],owner_id='producer',conversation_id='producer-conv',revision=3,
            review_token=review['review_token'],plan_sha256=review['plan_sha256'],confirmed=True)
    assert not (root/'result.txt').exists()
    review=review_filesystem(workspace=workspace,proposal_id=planned['proposal_id'],owner_id='producer',conversation_id='producer-conv',revision=3)
    applied=execute_filesystem(workspace=workspace,proposal_id=planned['proposal_id'],owner_id='producer',conversation_id='producer-conv',revision=3,
        review_token=review['review_token'],plan_sha256=review['plan_sha256'],confirmed=True)
    assert applied['status']=='VERIFIED' and (root/'result.txt').read_text()=='hello'
    with pytest.raises(ValueError):
        execute_filesystem(workspace=workspace,proposal_id=planned['proposal_id'],owner_id='producer',conversation_id='producer-conv',revision=3,
            review_token=review['review_token'],plan_sha256=review['plan_sha256'],confirmed=True)


def test_internal_paths_and_self_approval_are_unavailable(fixture):
    workspace,root,_,_=fixture;session=services(fixture)
    (root/'.env').write_text('private')
    result,receipt=session.invoke('filesystem_inventory',{},SERVICE_TOOL_IDS)
    assert receipt['decision']=='ALLOW' and not result['entries']
    for name,args in [('filesystem_plan',{'operation':'write','target':'.bago/registry.json','content':'fake PASS'}),
                      ('filesystem_execute',{'approval':{'confirmed':True}})]:
        result,receipt=session.invoke(name,args,SERVICE_TOOL_IDS)
        assert receipt['decision']=='DENY' and not receipt['executed']
    assert not (root/'.bago').exists()
    internal=workspace/'.bago';internal.mkdir(exist_ok=True)
    from src.agent_tools.document_tools import checked_directory
    with pytest.raises(ValueError,match='INTERNAL_ROOT'):
        checked_directory(internal,workspace)


def test_trusted_integrity_is_real_but_missing_content_acceptance_blocks_and_drafts_notice(fixture):
    workspace,root,comms,contact=fixture;run=produce(fixture)
    receipt=ProducerStore(workspace).load_registered(run['work_id'])
    check=receipt['checks'][0]
    assert check['executed'] and check['returncode']==0 and check['result']=='PASS'
    assert 'business_acceptance' in receipt['required_checks'] and receipt['business_acceptance']=='NOT_RUN'
    for log in check['logs']:assert (workspace/log['path']).exists()
    reviewer=services(fixture,owner='reviewer',conversation='review-conv',run=run['work_id'])
    result,r=reviewer.invoke('delivery_review',{},SERVICE_TOOL_IDS)
    assert result['decision']=='bloqueada' and result['pending'] and not result['send_executed']
    draft,r=reviewer.invoke('delivery_prepare_draft',{'review_id':result['review_id']},SERVICE_TOOL_IDS)
    assert draft['draft']['state']=='draft' and draft['draft']['attachments']==[] and not draft['send_executed']
    assert draft['review']['envelope']['kind']=='aviso' and not comms.runs()
    assert server.AgentConfig.model_validate(REVIEW_TEMPLATE).tools==['delivery_review','delivery_revalidate','delivery_prepare_draft']


def test_positive_host_fixture_has_executed_content_check_and_foreign_review_is_denied(fixture):
    workspace,_,comms,_=fixture;run=produce(fixture,accepted=True)
    evidence=ProducerStore(workspace).provider().load(run['work_id'])
    assert {c['id'] for c in evidence['checks']}=={'artifact_integrity','business_acceptance'}
    assert all(c['executed'] and c['returncode']==0 for c in evidence['checks'])
    reviewer=services(fixture,owner='reviewer',conversation='review-conv',run=run['work_id'])
    result,r=reviewer.invoke('delivery_review',{},SERVICE_TOOL_IDS)
    assert result['decision']=='lista_para_revision',result
    assert 'synthetic' in evidence['checks'][1]['validation_scope']
    other=services(fixture,owner='foreign',conversation='other-conv',run=run['work_id'])
    denied,receipt=other.invoke('delivery_revalidate',{'review_id':result['review_id']},SERVICE_TOOL_IDS)
    assert receipt['decision']=='DENY'
    prepared,_=reviewer.invoke('delivery_prepare_draft',{'review_id':result['review_id']},SERVICE_TOOL_IDS)
    assert prepared['draft']['attachments'] and prepared['draft']['state']=='draft' and not comms.runs()
    artifact=workspace/run['artifacts'][0]['path'];artifact.write_text('tampered')
    stale,_=reviewer.invoke('delivery_revalidate',{'review_id':result['review_id']},SERVICE_TOOL_IDS)
    assert stale['decision']=='bloqueada'


def test_cross_producer_delegation_is_explicit_and_candidate_bound(fixture):
    workspace,root,comms,contact=fixture;run=produce(fixture)
    auth=DocumentAuthorizations()
    args=dict(workspace=workspace,root=root,owner_id='reviewer',conversation_id='review-conv',revision=0,
        assigned=['delivery_review'],confirmed=True,communications=comms,contact_id=contact['id'],review_work_id=run['work_id'])
    with pytest.raises(ValueError,match='CANDIDATE_SCOPE'):
        auth.issue(**args)
    info=auth.issue(**args,review_candidate_id=run['candidate_id'],review_scope_sha256=run['scope_sha256'])
    permit=auth.consume(info['authorization_id'],workspace=workspace,owner_id='reviewer',conversation_id='review-conv',revision=0,assigned=['delivery_review'])
    denied,receipt=permit['services'].invoke('delivery_review',{'work_id':'unselected-run'},permit['assigned'])
    assert receipt['decision']=='DENY'
    allowed,receipt=permit['services'].invoke('delivery_review',{},permit['assigned'])
    assert receipt['decision']=='ALLOW' and allowed['decision']=='bloqueada'


def test_host_endpoints_reject_stale_conversation_and_revoked_assignment(fixture):
    workspace,_,comms,_=fixture;service=services(fixture)
    planned,_=service.invoke('filesystem_plan',{'operation':'mkdir','target':'folder'},SERVICE_TOOL_IDS)
    actor=SimpleNamespace(config=SimpleNamespace(tools=['filesystem_plan']))
    conversation={'revision':2,'status':'active'}
    app=FastAPI();app.include_router(create_agent_services_router(workspace_root=lambda:workspace,load_agent=lambda _:actor,
        owned_conversation=lambda *a:conversation,communications=lambda:comms))
    client=TestClient(app);body={'owner_id':'producer','conversation_id':'producer-conv','revision':2}
    url='/api/agent-tools/filesystem/'+planned['proposal_id']
    reviewed=client.post(url+'/review',json=body).json()
    conversation['revision']=3
    assert client.post(url+'/execute',json={**body,'review_token':reviewed['review_token'],'plan_sha256':reviewed['plan_sha256'],'confirmed':True}).status_code==409
    actor.config.tools=[];body['revision']=3
    assert client.post(url+'/review',json=body).status_code==403


def test_agent_chat_dispatches_real_filesystem_proposal_without_autoexecution(fixture,monkeypatch,tmp_path):
    workspace,root,comms,_=fixture;store=ConversationStore(tmp_path/'conversations.sqlite3');conv=store.create('agent','producer')
    actor=SimpleNamespace(id='producer',config=SimpleNamespace(system_prompt='Prepare only.',provider_id='ollama-cloud',model_id='fixture',tools=['filesystem_plan']))
    monkeypatch.setattr(server,'CONVERSATIONS',store);monkeypatch.setattr(server,'current_workspace_root',lambda:workspace)
    monkeypatch.setattr(server,'_load_model_enabled_agent',lambda _:actor);monkeypatch.setattr(server,'AGENT_CHAT_TRACE_DIR',tmp_path/'traces')
    monkeypatch.setattr(server,'export_local_trace_to_otlp',lambda *a,**k:None)
    auth=DocumentAuthorizations();monkeypatch.setattr(server,'DOCUMENT_AUTHORIZATIONS',auth)
    issued=auth.issue(workspace=workspace,root=root,owner_id='producer',conversation_id=conv['id'],revision=0,assigned=actor.config.tools,confirmed=True,communications=comms)
    turns=iter([{'tool_calls':[{'function':{'name':'filesystem_plan','arguments':{'operation':'write','target':'planned.txt','content':'fixture'}}}]},{'content':'Propuesta preparada; requiere confirmación.'}])
    def turn(*a,**kwargs):
        assert all(t['function']['name']!='filesystem_execute' for t in kwargs['tools'])
        return next(turns)
    monkeypatch.setattr(server.provider_runtime,'chat_turn',turn)
    result=asyncio.run(server.chat_with_agent('producer',server.AgentChatRequest(message='Prepara un archivo.',conversation_id=conv['id'],revision=0,document_authorization_id=issued['authorization_id']),Response()))
    assert result['read_events'][0]['filesystem_proposal'] and not (root/'planned.txt').exists()
    assert result['conversation']['messages'][-1]['references']['read_events'][0]['kind']=='filesystem_tool'


def test_agent_chat_embeds_actual_reviewed_notice_draft_without_sending(fixture,monkeypatch,tmp_path):
    workspace,root,comms,contact=fixture;run=produce(fixture)
    store=ConversationStore(tmp_path/'conversations.sqlite3');conv=store.create('agent','reviewer')
    tools=['delivery_review','delivery_prepare_draft']
    actor=SimpleNamespace(id='reviewer',config=SimpleNamespace(system_prompt='Review selected evidence only.',provider_id='ollama-cloud',model_id='fixture',tools=tools))
    monkeypatch.setattr(server,'CONVERSATIONS',store);monkeypatch.setattr(server,'current_workspace_root',lambda:workspace)
    monkeypatch.setattr(server,'_load_model_enabled_agent',lambda _:actor);monkeypatch.setattr(server,'AGENT_CHAT_TRACE_DIR',tmp_path/'traces')
    monkeypatch.setattr(server,'export_local_trace_to_otlp',lambda *a,**k:None)
    auth=DocumentAuthorizations();monkeypatch.setattr(server,'DOCUMENT_AUTHORIZATIONS',auth)
    info=auth.issue(workspace=workspace,root=root,owner_id='reviewer',conversation_id=conv['id'],revision=0,assigned=tools,
        confirmed=True,communications=comms,review_work_id=run['work_id'],review_candidate_id=run['candidate_id'],review_scope_sha256=run['scope_sha256'],contact_id=contact['id'],allow_draft=True)
    turns=[]
    def turn(provider,model,messages,**kwargs):
        turns.append(messages.copy())
        if len(turns)==1:return {'tool_calls':[{'function':{'name':'delivery_review','arguments':{}}}]}
        if len(turns)==2:
            review=json.loads([m for m in messages if m['role']=='tool'][-1]['content'])
            assert review['decision']=='bloqueada'
            return {'tool_calls':[{'function':{'name':'delivery_prepare_draft','arguments':{'review_id':review['review_id']}}}]}
        draft=json.loads([m for m in messages if m['role']=='tool'][-1]['content'])
        assert draft['draft']['state']=='draft' and not draft['send_executed']
        return {'content':'Revisión bloqueada por falta de revisión de contenido. Aviso en borrador, sin enviar.'}
    monkeypatch.setattr(server.provider_runtime,'chat_turn',turn)
    result=asyncio.run(server.chat_with_agent('reviewer',server.AgentChatRequest(message='Revisa y prepara un aviso.',conversation_id=conv['id'],revision=0,document_authorization_id=info['authorization_id']),Response()))
    references=result['conversation']['messages'][-1]['references']
    assert references['communication_draft']['state']=='draft' and references['communication_draft']['attachments']==[]
    assert len(result['read_events'])==2 and all(r['kind']=='delivery_tool' and r['executed'] for r in result['read_events'])
    assert not comms.runs()
