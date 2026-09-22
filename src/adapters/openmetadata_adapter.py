"""Governed OpenMetadata catalog adapter.

The adapter keeps OpenMetadata behind the BAGO execution boundary.  Reads
cover catalog search and lineage retrieval; writes cover lineage, ownership,
schema versioning and data-quality test definitions.  Every operation is an
``ExecutionRequest`` and requires a matching, unexpired ``Permit`` before the
transport client is called.

The transport is deliberately injected in tests and evidence scripts.  A
small stdlib HTTP client is available for a later local OpenMetadata run, but
the repository does not pretend that a fixture is a running catalog.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Mapping, Optional, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request as URLRequest
from urllib.request import urlopen

from orchestration.state_graph import (
    AuthorizationDecision,
    EffectType,
    ExecutionOutcome,
    ExecutionRequest,
    Permit,
)


class MetadataCatalogGovernanceError(PermissionError):
    """Raised for malformed or out-of-scope catalog operations."""


class MetadataCatalogConfigurationError(RuntimeError):
    """Raised when the real catalog transport cannot be configured."""


class OpenMetadataErrorKind(str, Enum):
    """Stable error taxonomy used by catalog receipts."""

    TIMEOUT = "TIMEOUT"
    THROTTLE = "THROTTLE"
    AUTHORIZATION = "AUTHORIZATION"
    VALIDATION = "VALIDATION"
    NETWORK = "NETWORK"
    RATE_LIMIT = "RATE_LIMIT"
    CONFIGURATION = "CONFIGURATION"
    NOT_FOUND = "NOT_FOUND"
    UNKNOWN = "UNKNOWN"


class OpenMetadataHTTPError(RuntimeError):
    """HTTP failure carrying a status code without exposing response secrets."""

    def __init__(self, status_code: int, message: str = "") -> None:
        self.status_code = status_code
        super().__init__(f"OpenMetadata HTTP {status_code}: {message}".strip())


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _text(value: Any, default: str = "") -> str:
    return value if isinstance(value, str) else default


def _entity_reference(value: Any, *, default_type: str = "") -> dict[str, str]:
    if isinstance(value, Mapping):
        data = dict(value)
        return {
            "id": _text(data.get("id"), _text(data.get("fullyQualifiedName"))),
            "type": _text(data.get("type"), default_type),
            "name": _text(data.get("name"), _text(data.get("fullyQualifiedName"))),
        }
    reference = _text(value)
    return {"id": reference, "type": default_type, "name": reference}


def _owner_name(value: Any) -> Optional[str]:
    if isinstance(value, str) and value:
        return value
    if isinstance(value, Mapping):
        return (
            _text(value.get("fullyQualifiedName"))
            or _text(value.get("name"))
            or _text(value.get("id"))
            or None
        )
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return _owner_name(value[0]) if value else None
    return None


@dataclass(frozen=True)
class OpenMetadataCatalogPolicy:
    """Local policy for API scope, retry, timeout and quota behavior."""

    base_url: str = "http://localhost:8585/api"
    timeout_seconds: float = 30.0
    max_attempts: int = 3
    backoff_seconds: float = 0.25
    allowed_entity_types: frozenset[str] = field(
        default_factory=lambda: frozenset(
            {
                "table",
                "dashboard",
                "pipeline",
                "topic",
                "apiEndpoint",
                "document",
                "knowledgeAsset",
                "knowledgeChunk",
            }
        )
    )
    max_page_size: int = 100
    max_query_chars: int = 512
    auto_allow_external_api: bool = True
    max_calls_per_window: Optional[int] = None
    rate_limit_window_seconds: float = 60.0

    def __post_init__(self) -> None:
        normalized_url = self.base_url.strip().rstrip("/")
        if not normalized_url:
            raise ValueError("base_url is required")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.max_attempts <= 0 or self.max_attempts > 8:
            raise ValueError("max_attempts must be between 1 and 8")
        if self.backoff_seconds < 0:
            raise ValueError("backoff_seconds cannot be negative")
        if self.max_page_size <= 0:
            raise ValueError("max_page_size must be positive")
        if self.max_query_chars <= 0:
            raise ValueError("max_query_chars must be positive")
        if self.max_calls_per_window is not None and self.max_calls_per_window <= 0:
            raise ValueError("max_calls_per_window must be positive when configured")
        if self.rate_limit_window_seconds <= 0:
            raise ValueError("rate_limit_window_seconds must be positive")
        object.__setattr__(self, "base_url", normalized_url)
        object.__setattr__(
            self,
            "allowed_entity_types",
            frozenset(str(item) for item in self.allowed_entity_types),
        )

    def allows_entity_type(self, entity_type: str) -> bool:
        return not entity_type or entity_type in self.allowed_entity_types


@dataclass(frozen=True)
class CatalogEntity:
    """Normalized OpenMetadata entity used by BAGO discovery and receipts."""

    entity_id: str
    entity_type: str
    fully_qualified_name: str
    name: str
    description: str = ""
    owner: Optional[str] = None
    tags: tuple[str, ...] = ()
    version: str = ""
    authority: str = "PROPOSED"
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, value: Any, *, default_type: str = "") -> "CatalogEntity":
        data = _mapping(value)
        source = _mapping(data.get("_source")) or data
        entity_id = _text(source.get("id"), _text(data.get("_id")))
        entity_type = _text(
            source.get("entityType"),
            _text(source.get("type"), default_type),
        )
        fqn = _text(
            source.get("fullyQualifiedName"),
            _text(source.get("fqn"), entity_id),
        )
        name = _text(source.get("name"), fqn.rsplit(".", 1)[-1])
        owners = source.get("owners", source.get("owner"))
        tags = source.get("tags", ())
        normalized_tags: list[str] = []
        if isinstance(tags, Sequence) and not isinstance(tags, (str, bytes)):
            for tag in tags:
                if isinstance(tag, Mapping):
                    tag_name = _text(tag.get("tagFQN"), _text(tag.get("name")))
                else:
                    tag_name = _text(tag)
                if tag_name:
                    normalized_tags.append(tag_name)
        metadata = _mapping(source.get("extension"))
        metadata.update(_mapping(source.get("metadata")))
        authority = _text(metadata.get("authority"), "PROPOSED")
        return cls(
            entity_id=entity_id,
            entity_type=entity_type,
            fully_qualified_name=fqn,
            name=name,
            description=_text(source.get("description")),
            owner=_owner_name(owners),
            tags=tuple(sorted(set(normalized_tags))),
            version=str(source.get("version", "")),
            authority=authority,
            metadata=metadata,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "entity_type": self.entity_type,
            "fully_qualified_name": self.fully_qualified_name,
            "name": self.name,
            "description": self.description,
            "owner": self.owner,
            "tags": list(self.tags),
            "version": self.version,
            "authority": self.authority,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class LineageEdge:
    """Normalized directional edge from upstream entity to downstream entity."""

    from_entity: str
    to_entity: str
    from_type: str = ""
    to_type: str = ""
    pipeline: Optional[str] = None
    sql_query: Optional[str] = None
    evidence_ref: Optional[str] = None

    @classmethod
    def from_mapping(cls, value: Any) -> "LineageEdge":
        data = _mapping(value)
        source = _entity_reference(data.get("fromEntity"), default_type="")
        target = _entity_reference(data.get("toEntity"), default_type="")
        details = _mapping(data.get("lineageDetails"))
        pipeline = _owner_name(details.get("pipeline"))
        return cls(
            from_entity=source["id"],
            to_entity=target["id"],
            from_type=source["type"],
            to_type=target["type"],
            pipeline=pipeline,
            sql_query=_text(details.get("sqlQuery")) or None,
            evidence_ref=_text(details.get("evidenceRef")) or None,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "from_entity": self.from_entity,
            "to_entity": self.to_entity,
            "from_type": self.from_type,
            "to_type": self.to_type,
            "pipeline": self.pipeline,
            "sql_query": self.sql_query,
            "evidence_ref": self.evidence_ref,
        }


@dataclass(frozen=True)
class QualityRule:
    """OpenMetadata test-definition shaped quality rule."""

    name: str
    entity_fqn: str
    entity_type: str = "TABLE"
    description: str = ""
    severity: str = "MEDIUM"
    parameters: Mapping[str, Any] = field(default_factory=dict)
    test_platforms: tuple[str, ...] = ("OpenMetadata",)

    def __post_init__(self) -> None:
        if not self.name.strip() or not self.entity_fqn.strip():
            raise ValueError("quality rule name and entity_fqn are required")
        if self.entity_type not in {"TABLE", "COLUMN"}:
            raise ValueError("entity_type must be TABLE or COLUMN")
        if self.severity not in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}:
            raise ValueError("severity must be LOW, MEDIUM, HIGH or CRITICAL")
        object.__setattr__(self, "parameters", dict(self.parameters))

    def to_payload(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "entityType": self.entity_type,
            "testPlatforms": list(self.test_platforms),
            "parameterDefinition": [
                {"name": str(name), "description": str(value)}
                for name, value in self.parameters.items()
            ],
            "extension": {
                "bagoSeverity": self.severity,
                "bagoEntityFQN": self.entity_fqn,
            },
        }


@dataclass(frozen=True)
class MetadataCatalogReceipt:
    """Audit receipt emitted for every allowed, denied or failed catalog call."""

    receipt_id: str
    request_id: str
    permit_id: str
    operation: str
    decision: AuthorizationDecision
    execution_outcome: ExecutionOutcome
    actual_effect: Mapping[str, Any]
    evidence_refs: tuple[str, ...]
    duration_ms: int
    result_count: int
    attempts: int
    error_kind: Optional[OpenMetadataErrorKind] = None
    error_message: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "request_id": self.request_id,
            "permit_id": self.permit_id,
            "operation": self.operation,
            "decision": self.decision.value,
            "execution_outcome": self.execution_outcome.value,
            "actual_effect": dict(self.actual_effect),
            "evidence_refs": list(self.evidence_refs),
            "duration_ms": self.duration_ms,
            "result_count": self.result_count,
            "attempts": self.attempts,
            "error_kind": self.error_kind.value if self.error_kind else None,
            "error_message": self.error_message,
        }


@dataclass(frozen=True)
class MetadataCatalogResult:
    """Normalized catalog result plus the receipt for the same request."""

    entities: tuple[CatalogEntity, ...]
    lineage: tuple[LineageEdge, ...]
    payload: Mapping[str, Any]
    raw_response: Mapping[str, Any]
    receipt: MetadataCatalogReceipt


class _StdlibOpenMetadataClient:
    """Minimal JSON client used only when a live transport is explicitly used."""

    def __init__(self, policy: OpenMetadataCatalogPolicy) -> None:
        self.policy = policy

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Mapping[str, Any]] = None,
        json: Optional[Mapping[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> Mapping[str, Any]:
        query = urlencode({key: value for key, value in (params or {}).items() if value is not None})
        url = f"{self.policy.base_url}{path}"
        if query:
            url = f"{url}?{query}"
        body = None if json is None else _canonical_json(json).encode("utf-8")
        request = URLRequest(
            url,
            data=body,
            method=method.upper(),
            headers={"Accept": "application/json", "Content-Type": "application/json"},
        )
        try:
            with urlopen(request, timeout=timeout or self.policy.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except HTTPError as error:
            message = error.read().decode("utf-8", errors="replace")[:500]
            raise OpenMetadataHTTPError(error.code, message) from error
        except (URLError, TimeoutError) as error:
            raise ConnectionError(str(error)) from error
        if not raw.strip():
            return {}
        decoded = json_module_loads(raw)
        return decoded if isinstance(decoded, Mapping) else {"data": decoded}


def json_module_loads(value: str) -> Any:
    """Keep the stdlib client easy to monkeypatch in tests."""
    return json.loads(value)


class GovernedOpenMetadataAdapter:
    """BAGO gateway for OpenMetadata catalog and lineage APIs."""

    OPERATION_EFFECTS = {
        "search": EffectType.READ,
        "get_lineage": EffectType.READ,
        "add_lineage": EffectType.WRITE,
        "assign_ownership": EffectType.WRITE,
        "register_schema_version": EffectType.WRITE,
        "create_quality_rule": EffectType.CREATE,
    }

    def __init__(
        self,
        *,
        policy: Optional[OpenMetadataCatalogPolicy] = None,
        client: Any = None,
        sleep_fn: Optional[Callable[[float], None]] = None,
        monotonic_fn: Optional[Callable[[], float]] = None,
    ) -> None:
        self.policy = policy or OpenMetadataCatalogPolicy()
        self._client = client
        self._sleep = sleep_fn or time.sleep
        self._monotonic = monotonic_fn or time.monotonic
        self._rate_events: deque[float] = deque()

    def build_request(
        self,
        operation: str,
        *,
        proposed_by: str,
        context_revision: str,
        resource: str = "",
        entity_type: str = "",
        request_id: Optional[str] = None,
        **parameters: Any,
    ) -> ExecutionRequest:
        """Build a catalog request without contacting OpenMetadata."""
        if operation not in self.OPERATION_EFFECTS:
            raise ValueError(f"unsupported catalog operation: {operation}")
        if not proposed_by.strip() or not context_revision.strip():
            raise ValueError("proposed_by and context_revision are required")
        if entity_type and not self.policy.allows_entity_type(entity_type):
            raise ValueError(f"entity type is outside policy: {entity_type}")
        normalized_resource = resource.strip()
        if operation == "search":
            query = str(parameters.get("query", normalized_resource)).strip()
            if not query:
                raise ValueError("search query is required")
            if len(query) > self.policy.max_query_chars:
                raise ValueError("search query exceeds policy limit")
            parameters["query"] = query
        elif operation != "create_quality_rule" and not normalized_resource:
            raise ValueError(f"resource is required for {operation}")
        if "page_size" in parameters:
            parameters["page_size"] = min(int(parameters["page_size"]), self.policy.max_page_size)
        else:
            parameters["page_size"] = self.policy.max_page_size
        parameters["resource"] = normalized_resource
        parameters["entity_type"] = entity_type
        stable_payload = {
            "operation": operation,
            "resource": normalized_resource,
            "entity_type": entity_type,
            "parameters": parameters,
            "proposed_by": proposed_by,
            "context_revision": context_revision,
        }
        normalized_id = request_id or (
            "omreq_"
            + hashlib.sha256(_canonical_json(stable_payload).encode("utf-8")).hexdigest()[:16]
        )
        return ExecutionRequest(
            request_id=normalized_id,
            tool_name=f"openmetadata.{operation}",
            effect_type=self.OPERATION_EFFECTS[operation],
            parameters=parameters,
            proposed_by=proposed_by,
            context_revision=context_revision,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    def authorize(self, request: ExecutionRequest) -> Permit:
        """Issue a scoped permit; writes can require human approval by policy."""
        operation = self._operation(request)
        entity_type = str(request.parameters.get("entity_type", ""))
        decision = AuthorizationDecision.ALLOW
        rationale = "OpenMetadata operation is within the configured catalog scope"
        if operation not in self.OPERATION_EFFECTS:
            decision = AuthorizationDecision.DENY
            rationale = "Unknown OpenMetadata operation"
        elif not self.policy.allows_entity_type(entity_type):
            decision = AuthorizationDecision.DENY
            rationale = f"Entity type {entity_type!r} is outside the catalog allowlist"
        elif (
            self.OPERATION_EFFECTS[operation] != request.effect_type
            or not self.policy.auto_allow_external_api
        ):
            decision = AuthorizationDecision.REQUIRE_HUMAN
            rationale = "Catalog operation requires explicit human approval"
        now = datetime.now(timezone.utc)
        permit_id = "ompermit_" + hashlib.sha256(
            f"{request.request_id}:{decision.value}:{operation}".encode("utf-8")
        ).hexdigest()[:16]
        return Permit(
            permit_id=permit_id,
            request_id=request.request_id,
            decision=decision,
            rationale=rationale,
            constraints=[
                f"base_url={self.policy.base_url}",
                f"operation={operation}",
                f"entity_type={entity_type or '*'}",
            ],
            issued_at=now.isoformat(),
            expires_at=(now + timedelta(minutes=5)).isoformat(),
            signed_by="bago.openmetadata.policy",
        )

    def search(self, request: ExecutionRequest, permit: Optional[Permit]) -> MetadataCatalogResult:
        query = str(request.parameters.get("query", ""))
        params = {
            "q": query,
            "index": request.parameters.get("entity_type") or None,
            "from": request.parameters.get("offset", 0),
            "size": request.parameters.get("page_size", self.policy.max_page_size),
        }
        return self._execute(
            request,
            permit,
            operation="search",
            method="GET",
            path="/v1/search/query",
            params=params,
            normalizer=self._normalize_search,
        )

    def get_lineage(
        self,
        request: ExecutionRequest,
        permit: Optional[Permit],
    ) -> MetadataCatalogResult:
        entity_type = str(request.parameters.get("entity_type", "table"))
        resource = quote(str(request.parameters.get("resource", "")), safe="")
        params = {
            "upstreamDepth": request.parameters.get("upstream_depth", 3),
            "downstreamDepth": request.parameters.get("downstream_depth", 3),
        }
        return self._execute(
            request,
            permit,
            operation="get_lineage",
            method="GET",
            path=f"/v1/{entity_type}/{resource}/lineage",
            params=params,
            normalizer=self._normalize_lineage,
        )

    def add_lineage(
        self,
        request: ExecutionRequest,
        permit: Optional[Permit],
    ) -> MetadataCatalogResult:
        body = self._lineage_payload(request.parameters)
        return self._execute(
            request,
            permit,
            operation="add_lineage",
            method="PUT",
            path="/v1/lineage",
            json_body=body,
            normalizer=self._normalize_lineage,
        )

    def assign_ownership(
        self,
        request: ExecutionRequest,
        permit: Optional[Permit],
    ) -> MetadataCatalogResult:
        entity_type = str(request.parameters.get("entity_type", "table"))
        resource = quote(str(request.parameters.get("resource", "")), safe="")
        owner = {
            "id": str(request.parameters.get("owner_id", "")),
            "name": str(request.parameters.get("owner_name", "")),
            "type": str(request.parameters.get("owner_type", "team")),
        }
        body = {"owners": [owner]}
        return self._execute(
            request,
            permit,
            operation="assign_ownership",
            method="PATCH",
            path=f"/v1/{entity_type}/{resource}",
            json_body=body,
            normalizer=self._normalize_entity,
        )

    def register_schema_version(
        self,
        request: ExecutionRequest,
        permit: Optional[Permit],
    ) -> MetadataCatalogResult:
        entity_type = str(request.parameters.get("entity_type", "table"))
        resource = quote(str(request.parameters.get("resource", "")), safe="")
        body = {
            "version": str(request.parameters.get("version", "")),
            "schema": _mapping(request.parameters.get("schema")),
            "extension": {"bagoSchemaRevision": request.parameters.get("version", "")},
        }
        return self._execute(
            request,
            permit,
            operation="register_schema_version",
            method="PATCH",
            path=f"/v1/{entity_type}/{resource}",
            json_body=body,
            normalizer=self._normalize_entity,
        )

    def create_quality_rule(
        self,
        request: ExecutionRequest,
        permit: Optional[Permit],
    ) -> MetadataCatalogResult:
        rule = request.parameters.get("quality_rule")
        if isinstance(rule, QualityRule):
            body = rule.to_payload()
        elif isinstance(rule, Mapping):
            body = dict(rule)
        else:
            raise ValueError("quality_rule must be a QualityRule or mapping")
        return self._execute(
            request,
            permit,
            operation="create_quality_rule",
            method="POST",
            path="/v1/dataQuality/testDefinitions",
            json_body=body,
            normalizer=self._normalize_entity,
        )

    def _execute(
        self,
        request: ExecutionRequest,
        permit: Optional[Permit],
        *,
        operation: str,
        method: str,
        path: str,
        params: Optional[Mapping[str, Any]] = None,
        json_body: Optional[Mapping[str, Any]] = None,
        normalizer: Callable[[Mapping[str, Any]], tuple[tuple[CatalogEntity, ...], tuple[LineageEdge, ...], dict[str, Any]]],
    ) -> MetadataCatalogResult:
        started = self._monotonic()
        base_effect = {
            "transport": "injected" if self._client is not None else "stdlib_http",
            "method": method,
            "path": path,
            "base_url": self.policy.base_url,
        }
        evidence_refs = tuple(str(item) for item in request.parameters.get("evidence_refs", ()))
        permit_id = permit.permit_id if permit else ""
        operation_matches = self._operation(request) == operation
        entity_type = str(request.parameters.get("entity_type", ""))
        if not operation_matches:
            return self._failure_result(
                request,
                permit_id,
                operation,
                base_effect,
                evidence_refs,
                started,
                OpenMetadataErrorKind.VALIDATION,
                "request operation does not match adapter method",
                decision=AuthorizationDecision.DENY,
            )
        if not self.policy.allows_entity_type(entity_type):
            return self._failure_result(
                request,
                permit_id,
                operation,
                base_effect,
                evidence_refs,
                started,
                OpenMetadataErrorKind.AUTHORIZATION,
                f"entity type {entity_type!r} is outside policy",
                decision=AuthorizationDecision.DENY,
            )
        if permit is None:
            return self._failure_result(
                request,
                "",
                operation,
                base_effect,
                evidence_refs,
                started,
                OpenMetadataErrorKind.AUTHORIZATION,
                "matching Permit is required before catalog transport",
                decision=AuthorizationDecision.DENY,
            )
        if permit.request_id != request.request_id or permit.decision is not AuthorizationDecision.ALLOW:
            return self._failure_result(
                request,
                permit_id,
                operation,
                base_effect,
                evidence_refs,
                started,
                OpenMetadataErrorKind.AUTHORIZATION,
                "Permit does not allow this request",
                decision=permit.decision,
            )
        if not permit.is_valid():
            return self._failure_result(
                request,
                permit_id,
                operation,
                base_effect,
                evidence_refs,
                started,
                OpenMetadataErrorKind.AUTHORIZATION,
                "Permit is expired or not yet valid",
                decision=AuthorizationDecision.DENY,
            )
        if not self._reserve_rate_limit():
            return self._failure_result(
                request,
                permit_id,
                operation,
                base_effect,
                evidence_refs,
                started,
                OpenMetadataErrorKind.RATE_LIMIT,
                "local OpenMetadata rate limit reached before transport call",
                decision=AuthorizationDecision.ALLOW,
            )

        attempts = 0
        try:
            raw_response: Mapping[str, Any] = {}
            last_error: Optional[Exception] = None
            for attempts in range(1, self.policy.max_attempts + 1):
                try:
                    raw_response = self._call_client(
                        method,
                        path,
                        params=params,
                        json_body=json_body,
                    )
                    last_error = None
                    break
                except Exception as error:  # transport implementations vary by SDK
                    last_error = error
                    kind = self.classify_error(error)
                    if kind not in {
                        OpenMetadataErrorKind.TIMEOUT,
                        OpenMetadataErrorKind.THROTTLE,
                        OpenMetadataErrorKind.NETWORK,
                    } or attempts >= self.policy.max_attempts:
                        break
                    self._sleep(self.policy.backoff_seconds * attempts)
            if last_error is not None:
                return self._failure_result(
                    request,
                    permit_id,
                    operation,
                    base_effect,
                    evidence_refs,
                    started,
                    self.classify_error(last_error),
                    str(last_error),
                    decision=AuthorizationDecision.ALLOW,
                    attempts=attempts,
                )
            entities, lineage, payload = normalizer(raw_response)
            receipt = self._receipt(
                request,
                permit_id,
                operation,
                base_effect,
                evidence_refs,
                started,
                AuthorizationDecision.ALLOW,
                ExecutionOutcome.SUCCESS,
                len(entities) + len(lineage),
                attempts,
            )
            return MetadataCatalogResult(entities, lineage, payload, raw_response, receipt)
        except Exception as error:
            return self._failure_result(
                request,
                permit_id,
                operation,
                base_effect,
                evidence_refs,
                started,
                OpenMetadataErrorKind.VALIDATION,
                str(error),
                decision=AuthorizationDecision.ALLOW,
                attempts=attempts,
            )

    def _call_client(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Mapping[str, Any]],
        json_body: Optional[Mapping[str, Any]],
    ) -> Mapping[str, Any]:
        client = self._client or _StdlibOpenMetadataClient(self.policy)
        if not hasattr(client, "request"):
            raise MetadataCatalogConfigurationError("catalog client must expose request()")
        response = client.request(
            method,
            path,
            params=dict(params or {}),
            json=dict(json_body or {}) if json_body is not None else None,
            timeout=self.policy.timeout_seconds,
        )
        return response if isinstance(response, Mapping) else {"data": response}

    def _reserve_rate_limit(self) -> bool:
        limit = self.policy.max_calls_per_window
        if limit is None:
            return True
        now = self._monotonic()
        cutoff = now - self.policy.rate_limit_window_seconds
        while self._rate_events and self._rate_events[0] <= cutoff:
            self._rate_events.popleft()
        if len(self._rate_events) >= limit:
            return False
        self._rate_events.append(now)
        return True

    @staticmethod
    def classify_error(error: Exception) -> OpenMetadataErrorKind:
        if isinstance(error, OpenMetadataHTTPError):
            if error.status_code in {401, 403}:
                return OpenMetadataErrorKind.AUTHORIZATION
            if error.status_code == 404:
                return OpenMetadataErrorKind.NOT_FOUND
            if error.status_code == 408:
                return OpenMetadataErrorKind.TIMEOUT
            if error.status_code == 429:
                return OpenMetadataErrorKind.THROTTLE
            if 400 <= error.status_code < 500:
                return OpenMetadataErrorKind.VALIDATION
            if error.status_code >= 500:
                return OpenMetadataErrorKind.NETWORK
        name = type(error).__name__.lower()
        message = str(error).lower()
        if "timeout" in name or "timed out" in message:
            return OpenMetadataErrorKind.TIMEOUT
        if "thrott" in name or "rate" in message:
            return OpenMetadataErrorKind.THROTTLE
        if "permission" in name or "forbidden" in message or "unauthorized" in message:
            return OpenMetadataErrorKind.AUTHORIZATION
        if "notfound" in name or "not found" in message:
            return OpenMetadataErrorKind.NOT_FOUND
        if isinstance(error, (ConnectionError, URLError)) or "connection" in message:
            return OpenMetadataErrorKind.NETWORK
        if isinstance(error, MetadataCatalogConfigurationError):
            return OpenMetadataErrorKind.CONFIGURATION
        return OpenMetadataErrorKind.UNKNOWN

    @staticmethod
    def _operation(request: ExecutionRequest) -> str:
        return request.tool_name.removeprefix("openmetadata.")

    @staticmethod
    def _normalize_search(
        response: Mapping[str, Any],
    ) -> tuple[tuple[CatalogEntity, ...], tuple[LineageEdge, ...], dict[str, Any]]:
        data = _mapping(response)
        hits = _mapping(data.get("hits")).get("hits", [])
        candidates = hits or data.get("data") or data.get("entities") or []
        if isinstance(candidates, Mapping):
            candidates = candidates.get("items", [])
        entities = tuple(CatalogEntity.from_mapping(item) for item in candidates)
        return entities, (), {"count": len(entities)}

    @staticmethod
    def _normalize_lineage(
        response: Mapping[str, Any],
    ) -> tuple[tuple[CatalogEntity, ...], tuple[LineageEdge, ...], dict[str, Any]]:
        data = _mapping(response)
        nodes = data.get("nodes", [])
        entities = tuple(CatalogEntity.from_mapping(item) for item in nodes)
        edges: list[LineageEdge] = []
        for key in ("upstreamEdges", "downstreamEdges", "edges"):
            values = data.get(key, [])
            if isinstance(values, Sequence) and not isinstance(values, (str, bytes)):
                edges.extend(LineageEdge.from_mapping(item) for item in values)
        return entities, tuple(edges), {"node_count": len(entities), "edge_count": len(edges)}

    @staticmethod
    def _normalize_entity(
        response: Mapping[str, Any],
    ) -> tuple[tuple[CatalogEntity, ...], tuple[LineageEdge, ...], dict[str, Any]]:
        data = _mapping(response)
        candidate = data.get("entity", data)
        entities = () if not _mapping(candidate) else (CatalogEntity.from_mapping(candidate),)
        return entities, (), {"updated": bool(entities)}

    @staticmethod
    def _lineage_payload(parameters: Mapping[str, Any]) -> dict[str, Any]:
        source = _entity_reference(parameters.get("from_entity"), default_type="table")
        target = _entity_reference(parameters.get("to_entity"), default_type="table")
        details = _mapping(parameters.get("lineage_details"))
        if parameters.get("pipeline"):
            details["pipeline"] = parameters["pipeline"]
        if parameters.get("sql_query"):
            details["sqlQuery"] = parameters["sql_query"]
        if parameters.get("evidence_ref"):
            details["evidenceRef"] = parameters["evidence_ref"]
        return {
            "edge": {
                "fromEntity": source,
                "toEntity": target,
                "lineageDetails": details,
            }
        }

    def _failure_result(
        self,
        request: ExecutionRequest,
        permit_id: str,
        operation: str,
        actual_effect: Mapping[str, Any],
        evidence_refs: tuple[str, ...],
        started: float,
        error_kind: OpenMetadataErrorKind,
        error_message: str,
        *,
        decision: AuthorizationDecision,
        attempts: int = 0,
    ) -> MetadataCatalogResult:
        receipt = self._receipt(
            request,
            permit_id,
            operation,
            actual_effect,
            evidence_refs,
            started,
            decision,
            ExecutionOutcome.FAILURE,
            0,
            attempts,
            error_kind=error_kind,
            error_message=error_message,
        )
        return MetadataCatalogResult((), (), {}, {}, receipt)

    def _receipt(
        self,
        request: ExecutionRequest,
        permit_id: str,
        operation: str,
        actual_effect: Mapping[str, Any],
        evidence_refs: tuple[str, ...],
        started: float,
        decision: AuthorizationDecision,
        outcome: ExecutionOutcome,
        result_count: int,
        attempts: int,
        *,
        error_kind: Optional[OpenMetadataErrorKind] = None,
        error_message: Optional[str] = None,
    ) -> MetadataCatalogReceipt:
        duration_ms = max(0, int((self._monotonic() - started) * 1000))
        fingerprint = _canonical_json(
            {
                "request_id": request.request_id,
                "permit_id": permit_id,
                "operation": operation,
                "decision": decision.value,
                "outcome": outcome.value,
                "error_kind": error_kind.value if error_kind else None,
            }
        )
        receipt_id = "omreceipt_" + hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()[:16]
        return MetadataCatalogReceipt(
            receipt_id=receipt_id,
            request_id=request.request_id,
            permit_id=permit_id,
            operation=operation,
            decision=decision,
            execution_outcome=outcome,
            actual_effect=dict(actual_effect),
            evidence_refs=evidence_refs,
            duration_ms=duration_ms,
            result_count=result_count,
            attempts=attempts,
            error_kind=error_kind,
            error_message=error_message,
        )


OpenMetadataAdapter = GovernedOpenMetadataAdapter
MetadataCatalogAdapter = GovernedOpenMetadataAdapter


__all__ = [
    "CatalogEntity",
    "GovernedOpenMetadataAdapter",
    "LineageEdge",
    "MetadataCatalogAdapter",
    "MetadataCatalogConfigurationError",
    "MetadataCatalogGovernanceError",
    "MetadataCatalogReceipt",
    "MetadataCatalogResult",
    "OpenMetadataAdapter",
    "OpenMetadataCatalogPolicy",
    "OpenMetadataErrorKind",
    "OpenMetadataHTTPError",
    "QualityRule",
]
