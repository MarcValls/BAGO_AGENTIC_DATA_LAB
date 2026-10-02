"""One-command launcher for the BAGO Governed Knowledge Agent portfolio demo.

This file is packaging only. It creates/reuses a local virtual environment and
then delegates execution to the existing governed public E2E demo.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent
VENV_ROOT = REPO_ROOT / ".venv"
REQUIREMENTS = REPO_ROOT / "requirements.txt"
REQUIREMENTS_MARKER = VENV_ROOT / ".bago-demo-requirements.sha256"
DEFAULT_ARTIFACTS_DIR = REPO_ROOT / "demo_output" / "latest"


def _venv_python() -> Path:
    if os.name == "nt":
        return VENV_ROOT / "Scripts" / "python.exe"
    return VENV_ROOT / "bin" / "python"


def _requirements_digest() -> str:
    return hashlib.sha256(REQUIREMENTS.read_bytes()).hexdigest()


def _ensure_environment() -> Path:
    python = _venv_python()
    if not python.exists():
        subprocess.run(
            [sys.executable, "-m", "venv", str(VENV_ROOT)],
            cwd=REPO_ROOT,
            check=True,
        )

    digest = _requirements_digest()
    installed_digest = (
        REQUIREMENTS_MARKER.read_text(encoding="utf-8").strip()
        if REQUIREMENTS_MARKER.exists()
        else ""
    )
    if installed_digest != digest:
        subprocess.run(
            [str(python), "-m", "pip", "install", "-r", str(REQUIREMENTS)],
            cwd=REPO_ROOT,
            check=True,
        )
        REQUIREMENTS_MARKER.write_text(digest + "\n", encoding="utf-8")
    return python


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the governed knowledge-agent demo and materialize its evidence bundle."
    )
    parser.add_argument(
        "--no-bootstrap",
        action="store_true",
        help="use the current Python environment instead of creating/reusing .venv",
    )
    parser.add_argument("--json", action="store_true", help="print the machine-readable summary")
    parser.add_argument(
        "--write-evidence",
        action="store_true",
        help="also refresh evidence/public_e2e_demo.md after a passing run",
    )
    parser.add_argument(
        "--artifacts-dir",
        type=Path,
        default=DEFAULT_ARTIFACTS_DIR,
        help="directory for summary, receipts, trace and evaluation JSON",
    )
    args = parser.parse_args(argv)

    python = Path(sys.executable) if args.no_bootstrap else _ensure_environment()
    command = [
        str(python),
        str(REPO_ROOT / "scripts" / "bago.py"),
        "demo",
        "--artifacts-dir",
        str(args.artifacts_dir),
    ]
    if args.json:
        command.append("--json")
    if args.write_evidence:
        command.append("--write-evidence")

    completed = subprocess.run(command, cwd=REPO_ROOT, check=False)
    return int(completed.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
