from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from src.runtime.ber import BerClient, BerRuntimeError
from src.runtime.ber.client import ARTIFACT_SHA256


def _client(tmp_path: Path) -> tuple[BerClient, Path]:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    return BerClient(workspace=workspace), workspace


def test_client_is_inert_until_explicit_start_and_reports_verified_identity(tmp_path: Path) -> None:
    client, _ = _client(tmp_path)
    assert client.running is False
    with pytest.raises(BerRuntimeError) as error:
        client.status()
    assert error.value.code == "ber_not_running"
    status = client.start()
    assert status["healthy"] is True
    assert status["ber_version"] == "0.1.0"
    assert status["artifact_sha256"] == ARTIFACT_SHA256
    assert "filesystem.delete" in status["blocked_effects"]
    client.close()
    assert client.running is False


def test_create_modify_and_stale_write_use_bago_receipts(tmp_path: Path) -> None:
    client, workspace = _client(tmp_path)
    try:
        client.start()
        prepared = client.prepare({"effect_id": "filesystem.write", "target": {"path": "note.txt"}, "arguments": {"content": "first", "expected_exists": False}})
        client.approve(prepared["challenge_id"], channel="desktop")
        created = client.execute(prepared["challenge_id"])
        assert created["receipt_id"].startswith("filesystem-write:sha256:")
        assert (workspace / "note.txt").read_text(encoding="utf-8") == "first"

        old_digest = hashlib.sha256(b"first").hexdigest()
        update = client.prepare({"effect_id": "filesystem.write", "target": {"path": "note.txt"}, "arguments": {"content": "second", "expected_exists": True, "expected_sha256": old_digest}})
        client.approve(update["challenge_id"], channel="desktop")
        modified = client.execute(update["challenge_id"])
        assert modified["receipt_id"].startswith("filesystem-write:sha256:")
        assert (workspace / "note.txt").read_text(encoding="utf-8") == "second"

        stale = client.prepare({"effect_id": "filesystem.write", "target": {"path": "note.txt"}, "arguments": {"content": "third", "expected_exists": True, "expected_sha256": hashlib.sha256(b"second").hexdigest()}})
        client.approve(stale["challenge_id"], channel="desktop")
        (workspace / "note.txt").write_text("external", encoding="utf-8")
        with pytest.raises(BerRuntimeError) as error:
            client.execute(stale["challenge_id"])
        assert error.value.code == "filesystem_precondition_stale"
        assert (workspace / "note.txt").read_text(encoding="utf-8") == "external"
    finally:
        client.close()


def test_typed_process_receipt_and_permit_replay_denial(tmp_path: Path) -> None:
    client, workspace = _client(tmp_path)
    subprocess.run(["git", "init", str(workspace)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        client.start()
        inspected = client.prepare({"effect_id": "process.inspect", "target": {"executable": "git", "cwd": str(workspace)}, "arguments": {"argv": ["status", "--porcelain=v1", "--untracked-files=all"]}})
        assert inspected["approval_required"] is False
        inspection = client.execute(inspected["challenge_id"])
        assert inspection["receipt_id"].startswith("bago-ber-process:sha256:")

        prepared = client.prepare({"effect_id": "process.execute", "target": {"executable": "git", "cwd": str(workspace)}, "arguments": {"argv": ["status", "--porcelain=v1", "--untracked-files=all"]}})
        client.approve(prepared["challenge_id"], channel="desktop")
        result = client.execute(prepared["challenge_id"])
        assert result["receipt_id"].startswith("bago-ber-process:sha256:")
        with pytest.raises(BerRuntimeError) as error:
            client.execute(prepared["challenge_id"])
        assert error.value.code == "ber_challenge_replay"
    finally:
        client.close()


def test_bundle_hash_is_pinned_and_unmodified_before_start(tmp_path: Path) -> None:
    client, _ = _client(tmp_path)
    artifact = client.artifact
    lock = json.loads(client.lockfile.read_text(encoding="utf-8"))
    assert hashlib.sha256(artifact.read_bytes()).hexdigest() == ARTIFACT_SHA256
    assert lock["artifact_sha256"] == ARTIFACT_SHA256

    altered = tmp_path / "altered.zip"
    altered.write_bytes(artifact.read_bytes() + b"tamper")
    client.artifact = altered
    with pytest.raises(BerRuntimeError) as error:
        client.start()
    assert error.value.code == "ber_package_integrity_failed"
