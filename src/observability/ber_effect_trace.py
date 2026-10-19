"""Project an executed BAGO Embedded Runtime effect into ADL-owned LocalTrace.

This adapter records BAGO-issued identifiers and outcomes only. It never
reconstructs authorization from UI state or copies a Permit token.
"""

from __future__ import annotations

import hashlib
from typing import Any, Mapping

from .local_trace import LocalTrace, TraceEvent, TraceKind


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _identifier(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def local_trace_from_ber_effect(
    prepared: Mapping[str, Any],
    approval: Mapping[str, Any] | None,
    execution: Mapping[str, Any],
    *,
    artifact_sha256: str,
) -> LocalTrace:
    """Create a trace projection from one BER prepare/approve/execute record.

    Identity mismatches are retained in separate source fields so evaluation
    can fail them visibly instead of silently repairing the source record.
    """

    result = _mapping(execution.get("result"))
    authorization = _mapping(execution.get("authorization"))
    request_id = _identifier(prepared.get("request_id"))
    effect_id = _identifier(prepared.get("effect_id"))
    run_id = _identifier(execution.get("ber_execution_id"))
    receipt_id = _identifier(result.get("receipt_id"))
    outer_receipt_id = _identifier(execution.get("receipt_id"))
    if not request_id or not effect_id or not run_id:
        raise ValueError("BER request, effect, and execution identities are required")

    digest = hashlib.sha256(run_id.encode("utf-8")).hexdigest()[:16]
    trace_id = f"trace-ber-{digest}"
    root_id = f"event-ber-{digest}-0"
    tool_id = f"event-ber-{digest}-1"
    auth_id = f"event-ber-{digest}-2"
    receipt_event_id = f"event-ber-{digest}-3"
    succeeded = result.get("ok") is True
    outcome = "SUCCESS" if succeeded else "FAILURE"
    permit_id = _identifier(authorization.get("permit_id"))
    decision_id = _identifier(authorization.get("decision_id"))
    proof_id = _identifier(authorization.get("proof_id"))
    approval_data = _mapping(approval)
    approval_required = prepared.get("approval_required") is True
    receipt_ref = f"ber://receipt/{receipt_id}" if receipt_id else ""
    evidence_refs = (receipt_ref,) if receipt_ref else ()

    events = (
        TraceEvent(
            event_id=root_id,
            trace_id=trace_id,
            sequence=0,
            name="ber.effect.run",
            kind=TraceKind.WORKFLOW,
            status=outcome,
            attributes={
                "run_id": run_id,
                "source": "bago-embedded-runtime",
                "ber_artifact_sha256": artifact_sha256,
                "effect_id": effect_id,
            },
        ),
        TraceEvent(
            event_id=tool_id,
            trace_id=trace_id,
            sequence=1,
            name="ber.effect",
            kind=TraceKind.TOOL,
            status=outcome,
            parent_event_id=root_id,
            attributes={
                "request_id": request_id,
                "execution_request_id": _identifier(execution.get("request_id")),
                "effect_id": effect_id,
                "tool_name": effect_id,
                "transport": "bago-ber",
                "approval_required": approval_required,
                "approval_state": _identifier(approval_data.get("state")),
                "authorization_state": _identifier(authorization.get("state")),
                "decision_id": decision_id,
                "proof_id": proof_id,
                "permit_id": permit_id,
                "called": result.get("executed") is True,
                "outcome": outcome,
                "receipt_id": receipt_id,
                "outer_receipt_id": outer_receipt_id,
            },
            evidence_refs=evidence_refs,
        ),
        TraceEvent(
            event_id=auth_id,
            trace_id=trace_id,
            sequence=2,
            name="ber.authorization",
            kind=TraceKind.AUTHORIZATION,
            status=_identifier(authorization.get("state")) or "UNKNOWN",
            parent_event_id=tool_id,
            attributes={
                "request_id": request_id,
                "decision_id": decision_id,
                "proof_id": proof_id,
                "permit_id": permit_id,
                "approval_required": approval_required,
                "approval_state": _identifier(approval_data.get("state")),
            },
            evidence_refs=evidence_refs,
        ),
        TraceEvent(
            event_id=receipt_event_id,
            trace_id=trace_id,
            sequence=3,
            name="ber.receipt",
            kind=TraceKind.RECEIPT,
            status=outcome,
            parent_event_id=tool_id,
            attributes={
                "receipt_id": receipt_id,
                "outer_receipt_id": outer_receipt_id,
                "request_id": _identifier(execution.get("request_id")),
                "permit_id": permit_id,
                "effect_id": effect_id,
            },
            evidence_refs=evidence_refs,
        ),
    )
    return LocalTrace(trace_id=trace_id, run_id=run_id, events=events)


__all__ = ["local_trace_from_ber_effect"]
