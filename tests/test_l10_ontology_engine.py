"""L10 governed ontology engine: RDF, SPARQL, inference and evidence paths."""

from __future__ import annotations

import sys
from pathlib import Path

import anyio

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from agent.governed_knowledge_agent import AgentRunStatus, GovernedKnowledgeAgent  # noqa: E402
from metadata.ontology import KnowledgeGraph, OntologyRelation, RelationType  # noqa: E402
from metadata.ontology_engine import (  # noqa: E402
    OntologyEngine,
    RDFGraph,
    RDFTriple,
)
from metadata.schema import (  # noqa: E402
    AuthorityLevel,
    KnowledgeAsset,
    Source,
)
from retrieval.governed_rag import GovernedRAG, RetrievalChunk  # noqa: E402


def _knowledge_graph() -> KnowledgeGraph:
    graph = KnowledgeGraph()
    graph.sources.update(
        {
            "source_policy": Source("source_policy", "docs/policy.md", "FILE"),
            "source_evidence": Source("source_evidence", "evidence/policy-receipt.md", "FILE"),
        }
    )
    policy_v1 = KnowledgeAsset(
        asset_id="policy_v1",
        title="Permit policy v1",
        description="Previous permit policy",
        asset_type="CONTRACT",
        source_id="source_policy",
        version="1.0.0",
        authority=AuthorityLevel.CANONICAL,
        metadata={"provenance": "docs/policy-v1.md"},
    )
    policy_v2 = KnowledgeAsset(
        asset_id="policy_v2",
        title="Permit policy v2",
        description="Current permit policy",
        asset_type="CONTRACT",
        source_id="source_policy",
        version="2.0.0",
        authority=AuthorityLevel.VERIFIED,
        metadata={"provenance": "docs/policy-v2.md"},
    )
    evidence = KnowledgeAsset(
        asset_id="policy_receipt",
        title="Policy v2 validation receipt",
        description="Receipt proving the policy validation",
        asset_type="EVIDENCE",
        source_id="source_evidence",
        version="1.0.0",
        authority=AuthorityLevel.VERIFIED,
        metadata={"provenance": "evidence/policy-receipt.md"},
    )
    candidate = KnowledgeAsset(
        asset_id="candidate_policy",
        title="Candidate policy",
        description="An incompatible experimental policy",
        asset_type="CONTRACT",
        source_id="source_policy",
        version="0.1.0",
        authority=AuthorityLevel.PROPOSED,
        metadata={"provenance": "docs/candidate-policy.md"},
    )
    policy_v1.mark_superseded("policy_v2")
    for asset in (policy_v1, policy_v2, evidence, candidate):
        graph.add_asset(asset)
    graph.relations.extend(
        [
            OntologyRelation(
                "rel_supersedes",
                RelationType.SUPERSEDES,
                "policy_v2",
                "policy_v1",
            ),
            OntologyRelation(
                "rel_validates",
                RelationType.VALIDATES,
                "policy_receipt",
                "policy_v2",
            ),
            OntologyRelation(
                "rel_contradicts",
                RelationType.CONTRADICTS,
                "candidate_policy",
                "policy_v2",
            ),
        ]
    )
    return graph


def test_engine_materializes_rdf_and_inverse_supersession_reasoning():
    engine = OntologyEngine.from_knowledge_graph(_knowledge_graph())

    assert len(engine.rdf_graph) > 0
    assert "@prefix bago:" in engine.graph.to_turtle()
    rows = engine.select(
        "PREFIX bago: <https://bago.local/ontology/> "
        "SELECT ?subject ?object WHERE "
        "{ ?subject bago:supersedes ?object . } LIMIT 10"
    )
    assert {
        (row["subject"].rsplit("/", 1)[-1], row["object"].rsplit("/", 1)[-1])
        for row in rows
    } == {("policy_v2", "policy_v1")}
    inverse = engine.select(
        "PREFIX bago: <https://bago.local/ontology/> "
        "SELECT ?old ?new WHERE "
        "{ ?old bago:supersededBy ?new . } LIMIT 10"
    )
    assert {(row["old"].rsplit("/", 1)[-1], row["new"].rsplit("/", 1)[-1]) for row in inverse} == {
        ("policy_v1", "policy_v2")
    }


def test_sparql_filter_and_reasoning_return_evidence_paths_and_contradictions():
    engine = OntologyEngine.from_knowledge_graph(_knowledge_graph())
    filtered = engine.select(
        "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> "
        "SELECT ?asset ?label WHERE { "
        "?asset rdfs:label ?label . "
        'FILTER regex(str(?label), "policy v2", "i") } LIMIT 10'
    )
    assert len(filtered) == 2
    assert any(row["asset"].endswith("/policy_v2") for row in filtered)

    result = engine.reason("¿Qué sustituye a la política anterior y qué evidencia la valida?")

    assert result.paths
    assert any(
        edge.predicate.endswith("/supersedes")
        for path in result.paths
        for edge in path.triples
    )
    assert any(
        edge.predicate.endswith("/validatedBy") or edge.predicate.endswith("/validates")
        for path in result.paths
        for edge in path.triples
    )
    assert result.contradictions
    assert "docs/policy-v2.md#revision=2.0.0" in result.evidence_refs
    assert result.receipt.cost_usd == 0.0
    assert result.receipt.outcome == "CONSTRAINT_VIOLATION"


def test_rag_seed_is_carried_into_agent_ontology_context_and_receipt():
    engine = OntologyEngine.from_knowledge_graph(_knowledge_graph())
    chunks = [
        RetrievalChunk(
            chunk_id="policy-v2-chunk",
            document_id="policy_v2",
            content="Permit policy v2 supersedes policy v1 and is validated by a receipt.",
            title="Permit policy v2",
            source_uri="docs/policy-v2.md",
            revision="2.0.0",
            authority=AuthorityLevel.VERIFIED,
            metadata={"asset_id": "policy_v2"},
        )
    ]
    agent = GovernedKnowledgeAgent(GovernedRAG(chunks), ontology_engine=engine)

    async def invoke():
        return await agent.run("¿Qué sustituye a la política anterior y qué evidencia la valida?")

    result = anyio.run(invoke)

    assert result.status is AgentRunStatus.CONSTRAINT_VIOLATION
    assert result.ontology is not None
    assert result.ontology.receipt.cost_usd == 0.0
    assert "Ontology Engine" in result.answer
    assert "policy_v2" in result.answer
    assert "docs/policy-v2.md#revision=2.0.0" in result.citations
    assert any(item.startswith("ontology_engine=") for item in result.trace)


def test_raw_rdf_graph_reports_relation_without_evidence_as_warning():
    engine = OntologyEngine(
        RDFGraph(
            [
                RDFTriple(
                    "https://bago.local/ontology/a",
                    "https://bago.local/ontology/contradicts",
                    "https://bago.local/ontology/b",
                )
            ]
        ),
        known_nodes=("a", "b"),
    )
    violations = engine.validate_constraints()

    assert any(item.code == "CONTRADICTION" for item in violations)
    assert any(item.code == "MISSING_EVIDENCE" and item.severity == "WARNING" for item in violations)
