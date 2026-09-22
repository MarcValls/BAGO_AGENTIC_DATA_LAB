"""Tests for the fully generated README contract."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from generate_dynamic_readme import (  # noqa: E402
    _read_json,
    collected_test_count,
    parse_roles,
    parse_skills,
    parse_state,
    phase_inventory,
    render_readme,
)


ROOT = Path(__file__).parent.parent


def test_readme_sources_are_real_and_state_is_parsed():
    manifest = _read_json(ROOT / "docs" / "readme_manifest.json")
    state = parse_state()
    phases = phase_inventory(manifest, state)

    assert state["current_phase"].startswith("L10")
    assert state["status_label"] == "VERIFIED"
    assert any(phase["id"] == "L10" for phase in phases)
    assert (ROOT / "docs" / "readme_manifest.json").is_file()


def test_readme_inventory_and_market_tables_are_discovered():
    assert collected_test_count() >= 100
    assert parse_roles()
    skills = parse_skills()
    assert any(row[0] == "RDF / SPARQL / Knowledge Graphs" for row in skills)


def test_rendered_readme_contains_dynamic_contract_and_l10_artifacts():
    manifest = _read_json(ROOT / "docs" / "readme_manifest.json")
    rendered = render_readme(
        manifest=manifest,
        state=parse_state(),
        passing_tests=113,
    )

    assert "README.md es un artefacto generado" in rendered
    assert chr(96) * 3 + "mermaid" in rendered
    assert chr(96) * 3 + "bash" in rendered
    assert "docs/readme_manifest.json" in rendered
    assert "src/metadata/ontology_engine.py" in rendered
    assert "tests/test_l10_ontology_engine.py" in rendered
    assert "python scripts/generate_dynamic_readme.py --check --skip-tests" in rendered
