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

    def evaluate_ber_effect(self, trace: LocalTrace) -> EvaluationReport:
        """Evaluate one BER effect receipt without requiring an agent workflow.

        This profile deliberately does not claim answer-quality or full-agent
        workflow coverage. It verifies source identity, approval linkage,
        request/receipt correlation, and the bounded BER effect allowlist.
        """

        events = trace.events
        tools = [event for event in events if event.kind is TraceKind.TOOL and event.name == "ber.effect"]
        receipts = [event for event in events if event.kind is TraceKind.RECEIPT and event.name == "ber.receipt"]
        auth_events = [event for event in events if event.kind is TraceKind.AUTHORIZATION and event.name == "ber.authorization"]
        refs = tuple(dict.fromkeys(ref for event in events for ref in event.evidence_refs))
        tool = tools[0] if len(tools) == 1 else None
        receipt = receipts[0] if len(receipts) == 1 else None
        auth = auth_events[0] if len(auth_events) == 1 else None
        tool_attrs = tool.attributes if tool else {}
        receipt_attrs = receipt.attributes if receipt else {}
        auth_attrs = auth.attributes if auth else {}
        effect_id = str(tool_attrs.get("effect_id") or "")
        allowed_effects = {"filesystem.read", "filesystem.write", "process.inspect", "process.execute"}
        request_matches = bool(tool_attrs.get("request_id")) and tool_attrs.get("request_id") == tool_attrs.get("execution_request_id") == receipt_attrs.get("request_id")
        receipt_matches = bool(tool_attrs.get("receipt_id")) and tool_attrs.get("receipt_id") == tool_attrs.get("outer_receipt_id") == receipt_attrs.get("receipt_id") == receipt_attrs.get("outer_receipt_id")
        receipt_has_evidence = bool(receipt and receipt.evidence_refs and all(ref.startswith("ber://receipt/") for ref in receipt.evidence_refs))
        approval_required = tool_attrs.get("approval_required") is True
        if approval_required:
            authorization_ok = (
                tool_attrs.get("approval_state") == "approved"
                and tool_attrs.get("authorization_state") == "consumed"
                and bool(tool_attrs.get("decision_id"))
                and bool(tool_attrs.get("proof_id"))
                and bool(tool_attrs.get("permit_id"))
                and tool_attrs.get("permit_id") == auth_attrs.get("permit_id")
            )
        else:
            authorization_ok = effect_id == "process.inspect" and bool(tool_attrs.get("authorization_state"))
        checks = (
            EvaluationCheck("ber_run_identity", bool(trace.run_id) and any(event.name == "ber.effect.run" and event.attributes.get("run_id") == trace.run_id for event in events), "BER execution identity is present and bound to the trace" if trace.run_id and any(event.name == "ber.effect.run" and event.attributes.get("run_id") == trace.run_id for event in events) else "BER execution identity is missing or mismatched", refs),
            EvaluationCheck("ber_effect_allowlist", effect_id in allowed_effects, "effect is in the bounded BER profile" if effect_id in allowed_effects else "effect is outside the bounded BER profile", refs),
            EvaluationCheck("ber_authorization_linkage", authorization_ok, "approval and BAGO authorization identifiers are linked" if authorization_ok else "approval or BAGO authorization linkage is missing or mismatched", refs),
            EvaluationCheck("ber_request_linkage", request_matches, "prepared, executed, and receipt request IDs match" if request_matches else "prepared, executed, and receipt request IDs do not match", refs),
            EvaluationCheck("ber_receipt_linkage", receipt_matches and receipt_has_evidence, "BAGO receipt ID is linked to its evidence reference" if receipt_matches and receipt_has_evidence else "BAGO receipt identity or evidence reference is missing or mismatched", refs),
            EvaluationCheck("ber_effect_count", tool is not None and receipt is not None and auth is not None, "exactly one effect, authorization, and receipt event are present" if tool is not None and receipt is not None and auth is not None else "effect, authorization, or receipt event is missing or duplicated", refs),
            EvaluationCheck("ber_outcome", tool is not None and tool.status == "SUCCESS" and receipt is not None and receipt.status == "SUCCESS", "the effect and receipt both report success" if tool is not None and tool.status == "SUCCESS" and receipt is not None and receipt.status == "SUCCESS" else "the effect and receipt do not both report success", refs),
        )
        passed = sum(check.passed for check in checks)
        score = passed / len(checks)
        digest = hashlib.sha256(f"ber-evaluation:{trace.trace_id}".encode("utf-8")).hexdigest()[:20]
        return EvaluationReport(
            evaluation_id=f"ber-eval-{digest}",
            trace_id=trace.trace_id,
            status=EvaluationStatus.PASS if passed == len(checks) else EvaluationStatus.FAIL,
            score=score,
            checks=checks,
            evidence_refs=refs,
            cost_usd=trace.cost_usd,
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
