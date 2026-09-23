"""Permit-to-sandbox derivation and receipt boundary."""

from __future__ import annotations

import time
import uuid
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Iterable

from src.orchestration.state_graph import AuthorizationDecision, Permit

from .backend import LocalRestrictedBackend, SandboxBackend, SandboxHandle
from .exceptions import AuthorizationDenied, SandboxError, SandboxProvisioningError, SandboxViolation
from .filesystem import FilesystemRequest
from .process import ProcessRequest
from .receipt import BackendExecution, SandboxExecutionResult, SandboxReceipt, SandboxStatus, digest_text
from .specification import (
    Capability,
    FilesystemMode,
    NetworkMode,
    PROFILE_CAPABILITIES,
    PROFILE_EXECUTABLES,
    SandboxProfile,
    SandboxSpecification,
)


@dataclass(frozen=True)
class SandboxRequest:
    """Request envelope carrying the workspace scope and typed operation."""

    request_id: str
    workspace_root: Path
    operation: FilesystemRequest | ProcessRequest
    requested_profile: SandboxProfile | None = None

    def __post_init__(self) -> None:
        if not self.request_id.strip():
            raise ValueError("request_id is required")
        if self.operation.request_id != self.request_id:
            raise ValueError("sandbox and typed operation request ids must match")
        if self.requested_profile is not None:
            profile = self.requested_profile if isinstance(self.requested_profile, SandboxProfile) else SandboxProfile(self.requested_profile)
            object.__setattr__(self, "requested_profile", profile)
        object.__setattr__(self, "workspace_root", Path(self.workspace_root).expanduser().resolve())

    @property
    def capability(self) -> Capability:
        if isinstance(self.operation, FilesystemRequest):
            return Capability.FILESYSTEM_READ if self.operation.operation.value == "read" else Capability.FILESYSTEM_WRITE
        return self.operation.capability


class SandboxPolicy:
    """Derive a profile that is never broader than the permit."""

    DEFAULT_TIMEOUT_SECONDS = 30.0

    @staticmethod
    def _constraint_values(permit: Permit) -> dict[str, list[str]]:
        values: dict[str, list[str]] = defaultdict(list)
        for raw in permit.constraints:
            text = str(raw).strip()
            if not text:
                continue
            if "=" in text:
                key, value = text.split("=", 1)
                values[key.strip().casefold()].append(value.strip())
            elif text.casefold().startswith("timeout_") and text.casefold().endswith("s"):
                values["timeout_seconds"].append(text[8:-1])
        return values

    @staticmethod
    def _require_single(values: dict[str, list[str]], key: str) -> str:
        items = values.get(key, [])
        if len(items) != 1 or not items[0]:
            raise AuthorizationDenied(f"permit must declare exactly one {key}", code=f"{key.upper()}_REQUIRED")
        return items[0]

    def derive(self, permit: Permit | None, request: SandboxRequest) -> SandboxSpecification:
        if permit is None:
            raise AuthorizationDenied("a matching permit is required", code="PERMIT_REQUIRED")
        if permit.request_id != request.request_id:
            raise AuthorizationDenied("permit does not match the sandbox request", code="PERMIT_REQUEST_MISMATCH")
        if permit.decision is not AuthorizationDecision.ALLOW:
            raise AuthorizationDenied("permit decision is not ALLOW", code="PERMIT_NOT_ALLOWED")
        if not permit.is_valid():
            raise AuthorizationDenied("permit is expired or not yet valid", code="PERMIT_EXPIRED")

        values = self._constraint_values(permit)
        profile = SandboxProfile(self._require_single(values, "sandbox_profile"))
        if request.requested_profile is not None and request.requested_profile is not profile:
            raise AuthorizationDenied(
                "requested profile differs from the permit profile",
                code="PROFILE_ESCALATION",
            )

        permitted_root = Path(self._require_single(values, "workspace_root")).expanduser().resolve()
        try:
            request.workspace_root.relative_to(permitted_root)
        except ValueError as error:
            raise AuthorizationDenied("workspace is outside the permit scope", code="WORKSPACE_SCOPE_DENIED") from error

        raw_capabilities = values.get("capability", [])
        if not raw_capabilities:
            raise AuthorizationDenied("permit must declare capabilities", code="CAPABILITY_SCOPE_REQUIRED")
        try:
            permit_capabilities = frozenset(Capability(value) for value in raw_capabilities)
        except ValueError as error:
            raise AuthorizationDenied("permit contains an unknown capability", code="CAPABILITY_UNKNOWN") from error
        effective_capabilities = permit_capabilities & PROFILE_CAPABILITIES[profile]
        if request.capability not in effective_capabilities:
            raise AuthorizationDenied(
                "requested capability is not in the effective profile",
                code="CAPABILITY_NOT_ALLOWED",
            )

        write_scope = values.get("write_scope", ["none"])[0].casefold()
        writable_roots: tuple[Path, ...] = ()
        if Capability.FILESYSTEM_WRITE in effective_capabilities:
            if write_scope != "workspace":
                effective_capabilities = frozenset(
                    capability for capability in effective_capabilities if capability is not Capability.FILESYSTEM_WRITE
                )
                if request.capability is Capability.FILESYSTEM_WRITE:
                    raise AuthorizationDenied("filesystem write requires write_scope=workspace", code="WRITE_SCOPE_REQUIRED")
            else:
                writable_roots = (request.workspace_root,)

        timeout = self.DEFAULT_TIMEOUT_SECONDS
        if values.get("timeout_seconds"):
            try:
                timeout = float(self._require_single(values, "timeout_seconds"))
            except ValueError as error:
                raise AuthorizationDenied("timeout_seconds must be numeric", code="TIMEOUT_INVALID") from error

        network = values.get("network", [NetworkMode.DENY.value])[0].casefold()
        try:
            network_mode = NetworkMode(network)
        except ValueError as error:
            raise AuthorizationDenied("unknown network policy", code="NETWORK_POLICY_UNKNOWN") from error
        requires_os_network_isolation = network_mode is not NetworkMode.DENY or values.get("os_network_isolation", [""])[0].casefold() == "required"

        git_operations = values.get("git_operation", ["status", "diff", "log", "show"])
        return SandboxSpecification(
            workspace_root=request.workspace_root,
            profile=profile,
            filesystem_mode=FilesystemMode.WORKSPACE_WRITE if writable_roots else FilesystemMode.READ_ONLY,
            writable_roots=writable_roots,
            allowed_capabilities=effective_capabilities,
            allowed_executables=PROFILE_EXECUTABLES[profile],
            allowed_git_operations=git_operations,
            timeout_seconds=timeout,
            network_mode=network_mode,
            requires_os_network_isolation=requires_os_network_isolation,
        )


class SandboxManager:
    """Materialize a permit as a sandbox and always return a receipt."""

    def __init__(self, *, backend: SandboxBackend | None = None, policy: SandboxPolicy | None = None) -> None:
        self.backend = backend or LocalRestrictedBackend()
        self.policy = policy or SandboxPolicy()
        self._used_permits: set[str] = set()
        self._permit_lock = Lock()

    def execute(self, *, permit: Permit | None, request: SandboxRequest) -> SandboxExecutionResult:
        started = time.monotonic()
        specification: SandboxSpecification | None = None
        handle: SandboxHandle | None = None
        outcome: BackendExecution | None = None
        failure: SandboxError | None = None
        try:
            specification = self.policy.derive(permit, request)
            if permit is not None:
                with self._permit_lock:
                    if permit.permit_id in self._used_permits:
                        raise AuthorizationDenied(
                            "permit has already been consumed",
                            code="PERMIT_REPLAY",
                        )
                    self._used_permits.add(permit.permit_id)
            handle = self.backend.create(specification)
            outcome = self.backend.execute(handle, request.operation)
        except SandboxError as error:
            failure = error
        except (FileNotFoundError, OSError) as error:
            failure = SandboxViolation(str(error), code="LOCAL_IO_FAILED")
        except Exception as error:  # pragma: no cover - defensive receipt boundary
            failure = SandboxViolation(str(error), code="UNEXPECTED_SANDBOX_FAILURE")
        finally:
            if handle is not None:
                try:
                    self.backend.destroy(handle)
                except Exception as error:  # pragma: no cover - defensive cleanup
                    if failure is None:
                        failure = SandboxProvisioningError(str(error), code="SANDBOX_DESTROY_FAILED")

        if failure is not None:
            return self._result(
                request=request,
                permit=permit,
                specification=specification,
                sandbox_id=handle.sandbox_id if handle else "",
                status=SandboxStatus.DENIED,
                operation=self._operation_name(request),
                duration_ms=self._duration(started),
                error_code=failure.code,
                error_message=str(failure),
            )
        assert outcome is not None
        return self._result(
            request=request,
            permit=permit,
            specification=specification,
            sandbox_id=handle.sandbox_id if handle else "",
            status=outcome.status,
            operation=outcome.operation,
            duration_ms=self._duration(started),
            value=outcome.value,
            stdout=outcome.stdout,
            stderr=outcome.stderr,
            argv=outcome.argv,
            exit_code=outcome.exit_code,
            timed_out=outcome.timed_out,
            error_code=outcome.error_code,
            error_message=outcome.error_message,
        )

    def deny(
        self,
        *,
        request_id: str,
        permit_id: str,
        capability: str,
        error_code: str,
        error_message: str,
    ) -> SandboxExecutionResult:
        receipt_id = f"sbxreceipt-{uuid.uuid4().hex[:16]}"
        receipt = SandboxReceipt(
            receipt_id=receipt_id,
            request_id=request_id,
            permit_id=permit_id,
            sandbox_id="",
            capability=capability,
            profile="unknown",
            operation="authorization",
            status=SandboxStatus.DENIED,
            filesystem_mode="unknown",
            network_mode=NetworkMode.DENY.value,
            duration_ms=0,
            error_code=error_code,
            error_message=error_message,
            evidence_refs=(f"sandbox://{receipt_id}",),
        )
        return SandboxExecutionResult(receipt=receipt)

    @staticmethod
    def _duration(started: float) -> int:
        return max(0, int((time.monotonic() - started) * 1000))

    @staticmethod
    def _operation_name(request: SandboxRequest) -> str:
        if isinstance(request.operation, FilesystemRequest):
            return f"filesystem_{request.operation.operation.value}"
        return request.operation.capability.value

    def _result(
        self,
        *,
        request: SandboxRequest,
        permit: Permit | None,
        specification: SandboxSpecification | None,
        sandbox_id: str,
        status: SandboxStatus,
        operation: str,
        duration_ms: int,
        value: object = None,
        stdout: str = "",
        stderr: str = "",
        argv: tuple[str, ...] = (),
        exit_code: int | None = None,
        timed_out: bool = False,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> SandboxExecutionResult:
        receipt_id = f"sbxreceipt-{uuid.uuid4().hex[:16]}"
        receipt_argv = self._receipt_argv(request, argv)
        receipt = SandboxReceipt(
            receipt_id=receipt_id,
            request_id=request.request_id,
            permit_id=permit.permit_id if permit else "",
            sandbox_id=sandbox_id,
            capability=request.capability.value,
            profile=specification.profile.value if specification else "unknown",
            operation=operation,
            status=status,
            filesystem_mode=specification.filesystem_mode.value if specification else "unknown",
            network_mode=specification.network_mode.value if specification else NetworkMode.DENY.value,
            duration_ms=duration_ms,
            argv=receipt_argv,
            exit_code=exit_code,
            timed_out=timed_out,
            stdout_sha256=digest_text(stdout) if stdout else None,
            stderr_sha256=digest_text(stderr) if stderr else None,
            stdout_bytes=len(stdout.encode("utf-8", errors="replace")),
            stderr_bytes=len(stderr.encode("utf-8", errors="replace")),
            error_code=error_code,
            error_message=error_message,
            evidence_refs=(f"sandbox://{receipt_id}",),
        )
        return SandboxExecutionResult(receipt=receipt, value=value, stdout=stdout, stderr=stderr)

    @staticmethod
    def _receipt_argv(request: SandboxRequest, argv: tuple[str, ...]) -> tuple[str, ...]:
        if not argv:
            return ()
        if isinstance(request.operation, ProcessRequest):
            if request.operation.capability is Capability.RUN_TESTS:
                return ("python", *argv[1:])
            if request.operation.capability is Capability.GIT_READ:
                return ("git", *argv[1:])
        return tuple(argv)
