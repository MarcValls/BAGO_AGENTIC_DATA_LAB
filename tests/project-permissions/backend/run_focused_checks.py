"""TeamCtl check driver that materializes its bounded pytest result as JSON."""
from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
import pytest


EVIDENCE = ROOT / ".bago/goals/project-file-operations-20261027/evidence/backend"
FULL = [
    "tests/project-permissions/backend",
    "tests/filesystem_tools/test_filesystem.py",
    "tests/test_agent_services_integration.py",
]
NEGATIVE = [
    "tests/project-permissions/backend/test_project_permissions.py",
    "tests/project-permissions/backend/test_saved_project_read.py",
    "tests/filesystem_tools/test_filesystem.py::FilesystemTests::test_authorization_missing_expired_wrong_root_hash_operation",
    "tests/filesystem_tools/test_filesystem.py::FilesystemTests::test_unsafe_paths",
    "tests/filesystem_tools/test_filesystem.py::FilesystemTests::test_edit_rejects_stale_target_and_preserves_new_content",
    "tests/test_agent_services_integration.py::test_project_policy_gates_filesystem_plan_and_host_apply_with_edit_copy_rename",
    "tests/test_agent_services_integration.py::test_saved_project_write_denial_and_revocation_block_apply",
    "tests/test_agent_services_integration.py::test_internal_paths_and_self_approval_are_unavailable",
]


def main() -> int:
    if len(sys.argv) != 3 or sys.argv[1] not in {"full", "negative"}:
        print("usage: run_focused_checks.py full|negative OUTPUT.json", file=sys.stderr)
        return 2
    mode, output_name = sys.argv[1:]
    args = FULL if mode == "full" else NEGATIVE
    captured = io.StringIO()
    with contextlib.redirect_stdout(captured), contextlib.redirect_stderr(captured):
        code = pytest.main(["-q", *args])
    rendered = captured.getvalue()
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    output = EVIDENCE / output_name
    output.write_text(json.dumps({
        "check": mode,
        "command": ["python", "-m", "pytest", "-q", *args],
        "pytest_exit_code": int(code),
        "result": "PASS" if int(code) == 0 else "FAIL",
        "output": rendered,
    }, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(rendered, end="")
    print(json.dumps({"evidence_path": output.relative_to(ROOT).as_posix(), "result": "PASS" if int(code) == 0 else "FAIL"}))
    return int(code)


if __name__ == "__main__":
    raise SystemExit(main())
