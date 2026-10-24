import hashlib
import json
from pathlib import Path
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from src.api.workspaces_routes import create_workspaces_router, validate_workspace_proposal
from src.workspace_sdk import WorkspaceService


def app(parent):
    result=FastAPI(); result.include_router(create_workspaces_router(parent)); return result


def test_api_vertical_create_context_files_trash_git_real(tmp_path):
    with TestClient(app(tmp_path)) as client:
        created=client.post('/api/workspaces/v1/workspaces',json={'name':'fixture','title':'FICTICIO','confirmed':True})
        assert created.status_code==201
        workspace=created.json(); identity=workspace['id']
        assert len(workspace['context_files'])==3
        sdk=WorkspaceService(tmp_path).open(identity)
        def action(operation,**args):
            if operation in {'write','move','trash','restore','delete_trash','git_init','git_stage','git_commit','git_branch'}:
                args['confirmation']={'confirmed':True,'operation':operation,'workspace_id':identity}
            return client.post(f'/api/workspaces/v1/workspaces/{identity}/actions',json={'operation':operation,**args})
        file=action('write',path='demo.txt',text='first\n',expected_sha256=None).json()
        assert sdk.read('demo.txt')['sha256']==file['sha256']
        assert action('write',path='demo.txt',text='stale',expected_sha256='wrong').status_code==409
        trash=action('trash',path='demo.txt',expected_sha256=file['sha256']).json()
        assert not (sdk.root/'demo.txt').exists()
        assert action('restore',trash_id=trash['trash_id'],expected_revision=trash['revision']).json()['sha256']==file['sha256']
        assert action('git_init').status_code==200
        staged=action('git_stage',paths=['demo.txt'],expected_head=None,expected_hashes={'demo.txt':file['sha256']}).json()
        committed=action('git_commit',message='Isolated API fixture',expected_head=None,selection_revision=staged['selection_revision'])
        assert committed.status_code==200 and len(committed.json()['commit'])==40
        plan=action('remote_plan',kind='pr_create',repo='MarcValls/fixture').json()
        assert plan['executed'] is False and plan['status']=='PROPOSED'
        trash=action('trash',path='demo.txt',expected_sha256=file['sha256']).json()
        assert action('delete_trash',trash_id=trash['trash_id'],expected_revision=trash['revision']).json()['deleted']


def test_reject_origin_invalid_bodies_escape_and_wrong_confirmation(tmp_path):
    with TestClient(app(tmp_path)) as client:
        base='/api/workspaces/v1/workspaces'
        assert client.post(base,json={},headers={'Origin':'https://untrusted.invalid'}).status_code==403
        assert client.post(base,json=[]).status_code==400
        assert client.post(base,content='{}',headers={'Content-Type':'text/plain'}).status_code==400
        assert client.post(base,json={'name':'x','title':'X','confirmed':False}).status_code==400
        w=client.post(base,json={'name':'x','title':'X','confirmed':True}).json()
        for path in ('../outside','.git/config','.env'):
            response=client.post(base+'/'+w['id']+'/actions',json={'operation':'write','path':path,'text':'x','expected_sha256':None,'confirmation':{'operation':'write','workspace_id':w['id'],'confirmed':True}})
            assert response.status_code in (400,403)
        assert client.get(base).headers['Cache-Control']=='no-store'


def test_configuration_missing_does_not_adopt_current_cwd(monkeypatch):
    monkeypatch.delenv('BAGO_WORKSPACE_PARENT',raising=False)
    with TestClient(app(None)) as client:
        assert client.get('/api/workspaces/v1/config').json()['configured'] is False
        assert client.get('/api/workspaces/v1/workspaces').status_code==503


@pytest.mark.parametrize('data',[{'intent':'delete'},{'intent':'create','confirmed':True},{'intent':'files','path':'../x'},{'intent':'files','path':'C:/x'},{'intent':'create','name':'../x'}])
def test_model_proposal_cannot_authorize_or_escape(data):
    with pytest.raises(ValueError): validate_workspace_proposal(data)


def test_model_proposal_is_only_preparation_and_no_sdk_side_effect(tmp_path):
    proposal=validate_workspace_proposal({'intent':'create','name':'fixture'})
    assert proposal=={'intent':'create','name':'fixture'}
    assert list(tmp_path.iterdir())==[]


def test_sdk_preserves_primitives_and_declares_reviewed_write_derivation():
    root=Path(__file__).resolve().parents[1]/'src/workspace_sdk'
    expected={'reused_primitives.py':'2c765bbe6f8fc8d1e5fdfbedea1c764426aae9cd367ae4c88aad302c12c70460','sync_primitives.py':'dcaf42d40969f969b797550c7023eb073c45032493b5b0285446935eb50b602b','auth_primitives.py':'440ca7b234326dda4107bc060754c10f9286cc5cd7877880dc2da9719784f368'}
    assert {name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in expected}==expected
    derivation=json.loads((root/'DERIVATION.json').read_text(encoding='utf-8'))
    from src.workspace_sdk.workspace_service import VERSION
    assert derivation['version']==VERSION
    assert derivation['base_reference']=='reference/workspace_service_0_1_0_RC1.py'
    assert derivation['derived_file']=='workspace_service.py'
    assert derivation['version']=='0.2.0-RC1' and derivation['base_version']=='0.1.0-RC1'
    assert derivation['base_sha256']=='5265e768d408975f67ffcff69e21d5923b1b147ede59177a782afb365737f066'
    assert hashlib.sha256((root/derivation['base_reference']).read_bytes()).hexdigest()==derivation['base_sha256']
    assert hashlib.sha256((root/derivation['derived_file']).read_bytes()).hexdigest()==derivation['derived_sha256']
    assert derivation['derived_sha256']!=derivation['base_sha256']



def test_chat_model_fixture_proposes_only_and_real_http_executes_after_review(monkeypatch,tmp_path):
    import asyncio
    from src.api import server
    from src.conversations import ConversationStore
    store=ConversationStore(tmp_path/'history.sqlite3'); conversation=store.create('assistant','app-assistant')
    parent=tmp_path/'projects'; parent.mkdir()
    monkeypatch.setattr(server,'CONVERSATIONS',store)
    monkeypatch.setattr(server.provider_runtime,'active_selection',lambda:{'provider_id':'ollama-cloud','model_id':'test-model','label':'Fixture','state':'configured_unverified'})
    monkeypatch.setattr(server,'_record_chat_cognition_trace',lambda **_:{'trace_id':'synthetic'})
    monkeypatch.setattr(server.ollama,'chat_turn',lambda *_a,**_k:{'tool_calls':[{'function':{'name':'resolve_control_request','arguments':{'decision':'workspace_action','intent':'create','name':'chat-demo','reply':'Revisa la creación antes de ejecutar.'}}}]})
    reply=asyncio.run(server.control_chat(server.ControlChatRequest(operation='chat',message='Crea un proyecto nuevo',conversation_id=conversation['id'],revision=0)))
    assert reply['operation']=='workspace_action'
    assert reply['workspace_proposal']=={'intent':'create','name':'chat-demo'}
    assert reply['conversation']['messages'][-1]['references']['workspace_proposal']==reply['workspace_proposal']
    assert list(parent.iterdir())==[]
    with TestClient(app(parent)) as client:
        created=client.post('/api/workspaces/v1/workspaces',json={'name':reply['workspace_proposal']['name'],'title':'FICTICIO desde chat','confirmed':True})
        assert created.status_code==201
    sdk=WorkspaceService(parent).open(created.json()['id'])
    assert 'FICTICIO desde chat' in sdk.read('.bago/context/PROJECT_CONTEXT.md')['text']
    assert server._control_request_from_arguments({'decision':'workspace_action','intent':'git','reply':'x','confirmed':True}) is None
