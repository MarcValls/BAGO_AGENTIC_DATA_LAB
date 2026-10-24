"""Real local SDK/ASGI integration; Google responses are explicit fixtures."""
import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from urllib.request import urlopen
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from src.api.contacts_routes import create_contacts_router
from src.contacts_service.core import API, Contacts, Google, ServiceError, SCOPE


def application(root, api=None):
    app = FastAPI()
    app.include_router(create_contacts_router(state_dir=root, api=api))
    return app


def test_crud_revision_and_independent_sdk_observe_same_state(tmp_path):
    root = tmp_path/'private'
    with TestClient(application(root)) as client:
        added = client.post('/api/contacts/v1/contacts', json={'name':'FICTICIO Uno','phone':'+12025550123'})
        assert added.status_code == 201
        contact = added.json()
        assert Contacts(root).get(contact['id']) == contact
        path = '/api/contacts/v1/contacts/' + contact['id']
        assert client.put(path, json={'name':'Nuevo','phone':contact['phone'],'expected_revision':'stale'}).status_code == 409
        changed = client.put(path, json={'name':'FICTICIO editado','phone':contact['phone'],'expected_revision':contact['revision']})
        assert changed.status_code == 200 and changed.json()['id'] == contact['id']
        assert client.request('DELETE', path, json={'expected_revision':changed.json()['revision'],'confirmed':False}).status_code == 400
        assert client.request('DELETE', path, json={'expected_revision':changed.json()['revision'],'confirmed':True}).status_code == 200
    assert Contacts(root).list()['contacts'] == []


@pytest.mark.parametrize('data',[
    {'name':'FICTICIO','phone':'+1\uff12\uff10\uff12\uff15\uff15\uff15\uff10\uff11\uff10\uff11'},
    {'name':'FICTICIO','email':'client\x00@example.test'},
    {'name':'FICTICIO','email':'client\x7f@example.test'},
])
def test_invalid_destinations_do_not_enter_store(tmp_path, data):
    with TestClient(application(tmp_path/'private')) as client:
        assert client.post('/api/contacts/v1/contacts',json=data).status_code == 400
        assert client.get('/api/contacts/v1/contacts').json()['contacts'] == []


def test_untrusted_origin_bad_body_and_oversize_fail_without_write(tmp_path):
    with TestClient(application(tmp_path/'private')) as client:
        path='/api/contacts/v1/contacts'
        assert client.post(path,json={'name':'FICTICIO','email':'a@example.test'},headers={'Origin':'https://other.invalid'}).status_code==403
        assert client.post(path,content='{}',headers={'Content-Type':'text/plain'}).status_code==400
        assert client.post(path,json=[]).status_code==400
        assert client.post(path,content='x'*(1024*1024+1),headers={'Content-Type':'application/json'}).status_code==413
        reply=client.get(path)
        assert reply.json()['contacts']==[] and reply.headers['Cache-Control']=='no-store'


def test_selective_import_uses_same_preview_revision_and_no_implicit_selection(tmp_path):
    contacts=Contacts(tmp_path/'private')
    preview=contacts.preview_people([{'resourceName':'people/fixture','names':[{'displayName':'FICTICIO'}],
                                    'emailAddresses':[{'value':'a@example.test'},{'value':'b@example.test'}]}])
    with TestClient(application(contacts.root, API(contacts))) as client:
        path='/api/contacts/v1/imports/selected'
        body={'preview_id':preview['preview_id'],'expected_revision':preview['revision'],'duplicate_policy':'skip','selected_ids':[]}
        assert client.post(path,json=body).status_code==400
        body['selected_ids']=[preview['contacts'][1]['selection_id']]
        result=client.post(path,json=body)
        assert result.status_code==200 and len(result.json()['imported'])==1
        assert contacts.list()['contacts'][0]['email']=='b@example.test'


def test_shutdown_closes_router_owned_callback_and_invalidates_pending(tmp_path):
    root=tmp_path/'private'
    contacts=Contacts(root)
    contacts.private.write('google-client.bin',{'client_id':'synthetic.apps.googleusercontent.com','client_secret':'SYNTHETIC'})
    actual=Google
    owners=[]
    def factory(store):
        google=actual(store,transport=lambda *_a,**_kw:{'access_token':'SYNTHETIC','token_type':'Bearer','scope':SCOPE,'expires_in':3600})
        owners.append(google)
        return google
    with patch('src.contacts_service.core.Google',factory):
        with TestClient(application(root)) as client:
            reply=client.post('/api/contacts/v1/google/connect',json={})
            assert reply.status_code==200
            flow=reply.json()
            state=parse_qs(urlparse(flow['authorization_url']).query)['state'][0]
            assert contacts.private.read('google-pending.bin')
    assert contacts.private.read('google-pending.bin') is None
    with pytest.raises(OSError):
        urlopen(flow['callback_uri']+'?state='+state+'&code=SYNTHETIC',timeout=1)
    with pytest.raises(ServiceError,match='closed'):
        owners[0].callback(state,'SYNTHETIC')
    assert not owners[0].status()['connected']


def test_persistence_errors_remain_failure(tmp_path):
    api=API(Contacts(tmp_path/'private'))
    with TestClient(application(api.contacts.root,api)) as client, patch.object(api,'dispatch',side_effect=OSError('synthetic')):
        reply=client.get('/api/contacts/v1/contacts')
        assert reply.status_code==503 and reply.json()['error']['code']=='service_unavailable'


def test_close_stops_listener_even_if_pending_state_cannot_be_removed(tmp_path):
    contacts=Contacts(tmp_path/'private')
    google=Google(contacts)
    contacts.private.write('google-client.bin',{'client_id':'synthetic.apps.googleusercontent.com','client_secret':'SYNTHETIC'})
    flow=google.begin()
    with patch.object(google.private,'remove',side_effect=OSError('synthetic storage failure')):
        with pytest.raises(OSError,match='synthetic'):
            google.close()
    with pytest.raises(OSError):
        urlopen(flow['callback_uri']+'?state=anything&code=SYNTHETIC',timeout=1)
    with pytest.raises(ServiceError,match='closed'):
        google.callback('anything','SYNTHETIC')
