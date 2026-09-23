"""Structured process requests; arbitrary shell strings are not supported."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping

from .specification import Capability


class GitOperation(str, Enum):
    STATUS = "status"
    DIFF = "diff"
    LOG = "log"
    SHOW = "show"


@dataclass(frozen=True)
class ProcessRequest:
    """Typed process request consumed by ``LocalRestrictedBackend``."""

    request_id: str
    capability: Capability
    tool: str
    arguments: tuple[str, ...] = ()
    cwd: str = "."
    timeout_seconds: float | None = None
    environment: Mapping[str, str] = field(default_factory=dict)
    git_operation: GitOperation | None = None
    git_path: str | None = None

    def __post_init__(self) -> None:
        if not self.request_id.strip():
            raise ValueError("request_id is required")
        capability = self.capability if isinstance(self.capability, Capability) else Capability(self.capability)
        object.__setattr__(self, "capability", capability)
        if not self.tool.strip() or "\x00" in self.tool:
            raise ValueError("tool is required")
        arguments = tuple(self.arguments)
        if any(not isinstance(argument, str) or "\x00" in argument for argument in arguments):
            raise ValueError("arguments must be NUL-free strings")
        object.__setattr__(self, "arguments", arguments)
        object.__setattr__(self, "environment", dict(self.environment))
        if self.git_operation is not None:
            operation = self.git_operation if isinstance(self.git_operation, GitOperation) else GitOperation(self.git_operation)
            object.__setattr__(self, "git_operation", operation)

