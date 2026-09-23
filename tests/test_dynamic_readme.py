"""Tests for the fully generated README contract."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from generate_dynamic_readme import (  # noqa: E402
    _read_json,
    collected_test_count,
    parse_roles,
    parse_skills,
    parse_soft_skills,
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

    assert state["current_phase"].startswith("L15")
    assert state["status_label"] == "VERIFIED"
    l10 = next(phase for phase in phases if phase["id"] == "L10")
    assert l10["status"] == "VERIFIED (local)"
    l11 = next(phase for phase in phases if phase["id"] == "L11")
    assert l11["status"] == "VERIFIED (local)"
    l12 = next(phase for phase in phases if phase["id"] == "L12")
    assert l12["status"] == "VERIFIED (local)"
    l13 = next(phase for phase in phases if phase["id"] == "L13")
    assert l13["status"] == "VERIFIED (local)"
    l14 = next(phase for phase in phases if phase["id"] == "L14")
    assert l14["status"] == "VERIFIED (local)"
    l15 = next(phase for phase in phases if phase["id"] == "L15")
    assert l15["status"] == "VERIFIED (local live)"
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
    soft_skills = parse_soft_skills()
    assert any(row[0] == "Arquitectura de sistemas" for row in soft_skills)


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
    assert "src/sandbox/backend.py" in rendered
    assert "tests/test_sandbox.py" in rendered
    assert "evidence/sandbox_local_restricted.md" in rendered
    assert "## Infraestructura reproducible" in rendered
    assert "infra/openmetadata/docker-compose.yml" in rendered
    assert "scripts/run_l8_openmetadata_live_validation.py" in rendered
    assert "scripts/run_sandbox_local_validation.py" in rendered
    assert "src/observability/local_trace.py" in rendered
    assert "src/evaluation/local_evals.py" in rendered
    assert "tests/test_l12_observability.py" in rendered
    assert "evidence/l12_observability_evals.md" in rendered
    assert "docs/observability_evals.md" in rendered
    assert "scripts/run_l12_observability_evidence.py" in rendered
    assert "scripts/run_public_e2e_demo.py" in rendered
    assert "tests/test_public_e2e_demo.py" in rendered
    assert "evidence/public_e2e_demo.md" in rendered
    assert "docs/public_e2e_demo.md" in rendered
    assert "requirements.txt" in rendered
    assert ".github/workflows/ci.yml" in rendered
    assert "python scripts/run_public_e2e_demo.py --check" in rendered
    assert "src/retrieval/sqlite_vector_store.py" in rendered
    assert "tests/test_sqlite_vector_store.py" in rendered
    assert "evidence/l14_vector_store.md" in rendered
    assert "docs/local_vector_store.md" in rendered
    assert "scripts/run_l14_vector_store_validation.py --check" in rendered
    assert "src/observability/otel_bridge.py" in rendered
    assert "tests/test_l15_otel_bridge.py" in rendered
    assert "evidence/l15_otel_jaeger_live.md" in rendered
    assert "docs/otel_jaeger.md" in rendered
    assert "infra/observability/docker-compose.yml" in rendered
    assert "scripts/run_l15_otel_live_validation.py --check" in rendered
    assert "python scripts/generate_dynamic_readme.py --check --skip-tests" in rendered
    assert "Estado actualizado" in rendered
    assert "| Fase actual | **L15 · OpenTelemetry + Jaeger Local Live** · VERIFIED (local live) |" in rendered
    assert "| L10 | VERIFIED (local) | BAGO / portfolio | Governed Ontology Engine | 4 | 2 |" in rendered
    assert "| L11 | VERIFIED (local) | BAGO / secure execution | Governed Sandbox Layer | 14 | 3 |" in rendered
    assert "| L12 | VERIFIED (local) | BAGO / portfolio | Local Observability & Evals | 5 | 3 |" in rendered
    assert "| L13 | VERIFIED (local) | BAGO / portfolio | Public E2E Demo & CI | 3 | 2 |" in rendered
    assert "| L14 | VERIFIED (local) | BAGO / portfolio | Governed Local Vector Store | 4 | 2 |" in rendered
    assert "| L15 | VERIFIED (local live) | BAGO / portfolio | OpenTelemetry + Jaeger Local Live | 3 | 2 |" in rendered
    assert "| Skill | Demanda | Nivel actual | Nivel objetivo | Primera evidencia | Entrevista |" in rendered
    assert "| RAG | Muy Alta | 🟡 Basic | 🎯 Advanced | L4 governed RAG | L4 completado |" in rendered
    assert "## Skills estratégicas" in rendered
    assert "| Arquitectura de sistemas | ✅ Fuerte | ✅ Mantener | AGENTS.md, CANON_BAGO |" in rendered
    assert "STATE.md" in rendered
    assert ".github/agents/bago-sync-agent.agent.md" in rendered
    assert "scripts/bago_sync_agent.py" in rendered
    assert "## Catálogo de agentes" in rendered
    assert "| `07-sincronizacion` |" in rendered


def test_mermaid_labels_are_quoted_for_github_parser():
    manifest = _read_json(ROOT / "docs" / "readme_manifest.json")
    rendered = render_readme(
        manifest=manifest,
        state=parse_state(),
        passing_tests=collected_test_count(),
    )

    assert 'L0["L0 Baseline & Lab Contract (COMPLETE)"]' in rendered
    assert 'RAG["Governed RAG"]' in rendered
    assert "L0[L0 Baseline & Lab Contract (COMPLETE)]" not in rendered
