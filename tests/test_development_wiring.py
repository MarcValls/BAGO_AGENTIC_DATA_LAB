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
