"""Governed AWS Bedrock provider adapter.

The adapter keeps the Bedrock SDK behind the BAGO execution boundary.  A
model call is represented as an ``ExecutionRequest`` and is sent to AWS only
when a matching, unexpired ``Permit`` allows the external API effect.

The AWS dependency is optional at import time.  Tests inject a small client
double, which makes the governance, retry and receipt contracts verifiable
without credentials or network access.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Iterable, Mapping, Optional

from orchestration.state_graph import (
    AuthorizationDecision,
    EffectType,
    ExecutionOutcome,
    ExecutionRequest,
    Permit,
)


class BedrockGovernanceError(PermissionError):
    """Raised for malformed requests that cannot enter the provider boundary."""


class BedrockConfigurationError(RuntimeError):
    """Raised when a real Bedrock client cannot be constructed."""


class BedrockErrorKind(str, Enum):
    """Stable provider error taxonomy used in receipts and evidence."""

    TIMEOUT = "TIMEOUT"
    THROTTLE = "THROTTLE"
    AUTHORIZATION = "AUTHORIZATION"
    VALIDATION = "VALIDATION"
    NETWORK = "NETWORK"
    RATE_LIMIT = "RATE_LIMIT"
    CONFIGURATION = "CONFIGURATION"
    UNKNOWN = "UNKNOWN"


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _nonnegative_int(value: Any, *, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class BedrockUsage:
    """Token usage returned by Converse or reconstructed from stream metadata."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0

    @classmethod
    def from_mapping(cls, value: Any) -> "BedrockUsage":
        data = _mapping(value)
        input_tokens = _nonnegative_int(
            data.get("inputTokens", data.get("input_tokens", 0))
        )
        output_tokens = _nonnegative_int(
            data.get("outputTokens", data.get("output_tokens", 0))
        )
        total = _nonnegative_int(data.get("totalTokens", data.get("total_tokens", 0)))
        if total == 0 and (input_tokens or output_tokens):
            total = input_tokens + output_tokens
        return cls(input_tokens, output_tokens, total)

    def to_dict(self) -> dict[str, int]:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
        }


@dataclass(frozen=True)
class BedrockProviderPolicy:
    """Local policy that bounds model, retry, timeout, quota and cost behavior."""

    region_name: str = "eu-west-1"
    timeout_seconds: float = 30.0
    max_attempts: int = 3
    backoff_seconds: float = 0.25
    allowed_model_ids: frozenset[str] = field(default_factory=frozenset)
    auto_allow_external_api: bool = True
    max_calls_per_window: Optional[int] = None
    rate_limit_window_seconds: float = 60.0
    input_cost_per_1k_tokens: float = 0.0
    output_cost_per_1k_tokens: float = 0.0

    def __post_init__(self) -> None:
        if not self.region_name.strip():
            raise ValueError("region_name is required")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.max_attempts <= 0 or self.max_attempts > 8:
            raise ValueError("max_attempts must be between 1 and 8")
        if self.backoff_seconds < 0:
            raise ValueError("backoff_seconds cannot be negative")
        if self.max_calls_per_window is not None and self.max_calls_per_window <= 0:
            raise ValueError("max_calls_per_window must be positive when configured")
        if self.rate_limit_window_seconds <= 0:
            raise ValueError("rate_limit_window_seconds must be positive")
        if self.input_cost_per_1k_tokens < 0 or self.output_cost_per_1k_tokens < 0:
            raise ValueError("cost rates cannot be negative")
        object.__setattr__(
            self,
            "allowed_model_ids",
            frozenset(str(model_id) for model_id in self.allowed_model_ids),
        )

    def allows_model(self, model_id: str) -> bool:
        """Return whether the configured model scope accepts ``model_id``.

        An empty set deliberately means "no local model allowlist" for this
        experimental adapter.  Production callers should configure an
        explicit allowlist and document the corresponding IAM resource scope.
        """

        return not self.allowed_model_ids or model_id in self.allowed_model_ids


@dataclass(frozen=True)
class BedrockCallReceipt:
    """Audit receipt emitted for allowed, denied and failed provider calls."""

    receipt_id: str
    request_id: str
    permit_id: str
    model_id: str
    operation: str
    decision: AuthorizationDecision
    execution_outcome: ExecutionOutcome
    actual_effect: Mapping[str, Any]
    evidence_refs: tuple[str, ...]
    duration_ms: int
    cost_usd: float
    usage: BedrockUsage
    attempts: int
    error_kind: Optional[BedrockErrorKind] = None
    error_message: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "request_id": self.request_id,
            "permit_id": self.permit_id,
            "model_id": self.model_id,
            "operation": self.operation,
            "decision": self.decision.value,
            "execution_outcome": self.execution_outcome.value,
            "actual_effect": dict(self.actual_effect),
            "evidence_refs": list(self.evidence_refs),
            "duration_ms": self.duration_ms,
            "cost_usd": self.cost_usd,
            "usage": self.usage.to_dict(),
            "attempts": self.attempts,
            "error_kind": self.error_kind.value if self.error_kind else None,
            "error_message": self.error_message,
        }


@dataclass(frozen=True)
class BedrockCallResult:
    """Normalized provider result plus the BAGO receipt for the same request."""

    text: str
    response: Mapping[str, Any]
    usage: BedrockUsage
    stop_reason: Optional[str]
    receipt: BedrockCallReceipt
    streamed_events: tuple[Mapping[str, Any], ...] = ()


class _PartialStreamError(RuntimeError):
    def __init__(self, cause: Exception, events: tuple[Mapping[str, Any], ...]) -> None:
        super().__init__(str(cause))
        self.cause = cause
        self.events = events


class GovernedBedrockAdapter:
    """BAGO gateway for AWS Bedrock Converse and ConverseStream."""

    def __init__(
        self,
        *,
        client: Any = None,
        policy: Optional[BedrockProviderPolicy] = None,
        sleep_fn: Optional[Callable[[float], None]] = None,
        monotonic_fn: Optional[Callable[[], float]] = None,
    ) -> None:
        self.policy = policy or BedrockProviderPolicy()
        self._client = client
        self._sleep = sleep_fn or time.sleep
        self._monotonic = monotonic_fn or time.monotonic
        self._rate_events: deque[float] = deque()

    def build_execution_request(
        self,
        model_id: str,
        messages: Iterable[Mapping[str, Any]],
        *,
        proposed_by: str,
        context_revision: str,
        system: Optional[Iterable[Mapping[str, Any]]] = None,
        inference_config: Optional[Mapping[str, Any]] = None,
        tool_config: Optional[Mapping[str, Any]] = None,
        request_id: Optional[str] = None,
        operation: str = "converse",
    ) -> ExecutionRequest:
        """Create a provider request without invoking the external client."""

        if not model_id.strip():
            raise ValueError("model_id is required")
        if not proposed_by.strip() or not context_revision.strip():
            raise ValueError("proposed_by and context_revision are required")
        if operation not in {"converse", "converse_stream"}:
            raise ValueError("operation must be converse or converse_stream")

        normalized_messages = self._normalize_messages(messages)
        normalized_system = self._normalize_system(system)
        parameters: dict[str, Any] = {
            "model_id": model_id,
            "messages": normalized_messages,
        }
        if normalized_system:
            parameters["system"] = normalized_system
        if inference_config:
            parameters["inference_config"] = dict(inference_config)
        if tool_config:
            parameters["tool_config"] = dict(tool_config)

        stable_payload = {
            "operation": operation,
            "parameters": parameters,
            "proposed_by": proposed_by,
            "context_revision": context_revision,
        }
        stable_id = request_id or "bedrock_req_" + hashlib.sha256(
            _canonical_json(stable_payload).encode("utf-8")
        ).hexdigest()[:16]
        return ExecutionRequest(
            request_id=stable_id,
            tool_name=f"bedrock.{operation}",
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
        signed_by: str = "bago.bedrock.policy",
    ) -> Permit:
        """Issue a permit whose scope is bound to one model request."""

        model_id = str(request.parameters.get("model_id", ""))
        operation_is_known = request.tool_name in {
            "bedrock.converse",
            "bedrock.converse_stream",
        }
        if request.effect_type is not EffectType.EXTERNAL_API or not operation_is_known:
            decision = AuthorizationDecision.DENY
            rationale = "Bedrock request is outside the EXTERNAL_API provider boundary"
        elif not self.policy.allows_model(model_id):
            decision = AuthorizationDecision.DENY
            rationale = f"Model {model_id!r} is outside the configured Bedrock allowlist"
        elif explicit_approval or self.policy.auto_allow_external_api:
            decision = AuthorizationDecision.ALLOW
            rationale = "Bedrock model call allowed by scoped provider policy"
        else:
            decision = AuthorizationDecision.REQUIRE_HUMAN
            rationale = "Bedrock external API call requires explicit human authorization"

        now = datetime.now(timezone.utc)
        permit_key = f"{request.to_hash()}:{decision.value}:{signed_by}"
        permit_id = "bedrock_permit_" + hashlib.sha256(
            permit_key.encode("utf-8")
        ).hexdigest()[:16]
        constraints = [
            f"timeout_{self.policy.timeout_seconds:g}s",
            f"max_attempts_{self.policy.max_attempts}",
            f"model_{model_id}",
        ]
        return Permit(
            permit_id=permit_id,
            request_id=request.request_id,
            decision=decision,
            rationale=rationale,
            constraints=constraints,
            issued_at=now.isoformat(),
            expires_at=(now + timedelta(seconds=self.policy.timeout_seconds)).isoformat(),
            signed_by=signed_by,
        )

    def converse(
        self,
        request: ExecutionRequest,
        permit: Optional[Permit],
    ) -> BedrockCallResult:
        """Execute one governed, non-streaming Converse request."""

        return self._execute(request, permit, operation="converse")

    def converse_stream(
        self,
        request: ExecutionRequest,
        permit: Optional[Permit],
    ) -> BedrockCallResult:
        """Execute one governed ConverseStream request and collect its events."""

        return self._execute(request, permit, operation="converse_stream")

    @staticmethod
    def classify_error(error: BaseException) -> BedrockErrorKind:
        """Map SDK and transport errors to a stable, provider-neutral taxonomy."""

        if isinstance(error, BedrockConfigurationError):
            return BedrockErrorKind.CONFIGURATION
        if isinstance(error, (TimeoutError,)):  # includes common socket timeouts
            return BedrockErrorKind.TIMEOUT

        response = getattr(error, "response", None)
        response_data = _mapping(response)
        error_data = _mapping(response_data.get("Error"))
        code = str(
            getattr(error, "error_code", "")
            or getattr(error, "code", "")
            or error_data.get("Code", "")
            or type(error).__name__
        ).lower()
        message = str(error).lower()
        combined = f"{code} {message}"

        if any(token in combined for token in ("timeout", "requestexpired", "readtimeout")):
            return BedrockErrorKind.TIMEOUT
        if any(
            token in combined
            for token in (
                "throttl",
                "toomanyrequests",
                "provisionedthroughput",
                "serviceunavailable",
                "slowdown",
                "modelnotready",
            )
        ):
            return BedrockErrorKind.THROTTLE
        if any(
            token in combined
            for token in (
                "accessdenied",
                "unauthorized",
                "unrecognizedclient",
                "invalidsignature",
                "expiredtoken",
                "forbidden",
            )
        ):
            return BedrockErrorKind.AUTHORIZATION
        if "validation" in combined or "invalidrequest" in combined:
            return BedrockErrorKind.VALIDATION
        if isinstance(error, (ConnectionError, OSError)) or any(
            token in combined
            for token in ("endpointconnection", "connectionreset", "network")
        ):
            return BedrockErrorKind.NETWORK
        return BedrockErrorKind.UNKNOWN

    def estimate_cost(self, usage: BedrockUsage) -> float:
        """Estimate cost from configured rates; zero means no rates were supplied."""

        return round(
            usage.input_tokens * self.policy.input_cost_per_1k_tokens / 1000
            + usage.output_tokens * self.policy.output_cost_per_1k_tokens / 1000,
            8,
        )

    def _execute(
        self,
        request: ExecutionRequest,
        permit: Optional[Permit],
        *,
        operation: str,
    ) -> BedrockCallResult:
        started = time.perf_counter()
        model_id = str(request.parameters.get("model_id", ""))
        evidence_ref = (
            f"bedrock://{self.policy.region_name}/{model_id}/{operation}"
            f"#request={request.request_id}"
        )
        gate_error, decision = self._gate_error(request, permit, operation)
        if gate_error:
            return self._denied_result(
                request,
                permit,
                model_id=model_id,
                operation=operation,
                evidence_ref=evidence_ref,
                reason=gate_error,
                decision=decision,
                started=started,
            )

        if not self._reserve_rate_limit():
            return self._failure_result(
                request,
                permit,
                model_id=model_id,
                operation=operation,
                evidence_ref=evidence_ref,
                error_kind=BedrockErrorKind.RATE_LIMIT,
                error_message="Local Bedrock rate limit reached before transport call",
                called=False,
                attempts=0,
                started=started,
            )

        try:
            client = self._get_client()
        except Exception as error:
            kind = self.classify_error(error)
            return self._failure_result(
                request,
                permit,
                model_id=model_id,
                operation=operation,
                evidence_ref=evidence_ref,
                error_kind=kind,
                error_message=f"{type(error).__name__}: {error}",
                called=False,
                attempts=0,
                started=started,
            )

        payload = self._payload_for(request)
        attempts = 0
        for attempt in range(1, self.policy.max_attempts + 1):
            attempts = attempt
            try:
                if operation == "converse":
                    raw_response = client.converse(**payload)
                    response = _mapping(raw_response)
                    text = self._extract_text(response)
                    usage = BedrockUsage.from_mapping(response.get("usage"))
                    stop_reason = self._optional_string(response.get("stopReason"))
                    events: tuple[Mapping[str, Any], ...] = ()
                else:
                    raw_response = client.converse_stream(**payload)
                    response, text, usage, stop_reason, events = self._consume_stream(
                        raw_response
                    )
                return self._success_result(
                    request,
                    permit,
                    model_id=model_id,
                    operation=operation,
                    evidence_ref=evidence_ref,
                    response=response,
                    text=text,
                    usage=usage,
                    stop_reason=stop_reason,
                    events=events,
                    attempts=attempts,
                    started=started,
                )
            except _PartialStreamError as error:
                kind = self.classify_error(error.cause)
                return self._failure_result(
                    request,
                    permit,
                    model_id=model_id,
                    operation=operation,
                    evidence_ref=evidence_ref,
                    error_kind=kind,
                    error_message=f"{type(error.cause).__name__}: {error.cause}",
                    called=True,
                    attempts=attempts,
                    started=started,
                    streamed_events=error.events,
                )
            except Exception as error:
                kind = self.classify_error(error)
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
                    model_id=model_id,
                    operation=operation,
                    evidence_ref=evidence_ref,
                    error_kind=kind,
                    error_message=f"{type(error).__name__}: {error}",
                    called=True,
                    attempts=attempts,
                    started=started,
                )

        raise AssertionError("Bedrock execution loop completed without a result")

    def _gate_error(
        self,
        request: ExecutionRequest,
        permit: Optional[Permit],
        operation: str,
    ) -> tuple[Optional[str], AuthorizationDecision]:
        if request.effect_type is not EffectType.EXTERNAL_API:
            return "DENY: Bedrock request must be classified as EXTERNAL_API", AuthorizationDecision.DENY
        if request.tool_name != f"bedrock.{operation}":
            return "DENY: request operation does not match the provider call", AuthorizationDecision.DENY
        if not self.policy.allows_model(str(request.parameters.get("model_id", ""))):
            return "DENY: model is outside the configured Bedrock allowlist", AuthorizationDecision.DENY
        if permit is None:
            return "DENY: no permit supplied", AuthorizationDecision.DENY
        if permit.request_id != request.request_id:
            return "DENY: permit is bound to a different request", AuthorizationDecision.DENY
        if permit.decision is not AuthorizationDecision.ALLOW:
            return (
                f"DENY: permit decision is {permit.decision.value}",
                permit.decision,
            )
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
                "or install boto3 before a live AWS call"
            ) from error

        timeout = max(1, int(self.policy.timeout_seconds))
        config = Config(
            connect_timeout=timeout,
            read_timeout=timeout,
            retries={"mode": "standard", "max_attempts": 0},
        )
        return boto3.client(
            "bedrock-runtime",
            region_name=self.policy.region_name,
            config=config,
        )

    @staticmethod
    def _normalize_messages(
        messages: Iterable[Mapping[str, Any]],
    ) -> tuple[dict[str, Any], ...]:
        normalized = tuple(dict(message) for message in messages)
        if not normalized:
            raise ValueError("at least one Bedrock message is required")
        for message in normalized:
            if message.get("role") not in {"user", "assistant"}:
                raise ValueError("Bedrock messages require role=user or role=assistant")
            if not isinstance(message.get("content"), list) or not message["content"]:
                raise ValueError("Bedrock messages require a non-empty content list")
        return normalized

    @staticmethod
    def _normalize_system(
        system: Optional[Iterable[Mapping[str, Any]]],
    ) -> tuple[dict[str, Any], ...]:
        if system is None:
            return ()
        normalized = tuple(dict(item) for item in system)
        if any(not item for item in normalized):
            raise ValueError("Bedrock system content blocks cannot be empty")
        return normalized

    @staticmethod
    def _payload_for(request: ExecutionRequest) -> dict[str, Any]:
        params = request.parameters
        payload: dict[str, Any] = {
            "modelId": params["model_id"],
            "messages": [dict(message) for message in params["messages"]],
        }
        if params.get("system"):
            payload["system"] = [dict(item) for item in params["system"]]
        if params.get("inference_config"):
            payload["inferenceConfig"] = dict(params["inference_config"])
        if params.get("tool_config"):
            payload["toolConfig"] = dict(params["tool_config"])
        return payload

    @staticmethod
    def _extract_text(response: Mapping[str, Any]) -> str:
        output = _mapping(response.get("output"))
        message = _mapping(output.get("message"))
        content = message.get("content", [])
        parts = []
        if isinstance(content, list):
            for item in content:
                if isinstance(item, Mapping) and isinstance(item.get("text"), str):
                    parts.append(item["text"])
        return "".join(parts)

    @staticmethod
    def _optional_string(value: Any) -> Optional[str]:
        return value if isinstance(value, str) else None

    @classmethod
    def _consume_stream(
        cls,
        raw_response: Any,
    ) -> tuple[dict[str, Any], str, BedrockUsage, Optional[str], tuple[Mapping[str, Any], ...]]:
        response = _mapping(raw_response)
        stream = response.get("stream", ())
        events: list[Mapping[str, Any]] = []
        text_parts: list[str] = []
        usage = BedrockUsage()
        stop_reason: Optional[str] = None
        try:
            for event in stream:
                event_data = _mapping(event)
                events.append(event_data)
                delta_container = _mapping(event_data.get("contentBlockDelta"))
                delta = _mapping(delta_container.get("delta"))
                if isinstance(delta.get("text"), str):
                    text_parts.append(delta["text"])
                stop_container = _mapping(event_data.get("messageStop"))
                if isinstance(stop_container.get("stopReason"), str):
                    stop_reason = stop_container["stopReason"]
                metadata = _mapping(event_data.get("metadata"))
                if metadata.get("usage") is not None:
                    usage = BedrockUsage.from_mapping(metadata["usage"])
        except Exception as error:
            raise _PartialStreamError(error, tuple(events)) from error
        return (
            {"events": [dict(event) for event in events]},
            "".join(text_parts),
            usage,
            stop_reason,
            tuple(events),
        )

    def _success_result(
        self,
        request: ExecutionRequest,
        permit: Permit,
        *,
        model_id: str,
        operation: str,
        evidence_ref: str,
        response: Mapping[str, Any],
        text: str,
        usage: BedrockUsage,
        stop_reason: Optional[str],
        events: tuple[Mapping[str, Any], ...],
        attempts: int,
        started: float,
    ) -> BedrockCallResult:
        cost = self.estimate_cost(usage)
        receipt = BedrockCallReceipt(
            receipt_id=self._receipt_id(request, permit, "success", attempts),
            request_id=request.request_id,
            permit_id=permit.permit_id,
            model_id=model_id,
            operation=operation,
            decision=AuthorizationDecision.ALLOW,
            execution_outcome=ExecutionOutcome.SUCCESS,
            actual_effect={
                "called": True,
                "provider": "aws.bedrock",
                "operation": operation,
                "model_id": model_id,
                "attempts": attempts,
            },
            evidence_refs=(evidence_ref,),
            duration_ms=self._duration_ms(started),
            cost_usd=cost,
            usage=usage,
            attempts=attempts,
        )
        return BedrockCallResult(text, response, usage, stop_reason, receipt, events)

    def _failure_result(
        self,
        request: ExecutionRequest,
        permit: Permit,
        *,
        model_id: str,
        operation: str,
        evidence_ref: str,
        error_kind: BedrockErrorKind,
        error_message: str,
        called: bool,
        attempts: int,
        started: float,
        streamed_events: tuple[Mapping[str, Any], ...] = (),
    ) -> BedrockCallResult:
        receipt = BedrockCallReceipt(
            receipt_id=self._receipt_id(request, permit, error_kind.value, attempts),
            request_id=request.request_id,
            permit_id=permit.permit_id,
            model_id=model_id,
            operation=operation,
            decision=AuthorizationDecision.ALLOW,
            execution_outcome=ExecutionOutcome.FAILURE,
            actual_effect={
                "called": called,
                "provider": "aws.bedrock",
                "operation": operation,
                "model_id": model_id,
                "attempts": attempts,
            },
            evidence_refs=(evidence_ref,),
            duration_ms=self._duration_ms(started),
            cost_usd=0.0,
            usage=BedrockUsage(),
            attempts=attempts,
            error_kind=error_kind,
            error_message=error_message,
        )
        return BedrockCallResult(
            text="",
            response={"events": [dict(event) for event in streamed_events]}
            if streamed_events
            else {},
            usage=BedrockUsage(),
            stop_reason=None,
            receipt=receipt,
            streamed_events=streamed_events,
        )

    def _denied_result(
        self,
        request: ExecutionRequest,
        permit: Optional[Permit],
        *,
        model_id: str,
        operation: str,
        evidence_ref: str,
        reason: str,
        decision: AuthorizationDecision,
        started: float,
    ) -> BedrockCallResult:
        permit_id = permit.permit_id if permit else ""
        receipt = BedrockCallReceipt(
            receipt_id=self._receipt_id(request, permit, "denied", 0),
            request_id=request.request_id,
            permit_id=permit_id,
            model_id=model_id,
            operation=operation,
            decision=decision,
            execution_outcome=ExecutionOutcome.FAILURE,
            actual_effect={
                "called": False,
                "provider": "aws.bedrock",
                "operation": operation,
                "model_id": model_id,
            },
            evidence_refs=(evidence_ref,),
            duration_ms=self._duration_ms(started),
            cost_usd=0.0,
            usage=BedrockUsage(),
            attempts=0,
            error_kind=BedrockErrorKind.AUTHORIZATION,
            error_message=reason,
        )
        return BedrockCallResult("", {}, BedrockUsage(), None, receipt)

    @staticmethod
    def _receipt_id(
        request: ExecutionRequest,
        permit: Optional[Permit],
        outcome: str,
        attempts: int,
    ) -> str:
        permit_id = permit.permit_id if permit else ""
        value = f"{request.request_id}:{permit_id}:{outcome}:{attempts}"
        return "bedrock_receipt_" + hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def _duration_ms(started: float) -> int:
        return max(0, int((time.perf_counter() - started) * 1000))


BedrockProviderAdapter = GovernedBedrockAdapter


__all__ = [
    "BedrockCallReceipt",
    "BedrockCallResult",
    "BedrockConfigurationError",
    "BedrockErrorKind",
    "BedrockGovernanceError",
    "BedrockProviderAdapter",
    "BedrockProviderPolicy",
    "BedrockUsage",
    "GovernedBedrockAdapter",
]
