"""Actual server mount, with isolated metadata and no provider/business execution."""
import asyncio
import hashlib
import importlib
import json
from pathlib import Path
import sqlite3
from types import SimpleNamespace

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from fastapi.responses import StreamingResponse
import httpx
import pytest

from src.runtime_status import GitMetadata, RuntimeActivityMiddleware


def tree(root):
    return {p.relative_to(root).as_posix(): (p.stat().st_mtime_ns, hashlib.sha256(p.read_bytes()).hexdigest())
            for p in root.rglob('*') if p.is_file()}


@pytest.fixture
def mounted(monkeypatch, tmp_path):
    monkeypatch.setenv('BAGO_CONVERSATION_DB_PATH', str(tmp_path / 'import-only.sqlite'))
    monkeypatch.setenv('BAGO_AGENT_EVALUATION_DB_PATH', str(tmp_path / 'import-only-evals.sqlite'))
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path / 'appdata'))
    server = importlib.import_module('src.api.server')
    root = tmp_path / 'selected'
    root.mkdir()
    paths = {name: tmp_path / (name + '.json') for name in ('selection', 'registry', 'ollama', 'policy')}
    paths['ollama'].write_text(json.dumps({'auth_mode': 'local_cli', 'model_id': 'fixture:1', 'secret': 'DO_NOT_EXPORT'}), encoding='utf8')
    history = tmp_path / 'history.sqlite'
    history.write_bytes(b'presence metadata only; never open as database')
    monkeypatch.setattr(server, 'CONVERSATIONS', SimpleNamespace(database_path=history))
    monkeypatch.setattr(server, 'WORKSPACE_ROOT', root)
    monkeypatch.setattr(server, '_WORKSPACE_ROOT_PINNED', True)
    monkeypatch.setattr(server, 'AGENT_CHAT_TRACE_DIR', tmp_path / 'traces')
    monkeypatch.setattr(server, '_WORKSPACE_CONFIG_DIR', tmp_path / 'workspace-config')
    monkeypatch.setattr(server, '_WORKSPACE_CONFIG_PATH', tmp_path / 'workspace-config/workspace.json')
    monkeypatch.setattr(server.provider_runtime, 'SELECTION_PATH', paths['selection'])
    monkeypatch.setattr(server.registration, 'REGISTRY_PATH', paths['registry'])
    monkeypatch.setattr(server.ollama, 'CONFIG_PATH', paths['ollama'])
    monkeypatch.setenv('BAGO_MODEL_POLICY_PATH', str(paths['policy']))
    monkeypatch.setenv('BAGO_RUNTIME_MODE', 'host')
    monkeypatch.setattr(server._RUNTIME_STATUS_SERVICE, 'git', GitMetadata())
    calls = []
    def forbidden(*args, **kwargs):
        calls.append(True)
        raise AssertionError('Provider, selection effects, DB or project writes forbidden during polling')
    for module, name in ((server.provider_runtime, 'active_selection'), (server.provider_runtime, 'status'),
                         (server.provider_runtime, 'select_provider'), (server.ollama, 'status'),
                         (server.ollama, '_request'), (server.codex, 'session_status'),
                         (server.registration, 'status'), (server.registration, '_secure_keyring'),
                         (server, '_set_workspace_root'), (sqlite3, 'connect')):
        monkeypatch.setattr(module, name, forbidden)
    routes = server.app.router.routes[:]
    assert server._RUNTIME_ACTIVITY_TRACKER.snapshot()['active_requests'] == 0
    yield server, root, paths, calls
    server.app.router.routes[:] = routes
    assert server._RUNTIME_ACTIVITY_TRACKER.snapshot()['active_requests'] == 0


def test_server_get_uses_pure_metadata_no_database_provider_or_selection_effects(mounted):
    server, root, paths, calls = mounted
    before = tree(root.parent)
    # No lifespan startup: the communications worker is unrelated to this GET.
    response = TestClient(server.app).get('/api/runtime/status')
    assert response.status_code == 200
    body = response.json()
    assert body['backend'] == {'responding': True} and body['activity']['active_requests'] == 0
    assert body['memory']['history']['state'] == 'present' and body['memory']['general']['state'] == 'disconnected'
    assert body['provider']['state'] == 'configured_unverified' and body['provider']['model'] == 'fixture:1'
    assert body['provider']['response_verified'] is False and body['git']['state'] == 'not_repository'
    assert 'DO_NOT_EXPORT' not in response.text and str(root.parent) not in response.text
    assert not calls and tree(root.parent) == before
    assert len([item for item in server.app.user_middleware if item.cls is RuntimeActivityMiddleware]) == 1
    assert len([item for item in server.app.routes if getattr(item, 'path', '') == '/api/runtime/status']) == 1


def test_post_import_launcher_overrides_are_resolved_on_every_poll(mounted, monkeypatch):
    server, root, paths, calls = mounted
    client = TestClient(server.app)
    assert client.get('/api/runtime/status').json()['provider']['model'] == 'fixture:1'
    replacement = root.parent / 'launcher-override.json'
    replacement.write_text(json.dumps({'auth_mode': 'api_key', 'model_id': 'fixture:2'}), encoding='utf8')
    monkeypatch.setattr(server.ollama, 'CONFIG_PATH', replacement)
    assert client.get('/api/runtime/status').json()['provider']['model'] == 'fixture:2'
    second_root = root.parent / 'second-selected'
    second_root.mkdir()
    monkeypatch.setattr(server, 'WORKSPACE_ROOT', second_root)
    snapshot = client.get('/api/runtime/status').json()
    assert snapshot['git']['state'] == 'not_repository' and snapshot['git']['cached'] is False
    assert server.current_workspace_root() == second_root and not calls


def test_provider_metadata_failure_is_partial_and_private(mounted):
    server, root, paths, calls = mounted
    paths['selection'].write_bytes(b'{invalid')
    response = TestClient(server.app).get('/api/runtime/status')
    assert response.status_code == 200 and response.json()['provider']['state'] == 'unavailable'
    assert response.json()['memory']['state'] == 'available' and response.json()['backend']['responding']
    assert 'invalid' not in response.text and str(root) not in response.text and not calls


@pytest.mark.parametrize('finish', ['complete', 'failure', 'cancel'])
def test_server_middleware_counts_waiting_operation_and_cleans_up(mounted, finish):
    server, root, paths, calls = mounted
    async def scenario():
        entered, release = asyncio.Event(), asyncio.Event()
        async def operation():
            entered.set()
            await release.wait()
            if finish == 'failure':
                raise RuntimeError('synthetic integration failure')
            return {'synthetic': True}
        server.app.router.routes.insert(0, APIRoute('/api/runtime-fixture-operation', operation, methods=['GET']))
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app), base_url='http://test') as client:
            pending = asyncio.create_task(client.get('/api/runtime-fixture-operation'))
            await asyncio.wait_for(entered.wait(), 2)
            assert (await client.get('/api/runtime/status')).json()['activity']['active_requests'] == 1
            if finish == 'cancel':
                pending.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await pending
            else:
                release.set()
                if finish == 'failure':
                    with pytest.raises(RuntimeError, match='synthetic integration'):
                        await pending
                else:
                    assert (await pending).status_code == 200
            assert (await client.get('/api/runtime/status')).json()['activity']['active_requests'] == 0
    asyncio.run(scenario())
    assert not calls


def test_integrated_stream_cancel_has_finally_cleanup(mounted):
    server, root, paths, calls = mounted
    async def scenario():
        entered = asyncio.Event()
        async def chunks():
            yield b'synthetic chunk'
            entered.set()
            await asyncio.Event().wait()
        async def stream():
            return StreamingResponse(chunks(), media_type='text/plain')
        server.app.router.routes.insert(0, APIRoute('/api/runtime-fixture-stream', stream, methods=['GET']))
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app), base_url='http://test') as client:
            pending = asyncio.create_task(client.get('/api/runtime-fixture-stream'))
            await asyncio.wait_for(entered.wait(), 2)
            assert (await client.get('/api/runtime/status')).json()['activity']['active_requests'] == 1
            pending.cancel()
            with pytest.raises(asyncio.CancelledError):
                await pending
            assert (await client.get('/api/runtime/status')).json()['activity']['active_requests'] == 0
    asyncio.run(scenario())
    assert not calls
