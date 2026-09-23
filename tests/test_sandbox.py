"""Security and evidence contracts for the governed local sandbox."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from src.execution import ExecutionGateway
from src.orchestration.state_graph import AuthorizationDecision, EffectType, ExecutionRequest, Permit
from src.sandbox import (
    Capability,
    FilesystemOperation,
    FilesystemRequest,
    GitOperation,
    ProcessRequest,
    SandboxFilesystem,
    SandboxManager,
    SandboxProfile,
    SandboxRequest,
    SandboxSpecification,
    SandboxStatus,
)
from src.sandbox.exceptions import PathEscapeViolation


def _permit(
    root: Path,
    request_id: str,
    *,
    profile: SandboxProfile = SandboxProfile.READ_ONLY_AGENT,
    capabilities: tuple[Capability, ...] = (Capability.FILESYSTEM_READ,),
    extra: tuple[str, ...] = (),
) -> Permit:
    now = datetime.now(timezone.utc)
    constraints = [
        f"sandbox_profile={profile.value}",
        f"workspace_root={root}",
        *(f"capability={capability.value}" for capability in capabilities),
        *extra,
    ]
    return Permit(
        permit_id=f"permit-{request_id}",
        request_id=request_id,
        decision=AuthorizationDecision.ALLOW,
        rationale="sandbox test permit",
        constraints=constraints,
        issued_at=now.isoformat(),
        expires_at=(now + timedelta(minutes=5)).isoformat(),
        signed_by="sandbox-test-authority",
    )


def _request(root: Path, operation, *, profile: SandboxProfile | None = None) -> SandboxRequest:
    return SandboxRequest(
        request_id=operation.request_id,
        workspace_root=root,
        operation=operation,
        requested_profile=profile,
    )


def test_filesystem_rejects_path_escape(tmp_path: Path):
    outside = tmp_path.parent / "sandbox-outside-secret.txt"
    outside.write_text("secret", encoding="utf-8")
    specification = SandboxSpecification.from_profile(
        tmp_path,
        SandboxProfile.READ_ONLY_AGENT,
        allowed_capabilities=(Capability.FILESYSTEM_READ,),
    )

    with pytest.raises(PathEscapeViolation):
        SandboxFilesystem(specification).resolve_read("../sandbox-outside-secret.txt")


def test_read_only_permit_denies_write(tmp_path: Path):
    operation = FilesystemRequest("req-write-denied", FilesystemOperation.WRITE, "result.txt", "nope")
    result = SandboxManager().execute(
        permit=_permit(tmp_path, operation.request_id),
        request=_request(tmp_path, operation),
    )

    assert result.receipt.status is SandboxStatus.DENIED
    assert result.receipt.error_code == "CAPABILITY_NOT_ALLOWED"
    assert not (tmp_path / "result.txt").exists()


def test_workspace_read_returns_receipt_and_evidence(tmp_path: Path):
    target = tmp_path / "input.txt"
    target.write_text("governed", encoding="utf-8")
    operation = FilesystemRequest("req-read", FilesystemOperation.READ, "input.txt")
    result = SandboxManager().execute(
        permit=_permit(tmp_path, operation.request_id),
        request=_request(tmp_path, operation),
    )

    assert result.ok
    assert result.value == "governed"
    assert result.receipt.evidence_refs == (f"sandbox://{result.receipt.receipt_id}",)
    assert result.receipt.profile == SandboxProfile.READ_ONLY_AGENT.value


def test_permit_replay_is_denied_by_sandbox_manager(tmp_path: Path):
    (tmp_path / "input.txt").write_text("once", encoding="utf-8")
    operation = FilesystemRequest("req-replay", FilesystemOperation.READ, "input.txt")
    permit = _permit(tmp_path, operation.request_id)
    manager = SandboxManager()

    first = manager.execute(permit=permit, request=_request(tmp_path, operation))
    second = manager.execute(permit=permit, request=_request(tmp_path, operation))

    assert first.ok
    assert second.receipt.status is SandboxStatus.DENIED
    assert second.receipt.error_code == "PERMIT_REPLAY"


def test_agent_cannot_select_more_privileged_profile(tmp_path: Path):
    operation = FilesystemRequest("req-profile", FilesystemOperation.READ, "input.txt")
    (tmp_path / "input.txt").write_text("ok", encoding="utf-8")
    result = SandboxManager().execute(
        permit=_permit(tmp_path, operation.request_id),
        request=_request(tmp_path, operation, profile=SandboxProfile.REPOSITORY_WORKER),
    )

    assert result.receipt.status is SandboxStatus.DENIED
    assert result.receipt.error_code == "PROFILE_ESCALATION"


def test_permit_workspace_scope_cannot_escape(tmp_path: Path):
    permitted = tmp_path / "permitted"
    requested = tmp_path / "requested"
    permitted.mkdir()
    requested.mkdir()
    operation = FilesystemRequest("req-scope", FilesystemOperation.READ, "missing.txt")
    result = SandboxManager().execute(
        permit=_permit(permitted, operation.request_id),
        request=_request(requested, operation),
    )

    assert result.receipt.status is SandboxStatus.DENIED
    assert result.receipt.error_code == "WORKSPACE_SCOPE_DENIED"


def test_structured_pytest_request_runs_without_shell(tmp_path: Path):
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_local.py").write_text("def test_local():\n    assert 2 + 2 == 4\n", encoding="utf-8")
    operation = ProcessRequest(
        "req-tests",
        Capability.RUN_TESTS,
        "pytest",
        arguments=("-q", "tests"),
    )
    permit = _permit(
        tmp_path,
        operation.request_id,
        profile=SandboxProfile.TEST_RUNNER,
        capabilities=(Capability.FILESYSTEM_READ, Capability.FILESYSTEM_WRITE, Capability.RUN_TESTS),
        extra=("write_scope=workspace", "timeout_seconds=30"),
    )
    result = SandboxManager().execute(permit=permit, request=_request(tmp_path, operation))

    assert result.ok
    assert result.receipt.operation == "run_tests"
    assert result.receipt.argv[:3] == ("python", "-m", "pytest")
    assert "1 passed" in result.stdout


def test_process_tool_is_allowlisted(tmp_path: Path):
    operation = ProcessRequest("req-tool", Capability.RUN_TESTS, "cmd", arguments=("/c", "echo nope"))
    permit = _permit(
        tmp_path,
        operation.request_id,
        profile=SandboxProfile.TEST_RUNNER,
        capabilities=(Capability.RUN_TESTS,),
    )
    result = SandboxManager().execute(permit=permit, request=_request(tmp_path, operation))

    assert result.receipt.status is SandboxStatus.DENIED
    assert result.receipt.error_code == "TOOL_NOT_ALLOWED"


def test_git_operation_is_typed_and_allowlisted(tmp_path: Path):
    operation = ProcessRequest(
        "req-git-diff",
        Capability.GIT_READ,
        "git",
        git_operation=GitOperation.DIFF,
    )
    permit = _permit(
        tmp_path,
        operation.request_id,
        profile=SandboxProfile.REPOSITORY_WORKER,
        capabilities=(Capability.GIT_READ,),
        extra=("git_operation=status",),
    )
    result = SandboxManager().execute(permit=permit, request=_request(tmp_path, operation))

    assert result.receipt.status is SandboxStatus.DENIED
    assert result.receipt.error_code == "GIT_OPERATION_DENIED"


def test_timeout_is_a_receipted_controlled_failure(tmp_path: Path):
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_slow.py").write_text(
        "import time\n\ndef test_slow():\n    time.sleep(0.5)\n",
        encoding="utf-8",
    )
    operation = ProcessRequest(
        "req-timeout",
        Capability.RUN_TESTS,
        "pytest",
        arguments=("-q", "tests"),
        timeout_seconds=0.05,
    )
    permit = _permit(
        tmp_path,
        operation.request_id,
        profile=SandboxProfile.TEST_RUNNER,
        capabilities=(Capability.RUN_TESTS,),
        extra=("timeout_seconds=0.05",),
    )
    result = SandboxManager().execute(permit=permit, request=_request(tmp_path, operation))

    assert result.receipt.status is SandboxStatus.TIMEOUT
    assert result.receipt.timed_out
    assert result.receipt.error_code == "TIMEOUT"


def test_sensitive_inherited_environment_is_not_forwarded(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("BAGO_TEST_SECRET", "must-not-leak")
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_env.py").write_text(
        "import os\n\ndef test_no_secret():\n    assert os.environ.get('BAGO_TEST_SECRET') is None\n",
        encoding="utf-8",
    )
    operation = ProcessRequest(
        "req-env",
        Capability.RUN_TESTS,
        "pytest",
        arguments=("-q", "tests"),
    )
    permit = _permit(
        tmp_path,
        operation.request_id,
        profile=SandboxProfile.TEST_RUNNER,
        capabilities=(Capability.RUN_TESTS,),
    )
    result = SandboxManager().execute(permit=permit, request=_request(tmp_path, operation))

    assert result.ok
    assert "1 passed" in result.stdout


def test_network_isolation_requirement_fails_closed(tmp_path: Path):
    operation = FilesystemRequest("req-network", FilesystemOperation.READ, "input.txt")
    (tmp_path / "input.txt").write_text("local", encoding="utf-8")
    permit = _permit(
        tmp_path,
        operation.request_id,
        profile=SandboxProfile.NETWORK_RESEARCHER,
        capabilities=(Capability.FILESYSTEM_READ,),
        extra=("network=allowlist", "os_network_isolation=required"),
    )
    result = SandboxManager().execute(permit=permit, request=_request(tmp_path, operation))

    assert result.receipt.status is SandboxStatus.DENIED
    assert result.receipt.error_code == "OS_NETWORK_ISOLATION_REQUIRED"


def test_execution_gateway_requires_typed_sandbox_request(tmp_path: Path):
    request = ExecutionRequest(
        request_id="req-gateway-missing",
        tool_name="file_reader",
        effect_type=EffectType.READ,
        parameters={},
        proposed_by="test",
        context_revision="test",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
    permit = _permit(tmp_path, request.request_id)
    result = ExecutionGateway().execute(request=request, permit=permit, sandbox_request=None)

    assert result.receipt.status is SandboxStatus.DENIED
    assert result.receipt.error_code == "SANDBOX_REQUEST_REQUIRED"


def test_execution_gateway_delegates_to_sandbox(tmp_path: Path):
    (tmp_path / "input.txt").write_text("gateway", encoding="utf-8")
    request = ExecutionRequest(
        request_id="req-gateway",
        tool_name="file_reader",
        effect_type=EffectType.READ,
        parameters={"path": "input.txt"},
        proposed_by="test",
        context_revision="test",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
    operation = FilesystemRequest(request.request_id, FilesystemOperation.READ, "input.txt")
    sandbox_request = SandboxRequest(request.request_id, tmp_path, operation)
    result = ExecutionGateway().execute(
        request=request,
        permit=_permit(tmp_path, request.request_id),
        sandbox_request=sandbox_request,
    )

    assert result.ok
    assert result.value == "gateway"
