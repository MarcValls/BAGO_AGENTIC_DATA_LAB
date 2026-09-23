"""Public clone-and-run E2E contract."""

from pathlib import Path
import sys

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from run_public_e2e_demo import render_evidence, run_demo  # noqa: E402


def test_public_demo_passes_the_complete_local_chain():
    result = run_demo()

    assert result["status"] == "PASS"
    assert result["agent_run"].status.value == "COMPLETED"
    assert result["ontology"].receipt.outcome == "SUCCESS"
    assert result["sandbox"].ok
    assert result["evaluation"].status.value == "PASS"
    assert result["evaluation"].score == 1.0


def test_public_demo_contains_the_expected_evidence_links():
    result = run_demo()

    assert len(result["agent_run"].retrieval.citations) == 2
    assert result["ontology"].receipt.paths_found >= 1
    assert result["ontology"].receipt.contradictions_found == 0
    assert result["sandbox"].receipt.network_mode == "deny"
    assert "ontology_engine" in result["trace"].names
    assert "sandbox_execution" in result["trace"].names
    assert result["fixture_calls"] == 1


def test_public_demo_evidence_declares_its_external_boundaries():
    evidence = render_evidence(run_demo())

    assert "AWS live: `NOT_RUN`" in evidence
    assert "OpenMetadata live: `NOT_RUN`" in evidence
    assert "python scripts/run_public_e2e_demo.py --check" in evidence
    assert '"evaluation_status": "PASS"' in evidence
