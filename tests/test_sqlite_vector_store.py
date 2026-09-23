"""Persistent local vector index and GovernedRAG integration contract."""

from pathlib import Path
import sys

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))

from metadata.schema import AuthorityLevel, ValidityStatus  # noqa: E402
from retrieval.governed_rag import GovernedRAG, MetadataFilter, RetrievalChunk, RetrievalMode  # noqa: E402
from retrieval.sqlite_vector_store import SQLiteVectorStore, VectorIndexError  # noqa: E402


def _chunks() -> list[RetrievalChunk]:
    return [
        RetrievalChunk(
            chunk_id="vector-current",
            document_id="policy-v2",
            content="La política vigente sustituye la versión anterior y exige evidencia.",
            title="Current policy",
            source_uri="docs/policy-v2.md",
            revision="2.0.0",
            authority=AuthorityLevel.VERIFIED,
            metadata={"asset_id": "policy-v2"},
        ),
        RetrievalChunk(
            chunk_id="vector-old",
            document_id="policy-v1",
            content="La política anterior describe permisos históricos.",
            title="Old policy",
            source_uri="docs/policy-v1.md",
            revision="1.0.0",
            authority=AuthorityLevel.CANONICAL,
            validity=ValidityStatus.SUPERSEDED,
            metadata={"asset_id": "policy-v1"},
        ),
        RetrievalChunk(
            chunk_id="vector-evidence",
            document_id="policy-receipt",
            content="La evidencia valida la política vigente.",
            title="Validation receipt",
            source_uri="evidence/policy-receipt.md",
            revision="1.0.0",
            authority=AuthorityLevel.VERIFIED,
            metadata={"asset_id": "policy-receipt"},
        ),
    ]


def test_sqlite_vector_store_persists_vectors_and_applies_metadata_gate(tmp_path: Path):
    store = SQLiteVectorStore(tmp_path / "vectors.db")
    assert store.upsert(_chunks()) == 3
    fingerprint = store.index_fingerprint

    response = store.search("qué evidencia valida la política vigente", top_k=3)

    assert store.count == 3
    assert fingerprint == store.index_fingerprint
    assert response.backend == "sqlite_hash_vector"
    assert response.eligible_count == 2
    assert response.filtered_count == 1
    assert response.hits[0].chunk.chunk_id == "vector-evidence"
    assert response.citations[0] == "evidence/policy-receipt.md#revision=1.0.0"


def test_governed_rag_can_use_the_persistent_vector_backend(tmp_path: Path):
    db_path = tmp_path / "vectors.db"
    chunks = _chunks()
    store = SQLiteVectorStore(db_path)
    store.upsert(chunks)

    retriever = GovernedRAG(
        chunks,
        semantic_backend=store,
        policy=MetadataFilter(minimum_authority=AuthorityLevel.VERIFIED),
    )
    response = retriever.retrieve(
        "política vigente evidencia",
        mode=RetrievalMode.SEMANTIC,
        top_k=2,
        rerank=False,
    )

    assert response.hits
    assert response.hits[0].chunk.chunk_id == "vector-evidence"
    assert "semantic_embedding" in response.pipeline
    assert response.hits[0].evidence.citation.startswith("evidence/")


def test_governed_rag_reloads_from_sqlite_vector_store(tmp_path: Path):
    db_path = tmp_path / "vectors.db"
    SQLiteVectorStore(db_path).upsert(_chunks())

    retriever = GovernedRAG.from_sqlite_vector_store(db_path)
    response = retriever.retrieve("política vigente", mode=RetrievalMode.SEMANTIC, top_k=2, rerank=False)

    assert {hit.chunk.chunk_id for hit in response.hits} == {"vector-current", "vector-evidence"}


def test_vector_backend_fails_closed_when_a_chunk_is_not_indexed(tmp_path: Path):
    store = SQLiteVectorStore(tmp_path / "vectors.db")
    store.upsert(_chunks()[:1])

    try:
        store.scores("política", _chunks())
    except VectorIndexError as error:
        assert "absent" in str(error)
    else:
        raise AssertionError("a missing persistent vector must fail closed")
