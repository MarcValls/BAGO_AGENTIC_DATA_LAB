"""Contract tests for the public root-level ``python demo.py`` command."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "demo.py"
REQUIRED = {
    "summary.json",
    "agent_run.json",
    "receipts.json",
    "trace.json",
    "evaluation.json",
}


def test_one_command_writes_five_linked_artifacts(tmp_path: Path) -> None:
    output = tmp_path / "demo-output"
    result = subprocess.run(
        [sys.executable, str(DEMO), "--output-dir", str(output)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=90,
    )
    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"
    assert REQUIRED == {path.name for path in output.iterdir() if path.is_file()}

    artifacts = {
        name: json.loads((output / name).read_text(encoding="utf-8"))
        for name in REQUIRED
    }
    summary = artifacts["summary.json"]
    agent = artifacts["agent_run.json"]
    receipts = artifacts["receipts.json"]
    trace = artifacts["trace.json"]
    evaluation = artifacts["evaluation.json"]

    assert summary["status"] == "PASS"
    assert summary["evaluation_status"] == "PASS"
    assert summary["evaluation_score"] == 1.0
    assert agent["run_id"] == summary["run_id"] == trace["run_id"]
    assert trace["trace_id"] == summary["trace_id"] == evaluation["trace_id"]
    assert receipts["run_id"] == agent["run_id"]
    assert receipts["trace_id"] == trace["trace_id"]
    assert len(trace["events"]) == summary["trace_events"]
    assert evaluation["status"] == "PASS"
    assert all(check["passed"] for check in evaluation["checks"])
    assert agent["query"] == summary["query"]
    assert agent["answer"] == summary["answer"]


def test_cli_documents_default_artifact_directory() -> None:
    result = subprocess.run(
        [sys.executable, str(DEMO), "--help"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0
    assert "demo_output" in result.stdout
    assert "--output-dir" in result.stdout
