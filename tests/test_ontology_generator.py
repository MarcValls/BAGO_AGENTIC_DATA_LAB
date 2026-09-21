"""CRIT P0 tests for the three-level ontology generator pipeline."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from metadata.ontology import KnowledgeGraph, OntologyRelation, RelationType  # noqa: E402
from metadata.ontology_generator import (  # noqa: E402
    MetadataGenerator,
    OntologyGenerator,
    OntologyProposal,
    OntologyValidator,
    ProposalStatus,
    RelationProposal,
)
from metadata.schema import KnowledgeAsset  # noqa: E402


DOCUMENT = """# BAGO Authorization Contract

Version: v2.0.0
Authority: CANONICAL

Contract IMPLEMENTS Component.
Permit AUTHORIZES Execution.
Execution GENERATES Evidence.
Provider SERVES Model.
"""


def build_proposal():
    return OntologyGenerator().generate([("execution_gateway.v2.md", DOCUMENT)])


def test_metadata_generator_extracts_document_and_concepts():
    proposal = build_proposal()

    document = next(asset for asset in proposal.graph.assets.values() if asset.asset_type == "DOCUMENT")
    concept_ids = set(proposal.graph.assets) - {document.asset_id}

    assert document.title == "BAGO Authorization Contract"
    assert document.version == "2.0.0"
    assert document.authority.value == "CANONICAL"
    assert document.metadata["provenance"] == "execution_gateway.v2.md"
    assert {
        "concept_contract",
        "concept_component",
        "concept_permit",
        "concept_execution",
        "concept_evidence",
        "concept_provider",
        "concept_model",
    }.issubset(concept_ids)


def test_metadata_generator_does_not_promote_on_a_generic_evidence_word():
    record = MetadataGenerator().extract_document(
        "notes.md",
        "# Notes\nEvidence is required for every proposal.",
    )

    assert record.asset.authority.value == "PROPOSED"


def test_metadata_generator_deduplicates_bilingual_concept_aliases():
    proposal = OntologyGenerator().generate(
        [
            (
                "bilingual.md",
                "TYPE=CONTRACT\nContrato AUTORIZA Ejecución. "
                "Proveedor SIRVE Modelo.",
            )
        ]
    )

    relation_keys = {
        (item.relation.source_id, item.relation.relation_type, item.relation.target_id)
        for item in proposal.relation_proposals
    }

    assert next(asset for asset in proposal.graph.assets.values() if asset.asset_type == "CONTRACT").asset_type == "CONTRACT"
    assert ("concept_contract", RelationType.AUTHORIZES, "concept_execution") in relation_keys
    assert ("concept_provider", RelationType.SERVES, "concept_model") in relation_keys


def test_relation_extractor_returns_proposals_not_accepted_edges():
    proposal = build_proposal()
    relation_types = {item.relation.relation_type for item in proposal.relation_proposals}

    assert proposal.graph.relations == []
    assert all(item.status is ProposalStatus.PROPOSED for item in proposal.relation_proposals)
    assert {
        RelationType.IMPLEMENTS,
        RelationType.AUTHORIZES,
        RelationType.GENERATES,
        RelationType.SERVES,
    }.issubset(relation_types)


def test_validator_accepts_explicit_relations_into_a_new_graph():
    proposal = build_proposal()

    report = OntologyValidator().validate(proposal)
    accepted_graph = OntologyValidator().accept(proposal, report)

    assert report.is_valid
    assert len(report.accepted) == 4
    assert report.rejected == []
    assert len(accepted_graph.relations) == 4
    assert proposal.graph.relations == []
    assert accepted_graph.validate_integrity() == []


def test_validator_rejects_unknown_endpoints_without_promoting_them():
    proposal = build_proposal()
    relation = OntologyRelation(
        relation_id="relation_unknown",
        relation_type=RelationType.IMPLEMENTS,
        source_id="missing_agent",
        target_id="concept_component",
        confidence=0.99,
    )
    invalid = OntologyProposal(
        graph=proposal.graph,
        relation_proposals=[
            RelationProposal(
                proposal_id="proposal_unknown",
                relation=relation,
                evidence_ref="synthetic invalid relation",
            )
        ],
        document_uris=proposal.document_uris,
    )

    report = OntologyValidator().validate(invalid)
    accepted_graph = OntologyValidator().accept(invalid, report)

    assert not report.is_valid
    assert len(report.rejected) == 1
    assert "missing_agent" in report.rejected[0].rejection_reason
    assert accepted_graph.relations == []


def test_validator_rejects_derived_from_cycles():
    graph = KnowledgeGraph()
    graph.add_asset(
        KnowledgeAsset(
            asset_id="concept_a",
            title="A",
            description="A",
            asset_type="CONCEPT",
            source_id="source",
        )
    )
    graph.add_asset(
        KnowledgeAsset(
            asset_id="concept_b",
            title="B",
            description="B",
            asset_type="CONCEPT",
            source_id="source",
        )
    )
    proposals = [
        RelationProposal(
            proposal_id="proposal_a",
            relation=OntologyRelation(
                relation_id="relation_a",
                relation_type=RelationType.DERIVED_FROM,
                source_id="concept_a",
                target_id="concept_b",
            ),
            evidence_ref="A DERIVED_FROM B",
        ),
        RelationProposal(
            proposal_id="proposal_b",
            relation=OntologyRelation(
                relation_id="relation_b",
                relation_type=RelationType.DERIVED_FROM,
                source_id="concept_b",
                target_id="concept_a",
            ),
            evidence_ref="B DERIVED_FROM A",
        ),
    ]

    report = OntologyValidator().validate(
        OntologyProposal(graph=graph, relation_proposals=proposals, document_uris=())
    )

    assert len(report.accepted) == 1
    assert len(report.rejected) == 1
    assert "cycle" in report.rejected[0].rejection_reason.lower()
