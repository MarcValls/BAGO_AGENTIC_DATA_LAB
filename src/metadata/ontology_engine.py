"""L10 governed ontology reasoning over a local RDF graph.

The existing L3 ontology model is intentionally kept as the domain model.  This
module adds a small, dependency-free RDF/SPARQL boundary on top of it so the
lab can demonstrate graph reasoning without a cloud account or a triplestore.

The SPARQL implementation is deliberately bounded: ``SELECT`` queries with
triple-pattern joins, ``FILTER regex``/equality and ``LIMIT`` are supported.
The supported subset is surfaced in the receipt and documentation rather than
being presented as a complete W3C query engine.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, Mapping, Optional, Sequence

from .ontology import KnowledgeGraph, OntologyRelation, RelationType
from .schema import KnowledgeAsset, KnowledgeChunk, Source


DEFAULT_BASE_IRI = "https://bago.local/ontology/"
RDF_NS = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
RDFS_NS = "http://www.w3.org/2000/01/rdf-schema#"
RDF_TYPE = f"{RDF_NS}type"
RDFS_LABEL = f"{RDFS_NS}label"

RELATION_PREDICATES: Mapping[RelationType, str] = {
    RelationType.DERIVED_FROM: "derivedFrom",
    RelationType.SUPERSEDES: "supersedes",
    RelationType.REFERENCES: "references",
    RelationType.VALIDATES: "validates",
    RelationType.CONTRADICTS: "contradicts",
    RelationType.GENERATED_BY: "generatedBy",
    RelationType.AUTHORIZES: "authorizes",
    RelationType.GENERATES: "generates",
    RelationType.SERVES: "serves",
    RelationType.REQUIRES: "requires",
    RelationType.BELONGS_TO: "belongsTo",
    RelationType.IMPLEMENTS: "implements",
    RelationType.CONFLICTS_WITH: "conflictsWith",
}
PREDICATE_RELATIONS = {value: key for key, value in RELATION_PREDICATES.items()}
TRANSITIVE_PREDICATES = frozenset({"derivedFrom", "supersedes", "requires"})
SYMMETRIC_PREDICATES = frozenset({"contradicts", "conflictsWith"})
INVERSE_PREDICATES: Mapping[str, str] = {
    "supersedes": "supersededBy",
    "validates": "validatedBy",
    "derivedFrom": "hasDerivedAsset",
    "requires": "requiredBy",
    "implements": "implementedBy",
    "authorizes": "authorizedBy",
    "generates": "generatedBy",
}

_TOKEN_PATTERN = re.compile(r"[\w]+", re.UNICODE)
_STOPWORDS = {
    "a", "al", "and", "are", "como", "con", "de", "del", "el", "en",
    "es", "for", "from", "la", "las", "los", "of", "para", "por",
    "que", "the", "to", "un", "una", "with", "y", "what", "which",
}


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


def _iri(value: str, base_iri: str = DEFAULT_BASE_IRI) -> str:
    value = str(value)
    if value.startswith(("http://", "https://", "urn:")):
        return value
    return f"{base_iri.rstrip('/')}/{value.lstrip('/')}"


def _local_id(value: str, base_iri: str = DEFAULT_BASE_IRI) -> str:
    prefix = base_iri.rstrip("/") + "/"
    return value[len(prefix):] if value.startswith(prefix) else value.rsplit("/", 1)[-1]


def _escape_literal(value: str) -> str:
    return json.dumps(str(value), ensure_ascii=False)


@dataclass(frozen=True)
class RDFTriple:
    """An RDF triple plus the evidence that supports its assertion."""

    subject: str
    predicate: str
    object: str
    object_is_literal: bool = False
    evidence_refs: tuple[str, ...] = ()
    inferred: bool = False
    inference_rule: str = ""

    @property
    def key(self) -> tuple[str, str, str, bool]:
        return (self.subject, self.predicate, self.object, self.object_is_literal)

    def to_dict(self) -> dict[str, Any]:
        return {
            "subject": self.subject,
            "predicate": self.predicate,
            "object": self.object,
            "object_is_literal": self.object_is_literal,
            "evidence_refs": list(self.evidence_refs),
            "inferred": self.inferred,
            "inference_rule": self.inference_rule,
        }


class RDFGraph:
    """Small deterministic in-memory RDF graph used by the local engine."""

    def __init__(self, triples: Iterable[RDFTriple] = ()) -> None:
        self._triples: dict[tuple[str, str, str, bool], RDFTriple] = {}
        for triple in triples:
            self.add(triple)

    def add(self, triple: RDFTriple) -> bool:
        """Add a triple, merging evidence when the assertion already exists."""

        existing = self._triples.get(triple.key)
        if existing is None:
            self._triples[triple.key] = triple
            return True
        merged_refs = tuple(sorted(set(existing.evidence_refs) | set(triple.evidence_refs)))
        preferred = existing
        if existing.inferred and not triple.inferred:
            preferred = triple
        if merged_refs != existing.evidence_refs or preferred is not existing:
            self._triples[triple.key] = RDFTriple(
                subject=preferred.subject,
                predicate=preferred.predicate,
                object=preferred.object,
                object_is_literal=preferred.object_is_literal,
                evidence_refs=merged_refs,
                inferred=preferred.inferred,
                inference_rule=preferred.inference_rule,
            )
        return False

    def extend(self, triples: Iterable[RDFTriple]) -> None:
        for triple in triples:
            self.add(triple)

    def triples(
        self,
        *,
        subject: Optional[str] = None,
        predicate: Optional[str] = None,
        object: Optional[str] = None,
    ) -> tuple[RDFTriple, ...]:
        return tuple(
            sorted(
                (
                    triple
                    for triple in self._triples.values()
                    if (subject is None or triple.subject == subject)
                    and (predicate is None or triple.predicate == predicate)
                    and (object is None or triple.object == object)
                ),
                key=lambda triple: triple.key,
            )
        )

    def __iter__(self):
        return iter(self.triples())

    def __len__(self) -> int:
        return len(self._triples)

    def to_turtle(self, *, base_iri: str = DEFAULT_BASE_IRI) -> str:
        """Serialize the graph as readable Turtle."""

        base = base_iri.rstrip("/") + "/"
        lines = [
            f"@prefix bago: <{base}> .",
            f"@prefix rdf: <{RDF_NS}> .",
            f"@prefix rdfs: <{RDFS_NS}> .",
            "",
        ]
        for triple in self.triples():
            subject = f"<{triple.subject}>"
            predicate = f"<{triple.predicate}>"
            obj = _escape_literal(triple.object) if triple.object_is_literal else f"<{triple.object}>"
            lines.append(f"{subject} {predicate} {obj} .")
        return "\n".join(lines) + "\n"


class SPARQLQueryError(ValueError):
    """Raised when a query is outside the supported local SPARQL subset."""


@dataclass(frozen=True)
class _TriplePattern:
    subject: str
    predicate: str
    object: str


@dataclass(frozen=True)
class _FilterPattern:
    variable: str
    operator: str
    value: str
    flags: str = ""


def _split_outside(text: str, delimiter: str = ".") -> list[str]:
    chunks: list[str] = []
    start = 0
    quote = ""
    angle = False
    parentheses = 0
    escaped = False
    for index, char in enumerate(text):
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = ""
            continue
        if char in {'"', "'"}:
            quote = char
        elif char == "<":
            angle = True
        elif char == ">":
            angle = False
        elif char == "(":
            parentheses += 1
        elif char == ")":
            parentheses = max(0, parentheses - 1)
        elif char == delimiter and not angle and parentheses == 0:
            chunks.append(text[start:index].strip())
            start = index + 1
    tail = text[start:].strip()
    if tail:
        chunks.append(tail)
    return chunks


def _sparql_tokens(statement: str) -> list[str]:
    return re.findall(r"<[^>]*>|\"(?:\\.|[^\"])*\"|'(?:\\.|[^'])*'|[^\s]+", statement)


def _parse_literal(token: str) -> Optional[str]:
    if len(token) < 2 or token[0] not in {'"', "'"} or token[-1] != token[0]:
        return None
    body = token[1:-1]
    return bytes(body, "utf-8").decode("unicode_escape") if "\\" in body else body


def _expand_term(token: str, prefixes: Mapping[str, str]) -> tuple[str, bool, bool]:
    """Return ``(value, is_literal, is_variable)`` for a query token."""

    token = token.strip()
    if token.startswith("?"):
        return token, False, True
    literal = _parse_literal(token)
    if literal is not None:
        return literal, True, False
    if token == "a":
        return RDF_TYPE, False, False
    if token.startswith("<") and token.endswith(">"):
        return token[1:-1], False, False
    if ":" in token:
        prefix, local = token.split(":", 1)
        if prefix in prefixes:
            return prefixes[prefix] + local, False, False
    return token, False, False


def _parse_sparql(query: str) -> tuple[dict[str, str], list[str], list[_TriplePattern], list[_FilterPattern], int]:
    prefixes = {"bago": DEFAULT_BASE_IRI, "rdf": RDF_NS, "rdfs": RDFS_NS}
    for match in re.finditer(r"(?im)^\s*PREFIX\s+([A-Za-z][\w-]*)?:\s*<([^>]+)>\s*", query):
        prefixes[match.group(1) or ""] = match.group(2)
    without_prefixes = re.sub(
        r"(?im)^\s*PREFIX\s+[A-Za-z][\w-]*:\s*<[^>]+>\s*", "", query
    ).strip()
    select_match = re.search(
        r"(?is)^SELECT\s+(DISTINCT\s+)?(.+?)\s+WHERE\s*\{", without_prefixes
    )
    if not select_match:
        raise SPARQLQueryError("Only SELECT ... WHERE queries are supported")
    distinct = bool(select_match.group(1))
    projection_text = select_match.group(2).strip()
    if projection_text == "*":
        projection: list[str] = []
    else:
        projection = re.findall(r"\?[A-Za-z_][\w-]*", projection_text)
        if not projection:
            raise SPARQLQueryError("SELECT must project variables or *")

    body_start = select_match.end()
    depth = 1
    quote = ""
    angle = False
    body_end = None
    for index in range(body_start, len(without_prefixes)):
        char = without_prefixes[index]
        if quote:
            if char == "\\":
                continue
            if char == quote:
                quote = ""
            continue
        if char in {'"', "'"}:
            quote = char
        elif char == "<":
            angle = True
        elif char == ">":
            angle = False
        elif not angle and char == "{":
            depth += 1
        elif not angle and char == "}":
            depth -= 1
            if depth == 0:
                body_end = index
                break
    if body_end is None:
        raise SPARQLQueryError("WHERE block is not closed")
    body = without_prefixes[body_start:body_end]
    tail = without_prefixes[body_end + 1:]
    limit_match = re.search(r"(?is)\bLIMIT\s+(\d+)", tail)
    limit = int(limit_match.group(1)) if limit_match else 1000
    if limit <= 0:
        raise SPARQLQueryError("LIMIT must be positive")

    patterns: list[_TriplePattern] = []
    filters: list[_FilterPattern] = []
    for statement in _split_outside(body):
        if statement.upper().startswith("FILTER"):
            regex_match = re.match(
                r'(?is)^FILTER\s+regex\s*\(\s*(?:str\s*\(\s*)?(\?[\w-]+)'
                r'\s*\)?\s*,\s*(["\'])(.*?)\2(?:\s*,\s*(["\'])i\4)?\s*\)$',
                statement,
            )
            if regex_match:
                filters.append(
                    _FilterPattern(regex_match.group(1), "regex", regex_match.group(3), "i")
                )
                continue
            equality_match = re.match(
                r"(?is)^FILTER\s*\(\s*(\?[\w-]+)\s*=\s*([^\)]+)\s*\)$", statement
            )
            if equality_match:
                filters.append(
                    _FilterPattern(equality_match.group(1), "equals", equality_match.group(2).strip())
                )
                continue
            raise SPARQLQueryError("Supported FILTER forms are regex(...) and (?var = term)")
        tokens = _sparql_tokens(statement)
        if len(tokens) != 3:
            raise SPARQLQueryError(f"Triple pattern must contain exactly 3 terms: {statement}")
        patterns.append(_TriplePattern(*tokens))
    if not patterns:
        raise SPARQLQueryError("WHERE must contain at least one triple pattern")
    if distinct:
        projection.insert(0, "__DISTINCT__")
    return prefixes, projection, patterns, filters, limit


@dataclass(frozen=True)
class ConstraintViolation:
    code: str
    message: str
    severity: str = "ERROR"
    evidence_refs: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
            "evidence_refs": list(self.evidence_refs),
        }


@dataclass(frozen=True)
class OntologyPath:
    """A directed, evidence-bearing path returned by graph traversal."""

    nodes: tuple[str, ...]
    triples: tuple[RDFTriple, ...]

    @property
    def evidence_refs(self) -> tuple[str, ...]:
        return tuple(
            sorted({reference for triple in self.triples for reference in triple.evidence_refs})
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": list(self.nodes),
            "triples": [triple.to_dict() for triple in self.triples],
            "evidence_refs": list(self.evidence_refs),
        }


@dataclass(frozen=True)
class OntologyReceipt:
    """Receipt for a read-only local ontology reasoning run."""

    receipt_id: str
    query: str
    outcome: str
    graph_fingerprint: str
    explicit_triples: int
    inferred_triples: int
    sparql_queries: tuple[str, ...]
    paths_found: int
    contradictions_found: int
    constraints_checked: int
    evidence_refs: tuple[str, ...]
    cost_usd: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "query": self.query,
            "outcome": self.outcome,
            "graph_fingerprint": self.graph_fingerprint,
            "explicit_triples": self.explicit_triples,
            "inferred_triples": self.inferred_triples,
            "sparql_queries": list(self.sparql_queries),
            "paths_found": self.paths_found,
            "contradictions_found": self.contradictions_found,
            "constraints_checked": self.constraints_checked,
            "evidence_refs": list(self.evidence_refs),
            "cost_usd": self.cost_usd,
        }


@dataclass(frozen=True)
class OntologyReasoningResult:
    """Answer returned by the engine for the RAG -> graph reasoning step."""

    query: str
    paths: tuple[OntologyPath, ...]
    sparql_bindings: tuple[Mapping[str, str], ...]
    inferred_triples: tuple[RDFTriple, ...]
    violations: tuple[ConstraintViolation, ...]
    evidence_refs: tuple[str, ...]
    receipt: OntologyReceipt
    summary: str

    @property
    def contradictions(self) -> tuple[ConstraintViolation, ...]:
        return tuple(item for item in self.violations if item.code == "CONTRADICTION")

    def context_block(self) -> str:
        return self.summary

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "paths": [path.to_dict() for path in self.paths],
            "sparql_bindings": [dict(binding) for binding in self.sparql_bindings],
            "inferred_triples": [triple.to_dict() for triple in self.inferred_triples],
            "violations": [violation.to_dict() for violation in self.violations],
            "evidence_refs": list(self.evidence_refs),
            "receipt": self.receipt.to_dict(),
            "summary": self.summary,
        }


class OntologyEngine:
    """Materialize, query and reason over a governed local ontology."""

    def __init__(
        self,
        rdf_graph: RDFGraph,
        *,
        knowledge_graph: Optional[KnowledgeGraph] = None,
        base_iri: str = DEFAULT_BASE_IRI,
        known_nodes: Iterable[str] = (),
    ) -> None:
        self.base_iri = base_iri.rstrip("/") + "/"
        self.rdf_graph = rdf_graph
        self.knowledge_graph = knowledge_graph
        supplied_nodes = {_iri(node, self.base_iri) for node in known_nodes}
        self.known_nodes = frozenset(supplied_nodes)
        self.inferred_triples: tuple[RDFTriple, ...] = ()
        self._materialized = RDFGraph(rdf_graph)

    @classmethod
    def from_knowledge_graph(
        cls,
        graph: KnowledgeGraph,
        *,
        base_iri: str = DEFAULT_BASE_IRI,
    ) -> "OntologyEngine":
        base = base_iri.rstrip("/") + "/"
        triples: list[RDFTriple] = []
        known_nodes: set[str] = set()

        def add(
            subject: str,
            predicate: str,
            object: str,
            *,
            literal: bool = False,
            evidence_refs: Iterable[str] = (),
        ) -> None:
            triples.append(
                RDFTriple(
                    subject=_iri(subject, base),
                    predicate=predicate if predicate.startswith("http") else _iri(predicate, base),
                    object=object if literal else _iri(object, base),
                    object_is_literal=literal,
                    evidence_refs=tuple(sorted(set(evidence_refs))),
                )
            )

        def asset_evidence(asset: KnowledgeAsset, source: Optional[Source]) -> tuple[str, ...]:
            uri = str(asset.metadata.get("provenance") or (source.uri if source else ""))
            if not uri:
                return ()
            revision = str(asset.version or asset.metadata.get("revision") or "unknown")
            return (f"{uri}#revision={revision}",)

        def entity_evidence(entity_id: str) -> tuple[str, ...]:
            asset = graph.assets.get(entity_id)
            if asset is not None:
                return asset_evidence(asset, graph.sources.get(asset.source_id))
            chunk = graph.chunks.get(entity_id)
            if chunk is not None:
                return (f"chunk://{chunk.chunk_id}#document={chunk.document_id}",)
            return ()

        for source in graph.sources.values():
            known_nodes.add(_iri(source.source_id, base))
            add(source.source_id, RDF_TYPE, "Source")
            add(source.source_id, RDFS_LABEL, source.uri, literal=True)
            add(source.source_id, "uri", source.uri, literal=True)

        for asset in graph.assets.values():
            known_nodes.add(_iri(asset.asset_id, base))
            evidence = asset_evidence(asset, graph.sources.get(asset.source_id))
            add(asset.asset_id, RDF_TYPE, asset.asset_type, evidence_refs=evidence)
            add(asset.asset_id, RDFS_LABEL, asset.title, literal=True, evidence_refs=evidence)
            add(asset.asset_id, "description", asset.description, literal=True, evidence_refs=evidence)
            add(asset.asset_id, "source", asset.source_id, evidence_refs=evidence)
            add(asset.asset_id, "version", asset.version, literal=True, evidence_refs=evidence)
            add(asset.asset_id, "authority", asset.authority.value, literal=True, evidence_refs=evidence)
            add(asset.asset_id, "validity", asset.validity.value, literal=True, evidence_refs=evidence)
            add(asset.asset_id, "provenance", str(asset.metadata.get("provenance", "")), literal=True, evidence_refs=evidence)
            if asset.superseded_by:
                add(asset.superseded_by, "supersedes", asset.asset_id, evidence_refs=evidence)

        for chunk in graph.chunks.values():
            known_nodes.add(_iri(chunk.chunk_id, base))
            evidence = entity_evidence(chunk.chunk_id)
            add(chunk.chunk_id, RDF_TYPE, "KnowledgeChunk", evidence_refs=evidence)
            add(chunk.chunk_id, "documentId", chunk.document_id, literal=True, evidence_refs=evidence)
            document_node = _iri(chunk.document_id, base)
            if document_node in known_nodes:
                add(chunk.chunk_id, "derivedFrom", chunk.document_id, evidence_refs=evidence)

        for relation in graph.relations:
            predicate_name = RELATION_PREDICATES.get(relation.relation_type)
            if predicate_name is None:
                continue
            refs = set(entity_evidence(relation.source_id)) | set(entity_evidence(relation.target_id))
            raw_refs = relation.metadata.get("evidence_refs", ())
            if isinstance(raw_refs, str):
                raw_refs = (raw_refs,)
            refs.update(str(item) for item in raw_refs)
            add(relation.source_id, predicate_name, relation.target_id, evidence_refs=refs)

        engine = cls(
            RDFGraph(triples),
            knowledge_graph=graph,
            base_iri=base,
            known_nodes=known_nodes,
        )
        engine.materialize_inferences()
        return engine

    @property
    def graph(self) -> RDFGraph:
        """Return explicit plus inferred triples."""

        return self._materialized

    def materialize_inferences(self) -> tuple[RDFTriple, ...]:
        """Apply bounded inverse, symmetric and transitive rules to a fixpoint."""

        known = RDFGraph(self.rdf_graph)
        inferred: dict[tuple[str, str, str, bool], RDFTriple] = {}
        changed = True
        while changed:
            changed = False
            current = tuple(known)
            for triple in current:
                inverse = INVERSE_PREDICATES.get(_local_id(triple.predicate, self.base_iri))
                if inverse and not triple.object_is_literal:
                    candidate = RDFTriple(
                        subject=triple.object,
                        predicate=_iri(inverse, self.base_iri),
                        object=triple.subject,
                        evidence_refs=triple.evidence_refs,
                        inferred=True,
                        inference_rule=f"inverse:{_local_id(triple.predicate, self.base_iri)}",
                    )
                    if candidate.key not in {item.key for item in known}:
                        known.add(candidate)
                        inferred[candidate.key] = candidate
                        changed = True
            for predicate_name in sorted(TRANSITIVE_PREDICATES):
                predicate = _iri(predicate_name, self.base_iri)
                links = [item for item in tuple(known) if item.predicate == predicate and not item.object_is_literal]
                for left in links:
                    for right in links:
                        if left.object != right.subject or left.subject == right.object:
                            continue
                        refs = tuple(sorted(set(left.evidence_refs) | set(right.evidence_refs)))
                        candidate = RDFTriple(
                            subject=left.subject,
                            predicate=predicate,
                            object=right.object,
                            evidence_refs=refs,
                            inferred=True,
                            inference_rule=f"transitive:{predicate_name}",
                        )
                        if candidate.key not in {item.key for item in known}:
                            known.add(candidate)
                            inferred[candidate.key] = candidate
                            changed = True
            for predicate_name in sorted(SYMMETRIC_PREDICATES):
                predicate = _iri(predicate_name, self.base_iri)
                for triple in tuple(known):
                    if triple.predicate != predicate or triple.object_is_literal:
                        continue
                    candidate = RDFTriple(
                        subject=triple.object,
                        predicate=predicate,
                        object=triple.subject,
                        evidence_refs=triple.evidence_refs,
                        inferred=True,
                        inference_rule=f"symmetric:{predicate_name}",
                    )
                    if candidate.key not in {item.key for item in known}:
                        known.add(candidate)
                        inferred[candidate.key] = candidate
                        changed = True
        self.inferred_triples = tuple(sorted(inferred.values(), key=lambda item: item.key))
        self._materialized = known
        return self.inferred_triples

    def select(self, query: str) -> tuple[dict[str, str], ...]:
        """Execute the supported local SPARQL SELECT subset."""

        prefixes, projection, patterns, filters, limit = _parse_sparql(query)
        bindings: list[dict[str, str]] = [{}]
        for pattern in patterns:
            subject, subject_literal, subject_variable = _expand_term(pattern.subject, prefixes)
            predicate, predicate_literal, predicate_variable = _expand_term(pattern.predicate, prefixes)
            object, object_literal, object_variable = _expand_term(pattern.object, prefixes)
            if subject_literal or predicate_literal or object_variable and object_literal:
                raise SPARQLQueryError("Unsupported literal/predicate form in triple pattern")
            next_bindings: list[dict[str, str]] = []
            for binding in bindings:
                for triple in self.graph:
                    candidate = dict(binding)
                    if not self._match_query_term(subject, subject_variable, triple.subject, False, candidate):
                        continue
                    if not self._match_query_term(predicate, predicate_variable, triple.predicate, False, candidate):
                        continue
                    if not self._match_query_term(object, object_variable, triple.object, triple.object_is_literal, candidate):
                        continue
                    next_bindings.append(candidate)
            bindings = next_bindings
        filtered = [binding for binding in bindings if self._filters_match(binding, filters, prefixes)]
        projected: list[dict[str, str]] = []
        variables = sorted({key for binding in filtered for key in binding}) if not projection else [item[1:] for item in projection if item != "__DISTINCT__"]
        distinct = "__DISTINCT__" in projection
        seen: set[tuple[tuple[str, str], ...]] = set()
        for binding in filtered:
            row = {variable: binding[variable] for variable in variables if variable in binding}
            key = tuple(sorted(row.items()))
            if distinct and key in seen:
                continue
            seen.add(key)
            projected.append(row)
            if len(projected) >= limit:
                break
        return tuple(projected)

    @staticmethod
    def _match_query_term(
        expected: str,
        is_variable: bool,
        actual: str,
        actual_literal: bool,
        binding: dict[str, str],
    ) -> bool:
        if is_variable:
            variable = expected[1:]
            bound = binding.get(variable)
            if bound is not None and bound != actual:
                return False
            binding[variable] = actual
            return True
        return expected == actual

    @staticmethod
    def _filters_match(
        binding: Mapping[str, str],
        filters: Sequence[_FilterPattern],
        prefixes: Mapping[str, str],
    ) -> bool:
        for item in filters:
            actual = binding.get(item.variable[1:])
            if actual is None:
                return False
            expected, _, _ = _expand_term(item.value, prefixes)
            if item.operator == "regex":
                flags = re.IGNORECASE if item.flags else 0
                if re.search(item.value, actual, flags) is None:
                    return False
            elif actual != expected:
                return False
        return True

    def find_paths(
        self,
        start_ids: Iterable[str],
        *,
        target_ids: Iterable[str] = (),
        predicates: Iterable[str] = (),
        max_hops: int = 3,
        max_paths: int = 20,
    ) -> tuple[OntologyPath, ...]:
        if max_hops <= 0 or max_paths <= 0:
            raise ValueError("max_hops y max_paths deben ser positivos")
        starts = tuple(dict.fromkeys(_iri(item, self.base_iri) for item in start_ids))
        targets = {_iri(item, self.base_iri) for item in target_ids}
        allowed = {
            _iri(predicate, self.base_iri) if not predicate.startswith("http") else predicate
            for predicate in predicates
        }
        results: list[OntologyPath] = []
        for start in starts:
            queue = deque([(start, (start,), ())])
            while queue and len(results) < max_paths:
                current, nodes, triples = queue.popleft()
                if triples and (not targets or current in targets):
                    results.append(OntologyPath(nodes=nodes, triples=triples))
                    if targets and current in targets:
                        continue
                if len(triples) >= max_hops:
                    continue
                for edge in self.graph.triples(subject=current):
                    if edge.object_is_literal or (allowed and edge.predicate not in allowed):
                        continue
                    if edge.object in nodes:
                        continue
                    queue.append((edge.object, (*nodes, edge.object), (*triples, edge)))
            if len(results) >= max_paths:
                break
        return tuple(results)

    def validate_constraints(self) -> tuple[ConstraintViolation, ...]:
        violations: list[ConstraintViolation] = []
        if self.knowledge_graph is not None:
            for error in self.knowledge_graph.validate_integrity():
                violations.append(ConstraintViolation("GRAPH_INTEGRITY", error))
        known_nodes = set(self.known_nodes)
        relation_predicates = {_iri(name, self.base_iri) for name in PREDICATE_RELATIONS}
        for triple in self.graph:
            if triple.predicate not in relation_predicates:
                continue
            if triple.subject not in known_nodes or triple.object not in known_nodes:
                violations.append(
                    ConstraintViolation(
                        "BROKEN_ENDPOINT",
                        f"Relation endpoint missing for {triple.subject} {triple.predicate} {triple.object}",
                        evidence_refs=triple.evidence_refs,
                    )
                )
            if not triple.evidence_refs:
                violations.append(
                    ConstraintViolation(
                        "MISSING_EVIDENCE",
                        f"Relation has no evidence: {triple.subject} {triple.predicate} {triple.object}",
                        severity="WARNING",
                    )
                )
            if (
                _local_id(triple.predicate, self.base_iri) in SYMMETRIC_PREDICATES
                and not triple.inferred
            ):
                violations.append(
                    ConstraintViolation(
                        "CONTRADICTION",
                        f"Contradictory relation detected between {triple.subject} and {triple.object}",
                        evidence_refs=triple.evidence_refs,
                    )
                )
        return tuple(violations)

    def reason(self, query: str, *, retrieval: Any = None, max_hops: int = 3) -> OntologyReasoningResult:
        """Resolve retrieval seeds through the graph and return evidence paths."""

        if not query.strip():
            raise ValueError("query no puede estar vacío")
        relation_names = self._relation_names_for_query(query)
        predicates = tuple(relation_names or PREDICATE_RELATIONS.keys())
        seed_nodes = self._seed_nodes(query, retrieval)
        if not seed_nodes:
            seed_nodes = self._nodes_with_predicates(predicates)
        paths = self.find_paths(seed_nodes, predicates=predicates, max_hops=max_hops)
        if relation_names:
            paths = tuple(
                path
                for path in paths
                if any(_local_id(edge.predicate, self.base_iri) in relation_names for edge in path.triples)
            )

        sparql_queries: list[str] = []
        bindings: list[Mapping[str, str]] = []
        query_predicates = tuple(dict.fromkeys(relation_names or ("supersedes", "validates", "contradicts")))
        for predicate_name in query_predicates:
            sparql = (
                "PREFIX bago: <{base}> "
                "SELECT ?subject ?object WHERE {{ ?subject bago:{predicate} ?object . }} LIMIT 50"
            ).format(base=self.base_iri, predicate=predicate_name)
            sparql_queries.append(sparql)
            bindings.extend(self.select(sparql))

        violations = self.validate_constraints()
        evidence_refs = set(reference for path in paths for reference in path.evidence_refs)
        evidence_refs.update(self._retrieval_evidence_for_seeds(retrieval, seed_nodes))
        inferred_for_result = tuple(
            triple for triple in self.inferred_triples
            if not relation_names or _local_id(triple.predicate, self.base_iri) in relation_names
        )
        outcome = "CONSTRAINT_VIOLATION" if any(item.severity == "ERROR" for item in violations) else "SUCCESS"
        fingerprint = hashlib.sha256(
            "\n".join(
                f"{item.subject}|{item.predicate}|{item.object}|{item.object_is_literal}"
                for item in self.graph
            ).encode("utf-8")
        ).hexdigest()
        receipt_id = "ontology_receipt_" + hashlib.sha256(
            f"{query}|{fingerprint}|{','.join(sorted(evidence_refs))}".encode("utf-8")
        ).hexdigest()[:16]
        receipt = OntologyReceipt(
            receipt_id=receipt_id,
            query=query,
            outcome=outcome,
            graph_fingerprint=fingerprint,
            explicit_triples=len(self.rdf_graph),
            inferred_triples=len(self.inferred_triples),
            sparql_queries=tuple(sparql_queries),
            paths_found=len(paths),
            contradictions_found=sum(1 for item in violations if item.code == "CONTRADICTION"),
            constraints_checked=len(violations),
            evidence_refs=tuple(sorted(evidence_refs)),
        )
        summary = self._summary(query, paths, inferred_for_result, violations, evidence_refs, receipt)
        return OntologyReasoningResult(
            query=query,
            paths=paths,
            sparql_bindings=tuple(bindings),
            inferred_triples=inferred_for_result,
            violations=violations,
            evidence_refs=tuple(sorted(evidence_refs)),
            receipt=receipt,
            summary=summary,
        )

    def _seed_nodes(self, query: str, retrieval: Any) -> tuple[str, ...]:
        candidates: list[str] = []
        if retrieval is not None:
            for hit in getattr(retrieval, "hits", ()):
                chunk = hit.chunk
                metadata = dict(chunk.metadata)
                values: list[str] = [chunk.chunk_id, chunk.document_id, chunk.source_uri]
                for key in ("asset_id", "entity_id", "ontology_id", "entity_ids", "ontology_ids"):
                    raw = metadata.get(key)
                    if isinstance(raw, (list, tuple, set)):
                        values.extend(str(item) for item in raw)
                    elif raw:
                        values.append(str(raw))
                for value in values:
                    resource = _iri(value, self.base_iri)
                    if resource in self.known_nodes:
                        candidates.append(resource)
                query_tokens = set(_tokens(query))
                for node in self.known_nodes:
                    text = self._node_text(node)
                    if query_tokens & set(_tokens(text)) and query_tokens & set(_tokens(chunk.content)):
                        candidates.append(node)
        query_tokens = set(_tokens(query))
        scored: list[tuple[int, str]] = []
        for node in self.known_nodes:
            overlap = len(query_tokens & set(_tokens(self._node_text(node))))
            if overlap:
                scored.append((overlap, node))
        candidates.extend(node for _, node in sorted(scored, key=lambda item: (-item[0], item[1]))[:8])
        return tuple(dict.fromkeys(candidates))

    def _retrieval_evidence_for_seeds(self, retrieval: Any, seeds: Sequence[str]) -> set[str]:
        if retrieval is None:
            return set()
        seed_set = set(seeds)
        refs: set[str] = set()
        for hit in getattr(retrieval, "hits", ()):
            chunk = hit.chunk
            values = [chunk.chunk_id, chunk.document_id, chunk.source_uri]
            metadata = dict(chunk.metadata)
            raw_ids = metadata.get("asset_id") or metadata.get("entity_id") or metadata.get("ontology_id")
            if raw_ids:
                values.append(str(raw_ids))
            if any(_iri(value, self.base_iri) in seed_set for value in values):
                refs.add(hit.evidence.citation)
        return refs

    def _node_text(self, node: str) -> str:
        labels = [triple.object for triple in self.graph.triples(subject=node, predicate=RDFS_LABEL)]
        return " ".join((_local_id(node, self.base_iri), *labels))

    def _nodes_with_predicates(self, predicates: Iterable[str]) -> tuple[str, ...]:
        allowed = {_iri(item, self.base_iri) for item in predicates}
        return tuple(
            dict.fromkeys(
                triple.subject
                for triple in self.graph
                if triple.predicate in allowed and not triple.object_is_literal
            )
        )

    @staticmethod
    def _relation_names_for_query(query: str) -> tuple[str, ...]:
        lowered = _normalize(query)
        found: list[str] = []
        mapping = (
            (("sustitu", "reemplaz", "supersed", "version anterior"), "supersedes"),
            (("valid", "evidencia", "demuestra", "proof"), "validates"),
            (("contradic", "conflict", "incompatible"), "contradicts"),
            (("depende", "requiere", "requires", "dependenc"), "requires"),
            (("deriv", "lineage", "origen"), "derivedFrom"),
        )
        for terms, predicate in mapping:
            if any(term in lowered for term in terms):
                found.append(predicate)
        if "validates" in found:
            found.append("validatedBy")
        return tuple(dict.fromkeys(found))

    def _summary(
        self,
        query: str,
        paths: Sequence[OntologyPath],
        inferred: Sequence[RDFTriple],
        violations: Sequence[ConstraintViolation],
        evidence_refs: Iterable[str],
        receipt: OntologyReceipt,
    ) -> str:
        lines = ["Ontology Engine (RDF/SPARQL local, coste=0):"]
        if paths:
            lines.append("Paths:")
            for path in paths[:8]:
                rendered = _local_id(path.nodes[0], self.base_iri)
                for edge in path.triples:
                    rendered += f" -[{_local_id(edge.predicate, self.base_iri)}]-> {_local_id(edge.object, self.base_iri)}"
                marker = " [inferred]" if any(edge.inferred for edge in path.triples) else ""
                lines.append(f"- {rendered}{marker}")
        else:
            lines.append("Paths: none found for the retrieved graph seeds.")
        if inferred:
            lines.append(f"Inferences: {len(inferred)} derived triples materialized locally.")
        contradictions = [item for item in violations if item.code == "CONTRADICTION"]
        if contradictions:
            lines.append(f"Contradictions: {len(contradictions)} explicit conflict relation(s) detected.")
        errors = [item for item in violations if item.severity == "ERROR" and item.code != "CONTRADICTION"]
        if errors:
            lines.append("Constraints: " + "; ".join(item.message for item in errors[:4]))
        refs = tuple(sorted(set(evidence_refs)))
        if refs:
            lines.append("Evidence: " + ", ".join(refs))
        lines.append(f"Receipt: {receipt.receipt_id} outcome={receipt.outcome} triples={len(self.graph)}")
        return "\n".join(lines)


__all__ = [
    "ConstraintViolation",
    "DEFAULT_BASE_IRI",
    "OntologyEngine",
    "OntologyPath",
    "OntologyReasoningResult",
    "OntologyReceipt",
    "RDFGraph",
    "RDFTriple",
    "SPARQLQueryError",
]
