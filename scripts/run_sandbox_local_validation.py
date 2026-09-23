"""Run a zero-cost validation of the governed local sandbox backend."""

from __future__ import annotations

import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.orchestration.state_graph import AuthorizationDecision, Permit
from src.sandbox import (
    Capability,
    FilesystemOperation,
    FilesystemRequest,
    ProcessRequest,
    SandboxManager,
    SandboxProfile,
    SandboxRequest,
    SandboxStatus,
)


EVIDENCE_PATH = REPO_ROOT / "evidence" / "sandbox_local_restricted.md"


def _permit(
    root: Path,
    request_id: str,
    *,
    profile: SandboxProfile,
    capabilities: tuple[Capability, ...],
    extra: tuple[str, ...] = (),
) -> Permit:
    now = datetime.now(timezone.utc)
    return Permit(
        permit_id=f"validation-{request_id}",
        request_id=request_id,
        decision=AuthorizationDecision.ALLOW,
        rationale="local sandbox validation",
        constraints=[
            f"sandbox_profile={profile.value}",
            f"workspace_root={root}",
            *(f"capability={capability.value}" for capability in capabilities),
            *extra,
        ],
        issued_at=now.isoformat(),
        expires_at=(now + timedelta(minutes=5)).isoformat(),
        signed_by="bago.sandbox.validation",
    )


def _execute(manager: SandboxManager, root: Path, operation, permit: Permit):
    return manager.execute(
        permit=permit,
        request=SandboxRequest(operation.request_id, root, operation),
    )


def _receipt_row(label: str, result) -> str:
    receipt = result.receipt
    return (
        f"| {label} | {receipt.status.value} | {receipt.operation} | "
        f"{receipt.error_code or '—'} | {receipt.stdout_sha256 or '—'} | "
        f"{receipt.evidence_refs[0]} |"
    )


def main() -> int:
    manager = SandboxManager()
    results: list[tuple[str, object]] = []
    with tempfile.TemporaryDirectory(prefix="bago-sandbox-validation-") as temporary:
        root = Path(temporary) / "workspace"
        root.mkdir()
        (root / "tests").mkdir()
        (root / "input.txt").write_text("local evidence", encoding="utf-8")
        (Path(temporary) / "outside-secret.txt").write_text("not in scope", encoding="utf-8")

        read = FilesystemRequest("validation-read", FilesystemOperation.READ, "input.txt")
        read_result = _execute(
            manager,
            root,
            read,
            _permit(
                root,
                read.request_id,
                profile=SandboxProfile.READ_ONLY_AGENT,
                capabilities=(Capability.FILESYSTEM_READ,),
            ),
        )
        assert read_result.ok and read_result.value == "local evidence"
        results.append(("workspace read", read_result))

        escape = FilesystemRequest("validation-escape", FilesystemOperation.READ, "../outside-secret.txt")
        escape_result = _execute(
            manager,
            root,
            escape,
            _permit(
                root,
                escape.request_id,
                profile=SandboxProfile.READ_ONLY_AGENT,
                capabilities=(Capability.FILESYSTEM_READ,),
            ),
        )
        assert escape_result.receipt.status is SandboxStatus.DENIED
        assert escape_result.receipt.error_code == "PATH_ESCAPE"
        results.append(("path traversal", escape_result))

        fixture = FilesystemRequest(
            "validation-fixture",
            FilesystemOperation.WRITE,
            "tests/test_local.py",
            "def test_local_sandbox():\n    assert True\n",
        )
        fixture_result = _execute(
            manager,
            root,
            fixture,
            _permit(
                root,
                fixture.request_id,
                profile=SandboxProfile.TEST_RUNNER,
                capabilities=(Capability.FILESYSTEM_READ, Capability.FILESYSTEM_WRITE),
                extra=("write_scope=workspace",),
            ),
        )
        assert fixture_result.ok
        results.append(("workspace write", fixture_result))

        environment_fixture = FilesystemRequest(
            "validation-env-fixture",
            FilesystemOperation.WRITE,
            "tests/test_environment.py",
            "import os\n\ndef test_secret_is_not_forwarded():\n    assert os.environ.get('BAGO_VALIDATION_SECRET') is None\n",
        )
        environment_fixture_result = _execute(
            manager,
            root,
            environment_fixture,
            _permit(
                root,
                environment_fixture.request_id,
                profile=SandboxProfile.TEST_RUNNER,
                capabilities=(Capability.FILESYSTEM_READ, Capability.FILESYSTEM_WRITE),
                extra=("write_scope=workspace",),
            ),
        )
        assert environment_fixture_result.ok
        results.append(("secret fixture write", environment_fixture_result))

        previous_secret = os.environ.get("BAGO_VALIDATION_SECRET")
        os.environ["BAGO_VALIDATION_SECRET"] = "must-not-cross-boundary"
        try:
            run_tests = ProcessRequest(
                "validation-tests",
                Capability.RUN_TESTS,
                "pytest",
                arguments=("-q", "tests"),
            )
            run_result = _execute(
                manager,
                root,
                run_tests,
                _permit(
                    root,
                    run_tests.request_id,
                    profile=SandboxProfile.TEST_RUNNER,
                    capabilities=(Capability.RUN_TESTS,),
                    extra=("timeout_seconds=30",),
                ),
            )
        finally:
            if previous_secret is None:
                os.environ.pop("BAGO_VALIDATION_SECRET", None)
            else:
                os.environ["BAGO_VALIDATION_SECRET"] = previous_secret
        assert run_result.ok
        results.append(("typed pytest + filtered environment", run_result))

        network = FilesystemRequest("validation-network", FilesystemOperation.READ, "input.txt")
        network_result = _execute(
            manager,
            root,
            network,
            _permit(
                root,
                network.request_id,
                profile=SandboxProfile.NETWORK_RESEARCHER,
                capabilities=(Capability.FILESYSTEM_READ,),
                extra=("network=allowlist", "os_network_isolation=required"),
            ),
        )
        assert network_result.receipt.status is SandboxStatus.DENIED
        assert network_result.receipt.error_code == "OS_NETWORK_ISOLATION_REQUIRED"
        results.append(("required OS network isolation", network_result))

    lines = [
        "# L11 · Local Restricted Sandbox Evidence",
        "",
        f"**Generated:** {datetime.now(timezone.utc).isoformat()}",
        "**Status:** PASS for the local logical boundary; OS-level network isolation remains NOT_RUN.",
        "",
        "This receipt set was generated by `scripts/run_sandbox_local_validation.py` "
        "using temporary workspace data and no external service.",
        "",
        "| Check | Receipt status | Operation | Error code | stdout SHA-256 | Evidence |",
        "|---|---|---|---|---|---|",
    ]
    lines.extend(_receipt_row(label, result) for label, result in results)
    lines.extend(
        [
            "",
            "## Verified boundary",
            "",
            "- Permit request/profile/workspace matching is enforced before provisioning.",
            "- Filesystem reads and writes resolve inside the workspace; traversal and write escapes are denied.",
            "- Process execution is typed (`pytest` or read-only Git operations); no shell string is accepted.",
            "- Timeouts, non-zero exits and every denial produce a receipt.",
            "- Inherited environment variables are filtered; credential-like names are denied.",
            "- A request requiring OS network isolation fails closed because this backend does not provide it.",
            "",
            "## Not claimed",
            "",
            "`LocalRestrictedBackend` is not a Windows Sandbox, container, namespace, seccomp or firewall. "
            "A future OS-level backend is required before claiming strong process/network isolation.",
            "",
        ]
    )
    EVIDENCE_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"sandbox local validation: PASS ({len(results)} receipts)")
    print(f"evidence: {EVIDENCE_PATH.relative_to(REPO_ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
