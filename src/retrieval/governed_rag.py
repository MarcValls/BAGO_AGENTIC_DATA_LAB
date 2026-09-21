"""L4 governed hybrid retrieval.

The module keeps retrieval separate from generation and execution:

``query -> intent -> metadata gate -> lexical/semantic retrieval -> rerank
-> evidence-ready context``

The semantic backend is deliberately deterministic and dependency-free.  It
uses hashed token and character n-gram features so tests and benchmark results
are reproducible offline.  A production embedding provider can replace
``HashEmbedding`` without changing the governance or evidence boundary.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Sequence

from metadata.schema import AuthorityLevel, ValidityStatus


class RetrievalMode(str, Enum):
    """Retrieval strategy used to rank eligible chunks."""

    LEXICAL = "lexical"
    SEMANTIC = "semantic"
    HYBRID = "hybrid"


class QueryIntent(str, Enum):
    """Coarse intent classification used for traceability, not execution."""

    RETRIEVAL = "retrieval"
    REASONING = "reasoning"
    ACTION = "action"


_AUTHORITY_RANK = {
    AuthorityLevel.DEPRECATED: 0,
    AuthorityLevel.EXPERIMENTAL: 1,
    AuthorityLevel.PROPOSED: 2,
    AuthorityLevel.VERIFIED: 3,
    AuthorityLevel.CANONICAL: 4,
}

_STOPWORDS = {
    "a",
    "al",
    "and",
    "are",
    "by",
    "con",
    "como",
    "de",
    "del",
    "el",
    "en",
    "es",
    "for",
    "from",
    "how",
    "la",
    "las",
    "los",
    "of",
    "on",
    "para",
    "por",
    "que",
    "the",
    "to",
    "un",
    "una",
    "with",
    "y",
}

_TOKEN_PATTERN = re.compile(r"[\w]+", re.UNICODE)


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    without_marks = "".join(char for char in decomposed if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", without_marks).strip().lower()


def _tokens(text: str) -> tuple[str, ...]:
    return tuple(
        token
        for token in _TOKEN_PATTERN.findall(_normalize(text))
        if len(token) > 1 and token not in _STOPWORDS
    )


def _char_features(text: str) -> tuple[str, ...]:
    """Return small character n-grams for deterministic paraphrase tolerance."""

    features: list[str] = []
    for word in _normalize(text).split():
        if len(word) < 3:
            continue
        padded = f"^{word}$"
        for size in (3, 4, 5):
            features.extend(
                f"{size}:{padded[index:index + size]}"
                for index in range(len(padded) - size + 1)
            )
    return tuple(features)


def _coerce_authority(value: AuthorityLevel | str) -> AuthorityLevel:
    if isinstance(value, AuthorityLevel):
        return value
    normalized = str(value).upper()
    try:
        return AuthorityLevel[normalized]
    except KeyError:
        try:
            return AuthorityLevel(normalized)
        except ValueError:
            return AuthorityLevel.PROPOSED


def _coerce_validity(value: ValidityStatus | str) -> ValidityStatus:
    if isinstance(value, ValidityStatus):
        return value
    normalized = str(value).upper()
    try:
        return ValidityStatus[normalized]
    except KeyError:
        try:
            return ValidityStatus(normalized)
        except ValueError:
            return ValidityStatus.UNKNOWN


@dataclass(frozen=True)
class RetrievalChunk:
    """A chunk plus the metadata required to make retrieval governable."""

    chunk_id: str
    document_id: str
    content: str
    metadata: Mapping[str, Any] = field(default_factory=dict)
    title: str = ""
    source_uri: str = ""
    revision: str = ""
    authority: AuthorityLevel | str = AuthorityLevel.PROPOSED
    validity: ValidityStatus | str = ValidityStatus.CURRENT
    domain: Optional[str] = None
    created_at: Optional[str] = None

    def __post_init__(self) -> None:
        metadata = dict(self.metadata)
        authority = _coerce_authority(self.authority)
        validity = _coerce_validity(self.validity)
        source_uri = self.source_uri or str(
            metadata.get("source_uri") or metadata.get("provenance") or ""
        )
        revision = self.revision or str(
            metadata.get("revision") or metadata.get("version") or ""
        )
        domain = self.domain or metadata.get("domain")
        created_at = self.created_at or metadata.get("created_at")
        object.__setattr__(self, "metadata", metadata)
        object.__setattr__(self, "authority", authority)
        object.__setattr__(self, "validity", validity)
        object.__setattr__(self, "source_uri", source_uri)
        object.__setattr__(self, "revision", revision)
        object.__setattr__(self, "domain", domain)
        object.__setattr__(self, "created_at", created_at)

    @property
    def provenance_complete(self) -> bool:
        return bool(self.source_uri and self.revision)

    @classmethod
    def from_etl_row(
        cls,
        row: Mapping[str, Any],
        *,
        source_prefix: str = "etl://",
    ) -> "RetrievalChunk":
        """Adapt one row from the L2 ``chunks`` table without mutating it."""

        raw_metadata = row.get("metadata_json", {})
        if isinstance(raw_metadata, str):
            try:
                metadata = json.loads(raw_metadata) if raw_metadata else {}
            except json.JSONDecodeError:
                metadata = {"metadata_parse_error": True}
        else:
            metadata = dict(raw_metadata or {})
        document_id = str(row.get("document_id", "unknown-document"))
        chunk_id = str(row.get("id", row.get("chunk_id", "unknown-chunk")))
        metadata.setdefault("provenance", f"{source_prefix}{document_id}")
        metadata.setdefault("revision", "etl")
        return cls(
            chunk_id=chunk_id,
            document_id=document_id,
            content=str(row.get("content", "")),
            metadata=metadata,
            title=str(metadata.get("title") or document_id),
            source_uri=str(metadata["provenance"]),
            revision=str(metadata["revision"]),
            authority=metadata.get("authority", AuthorityLevel.PROPOSED.value),
            validity=metadata.get("validity", ValidityStatus.CURRENT.value),
            domain=metadata.get("domain"),
            created_at=metadata.get("created_at") or row.get("ingested_at"),
        )


@dataclass(frozen=True)
class EvidenceRef:
    """Stable claim -> chunk -> source -> revision reference."""

    chunk_id: str
    document_id: str
    source_uri: str
    revision: str

    @property
    def citation(self) -> str:
        location = self.source_uri or f"document:{self.document_id}"
        return f"{location}#revision={self.revision or 'unknown'}"

    def to_dict(self) -> dict[str, str]:
        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "source_uri": self.source_uri,
            "revision": self.revision,
            "citation": self.citation,
        }


@dataclass(frozen=True)
class MetadataFilter:
    """Governance filters applied before any ranking algorithm."""

    minimum_authority: AuthorityLevel | str = AuthorityLevel.PROPOSED
    allowed_domains: tuple[str, ...] = ()
    required_classifications: tuple[str, ...] = ()
    created_after: Optional[str] = None
    include_superseded: bool = False
    require_provenance: bool = True

    def allows(self, chunk: RetrievalChunk) -> bool:
        if chunk.validity is ValidityStatus.INVALID:
            return False
        if chunk.validity is ValidityStatus.SUPERSEDED and not self.include_superseded:
            return False
        if chunk.authority is AuthorityLevel.DEPRECATED:
            return False
        if _AUTHORITY_RANK[chunk.authority] < _AUTHORITY_RANK[_coerce_authority(self.minimum_authority)]:
            return False
        if self.require_provenance and not chunk.provenance_complete:
            return False
        if self.allowed_domains:
            if not chunk.domain or chunk.domain not in self.allowed_domains:
                return False
        if self.created_after and (not chunk.created_at or chunk.created_at < self.created_after):
            return False
        if self.required_classifications:
            raw = chunk.metadata.get("classification", chunk.metadata.get("classifications", ()))
            classifications = {str(item).upper() for item in (raw if isinstance(raw, (list, tuple, set)) else [raw])}
            if not set(self.required_classifications).issubset(classifications):
                return False
        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "minimum_authority": _coerce_authority(self.minimum_authority).value,
            "allowed_domains": list(self.allowed_domains),
            "required_classifications": list(self.required_classifications),
            "created_after": self.created_after,
            "include_superseded": self.include_superseded,
            "require_provenance": self.require_provenance,
        }


@dataclass(frozen=True)
class RetrievalHit:
    """Ranked chunk with both component scores and its evidence reference."""

    rank: int
    chunk: RetrievalChunk
    score: float
    lexical_score: float
    semantic_score: float
    evidence: EvidenceRef

    def to_dict(self) -> dict[str, Any]:
        return {
            "rank": self.rank,
            "chunk_id": self.chunk.chunk_id,
            "document_id": self.chunk.document_id,
            "score": round(self.score, 8),
            "lexical_score": round(self.lexical_score, 8),
            "semantic_score": round(self.semantic_score, 8),
            "evidence": self.evidence.to_dict(),
        }


@dataclass(frozen=True)
class RetrievalResponse:
    """Complete retrieval receipt, ready for context assembly or audit."""

    query: str
    intent: QueryIntent
    mode: RetrievalMode
    hits: tuple[RetrievalHit, ...]
    eligible_count: int
    filtered_count: int
    reranked: bool
    pipeline: tuple[str, ...]
    metadata_filter: MetadataFilter

    def assemble_context(self, max_chars: int = 6000) -> str:
        if max_chars <= 0:
            raise ValueError("max_chars debe ser positivo")
        blocks: list[str] = []
        for hit in self.hits:
            block = (
                f"[{hit.rank}] {hit.chunk.content.strip()}\n"
                f"Evidence: {hit.evidence.citation}\n"
            )
            separator_size = len(blocks) if blocks else 0
            if sum(len(item) for item in blocks) + separator_size + len(block) > max_chars:
                break
            blocks.append(block)
        return "\n".join(blocks)

    @property
    def citations(self) -> tuple[str, ...]:
        return tuple(hit.evidence.citation for hit in self.hits)

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "intent": self.intent.value,
            "mode": self.mode.value,
            "hits": [hit.to_dict() for hit in self.hits],
            "eligible_count": self.eligible_count,
            "filtered_count": self.filtered_count,
            "reranked": self.reranked,
            "pipeline": list(self.pipeline),
            "metadata_filter": self.metadata_filter.to_dict(),
            "citations": list(self.citations),
        }


@dataclass(frozen=True)
class HashEmbedding:
    """Offline feature-hash embedding used as a deterministic semantic baseline."""

    dimensions: int = 128

    def __post_init__(self) -> None:
        if self.dimensions < 16:
            raise ValueError("dimensions debe ser >= 16")

    def embed(self, text: str) -> tuple[float, ...]:
        vector = [0.0] * self.dimensions
        features = [(f"token:{token}", 1.0) for token in _tokens(text)]
        features.extend((f"char:{feature}", 0.35) for feature in _char_features(text))
        for feature, weight in features:
            digest = hashlib.sha256(feature.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] & 1 else -1.0
            vector[index] += sign * weight
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return tuple(vector)
        return tuple(value / norm for value in vector)


def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
    return sum(a * b for a, b in zip(left, right))


def _bm25_scores(chunks: Sequence[RetrievalChunk], query: str) -> dict[str, float]:
    query_tokens = _tokens(query)
    document_tokens = {chunk.chunk_id: _tokens(chunk.content) for chunk in chunks}
    if not query_tokens or not chunks:
        return {chunk.chunk_id: 0.0 for chunk in chunks}
    document_frequency = Counter(
        token
        for tokens in document_tokens.values()
        for token in set(tokens)
    )
    average_length = sum(len(tokens) for tokens in document_tokens.values()) / len(chunks)
    average_length = max(average_length, 1.0)
    total_documents = len(chunks)
    scores: dict[str, float] = {}
    for chunk in chunks:
        tokens = document_tokens[chunk.chunk_id]
        counts = Counter(tokens)
        length = len(tokens)
        score = 0.0
        for token in query_tokens:
            if not counts[token]:
                continue
            df = document_frequency[token]
            idf = math.log(1.0 + (total_documents - df + 0.5) / (df + 0.5))
            term_frequency = counts[token]
            denominator = term_frequency + 1.5 * (0.25 + 0.75 * length / average_length)
            score += idf * (term_frequency * 2.5 / denominator)
        normalized_content = _normalize(chunk.content)
        normalized_query = _normalize(query)
        if normalized_query and normalized_query in normalized_content:
            score += 0.75
        scores[chunk.chunk_id] = score
    return scores


def _semantic_scores(
    chunks: Sequence[RetrievalChunk],
    query: str,
    embedder: HashEmbedding,
) -> dict[str, float]:
    query_vector = embedder.embed(query)
    return {
        chunk.chunk_id: _cosine(query_vector, embedder.embed(chunk.content))
        for chunk in chunks
    }


def _rank(scores: Mapping[str, float]) -> list[str]:
    return [
        chunk_id
        for chunk_id, _ in sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    ]


def _normalize_scores(scores: Mapping[str, float]) -> dict[str, float]:
    if not scores:
        return {}
    minimum = min(scores.values())
    maximum = max(scores.values())
    if math.isclose(minimum, maximum):
        return {key: (1.0 if maximum > 0 else 0.0) for key in scores}
    return {key: (value - minimum) / (maximum - minimum) for key, value in scores.items()}


def _fuse_scores(
    lexical: Mapping[str, float],
    semantic: Mapping[str, float],
    *,
    semantic_weight: float,
) -> dict[str, float]:
    lexical_normalized = _normalize_scores(lexical)
    semantic_normalized = _normalize_scores(semantic)
    lexical_rank = {item: index for index, item in enumerate(_rank(lexical), start=1)}
    semantic_rank = {item: index for index, item in enumerate(_rank(semantic), start=1)}
    fused: dict[str, float] = {}
    for chunk_id in lexical:
        reciprocal_rank = (1.0 / (60 + lexical_rank[chunk_id])) + (
            1.0 / (60 + semantic_rank[chunk_id])
        )
        fused[chunk_id] = (
            (1.0 - semantic_weight) * lexical_normalized[chunk_id]
            + semantic_weight * semantic_normalized[chunk_id]
            + 0.05 * reciprocal_rank
        )
    return fused


def _rerank_score(
    query: str,
    chunk: RetrievalChunk,
    base_score: float,
    lexical_score: float,
) -> float:
    query_tokens = set(_tokens(query))
    content_tokens = set(_tokens(chunk.content))
    overlap = len(query_tokens & content_tokens) / max(len(query_tokens), 1)
    title_tokens = set(_tokens(chunk.title))
    title_overlap = len(query_tokens & title_tokens) / max(len(query_tokens), 1)
    phrase_boost = 1.0 if _normalize(query) in _normalize(chunk.content) else 0.0
    return base_score + 0.12 * _normalize_score(lexical_score) + 0.05 * overlap + 0.04 * title_overlap + 0.15 * phrase_boost


def _normalize_score(score: float) -> float:
    return score / (score + 1.0) if score > 0 else 0.0


class GovernedRAG:
    """Offline governed retriever over L2/L3 chunks."""

    def __init__(
        self,
        chunks: Iterable[RetrievalChunk],
        *,
        policy: Optional[MetadataFilter] = None,
        embedder: Optional[HashEmbedding] = None,
        semantic_weight: float = 0.45,
        candidate_k: int = 50,
    ) -> None:
        materialized = tuple(chunks)
        identifiers = [chunk.chunk_id for chunk in materialized]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("chunk_id debe ser único en el índice")
        if not 0.0 <= semantic_weight <= 1.0:
            raise ValueError("semantic_weight debe estar entre 0 y 1")
        if candidate_k <= 0:
            raise ValueError("candidate_k debe ser positivo")
        self.chunks = materialized
        self.policy = policy or MetadataFilter()
        self.embedder = embedder or HashEmbedding()
        self.semantic_weight = semantic_weight
        self.candidate_k = candidate_k

    @classmethod
    def from_sqlite(
        cls,
        db_path: str | Path,
        **kwargs: Any,
    ) -> "GovernedRAG":
        return cls(load_sqlite_chunks(db_path), **kwargs)

    @staticmethod
    def classify_intent(query: str) -> QueryIntent:
        normalized = _normalize(query)
        action_terms = {
            "autoriza",
            "autorizar",
            "commit",
            "delete",
            "ejecuta",
            "ejecutar",
            "merge",
            "push",
            "run",
            "write",
        }
        reasoning_terms = {
            "compare",
            "compara",
            "como",
            "how",
            "por que",
            "why",
        }
        tokens = set(_tokens(normalized))
        if tokens & action_terms:
            return QueryIntent.ACTION
        if any(term in normalized for term in reasoning_terms):
            return QueryIntent.REASONING
        return QueryIntent.RETRIEVAL

    def retrieve(
        self,
        query: str,
        *,
        mode: RetrievalMode | str = RetrievalMode.HYBRID,
        top_k: int = 10,
        metadata_filter: Optional[MetadataFilter] = None,
        rerank: bool = True,
    ) -> RetrievalResponse:
        if not query.strip():
            raise ValueError("query no puede estar vacío")
        if top_k <= 0:
            raise ValueError("top_k debe ser positivo")
        mode = RetrievalMode(mode)
        active_filter = metadata_filter or self.policy
        eligible = tuple(chunk for chunk in self.chunks if active_filter.allows(chunk))
        filtered_count = len(self.chunks) - len(eligible)
        pipeline = ["intent_classification", "metadata_filters"]
        lexical_scores = _bm25_scores(eligible, query)
        semantic_scores = _semantic_scores(eligible, query, self.embedder)
        if mode is RetrievalMode.LEXICAL:
            scores = lexical_scores
            pipeline.append("lexical_bm25")
        elif mode is RetrievalMode.SEMANTIC:
            scores = semantic_scores
            pipeline.append("semantic_embedding")
        else:
            scores = _fuse_scores(
                lexical_scores,
                semantic_scores,
                semantic_weight=self.semantic_weight,
            )
            pipeline.extend(("lexical_bm25", "semantic_embedding", "hybrid_rrf_fusion"))
        candidate_ids = _rank(scores)[: max(top_k, self.candidate_k)]
        if rerank:
            pipeline.append("deterministic_reranker")
            reranked_scores = {
                chunk_id: _rerank_score(
                    query,
                    next(chunk for chunk in eligible if chunk.chunk_id == chunk_id),
                    scores[chunk_id],
                    lexical_scores[chunk_id],
                )
                for chunk_id in candidate_ids
            }
            candidate_ids = _rank(reranked_scores)
            scores = {**scores, **reranked_scores}
        pipeline.extend(("authority_validity_gate", "evidence_context_ready"))
        by_id = {chunk.chunk_id: chunk for chunk in eligible}
        hits = tuple(
            RetrievalHit(
                rank=index,
                chunk=by_id[chunk_id],
                score=scores[chunk_id],
                lexical_score=lexical_scores[chunk_id],
                semantic_score=semantic_scores[chunk_id],
                evidence=EvidenceRef(
                    chunk_id=by_id[chunk_id].chunk_id,
                    document_id=by_id[chunk_id].document_id,
                    source_uri=by_id[chunk_id].source_uri,
                    revision=by_id[chunk_id].revision,
                ),
            )
            for index, chunk_id in enumerate(candidate_ids[:top_k], start=1)
        )
        return RetrievalResponse(
            query=query,
            intent=self.classify_intent(query),
            mode=mode,
            hits=hits,
            eligible_count=len(eligible),
            filtered_count=filtered_count,
            reranked=rerank,
            pipeline=tuple(pipeline),
            metadata_filter=active_filter,
        )


def load_sqlite_chunks(db_path: str | Path) -> list[RetrievalChunk]:
    """Load L2 chunks as evidence-bearing retrieval records."""

    path = Path(db_path)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(
            """
            SELECT id, document_id, content, metadata_json, ingested_at
            FROM chunks
            ORDER BY document_id, chunk_index, id
            """
        ).fetchall()
    finally:
        connection.close()
    return [RetrievalChunk.from_etl_row(dict(row)) for row in rows]


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
    "ValidityStatus",
    "load_sqlite_chunks",
]
