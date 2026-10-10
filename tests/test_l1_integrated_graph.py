from __future__ import annotations

from pathlib import Path
import sys
import uuid

from langgraph.checkpoint.memory import InMemorySaver

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from metadata.schema import AuthorityLevel
from src.execution import ExecutionGateway
from src.orchestration.governed_execution import build_integrated_governed_graph, resume_approval
from src.retrieval.governed_rag import GovernedRAG, RetrievalChunk
from src.sandbox import (
    Capability,
    FilesystemOperation,
    FilesystemRequest,
    SandboxManager,
    SandboxProfile,
    SandboxRequest,
    SandboxStatus,
)
from src.orchestration.state_graph import EffectType, ExecutionRequest


def _app(root: Path, *, manager: SandboxManager | None = None, allow_test_runner: bool = False):
    rag = GovernedRAG([
        RetrievalChunk(
            chunk_id="current-governance",
            document_id="policy",
            content="A material write requires an explicit approval and a bounded workspace permit.",
            source_uri="docs/governance.md",
            revision="r1",
            authority=AuthorityLevel.CANONICAL,
            validity="CURRENT",
            domain="governance",
        ),
        RetrievalChunk(
            chunk_id="old-governance",
            document_id="policy-old",
            content="Superseded policy: writes are always allowed.",
            source_uri="docs/old-policy.md",
            revision="r0",
            authority=AuthorityLevel.CANONICAL,
            validity="SUPERSEDED",
            domain="governance",
        ),
    ])
    gateway = ExecutionGateway(sandbox_manager=manager or SandboxManager())
    return build_integrated_governed_graph(
        retriever=rag,
        gateway=gateway,
        workspace_root=root,
        checkpointer=InMemorySaver(),
        allow_test_runner=allow_test_runner,
    ), gateway


def _start(app, root: Path, *, path="notes/result.txt", content="approved content", action_kind="write", timeout_seconds=2.0):
    thread_id = uuid.uuid4().hex
    result = app.invoke(
        {
            "query": "What governs a local file write?",
            "request_id": "req-" + thread_id,
            "write_path": path,
            "write_content": content,
            "action_kind": action_kind,
            "test_path": path,
            "timeout_seconds": timeout_seconds,
        },
        config={"configurable": {"thread_id": thread_id}},
    )
    interrupts = result.get("__interrupt__", ())
    assert interrupts, result
    return thread_id, interrupts[0].value


def test_integrated_graph_pauses_before_effect_and_requires_exact_approval(tmp_path: Path):
    (tmp_path / "notes").mkdir()
    app, _gateway = _app(tmp_path)
    thread_id, request = _start(app, tmp_path)
    target = tmp_path / "notes/result.txt"

    assert not target.exists()
    assert request["kind"] == "human_approval_required"
    assert request["workspace_root"] == str(tmp_path.resolve())
    assert len(request["fingerprint"]) == 64

    denied = resume_approval(
        app,
        thread_id=thread_id,
        fingerprint="0" * 64,
        approved=True,
    )
    assert not target.exists()
    assert denied["authorization_status"] == "DENIED"
    assert denied["sandbox_result"].receipt.status is SandboxStatus.DENIED
    assert denied["sandbox_result"].receipt.error_code == "PERMIT_REQUIRED"
    assert "sandbox.execution" in denied["local_trace"].names


def test_integrated_graph_writes_only_after_matching_approval_and_traces_receipt(tmp_path: Path):
    (tmp_path / "notes").mkdir()
    app, _gateway = _app(tmp_path)
    thread_id, request = _start(app, tmp_path)
    target = tmp_path / "notes/result.txt"
    assert not target.exists()

    result = resume_approval(
        app,
        thread_id=thread_id,
        fingerprint=request["fingerprint"],
    )

    assert target.read_text(encoding="utf-8") == "approved content"
    assert result["sandbox_result"].ok
    receipt = result["sandbox_result"].receipt
    assert receipt.status is SandboxStatus.SUCCESS
    assert receipt.permit_id == result["permit"].permit_id
    assert receipt.request_id == result["proposal"]["request"]["request_id"]
    trace = result["local_trace"]
    assert "governed_retrieval" in trace.names
    assert "action.proposal" in trace.names
    assert "human.approval" in trace.names
    assert "sandbox.receipt" in trace.names
    assert receipt.receipt_id in trace.to_json()
    assert any(ref.startswith("sandbox://") for ref in trace.evidence_refs)
    assert "current-governance" in str(result["retrieved"])
    assert "old-governance" not in str(result["retrieved"])

    proposal = result["proposal"]["request"]
    execution_request = ExecutionRequest(
        request_id=proposal["request_id"],
        tool_name=proposal["tool_name"],
        effect_type=EffectType(proposal["effect_type"]),
        parameters=proposal["parameters"],
        proposed_by=proposal["proposed_by"],
        context_revision=proposal["context_revision"],
        timestamp=proposal["timestamp"],
    )
    replay = _gateway.execute(
        request=execution_request,
        permit=result["permit"],
        sandbox_request=SandboxRequest(
            request_id=execution_request.request_id,
            workspace_root=tmp_path,
            operation=FilesystemRequest(
                request_id=execution_request.request_id,
                operation=FilesystemOperation.WRITE,
                relative_path=proposal["parameters"]["path"],
                content=proposal["parameters"]["content"],
            ),
            requested_profile=SandboxProfile.REPOSITORY_WORKER,
        ),
    )
    assert replay.receipt.status is SandboxStatus.DENIED
    assert replay.receipt.error_code == "PERMIT_REPLAY"


def test_integrated_graph_path_escape_returns_denial_receipt(tmp_path: Path):
    app, _gateway = _app(tmp_path)
    thread_id, request = _start(app, tmp_path, path="../outside.txt")
    result = resume_approval(app, thread_id=thread_id, fingerprint=request["fingerprint"])

    assert not (tmp_path.parent / "outside.txt").exists()
    assert result["sandbox_result"].receipt.status is SandboxStatus.DENIED
    assert result["sandbox_result"].receipt.error_code == "PATH_ESCAPE"
    assert result["authorization_status"] == "ALLOW"
    assert result["execution_status"] == "FAILURE"
    assert result["local_trace"].events[-1].attributes["receipt_id"] == result["sandbox_result"].receipt.receipt_id


def test_integrated_graph_invalid_typed_request_returns_controlled_receipt(tmp_path: Path):
    app, _gateway = _app(tmp_path)
    thread_id, request = _start(app, tmp_path, path="bad\x00path")
    result = resume_approval(app, thread_id=thread_id, fingerprint=request["fingerprint"])

    assert result["sandbox_result"].receipt.status is SandboxStatus.DENIED
    assert result["sandbox_result"].receipt.error_code == "SANDBOX_REQUEST_INVALID"
    assert result["execution_status"] == "FAILURE"
    assert result["local_trace"].events[-1].attributes["receipt_id"] == result["sandbox_result"].receipt.receipt_id


def test_integrated_graph_process_timeout_returns_real_timeout_receipt(tmp_path: Path):
    (tmp_path / "timeout_case.py").write_text(
        "import time\n\ndef test_slow_case():\n    time.sleep(5)\n",
        encoding="utf-8",
    )
    app, _gateway = _app(tmp_path, allow_test_runner=True)
    thread_id, request = _start(
        app,
        tmp_path,
        path="timeout_case.py",
        action_kind="run_tests",
        timeout_seconds=2,
    )
    result = resume_approval(app, thread_id=thread_id, fingerprint=request["fingerprint"])

    receipt = result["sandbox_result"].receipt
    assert receipt.status is SandboxStatus.TIMEOUT
    assert receipt.timed_out is True
    assert receipt.error_code == "TIMEOUT"
    assert result["execution_status"] == "FAILURE"
    assert result["local_trace"].events[-1].attributes["receipt_id"] == receipt.receipt_id
