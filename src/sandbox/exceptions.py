"""Errors emitted by the local governed sandbox layer."""

from __future__ import annotations


class SandboxError(RuntimeError):
    """Base error with a stable code suitable for receipts."""

    code = "SANDBOX_ERROR"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code:
            self.code = code


class AuthorizationDenied(SandboxError):
    """The permit or the derived capability scope does not allow the request."""

    code = "AUTHORIZATION_DENIED"


class SandboxViolation(SandboxError):
    """The request violates a filesystem, process or credential boundary."""

    code = "SANDBOX_VIOLATION"


class PathEscapeViolation(SandboxViolation):
    """A requested path resolves outside the effective workspace."""

    code = "PATH_ESCAPE"


class SandboxProvisioningError(SandboxError):
    """The requested isolation could not be established safely."""

    code = "SANDBOX_PROVISIONING_FAILED"

