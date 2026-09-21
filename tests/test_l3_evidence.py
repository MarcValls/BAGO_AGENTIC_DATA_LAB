"""Tests for the reproducible L3 ontology evidence artifact."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from generate_l3_ontology_evidence import (  # noqa: E402
    build_evidence_graph,
    render_mermaid,
)


def test_evidence_graph_is_integrity_clean():
    graph = build_evidence_graph()

    assert graph.validate_integrity() == []
    assert graph.get_lineage("claim_metadata_first") == [
        "claim_metadata_first",
        "asset_lab_contract",
    ]


def test_evidence_mermaid_contains_entities_and_relations():
    mermaid = render_mermaid(build_evidence_graph())

    assert mermaid.startswith("graph LR")
    assert "asset_claim_metadata_first" in mermaid
    assert "chunk_chunk_contract_001" in mermaid
    assert "DERIVED_FROM" in mermaid
    assert "VALIDATES" in mermaid
    assert "PROVENANCE" in mermaid
