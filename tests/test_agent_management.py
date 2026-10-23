"""All profile mutations are isolated in tmp_path; no live agents/providers."""
import json
import sqlite3
from pathlib import Path

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from src.api.agent_management_routes import create_agent_management_router

A = 'agent_12345678'


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    directory = tmp_path / 'agents'; directory.mkdir()
    jobs = tmp_path / 'jobs'; jobs.mkdir()
    history = tmp_path / 'history.sqlite3'
    gex = tmp_path / 'gex'; gex.mkdir()
    monkeypatch.setenv('BAGO_TASK_HISTORY_PATH', str(history))
    monkeypatch.setenv('BAGO_GEX_STATE_DIR', str(gex))
    config = {'id': A, 'created_at': '2026-10-22T00:00:00Z', 'config': {'name': 'Agente de prueba', 'description': 'Aislado', 'type': 'tool', 'system_prompt': '', 'tools': []}}
    path = directory / f'{A}.json'; path.write_text(json.dumps(config), encoding='utf-8')
    def load(agent_id):
        target = directory / f'{agent_id}.json'
        if not target.exists(): raise HTTPException(404)
        return json.loads(target.read_text())
    app = FastAPI(); app.include_router(create_agent_management_router(agents_dir=lambda: directory, load_agent=load, jobs_dir=jobs))
    return {'client': TestClient(app), 'path': path, 'directory': directory, 'jobs': jobs, 'history': history, 'gex': gex, 'root': tmp_path}


def review(data):
    response = data['client'].get(f'/api/agents/{A}/deletion-review')
    assert response.status_code == 200
    return response.json()


def delete(data, **changes):
    body = {'confirmed': True, 'expected_revision': review(data)['revision'], **changes}
    return data['client'].request('DELETE', f'/api/agents/{A}', json=body)


def test_review_and_delete_preserves_history_and_recovery(isolated):
    original = isolated['path'].read_bytes()
    preserved = [isolated['root']/name for name in ('conversations.sqlite3','trace.json','evaluation.json')]
    for p in preserved: p.write_bytes(b'untouched')
    checked = review(isolated)
    assert checked['deletable'] is True and len(checked['revision']) == 64
    response = delete(isolated)
    assert response.status_code == 200 and response.json()['history_preserved']
    assert not isolated['path'].exists()
    assert (isolated['directory']/'.deleted'/f"{A}-{checked['revision']}.json").read_bytes() == original
    assert all(p.read_bytes() == b'untouched' for p in preserved)


def test_explicit_confirmation_required(isolated):
    assert delete(isolated, confirmed=False).status_code == 403
    assert isolated['path'].exists()


def test_stale_revision_rejected_after_edit(isolated):
    checked = review(isolated)
    content = json.loads(isolated['path'].read_text()); content['config']['name'] = 'Cambiado'
    isolated['path'].write_text(json.dumps(content))
    response = isolated['client'].request('DELETE',f'/api/agents/{A}',json={'confirmed':True,'expected_revision':checked['revision']})
    assert response.status_code == 409 and response.json()['detail']['code'] == 'profile_revision_conflict'
    assert isolated['path'].exists()


@pytest.mark.parametrize('body',[{}, {'confirmed':'true','expected_revision':'a'*64}, {'confirmed':True,'expected_revision':'bad'}, {'confirmed':True,'expected_revision':'a'*64,'extra':'forbidden'}])
def test_invalid_contract_no_effect(isolated,body):
    assert isolated['client'].request('DELETE',f'/api/agents/{A}',json=body).status_code == 422
    assert isolated['path'].exists()


@pytest.mark.parametrize('state',['running','queued','pending'])
def test_active_job_outside_recent_list_blocks(isolated,state):
    for n in range(130): (isolated['jobs']/f'z{n}.json').write_text(json.dumps({'agent_id':'agent_87654321','status':'success'}))
    (isolated['jobs']/'a-old-active.json').write_text(json.dumps({'agent_id':A,'status':state}))
    assert not review(isolated)['deletable']
    assert delete(isolated).status_code == 409 and isolated['path'].exists()


def test_running_task_blocks_even_after_process_restart(isolated):
    with sqlite3.connect(isolated['history']) as db:
        db.execute('CREATE TABLE task_runs(agent_id TEXT,status TEXT)')
        db.execute('INSERT INTO task_runs VALUES (?,?)',(A,'running'))
    assert review(isolated)['blockers'] == ['saved_task_running']
    assert delete(isolated).status_code == 409


def test_active_governed_run_blocks(isolated):
    with sqlite3.connect(isolated['gex']/'execution.sqlite3') as db:
        db.execute('CREATE TABLE control_records(agent_id TEXT,record_json TEXT)')
        db.execute('INSERT INTO control_records VALUES (?,?)',(A,json.dumps({'state':'RUNNING'})))
    assert review(isolated)['blockers'] == ['governed_execution_active']


def test_corrupt_activity_is_unknown_and_preserved(isolated):
    (isolated['jobs']/'corrupt.json').write_text('broken')
    assert isolated['client'].get(f'/api/agents/{A}/deletion-review').status_code == 503
    assert isolated['path'].exists()


def test_invalid_identity_returns_404(isolated):
    assert isolated['client'].get('/api/agents/not-an-agent/deletion-review').status_code == 404


def test_replay_not_found(isolated):
    revision = review(isolated)['revision']
    assert delete(isolated).status_code == 200
    assert isolated['client'].request('DELETE',f'/api/agents/{A}',json={'confirmed':True,'expected_revision':revision}).status_code == 404


def test_recovery_copy_real_long_windows_path(tmp_path):
    from src.api.agent_management_routes import _recovery_io_path
    identity = 'agent_' + 'a' * 32
    # Keep the backup beyond MAX_PATH even with a short POSIX temporary root.
    padding = max(1, 190 - len(str(tmp_path)) - len('profiles') - 2)
    directory = tmp_path / ('p' * padding) / 'profiles'
    _recovery_io_path(directory).mkdir(parents=True)
    path = directory / f'{identity}.json'
    raw = json.dumps({'id': identity, 'config': {'name': 'Long path isolated'}}).encode()
    _recovery_io_path(path).write_bytes(raw)
    app = FastAPI()
    app.include_router(create_agent_management_router(agents_dir=lambda: directory, load_agent=lambda i: {}, active_check=lambda i: []))
    client = TestClient(app)
    checked = client.get(f'/api/agents/{identity}/deletion-review')
    assert checked.status_code == 200
    revision = checked.json()['revision']
    archive = directory / '.deleted' / f'{identity}-{revision}.json'
    assert len(str(archive)) > 260
    response = client.request('DELETE', f'/api/agents/{identity}', json={'confirmed': True, 'expected_revision': revision})
    assert response.status_code == 200
    assert not _recovery_io_path(path).exists()
    assert _recovery_io_path(archive).read_bytes() == raw


@pytest.mark.parametrize('failure', ['open', 'fsync', 'corrupt', 'unreadable'])
def test_recovery_failure_preserves_exact_original(isolated, monkeypatch, failure):
    from src.api import agent_management_routes as routes
    original = isolated['path'].read_bytes()
    original_open, original_read = Path.open, Path.read_bytes
    def opened(path, *args, **kwargs):
        if '.deleted' in path.parts and failure == 'open':
            raise PermissionError('isolated backup denied')
        return original_open(path, *args, **kwargs)
    def read(path):
        if '.deleted' in path.parts:
            if failure == 'unreadable': raise PermissionError('isolated read denied')
            if failure == 'corrupt': return b'wrong bytes'
        return original_read(path)
    monkeypatch.setattr(Path, 'open', opened)
    monkeypatch.setattr(Path, 'read_bytes', read)
    if failure == 'fsync': monkeypatch.setattr(routes.os, 'fsync', lambda fd: (_ for _ in ()).throw(OSError('isolated fsync failure')))
    response = delete(isolated)
    assert response.status_code == 503
    assert isolated['path'].read_bytes() == original


@pytest.mark.parametrize('matching', [True, False])
def test_existing_archive_never_overwritten(isolated, matching):
    from src.api.agent_management_routes import _recovery_io_path
    checked = review(isolated)
    raw = isolated['path'].read_bytes()
    archive = _recovery_io_path(isolated['directory']/'.deleted'/f"{A}-{checked['revision']}.json")
    archive.parent.mkdir(); archived = raw if matching else b'different existing backup'; archive.write_bytes(archived)
    response = delete(isolated)
    assert response.status_code == (200 if matching else 503)
    assert archive.read_bytes() == archived
    assert isolated['path'].exists() is not matching


def test_unlink_failure_retains_source_and_verified_backup(isolated, monkeypatch):
    from src.api.agent_management_routes import _recovery_io_path
    checked=review(isolated);raw=isolated['path'].read_bytes();original_unlink=Path.unlink
    def unlink(path,*args,**kwargs):
        if path == isolated['path']: raise PermissionError('isolated unlink denied')
        return original_unlink(path,*args,**kwargs)
    monkeypatch.setattr(Path,'unlink',unlink)
    result=delete(isolated)
    assert result.status_code==503 and result.json()['detail']['code']=='delete_failed'
    assert isolated['path'].read_bytes()==raw
    assert _recovery_io_path(isolated['directory']/'.deleted'/f"{A}-{checked['revision']}.json").read_bytes()==raw


def test_real_server_get_list_put_and_delete_isolated(monkeypatch,tmp_path):
    from src.api import server
    from src import jobs
    directory=tmp_path/'profiles'; directory.mkdir()
    monkeypatch.setattr(server,'AGENTS_DIR',directory)
    monkeypatch.setattr(jobs,'JOBS_DIR',tmp_path/'jobs')
    monkeypatch.setenv('BAGO_TASK_HISTORY_PATH',str(tmp_path/'tasks.sqlite3'))
    monkeypatch.setenv('BAGO_GEX_STATE_DIR',str(tmp_path/'gex'))
    monkeypatch.setattr(server.model_policy,'read',lambda:(None,None))
    payload={'id':A,'created_at':'2026-10-22T00:00:00Z','config':{'name':'Inicial','description':'Aislado','type':'tool','system_prompt':'Trabaja con datos de prueba.','tools':[]}}
    (directory/f'{A}.json').write_text(json.dumps(payload))
    client=TestClient(server.app)
    assert any(row['id']==A for row in client.get('/api/agents/list').json()['agents'])
    loaded=client.get(f'/api/agents/{A}').json()
    changed={**loaded['config'],'name':'Guardado desde PUT'}
    assert client.put(f'/api/agents/{A}',json=changed).json()['config']['name']=='Guardado desde PUT'
    assert json.loads((directory/f'{A}.json').read_text())['config']['name']=='Guardado desde PUT'
    checked=client.get(f'/api/agents/{A}/deletion-review').json()
    assert client.request('DELETE',f'/api/agents/{A}',json={'confirmed':True,'expected_revision':checked['revision']}).status_code==200
    assert client.get(f'/api/agents/{A}').status_code==404
