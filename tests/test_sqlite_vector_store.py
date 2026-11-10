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


def test_immutable_upsert_rejects_content_change_without_partial_write(tmp_path: Path):
    from dataclasses import replace
    import pytest
    store = SQLiteVectorStore(tmp_path / 'immutable.db')
    original = _chunks()[0]
    store.upsert([original], immutable_content=True)
    new = replace(_chunks()[1], chunk_id='new-synthetic')
    conflicting = replace(original, content='different synthetic content')
    with pytest.raises(VectorIndexError):
        store.upsert([new, conflicting], immutable_content=True)
    assert store.count == 1
    assert store.load_chunks()[0].content == original.content
    assert store.upsert([original], immutable_content=True) == 1


def test_immutable_scope_observes_concurrent_writer_before_upsert(tmp_path: Path):
    import sqlite3
    import threading
    store = SQLiteVectorStore(tmp_path / 'concurrent.db')
    original = _chunks()[0]
    store.upsert([original])
    started, finished = threading.Event(), threading.Event()
    errors = []

    def worker():
        started.set()
        try:
            store.upsert([original], immutable_content=True,
                         immutable_scope=(original.source_uri, original.revision))
        except Exception as error:
            errors.append(error)
        finally:
            finished.set()

    with sqlite3.connect(store.db_path) as conn:
        conn.execute('BEGIN IMMEDIATE')
        row = conn.execute('SELECT * FROM vector_chunks WHERE chunk_id=?', (original.chunk_id,)).fetchone()
        conn.execute('INSERT INTO vector_chunks VALUES (?,?,?,?,?,?,?,?,?,?,?,?)', ('extra-concurrent', *row[1:]))
        thread = threading.Thread(target=worker)
        thread.start()
        assert started.wait(2)
        assert not finished.wait(.2)
        conn.commit()
    thread.join(5)
    assert not thread.is_alive()
    assert len(errors) == 1 and isinstance(errors[0], VectorIndexError)
    assert store.count == 2


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
