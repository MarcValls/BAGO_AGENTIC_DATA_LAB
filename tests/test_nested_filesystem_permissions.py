import json
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.agent_tools.agent_services import AgentServiceSession, execute_filesystem, review_filesystem
from src.agent_tools.document_tools import toolkit
from src.api.agent_services_routes import create_agent_services_router
from src.project_permissions import ProjectContext, ProjectPermissions


@pytest.fixture
def nested(tmp_path):
    toolkit()
    root=tmp_path/'workspace'; root.mkdir(); corpus=root/'corpus'; corpus.mkdir(); sibling=root/'private'; sibling.mkdir()
    permissions=ProjectPermissions(lambda:ProjectContext('project-fixture',root,'selection-fixture','Fixture'))
    snapshot=permissions.snapshot()
    permissions.save(expected_project_id=snapshot['project_id'],expected_binding=snapshot['binding'],expected_revision=snapshot['revision'],read_directories=['corpus'],write_directories=['corpus'],confirmed=True)
    session=AgentServiceSession(workspace=root,root=corpus,owner_id='writer',conversation_id='chat',communications=None,project_permissions=permissions)
    return root,corpus,permissions,session


def apply(root, permissions, proposal, revision):
    reviewed=review_filesystem(workspace=root,proposal_id=proposal['proposal_id'],owner_id='writer',conversation_id='chat',revision=revision,project_permissions=permissions)
    assert reviewed['review_token']
    return execute_filesystem(workspace=root,proposal_id=proposal['proposal_id'],owner_id='writer',conversation_id='chat',revision=revision,review_token=reviewed['review_token'],plan_sha256=reviewed['plan_sha256'],confirmed=True,project_permissions=permissions)


def test_nested_write_review_apply_trash_restore(nested):
    root,corpus,permissions,session=nested
    write,receipt=session.invoke('filesystem_plan',{'operation':'write','target':'nested.txt','content':'synthetic'},['filesystem_plan'])
    assert receipt['decision']=='ALLOW' and not (corpus/'nested.txt').exists()
    assert apply(root,permissions,write,1)['status']=='VERIFIED'
    assert (corpus/'nested.txt').read_text()=='synthetic'
    trash,receipt=session.invoke('filesystem_plan',{'operation':'trash','source':'nested.txt'},['filesystem_plan'])
    assert receipt['decision']=='ALLOW'
    trash_id=trash['plan']['id']
    assert apply(root,permissions,trash,2)['status']=='VERIFIED'
    assert not (corpus/'nested.txt').exists()
    restore,receipt=session.invoke('filesystem_plan',{'operation':'restore','trash_id':trash_id},['filesystem_plan'])
    assert receipt['decision']=='ALLOW'
    assert restore['plan']['source'] is None and restore['plan']['source_snapshot'] is None
    reviewed=review_filesystem(workspace=root,proposal_id=restore['proposal_id'],owner_id='writer',conversation_id='chat',revision=3,project_permissions=permissions)
    assert reviewed['plan']['source'] is None and reviewed['plan']['source_snapshot'] is None
    stored=json.loads((root/'.bago/state/fop'/(restore['proposal_id']+'.json')).read_text(encoding='utf-8'))
    assert stored['plan']['source'] and stored['plan']['source_snapshot']
    applied=execute_filesystem(workspace=root,proposal_id=restore['proposal_id'],owner_id='writer',conversation_id='chat',revision=3,review_token=reviewed['review_token'],plan_sha256=reviewed['plan_sha256'],confirmed=True,project_permissions=permissions)
    assert applied['status']=='VERIFIED' and applied['plan']['source'] is None
    assert applied['receipt']['source'] is None and applied['receipt_redacted_fields']==['source']
    assert (corpus/'nested.txt').read_text()=='synthetic'
    reread=review_filesystem(workspace=root,proposal_id=restore['proposal_id'],owner_id='writer',conversation_id='chat',revision=3,project_permissions=permissions)
    assert reread['status']=='VERIFIED' and reread['receipt']['source'] is None
    stored=json.loads((root/'.bago/state/fop'/(restore['proposal_id']+'.json')).read_text(encoding='utf-8'))
    assert stored['plan']['source'] and stored['plan']['source_snapshot'] and stored['receipt']['source']


def test_nested_restore_http_review_and_apply_redact_internal_payload(nested):
    root,corpus,permissions,session=nested
    (corpus/'original.txt').write_text('synthetic',encoding='utf-8')
    trash,receipt=session.invoke('filesystem_plan',{'operation':'trash','source':'original.txt'},['filesystem_plan'])
    assert receipt['decision']=='ALLOW'
    assert apply(root,permissions,trash,1)['status']=='VERIFIED'
    restore,receipt=session.invoke('filesystem_plan',{'operation':'restore','trash_id':trash['plan']['id']},['filesystem_plan'])
    assert receipt['decision']=='ALLOW'
    app=FastAPI()
    app.include_router(create_agent_services_router(workspace_root=lambda:root,load_agent=lambda _:SimpleNamespace(config=SimpleNamespace(tools=['filesystem_plan'])),owned_conversation=lambda *args:{'revision':2,'status':'active'},communications=lambda:None,project_permissions=lambda:permissions))
    client=TestClient(app)
    route='/api/agent-tools/filesystem/'+restore['proposal_id']
    body={'owner_id':'writer','conversation_id':'chat','revision':2}
    reviewed=client.post(route+'/review',json=body)
    assert reviewed.status_code==200
    data=reviewed.json()
    assert data['plan']['source'] is None and data['plan']['source_snapshot'] is None
    applied=client.post(route+'/execute',json={**body,'review_token':data['review_token'],'plan_sha256':data['plan_sha256'],'confirmed':True})
    assert applied.status_code==200
    data=applied.json()
    assert data['status']=='VERIFIED' and data['plan']['source'] is None and data['receipt']['source'] is None
    assert data['receipt_redacted_fields']==['source'] and (corpus/'original.txt').read_text()=='synthetic'


def test_nested_denies_sibling_and_missing_project_permissions(nested):
    root,corpus,permissions,session=nested
    outside=AgentServiceSession(workspace=root,root=root,owner_id='writer',conversation_id='chat',communications=None,project_permissions=permissions)
    denied,receipt=outside.invoke('filesystem_plan',{'operation':'write','target':'private/blocked.txt','content':'no'},['filesystem_plan'])
    assert receipt['decision']=='DENY' and not (root/'private/blocked.txt').exists()
    proposed,receipt=session.invoke('filesystem_plan',{'operation':'write','target':'nested.txt','content':'synthetic'},['filesystem_plan'])
    assert receipt['decision']=='ALLOW'
    with pytest.raises(ValueError,match='project permissions unavailable'):
        review_filesystem(workspace=root,proposal_id=proposed['proposal_id'],owner_id='writer',conversation_id='chat',revision=1)
    assert not (corpus/'nested.txt').exists()


def test_nested_revocation_blocks_review_and_apply(nested):
    root,corpus,permissions,session=nested
    proposal,receipt=session.invoke('filesystem_plan',{'operation':'write','target':'nested.txt','content':'synthetic'},['filesystem_plan'])
    assert receipt['decision']=='ALLOW'
    reviewed=review_filesystem(workspace=root,proposal_id=proposal['proposal_id'],owner_id='writer',conversation_id='chat',revision=1,project_permissions=permissions)
    snapshot=permissions.snapshot()
    permissions.revoke(expected_project_id=snapshot['project_id'],expected_binding=snapshot['binding'],expected_revision=snapshot['revision'],confirmed=True)
    with pytest.raises(ValueError,match='permissions or selected project changed'):
        execute_filesystem(workspace=root,proposal_id=proposal['proposal_id'],owner_id='writer',conversation_id='chat',revision=1,review_token=reviewed['review_token'],plan_sha256=reviewed['plan_sha256'],confirmed=True,project_permissions=permissions)
    assert not (corpus/'nested.txt').exists()


def test_nested_restore_requires_read_and_write_without_disclosing_trash(nested):
    root,corpus,permissions,session=nested
    (corpus/'original.txt').write_text('synthetic',encoding='utf-8')
    trash,receipt=session.invoke('filesystem_plan',{'operation':'trash','source':'original.txt'},['filesystem_plan'])
    assert receipt['decision']=='ALLOW'
    trash_id=trash['plan']['id']
    assert apply(root,permissions,trash,1)['status']=='VERIFIED'
    snapshot=permissions.snapshot()
    permissions.save(expected_project_id=snapshot['project_id'],expected_binding=snapshot['binding'],expected_revision=snapshot['revision'],read_directories=[],write_directories=['corpus'],confirmed=True)
    current=AgentServiceSession(workspace=root,root=corpus,owner_id='writer',conversation_id='chat',communications=None,project_permissions=permissions)
    denied,receipt=current.invoke('filesystem_plan',{'operation':'restore','trash_id':trash_id},['filesystem_plan'])
    assert denied['state']=='DENIED' and receipt['decision']=='DENY'
    assert 'trash-index' not in str(denied) and 'original.txt' not in str(denied)
    assert not (corpus/'original.txt').exists()
