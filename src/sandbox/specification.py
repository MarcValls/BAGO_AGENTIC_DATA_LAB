"""Immutable technical limits derived from a BAGO permit.

The specification is deliberately narrower than authorization.  A profile can
remove capabilities from a permit, but it can never add them.  The local
backend does not claim OS-level network isolation; requests that require it
fail closed during provisioning.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Iterable

from .exceptions import SandboxViolation


class Capability(str, Enum):
    FILESYSTEM_READ = "filesystem_read"
    FILESYSTEM_WRITE = "filesystem_write"
    RUN_TESTS = "run_tests"
    GIT_READ = "git_read"


class SandboxProfile(str, Enum):
    READ_ONLY_AGENT = "read_only_agent"
    REPOSITORY_WORKER = "repository_worker"
    TEST_RUNNER = "test_runner"
    NETWORK_RESEARCHER = "network_researcher"


class FilesystemMode(str, Enum):
    READ_ONLY = "read_only"
    WORKSPACE_WRITE = "workspace_write"


class NetworkMode(str, Enum):
    DENY = "deny"
    ALLOWLIST = "allowlist"


DEFAULT_ENVIRONMENT_ALLOWLIST = frozenset(
    {
        "APPDATA",
        "LANG",
        "LC_ALL",
        "LOCALAPPDATA",
        "PATH",
        "PATHEXT",
        "PYTHONIOENCODING",
        "PYTHONUSERBASE",
        "PYTHONUTF8",
        "SYSTEMROOT",
        "TEMP",
        "TMP",
        "USERPROFILE",
        "WINDIR",
    }
)


PROFILE_CAPABILITIES: dict[SandboxProfile, frozenset[Capability]] = {
    SandboxProfile.READ_ONLY_AGENT: frozenset({Capability.FILESYSTEM_READ}),
    SandboxProfile.REPOSITORY_WORKER: frozenset(
        {
            Capability.FILESYSTEM_READ,
            Capability.FILESYSTEM_WRITE,
            Capability.RUN_TESTS,
            Capability.GIT_READ,
        }
    ),
    SandboxProfile.TEST_RUNNER: frozenset(
        {
            Capability.FILESYSTEM_READ,
            Capability.FILESYSTEM_WRITE,
            Capability.RUN_TESTS,
        }
    ),
    SandboxProfile.NETWORK_RESEARCHER: frozenset({Capability.FILESYSTEM_READ}),
}


PROFILE_EXECUTABLES: dict[SandboxProfile, frozenset[str]] = {
    SandboxProfile.READ_ONLY_AGENT: frozenset(),
    SandboxProfile.REPOSITORY_WORKER: frozenset({"python", "git"}),
    SandboxProfile.TEST_RUNNER: frozenset({"python"}),
    SandboxProfile.NETWORK_RESEARCHER: frozenset(),
}


def _inside(root: Path, candidate: Path) -> bool:
    try:
        common = os.path.commonpath([str(root), str(candidate)])
    except ValueError:
        return False
    return os.path.normcase(common) == os.path.normcase(str(root))


def _capabilities(values: Iterable[Capability | str]) -> frozenset[Capability]:
    return frozenset(value if isinstance(value, Capability) else Capability(value) for value in values)


@dataclass(frozen=True)
class SandboxSpecification:
    """Effective limits for one sandbox handle."""

    workspace_root: Path
    profile: SandboxProfile
    filesystem_mode: FilesystemMode
    writable_roots: tuple[Path, ...] = ()
    allowed_capabilities: frozenset[Capability] = field(default_factory=frozenset)
    allowed_executables: frozenset[str] = field(default_factory=frozenset)
    allowed_git_operations: frozenset[str] = field(default_factory=frozenset)
    timeout_seconds: float = 30.0
    max_output_bytes: int = 1_000_000
    max_write_bytes: int = 1_000_000
    environment_allowlist: frozenset[str] = DEFAULT_ENVIRONMENT_ALLOWLIST
    network_mode: NetworkMode = NetworkMode.DENY
    allowed_network_hosts: frozenset[str] = field(default_factory=frozenset)
    requires_os_network_isolation: bool = False

    def __post_init__(self) -> None:
        root = Path(self.workspace_root).expanduser().resolve()
        if not root.exists() or not root.is_dir():
            raise SandboxViolation("workspace_root must be an existing directory", code="WORKSPACE_INVALID")
        object.__setattr__(self, "workspace_root", root)

        profile = self.profile if isinstance(self.profile, SandboxProfile) else SandboxProfile(self.profile)
        object.__setattr__(self, "profile", profile)
        filesystem_mode = (
            self.filesystem_mode
            if isinstance(self.filesystem_mode, FilesystemMode)
            else FilesystemMode(self.filesystem_mode)
        )
        object.__setattr__(self, "filesystem_mode", filesystem_mode)
        network_mode = self.network_mode if isinstance(self.network_mode, NetworkMode) else NetworkMode(self.network_mode)
        object.__setattr__(self, "network_mode", network_mode)

        writable = tuple(Path(path).expanduser().resolve() for path in self.writable_roots)
        if any(not _inside(root, path) for path in writable):
            raise SandboxViolation("writable root is outside workspace", code="WRITE_SCOPE_ESCAPE")
        if filesystem_mode is FilesystemMode.READ_ONLY and writable:
            raise SandboxViolation("read-only filesystem cannot have writable roots", code="WRITE_SCOPE_INVALID")
        object.__setattr__(self, "writable_roots", writable)

        capabilities = _capabilities(self.allowed_capabilities)
        object.__setattr__(self, "allowed_capabilities", capabilities)
        object.__setattr__(
            self,
            "allowed_executables",
            frozenset(str(value).strip() for value in self.allowed_executables if str(value).strip()),
        )
        object.__setattr__(
            self,
            "allowed_git_operations",
            frozenset(str(value).strip().casefold() for value in self.allowed_git_operations if str(value).strip()),
        )
        object.__setattr__(self, "environment_allowlist", frozenset(str(value).upper() for value in self.environment_allowlist))
        object.__setattr__(self, "allowed_network_hosts", frozenset(str(value).casefold() for value in self.allowed_network_hosts))

        if self.timeout_seconds <= 0 or self.timeout_seconds > 3600:
            raise SandboxViolation("timeout_seconds is outside the safe range", code="TIMEOUT_INVALID")
        if self.max_output_bytes <= 0 or self.max_write_bytes <= 0:
            raise SandboxViolation("sandbox byte limits must be positive", code="LIMIT_INVALID")
        if network_mode is NetworkMode.DENY and self.allowed_network_hosts:
            raise SandboxViolation("network hosts require an allowlist network mode", code="NETWORK_POLICY_INVALID")

    @classmethod
    def from_profile(
        cls,
        workspace_root: Path | str,
        profile: SandboxProfile,
        *,
        allowed_capabilities: Iterable[Capability | str] | None = None,
        writable_roots: Iterable[Path | str] = (),
        timeout_seconds: float = 30.0,
        allowed_git_operations: Iterable[str] = ("status", "diff", "log", "show"),
        network_mode: NetworkMode = NetworkMode.DENY,
        requires_os_network_isolation: bool = False,
    ) -> "SandboxSpecification":
        profile = profile if isinstance(profile, SandboxProfile) else SandboxProfile(profile)
        profile_caps = PROFILE_CAPABILITIES[profile]
        requested_caps = profile_caps if allowed_capabilities is None else _capabilities(allowed_capabilities)
        effective_caps = frozenset(requested_caps) & profile_caps
        writable = tuple(Path(path) for path in writable_roots)
        if profile is not SandboxProfile.READ_ONLY_AGENT and not writable and Capability.FILESYSTEM_WRITE in effective_caps:
            writable = (Path(workspace_root),)
        mode = FilesystemMode.WORKSPACE_WRITE if writable else FilesystemMode.READ_ONLY
        return cls(
            workspace_root=Path(workspace_root),
            profile=profile,
            filesystem_mode=mode,
            writable_roots=writable,
            allowed_capabilities=effective_caps,
            allowed_executables=PROFILE_EXECUTABLES[profile],
            allowed_git_operations=frozenset(allowed_git_operations),
            timeout_seconds=timeout_seconds,
            network_mode=network_mode,
            requires_os_network_isolation=requires_os_network_isolation,
        )
