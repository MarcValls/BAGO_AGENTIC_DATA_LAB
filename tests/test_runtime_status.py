"""Isolated PREPARED module only; never imports the product server/providers."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import threading

import httpx
import pytest
from fastapi import FastAPI

from src.runtime_status import (ActivityTracker, GitMetadata, MetadataError, ProviderSelectionMetadata,
                            RuntimeActivityMiddleware, RuntimeStatus, create_runtime_status_router)


def run(awaitable):
    return asyncio.run(awaitable)


def service(root, *, context=None, provider=None, tracker=None, git=None, timeout=1.0):
    return RuntimeStatus(workspace_root=lambda: root,
        context_metadata=context or (lambda: {'memory': {'kind': 'conversation_history', 'state': 'present'}, 'paths': ['PRIVATE PATH NOT EXPORTED']}),
        provider_selection=provider or (lambda: {'provider_id': 'ollama-cloud', 'model_id': 'fixture:1', 'state': 'configured_unverified', 'credential': 'PRIVATE TOKEN NOT EXPORTED'}),
        tracker=tracker or ActivityTracker(), git=git, callback_timeout=timeout)


def application(owner, *, inner=None):
    app = FastAPI()
    app.include_router(create_runtime_status_router(owner))
    app.add_middleware(RuntimeActivityMiddleware, tracker=owner.tracker)
    return app


def files(root):
    return {path.relative_to(root).as_posix(): (path.stat().st_mtime_ns, hashlib.sha256(path.read_bytes()).hexdigest())
            for path in root.rglob('*') if path.is_file()}


def test_constructor_and_metadata_get_do_not_write_or_export_context_payload(tmp_path):
    before = files(tmp_path)
    owner = service(tmp_path)
    assert files(tmp_path) == before
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=application(owner)), base_url='http://test') as client:
            response = await client.get('/api/runtime/status')
            assert response.status_code == 200 and response.headers['Cache-Control'] == 'no-store'
            body = response.json()
            assert body['backend'] == {'responding': True}
            assert body['activity']['active_requests'] == 0 and body['activity']['state'] == 'idle'
            assert body['memory']['history']['state'] == 'present'
            assert body['memory']['general']['state'] == 'disconnected'
            assert body['provider']['state'] == 'configured_unverified'
            assert body['provider']['response_verified'] is False
            assert body['git']['state'] == 'not_repository' and body['git']['remote_verification'] == 'not_checked'
            for forbidden in ('PRIVATE', str(tmp_path), 'credential', 'workspace_root', 'provider_id'):
                assert forbidden not in response.text
            assert datetime.fromisoformat(body['checked_at']).utcoffset().total_seconds() == 0
    run(scenario())
    assert files(tmp_path) == before


@pytest.mark.parametrize('state', ['present', 'absent'])
def test_history_presence_is_not_general_memory_or_semantic_retrieval(tmp_path, state):
    snapshot = run(service(tmp_path, context=lambda: {'memory': {'kind': 'conversation_history', 'state': state}}).snapshot())
    assert snapshot['memory']['history'] == {'kind': 'conversation_history', 'state': state, 'proof': 'metadata_presence_only'}
    assert snapshot['memory']['general']['state'] == 'disconnected'


def test_source_failures_are_isolated_and_do_not_export_raw_errors(tmp_path):
    def fail():
        raise RuntimeError('PRIVATE ERROR https://token.example.invalid/path')
    snapshot = run(service(tmp_path, context=fail).snapshot())
    assert snapshot['memory']['error_code'] == 'memory_metadata_unavailable'
    assert snapshot['provider']['state'] == 'configured_unverified' and snapshot['git']['state'] == 'not_repository'
    snapshot = run(service(tmp_path, provider=fail).snapshot())
    assert snapshot['provider']['error_code'] == 'provider_metadata_unavailable'
    assert snapshot['memory']['state'] == 'available'
    assert 'PRIVATE' not in json.dumps(snapshot)


def test_slow_metadata_callback_times_out_without_losing_other_groups(tmp_path):
    async def stalled():
        await asyncio.Event().wait()
    snapshot = run(service(tmp_path, context=stalled, timeout=0.01).snapshot())
    assert snapshot['memory']['state'] == 'unavailable' and snapshot['backend']['responding']
    assert snapshot['provider']['state'] == 'configured_unverified'


@pytest.mark.parametrize('malformed', [None, [], {}, {'state': 'ready', 'provider_id': 'codex', 'model_id': 'https://private.invalid/token'}, {'state': 'ready', 'model_id': 'fixture'}])
def test_invalid_provider_snapshot_cannot_be_ready(tmp_path, malformed):
    snapshot = run(service(tmp_path, provider=lambda: malformed).snapshot())
    assert snapshot['provider']['state'] == 'unavailable' and not snapshot['provider']['response_verified']


def test_awaiting_request_is_busy_and_returns_idle_after_completion(tmp_path):
    async def scenario():
        owner, entered, release = service(tmp_path), asyncio.Event(), asyncio.Event()
        app = application(owner)
        @app.get('/api/operation')
        async def operation():
            entered.set()
            await release.wait()
            return {'synthetic': True}
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            operation_task = asyncio.create_task(client.get('/api/operation?private=DO_NOT_EXPORT'))
            await asyncio.wait_for(entered.wait(), 2)
            snapshot = (await client.get('/api/runtime/status')).json()
            assert snapshot['activity']['active_requests'] == 1 and snapshot['activity']['state'] == 'active'
            assert 'DO_NOT_EXPORT' not in json.dumps(snapshot)
            release.set()
            await operation_task
            assert (await client.get('/api/runtime/status')).json()['activity']['active_requests'] == 0
    run(scenario())


@pytest.mark.parametrize('finish', ['failure', 'cancel'])
def test_failed_or_cancelled_request_decrements_in_finally(tmp_path, finish):
    async def scenario():
        owner, entered, release = service(tmp_path), asyncio.Event(), asyncio.Event()
        app = application(owner)
        @app.get('/api/operation')
        async def operation():
            entered.set()
            await release.wait()
            raise RuntimeError('synthetic route failure')
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            pending = asyncio.create_task(client.get('/api/operation'))
            await asyncio.wait_for(entered.wait(), 2)
            assert owner.tracker.snapshot()['active_requests'] == 1
            if finish == 'cancel':
                pending.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await pending
            else:
                release.set()
                with pytest.raises(RuntimeError, match='synthetic route'):
                    await pending
            assert (await client.get('/api/runtime/status')).json()['activity']['active_requests'] == 0
    run(scenario())


def test_asgi_stream_stays_active_until_cleanup_and_cancel(tmp_path):
    async def scenario():
        tracker, started, release = ActivityTracker(), asyncio.Event(), asyncio.Event()
        async def stream(scope, receive, send):
            await send({'type': 'http.response.start', 'status': 200, 'headers': []})
            await send({'type': 'http.response.body', 'body': b'fixture chunk', 'more_body': True})
            started.set()
            await release.wait()
            await send({'type': 'http.response.body', 'body': b'end', 'more_body': False})
        owner = service(tmp_path, tracker=tracker)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=RuntimeActivityMiddleware(stream, tracker=tracker)), base_url='http://test') as client:
            pending = asyncio.create_task(client.get('/api/stream'))
            await asyncio.wait_for(started.wait(), 2)
            assert (await owner.snapshot())['activity']['active_requests'] == 1
            pending.cancel()
            with pytest.raises(asyncio.CancelledError):
                await pending
            assert (await owner.snapshot())['activity']['active_requests'] == 0
    run(scenario())


@pytest.mark.parametrize('path', ['/api/runtime/status', '/api/runtime/status/', '/api/health', '/api/health/', '/health', '/assets/file'])
def test_poll_health_and_non_api_requests_do_not_count_as_activity(path):
    async def scenario():
        tracker, entered, release = ActivityTracker(), asyncio.Event(), asyncio.Event()
        async def waiting(scope, receive, send):
            entered.set()
            await release.wait()
        scope = {'type': 'http', 'path': path}
        task = asyncio.create_task(RuntimeActivityMiddleware(waiting, tracker=tracker)(scope, None, None))
        await entered.wait()
        assert tracker.snapshot()['active_requests'] == 0
        release.set()
        await task
    run(scenario())


def test_tracker_updates_are_thread_safe():
    tracker, entered, release = ActivityTracker(), threading.Barrier(9), threading.Event()
    def work():
        tracker.begin()
        entered.wait(2)
        assert release.wait(2)
        tracker.end()
    with ThreadPoolExecutor(max_workers=8) as pool:
        tasks = [pool.submit(work) for _ in range(8)]
        entered.wait(2)
        assert tracker.snapshot()['active_requests'] == 8
        release.set()
        for task in tasks:
            task.result(2)
    assert tracker.snapshot()['active_requests'] == 0


@pytest.fixture
def selection_files(tmp_path):
    paths = {name + '_path': tmp_path / (name + '.json') for name in ('selection', 'policy', 'registry', 'ollama')}
    return paths


def write(path, data):
    path.write_text(json.dumps(data), encoding='utf-8')


def test_provider_file_projection_is_pure_without_vault_network_or_processes(selection_files, monkeypatch):
    paths = selection_files
    write(paths['ollama_path'], {'auth_mode': 'local_cli', 'model_id': 'fixture:1', 'token': 'SYNTHETIC_SECRET'})
    before = files(paths['ollama_path'].parent)
    def forbidden(*args, **kwargs):
        raise AssertionError('No subprocess or provider probe permitted')
    monkeypatch.setattr(subprocess, 'Popen', forbidden)
    result = ProviderSelectionMetadata(**paths)()
    assert result == {'state': 'configured_unverified', 'provider_id': 'ollama-cloud', 'model_id': 'fixture:1'}
    assert files(paths['ollama_path'].parent) == before and 'SYNTHETIC_SECRET' not in json.dumps(result)


@pytest.mark.parametrize('verified', [False, True])
def test_registered_ready_is_historical_metadata_and_not_live_generation(selection_files, verified):
    paths = selection_files
    write(paths['selection_path'], {'provider_id': 'codex', 'model_id': 'fixture'})
    write(paths['registry_path'], {'providers': {'codex': {'auth_mode': 'codex_cli', 'model_id': 'fixture',
         'last_verified_model_id': 'fixture' if verified else None, 'base_url': 'https://PRIVATE.invalid', 'credential': 'SYNTHETIC_SECRET'}}})
    result = run(service(paths['registry_path'].parent, provider=ProviderSelectionMetadata(**paths)).snapshot())['provider']
    assert result['state'] == ('ready' if verified else 'configured_unverified')
    assert result['label'] == 'OpenAI Codex' and result['response_verified'] is False
    assert 'PRIVATE' not in json.dumps(result) and 'SYNTHETIC_SECRET' not in json.dumps(result)


def test_policy_selection_and_eligibility_are_read_without_mutation(selection_files):
    paths = selection_files
    write(paths['selection_path'], {'provider_id': 'codex', 'model_id': 'old'})
    write(paths['ollama_path'], {'auth_mode': 'api_key', 'model_id': 'registered'})
    policy = {'main_chat': 'ollama-cloud|selected', 'models': [{'provider_id': 'ollama-cloud', 'model_id': 'selected', 'chat': True}]}
    write(paths['policy_path'], policy)
    before = files(paths['policy_path'].parent)
    assert ProviderSelectionMetadata(**paths)()['model_id'] == 'selected'
    assert files(paths['policy_path'].parent) == before
    policy['models'][0]['orchestrator'] = False
    write(paths['policy_path'], policy)
    assert ProviderSelectionMetadata(**paths)()['state'] == 'not_configured'


def test_stale_or_missing_registration_does_not_claim_configured(selection_files):
    paths = selection_files
    assert ProviderSelectionMetadata(**paths)()['state'] == 'not_configured'
    write(paths['selection_path'], {'provider_id': 'ollama-cloud', 'model_id': 'selected'})
    write(paths['ollama_path'], {'auth_mode': 'api_key', 'model_id': 'other'})
    assert ProviderSelectionMetadata(**paths)()['state'] == 'not_configured'


def test_policy_model_override_does_not_inherit_another_registered_model_ready(selection_files):
    paths = selection_files
    write(paths['policy_path'], {'main_chat': 'codex|selected', 'models': [{'provider_id': 'codex', 'model_id': 'selected', 'orchestrator': True}]})
    write(paths['registry_path'], {'providers': {'codex': {'auth_mode': 'codex_cli', 'model_id': 'other', 'last_verified_model_id': 'selected'}}})
    assert ProviderSelectionMetadata(**paths)()['state'] == 'configured_unverified'


@pytest.mark.parametrize('bad', [b'{', b'[]', b'x' * (256 * 1024 + 1)], ids=['invalid-json', 'non-object', 'oversized'])
def test_unreadable_or_invalid_selection_metadata_isolated_and_never_repaired(selection_files, bad):
    paths = selection_files
    paths['selection_path'].write_bytes(bad)
    before = files(paths['selection_path'].parent)
    result = run(service(paths['selection_path'].parent, provider=ProviderSelectionMetadata(**paths)).snapshot())
    assert result['provider']['state'] == 'unavailable' and result['memory']['state'] == 'available'
    assert files(paths['selection_path'].parent) == before


def git(root, *arguments):
    completed = subprocess.run(['git', '--no-optional-locks', '-C', str(root), *arguments],
                               capture_output=True, timeout=10)
    assert completed.returncode == 0, completed.stderr.decode(errors='replace')
    return completed.stdout


def test_git_real_fixture_metadata_no_project_reads_writes_or_remote_contact(tmp_path):
    assert shutil.which('git') is not None
    git(tmp_path, 'init', '--initial-branch=fixture-main')
    remote = 'https://SYNTHETIC_TOKEN@example.invalid/synthetic/repository.git'
    git(tmp_path, 'remote', 'add', 'origin', remote)
    (tmp_path / 'private_corpus.py').write_bytes(b'Never enumerate or read through the status endpoint.')
    before = files(tmp_path)
    result = run(GitMetadata().status(tmp_path))
    assert result['state'] == 'repository' and result['repo_detected'] is True
    assert result['branch'] == 'fixture-main' and result['detached'] is False
    assert result['remote_configured'] is True and result['remote_verification'] == 'not_checked'
    assert remote not in json.dumps(result) and 'SYNTHETIC_TOKEN' not in json.dumps(result)
    assert str(tmp_path) not in json.dumps(result) and files(tmp_path) == before


def test_git_never_searches_parent_repository(tmp_path, monkeypatch):
    git(tmp_path, 'init')
    child = tmp_path / 'nested'
    child.mkdir()
    probe = GitMetadata()
    async def forbidden(*args, **kwargs):
        raise AssertionError('No .git at exact selected root, so no command is allowed')
    monkeypatch.setattr(probe, '_run', forbidden)
    assert run(probe.status(child))['state'] == 'not_repository'


def test_git_missing_selected_root_is_unknown_not_not_repository(tmp_path):
    result = run(GitMetadata().status(tmp_path / 'missing'))
    assert result['state'] == 'unavailable' and result['repo_detected'] is None


def test_git_failure_does_not_break_memory_provider_or_backend(tmp_path):
    (tmp_path / '.git').mkdir()
    result = run(service(tmp_path, git=GitMetadata(executable=str(tmp_path / 'missing-executable'))).snapshot())
    assert result['git']['error_code'] == 'git_metadata_unavailable'
    assert result['memory']['state'] == 'available' and result['provider']['state'] == 'configured_unverified'
    assert result['backend']['responding'] is True


def test_git_detached_without_remote_is_distinct_from_not_repository(tmp_path):
    git(tmp_path, 'init')
    git(tmp_path, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '--allow-empty', '-m', 'Synthetic fixture')
    git(tmp_path, 'checkout', '--detach')
    result = run(GitMetadata().status(tmp_path))
    assert result['repo_detected'] and result['detached'] is True and result['branch'] is None
    assert result['remote_configured'] is False


def test_git_cache_is_root_keyed_ttl_bounded_and_coalesces_polls(tmp_path, monkeypatch):
    clock, calls = [0.0], []
    probe = GitMetadata(ttl=5, clock=lambda: clock[0])
    async def observed(root):
        calls.append(root)
        await asyncio.sleep(0)
        return {'state': 'not_repository', 'remote_verification': 'not_checked'}
    monkeypatch.setattr(probe, '_probe', observed)
    async def scenario():
        results = await asyncio.gather(*(probe.status(tmp_path) for _ in range(8)))
        assert len(calls) == 1 and sum(result['cached'] for result in results) == 7
        await probe.status(tmp_path / 'changed-root')
        assert len(calls) == 2
        clock[0] = 6
        assert (await probe.status(tmp_path))['cached'] is False
        assert len(calls) == 3
    run(scenario())


@pytest.mark.parametrize('failure', ['timeout', 'output_limit'])
def test_git_subprocess_is_killed_on_timeout_or_oversized_output(tmp_path, monkeypatch, failure):
    class Output:
        async def read(self, size):
            if failure == 'timeout':
                await asyncio.Event().wait()
            return b'x' * size
    class Process:
        def __init__(self):
            self.returncode, self.stdout, self.killed = None, Output(), False
        def kill(self):
            self.killed, self.returncode = True, -9
        async def wait(self):
            if self.returncode is None:
                await asyncio.Event().wait()
            return self.returncode
    process, arguments = Process(), []
    async def create(*args, **kwargs):
        arguments.append((args, kwargs))
        return process
    monkeypatch.setattr(asyncio, 'create_subprocess_exec', create)
    probe = GitMetadata(timeout=0.01)
    with pytest.raises(TimeoutError if failure == 'timeout' else MetadataError):
        run(probe._run(tmp_path, ['rev-parse', '--show-toplevel']))
    assert process.killed
    assert arguments[0][0][1:3] == ('--no-optional-locks', '--no-pager')
    assert arguments[0][1]['stderr'] is asyncio.subprocess.DEVNULL
