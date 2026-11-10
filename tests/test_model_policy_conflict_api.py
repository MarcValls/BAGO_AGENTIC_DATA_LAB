from fastapi.testclient import TestClient
from src.api import server

def test_model_policy_conflict_http_and_storage(tmp_path, monkeypatch):
    monkeypatch.setenv('BAGO_MODEL_POLICY_PATH',str(tmp_path/'policy.json'))
    model={'provider_id':'ollama-cloud','model_id':'fixture','label':'Fixture','state':'ready'}
    monkeypatch.setattr(server.provider_runtime,'model_catalog',lambda:{'models':[model],'warnings':[]})
    client=TestClient(server.app)
    request={'models':[{'provider_id':'ollama-cloud','model_id':'fixture','orchestrator':True,'agent_types':['rag']}], 'main_chat':'ollama-cloud|fixture','expected_revision':'none'}
    first=client.put('/api/providers/model-policy',json=request)
    assert first.status_code==200,first.text
    before=(tmp_path/'policy.json').read_bytes()
    stale=client.put('/api/providers/model-policy',json=request)
    assert stale.status_code==409,stale.text
    assert stale.json()['detail']['code']=='model_policy_conflict'
    assert (tmp_path/'policy.json').read_bytes()==before

def test_provider_unavailable_remains_503(monkeypatch):
    def fail():
        raise server.provider_runtime.ProviderRuntimeError('model_policy_unavailable','Unavailable')
    monkeypatch.setattr(server.model_policy,'read',fail)
    result=TestClient(server.app).get('/api/providers/model-policy')
    assert result.status_code==503
    assert result.json()['detail']['code']=='model_policy_unavailable'
