"""Persistent, project-bound filesystem permissions with revocable IO leases.

This module stores human-granted directory policy inside the selected project.
It deliberately does not treat a selected root, a previous chat ticket, or a
client supplied project identifier as authorization.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import threading
import time
import errno
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator, Literal, Sequence


class PermissionError(Exception):
    def __init__(self, code: str, message: str, status: int = 403) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


@dataclass(frozen=True)
class ProjectContext:
    project_id: str
    root: Path
    binding: str
    title: str = ""


_POLICY_REL = Path(".bago") / "state" / "PROJECT_PERMISSIONS.json"
_LOCK_REL = Path(".bago") / "state" / ".PROJECT_PERMISSIONS.lock"
_SCHEMA = "project-permissions.v1"
_CONTEXT_READ_PATHS = frozenset({
    ".bago/context/PROJECT_CONTEXT.md",
    ".bago/state/PROJECT_STATE.json",
    ".bago/runtime/ACTIVE_HANDOFF.md",
})
_MAX_DIRS = 50
_MAX_TREE_CHILDREN = 500
_MAX_TREE_ENTRIES = 5000
_MAX_BYTES = 128 * 1024
_RESERVED = re.compile(r"(?i)^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?$")
_BLOCKED = {
    ".bago", ".bago-filesystem", "trash", ".workspace-service", ".git", ".codex", ".ssh", ".aws",
    ".azure", ".env", ".env.local", ".env.production", ".env.development.local",
    "credentials", "credential", "secrets", "secret", "tokens", "token", "private_keys",
}
_SENSITIVE = re.compile(r"(?i)(^|[._-])(credential|secret|password|token|private.?key|api.?key)([._-]|$)")
_DRIVE = re.compile(r"^[A-Za-z]:")
_PROCESS_LOCKS: dict[str, threading.RLock] = {}
_PROCESS_LOCKS_GUARD = threading.Lock()
_THREAD_HELD_LOCKS = threading.local()


def _deny(code: str, status: int | None = None) -> PermissionError:
    messages = {
        "project_context_unavailable": "The active project context is unavailable.",
        "project_context_changed": "The active project changed; refresh the permission state.",
        "project_policy_unavailable": "The project permission policy is unavailable.",
        "project_policy_invalid": "The project permission policy is invalid or belongs to another project.",
        "revision_conflict": "The permission policy changed; reload it before saving.",
        "permission_not_confirmed": "Explicit confirmation is required to change project permissions.",
        "invalid_permission_request": "The permission request is invalid.",
        "project_path_unavailable": "The selected project path is unavailable.",
        "project_path_denied": "The requested path is outside the approved project scope.",
        "permission_denied": "The current project policy does not permit this operation.",
        "project_lock_failed": "The project permission lock could not be acquired safely.",
        "directory_listing_unavailable": "The project directory metadata is unavailable.",
    }
    resolved_status = status if status is not None else (422 if code == "invalid_permission_request" else 403)
    return PermissionError(code, messages.get(code, "The project permission operation failed."), resolved_status)


def _physical_identity(root: Path) -> dict[str, int]:
    info = root.stat()
    if not stat.S_ISDIR(info.st_mode):
        raise _deny("project_path_unavailable", 409)
    return {"device": int(info.st_dev), "file": int(info.st_ino)}


def _inspect_no_links(path: Path, *, allow_missing: bool = True) -> None:
    absolute = Path(os.path.abspath(os.fspath(path)))
    for current in reversed((absolute, *absolute.parents)):
        try:
            info = current.lstat()
        except FileNotFoundError:
            if allow_missing:
                continue
            raise _deny("project_path_unavailable", 409)
        except OSError:
            raise _deny("project_path_unavailable", 409) from None
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
            raise _deny("project_path_denied")


def _context(provider: Callable[[], ProjectContext]) -> tuple[ProjectContext, Path, dict[str, int]]:
    try:
        value = provider()
        if not isinstance(value, ProjectContext) or not value.project_id or not value.binding:
            raise ValueError
        raw = Path(value.root).expanduser()
        _inspect_no_links(raw, allow_missing=False)
        root = raw.resolve(strict=True)
        identity = _physical_identity(root)
        return value, root, identity
    except PermissionError:
        raise
    except Exception:
        raise _deny("project_context_unavailable", 409) from None


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _policy_bytes(policy: dict[str, object]) -> bytes:
    return _canonical_json(policy) + b"\n"


def _revision(policy: dict[str, object]) -> str:
    return hashlib.sha256(_policy_bytes(policy)).hexdigest()


def _safe_relative_directory(root: Path, value: str) -> str:
    if not isinstance(value, str) or not value or value.startswith(("/", "\\")) or _DRIVE.match(value) or "\\" in value or ":" in value or "\x00" in value:
        raise _deny("invalid_permission_request")
    if value == ".":
        return "."
    parts = value.split("/")
    if any(not part or part in {".", ".."} or part != part.rstrip(" .") or any(ord(char) < 32 or char in '<>"|?*' for char in part) for part in parts):
        raise _deny("invalid_permission_request")
    if any(part.casefold() in _BLOCKED or _SENSITIVE.search(part) or _RESERVED.fullmatch(part) for part in parts):
        raise _deny("invalid_permission_request")
    raw = root.joinpath(*parts)
    _inspect_no_links(raw, allow_missing=False)
    try:
        resolved = raw.resolve(strict=True)
    except (OSError, RuntimeError):
        raise _deny("project_path_unavailable", 409) from None
    if resolved != root and root not in resolved.parents or not resolved.is_dir():
        raise _deny("invalid_permission_request")
    return "/".join(parts)


def _normalise_directories(root: Path, values: Sequence[str]) -> list[str]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence) or len(values) > _MAX_DIRS:
        raise _deny("invalid_permission_request")
    result = sorted({_safe_relative_directory(root, item) for item in values}, key=lambda item: (item.casefold(), item))
    return result


@contextmanager
def _project_lock(lock_path: Path) -> Iterator[None]:
    key = os.path.normcase(os.path.abspath(lock_path))
    held = getattr(_THREAD_HELD_LOCKS, "paths", None)
    if held is None:
        held = {}
        _THREAD_HELD_LOCKS.paths = held
    if key in held:
        # The owning thread retains the outer OS lock until its outermost lease
        # exits; nested READ/WRITE checks must not open a second OS handle.
        yield
        return
    _inspect_no_links(lock_path.parent, allow_missing=True)
    try:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        _inspect_no_links(lock_path.parent, allow_missing=False)
        with _PROCESS_LOCKS_GUARD:
            local_lock = _PROCESS_LOCKS.setdefault(key, threading.RLock())
    except PermissionError:
        raise
    except OSError:
        raise _deny("project_lock_failed", 409) from None
    with local_lock:
        try:
            _inspect_no_links(lock_path, allow_missing=True)
            deadline = time.monotonic() + 30
            while True:
                try:
                    descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR | getattr(os, "O_BINARY", 0), 0o600)
                    break
                except OSError as error:
                    retryable = error.errno in {errno.EACCES, errno.EAGAIN, errno.EBUSY} or getattr(error, "winerror", None) in {5, 32, 33}
                    if not retryable or time.monotonic() >= deadline:
                        raise _deny("project_lock_failed", 409) from None
                    time.sleep(0.025)
            info = os.fstat(descriptor)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                os.close(descriptor)
                raise _deny("project_lock_failed")
        except PermissionError:
            raise
        except OSError:
            raise _deny("project_lock_failed", 409) from None

        try:
            if os.name == "nt":
                import msvcrt
                if os.fstat(descriptor).st_size == 0:
                    os.write(descriptor, b"0")
                    os.lseek(descriptor, 0, os.SEEK_SET)
                deadline = time.monotonic() + 30
                while True:
                    try:
                        msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
                        break
                    except OSError:
                        if time.monotonic() >= deadline:
                            raise _deny("project_lock_failed", 409)
                        time.sleep(0.025)
                held[key] = descriptor
                try:
                    yield
                finally:
                    held.pop(key, None)
                    os.lseek(descriptor, 0, os.SEEK_SET)
                    msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(descriptor, fcntl.LOCK_EX)
                held[key] = descriptor
                try:
                    yield
                finally:
                    held.pop(key, None)
                    fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)


class ProjectPermissions:
    def __init__(self, context_provider: Callable[[], ProjectContext], clock: Callable[[], float] | None = None) -> None:
        self._context_provider = context_provider
        self._clock = clock or time.time

    def _current(self) -> tuple[ProjectContext, Path, dict[str, int]]:
        return _context(self._context_provider)

    def _paths(self, root: Path) -> tuple[Path, Path]:
        policy, lock = root / _POLICY_REL, root / _LOCK_REL
        _inspect_no_links(policy.parent, allow_missing=True)
        _inspect_no_links(policy, allow_missing=True)
        _inspect_no_links(lock, allow_missing=True)
        return policy, lock

    def _load(self, context: ProjectContext, root: Path, identity: dict[str, int], policy_path: Path) -> dict[str, object] | None:
        _inspect_no_links(policy_path, allow_missing=True)
        try:
            info = policy_path.lstat()
        except FileNotFoundError:
            return None
        except OSError:
            raise _deny("project_policy_unavailable", 503) from None
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > _MAX_BYTES:
            raise _deny("project_policy_invalid", 503)
        try:
            raw_bytes = policy_path.read_bytes()
            policy = json.loads(raw_bytes.decode("utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            raise _deny("project_policy_invalid", 503) from None
        if not isinstance(policy, dict) or _policy_bytes(policy) != raw_bytes:
            raise _deny("project_policy_invalid", 503)
        expected = {"schema", "project_id", "root", "physical_root", "revision_counter", "read_directories", "write_directories", "updated_at"}
        if not isinstance(policy, dict) or set(policy) != expected or policy.get("schema") != _SCHEMA:
            raise _deny("project_policy_invalid", 503)
        if (policy["project_id"] != context.project_id or policy["root"] != str(root)
                or policy["physical_root"] != identity or type(policy["revision_counter"]) is not int
                or policy["revision_counter"] < 1):
            raise _deny("project_policy_invalid", 503)
        for field in ("read_directories", "write_directories"):
            values = policy[field]
            if not isinstance(values, list) or len(values) > _MAX_DIRS or any(not isinstance(item, str) for item in values):
                raise _deny("project_policy_invalid", 503)
            normalized = _normalise_directories(root, values)
            if normalized != values:
                raise _deny("project_policy_invalid", 503)
        return policy

    def _snapshot(self, context: ProjectContext, root: Path, identity: dict[str, int], policy: dict[str, object] | None) -> dict[str, object]:
        return {
            "schema": _SCHEMA,
            "project_id": context.project_id,
            "root": str(root),
            "title": context.title,
            "binding": context.binding,
            "revision": _revision(policy) if policy is not None else "none",
            "state": "configured" if policy is not None else "unconfigured",
            "read_directories": list(policy["read_directories"]) if policy is not None else [],
            "write_directories": list(policy["write_directories"]) if policy is not None else [],
        }

    def snapshot(self) -> dict[str, object]:
        context, root, identity = self._current()
        policy_path, _ = self._paths(root)
        return self._snapshot(context, root, identity, self._load(context, root, identity, policy_path))

    def browse_directories(self, *, expected_project_id: str, expected_binding: str,
                           expected_revision: str, directory: str) -> dict[str, object]:
        """List one level of real project directories for the human permission editor.

        This is configuration metadata, not a READ lease. It intentionally does
        not create the permission directory, policy, lock, or any other state.
        """
        context, root, identity = self._current()
        if context.project_id != expected_project_id or context.binding != expected_binding:
            raise _deny("project_context_changed", 409)
        if not isinstance(directory, str):
            raise _deny("invalid_permission_request")
        if directory == ".":
            relative = "."
            target = root
        else:
            # Reuse the same canonical path and protected-component checks as
            # policy paths, while reporting forbidden locations as authority
            # denials rather than malformed user input.
            try:
                relative = _safe_relative_directory(root, directory)
            except PermissionError as error:
                if error.code == "invalid_permission_request":
                    raise _deny("project_path_denied") from None
                raise
            target = root.joinpath(*relative.split("/"))

        policy_path, _ = self._paths(root)
        policy = self._load(context, root, identity, policy_path)
        before = self._snapshot(context, root, identity, policy)
        self._assert_expected(context, before, expected_project_id, expected_binding, expected_revision)

        try:
            _inspect_no_links(target, allow_missing=False)
            resolved_target = target.resolve(strict=True)
            if resolved_target != root and root not in resolved_target.parents:
                raise _deny("project_path_denied")
            if not resolved_target.is_dir():
                raise _deny("project_path_denied")
            with os.scandir(resolved_target) as entries:
                candidates = []
                iterator = iter(entries)
                scanned = 0
                scan_truncated = False
                while scanned < _MAX_TREE_ENTRIES:
                    try:
                        entry = next(iterator)
                    except StopIteration:
                        break
                    scanned += 1
                    # Names only. Never follow an entry link/junction, and do
                    # not expose protected directory names in the chooser.
                    name = entry.name
                    if (not name or name.casefold() in _BLOCKED or _SENSITIVE.search(name)
                            or _RESERVED.fullmatch(name)):
                        continue
                    try:
                        child = resolved_target / name
                        _inspect_no_links(child, allow_missing=False)
                        if not entry.is_dir(follow_symlinks=False):
                            continue
                        resolved_child = child.resolve(strict=True)
                        if (resolved_child != root and root not in resolved_child.parents) or not resolved_child.is_dir():
                            raise _deny("project_path_denied")
                    except PermissionError:
                        # Junctions/reparse points are not traversable or
                        # discoverable in the human tree.
                        continue
                    except (OSError, RuntimeError):
                        raise _deny("directory_listing_unavailable", 503) from None
                    candidates.append((name, relative + "/" + name if relative != "." else name))
                    if len(candidates) > _MAX_TREE_CHILDREN:
                        scan_truncated = True
                        break
                else:
                    # We did not inspect one more entry to determine whether
                    # the directory ended exactly at the safety budget.
                    scan_truncated = True
        except PermissionError:
            raise
        except (OSError, RuntimeError):
            raise _deny("directory_listing_unavailable", 503) from None

        candidates.sort(key=lambda item: (item[0].casefold(), item[0]))
        truncated = scan_truncated or len(candidates) > _MAX_TREE_CHILDREN
        children = [{"name": name, "path": path} for name, path in candidates[:_MAX_TREE_CHILDREN]]

        # Bind the response to the same active selection and permission revision
        # after enumeration. A project switch or concurrent save invalidates it.
        current, current_root, current_identity = self._current()
        if (current.project_id != context.project_id or current.binding != context.binding
                or current_root != root or current_identity != identity):
            raise _deny("project_context_changed", 409)
        current_policy_path, _ = self._paths(current_root)
        current_policy = self._load(current, current_root, current_identity, current_policy_path)
        after = self._snapshot(current, current_root, current_identity, current_policy)
        self._assert_expected(current, after, expected_project_id, expected_binding, expected_revision)
        return {"project_id": context.project_id, "root": str(root), "binding": context.binding,
                "revision": before["revision"], "directory": relative,
                "directories": children, "truncated": truncated}

    def _assert_expected(self, context: ProjectContext, snapshot: dict[str, object], project_id: str, binding: str, revision: str) -> None:
        if context.project_id != project_id or context.binding != binding:
            raise _deny("project_context_changed", 409)
        if snapshot["revision"] != revision:
            raise _deny("revision_conflict", 409)

    def _write(self, policy_path: Path, policy: dict[str, object]) -> None:
        payload = _policy_bytes(policy)
        if len(payload) > _MAX_BYTES:
            raise _deny("invalid_permission_request")
        temporary = policy_path.with_name(".PROJECT_PERMISSIONS." + os.urandom(12).hex() + ".tmp")
        _inspect_no_links(temporary, allow_missing=True)
        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0)
        fd = os.open(temporary, flags, 0o600)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            fd = -1
            os.replace(temporary, policy_path)
        finally:
            if fd >= 0:
                os.close(fd)
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass

    def save(self, *, expected_project_id: str, expected_binding: str, expected_revision: str,
             read_directories: Sequence[str], write_directories: Sequence[str], confirmed: bool) -> dict[str, object]:
        if confirmed is not True:
            raise _deny("permission_not_confirmed")
        context, root, identity = self._current()
        policy_path, lock_path = self._paths(root)
        with _project_lock(lock_path):
            current, current_root, current_identity = self._current()
            if current.project_id != context.project_id or current.binding != context.binding or current_root != root or current_identity != identity:
                raise _deny("project_context_changed", 409)
            old = self._load(current, root, identity, policy_path)
            snapshot = self._snapshot(current, root, identity, old)
            self._assert_expected(current, snapshot, expected_project_id, expected_binding, expected_revision)
            reads = _normalise_directories(root, read_directories)
            writes = _normalise_directories(root, write_directories)
            counter = int(old["revision_counter"]) + 1 if old else 1
            policy: dict[str, object] = {"schema": _SCHEMA, "project_id": current.project_id,
                "root": str(root), "physical_root": identity, "revision_counter": counter,
                "read_directories": reads, "write_directories": writes, "updated_at": int(self._clock())}
            self._write(policy_path, policy)
            return self._snapshot(current, root, identity, policy)

    def revoke(self, *, expected_project_id: str, expected_binding: str, expected_revision: str, confirmed: bool) -> dict[str, object]:
        return self.save(expected_project_id=expected_project_id, expected_binding=expected_binding,
                         expected_revision=expected_revision, read_directories=(), write_directories=(), confirmed=confirmed)

    @contextmanager
    def lease(self, effect: Literal["read", "write"], paths: Sequence[str], *, expected_revision: str | None = None) -> Iterator[dict[str, object]]:
        if (effect not in {"read", "write"} or isinstance(paths, (str, bytes))
                or not isinstance(paths, Sequence) or not paths):
            raise _deny("invalid_permission_request")
        context, root, identity = self._current()
        policy_path, lock_path = self._paths(root)
        # A denied action must not bootstrap an empty state directory or leave
        # behind a lock file when the project has never been configured.
        if not policy_path.is_file():
            raise _deny("permission_denied")
        # The lock is held only across bounded IO by the caller. Never acquire a
        # lease before model inference or human review.
        with _project_lock(lock_path):
            current, current_root, current_identity = self._current()
            if current.project_id != context.project_id or current.binding != context.binding or current_root != root or current_identity != identity:
                raise _deny("project_context_changed", 409)
            policy = self._load(current, root, identity, policy_path)
            if policy is None:
                raise _deny("permission_denied")
            snapshot = self._snapshot(current, root, identity, policy)
            if expected_revision is not None and snapshot["revision"] != expected_revision:
                raise _deny("revision_conflict", 409)
            directories = policy["read_directories"] if effect == "read" else policy["write_directories"]
            approved_roots = [root if item == "." else root.joinpath(*item.split("/")) for item in directories]
            for relative in paths:
                rel = _safe_effect_path(relative)
                target = root.joinpath(*rel.parts)
                _inspect_no_links(target, allow_missing=effect == "write")
                try:
                    resolved = target.resolve(strict=effect == "read")
                except (OSError, RuntimeError):
                    raise _deny("project_path_unavailable", 409) from None
                if resolved != root and root not in resolved.parents:
                    raise _deny("project_path_denied")
                if resolved.exists():
                    target_info = resolved.stat()
                    if stat.S_ISREG(target_info.st_mode) and target_info.st_nlink != 1:
                        raise _deny("project_path_denied")
                if any(_path_within(resolved, approved) for approved in approved_roots):
                    continue
                raise _deny("permission_denied")
            yield snapshot

    @contextmanager
    def context_lease(self, paths: Sequence[str], *, expected_revision: str | None = None) -> Iterator[dict[str, object]]:
        """Permit host-only reads of the three project continuity ledgers.

        This narrow bridge is intentionally separate from model/tool leases:
        generic lease() continues to reject every governance-root path.
        """
        if (isinstance(paths, (str, bytes)) or not isinstance(paths, Sequence)
                or not paths or len(paths) > len(_CONTEXT_READ_PATHS)
                or any(not isinstance(path, str) or path not in _CONTEXT_READ_PATHS for path in paths)
                or len(set(paths)) != len(paths)):
            raise _deny("project_path_denied")
        context, root, identity = self._current()
        policy_path, lock_path = self._paths(root)
        if not policy_path.is_file():
            raise _deny("permission_denied")
        with _project_lock(lock_path):
            current, current_root, current_identity = self._current()
            if current.project_id != context.project_id or current.binding != context.binding or current_root != root or current_identity != identity:
                raise _deny("project_context_changed", 409)
            policy = self._load(current, root, identity, policy_path)
            if policy is None or "." not in policy["read_directories"]:
                raise _deny("permission_denied")
            snapshot = self._snapshot(current, root, identity, policy)
            if expected_revision is not None and snapshot["revision"] != expected_revision:
                raise _deny("revision_conflict", 409)
            for relative in paths:
                target = root.joinpath(*relative.split("/"))
                _inspect_no_links(target, allow_missing=True)
                try:
                    resolved = target.resolve(strict=False)
                except (OSError, RuntimeError):
                    raise _deny("project_path_unavailable", 409) from None
                if resolved != root and root not in resolved.parents:
                    raise _deny("project_path_denied")
                if resolved.exists():
                    info = resolved.stat()
                    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                        raise _deny("project_path_denied")
            yield snapshot

    def allowed(self, effect: Literal["read", "write"], relative_path: str) -> bool:
        try:
            with self.lease(effect, (relative_path,)):
                return True
        except PermissionError:
            return False


def _safe_effect_path(value: str) -> Path:
    if value == ".":
        return Path(".")
    if not isinstance(value, str) or not value or value.startswith(("/", "\\")) or _DRIVE.match(value) or "\\" in value or ":" in value or "\x00" in value:
        raise _deny("project_path_denied")
    parts = value.split("/")
    if any(not part or part in {".", ".."} or part != part.rstrip(" .") or _RESERVED.fullmatch(part) or part.casefold() in _BLOCKED or _SENSITIVE.search(part) or any(ord(char) < 32 or char in '<>"|?*' for char in part) for part in parts):
        raise _deny("project_path_denied")
    return Path(*parts)


def _path_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False
