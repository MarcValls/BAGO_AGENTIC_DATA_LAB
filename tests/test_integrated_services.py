"""Cross-service composition acceptance on isolated synthetic data only."""
import asyncio
import hashlib
import json
import sqlite3
from pathlib import Path
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from src.api.contacts_routes import create_contacts_router
from src.api.communication_routes import create_communication_router
from src.contacts_service.core import Contacts
from src.communications import CommunicationService, CommunicationError
from src.services.contacts_bridge import ContactsBridge


def setup(tmp_path):
    root=tmp_path/'contacts'; contacts=Contacts(root)
    service=CommunicationService(tmp_path/'comms',workspace_root=tmp_path,contacts_store=ContactsBridge(root))
    app=FastAPI();app.include_router(create_contacts_router(root));app.include_router(create_communication_router(service))
    return contacts,service,TestClient(app)


def test_canonical_contacts_alias_crud_and_snapshot(tmp_path):
    contacts,service,client=setup(tmp_path)
    with client:
        c=client.post('/api/contacts/v1/contacts',json={'name':'FICTICIO Uno','phone':'+12025550123'}).json()
        assert client.get('/api/communications/contacts').json()['contacts']==[{k:c[k] for k in ('id','name','phone')}]
        d=client.post('/api/communications/drafts',json={'contact_id':c['id'],'text':'FICTICIO No enviar'}).json()
        assert d['recipient']['id']==c['id'] and d['state']=='draft'
        contacts.update(c['id'],{'name':'FICTICIO Nuevo','phone':'+12025550124','expected_revision':c['revision']})
        assert service.get_draft(d['id'])['recipient']['phone']=='+12025550123'
        assert service.contacts()[0]['phone']=='+12025550124'
        assert service.runs()==[]
        added=client.post('/api/communications/contacts',json={'name':'FICTICIO Dos','phone':'+12025550125'}).json()
        assert contacts.get(added['id'])['phone']==added['phone']
        assert client.post('/api/communications/contacts',json={'name':'Dup','phone':added['phone']}).status_code==409


def test_email_only_and_unicode_phone_not_whatsapp_targets(tmp_path):
    contacts,service,_=setup(tmp_path)
    c=contacts.add({'name':'FICTICIO Email','email':'fixture@example.invalid'})
    assert service.contacts()[0]['id']==c['id']
    with pytest.raises(CommunicationError):service.create_draft(c['id'],'text')
    with pytest.raises(CommunicationError):service.create_contact('FICTICIO','+12٣٤٥٦٧٨٩٠')


def test_legacy_import_idempotent_preserves_ids_and_originals(tmp_path):
    legacy=CommunicationService(tmp_path/'comms',workspace_root=tmp_path)
    c=legacy.create_contact('FICTICIO Legacy','+12025550123')
    d=legacy.create_draft(c['id'],'Keep immutable')
    original=(legacy.root/'communications.sqlite3').read_bytes()
    bridge=ContactsBridge(tmp_path/'contacts')
    linked=CommunicationService(legacy.root,workspace_root=tmp_path,contacts_store=bridge)
    assert linked.contacts()==[c] and linked.contacts()==[c]
    assert linked.get_draft(d['id'])==d
    assert (legacy.root/'communications.sqlite3').read_bytes()==original
    canonical=Contacts(tmp_path/'contacts');new=canonical.get(c['id'])
    canonical.update(c['id'],{'name':'FICTICIO Edited','phone':'+12025550124','expected_revision':new['revision']})
    assert linked.contacts()[0]['phone']=='+12025550124'
    new=canonical.get(c['id']);canonical.delete(c['id'],{'confirmed':True,'expected_revision':new['revision']})
    assert linked.contacts()==[] # no resurrection from retained legacy source
    assert linked.get_draft(d['id'])['recipient']==c


def test_legacy_collision_rolls_back_whole_import(tmp_path):
    legacy=CommunicationService(tmp_path/'comms',workspace_root=tmp_path)
    one=legacy.create_contact('FICTICIO One','+12025550123')
    legacy.create_contact('FICTICIO Collision','+12025550124')
    canonical=Contacts(tmp_path/'contacts');existing=canonical.add({'name':'FICTICIO Existing','phone':'+12025550124'})
    linked=CommunicationService(legacy.root,workspace_root=tmp_path,contacts_store=ContactsBridge(canonical.root))
    with pytest.raises(CommunicationError,match='duplicado'):linked.contacts()
    assert [c['id'] for c in canonical.list()['contacts']]==[existing['id']]
    assert len(legacy.contacts())==2


def test_routes_and_proposal_contracts_preserved():
    from src.api import server
    paths={r.path for r in server.app.routes}
    for path in ('/api/contacts/v1/{path:path}','/api/workspaces/v1/{path:path}','/api/communications/drafts','/api/whatsapp/session','/api/agents/{agent_id}/deletion-review'):
        assert path in paths
    decisions=server.CONTROL_REQUEST_TOOL['function']['parameters']['properties']['decision']['enum']
    assert {'communication_draft','workspace_action'}<=set(decisions)
    assert server._control_request_from_arguments({'decision':'workspace_action','intent':'git','reply':'Review','confirmed':True}) is None


def test_chat_both_references_coexist_without_effects(monkeypatch,tmp_path):
    from src.api import server
    from src.conversations import ConversationStore
    contacts,service,_=setup(tmp_path)
    contact=contacts.add({'name':'FICTICIO Chat','phone':'+12025550123'})
    store=ConversationStore(tmp_path/'conversations.sqlite3');conv=store.create('assistant','app-assistant')
    monkeypatch.setattr(server,'CONVERSATIONS',store)
    monkeypatch.setattr(server,'_communication_service',lambda:service)
    monkeypatch.setattr(server.provider_runtime,'active_selection',lambda:{'provider_id':'codex','model_id':'fixture'})
    selected={'decision':'communication_draft','communication':{'contact_id':contact['id'],'text':'No enviar'},'reply':'Review'}
    def chat(*a,**k):return {'tool_calls':[{'function':{'name':'resolve_control_request','arguments':dict(selected)}}]}
    monkeypatch.setattr(server.provider_runtime,'chat_turn',chat)
    first=asyncio.run(server.control_chat(server.ControlChatRequest(message='Prepara',conversation_id=conv['id'],revision=0)))
    selected.clear();selected.update(decision='workspace_action',intent='create',name='should-not-exist',reply='Revisa')
    second=asyncio.run(server.control_chat(server.ControlChatRequest(message='Crear proyecto',conversation_id=conv['id'],revision=first['revision'])))
    messages=store.get(conv['id'])['messages']
    assert messages[1]['references']['communication_draft_id']==first['communication_draft']['id']
    assert messages[3]['references']['workspace_proposal']['name']=='should-not-exist'
    assert second['operation']=='workspace_action' and service.runs()==[]
    assert not (tmp_path/'should-not-exist').exists()


def test_create_alias_reconciles_before_adding_duplicate(tmp_path):
    legacy=CommunicationService(tmp_path/'comms',workspace_root=tmp_path)
    c=legacy.create_contact('FICTICIO Legacy','+12025550123')
    linked=CommunicationService(legacy.root,workspace_root=tmp_path,contacts_store=ContactsBridge(tmp_path/'contacts'))
    with pytest.raises(CommunicationError) as error:
        linked.create_contact('FICTICIO Duplicate','+12025550123')
    assert error.value.status==409
    assert linked.contacts()==[c] and legacy.contacts()==[c]


def test_bridge_persistence_failure_is_visible_without_losing_original(tmp_path,monkeypatch):
    legacy=CommunicationService(tmp_path/'comms',workspace_root=tmp_path)
    c=legacy.create_contact('FICTICIO Keep','+12025550123')
    bridge=ContactsBridge(tmp_path/'contacts')
    def broken():raise OSError('synthetic persistence failure')
    monkeypatch.setattr(bridge,'_store',broken)
    linked=CommunicationService(legacy.root,workspace_root=tmp_path,contacts_store=bridge)
    with pytest.raises(CommunicationError) as error:linked.contacts()
    assert error.value.status==503 and legacy.contacts()==[c]
