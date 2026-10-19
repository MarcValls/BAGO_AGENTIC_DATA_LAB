"""Semantic parity checks between ADL's legacy sandbox and pinned BER v0.1."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from runtime.ber import BerClient
from runtime.ber.compatibility import legacy_compatible_operation
from src.sandbox import (
    Capability,
    FilesystemOperation,
    FilesystemRequest,
    GitOperation,
    ProcessRequest,
    SandboxManager,
    SandboxProfile,
    SandboxRequest,
)
from src.orchestration.state_graph import AuthorizationDecision, Permit


def _permit(root: Path, request_id: str, *, profile: SandboxProfile, capabilities: tuple[Capability, ...], extra: tuple[str, ...] = ()) -> Permit:
    now = datetime.now(timezone.utc)
    constraints = [
        f"sandbox_profile={profile.value}",
        f"workspace_root={root}",
        *(f"capability={capability.value}" for capability in capabilities),
        *extra,
    ]
    return Permit(
        permit_id=f"parity-{request_id}",
        request_id=request_id,
        decision=AuthorizationDecision.ALLOW,
        rationale="legacy parity fixture",
        constraints=constraints,
        issued_at=now.isoformat(),
        expires_at=(now + timedelta(minutes=2)).isoformat(),
        signed_by="parity-test-authority",
    )


def _legacy_filesystem(root: Path, request_id: str, operation: FilesystemOperation, path: str, content: str | None = None):
    capability = Capability.FILESYSTEM_READ if operation is FilesystemOperation.READ else Capability.FILESYSTEM_WRITE
    profile = SandboxProfile.READ_ONLY_AGENT if capability is Capability.FILESYSTEM_READ else SandboxProfile.REPOSITORY_WORKER
    extra = () if capability is Capability.FILESYSTEM_READ else ("write_scope=workspace",)
    typed = FilesystemRequest(request_id, operation, path, content)
    request = SandboxRequest(request_id, root, typed)
    return SandboxManager().execute(
        permit=_permit(root, request_id, profile=profile, capabilities=(capability,), extra=extra),
        request=request,
    )


def _ber_effect(client: BerClient, effect_id: str, target: dict[str, object], arguments: dict[str, object]):
    operation = {"effect_id": effect_id, "target": target, "arguments": arguments}
    prepared = client.prepare_legacy_compatible(operation) if effect_id == "filesystem.write" else client.prepare(operation)
    approval = client.approve(prepared["challenge_id"], channel="desktop") if prepared["approval_required"] else None
    return prepared, approval, client.execute(prepared["challenge_id"])


def test_filesystem_read_has_same_semantic_result_in_legacy_and_ber(tmp_path: Path) -> None:
    legacy_root = tmp_path / "legacy-read"
    ber_root = tmp_path / "ber-read"
    legacy_root.mkdir()
    ber_root.mkdir()
    for root in (legacy_root, ber_root):
        (root / "input.txt").write_bytes(b"identical source bytes\r\n")

    legacy = _legacy_filesystem(legacy_root, "legacy-read", FilesystemOperation.READ, "input.txt")
    client = BerClient(workspace=ber_root)
    try:
        client.start()
        _, _, ber = _ber_effect(client, "filesystem.read", {"path": "input.txt"}, {})
    finally:
        client.close()

    assert legacy.ok and legacy.value == "identical source bytes\r\n"
    assert ber["result"]["ok"] is True
    assert ber["result"]["result"] == legacy.value
    assert legacy.receipt.receipt_id
    assert ber["receipt_id"] == ber["result"]["receipt_id"]


def test_filesystem_create_and_modify_have_matching_bytes_across_backends(tmp_path: Path) -> None:
    create_roots = (tmp_path / "legacy-create", tmp_path / "ber-create")
    for root in create_roots:
        root.mkdir()
    legacy_create = _legacy_filesystem(create_roots[0], "legacy-create", FilesystemOperation.WRITE, "created.txt", "created bytes")
    client = BerClient(workspace=create_roots[1])
    try:
        client.start()
        _, _, ber_create = _ber_effect(client, "filesystem.write", {"path": "created.txt"}, {"content": "created bytes", "expected_exists": False})
    finally:
        client.close()
    assert legacy_create.ok
    assert ber_create["result"]["ok"] is True
    assert (create_roots[0] / "created.txt").read_bytes() == (create_roots[1] / "created.txt").read_bytes()

    modify_roots = (tmp_path / "legacy-modify", tmp_path / "ber-modify")
    for root in modify_roots:
        root.mkdir()
        (root / "existing.txt").write_bytes(b"before\n")
    legacy_modify = _legacy_filesystem(modify_roots[0], "legacy-modify", FilesystemOperation.WRITE, "existing.txt", "after\n")
    expected_digest = hashlib.sha256(b"before\n").hexdigest()
    client = BerClient(workspace=modify_roots[1])
    try:
        client.start()
        _, _, ber_modify = _ber_effect(client, "filesystem.write", {"path": "existing.txt"}, {
            "content": "after\n",
            "expected_exists": True,
            "expected_sha256": expected_digest,
        })
    finally:
        client.close()
    assert legacy_modify.ok
    assert ber_modify["result"]["ok"] is True
    assert (modify_roots[0] / "existing.txt").read_bytes() == (modify_roots[1] / "existing.txt").read_bytes()


def test_legacy_compatibility_adapter_does_not_mutate_caller_operation() -> None:
    original = {"effect_id": "filesystem.write", "target": {"path": "a.txt"}, "arguments": {"content": "first\nsecond"}}
    adapted = legacy_compatible_operation(original)
    assert original["arguments"]["content"] == "first\nsecond"
    assert adapted["arguments"]["content"] == "first\nsecond".replace("\n", os.linesep)


def test_typed_git_status_matches_legacy_sandbox_and_ber_inspect(tmp_path: Path) -> None:
    legacy_root = tmp_path / "legacy-git"
    ber_root = tmp_path / "ber-git"
    legacy_root.mkdir()
    ber_root.mkdir()
    outputs = []
    for root in (legacy_root, ber_root):
        subprocess.run(["git", "init", str(root)], check=True, capture_output=True, text=True)
        (root / "pending.txt").write_text("untracked", encoding="utf-8")

    legacy_request_id = "legacy-git-status"
    typed = ProcessRequest(legacy_request_id, Capability.GIT_READ, "git", cwd=".", git_operation=GitOperation.STATUS)
    legacy_result = SandboxManager().execute(
        permit=_permit(legacy_root, legacy_request_id, profile=SandboxProfile.REPOSITORY_WORKER, capabilities=(Capability.GIT_READ,), extra=("git_operation=status",)),
        request=SandboxRequest(legacy_request_id, legacy_root, typed),
    )
    outputs.append(legacy_result.stdout)

    client = BerClient(workspace=ber_root)
    try:
        client.start()
        _, approval, ber_result = _ber_effect(client, "process.inspect", {"executable": "git", "cwd": str(ber_root)}, {"argv": ["status", "--porcelain=v1", "--untracked-files=all"]})
    finally:
        client.close()
    outputs.append(ber_result["result"]["stdout"])

    assert legacy_result.ok
    assert approval is None
    assert outputs[0] == outputs[1] == "?? pending.txt\n"
    assert legacy_result.receipt.receipt_id
    assert ber_result["receipt_id"] == ber_result["result"]["receipt_id"]


def test_typed_pytest_execution_matches_legacy_success_semantics(tmp_path: Path) -> None:
    roots = (tmp_path / "legacy-pytest", tmp_path / "ber-pytest")
    for root in roots:
        tests = root / "tests"
        tests.mkdir(parents=True)
        (tests / "test_parity.py").write_text("def test_same_contract():\n    assert 2 + 2 == 4\n", encoding="utf-8")

    legacy_request_id = "legacy-pytest"
    typed = ProcessRequest(legacy_request_id, Capability.RUN_TESTS, "pytest", arguments=("-q", "tests"), cwd=".")
    legacy_result = SandboxManager().execute(
        permit=_permit(roots[0], legacy_request_id, profile=SandboxProfile.TEST_RUNNER, capabilities=(Capability.FILESYSTEM_READ, Capability.RUN_TESTS), extra=("timeout_seconds=30",)),
        request=SandboxRequest(legacy_request_id, roots[0], typed),
    )

    client = BerClient(workspace=roots[1])
    try:
        client.start()
        prepared, approval, ber_result = _ber_effect(client, "process.execute", {"executable": sys.executable, "cwd": str(roots[1])}, {"argv": ["-m", "pytest", "-q", "tests"]})
    finally:
        client.close()

    ber_stdout = ber_result["result"]["stdout"]
    legacy_passed = re.search(r"\b1 passed\b", legacy_result.stdout) is not None
    ber_passed = re.search(r"\b1 passed\b", ber_stdout) is not None
    assert legacy_result.ok and ber_result["result"]["ok"] is True, (
        ber_result["result"].get("returncode"),
        ber_result["result"].get("stdout"),
        ber_result["result"].get("stderr"),
    )
    assert legacy_passed and ber_passed
    assert approval["request_id"] == prepared["request_id"] == ber_result["request_id"]
    assert legacy_result.receipt.receipt_id
    assert ber_result["receipt_id"] == ber_result["result"]["receipt_id"]
