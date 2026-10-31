"""Isolated contract checks. No provider network/inference or real-user settings."""
import asyncio
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient
from src.api import server
from src.providers import model_policy, runtime, registration, codex, ollama

with TemporaryDirectory(dir=Path(__file__).parent) as folder:
    root = Path(folder)
    catalog = [{"provider_id": "ollama-cloud", "model_id": model, "display_name": model, "label": "Ollama", "state": "ready"} for model in ("alpha", "beta", "gamma")]
    catalog.append({"provider_id": "codex", "model_id": "alternate", "display_name": "Alternate", "label": "Codex", "state": "configured_unverified"})
    def status(provider):
        return {"provider_id": provider, "state": "ready", "model_id": "alpha" if provider == "ollama-cloud" else "registered"}
    registry = root / 'registry.json'
    agents = root / 'agents'; agents.mkdir()
    with patch.dict(os.environ, BAGO_MODEL_POLICY_PATH=str(root / 'policy.json')), patch.object(registration, 'REGISTRY_PATH', registry), patch.object(runtime, 'SELECTION_PATH', root / 'selection.json'), patch.object(runtime, 'status', status), patch.object(runtime, 'model_catalog', lambda: {"models": catalog, "warnings": []}), patch.object(server, 'AGENTS_DIR', agents):
        client = TestClient(server.app)
        initial = client.get('/api/providers/model-policy').json()
        assert initial['revision'] == 'none'
        payload = {'models': [
            {'provider_id': 'ollama-cloud', 'model_id': 'alpha', 'chat': True, 'agent_types': ['rag']},
            {'provider_id': 'ollama-cloud', 'model_id': 'beta', 'chat': True, 'agent_types': ['tool']},
            {'provider_id': 'ollama-cloud', 'model_id': 'gamma', 'chat': False, 'agent_types': ['multi-agent']},
            {'provider_id': 'codex', 'model_id': 'alternate', 'chat': False, 'agent_types': ['tool']},
        ], 'main_chat': 'ollama-cloud|alpha', 'expected_revision': 'none'}
        assert client.put('/api/providers/model-policy', json={**payload, 'main_chat': 'ollama-cloud|gamma'}).status_code >= 400
        assert client.put('/api/providers/model-policy', json={**payload, 'models': payload['models'] * 2}).status_code >= 400
        assert client.put('/api/providers/model-policy', json={**payload, 'models': [{**payload['models'][0], 'model_id': 'unknown'}]}).status_code >= 400
        saved = client.put('/api/providers/model-policy', json=payload)
        assert saved.status_code == 200, saved.text
        assert client.put('/api/providers/model-policy', json=payload).status_code >= 400
        assert runtime.active_selection()['model_id'] == 'alpha'
        assert runtime.select_chat_model('ollama-cloud', 'beta')['model_id'] == 'beta'
        assert client.put('/api/providers/selection', json={'provider_id':'ollama-cloud','model_id':'gamma'}).status_code >= 400
        assert runtime.active_selection()['model_id'] == 'beta'
        assert not (root / 'selection.json').exists(), 'must not rewrite provider registration/legacy selection'
        assert model_policy.assigned('rag','ollama-cloud','beta') == ('ollama-cloud','alpha')
        assert model_policy.assigned('tool','ollama-cloud','alpha') == ('ollama-cloud','beta')
        assert model_policy.assigned('multi-agent','ollama-cloud','alpha') == ('ollama-cloud','gamma')
        visible = client.get('/api/providers/chat-models').json()['models']
        assert [x['model_id'] for x in visible if x['chat_enabled']] == ['alpha','beta']
        draft = {'name':'Fixture','description':'Fixture task','type':'tool','system_prompt':'Fixture only','tools':[]}
        with patch.object(runtime,'chat',lambda *args: json.dumps(draft)):
            generated = asyncio.run(server._generate_agent_draft('fixture',[],'alpha','ollama-cloud'))
        assert generated.model_id == 'beta'
        rejected = client.post('/api/agents/create',json={**draft,'provider_id':'ollama-cloud','model_id':'alpha'})
        assert rejected.status_code >= 400
        accepted = client.post('/api/agents/create',json={**draft,'provider_id':'ollama-cloud','model_id':'beta'})
        assert accepted.status_code == 200, accepted.text
        assert accepted.json()['config']['model_id'] == 'beta'
        before = accepted.json()
        changed = client.put('/api/agents/'+before['id'],json={**before['config'],'type':'rag'})
        assert changed.status_code >= 400
        # Alternate-model adapter receives its own model; the registered model's verification is not overwritten.
        registry.write_text(json.dumps({'providers': {'codex': {'auth_mode':'codex_cli','model_id':'registered','updated_at':'fixture-revision'}}}),encoding='utf-8')
        with patch.object(codex,'chat_turn',lambda model,messages,**kwargs: {'content':model+':'+kwargs['binding'].model_id}):
            assert runtime.chat('codex','alternate',[{'role':'user','content':'fixture'}]) == 'alternate:alternate'
        assert registration.get_registration('codex')['model_id'] == 'registered'
        assert 'last_verified_model_id' not in registration.get_registration('codex')
        # A disabled saved profile stays readable/editable but cannot chat or start another saved task.
        current = client.get('/api/providers/model-policy').json()
        for item in current['models']:
            if item['model_id'] == 'beta':
                item['agent_types'] = []
        result = client.put('/api/providers/model-policy',json={'models':current['models'],'main_chat':current['main_chat'],'expected_revision':current['revision']})
        assert result.status_code == 200, result.text
        assert client.get('/api/agents/'+before['id']).status_code == 200
        blocked = client.post('/api/agents/'+before['id']+'/chat',json={'message':'fixture','conversation_id':'missing','revision':0})
        assert blocked.json()['detail']['code'] == 'agent_model_disabled', blocked.text
        try:
            server._load_model_enabled_agent(before['id'])
            raise AssertionError('GEX loader accepted disabled profile')
        except server.HTTPException as error:
            assert error.detail['code'] == 'agent_model_disabled'
        task = client.get('/api/agents/'+before['id']+'/task').json()
        with patch.dict(os.environ,BAGO_TASK_HISTORY_PATH=str(root/'task-history.sqlite3')):
            blocked = client.post('/api/agents/'+before['id']+'/task-runs',json={'expected_revision':task['revision'],'confirmed':True})
            assert blocked.json()['detail']['code'] == 'agent_model_disabled', blocked.text
            assert client.get('/api/agents/'+before['id']+'/task-runs').json()['runs'] == []
        # Corrupt configuration fails closed.
        (root/'policy.json').write_text('{invalid',encoding='utf-8')
        assert client.get('/api/providers/model-policy').status_code >= 400
    print('PASS: isolated persistence, stale revision, invalid/duplicate/catalog guards, chat filtering/selection, role assignment, agent create/update restrictions, draft routing, alternate adapter, unchanged registrations, existing-profile chat/task/GEX restrictions, readable history/profile, corrupt policy.')
