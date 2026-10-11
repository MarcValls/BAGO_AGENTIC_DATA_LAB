"""Reproduce local L1 interrupt/resume, sandbox receipts and LocalTrace evidence."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from metadata.schema import AuthorityLevel
from src.execution import ExecutionGateway
from src.orchestration.governed_execution import build_integrated_governed_graph, resume_approval
from src.orchestration.state_graph import EffectType, ExecutionRequest
from src.retrieval.governed_rag import GovernedRAG, RetrievalChunk
from src.sandbox import FilesystemOperation, FilesystemRequest, SandboxManager, SandboxProfile, SandboxRequest


def build_app(root: Path, manager: SandboxManager, *, allow_test_runner: bool = False):
    rag = GovernedRAG([
        RetrievalChunk(
            chunk_id="l1-current-policy",
            document_id="l1-policy",
            content="Material writes require a matching approval and workspace-scoped permit.",
            source_uri="docs/langgraph_architecture.md",
            revision="l1-current",
            authority=AuthorityLevel.CANONICAL,
            validity="CURRENT",
            domain="governance",
        ),
        RetrievalChunk(
            chunk_id="l1-superseded-policy",
            document_id="l1-old-policy",
            content="Superseded: all writes are automatically allowed.",
            source_uri="docs/old-policy.md",
            revision="l1-old",
            authority=AuthorityLevel.CANONICAL,
            validity="SUPERSEDED",
            domain="governance",
        ),
    ])
    gateway = ExecutionGateway(sandbox_manager=manager)
    app = build_integrated_governed_graph(
        retriever=rag, gateway=gateway, workspace_root=root, allow_test_runner=allow_test_runner
    )
    return app, gateway


def start(app, path: str, content: str = "", *, action_kind: str = "write", timeout_seconds: float = 2.0):
    thread_id = uuid.uuid4().hex
    result = app.invoke({
        "query": "What policy governs a workspace write?",
        "request_id": "l1-" + thread_id,
        "write_path": path,
        "write_content": content,
        "action_kind": action_kind,
        "test_path": path,
        "timeout_seconds": timeout_seconds,
    }, config={"configurable": {"thread_id": thread_id}})
    pending = result["__interrupt__"][0].value
    return thread_id, pending


def run(output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    cases: dict[str, dict] = {}
    transcript: list[str] = []
    with tempfile.TemporaryDirectory(prefix="bago-l1-governed-") as temp:
        root = Path(temp).resolve()
        (root / "notes").mkdir()
        manager = SandboxManager()
        app, gateway = build_app(root, manager)

        # Allowed write: verify pause, exact resume binding, effect and actual receipt.
        thread_id, pending = start(app, "notes/approved.txt", "L1 governed execution evidence\n")
        approved_path = root / "notes/approved.txt"
        transcript.append(f"RUN allowed: paused before effect; file_exists={approved_path.exists()}")
        allowed = resume_approval(app, thread_id=thread_id, fingerprint=pending["fingerprint"])
        allowed_receipt = allowed["sandbox_result"].receipt
        assert approved_path.read_text(encoding="utf-8") == "L1 governed execution evidence\n"
        assert allowed["sandbox_result"].ok
        assert "l1-current-policy" in str(allowed["retrieved"])
        assert "l1-superseded-policy" not in str(allowed["retrieved"])
        cases["allowed"] = {
            "request_id": allowed_receipt.request_id,
            "fingerprint": pending["fingerprint"],
            "receipt": allowed_receipt.to_dict(),
            "file_sha256": hashlib.sha256(approved_path.read_bytes()).hexdigest(),
            "trace": allowed["local_trace"].to_dict(),
        }
        transcript.append(f"RUN allowed: file_sha256={cases['allowed']['file_sha256']}; receipt={allowed_receipt.receipt_id}; status={allowed_receipt.status.value}")

        # Explicit rejection/mismatch still crosses the gateway and creates denial evidence.
        denied_app, _ = build_app(root, SandboxManager())
        denied_thread, denied_pending = start(denied_app, "notes/denied.txt", "must not appear")
        denied = resume_approval(denied_app, thread_id=denied_thread, fingerprint="0" * 64)
        denied_receipt = denied["sandbox_result"].receipt
        assert not (root / "notes/denied.txt").exists()
        assert denied_receipt.error_code == "PERMIT_REQUIRED"
        cases["denied"] = {"fingerprint": denied_pending["fingerprint"], "receipt": denied_receipt.to_dict(), "trace": denied["local_trace"].to_dict()}
        transcript.append(f"RUN denied: no file created; receipt={denied_receipt.receipt_id}; error={denied_receipt.error_code}")

        # Replay the exact permit/request through the same manager instance.
        proposal = allowed["proposal"]["request"]
        request = ExecutionRequest(
            request_id=proposal["request_id"], tool_name=proposal["tool_name"],
            effect_type=EffectType(proposal["effect_type"]), parameters=proposal["parameters"],
            proposed_by=proposal["proposed_by"], context_revision=proposal["context_revision"], timestamp=proposal["timestamp"],
        )
        replay = gateway.execute(
            request=request,
            permit=allowed["permit"],
            sandbox_request=SandboxRequest(
                request_id=request.request_id, workspace_root=root,
                operation=FilesystemRequest(request_id=request.request_id, operation=FilesystemOperation.WRITE,
                                            relative_path=proposal["parameters"]["path"], content=proposal["parameters"]["content"]),
                requested_profile=SandboxProfile.REPOSITORY_WORKER,
            ),
        )
        assert replay.receipt.error_code == "PERMIT_REPLAY"
        cases["replay"] = {"receipt": replay.receipt.to_dict(), "permit_lifetime": "same SandboxManager instance"}
        transcript.append(f"RUN replay: receipt={replay.receipt.receipt_id}; error={replay.receipt.error_code}")

        # Approved but escaping path produces a controlled sandbox denial and trace receipt.
        fail_app, _ = build_app(root, SandboxManager())
        fail_thread, fail_pending = start(fail_app, "../escape.txt", "must not escape")
        failed = resume_approval(fail_app, thread_id=fail_thread, fingerprint=fail_pending["fingerprint"])
        failure_receipt = failed["sandbox_result"].receipt
        assert failure_receipt.error_code == "PATH_ESCAPE"
        assert not (root.parent / "escape.txt").exists()
        cases["path_escape_failure"] = {"receipt": failure_receipt.to_dict(), "trace": failed["local_trace"].to_dict()}
        transcript.append(f"RUN path_escape_failure: receipt={failure_receipt.receipt_id}; error={failure_receipt.error_code}; outside_file_exists=false")

        (root / "timeout_case.py").write_text(
            "import time\n\ndef test_slow_case():\n    time.sleep(5)\n", encoding="utf-8"
        )
        timeout_app, _ = build_app(root, SandboxManager(), allow_test_runner=True)
        timeout_thread, timeout_pending = start(
            timeout_app, "timeout_case.py", action_kind="run_tests", timeout_seconds=2.0
        )
        timed_out = resume_approval(
            timeout_app, thread_id=timeout_thread, fingerprint=timeout_pending["fingerprint"]
        )
        timeout_receipt = timed_out["sandbox_result"].receipt
        assert timeout_receipt.status.value == "TIMEOUT" and timeout_receipt.timed_out
        cases["process_timeout"] = {
            "receipt": timeout_receipt.to_dict(),
            "trace": timed_out["local_trace"].to_dict(),
            "capability_enabled_by_factory": True,
            "command_boundary": "typed pytest only; no shell string",
        }
        transcript.append(f"RUN process_timeout: receipt={timeout_receipt.receipt_id}; status={timeout_receipt.status.value}; timeout_seconds=2")

    payload = {
        "goal_id": "L1-GOVERNED-EXECUTION-COMPLETION-001",
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_head_at_run": _git_head(),
        "scope": "local temporary workspace; LocalRestrictedBackend logical filesystem policy; no remote provider, Jaeger, or OS isolation claim",
        "cases": cases,
    }
    json_path = output / "L1_DEMO_RECEIPTS.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output / "L1_DEMO_TRANSCRIPT.md").write_text(
        "# L1 integrated graph demo transcript\n\n"
        f"Source HEAD at execution: `{payload['source_head_at_run']}`\n\n"
        "The graph retrieved governed local evidence, paused before the write, resumed with the exact fingerprint, and routed the operation through `ExecutionGateway` and `SandboxManager`.\n\n"
        + "\n".join(f"- {line}" for line in transcript)
        + "\n\nA LocalTrace was built from each graph result and the sandbox receipts. Replay was rejected within the same in-memory manager. No video was recorded. This demonstrates local logical workspace controls, not OS/network isolation or authenticated production identity.\n",
        encoding="utf-8",
    )
    return payload


def _git_head() -> str:
    import subprocess
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


if __name__ == "__main__":
    destination = ROOT / "evidence" / "l1-governed-execution-completion-20261010"
    result = run(destination)
    print(json.dumps({"cases": list(result["cases"]), "output": str(destination)}, ensure_ascii=False))
