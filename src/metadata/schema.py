"""L3 entity schema for governed knowledge metadata."""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
import hashlib


class AuthorityLevel(Enum):
    """Niveles de autoridad para gobernanza."""

    CANONICAL = "CANONICAL"
    VERIFIED = "VERIFIED"
    PROPOSED = "PROPOSED"
    EXPERIMENTAL = "EXPERIMENTAL"
    DEPRECATED = "DEPRECATED"


class ClassificationTag(Enum):
    """Tags de clasificación para filtering."""

    ARCHITECTURE = "ARCHITECTURE"
    CONTRACT = "CONTRACT"
    EVIDENCE = "EVIDENCE"
    PROCEDURE = "PROCEDURE"
    DECISION = "DECISION"
    LEARNING = "LEARNING"
    REQUIREMENT = "REQUIREMENT"
    TEST = "TEST"


class ValidityStatus(Enum):
    """Estado de validez temporal o gobernada de un asset."""

    CURRENT = "CURRENT"
    SUPERSEDED = "SUPERSEDED"
    INVALID = "INVALID"
    UNKNOWN = "UNKNOWN"


@dataclass
class Source:
    """Fuente original de conocimiento."""

    source_id: str
    uri: str
    source_type: str
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict = field(default_factory=dict)

    def content_hash(self, content: str) -> str:
        """SHA-256 del contenido para idempotencia."""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()


@dataclass
class KnowledgeAsset:
    """Activo de conocimiento atómico."""

    asset_id: str
    title: str
    description: str
    asset_type: str
    source_id: str
    version: str = "1.0.0"
    authority: AuthorityLevel = AuthorityLevel.PROPOSED
    classification: List[ClassificationTag] = field(default_factory=list)
    validity: ValidityStatus = ValidityStatus.CURRENT
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: Optional[str] = None
    superseded_by: Optional[str] = None
    metadata: dict = field(default_factory=dict)

    def mark_superseded(self, new_asset_id: str):
        """Marcar como superseded por nueva versión."""
        self.superseded_by = new_asset_id
        self.validity = ValidityStatus.SUPERSEDED
        self.updated_at = datetime.now(timezone.utc).isoformat()


@dataclass
class KnowledgeChunk:
    """Chunk de documento con metadata semántica."""

    chunk_id: str
    document_id: str
    chunk_index: int
    content: str
    start_offset: int
    end_offset: int
    word_count: int
    embedding_ref: Optional[str] = None
    keywords: List[str] = field(default_factory=list)
    entities: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        """Convertir a dict para serialización."""
        return asdict(self)


@dataclass
class Revision:
    """Registro de revisión para lineage tracking."""

    revision_id: str
    asset_id: str
    revision_number: str
    change_summary: str
    changed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    changed_by: Optional[str] = None
    evidence_refs: List[str] = field(default_factory=list)


__all__ = [
    "AuthorityLevel",
    "ClassificationTag",
    "KnowledgeAsset",
    "KnowledgeChunk",
    "Revision",
    "Source",
    "ValidityStatus",
]
