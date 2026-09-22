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
    _test_function_count,
)


ROOT = Path(__file__).parent.parent


def test_readme_sources_are_real_and_state_is_parsed():
    manifest = _read_json(ROOT / "docs" / "readme_manifest.json")
    state = parse_state()
    phases = phase_inventory(manifest, state)

    assert state["current_phase"].startswith("L10")
    assert state["status_label"] == "VERIFIED"
    l10 = next(phase for phase in phases if phase["id"] == "L10")
    assert l10["status"] == "VERIFIED (local)"
    assert any(phase["id"] == "L10" for phase in phases)
    assert (ROOT / "docs" / "readme_manifest.json").is_file()
    l1 = next(phase for phase in phases if phase["id"] == "L1")
    l3 = next(phase for phase in phases if phase["id"] == "L3")
    assert sum(
        _test_function_count(ROOT / match)
        for check in l1["checks"]
        if check["kind"] == "tests"
        for match in check["matches"]
    ) == 7
    assert sum(
        _test_function_count(ROOT / match)
        for check in l3["checks"]
        if check["kind"] == "tests"
        for match in check["matches"]
    ) == 25


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
        passing_tests=collected_test_count(),
    )

    assert "README.md es un artefacto generado" in rendered
    assert chr(96) * 3 + "mermaid" in rendered
    assert chr(96) * 3 + "bash" in rendered
    assert "docs/readme_manifest.json" in rendered
    assert "src/metadata/ontology_engine.py" in rendered
    assert "tests/test_l10_ontology_engine.py" in rendered
    assert "python scripts/generate_dynamic_readme.py --check --skip-tests" in rendered
    assert "Estado actualizado" in rendered
    assert "| Fase actual | **L10 · Governed Ontology Engine** · VERIFIED (local) |" in rendered
    assert "| L10 | VERIFIED (local) |" in rendered
    assert "STATE.md" in rendered
    assert ".github/agents/bago-sync-agent.agent.md" in rendered
    assert "scripts/bago_sync_agent.py" in rendered
