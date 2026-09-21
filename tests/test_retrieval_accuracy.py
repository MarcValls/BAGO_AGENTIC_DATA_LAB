"""L4 governed RAG tests: ranking, governance filters and evidence."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from metadata.schema import AuthorityLevel, ValidityStatus  # noqa: E402
from retrieval.governed_rag import (  # noqa: E402
    GovernedRAG,
    MetadataFilter,
    QueryIntent,
    RetrievalChunk,
    RetrievalMode,
    load_sqlite_chunks,
)


def _chunk(
    chunk_id: str,
    content: str,
    *,
    authority: AuthorityLevel = AuthorityLevel.VERIFIED,
    validity: ValidityStatus = ValidityStatus.CURRENT,
    domain: str = "governance",
    created_at: str = "2026-09-21T12:00:00Z",
) -> RetrievalChunk:
    return RetrievalChunk(
        chunk_id=chunk_id,
        document_id=f"doc-{chunk_id}",
        content=content,
        title=chunk_id.replace("-", " "),
        source_uri=f"docs/{chunk_id}.md",
        revision="v1",
        authority=authority,
        validity=validity,
        domain=domain,
        created_at=created_at,
        metadata={"classification": ["ARCHITECTURE"]},
    )


def corpus() -> list[RetrievalChunk]:
    return [
        _chunk(
            "permit-auth",
            "A Permit authorizes an Execution through the ExecutionGateway. "
            "Authorization limits are checked before the effect.",
            authority=AuthorityLevel.CANONICAL,
        ),
        _chunk(
            "hybrid-rag",
            "Hybrid retrieval combines BM25 lexical matching with semantic embeddings "
            "and reranking for governed context assembly.",
            domain="retrieval",
        ),
        _chunk(
            "evidence-lineage",
            "Evidence receipts map a claim to its chunk, source and revision for audit.",
            domain="evidence",
        ),
        _chunk(
            "old-permit",
            "The old Permit authorizes an Execution with the previous policy.",
            authority=AuthorityLevel.CANONICAL,
            validity=ValidityStatus.SUPERSEDED,
        ),
        _chunk(
            "mcp-tools",
            "MCP tools require explicit registration and effect classification.",
            domain="mcp",
        ),
        _chunk(
            "unrelated",
            "The portfolio timeline contains interview preparation and market notes.",
            domain="career",
        ),
    ]


def test_query_intent_is_traceable_without_authorizing_actions():
    assert GovernedRAG.classify_intent("metadata provenance") is QueryIntent.RETRIEVAL
    assert GovernedRAG.classify_intent("¿Cómo comparar lexical y semantic retrieval?") is QueryIntent.REASONING
    assert GovernedRAG.classify_intent("ejecuta el workflow") is QueryIntent.ACTION


def test_lexical_retrieval_returns_exact_governed_evidence():
    response = GovernedRAG(corpus()).retrieve(
        "permit authorizes execution",
        mode=RetrievalMode.LEXICAL,
        top_k=2,
    )

    assert response.hits[0].chunk.chunk_id == "permit-auth"
    assert response.hits[0].evidence.citation == "docs/permit-auth.md#revision=v1"
    assert "lexical_bm25" in response.pipeline
    assert "Evidence: docs/permit-auth.md#revision=v1" in response.assemble_context()


def test_hybrid_retrieval_fuses_components_and_reranks_deterministically():
    retriever = GovernedRAG(corpus())
    first = retriever.retrieve("authorization execution gateway", top_k=3)
    second = retriever.retrieve("authorization execution gateway", top_k=3)

    assert first.mode is RetrievalMode.HYBRID
    assert first.hits[0].chunk.chunk_id == "permit-auth"
    assert [hit.chunk.chunk_id for hit in first.hits] == [
        hit.chunk.chunk_id for hit in second.hits
    ]
    assert "hybrid_rrf_fusion" in first.pipeline
    assert "deterministic_reranker" in first.pipeline


def test_semantic_mode_is_offline_and_returns_component_scores():
    response = GovernedRAG(corpus()).retrieve(
        "authorisation execution gateway",
        mode=RetrievalMode.SEMANTIC,
        top_k=3,
        rerank=False,
    )

    assert response.hits
    assert "semantic_embedding" in response.pipeline
    assert all(isinstance(hit.semantic_score, float) for hit in response.hits)
    assert response.reranked is False


def test_metadata_gate_excludes_superseded_and_below_authority_chunks():
    response = GovernedRAG(corpus()).retrieve(
        "permit execution",
        metadata_filter=MetadataFilter(
            minimum_authority=AuthorityLevel.CANONICAL,
            allowed_domains=("governance",),
        ),
        top_k=10,
    )

    assert response.eligible_count == 1
    assert response.filtered_count == 5
    assert [hit.chunk.chunk_id for hit in response.hits] == ["permit-auth"]


def test_metadata_gate_requires_provenance():
    missing_provenance = RetrievalChunk(
        chunk_id="missing-provenance",
        document_id="doc-missing",
        content="A useful governed fact.",
    )
    response = GovernedRAG([missing_provenance]).retrieve("governed fact")

    assert response.eligible_count == 0
    assert response.hits == ()


def test_sqlite_adapter_loads_l2_chunks_with_stable_evidence_refs():
    chunks = load_sqlite_chunks("l2_etl_metadata.db")
    response = GovernedRAG(chunks).retrieve("metadata authority provenance", top_k=5)

    assert len(chunks) == 65
    assert response.hits
    assert all(hit.evidence.source_uri.startswith("etl://") for hit in response.hits)
    assert all(hit.evidence.revision == "etl" for hit in response.hits)


def test_top_k_and_context_budget_are_respected():
    response = GovernedRAG(corpus()).retrieve("execution", top_k=2)

    assert len(response.hits) <= 2
    assert response.hits[0].rank == 1
    assert len(response.assemble_context(max_chars=80)) <= 80


def test_invalid_queries_and_duplicate_chunks_are_rejected():
    try:
        GovernedRAG([corpus()[0], corpus()[0]])
    except ValueError as error:
        assert "único" in str(error)
    else:
        raise AssertionError("duplicate chunk IDs must be rejected")

    retriever = GovernedRAG(corpus())
    for query in ("", "   "):
        try:
            retriever.retrieve(query)
        except ValueError as error:
            assert "vacío" in str(error)
        else:
            raise AssertionError("empty queries must be rejected")
