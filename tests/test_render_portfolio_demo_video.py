"""Tests for the portfolio demo video renderer.

These tests guard two invariants that the freeze goal requires:

1. ``--check`` MUST be read-only. It must not modify the canonical
   artifacts (``evidence/portfolio_demo_v1.mp4``,
   ``evidence/portfolio_demo_v1.mp4.sha256``,
   ``evidence/portfolio_demo_v1.md``) so that reviewers and CI can
   invoke it without invalidating the freeze.

2. The frame-set SHA-256 MUST be deterministic between runs given the
   same evidence source. The MP4 wrapper hash may vary across ffmpeg
   builds but the rendered PNG content is byte-stable.

The tests are scoped to the read-only path and avoid heavy ffmpeg
invocations when possible.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
RENDERER = REPO_ROOT / "scripts" / "render_portfolio_demo_video.py"
MP4 = REPO_ROOT / "evidence" / "portfolio_demo_v1.mp4"
SHA = REPO_ROOT / "evidence" / "portfolio_demo_v1.mp4.sha256"
NOTE = REPO_ROOT / "evidence" / "portfolio_demo_v1.md"


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _artifacts_snapshot() -> dict[str, str]:
    out: dict[str, str] = {}
    for label, path in (("mp4", MP4), ("sha256", SHA), ("md", NOTE)):
        if path.is_file():
            out[label] = _hash(path)
    return out


def test_check_is_read_only_in_truth() -> None:
    """`--check` must not mutate the canonical evidence artifacts."""

    before = _artifacts_snapshot()
    result = subprocess.run(
        [sys.executable, str(RENDERER), "--check"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"--check exited {result.returncode}\nSTDOUT: {result.stdout}\n"
        f"STDERR: {result.stderr}"
    )
    after = _artifacts_snapshot()
    assert before == after, (
        "--check mutated evidence artifacts: "
        f"before={before} after={after}"
    )


def test_check_reports_in_sync_sidecar() -> None:
    """`--check` must report that the sidecar matches the mp4 in the repo."""

    result = subprocess.run(
        [sys.executable, str(RENDERER), "--check"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["mode"] == "check"
    assert payload["in_target_window"] is True
    assert 60.0 <= payload["duration_seconds"] <= 90.0
    assert payload["sidecar_in_sync"] is True, (
        f"sidecar/desync: {payload}"
    )
    assert payload["frame_set_sha256"], "frame_set_sha256 missing"
    assert len(payload["frame_set_sha256"]) == 64


def test_frame_set_sha256_is_deterministic() -> None:
    """Two consecutive `--check` runs must yield the same frame_set_sha256."""

    first = subprocess.run(
        [sys.executable, str(RENDERER), "--check"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    second = subprocess.run(
        [sys.executable, str(RENDERER), "--check"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert first.returncode == 0 and second.returncode == 0
    a = json.loads(first.stdout)["frame_set_sha256"]
    b = json.loads(second.stdout)["frame_set_sha256"]
    assert a == b, f"frame_set_sha256 not deterministic: {a} != {b}"