"""Canonical repository/workspace binding for governed agent actions.

The binding is an attestation of *where* an agent is operating, not a permit
to perform a material effect.  It keeps repository identity, the current Git
revision and the BAGO context revision together, and it rejects paths outside
the bound repository root.

All Git inspection in this module is read-only.  Authorization and execution
remain separate concerns owned by the existing permit/receipt boundaries.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import urlsplit


_COMMIT_PATTERN = re.compile(r"^[0-9a-f]{7,64}$", re.IGNORECASE)


class WorkspaceBindingError(ValueError):
    """Raised when a repository cannot be bound safely."""


def _digest(value: str, *, length: int = 16) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def _clean_text(name: str, value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise WorkspaceBindingError(f"{name} is required")
    normalized = value.strip()
    if "\n" in normalized or "\r" in normalized:
        raise WorkspaceBindingError(f"{name} must be a single line")
    return normalized


def _strip_git_suffix(path: str) -> str:
    normalized = path.strip().strip("/")
    return normalized[:-4] if normalized.casefold().endswith(".git") else normalized


def normalize_repository_identity(remote: str, root: Optional[Path] = None) -> str:
    """Return a credential-free, stable identity for a Git remote.

    HTTPS userinfo, SSH usernames and query strings are never included in the
    result.  Repositories without a remote receive a local, root-derived
    identity so a binding is still possible in an offline checkout.
    """

    value = (remote or "").strip()
    if not value:
        if root is None:
            raise WorkspaceBindingError("remote or root is required")
        return f"local:{_digest(str(root.expanduser().resolve()))}"

    if value.startswith("git@") and ":" in value:
        host, path = value[4:].split(":", 1)
        return f"{host.casefold()}/{_strip_git_suffix(path)}"

    parsed = urlsplit(value)
    if parsed.hostname:
        path = _strip_git_suffix(parsed.path)
        return f"{parsed.hostname.casefold()}/{path}" if path else parsed.hostname.casefold()

    # A plain host/path identity is useful in tests and contains no URL userinfo.
    return _strip_git_suffix(value)


def _git(root: Path, *arguments: str, required: bool = True) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *arguments],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except OSError as error:
        raise WorkspaceBindingError("git is required to bind a workspace") from error
    output = result.stdout.strip()
    if result.returncode != 0:
        if required:
            detail = result.stderr.strip() or "unknown git error"
            raise WorkspaceBindingError(f"git {' '.join(arguments)} failed: {detail}")
        return ""
    return output


def _fingerprint(
    *,
    workspace_id: str,
    repository_identity: str,
    branch: str,
    commit_sha: str,
    context_revision: str,
) -> str:
    payload = {
        "branch": branch,
        "commit_sha": commit_sha,
        "context_revision": context_revision,
        "repository_identity": repository_identity,
        "workspace_id": workspace_id,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class WorkspaceBinding:
    """Immutable identity and scope boundary for one governed workspace."""

    workspace_id: str
    repository_root: Path
    repository_identity: str
    branch: str
    commit_sha: str
    context_revision: str
    fingerprint: str

    def __post_init__(self) -> None:
        root = Path(self.repository_root).expanduser().resolve()
        if not root.exists() or not root.is_dir():
            raise WorkspaceBindingError("repository_root must be an existing directory")
        object.__setattr__(self, "repository_root", root)

        workspace_id = _clean_text("workspace_id", self.workspace_id)
        repository_identity = _clean_text("repository_identity", self.repository_identity)
        branch = _clean_text("branch", self.branch)
        context_revision = _clean_text("context_revision", self.context_revision)
        fingerprint = _clean_text("fingerprint", self.fingerprint)
        if not _COMMIT_PATTERN.fullmatch(self.commit_sha):
            raise WorkspaceBindingError("commit_sha must be a hexadecimal Git revision")
        if len(fingerprint) != 64 or not re.fullmatch(r"[0-9a-f]{64}", fingerprint, re.IGNORECASE):
            raise WorkspaceBindingError("fingerprint must be a SHA-256 hex digest")

        object.__setattr__(self, "workspace_id", workspace_id)
        object.__setattr__(self, "repository_identity", repository_identity)
        object.__setattr__(self, "branch", branch)
        object.__setattr__(self, "context_revision", context_revision)
        object.__setattr__(self, "commit_sha", self.commit_sha.casefold())
        object.__setattr__(self, "fingerprint", fingerprint.casefold())

        expected = _fingerprint(
            workspace_id=workspace_id,
            repository_identity=repository_identity,
            branch=branch,
            commit_sha=self.commit_sha.casefold(),
            context_revision=context_revision,
        )
        if self.fingerprint != expected:
            raise WorkspaceBindingError("fingerprint does not match binding claims")

    @classmethod
    def from_git(
        cls,
        root: Path | str,
        *,
        context_revision: str,
        expected_repository: Optional[str] = None,
        workspace_id: Optional[str] = None,
        remote_name: str = "origin",
    ) -> "WorkspaceBinding":
        """Create a binding from read-only Git metadata."""

        requested_root = Path(root).expanduser()
        if not requested_root.exists() or not requested_root.is_dir():
            raise WorkspaceBindingError("workspace root must be an existing directory")
        git_root = Path(_git(requested_root, "rev-parse", "--show-toplevel")).resolve()
        context_revision = _clean_text("context_revision", context_revision)
        remote = _git(git_root, "remote", "get-url", remote_name, required=False)
        repository_identity = normalize_repository_identity(remote, git_root)
        if expected_repository:
            expected_identity = normalize_repository_identity(expected_repository, git_root)
            if repository_identity != expected_identity:
                raise WorkspaceBindingError(
                    "workspace repository does not match expected_repository"
                )

        branch = _git(git_root, "symbolic-ref", "--short", "-q", "HEAD", required=False)
        commit_sha = _git(git_root, "rev-parse", "HEAD").casefold()
        resolved_workspace_id = workspace_id or f"workspace_{_digest(str(git_root))}"
        fingerprint = _fingerprint(
            workspace_id=resolved_workspace_id,
            repository_identity=repository_identity,
            branch=branch or "DETACHED",
            commit_sha=commit_sha,
            context_revision=context_revision,
        )
        return cls(
            workspace_id=resolved_workspace_id,
            repository_root=git_root,
            repository_identity=repository_identity,
            branch=branch or "DETACHED",
            commit_sha=commit_sha,
            context_revision=context_revision,
            fingerprint=fingerprint,
        )

    def is_in_scope(self, path: Path | str) -> bool:
        """Return whether a path resolves inside this repository root."""

        try:
            candidate = Path(path).expanduser().resolve(strict=False)
            common = os.path.commonpath([str(self.repository_root), str(candidate)])
            return os.path.normcase(common) == os.path.normcase(str(self.repository_root))
        except (OSError, ValueError):
            return False

    def assert_in_scope(self, path: Path | str) -> Path:
        """Return a canonical in-scope path or reject a traversal."""

        candidate = Path(path).expanduser().resolve(strict=False)
        if not self.is_in_scope(candidate):
            raise WorkspaceBindingError(
                f"path is outside bound workspace: {candidate}"
            )
        return candidate

    def matches_current(self) -> bool:
        """Check that the Git identity has not drifted since binding."""

        try:
            current = type(self).from_git(
                self.repository_root,
                context_revision=self.context_revision,
                workspace_id=self.workspace_id,
            )
        except WorkspaceBindingError:
            return False
        return current == self

    def to_dict(self) -> dict[str, str]:
        """Serialize claims for a receipt without exposing remote credentials."""

        return {
            "workspace_id": self.workspace_id,
            "repository_root": str(self.repository_root),
            "repository_identity": self.repository_identity,
            "branch": self.branch,
            "commit_sha": self.commit_sha,
            "context_revision": self.context_revision,
            "fingerprint": self.fingerprint,
        }


def bind_workspace(
    root: Path | str,
    *,
    context_revision: str,
    expected_repository: Optional[str] = None,
) -> WorkspaceBinding:
    """Short, explicit entry point for callers creating a governed binding."""

    return WorkspaceBinding.from_git(
        root,
        context_revision=context_revision,
        expected_repository=expected_repository,
    )


def workspace_binding_is_governed(
    binding: WorkspaceBinding,
    *,
    expected_repository: Optional[str] = None,
    require_current: bool = True,
) -> bool:
    """Validate scope, claims and optional current-repository freshness.

    This function validates context identity only.  A ``True`` result does not
    authorize CREATE/WRITE/DELETE or external API effects.
    """

    if not isinstance(binding, WorkspaceBinding):
        return False
    try:
        if not binding.repository_root.is_dir():
            return False
        if expected_repository:
            expected_identity = normalize_repository_identity(
                expected_repository, binding.repository_root
            )
            if binding.repository_identity != expected_identity:
                return False
        if not binding.is_in_scope(binding.repository_root):
            return False
        return binding.matches_current() if require_current else True
    except (OSError, WorkspaceBindingError):
        return False


__all__ = [
    "WorkspaceBinding",
    "WorkspaceBindingError",
    "bind_workspace",
    "normalize_repository_identity",
    "workspace_binding_is_governed",
]
