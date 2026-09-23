"""Persistent, zero-cost vector index for governed local retrieval.

The store persists deterministic ``HashEmbedding`` vectors beside the chunk
metadata in SQLite.  It is intentionally a small local backend, not a claim
to provide distributed vector-database or production ANN guarantees.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence

from metadata.schema import AuthorityLevel, ValidityStatus

from .governed_rag import (
    EvidenceRef,
    HashEmbedding,
    MetadataFilter,
    RetrievalChunk,
)


class VectorIndexError(ValueError):
    """Raised when a persistent vector index cannot satisfy a request."""


@dataclass(frozen=True)
class VectorHit:
    """Evidence-bearing result from the local vector index."""

    rank: int
    chunk: RetrievalChunk
    score: float
    evidence: EvidenceRef

    def to_dict(self) -> dict[str, Any]:
        return {
            "rank": self.rank,
            "chunk_id": self.chunk.chunk_id,
            "document_id": self.chunk.document_id,
            "score": round(self.score, 8),
            "evidence": self.evidence.to_dict(),
        }


@dataclass(frozen=True)
class VectorSearchResponse:
    """Reviewable local vector-search receipt."""

    query: str
    hits: tuple[VectorHit, ...]
    eligible_count: int
    filtered_count: int
    index_fingerprint: str
    backend: str = "sqlite_hash_vector"

    @property
    def citations(self) -> tuple[str, ...]:
        return tuple(hit.evidence.citation for hit in self.hits)

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "backend": self.backend,
            "index_fingerprint": self.index_fingerprint,
            "hits": [hit.to_dict() for hit in self.hits],
            "eligible_count": self.eligible_count,
            "filtered_count": self.filtered_count,
            "citations": list(self.citations),
        }


class SQLiteVectorStore:
    """Persistent local semantic index with metadata-first governance."""

    def __init__(
        self,
        db_path: str | Path,
        *,
        embedder: HashEmbedding | None = None,
    ) -> None:
        self.db_path = Path(db_path).expanduser().resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.embedder = embedder or HashEmbedding()
        self._initialize()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS vector_chunks (
                    chunk_id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    title TEXT NOT NULL,
                    source_uri TEXT NOT NULL,
                    revision TEXT NOT NULL,
                    authority TEXT NOT NULL,
                    validity TEXT NOT NULL,
                    domain TEXT,
                    created_at TEXT,
                    metadata_json TEXT NOT NULL,
                    vector_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS vector_index_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                """
            )
            current = connection.execute(
                "SELECT value FROM vector_index_meta WHERE key = 'dimensions'"
            ).fetchone()
            if current is None:
                connection.execute(
                    "INSERT INTO vector_index_meta(key, value) VALUES('dimensions', ?)",
                    (str(self.embedder.dimensions),),
                )
            elif int(current["value"]) != self.embedder.dimensions:
                raise VectorIndexError(
                    "vector dimensions do not match the existing SQLite index"
                )

    @property
    def count(self) -> int:
        with self._connection() as connection:
            row = connection.execute("SELECT COUNT(*) AS count FROM vector_chunks").fetchone()
        return int(row["count"])

    @property
    def index_fingerprint(self) -> str:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT chunk_id, document_id, content, source_uri, revision,
                       authority, validity, metadata_json, vector_json
                FROM vector_chunks ORDER BY chunk_id
                """
            ).fetchall()
        payload = "\n".join(
            "|".join(str(row[key]) for key in row.keys())
            for row in rows
        )
        return hashlib.sha256(
            f"dimensions={self.embedder.dimensions}\n{payload}".encode("utf-8")
        ).hexdigest()

    def upsert(self, chunks: Iterable[RetrievalChunk]) -> int:
        """Persist chunks and deterministic vectors; return rows written."""

        materialized = tuple(chunks)
        identifiers = [chunk.chunk_id for chunk in materialized]
        if len(identifiers) != len(set(identifiers)):
            raise VectorIndexError("chunk_id debe ser único en el vector index")
        with self._connection() as connection:
            for chunk in materialized:
                metadata_json = json.dumps(
                    dict(chunk.metadata),
                    ensure_ascii=False,
                    sort_keys=True,
                    default=str,
                )
                vector_json = json.dumps(
                    list(self.embedder.embed(chunk.content)),
                    separators=(",", ":"),
                )
                connection.execute(
                    """
                    INSERT INTO vector_chunks(
                        chunk_id, document_id, content, title, source_uri, revision,
                        authority, validity, domain, created_at, metadata_json, vector_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(chunk_id) DO UPDATE SET
                        document_id=excluded.document_id,
                        content=excluded.content,
                        title=excluded.title,
                        source_uri=excluded.source_uri,
                        revision=excluded.revision,
                        authority=excluded.authority,
                        validity=excluded.validity,
                        domain=excluded.domain,
                        created_at=excluded.created_at,
                        metadata_json=excluded.metadata_json,
                        vector_json=excluded.vector_json
                    """,
                    (
                        chunk.chunk_id,
                        chunk.document_id,
                        chunk.content,
                        chunk.title,
                        chunk.source_uri,
                        chunk.revision,
                        chunk.authority.value,
                        chunk.validity.value,
                        chunk.domain,
                        chunk.created_at,
                        metadata_json,
                        vector_json,
                    ),
                )
        return len(materialized)

    def load_chunks(self) -> tuple[RetrievalChunk, ...]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM vector_chunks ORDER BY chunk_id"
            ).fetchall()
        return tuple(self._chunk_from_row(row) for row in rows)

    def scores(
        self,
        query: str,
        chunks: Sequence[RetrievalChunk],
    ) -> dict[str, float]:
        """Implement the semantic backend contract used by ``GovernedRAG``."""

        query_vector = self.embedder.embed(query)
        requested = {chunk.chunk_id for chunk in chunks}
        if not requested:
            return {}
        with self._connection() as connection:
            placeholders = ",".join("?" for _ in requested)
            rows = connection.execute(
                f"SELECT chunk_id, vector_json FROM vector_chunks WHERE chunk_id IN ({placeholders})",
                tuple(sorted(requested)),
            ).fetchall()
        vectors = {str(row["chunk_id"]): json.loads(row["vector_json"]) for row in rows}
        missing = sorted(requested - set(vectors))
        if missing:
            raise VectorIndexError(
                "chunks are absent from the persistent vector index: " + ", ".join(missing)
            )
        return {
            chunk_id: sum(left * right for left, right in zip(query_vector, vectors[chunk_id]))
            for chunk_id in requested
        }

    def search(
        self,
        query: str,
        *,
        top_k: int = 10,
        metadata_filter: MetadataFilter | None = None,
    ) -> VectorSearchResponse:
        """Search vectors after applying the BAGO metadata gate."""

        if not query.strip():
            raise VectorIndexError("query no puede estar vacío")
        if top_k <= 0:
            raise VectorIndexError("top_k debe ser positivo")
        chunks = self.load_chunks()
        active_filter = metadata_filter or MetadataFilter()
        eligible = tuple(chunk for chunk in chunks if active_filter.allows(chunk))
        scores = self.scores(query, eligible)
        ranked = sorted(scores, key=lambda chunk_id: (-scores[chunk_id], chunk_id))[:top_k]
        by_id = {chunk.chunk_id: chunk for chunk in eligible}
        hits = tuple(
            VectorHit(
                rank=index,
                chunk=by_id[chunk_id],
                score=scores[chunk_id],
                evidence=EvidenceRef(
                    chunk_id=by_id[chunk_id].chunk_id,
                    document_id=by_id[chunk_id].document_id,
                    source_uri=by_id[chunk_id].source_uri,
                    revision=by_id[chunk_id].revision,
                ),
            )
            for index, chunk_id in enumerate(ranked, start=1)
        )
        return VectorSearchResponse(
            query=query,
            hits=hits,
            eligible_count=len(eligible),
            filtered_count=len(chunks) - len(eligible),
            index_fingerprint=self.index_fingerprint,
        )

    @staticmethod
    def _chunk_from_row(row: sqlite3.Row) -> RetrievalChunk:
        return RetrievalChunk(
            chunk_id=str(row["chunk_id"]),
            document_id=str(row["document_id"]),
            content=str(row["content"]),
            title=str(row["title"]),
            source_uri=str(row["source_uri"]),
            revision=str(row["revision"]),
            authority=AuthorityLevel(str(row["authority"])),
            validity=ValidityStatus(str(row["validity"])),
            domain=row["domain"],
            created_at=row["created_at"],
            metadata=json.loads(row["metadata_json"]),
        )


__all__ = [
    "SQLiteVectorStore",
    "VectorHit",
    "VectorIndexError",
    "VectorSearchResponse",
]
