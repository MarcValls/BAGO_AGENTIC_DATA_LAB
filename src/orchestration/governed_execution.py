"""Integrated LangGraph flow for governed retrieval and local file writes.

The factory owns the workspace, retriever and gateway. Graph state is treated
as untrusted proposal data; material execution always passes through a
request-bound resume gate and the typed sandbox gateway.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from src.execution.gateway import ExecutionGateway
from src.observability.local_trace import LocalTrace, TraceEvent, TraceKind
from src.orchestration.state_graph import (
    AuthorizationDecision,
    EffectType,
    ExecutionRequest,
    Permit,
)
from src.retrieval.governed_rag import GovernedRAG
from src.sandbox import (
    Capability,
    FilesystemOperation,
    FilesystemRequest,
    SandboxProfile,
    SandboxRequest,
    SandboxStatus,
)


class GovernedExecutionState(TypedDict, total=False):
    query: str
    request_id: str
    write_path: str
    write_content: str
    retrieved: dict[str, Any]
    proposal: dict[str, Any]
    approval: dict[str, Any]
    permit: Permit | None
    sandbox_result: Any
    authorization_status: str
    execution_status: str
    action_kind: str
    test_path: str
    timeout_seconds: float
    final_response: str
    local_trace: LocalTrace


def _fingerprint(request: ExecutionRequest, workspace_root: Path) -> str:
    capability = Capability.RUN_TESTS.value if request.tool_name == "pytest" else Capability.FILESYSTEM_WRITE.value
    payload = {
        "request_id": request.request_id,
        "tool_name": request.tool_name,
        "effect_type": request.effect_type.value,
        "parameters": request.parameters,
        "proposed_by": request.proposed_by,
        "context_revision": request.context_revision,
        "timestamp": request.timestamp,
        "workspace_root": str(workspace_root.resolve()),
        "capability": capability,
        "operation_scope": "workspace",
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _request_from(state: GovernedExecutionState) -> ExecutionRequest:
    raw = state["proposal"]["request"]
    return ExecutionRequest(
        request_id=raw["request_id"],
        tool_name=raw["tool_name"],
        effect_type=EffectType(raw["effect_type"]),
        parameters=dict(raw["parameters"]),
        proposed_by=raw["proposed_by"],
        context_revision=raw["context_revision"],
        timestamp=raw["timestamp"],
    )


def _trace_from_state(state: GovernedExecutionState) -> LocalTrace:
    proposal = state.get("proposal", {})
    request = proposal.get("request", {})
    result = state.get("sandbox_result")
    receipt = result.receipt if result is not None else None
    status = state.get("authorization_status", "NO_ACTION")
    run_id = state.get("request_id") or request.get("request_id") or uuid.uuid4().hex
    trace_id = "trace-" + hashlib.sha256(run_id.encode()).hexdigest()[:16]
    events: list[TraceEvent] = []

    def add(name: str, kind: TraceKind, event_status: str, attributes: dict[str, Any], refs: tuple[str, ...] = ()) -> None:
        sequence = len(events)
        event_id = "event-" + hashlib.sha256(f"{trace_id}:{sequence}:{name}".encode()).hexdigest()[:16]
        events.append(TraceEvent(
            event_id=event_id,
            trace_id=trace_id,
            sequence=sequence,
            name=name,
            kind=kind,
            status=event_status,
            attributes=attributes,
            evidence_refs=refs,
        ))

    add("langgraph.run", TraceKind.WORKFLOW, "COMPLETED", {"run_id": run_id})
    retrieval = state.get("retrieved", {})
    add("governed_retrieval", TraceKind.RETRIEVAL, "SUCCESS" if retrieval.get("hits") else "EMPTY",
        {"hits": retrieval.get("hits", []), "citations": retrieval.get("citations", [])},
        tuple(retrieval.get("citations", [])))
    if request:
        add("action.proposal", TraceKind.TOOL, "PROPOSED", {
            "request_id": request.get("request_id"),
            "fingerprint": proposal.get("fingerprint"),
            "tool_name": request.get("tool_name"),
            "effect_type": request.get("effect_type"),
        })
        add("human.approval", TraceKind.AUTHORIZATION, status, {
            "fingerprint": proposal.get("fingerprint"),
            "approved": state.get("approval", {}).get("approved", False),
        })
    if receipt is not None:
        payload = receipt.to_dict()
        refs = tuple(payload.get("evidence_refs", ()))
        add("sandbox.execution", TraceKind.SANDBOX, payload["status"], {
            "request_id": payload["request_id"],
            "permit_id": payload["permit_id"],
            "receipt_id": payload["receipt_id"],
            "capability": payload["capability"],
            "operation": payload["operation"],
            "error_code": payload["error_code"],
        }, refs)
        add("sandbox.receipt", TraceKind.RECEIPT, payload["status"], payload, refs)
    return LocalTrace(trace_id=trace_id, run_id=run_id, events=tuple(events))


def build_integrated_governed_graph(
    *,
    retriever: GovernedRAG,
    gateway: ExecutionGateway,
    workspace_root: Path | str,
    checkpointer: Any | None = None,
    allow_test_runner: bool = False,
):
    """Build a request-bound graph; caller must provide a per-run thread_id."""
    root = Path(workspace_root).expanduser().resolve()
    if not root.is_dir():
        raise ValueError("workspace_root must be an existing directory")

    def retrieve(state: GovernedExecutionState) -> dict[str, Any]:
        response = retriever.retrieve(state.get("query", ""), top_k=5)
        return {"retrieved": {
            "hits": [
                {"chunk_id": hit.chunk.chunk_id, "content": hit.chunk.content,
                 "citation": hit.evidence.citation, "revision": hit.evidence.revision}
                for hit in response.hits
            ],
            "citations": list(response.citations),
            "eligible_count": response.eligible_count,
            "filtered_count": response.filtered_count,
        }}

    def propose(state: GovernedExecutionState) -> dict[str, Any]:
        action_kind = state.get("action_kind", "write")
        if action_kind == "write":
            tool_name = "filesystem.write"
            effect_type = EffectType.WRITE
            timeout_seconds = 10.0
            parameters = {"path": state.get("write_path", ""), "content": state.get("write_content", "")}
        elif action_kind == "run_tests" and allow_test_runner:
            tool_name = "pytest"
            effect_type = EffectType.EXTERNAL_TOOL
            try:
                timeout_seconds = min(float(state.get("timeout_seconds", 2.0)), 2.0)
            except (TypeError, ValueError):
                timeout_seconds = 0.0
            parameters = {"path": state.get("test_path", ""), "timeout_seconds": timeout_seconds, "cwd": "."}
        else:
            action_kind = "unsupported"
            tool_name = "unregistered:" + str(state.get("action_kind", "unknown"))
            effect_type = EffectType.EXTERNAL_TOOL
            timeout_seconds = 10.0
            parameters = {}
        request = ExecutionRequest(
            request_id=state["request_id"],
            tool_name=tool_name,
            effect_type=effect_type,
            parameters=parameters,
            proposed_by="langgraph_user_request",
            context_revision="governed-rag-current",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        return {"action_kind": action_kind, "timeout_seconds": timeout_seconds, "proposal": {
            "request": {
                "request_id": request.request_id,
                "tool_name": request.tool_name,
                "effect_type": request.effect_type.value,
                "parameters": request.parameters,
                "proposed_by": request.proposed_by,
                "context_revision": request.context_revision,
                "timestamp": request.timestamp,
            },
            "fingerprint": _fingerprint(request, root),
        }}

    def authorize(state: GovernedExecutionState) -> dict[str, Any]:
        request = _request_from(state)
        if request.tool_name not in {"filesystem.write", "pytest"}:
            return {"approval": {"approved": False}, "permit": None, "authorization_status": "DENIED"}
        fingerprint = state["proposal"]["fingerprint"]
        canonical_fingerprint = _fingerprint(request, root)
        response = interrupt({
            "kind": "human_approval_required",
            "request_id": request.request_id,
            "fingerprint": fingerprint,
            "request": state["proposal"]["request"],
            "workspace_root": str(root),
        })
        approved = (
            isinstance(response, dict)
            and response.get("approved") is True
            and fingerprint == canonical_fingerprint
            and response.get("fingerprint") == canonical_fingerprint
        )
        approval = {
            "approved": approved,
            "fingerprint": response.get("fingerprint") if isinstance(response, dict) else None,
        }
        if not approved:
            return {"approval": approval, "permit": None, "authorization_status": "DENIED"}

        now = datetime.now(timezone.utc)
        is_test_run = request.tool_name == "pytest"
        if is_test_run and (not allow_test_runner or state.get("action_kind") != "run_tests"):
            return {"approval": approval, "permit": None, "authorization_status": "DENIED"}
        profile = SandboxProfile.TEST_RUNNER if is_test_run else SandboxProfile.REPOSITORY_WORKER
        capability = Capability.RUN_TESTS if is_test_run else Capability.FILESYSTEM_WRITE
        permit_constraints = [
            f"sandbox_profile={profile.value}",
            f"workspace_root={root}",
            f"capability={capability.value}",
            "network=deny",
            f"timeout_seconds={min(max(float(state.get('timeout_seconds', 10.0)), 0.1), 10.0)}",
        ]
        if not is_test_run:
            permit_constraints.append("write_scope=workspace")
        permit = Permit(
            permit_id="permit-" + fingerprint[:20],
            request_id=request.request_id,
            decision=AuthorizationDecision.ALLOW,
            rationale="Explicit LangGraph resume matched the complete request fingerprint",
            constraints=permit_constraints,
            issued_at=now.isoformat(),
            expires_at=(now + timedelta(minutes=2)).isoformat(),
            signed_by="local_langgraph_resume_demo",
        )
        return {"approval": approval, "permit": permit, "authorization_status": "ALLOW"}

    def execute(state: GovernedExecutionState) -> dict[str, Any]:
        request = _request_from(state)
        try:
            if request.tool_name not in {"filesystem.write", "pytest"}:
                return {"sandbox_result": gateway.sandbox_manager.deny(
                    request_id=request.request_id,
                    permit_id="",
                    capability="unregistered",
                    error_code="CAPABILITY_NOT_REGISTERED",
                    error_message="the requested action has no registered execution capability",
                ), "execution_status": "FAILURE"}
            if request.tool_name == "pytest":
                if not allow_test_runner or state.get("action_kind") != "run_tests":
                    raise ValueError("typed test runner capability is not registered")
                from src.sandbox import ProcessRequest
                operation = ProcessRequest(
                    request_id=request.request_id,
                    capability=Capability.RUN_TESTS,
                    tool="pytest",
                    arguments=(str(request.parameters["path"]),),
                    cwd=str(request.parameters["cwd"]),
                    timeout_seconds=float(request.parameters["timeout_seconds"]),
                )
                profile = SandboxProfile.TEST_RUNNER
            else:
                operation = FilesystemRequest(
                    request_id=request.request_id,
                    operation=FilesystemOperation.WRITE,
                    relative_path=str(request.parameters["path"]),
                    content=str(request.parameters["content"]),
                )
                profile = SandboxProfile.REPOSITORY_WORKER
            sandbox_request = SandboxRequest(
                request_id=request.request_id,
                workspace_root=root,
                operation=operation,
                requested_profile=profile,
            )
            result = gateway.execute(request=request, permit=state.get("permit"), sandbox_request=sandbox_request)
        except (KeyError, TypeError, ValueError) as error:
            result = gateway.sandbox_manager.deny(
                request_id=request.request_id,
                permit_id=state.get("permit").permit_id if state.get("permit") else "",
                capability=Capability.RUN_TESTS.value if request.tool_name == "pytest" else Capability.FILESYSTEM_WRITE.value,
                error_code="SANDBOX_REQUEST_INVALID",
                error_message=str(error),
            )
        status = "SUCCESS" if result.receipt.status is SandboxStatus.SUCCESS else "FAILURE"
        return {"sandbox_result": result, "execution_status": status}

    def respond(state: GovernedExecutionState) -> dict[str, Any]:
        result = state.get("sandbox_result")
        if state.get("authorization_status") == "DENIED":
            message = f"Approval was denied or did not match; no write was authorized. Receipt {result.receipt.receipt_id}."
        elif result is None:
            message = "No material operation was executed."
        elif state.get("proposal", {}).get("request", {}).get("tool_name") == "pytest" and result.ok:
            message = f"Governed test command completed; receipt {result.receipt.receipt_id}."
        elif state.get("proposal", {}).get("request", {}).get("tool_name") == "pytest":
            message = f"Governed test command failed ({result.receipt.error_code or result.receipt.status.value}); receipt {result.receipt.receipt_id}."
        elif result.ok:
            message = f"Workspace write completed; receipt {result.receipt.receipt_id}."
        else:
            message = f"Workspace write failed ({result.receipt.error_code or result.receipt.status.value}); receipt {result.receipt.receipt_id}."
        interim = {**state, "final_response": message}
        return {"final_response": message, "local_trace": _trace_from_state(interim)}

    graph = StateGraph(GovernedExecutionState)
    graph.add_node("retrieve_governed_context", retrieve)
    graph.add_node("propose_action", propose)
    graph.add_node("authorize_action", authorize)
    graph.add_node("execute_action", execute)
    graph.add_node("respond", respond)
    graph.add_edge(START, "retrieve_governed_context")
    graph.add_edge("retrieve_governed_context", "propose_action")
    graph.add_edge("propose_action", "authorize_action")
    graph.add_edge("authorize_action", "execute_action")
    graph.add_edge("execute_action", "respond")
    graph.add_edge("respond", END)
    return graph.compile(checkpointer=checkpointer or InMemorySaver())


def resume_approval(app: Any, *, thread_id: str, fingerprint: str, approved: bool = True) -> dict[str, Any]:
    """Resume one paused run with an explicit approval/rejection payload."""
    return app.invoke(
        Command(resume={"approved": bool(approved), "fingerprint": fingerprint}),
        config={"configurable": {"thread_id": thread_id}},
    )

