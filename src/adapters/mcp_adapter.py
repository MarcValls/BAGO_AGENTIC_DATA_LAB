"""Governed MCP capability discovery and execution.

MCP discovery is treated as untrusted input.  A discovered tool becomes
callable only after a BAGO-side registration assigns its effect type and a
request receives a valid permit.  The adapter deliberately keeps protocol
transport separate from governance so an MCP session can be replaced by a
test double or another transport without changing the policy boundary.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Mapping, Optional

from orchestration.state_graph import (
    AuthorizationDecision,
    EffectType,
    ExecutionOutcome,
    ExecutionRequest,
    Permit,
)


class MCPGovernanceError(PermissionError):
    """Raised when a capability violates the BAGO MCP boundary."""


def _field(value: Any, *names: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        for name in names:
            if name in value:
                return value[name]
    for name in names:
        if hasattr(value, name):
            return getattr(value, name)
    return default


def _model_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, "model_dump"):
        return dict(value.model_dump(by_alias=True))
    if hasattr(value, "dict"):
        return dict(value.dict())
    return {}


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _type_matches(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, Mapping)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "null":
        return value is None
    return True


def _validate_arguments(schema: Mapping[str, Any], arguments: Mapping[str, Any]) -> None:
    """Validate the small JSON-Schema subset needed at the governance edge."""

    if not isinstance(arguments, Mapping):
        raise MCPGovernanceError("MCP arguments must be a JSON object")

    required = schema.get("required", [])
    missing = [name for name in required if name not in arguments]
    if missing:
        raise MCPGovernanceError(f"Missing required MCP arguments: {', '.join(missing)}")

    properties = schema.get("properties", {})
    if not isinstance(properties, Mapping):
        properties = {}
    if schema.get("additionalProperties") is False:
        unknown = sorted(set(arguments) - set(properties))
        if unknown:
            raise MCPGovernanceError(f"Unknown MCP arguments: {', '.join(unknown)}")

    for name, value in arguments.items():
        definition = properties.get(name, {})
        if not isinstance(definition, Mapping):
            continue
        expected = definition.get("type")
        if expected and not _type_matches(value, str(expected)):
            raise MCPGovernanceError(
                f"MCP argument {name!r} must have type {expected!r}"
            )
        allowed = definition.get("enum")
        if allowed is not None and value not in allowed:
            raise MCPGovernanceError(f"MCP argument {name!r} is outside its enum")


@dataclass(frozen=True)
class CapabilityDescriptor:
    """Untrusted metadata obtained from MCP ``tools/list``."""

    server_name: str
    name: str
    description: str = ""
    input_schema: Mapping[str, Any] = field(default_factory=dict)
    output_schema: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.server_name.strip() or not self.name.strip():
            raise ValueError("server_name and name are required")
        object.__setattr__(self, "input_schema", dict(self.input_schema or {}))
        object.__setattr__(self, "output_schema", dict(self.output_schema or {}))

    @classmethod
    def from_tool(cls, tool: Any, *, server_name: str) -> "CapabilityDescriptor":
        name = _field(tool, "name", default="")
        if not isinstance(name, str) or not name.strip():
            raise MCPGovernanceError("MCP discovery returned a tool without a name")
        return cls(
            server_name=server_name,
            name=name,
            description=str(_field(tool, "description", default="") or ""),
            input_schema=_field(
                tool,
                "inputSchema",
                "input_schema",
                default={"type": "object", "properties": {}},
            ),
            output_schema=_field(tool, "outputSchema", "output_schema", default={}),
        )

    @property
    def fingerprint(self) -> str:
        payload = _canonical_json(self._payload()).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()[:16]

    def _payload(self) -> dict[str, Any]:
        return {
            "server_name": self.server_name,
            "name": self.name,
            "description": self.description,
            "input_schema": dict(self.input_schema),
            "output_schema": dict(self.output_schema),
        }

    def to_dict(self) -> dict[str, Any]:
        payload = self._payload()
        payload["fingerprint"] = self.fingerprint
        return payload


@dataclass(frozen=True)
class RegisteredCapability:
    """A discovered capability explicitly classified by BAGO."""

    descriptor: CapabilityDescriptor
    effect_type: EffectType
    approved_by: str
    registered_at: str
    constraints: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "descriptor": self.descriptor.to_dict(),
            "effect_type": self.effect_type.value,
            "approved_by": self.approved_by,
            "registered_at": self.registered_at,
            "constraints": list(self.constraints),
        }


class CapabilityRegistry:
    """Separates MCP discovery from explicit capability registration."""

    def __init__(self) -> None:
        self._discovered: dict[str, CapabilityDescriptor] = {}
        self._registered: dict[str, RegisteredCapability] = {}

    def discover(
        self,
        tools: Iterable[Any],
        *,
        server_name: str,
    ) -> tuple[CapabilityDescriptor, ...]:
        discovered: list[CapabilityDescriptor] = []
        for tool in tools:
            descriptor = CapabilityDescriptor.from_tool(tool, server_name=server_name)
            previous = self._discovered.get(descriptor.name)
            if previous and previous.to_dict() != descriptor.to_dict():
                raise MCPGovernanceError(
                    f"MCP tool {descriptor.name!r} changed schema during discovery"
                )
            self._discovered[descriptor.name] = descriptor
            discovered.append(descriptor)
        return tuple(discovered)

    @property
    def discovered(self) -> tuple[CapabilityDescriptor, ...]:
        return tuple(self._discovered[name] for name in sorted(self._discovered))

    @property
    def registered(self) -> tuple[RegisteredCapability, ...]:
        return tuple(self._registered[name] for name in sorted(self._registered))

    def require_discovered(self, tool_name: str) -> CapabilityDescriptor:
        try:
            return self._discovered[tool_name]
        except KeyError as error:
            raise MCPGovernanceError(
                f"DENY: MCP tool {tool_name!r} was not discovered"
            ) from error

    def register(
        self,
        tool_name: str,
        *,
        effect_type: EffectType | str,
        approved_by: str,
        constraints: Iterable[str] = (),
    ) -> RegisteredCapability:
        descriptor = self.require_discovered(tool_name)
        if not approved_by.strip():
            raise ValueError("approved_by is required for MCP registration")
        normalized_effect = EffectType(effect_type)
        current = self._registered.get(tool_name)
        if current and (
            current.effect_type != normalized_effect
            or current.descriptor.fingerprint != descriptor.fingerprint
        ):
            raise MCPGovernanceError(
                f"MCP tool {tool_name!r} cannot change classification silently"
            )
        registration = RegisteredCapability(
            descriptor=descriptor,
            effect_type=normalized_effect,
            approved_by=approved_by,
            registered_at=datetime.now(timezone.utc).isoformat(),
            constraints=tuple(constraints),
        )
        self._registered[tool_name] = registration
        return registration

    def require_registered(self, tool_name: str) -> RegisteredCapability:
        try:
            return self._registered[tool_name]
        except KeyError as error:
            raise MCPGovernanceError(
                f"DENY: MCP tool {tool_name!r} is discovered but not registered"
            ) from error


@dataclass(frozen=True)
class MCPGovernancePolicy:
    """Policy for automatic permits at the MCP boundary."""

    auto_allow_effects: frozenset[EffectType] = field(
        default_factory=lambda: frozenset({EffectType.READ})
    )
    timeout_seconds: int = 30

    def __post_init__(self) -> None:
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        object.__setattr__(
            self,
            "auto_allow_effects",
            frozenset(EffectType(effect) for effect in self.auto_allow_effects),
        )


@dataclass(frozen=True)
class MCPCallReceipt:
    """Audit receipt for an allowed, denied or failed MCP call."""

    receipt_id: str
    request_id: str
    permit_id: str
    server_name: str
    tool_name: str
    decision: AuthorizationDecision
    execution_outcome: ExecutionOutcome
    actual_effect: Mapping[str, Any]
    evidence_refs: tuple[str, ...]
    duration_ms: int
    result: Any = None
    error_message: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "request_id": self.request_id,
            "permit_id": self.permit_id,
            "server_name": self.server_name,
            "tool_name": self.tool_name,
            "decision": self.decision.value,
            "execution_outcome": self.execution_outcome.value,
            "actual_effect": dict(self.actual_effect),
            "evidence_refs": list(self.evidence_refs),
            "duration_ms": self.duration_ms,
            "result": self.result,
            "error_message": self.error_message,
        }


class GovernedMCPAdapter:
    """BAGO-side adapter for MCP discovery, authorization and invocation."""

    def __init__(
        self,
        server_name: str,
        *,
        registry: Optional[CapabilityRegistry] = None,
        policy: Optional[MCPGovernancePolicy] = None,
    ) -> None:
        if not server_name.strip():
            raise ValueError("server_name is required")
        self.server_name = server_name
        self.registry = registry or CapabilityRegistry()
        self.policy = policy or MCPGovernancePolicy()

    def discover_tools(self, tools: Iterable[Any]) -> tuple[CapabilityDescriptor, ...]:
        return self.registry.discover(tools, server_name=self.server_name)

    def register_tool(
        self,
        tool_name: str,
        *,
        effect_type: EffectType | str,
        approved_by: str,
        constraints: Iterable[str] = (),
    ) -> RegisteredCapability:
        return self.registry.register(
            tool_name,
            effect_type=effect_type,
            approved_by=approved_by,
            constraints=constraints,
        )

    def build_execution_request(
        self,
        tool_name: str,
        arguments: Mapping[str, Any],
        *,
        proposed_by: str,
        context_revision: str,
        request_id: Optional[str] = None,
    ) -> ExecutionRequest:
        registered = self.registry.require_registered(tool_name)
        _validate_arguments(registered.descriptor.input_schema, arguments)
        if not proposed_by.strip() or not context_revision.strip():
            raise ValueError("proposed_by and context_revision are required")
        payload = {
            "server": self.server_name,
            "tool": tool_name,
            "arguments": dict(arguments),
            "context_revision": context_revision,
        }
        stable_id = request_id or "mcp_req_" + hashlib.sha256(
            _canonical_json(payload).encode("utf-8")
        ).hexdigest()[:16]
        return ExecutionRequest(
            request_id=stable_id,
            tool_name=tool_name,
            effect_type=registered.effect_type,
            parameters=dict(arguments),
            proposed_by=proposed_by,
            context_revision=context_revision,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    def authorize(
        self,
        request: ExecutionRequest,
        *,
        explicit_approval: bool = False,
        signed_by: str = "bago.mcp.policy",
    ) -> Permit:
        registered = self.registry.require_registered(request.tool_name)
        if registered.effect_type != request.effect_type:
            raise MCPGovernanceError(
                f"DENY: effect classification changed for {request.tool_name!r}"
            )
        decision = (
            AuthorizationDecision.ALLOW
            if explicit_approval or request.effect_type in self.policy.auto_allow_effects
            else AuthorizationDecision.REQUIRE_HUMAN
        )
        now = datetime.now(timezone.utc)
        rationale = (
            "Registered MCP capability is within the automatic policy"
            if decision is AuthorizationDecision.ALLOW
            else "MCP effect requires explicit human authorization"
        )
        permit_key = f"{request.to_hash()}:{decision.value}:{signed_by}"
        permit_id = "mcp_permit_" + hashlib.sha256(permit_key.encode("utf-8")).hexdigest()[:16]
        return Permit(
            permit_id=permit_id,
            request_id=request.request_id,
            decision=decision,
            rationale=rationale,
            constraints=(
                f"timeout_{self.policy.timeout_seconds}s",
                "registered_capability",
                f"server_{self.server_name}",
            ),
            issued_at=now.isoformat(),
            expires_at=(now + timedelta(seconds=self.policy.timeout_seconds)).isoformat(),
            signed_by=signed_by,
        )

    async def call(
        self,
        session: Any,
        request: ExecutionRequest,
        permit: Optional[Permit],
    ) -> MCPCallReceipt:
        started = time.perf_counter()
        evidence_ref = (
            f"mcp://{self.server_name}/tools/{request.tool_name}"
            f"#request={request.request_id}"
        )
        try:
            registered = self.registry.require_registered(request.tool_name)
        except MCPGovernanceError as error:
            return self._denied_receipt(request, evidence_ref, str(error), started)

        denial: Optional[str] = None
        denial_decision = AuthorizationDecision.DENY
        if registered.effect_type != request.effect_type:
            denial = "DENY: request effect does not match registered capability"
        elif permit is None:
            denial = "DENY: no permit supplied"
        elif permit.request_id != request.request_id:
            denial = "DENY: permit is bound to a different request"
        elif permit.decision is not AuthorizationDecision.ALLOW:
            denial = f"DENY: permit decision is {permit.decision.value}"
            denial_decision = permit.decision
        elif not permit.is_valid():
            denial = "DENY: permit is expired"

        if denial:
            return self._denied_receipt(
                request,
                evidence_ref,
                denial,
                started,
                permit_id=permit.permit_id if permit else "",
                decision=denial_decision,
            )

        try:
            result = await session.call_tool(
                name=request.tool_name,
                arguments=request.parameters,
            )
            serialized = _model_dict(result) or {"repr": repr(result)}
            is_error = bool(_field(result, "isError", "is_error", default=False))
            return MCPCallReceipt(
                receipt_id="mcp_receipt_" + hashlib.sha256(
                    f"{request.request_id}:{permit.permit_id}".encode("utf-8")
                ).hexdigest()[:16],
                request_id=request.request_id,
                permit_id=permit.permit_id,
                server_name=self.server_name,
                tool_name=request.tool_name,
                decision=AuthorizationDecision.ALLOW,
                execution_outcome=(
                    ExecutionOutcome.FAILURE if is_error else ExecutionOutcome.SUCCESS
                ),
                actual_effect={
                    "called": True,
                    "server": self.server_name,
                    "tool": request.tool_name,
                },
                evidence_refs=(evidence_ref,),
                duration_ms=max(0, int((time.perf_counter() - started) * 1000)),
                result=serialized,
                error_message="MCP server returned isError=true" if is_error else None,
            )
        except Exception as error:  # transport/provider failures become receipts
            return MCPCallReceipt(
                receipt_id="mcp_receipt_" + hashlib.sha256(
                    f"{request.request_id}:{permit.permit_id}".encode("utf-8")
                ).hexdigest()[:16],
                request_id=request.request_id,
                permit_id=permit.permit_id,
                server_name=self.server_name,
                tool_name=request.tool_name,
                decision=AuthorizationDecision.ALLOW,
                execution_outcome=ExecutionOutcome.FAILURE,
                actual_effect={
                    "called": True,
                    "server": self.server_name,
                    "tool": request.tool_name,
                },
                evidence_refs=(evidence_ref,),
                duration_ms=max(0, int((time.perf_counter() - started) * 1000)),
                error_message=f"{type(error).__name__}: {error}",
            )

    def _denied_receipt(
        self,
        request: ExecutionRequest,
        evidence_ref: str,
        reason: str,
        started: float,
        *,
        permit_id: str = "",
        decision: AuthorizationDecision = AuthorizationDecision.DENY,
    ) -> MCPCallReceipt:
        return MCPCallReceipt(
            receipt_id="mcp_receipt_" + hashlib.sha256(
                f"{request.request_id}:{permit_id}:{reason}".encode("utf-8")
            ).hexdigest()[:16],
            request_id=request.request_id,
            permit_id=permit_id,
            server_name=self.server_name,
            tool_name=request.tool_name,
            decision=decision,
            execution_outcome=ExecutionOutcome.FAILURE,
            actual_effect={
                "called": False,
                "server": self.server_name,
                "tool": request.tool_name,
            },
            evidence_refs=(evidence_ref,),
            duration_ms=max(0, int((time.perf_counter() - started) * 1000)),
            error_message=reason,
        )


__all__ = [
    "CapabilityDescriptor",
    "CapabilityRegistry",
    "GovernedMCPAdapter",
    "MCPCallReceipt",
    "MCPGovernanceError",
    "MCPGovernancePolicy",
    "RegisteredCapability",
]
