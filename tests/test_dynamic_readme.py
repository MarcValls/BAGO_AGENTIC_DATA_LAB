"""Tests for the fully generated README contract."""

from pathlib import Path
import re
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import generate_dynamic_readme as generator  # noqa: E402
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


def test_checked_in_readme_matches_canonical_render():
    rendered = render_readme(
        manifest=_read_json(ROOT / "docs" / "readme_manifest.json"),
        state=parse_state(),
        passing_tests=0,
    )

    assert (ROOT / "README_DETAILS.md").read_text(encoding="utf-8") == rendered
    assert (ROOT / "README.md").read_text(encoding="utf-8") == generator.render_svg_landing()


@pytest.mark.parametrize(
    ("content", "expected_status"),
    [("canonical", 0), ("stale", 1), ("missing", 1)],
)
def test_readme_ci_check_is_read_only(
    tmp_path, monkeypatch, capsys, content, expected_status
):
    readme = tmp_path / "README.md"
    if content != "missing":
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        if content == "stale":
            text += "\nStale generated content.\n"
        readme.write_text(text, encoding="utf-8")
    before = readme.read_bytes() if readme.exists() else None
    monkeypatch.setattr(generator, "README_PATH", readme)
    monkeypatch.setattr(generator, "collected_test_count", lambda: 248)

    def unexpected_execution():
        pytest.fail("--skip-tests must not execute the suite")

    monkeypatch.setattr(generator, "executed_test_count", unexpected_execution)

    assert generator.main(["--check", "--skip-tests"]) == expected_status
    output = capsys.readouterr().out
    if expected_status == 0:
        assert "suite NOT_RUN (248 casos recogidos)" in output
    else:
        assert "README desactualizado" in output
        assert "python scripts/generate_dynamic_readme.py" in output
    assert (readme.read_bytes() if readme.exists() else None) == before


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
    assert l1["status"] == "VALIDATED (local governed graph evidence)"
    l3 = next(phase for phase in phases if phase["id"] == "L3")
    assert sum(
        _test_function_count(ROOT / match)
        for check in l1["checks"]
        if check["kind"] == "tests"
        for match in check["matches"]
    ) == 14
    assert sum(
        _test_function_count(ROOT / match)
        for check in l3["checks"]
        if check["kind"] == "tests"
        for match in check["matches"]
    ) == 25


def test_readme_inventory_and_market_tables_are_discovered():
    workflow = (ROOT / ".github" / "workflows" / "readme-consistency.yml").read_text(
        encoding="utf-8"
    )
    assert workflow.index("run: python -m pip install -r requirements-test.txt") < workflow.index(
        "run: python scripts/generate_dynamic_readme.py --check --skip-tests"
    )
    assert collected_test_count() >= 100
    assert parse_roles()
    skills = parse_skills()
    assert any(row[0] == "RDF / SPARQL / Knowledge Graphs" for row in skills)
    soft_skills = parse_soft_skills()
    assert any(row[0] == "Arquitectura de sistemas" for row in soft_skills)


def test_ci_installs_video_runtime_before_running_full_suite():
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    test_dependencies = (ROOT / "requirements-test.txt").read_text(encoding="utf-8")

    assert "Pillow==13.0.0" in test_dependencies
    assert "sudo apt-get install --yes ffmpeg" in workflow
    assert workflow.index("sudo apt-get install --yes ffmpeg") < workflow.index(
        "run: python -m pytest tests -q"
    )


def test_rendered_readme_is_comprehensive_scope_bound_and_does_not_claim_collected_tests_pass():
    manifest = _read_json(ROOT / "docs" / "readme_manifest.json")
    rendered = render_readme(
        manifest=manifest,
        state=parse_state(),
        passing_tests=collected_test_count(),
    )

    # The principal product sections stay visible; only supplementary history
    # is folded. The requested corporate README has no compact-page line cap.
    visible = re.sub(r"<details>.*?</details>", "", rendered, flags=re.DOTALL)
    assert len(re.findall(r"^## ", visible, re.MULTILINE)) >= 14
    assert "**Entrada principal: Chat.**" in visible
    assert "BAGO Agentic Data Lab" in rendered
    assert "python demo.py" in rendered
    assert "docs/one_command_demo.md" in rendered
    assert "README.md` es un artefacto generado" in rendered
    assert "docs/readme_manifest.json" in rendered
    # The previous CI remains visible as history; the opening snapshot now has
    # its own dated, candidate-bound verification record.
    assert "Registro histórico de CI conservado en STATE.md" in rendered
    assert "38665463586" in rendered
    assert "ff9292fe4340a2bdab9658a2e804579fa4ef8fb0" in rendered
    assert "This result does not cover later changes" in rendered
    assert "NOT_RUN" in rendered
    assert "2026-10-08" in rendered
    assert "docs/agent-chat-control/TUTORIAL_PRIMER_USO.md" in rendered
    assert "evidence/l15_otel_jaeger_live.md" in rendered
    # Current imagery comes from the dated gallery, not the old Jaeger image.
    assert "portfolio/assets/jaeger-trace-graph.png" not in visible
    assert "### Roadmap y evidencia por fase" in rendered
    assert "| Fase | Código localizado | Tests | Evidencia | Patrones sin resolver |" not in rendered
    assert "### L1 — LangGraph Governed Execution" in rendered
    assert "**Patrones sin resolver:**" in rendered
    # Supplementary history can fold without hiding the product overview.
    assert rendered.count("<details>") == rendered.count("</details>") > 0
    assert "### Recorrido comercial de la app: Bruma Market" in rendered
    assert "BM-1001" in rendered and "BM-1004" in rendered
    assert "actions_executed" in rendered
    assert "directorio de clientes, facturas ni albaranes" in rendered
    assert "### Skills técnicas" in rendered
    assert "RDF / SPARQL / Knowledge Graphs" in rendered
    assert "state.json" not in rendered
    assert "203 test cases" not in rendered
    assert "248/248" not in rendered
    assert "tests-248" not in rendered
    assert "![Tests]" not in rendered
    assert "python scripts/run_l6_aws_free_tier_validation.py" not in rendered
    assert "Inventario real del checkout" not in rendered
    assert "Fit técnico" not in rendered

def test_mermaid_labels_are_quoted_for_github_parser():
    manifest = _read_json(ROOT / "docs" / "readme_manifest.json")
    rendered = render_readme(
        manifest=manifest,
        state=parse_state(),
        passing_tests=collected_test_count(),
    )

    assert 'L0["L0 Baseline & Lab Contract (COMPLETE)"]' in rendered
    assert 'L1["L1 LangGraph Governed Execution (VALIDATED (local governed graph evidence))"]' in rendered
    assert "L0[L0 Baseline & Lab Contract (COMPLETE)]" not in rendered
