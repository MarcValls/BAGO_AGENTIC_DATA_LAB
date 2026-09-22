"""Governed Amazon Bedrock Knowledge Base retrieval adapter.

The adapter targets the ``bedrock-agent-runtime`` client and keeps the two
useful Knowledge Base paths explicit:

* ``Retrieve`` returns ranked source references for a BAGO-controlled answer;
* ``RetrieveAndGenerate`` returns an AWS-generated answer plus citations.

Both paths require a model/knowledge-base scoped BAGO ``Permit`` before the
injected or real client is called.  Tests use a deterministic client double so
the contract is verifiable without AWS credentials or network access.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Iterable, Mapping, Optional

from orchestration.state_graph import (
    AuthorizationDecision,
    EffectType,
    ExecutionOutcome,
    ExecutionRequest,
    Permit,
)

from .bedrock_provider_adapter import (
    BedrockConfigurationError,
    BedrockErrorKind,
    BedrockProviderAdapter,
)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _optional_string(value: Any) -> Optional[str]:
    return value if isinstance(value, str) and value else None


@dataclass(frozen=True)
class BedrockKnowledgeBasePolicy:
    """Local policy for knowledge-base scope, retrieval and quota limits."""

    knowledge_base_id: str
    region_name: str = "eu-west-1"
    allowed_knowledge_base_ids: frozenset[str] = field(default_factory=frozenset)
    generation_model_arn: str = ""
    timeout_seconds: float = 30.0
    max_attempts: int = 3
    backoff_seconds: float = 0.25
    max_results: int = 5
    default_search_type: str = "HYBRID"
    max_query_chars: int = 10_000
    auto_allow_external_api: bool = True
    max_calls_per_window: Optional[int] = None
    rate_limit_window_seconds: float = 60.0
    retrieve_cost_usd: float = 0.0
    retrieve_and_generate_cost_usd: float = 0.0

    def __post_init__(self) -> None:
        if not self.knowledge_base_id.strip():
            raise ValueError("knowledge_base_id is required")
        if not self.region_name.strip():
            raise ValueError("region_name is required")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.max_attempts <= 0 or self.max_attempts > 8:
            raise ValueError("max_attempts must be between 1 and 8")
        if self.backoff_seconds < 0:
            raise ValueError("backoff_seconds cannot be negative")
        if self.max_results <= 0:
            raise ValueError("max_results must be positive")
        if self.default_search_type not in {"HYBRID", "SEMANTIC"}:
            raise ValueError("default_search_type must be HYBRID or SEMANTIC")
        if self.max_query_chars <= 0:
            raise ValueError("max_query_chars must be positive")
        if self.max_calls_per_window is not None and self.max_calls_per_window <= 0:
            raise ValueError("max_calls_per_window must be positive when configured")
        if self.rate_limit_window_seconds <= 0:
            raise ValueError("rate_limit_window_seconds must be positive")
        if self.retrieve_cost_usd < 0 or self.retrieve_and_generate_cost_usd < 0:
            raise ValueError("cost rates cannot be negative")
        allowed = frozenset(str(item) for item in self.allowed_knowledge_base_ids)
        if not allowed:
            allowed = frozenset({self.knowledge_base_id})
        object.__setattr__(self, "allowed_knowledge_base_ids", allowed)

    def allows_knowledge_base(self, knowledge_base_id: str) -> bool:
        return knowledge_base_id in self.allowed_knowledge_base_ids

    def cost_for(self, operation: str) -> float:
        if operation == "retrieve_and_generate":
            return self.retrieve_and_generate_cost_usd
        return self.retrieve_cost_usd


@dataclass(frozen=True)
class BedrockKBHit:
    """Normalized source reference returned by a Bedrock Knowledge Base."""

    knowledge_base_id: str
    chunk_id: str
    content: str
    source_uri: str
    score: Optional[float]
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def citation(self) -> str:
        base = self.source_uri or f"bedrock-kb://{self.knowledge_base_id}/unknown"
        separator = "&" if "?" in base or "#" in base else "?"
        return f"{base}{separator}kb={self.knowledge_base_id}&chunk={self.chunk_id}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "knowledge_base_id": self.knowledge_base_id,
            "chunk_id": self.chunk_id,
            "content": self.content,
            "source_uri": self.source_uri,
            "score": self.score,
            "metadata": dict(self.metadata),
            "citation": self.citation,
        }


@dataclass(frozen=True)
class BedrockKBReceipt:
    """Audit receipt for a Knowledge Base retrieval or generated answer."""

    receipt_id: str
    request_id: str
    permit_id: str
    knowledge_base_id: str
    operation: str
    decision: AuthorizationDecision
    execution_outcome: ExecutionOutcome
    actual_effect: Mapping[str, Any]
    evidence_refs: tuple[str, ...]
    duration_ms: int
    cost_usd: float
    result_count: int
    attempts: int
    error_kind: Optional[BedrockErrorKind] = None
    error_message: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "request_id": self.request_id,
            "permit_id": self.permit_id,
            "knowledge_base_id": self.knowledge_base_id,
            "operation": self.operation,
            "decision": self.decision.value,
            "execution_outcome": self.execution_outcome.value,
            "actual_effect": dict(self.actual_effect),
            "evidence_refs": list(self.evidence_refs),
            "duration_ms": self.duration_ms,
            "cost_usd": self.cost_usd,
            "result_count": self.result_count,
            "attempts": self.attempts,
            "error_kind": self.error_kind.value if self.error_kind else None,
            "error_message": self.error_message,
        }


@dataclass(frozen=True)
class BedrockKBResult:
    """Normalized Knowledge Base output and its BAGO receipt."""

    answer: str
    hits: tuple[BedrockKBHit, ...]
    session_id: Optional[str]
    raw_response: Mapping[str, Any]
    receipt: BedrockKBReceipt

    @property
    def citations(self) -> tuple[str, ...]:
        return tuple(hit.citation for hit in self.hits)


class GovernedBedrockKnowledgeBaseAdapter:
    """BAGO gateway for Amazon Bedrock Knowledge Base APIs."""

    def __init__(
        self,
        *,
        policy: BedrockKnowledgeBasePolicy,
        client: Any = None,
        sleep_fn: Optional[Callable[[float], None]] = None,
        monotonic_fn: Optional[Callable[[], float]] = None,
    ) -> None:
        self.policy = policy
        self._client = client
        self._sleep = sleep_fn or time.sleep
        self._monotonic = monotonic_fn or time.monotonic
        self._rate_events: deque[float] = deque()

    def build_request(
        self,
        query: str,
        *,
        proposed_by: str,
        context_revision: str,
        operation: str = "retrieve",
        knowledge_base_id: Optional[str] = None,
        number_of_results: Optional[int] = None,
        search_type: Optional[str] = None,
        metadata_filter: Optional[Mapping[str, Any]] = None,
        model_arn: Optional[str] = None,
        generation_configuration: Optional[Mapping[str, Any]] = None,
        session_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> ExecutionRequest:
        """Build a retrieval request without contacting AWS."""

        normalized_query = query.strip()
        if not normalized_query:
            raise ValueError("query is required")
        if len(normalized_query) > self.policy.max_query_chars:
            raise ValueError("query exceeds max_query_chars")
        if not proposed_by.strip() or not context_revision.strip():
            raise ValueError("proposed_by and context_revision are required")
        if operation not in {"retrieve", "retrieve_and_generate"}:
            raise ValueError("operation must be retrieve or retrieve_and_generate")

        kb_id = knowledge_base_id or self.policy.knowledge_base_id
        result_limit = number_of_results or self.policy.max_results
        if result_limit <= 0:
            raise ValueError("number_of_results must be positive")
        effective_search_type = search_type or self.policy.default_search_type
        if effective_search_type not in {"HYBRID", "SEMANTIC"}:
            raise ValueError("search_type must be HYBRID or SEMANTIC")
        if metadata_filter is not None and not isinstance(metadata_filter, Mapping):
            raise ValueError("metadata_filter must be a mapping")

        parameters: dict[str, Any] = {
            "knowledge_base_id": kb_id,
            "query": normalized_query,
            "retrieval_configuration": {
                "number_of_results": result_limit,
                "override_search_type": effective_search_type,
            },
        }
        if metadata_filter:
            parameters["retrieval_configuration"]["filter"] = dict(metadata_filter)
        if session_id:
            parameters["session_id"] = session_id
        if operation == "retrieve_and_generate":
            effective_model_arn = model_arn or self.policy.generation_model_arn
            if not effective_model_arn:
                raise ValueError("model_arn is required for retrieve_and_generate")
            parameters["model_arn"] = effective_model_arn
            if generation_configuration:
                parameters["generation_configuration"] = dict(generation_configuration)

        payload = {
            "operation": operation,
            "parameters": parameters,
            "proposed_by": proposed_by,
            "context_revision": context_revision,
        }
        stable_id = request_id or "bedrock_kb_req_" + hashlib.sha256(
            _canonical_json(payload).encode("utf-8")
        ).hexdigest()[:16]
        return ExecutionRequest(
            request_id=stable_id,
            tool_name=f"bedrock.knowledge_base.{operation}",
            effect_type=EffectType.EXTERNAL_API,
            parameters=parameters,
            proposed_by=proposed_by,
            context_revision=context_revision,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    def authorize(
        self,
        request: ExecutionRequest,
        *,
        explicit_approval: bool = False,
        signed_by: str = "bago.bedrock-kb.policy",
    ) -> Permit:
        """Issue a permit scoped to one Knowledge Base and operation."""

        operation = request.tool_name.removeprefix("bedrock.knowledge_base.")
        kb_id = str(request.parameters.get("knowledge_base_id", ""))
        known_operation = operation in {"retrieve", "retrieve_and_generate"}
        has_model = bool(request.parameters.get("model_arn"))
        if request.effect_type is not EffectType.EXTERNAL_API or not known_operation:
            decision = AuthorizationDecision.DENY
            rationale = "Knowledge Base request is outside the EXTERNAL_API boundary"
        elif not self.policy.allows_knowledge_base(kb_id):
            decision = AuthorizationDecision.DENY
            rationale = f"Knowledge Base {kb_id!r} is outside the configured allowlist"
        elif operation == "retrieve_and_generate" and not has_model:
            decision = AuthorizationDecision.DENY
            rationale = "RetrieveAndGenerate requires an approved model ARN"
        elif explicit_approval or self.policy.auto_allow_external_api:
            decision = AuthorizationDecision.ALLOW
            rationale = "Knowledge Base query allowed by scoped provider policy"
        else:
            decision = AuthorizationDecision.REQUIRE_HUMAN
            rationale = "Knowledge Base external API call requires human authorization"

        now = datetime.now(timezone.utc)
        permit_key = f"{request.to_hash()}:{decision.value}:{signed_by}"
        permit_id = "bedrock_kb_permit_" + hashlib.sha256(
            permit_key.encode("utf-8")
        ).hexdigest()[:16]
        return Permit(
            permit_id=permit_id,
            request_id=request.request_id,
            decision=decision,
            rationale=rationale,
            constraints=[
                f"timeout_{self.policy.timeout_seconds:g}s",
                f"max_attempts_{self.policy.max_attempts}",
                f"knowledge_base_{kb_id}",
                f"max_results_{request.parameters['retrieval_configuration']['number_of_results']}",
            ],
            issued_at=now.isoformat(),
            expires_at=(now + timedelta(seconds=self.policy.timeout_seconds)).isoformat(),
            signed_by=signed_by,
        )

    def retrieve(
        self,
        request: ExecutionRequest,
        permit: Optional[Permit],
    ) -> BedrockKBResult:
        return self._execute(request, permit, operation="retrieve")

    def retrieve_and_generate(
        self,
        request: ExecutionRequest,
        permit: Optional[Permit],
    ) -> BedrockKBResult:
        return self._execute(request, permit, operation="retrieve_and_generate")

    def _execute(
        self,
        request: ExecutionRequest,
        permit: Optional[Permit],
        *,
        operation: str,
    ) -> BedrockKBResult:
        started = time.perf_counter()
        kb_id = str(request.parameters.get("knowledge_base_id", ""))
        evidence_base = (
            f"bedrock-kb://{self.policy.region_name}/{kb_id}/{operation}"
            f"#request={request.request_id}"
        )
        gate_error, decision = self._gate_error(request, permit, operation)
        if gate_error:
            return self._denied_result(
                request,
                permit,
                kb_id=kb_id,
                operation=operation,
                evidence_ref=evidence_base,
                reason=gate_error,
                decision=decision,
                started=started,
            )

        if not self._reserve_rate_limit():
            return self._failure_result(
                request,
                permit,
                kb_id=kb_id,
                operation=operation,
                evidence_ref=evidence_base,
                error_kind=BedrockErrorKind.RATE_LIMIT,
                error_message="Local Knowledge Base rate limit reached before transport call",
                called=False,
                attempts=0,
                started=started,
            )

        try:
            client = self._get_client()
        except Exception as error:
            return self._failure_result(
                request,
                permit,
                kb_id=kb_id,
                operation=operation,
                evidence_ref=evidence_base,
                error_kind=self._classify_error(error),
                error_message=f"{type(error).__name__}: {error}",
                called=False,
                attempts=0,
                started=started,
            )

        payload = self._payload_for(request, operation)
        attempts = 0
        for attempt in range(1, self.policy.max_attempts + 1):
            attempts = attempt
            try:
                if operation == "retrieve":
                    raw_response = client.retrieve(**payload)
                else:
                    raw_response = client.retrieve_and_generate(**payload)
                response = _mapping(raw_response)
                answer, hits, session_id = self._normalize_response(
                    response,
                    knowledge_base_id=kb_id,
                    operation=operation,
                )
                return self._success_result(
                    request,
                    permit,
                    kb_id=kb_id,
                    operation=operation,
                    evidence_ref=evidence_base,
                    answer=answer,
                    hits=hits,
                    session_id=session_id,
                    response=response,
                    attempts=attempts,
                    started=started,
                )
            except Exception as error:
                kind = self._classify_error(error)
                retryable = kind in {
                    BedrockErrorKind.TIMEOUT,
                    BedrockErrorKind.THROTTLE,
                    BedrockErrorKind.NETWORK,
                }
                if retryable and attempt < self.policy.max_attempts:
                    self._sleep(self.policy.backoff_seconds * (2 ** (attempt - 1)))
                    continue
                return self._failure_result(
                    request,
                    permit,
                    kb_id=kb_id,
                    operation=operation,
                    evidence_ref=evidence_base,
                    error_kind=kind,
                    error_message=f"{type(error).__name__}: {error}",
                    called=True,
                    attempts=attempts,
                    started=started,
                )

        raise AssertionError("Knowledge Base execution loop completed without a result")

    def _gate_error(
        self,
        request: ExecutionRequest,
        permit: Optional[Permit],
        operation: str,
    ) -> tuple[Optional[str], AuthorizationDecision]:
        if request.effect_type is not EffectType.EXTERNAL_API:
            return "DENY: Knowledge Base request must be EXTERNAL_API", AuthorizationDecision.DENY
        if request.tool_name != f"bedrock.knowledge_base.{operation}":
            return "DENY: request operation does not match the Knowledge Base call", AuthorizationDecision.DENY
        kb_id = str(request.parameters.get("knowledge_base_id", ""))
        if not self.policy.allows_knowledge_base(kb_id):
            return "DENY: Knowledge Base is outside the configured allowlist", AuthorizationDecision.DENY
        if operation == "retrieve_and_generate" and not request.parameters.get("model_arn"):
            return "DENY: RetrieveAndGenerate has no model ARN", AuthorizationDecision.DENY
        if permit is None:
            return "DENY: no permit supplied", AuthorizationDecision.DENY
        if permit.request_id != request.request_id:
            return "DENY: permit is bound to a different request", AuthorizationDecision.DENY
        if permit.decision is not AuthorizationDecision.ALLOW:
            return f"DENY: permit decision is {permit.decision.value}", permit.decision
        if not permit.is_valid():
            return "DENY: permit is expired", AuthorizationDecision.DENY
        return None, AuthorizationDecision.ALLOW

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

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            import boto3  # type: ignore[import-not-found]
            from botocore.config import Config  # type: ignore[import-not-found]
        except ImportError as error:
            raise BedrockConfigurationError(
                "boto3 is optional and is not installed; inject a client for offline use "
                "or install boto3 before a live Knowledge Base call"
            ) from error
        timeout = max(1, int(self.policy.timeout_seconds))
        config = Config(
            connect_timeout=timeout,
            read_timeout=timeout,
            retries={"mode": "standard", "max_attempts": 0},
        )
        return boto3.client(
            "bedrock-agent-runtime",
            region_name=self.policy.region_name,
            config=config,
        )

    @staticmethod
    def _payload_for(request: ExecutionRequest, operation: str) -> dict[str, Any]:
        params = request.parameters
        local_retrieval = _mapping(params["retrieval_configuration"])
        vector_config: dict[str, Any] = {
            "numberOfResults": local_retrieval["number_of_results"],
            "overrideSearchType": local_retrieval["override_search_type"],
        }
        if local_retrieval.get("filter"):
            vector_config["filter"] = dict(local_retrieval["filter"])
        retrieval_configuration = {"vectorSearchConfiguration": vector_config}
        if operation == "retrieve":
            return {
                "knowledgeBaseId": params["knowledge_base_id"],
                "retrievalQuery": {"text": params["query"]},
                "retrievalConfiguration": retrieval_configuration,
            }

        kb_configuration: dict[str, Any] = {
            "knowledgeBaseId": params["knowledge_base_id"],
            "modelArn": params["model_arn"],
            "retrievalConfiguration": retrieval_configuration,
        }
        if params.get("generation_configuration"):
            kb_configuration["generationConfiguration"] = dict(
                params["generation_configuration"]
            )
        payload: dict[str, Any] = {
            "input": {"text": params["query"]},
            "retrieveAndGenerateConfiguration": {
                "type": "KNOWLEDGE_BASE",
                "knowledgeBaseConfiguration": kb_configuration,
            },
        }
        if params.get("session_id"):
            payload["sessionId"] = params["session_id"]
        return payload

    @classmethod
    def _normalize_response(
        cls,
        response: Mapping[str, Any],
        *,
        knowledge_base_id: str,
        operation: str,
    ) -> tuple[str, tuple[BedrockKBHit, ...], Optional[str]]:
        if operation == "retrieve":
            raw_references = response.get("retrievalResults", [])
            answer = ""
        else:
            output = _mapping(response.get("output"))
            answer = str(output.get("text", "") or "")
            raw_references = []
            for citation in response.get("citations", []) or []:
                citation_data = _mapping(citation)
                raw_references.extend(citation_data.get("retrievedReferences", []) or [])
        hits: list[BedrockKBHit] = []
        seen: set[str] = set()
        for index, reference in enumerate(raw_references):
            hit = cls._normalize_hit(
                reference,
                knowledge_base_id=knowledge_base_id,
                index=index,
            )
            if hit.chunk_id in seen:
                continue
            seen.add(hit.chunk_id)
            hits.append(hit)
        return answer, tuple(hits), _optional_string(response.get("sessionId"))

    @staticmethod
    def _normalize_hit(
        reference: Any,
        *,
        knowledge_base_id: str,
        index: int,
    ) -> BedrockKBHit:
        data = _mapping(reference)
        content_data = _mapping(data.get("content"))
        content = str(content_data.get("text", data.get("text", "")) or "")
        metadata = _mapping(data.get("metadata"))
        source_uri = GovernedBedrockKnowledgeBaseAdapter._source_uri(data)
        raw_chunk_id = metadata.get("chunk_id") or metadata.get("chunkId")
        chunk_id = str(
            raw_chunk_id
            or hashlib.sha256(f"{source_uri}:{content}".encode("utf-8")).hexdigest()[:16]
            or f"reference-{index}"
        )
        raw_score = data.get("score")
        try:
            score = float(raw_score) if raw_score is not None else None
        except (TypeError, ValueError):
            score = None
        return BedrockKBHit(
            knowledge_base_id=knowledge_base_id,
            chunk_id=chunk_id,
            content=content,
            source_uri=source_uri,
            score=score,
            metadata=metadata,
        )

    @staticmethod
    def _source_uri(reference: Mapping[str, Any]) -> str:
        location = _mapping(reference.get("location"))
        for location_type in (
            "s3Location",
            "webLocation",
            "confluenceLocation",
            "sharePointLocation",
            "salesforceLocation",
            "customDocumentLocation",
        ):
            location_data = _mapping(location.get(location_type))
            for key in ("uri", "url", "id"):
                value = location_data.get(key)
                if isinstance(value, str) and value:
                    return value
        for key in ("source_uri", "sourceUri", "uri", "url"):
            value = reference.get(key)
            if isinstance(value, str) and value:
                return value
        return ""

    @staticmethod
    def _classify_error(error: BaseException) -> BedrockErrorKind:
        return BedrockProviderAdapter.classify_error(error)

    def _success_result(
        self,
        request: ExecutionRequest,
        permit: Permit,
        *,
        kb_id: str,
        operation: str,
        evidence_ref: str,
        answer: str,
        hits: tuple[BedrockKBHit, ...],
        session_id: Optional[str],
        response: Mapping[str, Any],
        attempts: int,
        started: float,
    ) -> BedrockKBResult:
        evidence_refs = tuple(hit.citation for hit in hits) or (evidence_ref,)
        receipt = BedrockKBReceipt(
            receipt_id=self._receipt_id(request, permit, "success", attempts),
            request_id=request.request_id,
            permit_id=permit.permit_id,
            knowledge_base_id=kb_id,
            operation=operation,
            decision=AuthorizationDecision.ALLOW,
            execution_outcome=ExecutionOutcome.SUCCESS,
            actual_effect={
                "called": True,
                "provider": "aws.bedrock",
                "service": "bedrock-agent-runtime",
                "operation": operation,
                "knowledge_base_id": kb_id,
                "result_count": len(hits),
                "attempts": attempts,
            },
            evidence_refs=evidence_refs,
            duration_ms=self._duration_ms(started),
            cost_usd=self.policy.cost_for(operation),
            result_count=len(hits),
            attempts=attempts,
        )
        return BedrockKBResult(answer, hits, session_id, response, receipt)

    def _failure_result(
        self,
        request: ExecutionRequest,
        permit: Permit,
        *,
        kb_id: str,
        operation: str,
        evidence_ref: str,
        error_kind: BedrockErrorKind,
        error_message: str,
        called: bool,
        attempts: int,
        started: float,
    ) -> BedrockKBResult:
        receipt = BedrockKBReceipt(
            receipt_id=self._receipt_id(request, permit, error_kind.value, attempts),
            request_id=request.request_id,
            permit_id=permit.permit_id,
            knowledge_base_id=kb_id,
            operation=operation,
            decision=AuthorizationDecision.ALLOW,
            execution_outcome=ExecutionOutcome.FAILURE,
            actual_effect={
                "called": called,
                "provider": "aws.bedrock",
                "service": "bedrock-agent-runtime",
                "operation": operation,
                "knowledge_base_id": kb_id,
                "attempts": attempts,
            },
            evidence_refs=(evidence_ref,),
            duration_ms=self._duration_ms(started),
            cost_usd=0.0,
            result_count=0,
            attempts=attempts,
            error_kind=error_kind,
            error_message=error_message,
        )
        return BedrockKBResult("", (), None, {}, receipt)

    def _denied_result(
        self,
        request: ExecutionRequest,
        permit: Optional[Permit],
        *,
        kb_id: str,
        operation: str,
        evidence_ref: str,
        reason: str,
        decision: AuthorizationDecision,
        started: float,
    ) -> BedrockKBResult:
        permit_id = permit.permit_id if permit else ""
        receipt = BedrockKBReceipt(
            receipt_id=self._receipt_id(request, permit, "denied", 0),
            request_id=request.request_id,
            permit_id=permit_id,
            knowledge_base_id=kb_id,
            operation=operation,
            decision=decision,
            execution_outcome=ExecutionOutcome.FAILURE,
            actual_effect={
                "called": False,
                "provider": "aws.bedrock",
                "service": "bedrock-agent-runtime",
                "operation": operation,
                "knowledge_base_id": kb_id,
            },
            evidence_refs=(evidence_ref,),
            duration_ms=self._duration_ms(started),
            cost_usd=0.0,
            result_count=0,
            attempts=0,
            error_kind=BedrockErrorKind.AUTHORIZATION,
            error_message=reason,
        )
        return BedrockKBResult("", (), None, {}, receipt)

    @staticmethod
    def _receipt_id(
        request: ExecutionRequest,
        permit: Optional[Permit],
        outcome: str,
        attempts: int,
    ) -> str:
        permit_id = permit.permit_id if permit else ""
        value = f"{request.request_id}:{permit_id}:{outcome}:{attempts}"
        return "bedrock_kb_receipt_" + hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def _duration_ms(started: float) -> int:
        return max(0, int((time.perf_counter() - started) * 1000))


BedrockKnowledgeBaseAdapter = GovernedBedrockKnowledgeBaseAdapter
BedrockKBAdapter = GovernedBedrockKnowledgeBaseAdapter


__all__ = [
    "BedrockKBAdapter",
    "BedrockKBHit",
    "BedrockKBReceipt",
    "BedrockKBResult",
    "BedrockKnowledgeBaseAdapter",
    "BedrockKnowledgeBasePolicy",
    "GovernedBedrockKnowledgeBaseAdapter",
]
