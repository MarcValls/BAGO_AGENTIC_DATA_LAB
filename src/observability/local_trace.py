"""Deterministic local traces assembled from governed run evidence.

This module deliberately does not become an authority or a transport.  It
normalizes the evidence already produced by the governed agent and sandbox so
that a local evaluator can inspect one trace without requiring a collector,
SaaS account or network access.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping, TYPE_CHECKING

if TYPE_CHECKING:
    from agent.governed_knowledge_agent import AgentRun
    from sandbox.receipt import SandboxExecutionResult


class TraceKind(str, Enum):
    WORKFLOW = "workflow"
    RETRIEVAL = "retrieval"
    REASONING = "reasoning"
    AUTHORIZATION = "authorization"
    TOOL = "tool"
    EXECUTION = "execution"
    RECEIPT = "receipt"
    SANDBOX = "sandbox"


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def _to_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        result = to_dict()
        return dict(result) if isinstance(result, Mapping) else {}
    return {}


def _enum_value(value: Any) -> str | None:
    if value is None:
        return None
    return str(getattr(value, "value", value))


@dataclass(frozen=True)
class TraceEvent:
    """One ordered, evidence-bearing event in a local trace."""

    event_id: str
    trace_id: str
    sequence: int
    name: str
    kind: TraceKind | str
    status: str
    parent_event_id: str | None = None
    attributes: Mapping[str, Any] = field(default_factory=dict)
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.event_id.strip() or not self.trace_id.strip():
            raise ValueError("event_id and trace_id are required")
        if self.sequence < 0:
            raise ValueError("sequence must be non-negative")
        if not self.name.strip() or not self.status.strip():
            raise ValueError("name and status are required")
        kind = self.kind if isinstance(self.kind, TraceKind) else TraceKind(self.kind)
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "attributes", dict(self.attributes))
        object.__setattr__(self, "evidence_refs", tuple(str(item) for item in self.evidence_refs))

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "trace_id": self.trace_id,
            "sequence": self.sequence,
            "name": self.name,
            "kind": self.kind.value,
            "status": self.status,
            "parent_event_id": self.parent_event_id,
            "attributes": dict(self.attributes),
            "evidence_refs": list(self.evidence_refs),
        }


@dataclass(frozen=True)
class LocalTrace:
    """A complete local trace with no external collector dependency."""

    trace_id: str
    run_id: str
    events: tuple[TraceEvent, ...]
    cost_usd: float = 0.0

    def __post_init__(self) -> None:
        if not self.trace_id.strip() or not self.run_id.strip():
            raise ValueError("trace_id and run_id are required")
        if self.cost_usd < 0:
            raise ValueError("cost_usd cannot be negative")
        object.__setattr__(self, "events", tuple(self.events))

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(event.name for event in self.events)

    @property
    def evidence_refs(self) -> tuple[str, ...]:
        return tuple(
            dict.fromkeys(
                reference
                for event in self.events
                for reference in event.evidence_refs
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "run_id": self.run_id,
            "cost_usd": self.cost_usd,
            "event_count": len(self.events),
            "evidence_refs": list(self.evidence_refs),
            "events": [event.to_dict() for event in self.events],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True, default=str)


class LocalTraceBuilder:
    """Project existing agent and sandbox evidence into one trace."""

    @classmethod
    def from_agent_run(
        cls,
        run: "AgentRun",
        *,
        sandbox_results: Iterable["SandboxExecutionResult"] = (),
    ) -> LocalTrace:
        trace_id = "trace-" + _digest(run.run_id)[:16]
        events: list[TraceEvent] = []
        sequence = 0
        seen_receipts: set[str] = set()
        receipt_event_by_id: dict[str, str] = {}
        proposal_event_by_receipt: dict[str, str] = {}

        def add(
            name: str,
            kind: TraceKind,
            status: str,
            *,
            parent_event_id: str | None = None,
            attributes: Mapping[str, Any] | None = None,
            evidence_refs: Iterable[str] = (),
        ) -> TraceEvent:
            nonlocal sequence
            event_id = "event-" + _digest(f"{trace_id}:{sequence}:{name}")[:16]
            event = TraceEvent(
                event_id=event_id,
                trace_id=trace_id,
                sequence=sequence,
                name=name,
                kind=kind,
                status=status,
                parent_event_id=parent_event_id,
                attributes=attributes or {},
                evidence_refs=tuple(dict.fromkeys(str(item) for item in evidence_refs if str(item))),
            )
            events.append(event)
            sequence += 1
            return event

        root = add(
            "agent.run",
            TraceKind.WORKFLOW,
            _enum_value(run.status) or "UNKNOWN",
            attributes={
                "run_id": run.run_id,
                "intent": _enum_value(run.intent),
                "query_sha256": _digest(run.query),
            },
        )

        stage_events: dict[str, TraceEvent] = {}
        for raw in run.trace:
            key, _, detail = raw.partition("=")
            canonical = key.split(":", 1)[0].strip()
            if not canonical:
                continue
            kind = cls._kind_for(canonical)
            status = cls._status_for(detail)
            stage = add(
                canonical,
                kind,
                status,
                parent_event_id=root.event_id,
                attributes={"raw": raw, "detail": detail},
            )
            stage_events[canonical] = stage

        retrieval = run.retrieval
        retrieval_event = add(
            "retrieval",
            TraceKind.RETRIEVAL,
            "SUCCESS" if retrieval.hits else "EMPTY",
            parent_event_id=stage_events.get("retrieve_context", root).event_id,
            attributes={
                "hits": len(retrieval.hits),
                "eligible_count": retrieval.eligible_count,
                "filtered_count": retrieval.filtered_count,
                "mode": _enum_value(retrieval.mode),
                "pipeline": list(retrieval.pipeline),
            },
            evidence_refs=retrieval.citations,
        )

        tool_events: list[TraceEvent] = []
        for proposal in run.proposals:
            request = proposal.request
            decision = _enum_value(proposal.decision)
            outcome = _enum_value(proposal.outcome)
            called = bool(proposal.called)
            status = cls._proposal_status(decision, outcome, called)
            receipt_ref = f"receipt://{proposal.receipt_id}" if proposal.receipt_id else ""
            tool_event = add(
                "tool_call",
                TraceKind.TOOL,
                status,
                parent_event_id=stage_events.get("reason_and_propose", root).event_id,
                attributes={
                    "proposal_id": proposal.proposal_id,
                    "request_id": request.request_id,
                    "tool_name": request.tool_name,
                    "transport": proposal.transport,
                    "effect_type": _enum_value(request.effect_type),
                    "decision": decision,
                    "permit_id": proposal.permit_id,
                    "called": called,
                    "outcome": outcome,
                    "receipt_id": proposal.receipt_id,
                },
                evidence_refs=(receipt_ref,) if receipt_ref else (),
            )
            tool_events.append(tool_event)
            if proposal.receipt_id:
                proposal_event_by_receipt[proposal.receipt_id] = tool_event.event_id
            if decision:
                add(
                    "permit",
                    TraceKind.AUTHORIZATION,
                    decision,
                    parent_event_id=tool_event.event_id,
                    attributes={
                        "request_id": request.request_id,
                        "tool_name": request.tool_name,
                        "decision": decision,
                        "permit_id": proposal.permit_id,
                    },
                    evidence_refs=(receipt_ref,) if receipt_ref else (),
                )

        def add_receipt(
            payload: Mapping[str, Any],
            *,
            source: str,
            parent_event_id: str,
            fallback_receipt_id: str = "",
        ) -> None:
            receipt_id = str(payload.get("receipt_id") or fallback_receipt_id or "")
            if not receipt_id or receipt_id in seen_receipts:
                return
            seen_receipts.add(receipt_id)
            evidence_refs = tuple(str(item) for item in (payload.get("evidence_refs") or ()))
            if not evidence_refs:
                evidence_refs = (f"receipt://{receipt_id}",)
            actual_effect = payload.get("actual_effect")
            called = actual_effect.get("called") if isinstance(actual_effect, Mapping) else None
            status = str(
                payload.get("status")
                or payload.get("execution_outcome")
                or payload.get("outcome")
                or "RECORDED"
            )
            receipt_event = add(
                "receipt",
                TraceKind.RECEIPT,
                status,
                parent_event_id=parent_event_id,
                attributes={
                    "receipt_id": receipt_id,
                    "source": source,
                    "request_id": payload.get("request_id", ""),
                    "permit_id": payload.get("permit_id", ""),
                    "called": called,
                    "cost_usd": payload.get("cost_usd", 0.0),
                },
                evidence_refs=evidence_refs,
            )
            receipt_event_by_id[receipt_id] = receipt_event.event_id

        for decision_receipt in run.decision_receipts:
            payload = _to_mapping(decision_receipt)
            receipt_id = str(payload.get("receipt_id", ""))
            parent = proposal_event_by_receipt.get(receipt_id, root.event_id)
            add_receipt(payload, source="authorization", parent_event_id=parent)

        for mcp_receipt in run.mcp_receipts:
            payload = _to_mapping(mcp_receipt)
            receipt_id = str(payload.get("receipt_id", ""))
            parent = proposal_event_by_receipt.get(receipt_id, root.event_id)
            add_receipt(payload, source="mcp", parent_event_id=parent)

        provider_result = run.provider_result
        if provider_result is not None:
            payload = _to_mapping(provider_result.receipt)
            receipt_id = str(payload.get("receipt_id", ""))
            parent = proposal_event_by_receipt.get(receipt_id, root.event_id)
            add_receipt(payload, source="provider", parent_event_id=parent)

        ontology = run.ontology
        if ontology is not None:
            payload = _to_mapping(ontology.receipt)
            add_receipt(payload, source="ontology", parent_event_id=retrieval_event.event_id)

        for sandbox_result in sandbox_results:
            receipt = sandbox_result.receipt
            payload = _to_mapping(receipt)
            sandbox_event = add(
                "sandbox_execution",
                TraceKind.SANDBOX,
                str(payload.get("status", "RECORDED")),
                parent_event_id=root.event_id,
                attributes={
                    "request_id": payload.get("request_id", ""),
                    "permit_id": payload.get("permit_id", ""),
                    "receipt_id": payload.get("receipt_id", ""),
                    "capability": payload.get("capability", ""),
                    "operation": payload.get("operation", ""),
                    "profile": payload.get("profile", ""),
                    "network_mode": payload.get("network_mode", ""),
                },
                evidence_refs=payload.get("evidence_refs", ()),
            )
            add_receipt(payload, source="sandbox", parent_event_id=sandbox_event.event_id)

        return LocalTrace(
            trace_id=trace_id,
            run_id=run.run_id,
            events=tuple(events),
            cost_usd=cls._cost_usd(run),
        )

    @staticmethod
    def _kind_for(name: str) -> TraceKind:
        if name == "retrieve_context":
            return TraceKind.RETRIEVAL
        if name == "ontology_engine":
            return TraceKind.REASONING
        if name == "authorize":
            return TraceKind.AUTHORIZATION
        if name == "execute":
            return TraceKind.EXECUTION
        return TraceKind.WORKFLOW

    @staticmethod
    def _status_for(detail: str) -> str:
        upper = detail.upper()
        if "REQUIRE_HUMAN" in upper:
            return "PENDING"
        if "DENY" in upper:
            return "DENIED"
        if "CONSTRAINT_VIOLATION" in upper:
            return "CONSTRAINT_VIOLATION"
        if "FAILURE" in upper:
            return "FAILURE"
        return "SUCCESS"

    @staticmethod
    def _proposal_status(decision: str | None, outcome: str | None, called: bool) -> str:
        if decision == "REQUIRE_HUMAN":
            return "PENDING"
        if decision == "DENY":
            return "DENIED"
        if outcome:
            return outcome
        if called:
            return "SUCCESS"
        return "PROPOSED"

    @staticmethod
    def _cost_usd(run: "AgentRun") -> float:
        provider_result = run.provider_result
        if provider_result is None:
            return 0.0
        receipt = getattr(provider_result, "receipt", None)
        return float(getattr(receipt, "cost_usd", 0.0) or 0.0)


__all__ = ["LocalTrace", "LocalTraceBuilder", "TraceEvent", "TraceKind"]
