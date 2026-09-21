"""Governed, deterministic ontology induction for the Agentic Data Lab.

The pipeline is deliberately split into three stages:

1. ``MetadataGenerator`` extracts document metadata and known concepts.
2. ``RelationExtractor`` proposes only explicitly stated relations.
3. ``OntologyValidator`` accepts proposals into a ``KnowledgeGraph`` only
   after endpoint, confidence, duplicate, and cycle checks pass.

There is no LLM call in this module. An LLM may provide proposals later, but
the proposal/validation boundary remains the same.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, replace
from enum import Enum
from pathlib import Path
from typing import Iterable, Mapping, Optional, Sequence

from .ontology import KnowledgeGraph, OntologyRelation, RelationType
from .schema import (
    AuthorityLevel,
    ClassificationTag,
    KnowledgeAsset,
    Source,
)


class ProposalStatus(Enum):
    """Lifecycle state of a relation proposal."""

    PROPOSED = "PROPOSED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class MetadataRecord:
    """Document source plus the asset generated from its metadata."""

    source: Source
    asset: KnowledgeAsset


@dataclass
class RelationProposal:
    """A candidate relation with evidence, not yet an accepted graph edge."""

    proposal_id: str
    relation: OntologyRelation
    evidence_ref: str
    proposed_by: str = "rule_based_relation_extractor"
    status: ProposalStatus = ProposalStatus.PROPOSED
    rejection_reason: Optional[str] = None


@dataclass(frozen=True)
class OntologyProposal:
    """Metadata graph plus relation proposals awaiting validation."""

    graph: KnowledgeGraph
    relation_proposals: Sequence[RelationProposal]
    document_uris: Sequence[str]


@dataclass(frozen=True)
class OntologyValidationReport:
    """Accepted and rejected proposals produced by the validator."""

    accepted: Sequence[RelationProposal]
    rejected: Sequence[RelationProposal]

    @property
    def is_valid(self) -> bool:
        """True when every proposal passed validation."""
        return not self.rejected


class MetadataGenerator:
    """Extract deterministic metadata and governed domain concepts."""

    CONCEPT_CATALOG: Mapping[str, tuple[str, Sequence[str]]] = {
        "Agent": ("CONCEPT", ("Agent", "Agente")),
        "Contract": ("CONTRACT", ("Contract", "Contrato")),
        "Provider": ("CONCEPT", ("Provider", "Proveedor")),
        "Permit": ("PERMIT", ("Permit", "Permiso")),
        "Execution": ("EXECUTION", ("Execution", "Ejecución", "Ejecucion")),
        "Evidence": ("EVIDENCE", ("Evidence", "Evidencia")),
        "Component": ("COMPONENT", ("Component", "Componente")),
        "Model": ("MODEL", ("Model", "Modelo")),
        "ExecutionGateway": ("COMPONENT", ("ExecutionGateway",)),
        "AuthorizationBoundary": ("COMPONENT", ("AuthorizationBoundary",)),
        "KnowledgeAsset": ("CONCEPT", ("KnowledgeAsset",)),
        "KnowledgeChunk": ("CONCEPT", ("KnowledgeChunk",)),
        "Source": ("CONCEPT", ("Source", "Fuente")),
        "Revision": ("CONCEPT", ("Revision", "Revisión", "Revision")),
    }

    CLASSIFICATION_KEYWORDS: Mapping[str, ClassificationTag] = {
        "architecture": ClassificationTag.ARCHITECTURE,
        "contract": ClassificationTag.CONTRACT,
        "evidence": ClassificationTag.EVIDENCE,
        "procedure": ClassificationTag.PROCEDURE,
        "decision": ClassificationTag.DECISION,
        "learning": ClassificationTag.LEARNING,
        "requirement": ClassificationTag.REQUIREMENT,
        "test": ClassificationTag.TEST,
    }

    def extract_document(
        self,
        source_uri: str,
        content: str,
        source_type: str = "FILE",
    ) -> MetadataRecord:
        """Create stable source and document asset metadata."""
        identity = hashlib.sha256(f"{source_uri}\0{content}".encode("utf-8")).hexdigest()
        source_id = f"source_{identity[:12]}"
        asset_id = f"asset_{identity[:12]}"
        version = self._extract_version(content)
        authority = self._extract_authority(content)
        classification = self._extract_classification(content)
        title = self._extract_title(source_uri, content)
        asset_type = self._extract_asset_type(content)

        source = Source(
            source_id=source_id,
            uri=source_uri,
            source_type=source_type,
            metadata={"content_hash": hashlib.sha256(content.encode("utf-8")).hexdigest()},
        )
        asset = KnowledgeAsset(
            asset_id=asset_id,
            title=title,
            description=f"Document asset generated from {source_uri}",
            asset_type=asset_type,
            source_id=source_id,
            version=version,
            authority=authority,
            classification=classification,
            metadata={
                "provenance": source_uri,
                "content_hash": source.metadata["content_hash"],
                "generator": "metadata_generator",
            },
        )
        return MetadataRecord(source=source, asset=asset)

    def extract_concepts(self, content: str, source_id: str) -> list[KnowledgeAsset]:
        """Propose known domain concepts explicitly present in the content."""
        concepts: list[KnowledgeAsset] = []
        for label, (asset_type, aliases) in self.CONCEPT_CATALOG.items():
            matched_aliases = [
                alias
                for alias in aliases
                if re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", content, re.IGNORECASE)
            ]
            if not matched_aliases:
                continue
            concept_id = f"concept_{self._slug(label)}"
            classification = self._concept_classification(label, asset_type)
            concepts.append(
                KnowledgeAsset(
                    asset_id=concept_id,
                    title=label,
                    description=f"Domain concept proposed from documentation: {label}",
                    asset_type=asset_type,
                    source_id=source_id,
                    authority=AuthorityLevel.PROPOSED,
                    classification=classification,
                    metadata={
                        "concept_name": label,
                        "aliases": matched_aliases,
                        "generator": "metadata_generator",
                    },
                )
            )
        return concepts

    @staticmethod
    def _extract_title(source_uri: str, content: str) -> str:
        heading = re.search(r"(?m)^\s*#\s+(.+?)\s*$", content)
        return heading.group(1).strip() if heading else Path(source_uri).stem

    @staticmethod
    def _extract_version(content: str) -> str:
        match = re.search(
            r"(?i)\b(?:version|release)\s*[:=]?\s*v?(\d+(?:\.\d+){1,2})\b",
            content,
        )
        if not match:
            match = re.search(r"(?i)\bv(\d+(?:\.\d+){1,2})\b", content)
        return match.group(1) if match else "1.0.0"

    @staticmethod
    def _extract_asset_type(content: str) -> str:
        match = re.search(
            r"(?i)^\s*TYPE\s*[:=]\s*([A-Z][A-Z0-9_-]*)\s*$",
            content,
            re.MULTILINE,
        )
        return match.group(1).upper() if match else "DOCUMENT"

    @staticmethod
    def _extract_authority(content: str) -> AuthorityLevel:
        explicit = content.upper()
        if "ACTIVE_CANON" in explicit or re.search(
            r"(?i)\b(?:authority|status)\s*[:=]\s*CANONICAL\b", content
        ):
            return AuthorityLevel.CANONICAL
        if re.search(r"(?i)\b(?:authority|status)\s*[:=]\s*VERIFIED\b", content):
            return AuthorityLevel.VERIFIED
        return AuthorityLevel.PROPOSED

    def _extract_classification(self, content: str) -> list[ClassificationTag]:
        lowered = content.lower()
        return [
            tag
            for keyword, tag in self.CLASSIFICATION_KEYWORDS.items()
            if keyword in lowered
        ]

    @staticmethod
    def _concept_classification(label: str, asset_type: str) -> list[ClassificationTag]:
        if asset_type == "CONTRACT" or label == "Contract":
            return [ClassificationTag.CONTRACT]
        if asset_type == "EVIDENCE" or label == "Evidence":
            return [ClassificationTag.EVIDENCE]
        if asset_type == "COMPONENT":
            return [ClassificationTag.ARCHITECTURE]
        if asset_type == "PERMIT" or label == "Permit":
            return [ClassificationTag.PROCEDURE]
        return []

    @staticmethod
    def _slug(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


class RelationExtractor:
    """Extract explicit relation statements as proposals."""

    RELATION_PATTERNS: Sequence[tuple[RelationType, Sequence[str]]] = (
        (RelationType.DERIVED_FROM, (r"DERIVED[_ ]FROM", r"DERIVA\s+DE")),
        (RelationType.SUPERSEDES, (r"SUPERSEDES", r"SUPERA\s+A")),
        (RelationType.IMPLEMENTS, (r"IMPLEMENTS", r"IMPLEMENTA")),
        (RelationType.AUTHORIZES, (r"AUTHORIZES", r"AUTORIZA")),
        (RelationType.GENERATES, (r"GENERATES", r"GENERA")),
        (RelationType.SERVES, (r"SERVES", r"SIRVE")),
        (RelationType.REQUIRES, (r"REQUIRES", r"REQUIERE")),
        (RelationType.VALIDATES, (r"VALIDATES", r"VALIDA")),
        (RelationType.REFERENCES, (r"REFERENCES", r"REFERENCIA")),
        (RelationType.CONTRADICTS, (r"CONTRADICTS", r"CONTRADICE")),
        (RelationType.GENERATED_BY, (r"GENERATED[_ ]BY",)),
    )

    def propose(
        self,
        content: str,
        entities: Iterable[KnowledgeAsset],
    ) -> list[RelationProposal]:
        entity_aliases = self._entity_aliases(entities)
        proposals: list[RelationProposal] = []
        seen: set[tuple[str, RelationType, str]] = set()

        for source_alias, source in entity_aliases.items():
            for target_alias, target in entity_aliases.items():
                if source.asset_id == target.asset_id:
                    continue
                for relation_type, verbs in self.RELATION_PATTERNS:
                    for verb in verbs:
                        pattern = re.compile(
                            rf"(?<!\w){re.escape(source_alias)}\s+{verb}"
                            rf"\s+(?:A\s+)?{re.escape(target_alias)}(?!\w)",
                            re.IGNORECASE,
                        )
                        match = pattern.search(content)
                        if not match:
                            continue
                        key = (source.asset_id, relation_type, target.asset_id)
                        if key in seen:
                            continue
                        seen.add(key)
                        evidence = self._evidence_line(content, match.start())
                        proposal_key = hashlib.sha256(
                            f"{source.asset_id}|{relation_type.value}|{target.asset_id}|{evidence}".encode(
                                "utf-8"
                            )
                        ).hexdigest()[:12]
                        proposals.append(
                            RelationProposal(
                                proposal_id=f"proposal_{proposal_key}",
                                relation=OntologyRelation(
                                    relation_id=f"relation_{proposal_key}",
                                    relation_type=relation_type,
                                    source_id=source.asset_id,
                                    target_id=target.asset_id,
                                    confidence=0.95,
                                    metadata={"evidence": evidence},
                                ),
                                evidence_ref=evidence,
                            )
                        )
        return proposals

    @staticmethod
    def _entity_aliases(entities: Iterable[KnowledgeAsset]) -> dict[str, KnowledgeAsset]:
        aliases: dict[str, KnowledgeAsset] = {}
        ordered = sorted(
            entities,
            key=lambda entity: (
                not entity.asset_id.startswith("concept_"),
                -len(entity.title),
                entity.asset_id,
            ),
        )
        for entity in ordered:
            names = {
                entity.title,
                entity.asset_id,
                entity.metadata.get("concept_name", ""),
            }
            names.update(entity.metadata.get("aliases", []))
            for name in names:
                if name:
                    aliases.setdefault(name, entity)
        return aliases

    @staticmethod
    def _evidence_line(content: str, offset: int) -> str:
        start = content.rfind("\n", 0, offset) + 1
        end = content.find("\n", offset)
        return content[start:] if end == -1 else content[start:end]


class OntologyValidator:
    """Validate and accept relation proposals into the canonical graph."""

    def __init__(self, minimum_confidence: float = 0.8):
        self.minimum_confidence = minimum_confidence

    def validate(self, proposal: OntologyProposal) -> OntologyValidationReport:
        accepted: list[RelationProposal] = []
        rejected: list[RelationProposal] = []
        seen: set[tuple[str, RelationType, str]] = set()
        known_ids = set(proposal.graph.assets) | set(proposal.graph.chunks)

        for candidate in proposal.relation_proposals:
            relation = candidate.relation
            reasons: list[str] = []
            key = (relation.source_id, relation.relation_type, relation.target_id)
            if relation.source_id not in known_ids:
                reasons.append(f"source {relation.source_id} not found")
            if relation.target_id not in known_ids:
                reasons.append(f"target {relation.target_id} not found")
            if not isinstance(relation.relation_type, RelationType):
                reasons.append("relation type is not allowed")
            if relation.confidence < self.minimum_confidence:
                reasons.append(
                    f"confidence {relation.confidence:.2f} below "
                    f"minimum {self.minimum_confidence:.2f}"
                )
            if key in seen:
                reasons.append("duplicate relation")

            if not reasons and relation.relation_type == RelationType.DERIVED_FROM:
                candidate_graph = self._graph_with(
                    proposal.graph,
                    [item.relation for item in accepted] + [relation],
                )
                if any("Cycle detected" in error for error in candidate_graph.validate_integrity()):
                    reasons.append("DERIVED_FROM cycle detected")

            if reasons:
                rejected.append(
                    replace(
                        candidate,
                        status=ProposalStatus.REJECTED,
                        rejection_reason="; ".join(reasons),
                    )
                )
                continue

            seen.add(key)
            accepted.append(replace(candidate, status=ProposalStatus.ACCEPTED))

        return OntologyValidationReport(accepted=accepted, rejected=rejected)

    def accept(
        self,
        proposal: OntologyProposal,
        report: Optional[OntologyValidationReport] = None,
    ) -> KnowledgeGraph:
        """Build an accepted graph; proposals never mutate the input graph."""
        report = report or self.validate(proposal)
        graph = self._graph_with(proposal.graph, [item.relation for item in report.accepted])
        integrity_errors = graph.validate_integrity()
        if integrity_errors:
            raise ValueError("Accepted ontology is invalid: " + "; ".join(integrity_errors))
        return graph

    @staticmethod
    def _graph_with(graph: KnowledgeGraph, relations: Sequence[OntologyRelation]) -> KnowledgeGraph:
        return KnowledgeGraph(
            assets=dict(graph.assets),
            chunks=dict(graph.chunks),
            relations=list(relations),
            sources=dict(graph.sources),
        )


class OntologyGenerator:
    """Compose metadata extraction, relation proposals, and validation."""

    def __init__(
        self,
        metadata_generator: Optional[MetadataGenerator] = None,
        relation_extractor: Optional[RelationExtractor] = None,
    ):
        self.metadata_generator = metadata_generator or MetadataGenerator()
        self.relation_extractor = relation_extractor or RelationExtractor()

    def generate(self, documents: Iterable[tuple[str, str]]) -> OntologyProposal:
        graph = KnowledgeGraph()
        relation_proposals: list[RelationProposal] = []
        document_uris: list[str] = []

        for source_uri, content in documents:
            document_uris.append(source_uri)
            metadata = self.metadata_generator.extract_document(source_uri, content)
            graph.sources[metadata.source.source_id] = metadata.source
            graph.add_asset(metadata.asset)
            for concept in self.metadata_generator.extract_concepts(
                content, metadata.source.source_id
            ):
                graph.assets.setdefault(concept.asset_id, concept)

            relation_proposals.extend(
                self.relation_extractor.propose(content, graph.assets.values())
            )

        return OntologyProposal(
            graph=graph,
            relation_proposals=relation_proposals,
            document_uris=tuple(document_uris),
        )

    def generate_from_files(self, paths: Iterable[str | Path]) -> OntologyProposal:
        """Generate proposals from UTF-8 Markdown/text files."""
        documents = []
        for raw_path in paths:
            path = Path(raw_path)
            documents.append((str(path), path.read_text(encoding="utf-8")))
        return self.generate(documents)


__all__ = [
    "MetadataGenerator",
    "MetadataRecord",
    "OntologyGenerator",
    "OntologyProposal",
    "OntologyValidationReport",
    "OntologyValidator",
    "ProposalStatus",
    "RelationExtractor",
    "RelationProposal",
]
