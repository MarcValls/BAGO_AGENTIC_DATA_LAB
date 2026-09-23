"""Local restricted sandbox backend.

This backend enforces BAGO's logical boundaries and typed command policy. It is
not an OS-level container. A request that asks for OS network isolation fails
closed instead of silently executing with weaker isolation.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .exceptions import SandboxProvisioningError, SandboxViolation
from .filesystem import FilesystemOperation, FilesystemRequest, SandboxFilesystem
from .process import GitOperation, ProcessRequest
from .receipt import BackendExecution, SandboxStatus
from .specification import Capability, NetworkMode, SandboxSpecification


class SandboxBackend(Protocol):
    def create(self, specification: SandboxSpecification) -> "SandboxHandle": ...

    def execute(self, sandbox: "SandboxHandle", request: FilesystemRequest | ProcessRequest) -> BackendExecution: ...

    def destroy(self, sandbox: "SandboxHandle") -> None: ...


@dataclass(frozen=True)
class SandboxHandle:
    sandbox_id: str
    specification: SandboxSpecification
    filesystem: SandboxFilesystem


_SENSITIVE_ENVIRONMENT = re.compile(
    r"(?:TOKEN|SECRET|PASSWORD|CREDENTIAL|API[_-]?KEY|PRIVATE[_-]?KEY|AWS_|AZURE_|GCP_|GOOGLE_|OPENAI_|GITHUB_)",
    re.IGNORECASE,
)
_ALLOWED_TEST_FLAGS = {
    "-q",
    "-v",
    "-x",
    "--disable-warnings",
    "--tb=short",
    "--maxfail=1",
}
_SHELL_MARKERS = frozenset(";&|<>`\n\r")


class LocalRestrictedBackend:
    """Workspace/path/typed-process enforcement without external services."""

    def create(self, specification: SandboxSpecification) -> SandboxHandle:
        if specification.requires_os_network_isolation:
            raise SandboxProvisioningError(
                "OS network isolation was requested but LocalRestrictedBackend cannot provide it",
                code="OS_NETWORK_ISOLATION_REQUIRED",
            )
        if specification.network_mode is not NetworkMode.DENY:
            raise SandboxProvisioningError(
                "LocalRestrictedBackend only provisions network-deny profiles",
                code="NETWORK_ISOLATION_UNAVAILABLE",
            )
        return SandboxHandle(
            sandbox_id=f"sbx-{uuid.uuid4().hex[:16]}",
            specification=specification,
            filesystem=SandboxFilesystem(specification),
        )

    def destroy(self, sandbox: SandboxHandle) -> None:
        # The first backend has no external resource. Keeping this lifecycle
        # method explicit makes OS/container backends replaceable later.
        del sandbox

    def execute(
        self,
        sandbox: SandboxHandle,
        request: FilesystemRequest | ProcessRequest,
    ) -> BackendExecution:
        if isinstance(request, FilesystemRequest):
            return self._execute_filesystem(sandbox, request)
        if isinstance(request, ProcessRequest):
            return self._execute_process(sandbox, request)
        raise SandboxViolation("unsupported sandbox request type", code="REQUEST_TYPE_UNSUPPORTED")

    @staticmethod
    def _require_capability(specification: SandboxSpecification, capability: Capability) -> None:
        if capability not in specification.allowed_capabilities:
            raise SandboxViolation(
                f"capability is not in the effective permit: {capability.value}",
                code="CAPABILITY_NOT_ALLOWED",
            )

    def _execute_filesystem(
        self,
        sandbox: SandboxHandle,
        request: FilesystemRequest,
    ) -> BackendExecution:
        specification = sandbox.specification
        capability = (
            Capability.FILESYSTEM_READ
            if request.operation is FilesystemOperation.READ
            else Capability.FILESYSTEM_WRITE
        )
        self._require_capability(specification, capability)
        if request.operation is FilesystemOperation.READ:
            target = sandbox.filesystem.resolve_read(request.relative_path)
            data = target.read_bytes()
            if len(data) > specification.max_output_bytes:
                raise SandboxViolation("file read exceeds output limit", code="OUTPUT_LIMIT")
            try:
                value: str | bytes = data.decode(request.encoding)
            except UnicodeDecodeError:
                value = data
            return BackendExecution(
                status=SandboxStatus.SUCCESS,
                operation="filesystem_read",
                value=value,
            )

        content = request.content
        if isinstance(content, str):
            size = len(content.encode(request.encoding))
        elif isinstance(content, bytes):
            size = len(content)
        else:
            raise SandboxViolation("file content must be text or bytes", code="CONTENT_INVALID")
        if size > specification.max_write_bytes:
            raise SandboxViolation("file write exceeds write limit", code="WRITE_LIMIT")
        target = sandbox.filesystem.write_file(
            request.relative_path,
            content,
            encoding=request.encoding,
        )
        return BackendExecution(
            status=SandboxStatus.SUCCESS,
            operation="filesystem_write",
            value={"path": sandbox.filesystem.relative_path(target), "bytes": size},
        )

    @staticmethod
    def _executable_name(value: str) -> str:
        name = Path(value).name.casefold()
        for suffix in (".exe", ".cmd", ".bat"):
            if name.endswith(suffix):
                name = name[: -len(suffix)]
        if re.fullmatch(r"python(?:\d+(?:\.\d+)*)?", name):
            return "python"
        return name

    def _resolve_executable(self, requested: str, specification: SandboxSpecification) -> str:
        resolved = str(Path(requested).expanduser().resolve()) if Path(requested).is_absolute() else (shutil.which(requested) or requested)
        requested_name = self._executable_name(resolved)
        allowed = tuple(specification.allowed_executables)
        for entry in allowed:
            entry_path = Path(entry)
            if entry_path.is_absolute() and Path(resolved).resolve() == entry_path.expanduser().resolve():
                return resolved
            if not entry_path.is_absolute() and requested_name == self._executable_name(entry):
                return resolved
        raise SandboxViolation(
            f"executable is not allowlisted: {requested_name}",
            code="EXECUTABLE_NOT_ALLOWED",
        )

    @staticmethod
    def _validate_text_argument(argument: str) -> None:
        if any(marker in argument for marker in _SHELL_MARKERS):
            raise SandboxViolation("shell metacharacters are not accepted", code="SHELL_ARGUMENT_DENIED")

    def _test_arguments(self, sandbox: SandboxHandle, arguments: tuple[str, ...]) -> tuple[str, ...]:
        validated: list[str] = []
        for argument in arguments:
            self._validate_text_argument(argument)
            if argument.startswith("-"):
                if argument not in _ALLOWED_TEST_FLAGS:
                    raise SandboxViolation(
                        f"pytest flag is not allowlisted: {argument}",
                        code="TEST_ARGUMENT_DENIED",
                    )
                validated.append(argument)
                continue
            target = sandbox.filesystem.resolve_read(argument)
            validated.append(sandbox.filesystem.relative_path(target))
        return tuple(validated)

    def _git_arguments(self, sandbox: SandboxHandle, request: ProcessRequest) -> tuple[str, ...]:
        if request.git_operation is None:
            raise SandboxViolation("git requests require a typed operation", code="GIT_OPERATION_REQUIRED")
        operation = request.git_operation if isinstance(request.git_operation, GitOperation) else GitOperation(request.git_operation)
        if operation.value not in sandbox.specification.allowed_git_operations:
            raise SandboxViolation(
                f"git operation is not allowlisted: {operation.value}",
                code="GIT_OPERATION_DENIED",
            )
        if request.arguments:
            raise SandboxViolation("git arguments must be constructed by BAGO", code="GIT_ARGUMENTS_DENIED")
        path_argument: list[str] = []
        if request.git_path:
            path = sandbox.filesystem.resolve_read(request.git_path)
            path_argument = ["--", sandbox.filesystem.relative_path(path)]
        if operation is GitOperation.STATUS:
            return ("status", "--short", *path_argument)
        if operation is GitOperation.DIFF:
            return ("diff", "--no-ext-diff", *path_argument)
        if operation is GitOperation.LOG:
            return ("log", "-n", "20", "--oneline", "--decorate", *path_argument)
        return ("show", "--stat", "--oneline", *path_argument)

    def _build_command(
        self,
        sandbox: SandboxHandle,
        request: ProcessRequest,
    ) -> tuple[str, tuple[str, ...], str]:
        tool = request.tool.casefold()
        if request.capability is Capability.RUN_TESTS:
            self._require_capability(sandbox.specification, Capability.RUN_TESTS)
            if tool not in {"pytest", "python"}:
                raise SandboxViolation("RUN_TESTS only accepts the typed pytest tool", code="TOOL_NOT_ALLOWED")
            executable = self._resolve_executable(sys.executable, sandbox.specification)
            return executable, ("-m", "pytest", *self._test_arguments(sandbox, request.arguments)), "run_tests"
        if request.capability is Capability.GIT_READ:
            self._require_capability(sandbox.specification, Capability.GIT_READ)
            if tool != "git":
                raise SandboxViolation("GIT_READ only accepts the git tool", code="TOOL_NOT_ALLOWED")
            executable = self._resolve_executable(shutil.which("git") or "git", sandbox.specification)
            return executable, self._git_arguments(sandbox, request), "git_read"
        raise SandboxViolation(
            f"process capability is not executable: {request.capability.value}",
            code="PROCESS_CAPABILITY_DENIED",
        )

    def _environment(self, sandbox: SandboxHandle, request: ProcessRequest) -> dict[str, str]:
        allowed = sandbox.specification.environment_allowlist
        result: dict[str, str] = {}
        for key in allowed:
            if key in os.environ and not _SENSITIVE_ENVIRONMENT.search(key):
                result[key] = os.environ[key]
        for key, value in request.environment.items():
            normalized = str(key).upper()
            if _SENSITIVE_ENVIRONMENT.search(normalized):
                raise SandboxViolation("credential-like environment variables are denied", code="CREDENTIAL_ENV_DENIED")
            if normalized not in allowed:
                raise SandboxViolation(
                    f"environment variable is not allowlisted: {key}",
                    code="ENV_NOT_ALLOWLISTED",
                )
            if "\x00" in str(value):
                raise SandboxViolation("environment values cannot contain NUL", code="ENV_VALUE_INVALID")
            result[normalized] = str(value)
        result["PYTHONDONTWRITEBYTECODE"] = "1"
        return result

    def _execute_process(self, sandbox: SandboxHandle, request: ProcessRequest) -> BackendExecution:
        specification = sandbox.specification
        executable, arguments, operation = self._build_command(sandbox, request)
        cwd = sandbox.filesystem.resolve_read(request.cwd)
        if not cwd.is_dir():
            raise SandboxViolation("process cwd must be a directory", code="CWD_INVALID")
        timeout = specification.timeout_seconds if request.timeout_seconds is None else request.timeout_seconds
        if timeout <= 0 or timeout > specification.timeout_seconds:
            raise SandboxViolation("request timeout exceeds the permit", code="TIMEOUT_EXCEEDS_PERMIT")
        argv = (executable, *arguments)
        started = time.monotonic()
        try:
            completed = subprocess.run(
                list(argv),
                cwd=str(cwd),
                env=self._environment(sandbox, request),
                shell=False,
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as error:
            stdout = error.stdout if isinstance(error.stdout, str) else ""
            stderr = error.stderr if isinstance(error.stderr, str) else ""
            return BackendExecution(
                status=SandboxStatus.TIMEOUT,
                operation=operation,
                stdout=stdout,
                stderr=stderr,
                argv=argv,
                timed_out=True,
                error_code="TIMEOUT",
                error_message=f"process exceeded {timeout:.3f}s",
            )
        except OSError as error:
            return BackendExecution(
                status=SandboxStatus.FAILURE,
                operation=operation,
                argv=argv,
                error_code="PROCESS_START_FAILED",
                error_message=str(error),
            )

        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        output_bytes = len(stdout.encode("utf-8", errors="replace")) + len(stderr.encode("utf-8", errors="replace"))
        if output_bytes > specification.max_output_bytes:
            return BackendExecution(
                status=SandboxStatus.FAILURE,
                operation=operation,
                stdout=stdout[: specification.max_output_bytes],
                stderr=stderr[: specification.max_output_bytes],
                argv=argv,
                exit_code=completed.returncode,
                error_code="OUTPUT_LIMIT",
                error_message="process output exceeded the sandbox limit",
            )
        return BackendExecution(
            status=SandboxStatus.SUCCESS if completed.returncode == 0 else SandboxStatus.FAILURE,
            operation=operation,
            stdout=stdout,
            stderr=stderr,
            argv=argv,
            exit_code=completed.returncode,
            error_code=None if completed.returncode == 0 else "PROCESS_EXIT_NONZERO",
            error_message=None if completed.returncode == 0 else f"process exited with code {completed.returncode}",
        )
