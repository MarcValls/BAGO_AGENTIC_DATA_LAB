"""Run the independent HTTP matrix and retain reviewable evidence once."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    directory = Path(__file__).resolve().parent
    repo = directory.parents[3]
    destination = directory / "http"
    if destination.exists():
        raise RuntimeError("Final HTTP evidence already exists; preserve it and review before another run.")
    destination.mkdir()
    os.chdir(repo)
    env = dict(os.environ, ADL_CSV_FLOW_EVIDENCE_DIR=str(destination),
               BAGO_OTEL_EXPORTER_OTLP_ENDPOINT="", OTEL_TRACES_SAMPLER="always_on")
    started = datetime.now(timezone.utc).isoformat()
    command = [sys.executable, "-m", "pytest", "-q", "tests/test_csv_chat_flow.py"]
    completed = subprocess.run(command, capture_output=True, text=True, env=env, timeout=240)
    log = directory / "pytest.log"
    log.write_text(completed.stdout + completed.stderr, encoding="utf-8")
    print(completed.stdout + completed.stderr, flush=True)
    if completed.returncode:
        return completed.returncode
    spec = importlib.util.spec_from_file_location("independent_csv_flow", repo / "tests/test_csv_chat_flow.py")
    tests = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tests)
    reports = {path.stem: json.loads(path.read_text()) for path in destination.glob("*.json")}
    assert set(reports) == set(tests.CASES)
    assert all(report["status"] == "PASS" for report in reports.values())
    preserved = ["docs/verification/user-demand-20261101", ".bago/team/runtime", "src/knowledge/local_rag.py", "src/conversations/library.py"]
    diff = subprocess.run(["git", "diff", "--exit-code", "HEAD", "--", *preserved], capture_output=True, text=True)
    assert diff.returncode == 0, diff.stdout + diff.stderr
    source = repo / "docs/verification/csv-chat-20261101/parser/pedidos-original.csv"
    assert source.read_bytes() == tests.ORIGINAL
    manifest = [{"path": str(path.relative_to(repo)), "sha256": sha256(path)}
                for path in sorted(destination.glob("*.json"))]
    summary = {
        "status": "PASS", "scope": "57 real HTTP cases, synthetic files and state, controlled provider interpretation",
        "started_at": started, "finished_at": datetime.now(timezone.utc).isoformat(),
        "command": command, "pass": len(reports), "fail": 0,
        "original_csv": {"bytes": len(tests.ORIGINAL), "sha256": sha256(source),
            "expected_row_totals": ["199.80", "54.00", "47.50"], "expected_pending": "247.30", "expected_total": "301.30"},
        "historical_and_existing_files_unchanged": {"paths": preserved, "git_diff_exit_code": diff.returncode},
        "runtime_state_location": "/tmp", "interpreter": "controlled query plan; no live AI model",
        "not_run": ["Windows", "live provider", "user installation", "deployment", "global STOP outside CSV route"],
        "source_sha256": reports["F10"]["source_sha256"],
        "test_summary": [{"case": case, "status": reports[case]["status"],
            "csv_read_count": reports[case]["csv_read_count"], "query_provider_calls": reports[case]["query_provider_calls"],
            "error_code": reports[case].get("code")} for case in tests.CASES],
        "evidence": manifest, "pytest_log_sha256": sha256(log),
    }
    (directory / "SUMMARY.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "cases": len(reports), "summary": str(directory / "SUMMARY.json")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
