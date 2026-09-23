"""Workspace-scoped filesystem operations for the local backend."""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from .exceptions import PathEscapeViolation, SandboxViolation
from .specification import SandboxSpecification


class FilesystemOperation(str, Enum):
    READ = "read"
    WRITE = "write"


@dataclass(frozen=True)
class FilesystemRequest:
    """Typed file request; callers never provide a shell command."""

    request_id: str
    operation: FilesystemOperation
    relative_path: str
    content: str | bytes | None = None
    encoding: str = "utf-8"

    def __post_init__(self) -> None:
        if not self.request_id.strip():
            raise ValueError("request_id is required")
        operation = self.operation if isinstance(self.operation, FilesystemOperation) else FilesystemOperation(self.operation)
        object.__setattr__(self, "operation", operation)
        if not isinstance(self.relative_path, str) or "\x00" in self.relative_path:
            raise ValueError("relative_path must be a valid string")
        if self.operation is FilesystemOperation.WRITE and self.content is None:
            raise ValueError("write requests require content")
        if self.operation is FilesystemOperation.READ and self.content is not None:
            raise ValueError("read requests cannot contain content")


def _inside(root: Path, candidate: Path) -> bool:
    try:
        common = os.path.commonpath([str(root), str(candidate)])
    except ValueError:
        return False
    return os.path.normcase(common) == os.path.normcase(str(root))


@dataclass(frozen=True)
class SandboxFilesystem:
    """Filesystem view rooted in one resolved workspace."""

    specification: SandboxSpecification

    @property
    def root(self) -> Path:
        return self.specification.workspace_root

    def _resolve_relative(self, requested: str | Path) -> Path:
        value = str(requested)
        candidate = Path(value)
        if candidate.is_absolute() or candidate.drive:
            raise PathEscapeViolation("absolute paths are not accepted by the sandbox")
        resolved = (self.root / candidate).resolve(strict=False)
        if not _inside(self.root, resolved):
            raise PathEscapeViolation(f"path resolves outside workspace: {value}")
        return resolved

    def resolve_read(self, requested: str | Path) -> Path:
        target = self._resolve_relative(requested)
        if not target.exists():
            raise FileNotFoundError(target)
        return target

    def resolve_write(self, requested: str | Path) -> Path:
        target = self._resolve_relative(requested)
        if not any(_inside(root, target) for root in self.specification.writable_roots):
            raise SandboxViolation("write is outside the effective writable roots", code="WRITE_DENIED")
        if target.exists() and target.is_dir():
            raise SandboxViolation("cannot write a directory", code="WRITE_TARGET_INVALID")
        if not target.parent.exists() or not target.parent.is_dir():
            raise SandboxViolation("write parent directory must already exist", code="WRITE_PARENT_INVALID")
        return target

    def relative_path(self, target: Path) -> str:
        resolved = target.resolve(strict=False)
        if not _inside(self.root, resolved):
            raise PathEscapeViolation("path is outside workspace")
        return resolved.relative_to(self.root).as_posix() or "."

    def read_file(self, requested: str | Path, *, encoding: str = "utf-8") -> str | bytes:
        target = self.resolve_read(requested)
        data = target.read_bytes()
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            return data

    def write_file(self, requested: str | Path, content: str | bytes, *, encoding: str = "utf-8") -> Path:
        target = self.resolve_write(requested)
        if isinstance(content, bytes):
            target.write_bytes(content)
        elif isinstance(content, str):
            target.write_text(content, encoding=encoding)
        else:
            raise SandboxViolation("file content must be text or bytes", code="CONTENT_INVALID")
        return target

