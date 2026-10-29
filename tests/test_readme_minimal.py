"""Minimal landing content, trust boundaries, and v2 compatibility."""
import copy
import json
from pathlib import Path
import re
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import generate_dynamic_readme as generator


def configuration():
    return json.loads(generator.SVG_LANDING_MANIFEST_PATH.read_text(encoding='utf-8'))


def use_manifest(data, tmp_path, monkeypatch):
    path = tmp_path / 'landing.json'
    path.write_text(json.dumps(data), encoding='utf-8')
    monkeypatch.setattr(generator, 'SVG_LANDING_MANIFEST_PATH', path)


def test_minimal_content_and_deterministic_output(monkeypatch):
    first = generator.render_svg_landing()
    monkeypatch.setenv('TZ', 'Pacific/Auckland')
    assert first == generator.render_svg_landing()
    assert first.endswith('\n') and not first.endswith('\n\n')
    for heading in ('Qué ofrece', 'Del chat a una operación verificable', 'La aplicación', 'Probar ADL', 'Documentación y evidencia'):
        assert f'## {heading}' in first
    assert first.count('![') == 1
    assert '2026-10-22' in first and 'no acredita por sí sola' in first
    assert 'fixtures; no valida servicios cloud en producción' in first
    assert len(configuration()['minimal']['areas']) == 4
    header = first.split('## Qué ofrece')[0]
    for link in configuration()['navigation'][:4]:
        assert f"[{link['label']}]({link['target']})" in header
    for target in re.findall(r'\]\(([^)]+)\)', first):
        path, _, fragment = target.partition('#')
        assert not fragment  # Every landing link is a direct file/directory target.
        assert (ROOT / path).resolve().is_relative_to(ROOT)
        assert (ROOT / path).exists(), target


def test_legacy_v2_manifest_still_renders_with_all_validations(tmp_path, monkeypatch):
    data = configuration()
    data['schema'] = 'bago.readme.svg.landing.v2'
    data.pop('minimal')
    use_manifest(data, tmp_path, monkeypatch)
    text = generator.render_svg_landing()
    assert text.count('<details>') == 8
    assert text.count('<img ') == len(data['panels'])


@pytest.mark.parametrize('mutation', [
    'schema', 'capture_escape', 'capture_external', 'capture_missing',
    'capture_alt', 'capture_date', 'capture_guide', 'area_target',
    'area_label', 'area_description', 'intro', 'summary', 'areas', 'entry_links',
])
def test_minimal_manifest_rejects_invalid_content(tmp_path, monkeypatch, mutation):
    data = copy.deepcopy(configuration())
    minimal = data['minimal']
    capture = minimal['capture']
    if mutation == 'schema':
        data['schema'] = 'unknown'
    elif mutation.startswith('capture_'):
        key = mutation.removeprefix('capture_')
        field, value = {
            'escape': ('asset', 'docs/assets/../../secret.png'),
            'external': ('asset', 'https://example.org/image.png'),
            'missing': ('asset', 'docs/assets/missing.png'),
            'alt': ('alt', '<details>hidden'),
            'date': ('date', 'yesterday'),
            'guide': ('guide', '../README.md'),
        }[key]
        capture[field] = value
    elif mutation.startswith('area_'):
        field = mutation.removeprefix('area_')
        minimal['areas'][0][field] = 'https://example.org' if field == 'target' else '[injected](https://example.org)'
    elif mutation == 'areas':
        minimal['areas'] = []
    elif mutation == 'entry_links':
        data['navigation'][0]['category'] = 'Other'
    elif mutation == 'summary':
        data['summary'] = '<details>hidden'
    else:
        minimal['intro'] = 'line one\nline two'
    use_manifest(data, tmp_path, monkeypatch)
    with pytest.raises((ValueError, FileNotFoundError)):
        generator.render_svg_landing()


def test_markdown_targets_reject_absolute_and_symlink_escape(tmp_path, monkeypatch):
    outside = tmp_path / 'outside.md'
    outside.write_text('outside', encoding='utf-8')
    repo = tmp_path / 'repo'
    repo.mkdir()
    (repo / 'link.md').symlink_to(outside)
    monkeypatch.setattr(generator, 'REPO_ROOT', repo)
    for target in (str(outside), 'link.md'):
        with pytest.raises(ValueError):
            generator._validate_local_markdown_target(target, 'escape')
