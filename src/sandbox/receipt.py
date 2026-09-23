"""Receipts for every local sandbox attempt, including denials."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SandboxStatus(str, Enum):
    SUCCESS = "SUCCESS"
    DENIED = "DENIED"
    FAILURE = "FAILURE"
    TIMEOUT = "TIMEOUT"


def digest_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


@dataclass(frozen=True)
class BackendExecution:
    status: SandboxStatus
    operation: str
    value: Any = None
    stdout: str = ""
    stderr: str = ""
    argv: tuple[str, ...] = ()
    exit_code: int | None = None
    timed_out: bool = False
    error_code: str | None = None
    error_message: str | None = None


@dataclass(frozen=True)
class SandboxReceipt:
    receipt_id: str
    request_id: str
    permit_id: str
    sandbox_id: str
    capability: str
    profile: str
    operation: str
    status: SandboxStatus
    filesystem_mode: str
    network_mode: str
    duration_ms: int
    argv: tuple[str, ...] = ()
    exit_code: int | None = None
    timed_out: bool = False
    stdout_sha256: str | None = None
    stderr_sha256: str | None = None
    stdout_bytes: int = 0
    stderr_bytes: int = 0
    error_code: str | None = None
    error_message: str | None = None
    evidence_refs: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "request_id": self.request_id,
            "permit_id": self.permit_id,
            "sandbox_id": self.sandbox_id,
            "capability": self.capability,
            "profile": self.profile,
            "operation": self.operation,
            "status": self.status.value,
            "filesystem_mode": self.filesystem_mode,
            "network_mode": self.network_mode,
            "duration_ms": self.duration_ms,
            "argv": list(self.argv),
            "exit_code": self.exit_code,
            "timed_out": self.timed_out,
            "stdout_sha256": self.stdout_sha256,
            "stderr_sha256": self.stderr_sha256,
            "stdout_bytes": self.stdout_bytes,
            "stderr_bytes": self.stderr_bytes,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "evidence_refs": list(self.evidence_refs),
        }


@dataclass(frozen=True)
class SandboxExecutionResult:
    receipt: SandboxReceipt
    value: Any = None
    stdout: str = ""
    stderr: str = ""

    @property
    def ok(self) -> bool:
        return self.receipt.status is SandboxStatus.SUCCESS

    def to_dict(self) -> dict[str, Any]:
        return {
            "receipt": self.receipt.to_dict(),
            "value": self.value,
            "stdout": self.stdout,
            "stderr": self.stderr,
        }

