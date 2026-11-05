from pathlib import Path
from types import SimpleNamespace
import stat

import pytest

from scripts.runtime_fingerprint import _is_link, fingerprint


@pytest.fixture
def project(tmp_path):
    for directory in ('src', 'tools', 'frontend/src', 'frontend/dist'):
        (tmp_path / directory).mkdir(parents=True)
    for name in ('frontend/index.html', 'frontend/package.json', 'frontend/package-lock.json',
                 'src/server.py', 'tools/tool.py', 'frontend/src/app.ts', 'frontend/dist/index.html'):
        (tmp_path / name).write_text(name, encoding='utf-8')
    return tmp_path


@pytest.mark.parametrize('kind,name', [('backend', 'src/server.py'), ('backend', 'tools/tool.py'),
                                      ('frontend', 'frontend/src/app.ts'), ('frontend', 'frontend/package-lock.json'),
                                      ('dist', 'frontend/dist/index.html')])
def test_edit_is_detected(project, kind, name):
    before = fingerprint(project, kind)
    (project / name).write_text('changed', encoding='utf-8')
    assert fingerprint(project, kind) != before


@pytest.mark.parametrize('kind,name', [('backend', 'src/new.py'), ('frontend', 'frontend/src/new.ts'),
                                      ('dist', 'frontend/dist/new.js')])
def test_add_and_delete_are_detected(project, kind, name):
    before = fingerprint(project, kind)
    path = project / name
    path.write_text('new', encoding='utf-8')
    assert fingerprint(project, kind) != before
    path.unlink()
    assert fingerprint(project, kind) == before


def test_cache_changes_do_not_change_backend_fingerprint(project):
    before = fingerprint(project, 'backend')
    cache = project / 'src/__pycache__'
    cache.mkdir()
    (cache / 'server.pyc').write_bytes(b'cache')
    assert fingerprint(project, 'backend') == before


def test_missing_required_input_fails_closed(project):
    (project / 'frontend/package-lock.json').unlink()
    with pytest.raises(ValueError, match='required input missing'):
        fingerprint(project, 'frontend')


def test_empty_directory_addition_is_detected(project):
    before = fingerprint(project, 'backend')
    (project / 'src/empty').mkdir()
    assert fingerprint(project, 'backend') != before


def test_team_kit_source_change_is_detected(project):
    kit = project / '.bago/team/kit/scripts'
    kit.mkdir(parents=True)
    (kit / 'teamctl.py').write_text('before', encoding='utf-8')
    before = fingerprint(project, 'backend')
    (kit / 'teamctl.py').write_text('after', encoding='utf-8')
    assert fingerprint(project, 'backend') != before


def test_vite_env_file_and_process_setting_are_detected(project, monkeypatch):
    before = fingerprint(project, 'frontend')
    (project / 'frontend/.env.production.local').write_text('VITE_TEST=value', encoding='utf-8')
    with_file = fingerprint(project, 'frontend')
    assert with_file != before
    monkeypatch.setenv('VITE_TEST', 'other')
    assert fingerprint(project, 'frontend') != with_file


def test_walk_permission_error_is_not_silently_ignored(project, monkeypatch):
    def broken_walk(path, *, followlinks, onerror):
        onerror(PermissionError('simulated unreadable directory'))
        return iter(())
    monkeypatch.setattr('scripts.runtime_fingerprint.os.walk', broken_walk)
    with pytest.raises(PermissionError, match='simulated unreadable'):
        fingerprint(project, 'backend')


def test_windows_reparse_attribute_is_rejected():
    assert _is_link(SimpleNamespace(st_mode=stat.S_IFREG, st_file_attributes=0x400))
    assert not _is_link(SimpleNamespace(st_mode=stat.S_IFREG, st_file_attributes=0))


def test_linked_file_is_rejected(project):
    link = project / 'src/link.py'
    try:
        link.symlink_to(project / 'src/server.py')
    except OSError:
        pytest.skip('creating symlinks is unavailable')
    with pytest.raises(ValueError, match='unsafe input'):
        fingerprint(project, 'backend')
