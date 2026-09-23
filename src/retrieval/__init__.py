"""Governed retrieval primitives for L4."""

from .governed_rag import (
    AuthorityLevel,
    EvidenceRef,
    GovernedRAG,
    HashEmbedding,
    MetadataFilter,
    QueryIntent,
    RetrievalChunk,
    RetrievalHit,
    RetrievalMode,
    RetrievalResponse,
    SemanticBackend,
    ValidityStatus,
    load_sqlite_chunks,
)
from .sqlite_vector_store import (
    SQLiteVectorStore,
    VectorHit,
    VectorIndexError,
    VectorSearchResponse,
)

__all__ = [
    "AuthorityLevel",
    "EvidenceRef",
    "GovernedRAG",
    "HashEmbedding",
    "MetadataFilter",
    "QueryIntent",
    "RetrievalChunk",
    "RetrievalHit",
    "RetrievalMode",
    "RetrievalResponse",
    "SemanticBackend",
    "SQLiteVectorStore",
    "VectorHit",
    "VectorIndexError",
    "VectorSearchResponse",
    "ValidityStatus",
    "load_sqlite_chunks",
]
