"""Zero-cost deterministic checks over local governed traces."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable

from observability.local_trace import LocalTrace, TraceEvent, TraceKind


class EvaluationStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"


@dataclass(frozen=True)
class EvaluationCheck:
    name: str
    passed: bool
    detail: str
    evidence_refs: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "passed": self.passed,
            "detail": self.detail,
            "evidence_refs": list(self.evidence_refs),
        }


@dataclass(frozen=True)
class EvaluationReport:
    evaluation_id: str
    trace_id: str
    status: EvaluationStatus
    score: float
    checks: tuple[EvaluationCheck, ...]
    evidence_refs: tuple[str, ...] = field(default_factory=tuple)
    cost_usd: float = 0.0

    def __post_init__(self) -> None:
        status = self.status if isinstance(self.status, EvaluationStatus) else EvaluationStatus(self.status)
        object.__setattr__(self, "status", status)
        if not 0.0 <= self.score <= 1.0:
            raise ValueError("score must be between 0 and 1")
        if self.cost_usd < 0:
            raise ValueError("cost_usd cannot be negative")
        object.__setattr__(self, "checks", tuple(self.checks))
        object.__setattr__(self, "evidence_refs", tuple(self.evidence_refs))

    def to_dict(self) -> dict[str, Any]:
        return {
            "evaluation_id": self.evaluation_id,
            "trace_id": self.trace_id,
            "status": self.status.value,
            "score": self.score,
            "cost_usd": self.cost_usd,
            "checks": [check.to_dict() for check in self.checks],
            "evidence_refs": list(self.evidence_refs),
        }


class LocalTraceEvaluator:
    """Evaluate evidence linkage and governance invariants, not answer quality."""

    REQUIRED_WORKFLOW = frozenset(
        {
            "classify_intent",
            "retrieve_context",
            "reason_and_propose",
            "authorize",
            "execute",
            "verify_and_respond",
        }
    )

    def evaluate(self, trace: LocalTrace, *, require_sandbox: bool = False) -> EvaluationReport:
        events = trace.events
        names = {event.name for event in events}
        tool_events = [event for event in events if event.kind is TraceKind.TOOL]
        receipt_events = [event for event in events if event.kind is TraceKind.RECEIPT]
        receipt_ids = {
            str(event.attributes.get("receipt_id"))
            for event in receipt_events
            if event.attributes.get("receipt_id")
        }
        checks: list[EvaluationCheck] = []

        checks.append(
            self._check(
                "trace_root",
                "agent.run" in names,
                "agent.run root is present" if "agent.run" in names else "agent.run root is missing",
                events,
            )
        )
        missing_workflow = sorted(self.REQUIRED_WORKFLOW - names)
        checks.append(
            self._check(
                "workflow_coverage",
                not missing_workflow,
                "all governed workflow stages are present"
                if not missing_workflow
                else "missing workflow stages: " + ", ".join(missing_workflow),
                events,
            )
        )

        retrieval_events = [event for event in events if event.name == "retrieval"]
        retrieval_ok = bool(retrieval_events) and all(
            int(event.attributes.get("hits", 0)) == 0 or bool(event.evidence_refs)
            for event in retrieval_events
        )
        checks.append(
            self._check(
                "retrieval_evidence",
                retrieval_ok,
                "retrieval hits are linked to citations" if retrieval_ok else "retrieval evidence is missing",
                retrieval_events,
            )
        )

        linkage_failures: list[str] = []
        for event in tool_events:
            request_id = str(event.attributes.get("request_id", ""))
            decision = str(event.attributes.get("decision") or "")
            transport = str(event.attributes.get("transport") or "")
            permit_id = str(event.attributes.get("permit_id") or "")
            if not request_id:
                linkage_failures.append("tool without request_id")
            if decision == "ALLOW" and transport != "local" and not permit_id:
                linkage_failures.append(f"{event.attributes.get('tool_name', 'tool')} without permit")
        checks.append(
            self._check(
                "permit_linkage",
                not linkage_failures,
                "tool requests retain authorization linkage"
                if not linkage_failures
                else "; ".join(linkage_failures),
                tool_events,
            )
        )

        receipt_failures: list[str] = []
        for event in tool_events:
            receipt_id = str(event.attributes.get("receipt_id") or "")
            called = bool(event.attributes.get("called"))
            outcome = event.attributes.get("outcome")
            if (called or outcome) and (not receipt_id or receipt_id not in receipt_ids):
                receipt_failures.append(f"{event.attributes.get('tool_name', 'tool')} has no receipt")
        receipt_ok = not receipt_failures and all(event.evidence_refs for event in receipt_events)
        checks.append(
            self._check(
                "receipt_linkage",
                receipt_ok,
                "executions and receipts are linked to evidence"
                if receipt_ok
                else "; ".join(receipt_failures) or "receipt without evidence reference",
                receipt_events,
            )
        )

        unauthorized = [
            str(event.attributes.get("tool_name", "tool"))
            for event in tool_events
            if str(event.attributes.get("decision") or "") in {"DENY", "REQUIRE_HUMAN"}
            and bool(event.attributes.get("called"))
        ]
        checks.append(
            self._check(
                "no_unauthorized_effect",
                not unauthorized,
                "denied or pending tools have no material call"
                if not unauthorized
                else "unauthorized calls observed: " + ", ".join(unauthorized),
                tool_events,
            )
        )

        sandbox_events = [event for event in events if event.kind is TraceKind.SANDBOX]
        sandbox_ok = bool(sandbox_events) and all(
            bool(event.attributes.get("receipt_id")) and bool(event.evidence_refs)
            for event in sandbox_events
        )
        if require_sandbox:
            checks.append(
                self._check(
                    "sandbox_receipt",
                    sandbox_ok,
                    "sandbox execution is linked to a receipt"
                    if sandbox_ok
                    else "sandbox execution or receipt linkage is missing",
                    sandbox_events,
                )
            )

        passed = sum(1 for check in checks if check.passed)
        score = round(passed / len(checks), 4) if checks else 0.0
        status = EvaluationStatus.PASS if passed == len(checks) else EvaluationStatus.FAIL
        evaluation_id = "eval-" + hashlib.sha256(
            f"{trace.trace_id}|{status.value}|{','.join(str(check.passed) for check in checks)}".encode()
        ).hexdigest()[:16]
        evidence_refs = tuple(
            dict.fromkeys(
                reference
                for check in checks
                for reference in check.evidence_refs
            )
        )
        return EvaluationReport(
            evaluation_id=evaluation_id,
            trace_id=trace.trace_id,
            status=status,
            score=score,
            checks=tuple(checks),
            evidence_refs=evidence_refs,
            cost_usd=trace.cost_usd,
        )

    @staticmethod
    def _check(
        name: str,
        passed: bool,
        detail: str,
        events: Iterable[TraceEvent],
    ) -> EvaluationCheck:
        refs = tuple(
            dict.fromkeys(
                reference
                for event in events
                for reference in event.evidence_refs
            )
        )
        return EvaluationCheck(name=name, passed=passed, detail=detail, evidence_refs=refs)


__all__ = [
    "EvaluationCheck",
    "EvaluationReport",
    "EvaluationStatus",
    "LocalTraceEvaluator",
]
