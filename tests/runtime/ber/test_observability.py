from __future__ import annotations

from pathlib import Path
import json
import subprocess
import sys
import hashlib

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from evaluation.local_evals import EvaluationStatus, LocalTraceEvaluator  # noqa: E402
from observability.ber_effect_trace import local_trace_from_ber_effect  # noqa: E402
from runtime.ber import BerClient  # noqa: E402
from runtime.ber.client import ARTIFACT_SHA256  # noqa: E402


def test_real_ber_receipt_projects_to_adl_local_trace_and_ber_evaluation(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    client = BerClient(workspace=workspace)
    try:
        client.start()
        prepared = client.prepare({
            "effect_id": "filesystem.write",
            "target": {"path": "observed.txt"},
            "arguments": {"content": "BER result", "expected_exists": False},
        })
        approval = client.approve(prepared["challenge_id"], channel="desktop")
        execution = client.execute(prepared["challenge_id"])

        trace = local_trace_from_ber_effect(
            prepared,
            approval,
            execution,
            artifact_sha256=ARTIFACT_SHA256,
        )
        report = LocalTraceEvaluator().evaluate_ber_effect(trace)

        assert (workspace / "observed.txt").read_text(encoding="utf-8") == "BER result"
        assert trace.run_id == execution["ber_execution_id"]
        assert trace.events[1].attributes["receipt_id"] == execution["receipt_id"]
        assert trace.events[1].attributes["permit_id"] == execution["authorization"]["permit_id"]
        assert report.status is EvaluationStatus.PASS
        assert report.score == 1.0
        assert "permit_token" not in trace.to_json()
        assert report.evidence_refs == (f"ber://receipt/{execution['receipt_id']}",)
    finally:
        client.close()


def test_ber_evaluation_fails_when_execution_request_or_receipt_identity_drifted() -> None:
    prepared = {"request_id": "request-A", "effect_id": "filesystem.write", "approval_required": True}
    approval = {"request_id": "request-A", "state": "approved", "decision_id": "decision-A", "proof_id": "proof-A"}
    execution = {
        "ber_execution_id": "ber-exec-A",
        "request_id": "request-B",
        "receipt_id": "receipt-outer-B",
        "authorization": {"state": "consumed", "permit_id": "permit-A", "decision_id": "decision-A", "proof_id": "proof-A"},
        "result": {"executed": True, "ok": True, "receipt_id": "receipt-inner-A"},
    }

    trace = local_trace_from_ber_effect(prepared, approval, execution, artifact_sha256=ARTIFACT_SHA256)
    report = LocalTraceEvaluator().evaluate_ber_effect(trace)

    results = {check.name: check.passed for check in report.checks}
    assert report.status is EvaluationStatus.FAIL
    assert results["ber_request_linkage"] is False
    assert results["ber_receipt_linkage"] is False


def test_interactive_effect_demo_requires_explicit_confirmation_and_emits_evidence(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    script = ROOT / "scripts" / "ber_effect_demo.py"
    command = [
        sys.executable,
        str(script),
        "--workspace",
        str(workspace),
        "--effect",
        "filesystem.write",
        "--path",
        "report.txt",
        "--content",
        "confirmed by local user prompt",
    ]

    denied = subprocess.run(command, input="no\n", capture_output=True, text=True, check=False)
    assert denied.returncode == 3
    assert json.loads(denied.stdout)["status"] == "NOT_EXECUTED"
    assert not (workspace / "report.txt").exists()

    approved = subprocess.run(command, input="APROBAR filesystem.write\n", capture_output=True, text=True, check=False)
    record = json.loads(approved.stdout)
    assert approved.returncode == 0
    assert record["status"] == "PASS"
    assert record["execution"]["authorization"]["permit_id"]
    assert record["evaluation"]["status"] == "PASS"
    assert record["trace"]["run_id"] == record["execution"]["ber_execution_id"]
    assert (workspace / "report.txt").read_text(encoding="utf-8") == "confirmed by local user prompt"

    old_digest = hashlib.sha256(b"confirmed by local user prompt").hexdigest()
    update = subprocess.run(
        [*command[:-1], "updated with confirmation", "--expected-sha256", old_digest],
        input="APROBAR filesystem.write\n",
        capture_output=True,
        text=True,
        check=False,
    )
    updated = json.loads(update.stdout)
    assert update.returncode == 0
    assert updated["status"] == "PASS"
    assert (workspace / "report.txt").read_text(encoding="utf-8") == "updated with confirmation"


def test_typed_process_inspection_is_recorded_without_approval_prompt(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    subprocess.run(["git", "init", str(workspace)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    script = ROOT / "scripts" / "ber_effect_demo.py"
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--workspace",
            str(workspace),
            "--effect",
            "process.inspect",
            "--executable",
            "git",
            "--cwd",
            str(workspace),
            "--argv",
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    record = json.loads(result.stdout)

    assert result.returncode == 0
    assert record["status"] == "PASS"
    assert record["approval"] is None
    assert "Escribe APROBAR" not in result.stderr
    assert record["execution"]["result"]["effect_id"] == "process.inspect"
    assert record["evaluation"]["status"] == "PASS"
