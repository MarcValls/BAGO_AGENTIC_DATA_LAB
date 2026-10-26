"""Project-folder initialization with isolated roots and no implicit side effects."""
import hashlib
from contextlib import contextmanager
import json
import os
from pathlib import Path
import subprocess
import threading

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.project_folder_routes import create_project_folder_router
from src.project_folders import CONTEXT, MANIFEST, ProjectFolderError, ProjectFolders, binding_identity
from src.workspace_sdk import WorkspaceService, ServiceError


@pytest.fixture
def folders(tmp_path):
    active, chosen, admin = [tmp_path / name for name in ('active', 'chosen', 'administrative')]
    for root in (active, chosen, admin):
        root.mkdir()
    runtime = {'root': active, 'revision': 0, 'sets': 0}
    def select(root):
        runtime.update(root=Path(root), revision=runtime['revision'] + 1, sets=runtime['sets'] + 1)
        return Path(root)
    args = dict(state_directory=tmp_path / 'config' / 'project-folders', workspace_root=lambda: runtime['root'],
                set_workspace_root=select, pick_directory=lambda initial: chosen,
                binding_identity=lambda: {'root': str(runtime['root']), 'revision': runtime['revision']},
                legacy_parent=lambda: admin, binding_lock=threading.RLock())
    owner = ProjectFolders(**args)
    return owner, runtime, chosen, admin, args


def plan(owner, root, **kwargs):
    return owner.prepare(mode=kwargs.get('mode', 'existing'), path=str(root), name=kwargs.get('name', 'selected'),
                         title=kwargs.get('title', 'Selected project'), expected_workspace_root=str(owner.workspace_root()))


def apply(owner, proposal):
    return owner.apply(proposal['plan_id'], plan_sha256=proposal['plan_sha256'], confirmed=True)


def tree(root):
    return {item.relative_to(root).as_posix(): hashlib.sha256(item.read_bytes()).hexdigest()
            for item in root.rglob('*') if item.is_file()}


def test_prepare_browse_and_config_are_readonly(folders):
    owner, runtime, chosen, admin, _ = folders
    before = tree(chosen.parent)
    proposal = plan(owner, chosen)
    assert proposal['target_root'] == str(chosen)
    assert owner.browse() == {'path': str(chosen), 'cancelled': False}
    assert owner.config()['workspace_root'] == str(runtime['root'])
    assert tree(chosen.parent) == before and not owner.state.exists() and runtime['sets'] == 0


def test_exact_existing_root_initializes_minimums_and_replays_without_effect(folders):
    owner, runtime, chosen, admin, args = folders
    user_file = chosen / 'keep.txt'
    user_file.write_bytes(b'unchanged user bytes\r\n')
    result = apply(owner, plan(owner, chosen))
    assert result['workspace_root'] == str(chosen) == str(runtime['root'])
    assert result['workspace']['root'] == str(chosen)
    assert result['receipt']['status'] == 'APPLIED'
    assert set(result['receipt']['created_files']) == {*CONTEXT, MANIFEST}
    assert user_file.read_bytes() == b'unchanged user bytes\r\n'
    assert not list(admin.iterdir())
    before, sets = tree(chosen.parent), runtime['sets']
    replay = ProjectFolders(**args).apply(result['receipt']['plan_id'], plan_sha256=result['receipt']['plan_sha256'], confirmed=True)
    assert replay['receipt'] == result['receipt']
    assert tree(chosen.parent) == before and runtime['sets'] == sets


def test_child_uses_explicit_parent_and_is_registered_for_sdk_actions(folders):
    owner, runtime, chosen, admin, _ = folders
    result = apply(owner, plan(owner, chosen, mode='create_child', name='child'))
    assert result['workspace']['root'] == str(chosen / 'child')
    assert owner.workspaces()['workspaces'][0]['id'] == result['workspace']['id']
    status, payload = owner.action(result['workspace']['id'], {'operation': 'list_files'})
    assert status == 200
    assert not list(admin.iterdir())


def test_active_project_exposes_registered_identity_for_conversation_scope(folders):
    owner, runtime, chosen, _, _ = folders
    result = apply(owner, plan(owner, chosen, title='Project chat scope'))

    active = owner.active_project()

    assert active == {
        'project_id': result['workspace']['id'],
        'name': result['workspace']['name'],
        'title': 'Project chat scope',
        'root': str(chosen.resolve()),
        'scope': 'project',
    }


def test_existing_sdk_identity_preserves_bytes_and_canonical_name(folders):
    owner, runtime, chosen, _, _ = folders
    first = apply(owner, plan(owner, chosen))
    before = tree(chosen)
    proposal = plan(owner, chosen, name='different', title='Different')
    assert (proposal['name'], proposal['title']) == (first['workspace']['name'], first['workspace']['title'])
    second = apply(owner, proposal)
    assert second['receipt']['created_files'] == []
    assert tree(chosen) == before


@pytest.mark.parametrize('bad_confirm', [False, None, 1, 'true'])
def test_confirmation_is_exact_and_no_state_is_created(folders, bad_confirm):
    owner, runtime, chosen, _, _ = folders
    proposal = plan(owner, chosen)
    with pytest.raises(ProjectFolderError, match='Confirma'):
        owner.apply(proposal['plan_id'], plan_sha256=proposal['plan_sha256'], confirmed=bad_confirm)
    assert not owner.state.exists() and list(chosen.iterdir()) == [] and runtime['sets'] == 0


@pytest.mark.parametrize('digest', ['0' * 64, 'x' * 64, '', None])
def test_wrong_hash_never_creates_state(folders, digest):
    owner, runtime, chosen, _, _ = folders
    proposal = plan(owner, chosen)
    with pytest.raises(ProjectFolderError):
        owner.apply(proposal['plan_id'], plan_sha256=digest, confirmed=True)
    assert not owner.state.exists() and list(chosen.iterdir()) == [] and runtime['sets'] == 0


@pytest.mark.parametrize('changed', ['context', 'directory', 'binding', 'aba', 'expiry', 'child_exists'])
def test_stale_plan_rejected_before_initialization(folders, changed):
    owner, runtime, chosen, _, _ = folders
    proposal = plan(owner, chosen, mode='create_child' if changed == 'child_exists' else 'existing', name='child')
    if changed == 'context':
        (chosen / '.bago/context').mkdir(parents=True)
        (chosen / CONTEXT[0]).write_text('external edit', encoding='utf-8')
    elif changed == 'directory':
        chosen.rename(chosen.with_name('original-chosen'))
        chosen.mkdir()
    elif changed == 'binding':
        runtime.update(root=chosen, revision=1)
    elif changed == 'aba':
        runtime['revision'] += 2
    elif changed == 'expiry':
        owner.clock = lambda: 10 ** 12
    else:
        (chosen / 'child').mkdir()
    before = tree(chosen.parent)
    with pytest.raises(ProjectFolderError):
        apply(owner, proposal)
    assert tree(chosen.parent) == before and not owner.state.exists() and runtime['sets'] == 0


def test_plan_output_cannot_mutate_server_snapshot(folders):
    owner, _, chosen, admin, _ = folders
    proposal = plan(owner, chosen)
    original_id, digest = proposal['plan_id'], proposal['plan_sha256']
    proposal.update(target_root=str(admin), name='tampered')
    proposal['files'][0]['action'] = 'preserve'
    result = owner.apply(original_id, plan_sha256=digest, confirmed=True)
    assert result['workspace_root'] == str(chosen) and not list(admin.iterdir())
    assert set(result['receipt']['created_files']) == {*CONTEXT, MANIFEST}


@pytest.mark.parametrize('relative', ['.bago', '.bago/context', CONTEXT[0], '.workspace-service'])
def test_foreign_types_or_metadata_are_preserved_and_rejected(folders, relative):
    owner, _, chosen, _, _ = folders
    path = chosen / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    if relative == '.workspace-service':
        path.mkdir()
        (path / 'foreign').write_bytes(b'original')
    elif relative == CONTEXT[0]:
        path.mkdir()
    else:
        path.write_bytes(b'original')
    before = tree(chosen)
    with pytest.raises(ProjectFolderError):
        plan(owner, chosen)
    assert tree(chosen) == before and not owner.state.exists()


def test_existing_context_utf8_bytes_are_preserved(folders):
    owner, _, chosen, _, _ = folders
    (chosen / '.bago/context').mkdir(parents=True)
    preserved = b'# Existing context\r\n\r\nOriginal user decisions.\r\n'
    (chosen / CONTEXT[0]).write_bytes(preserved)
    result = apply(owner, plan(owner, chosen))
    assert CONTEXT[0] not in result['receipt']['created_files']
    assert (chosen / CONTEXT[0]).read_bytes() == preserved


def directory_link(link, target):
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        if os.name != 'nt':
            raise
        # A Windows junction exercises the real reparse-point path without
        # administrator symlink privilege; both paths are isolated fixtures.
        def quote(path):
            return "'" + str(path).replace("'", "''") + "'"
        completed = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command',
            'New-Item -ItemType Junction -Path ' + quote(link) + ' -Value ' + quote(target) + ' -ErrorAction Stop | Out-Null'],
            capture_output=True, timeout=20)
        assert completed.returncode == 0, completed.stderr.decode(errors='replace')


def test_symlink_in_target_ancestor_cannot_be_followed(folders):
    owner, _, chosen, admin, _ = folders
    linked = chosen.parent / 'linked'
    directory_link(linked, chosen)
    with pytest.raises(ProjectFolderError, match='enlaces'):
        plan(owner, linked)
    assert list(chosen.iterdir()) == [] and list(admin.iterdir()) == []


def test_state_symlink_is_rejected_before_target_effects(folders):
    owner, runtime, chosen, admin, _ = folders
    proposal = plan(owner, chosen)
    owner.state.parent.mkdir()
    directory_link(owner.state, admin)
    with pytest.raises(ProjectFolderError):
        apply(owner, proposal)
    assert list(chosen.iterdir()) == [] and list(admin.iterdir()) == [] and runtime['sets'] == 0


def test_partial_file_failure_has_exact_receipt_and_replay_no_effects(folders, monkeypatch):
    owner, runtime, chosen, _, args = folders
    proposal = plan(owner, chosen)
    real_create = owner._create_file
    def fail_second(target, relative, raw):
        if relative == CONTEXT[1]:
            raise OSError('synthetic failure only')
        real_create(target, relative, raw)
    monkeypatch.setattr(owner, '_create_file', fail_second)
    with pytest.raises(ProjectFolderError) as failure:
        apply(owner, proposal)
    receipt = failure.value.receipt
    assert receipt['status'] == 'PARTIAL_FAILED'
    assert receipt['created_files'] == [CONTEXT[0]] and receipt['binding_applied'] is False
    assert set(receipt['created_directories']) == {'.bago', '.bago/context', '.bago/state'}
    assert runtime['sets'] == 0 and (chosen / CONTEXT[0]).exists() and not (chosen / CONTEXT[1]).exists()
    before = tree(chosen.parent)
    with pytest.raises(ProjectFolderError) as replay:
        apply(ProjectFolders(**args), proposal)
    assert replay.value.receipt == receipt and tree(chosen.parent) == before and runtime['sets'] == 0


@pytest.mark.parametrize('failure_kind', ['registry', 'binding_before', 'binding_after', 'receipt_after_binding'])
def test_partial_registry_binding_and_receipt_failures_never_claim_success(folders, monkeypatch, failure_kind):
    owner, runtime, chosen, _, args = folders
    proposal = plan(owner, chosen)
    real_select, real_save = owner.set_workspace_root, owner._save_receipt
    def fail(*args):
        raise RuntimeError('synthetic failure without leaked raw error')
    if failure_kind == 'registry':
        monkeypatch.setattr(owner, '_save_registry', fail)
    elif failure_kind.startswith('binding'):
        def select(root):
            if failure_kind == 'binding_after':
                real_select(root)
            fail()
        monkeypatch.setattr(owner, 'set_workspace_root', select)
    else:
        def save(receipt):
            if receipt['binding_applied'] is True:
                raise OSError('receipt persistence failed')
            real_save(receipt)
        monkeypatch.setattr(owner, '_save_receipt', save)
    with pytest.raises(ProjectFolderError) as failure:
        apply(owner, proposal)
    receipt = failure.value.receipt
    assert receipt['status'] in {'PARTIAL_FAILED', 'INCONCLUSIVE'}
    assert receipt['created_files'] == [*CONTEXT, MANIFEST]
    assert receipt['registry_applied'] is (failure_kind != 'registry')
    assert receipt['binding_applied'] is (False if failure_kind == 'registry' else True if failure_kind == 'receipt_after_binding' else None)
    assert receipt['actual_workspace_root'] == str(runtime['root'])
    assert (runtime['root'] == chosen) is (failure_kind in {'binding_after', 'receipt_after_binding'})
    before, sets = tree(chosen.parent), runtime['sets']
    with pytest.raises(ProjectFolderError):
        apply(ProjectFolders(**args), proposal)
    assert tree(chosen.parent) == before and runtime['sets'] == sets


def test_binding_identity_detects_same_root_atomic_config_replacement(tmp_path):
    configuration = tmp_path / 'workspace.json'
    configuration.write_text('{"workspace_root":"A"}', encoding='utf-8')
    first = binding_identity(configuration, tmp_path)
    replacement = tmp_path / 'replacement'
    replacement.write_bytes(configuration.read_bytes())
    replacement.replace(configuration)
    assert first != binding_identity(configuration, tmp_path)


def test_legacy_projects_and_exact_registered_root_are_aggregated(folders):
    owner, _, chosen, admin, args = folders
    legacy = WorkspaceService(admin).create('legacy', 'Legacy', True)
    current = apply(owner, plan(owner, chosen))['workspace']
    fresh = ProjectFolders(**args)
    assert {item['id'] for item in fresh.workspaces()['workspaces']} == {legacy['id'], current['id']}
    for identity in (legacy['id'], current['id']):
        assert fresh.action(identity, {'operation': 'list_files'})[0] == 200
    with pytest.raises((ServiceError, ProjectFolderError)):
        fresh.action(current['id'], {'operation': 'list_files', 'root': str(admin)})
    with pytest.raises((ServiceError, ProjectFolderError)):
        fresh.action('workspace_' + 'a' * 32, {'operation': 'list_files', 'root': str(chosen)})


def test_routes_require_same_origin_strict_json_and_confirmation(folders):
    owner, runtime, chosen, _, args = folders
    app = FastAPI()
    app.include_router(create_project_folder_router(**args))
    base = '/api/project-folders/v1'
    with TestClient(app) as client:
        for origin in ('https://untrusted.invalid', 'http://['):
            assert client.get(base + '/config', headers={'Origin': origin}).status_code == 403
        assert client.get(base + '/config').json() == owner.config()
        assert client.post(base + '/browse', json={}).json()['path'] == str(chosen)
        for payload in ([], None, 'text'):
            assert client.post(base + '/plans', json=payload).status_code == 400
        assert client.post(base + '/plans', content='{}', headers={'Content-Type': 'text/plain'}).status_code == 400
        assert client.post(base + '/plans', json={'extra': 'untrusted'}).status_code == 422
        assert client.post(base + '/browse', json={'path': str(chosen)}).status_code == 422
        draft = dict(mode='existing', path=str(chosen), name='selected', title='Selected project', expected_workspace_root=str(runtime['root']))
        response = client.post(base + '/plans', json=draft)
        assert response.status_code == 200
        proposal = response.json()
        assert not owner.state.exists() and list(chosen.iterdir()) == [] and runtime['sets'] == 0
        route = base + '/plans/' + proposal['plan_id'] + '/apply'
        assert client.post(route, json={'plan_sha256': proposal['plan_sha256'], 'confirmed': False}).status_code == 422
        result = client.post(route, json={'plan_sha256': proposal['plan_sha256'], 'confirmed': True})
        assert result.status_code == 200 and result.json()['workspace_root'] == str(chosen)
        assert result.headers['Cache-Control'] == 'no-store'
        identity = result.json()['workspace']['id']
        assert client.get(base + '/workspaces').json()['workspaces'][0]['id'] == identity
        assert client.post(base + '/workspaces/' + identity + '/actions', json={'operation': 'list_files'}).status_code == 200


@pytest.mark.parametrize('race', ['binding', 'context', 'expiry'])
def test_plan_is_revalidated_under_persistent_lock_before_any_target_effect(folders, monkeypatch, race):
    owner, runtime, chosen, _, _ = folders
    proposal = plan(owner, chosen)
    real_lock = owner._state_lock
    @contextmanager
    def intervening_lock():
        with real_lock():
            if race == 'binding':
                runtime['revision'] += 2
            elif race == 'context':
                (chosen / '.bago/context').mkdir(parents=True)
                (chosen / CONTEXT[0]).write_bytes(b'external edit only')
            else:
                owner.clock = lambda: 10 ** 12
            yield
    monkeypatch.setattr(owner, '_state_lock', intervening_lock)
    with pytest.raises(ProjectFolderError):
        apply(owner, proposal)
    assert not owner._receipt_path(proposal['plan_id']).exists()
    assert not (chosen / MANIFEST).exists() and runtime['sets'] == 0
    assert tree(chosen) == ({CONTEXT[0]: hashlib.sha256(b'external edit only').hexdigest()} if race == 'context' else {})


def test_workspace_selection_lock_covers_validation_writes_registry_and_binding(folders, monkeypatch):
    owner, runtime, chosen, admin, args = folders
    proposal = plan(owner, chosen)
    entered, release, attempted, selected = [threading.Event() for _ in range(4)]
    result, failures = [], []
    real_create = owner._create_file
    def blocked_create(*arguments):
        entered.set()
        assert release.wait(5)
        return real_create(*arguments)
    monkeypatch.setattr(owner, '_create_file', blocked_create)
    def initialize():
        try:
            result.append(apply(owner, proposal))
        except Exception as failure:
            failures.append(failure)
    def concurrent_select():
        attempted.set()
        with args['binding_lock']:
            owner.set_workspace_root(admin)
            selected.set()
    first = threading.Thread(target=initialize)
    second = threading.Thread(target=concurrent_select)
    first.start()
    try:
        assert entered.wait(5)
        second.start()
        assert attempted.wait(5)
        assert not selected.wait(0.05)
    finally:
        release.set()
        first.join(5)
        if second.ident is not None:
            second.join(5)
    assert not failures and len(result) == 1
    assert result[0]['receipt']['status'] == 'APPLIED' and selected.is_set()
    assert runtime['sets'] == 2 and runtime['root'] == admin


def test_existing_lock_hardlink_is_rejected_without_modifying_foreign_file(folders):
    owner, runtime, chosen, admin, _ = folders
    proposal = plan(owner, chosen)
    owner.state.mkdir(parents=True)
    foreign = admin / 'foreign-empty'
    foreign.write_bytes(b'')
    os.link(foreign, owner.state / 'lock')
    with pytest.raises(ProjectFolderError, match='enlaces'):
        apply(owner, proposal)
    assert foreign.read_bytes() == b'' and not list(chosen.iterdir()) and runtime['sets'] == 0


@pytest.mark.parametrize('change', ['missing_appears', 'preserved_disappears', 'preserved_bytes_change'])
def test_plan_file_actions_are_exact_snapshot_not_conditional_apply(folders, change):
    owner, runtime, chosen, _, _ = folders
    (chosen / '.bago/context').mkdir(parents=True)
    path = chosen / CONTEXT[0]
    if change != 'missing_appears':
        path.write_bytes(b'original context')
    proposal = plan(owner, chosen)
    action = next(item['action'] for item in proposal['files'] if item['path'] == CONTEXT[0])
    assert action == ('create' if change == 'missing_appears' else 'preserve')
    if change == 'preserved_disappears':
        path.unlink()
    else:
        path.write_bytes(b'external change')
    before = tree(chosen)
    with pytest.raises(ProjectFolderError) as failure:
        apply(owner, proposal)
    assert failure.value.status == 409 and failure.value.code == 'files_changed'
    assert tree(chosen) == before and not owner.state.exists() and runtime['sets'] == 0


@pytest.mark.parametrize('change', ['utf16', 'invalid_title', 'empty_name', 'wrong_root'])
def test_invalid_existing_manifest_is_rejected_during_readonly_planning(folders, change):
    owner, runtime, chosen, _, _ = folders
    internal = chosen / '.workspace-service'
    internal.mkdir()
    metadata = {'id': 'workspace_' + 'e' * 32, 'root': str(chosen), 'name': 'valid',
                'title': 'Valid', 'revision': 'revision', 'created_at': '2026-10-25T00:00:00+00:00'}
    if change == 'invalid_title':
        metadata['title'] = 'not\na single line'
    elif change == 'empty_name':
        metadata['name'] = ''
    elif change == 'wrong_root':
        metadata['root'] = str(chosen.parent)
    (chosen / MANIFEST).write_bytes(json.dumps(metadata).encode('utf-16' if change == 'utf16' else 'utf-8'))
    before = tree(chosen)
    with pytest.raises(ProjectFolderError) as failure:
        plan(owner, chosen)
    assert failure.value.code == 'foreign_service_state'
    assert tree(chosen) == before and not owner.state.exists() and runtime['sets'] == 0


def test_registry_entry_count_is_bounded_before_replacing_existing_file(folders):
    owner, _, chosen, _, _ = folders
    apply(owner, plan(owner, chosen))
    registry = owner.state / 'registry.json'
    before = registry.read_bytes()
    row = next(iter(owner._registry().values()))
    oversized = {'workspace_' + f'{number:032x}': row for number in range(1001)}
    with pytest.raises(ProjectFolderError) as failure:
        owner._save_registry(oversized)
    assert failure.value.code == 'registry_capacity'
    assert registry.read_bytes() == before and len(owner.workspaces()['workspaces']) == 1


def test_oversized_registry_fails_partial_without_breaking_previously_registered_roots(folders, monkeypatch):
    from src import project_folders
    owner, runtime, chosen, _, _ = folders
    monkeypatch.setattr(project_folders, 'MAX', 5000)
    approved = []
    for number in range(20):
        target = chosen / f'project-{number}'
        target.mkdir()
        proposal = plan(owner, target)
        path = owner.state / 'registry.json'
        previous = path.read_bytes() if path.exists() else None
        selected, sets = runtime['root'], runtime['sets']
        try:
            result = apply(owner, proposal)
            approved.append(result['workspace']['id'])
        except ProjectFolderError as failure:
            receipt = failure.receipt
            assert receipt['status'] == 'PARTIAL_FAILED' and receipt['error_code'] == 'registry_capacity'
            assert receipt['registry_applied'] is False and receipt['binding_applied'] is False
            assert runtime['root'] == selected and runtime['sets'] == sets
            assert previous is not None and path.read_bytes() == previous and len(previous) <= 5000
            assert {item['id'] for item in owner.workspaces()['workspaces']} == set(approved)
            before = tree(chosen.parent)
            with pytest.raises(ProjectFolderError):
                apply(owner, proposal)
            assert tree(chosen.parent) == before and runtime['sets'] == sets
            break
    else:
        pytest.fail('Fixture did not reach the deliberately reduced registry size limit')
