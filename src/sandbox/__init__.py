"""Zero-cost governed sandbox primitives for the BAGO Agentic Data Lab."""

from .backend import LocalRestrictedBackend, SandboxBackend, SandboxHandle
from .exceptions import (
    AuthorizationDenied,
    PathEscapeViolation,
    SandboxError,
    SandboxProvisioningError,
    SandboxViolation,
)
from .filesystem import FilesystemOperation, FilesystemRequest, SandboxFilesystem
from .manager import SandboxManager, SandboxPolicy, SandboxRequest
from .process import GitOperation, ProcessRequest
from .receipt import SandboxExecutionResult, SandboxReceipt, SandboxStatus
from .specification import (
    Capability,
    FilesystemMode,
    NetworkMode,
    SandboxProfile,
    SandboxSpecification,
)

__all__ = [
    "AuthorizationDenied",
    "Capability",
    "FilesystemMode",
    "FilesystemOperation",
    "FilesystemRequest",
    "GitOperation",
    "LocalRestrictedBackend",
    "NetworkMode",
    "PathEscapeViolation",
    "ProcessRequest",
    "SandboxBackend",
    "SandboxError",
    "SandboxExecutionResult",
    "SandboxFilesystem",
    "SandboxHandle",
    "SandboxManager",
    "SandboxPolicy",
    "SandboxProfile",
    "SandboxProvisioningError",
    "SandboxReceipt",
    "SandboxRequest",
    "SandboxSpecification",
    "SandboxStatus",
    "SandboxViolation",
]

