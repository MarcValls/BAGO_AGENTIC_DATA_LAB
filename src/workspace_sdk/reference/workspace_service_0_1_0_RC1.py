"""Standalone bounded workspaces, local files and local Git. No BAGO dependency."""
from __future__ import annotations
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import re
import shutil
import stat
import subprocess
import sys
import uuid
from urllib.parse import urlparse
from reused_primitives import atomic_write, MERGE_CONFLICT_RE, normalize_visibility, validate_repository_name
from sync_primitives import CommandResult, GitSnapshot, build_plan, _action
from auth_primitives import _extract_auth_info

VERSION = "0.1.0-RC1"
CONTEXT = (".bago/context/PROJECT_CONTEXT.md", ".bago/state/PROJECT_STATE.json", ".bago/runtime/ACTIVE_HANDOFF.md")
SENSITIVE = re.compile(r"^(?:\.env(?:\..*)?|credentials?(?:\..*)?|secrets?(?:\..*)?|id_(?:rsa|ed25519)(?:\..*)?|\.npmrc|\.netrc|\.pypirc|.*(?:[._-])(?:token|password|secret|credential|api[_-]?key)(?:[._-].*)?)$|\.(?:pem|key|p12|pfx|keystore)$", re.I)
SECRET = re.compile(r"-----BEGIN .*PRIVATE KEY-----|\b(?:api[_-]?key|client[_-]?secret|access[_-]?token|password)\s*[:=]\s*['\"][A-Za-z0-9._~+/=-]{12,}['\"]|\bBearer\s+[A-Za-z0-9._~+/=-]{24,}", re.I)
MAX = 1024 * 1024


def now(): return datetime.now(timezone.utc).isoformat()
def encoded(value): return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
def sha(value): return hashlib.sha256(value).hexdigest()
def digest(value): return sha(encoded(value))


class ServiceError(Exception):
    def __init__(self, code, message, status=400):
        super().__init__(message)
        self.code, self.status = code, status


def linked(path):
    try:
        details = path.lstat()
        return stat.S_ISLNK(details.st_mode) or bool(getattr(details, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
    except FileNotFoundError:
        return False


def atomic(path, content):
    atomic_write(path, content)


def checked_name(name):
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", name) or name.upper().split(".")[0] in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1,10)), *(f"LPT{i}" for i in range(1,10))}:
        raise ServiceError("invalid_name", "Choose an ASCII workspace name containing letters, numbers, _ or -")
    return name


class WorkspaceService:
    def __init__(self, allowed_parent):
        parent = Path(allowed_parent)
        if not parent.is_absolute() or not parent.is_dir():
            raise ServiceError("invalid_parent", "An existing absolute allowed parent directory is required")
        for part in (parent, *parent.parents):
            if linked(part):
                raise ServiceError("linked_parent", "Parent must not contain symlinks or reparse points")
        self.parent = parent.resolve()

    def create(self, name, title, confirmed=False):
        checked_name(name)
        if confirmed is not True:
            raise ServiceError("confirmation_required", "Confirm creation beneath the explicit allowed parent")
        if not isinstance(title, str) or not title.strip() or len(title) > 200 or any(ord(c) < 32 for c in title) or SECRET.search(title):
            raise ServiceError("invalid_title", "A short, single-line workspace title is required")
        root = self.parent / name
        try:
            root.mkdir(exist_ok=False)
        except FileExistsError:
            raise ServiceError("workspace_exists", "Never overwrite or adopt an existing directory", 409) from None
        identity = "workspace_" + uuid.uuid4().hex
        internal = root / ".workspace-service"
        internal.mkdir()
        (internal / "trash").mkdir()
        (internal / "hooks").mkdir()
        record = {"id": identity, "root": str(root), "name": name, "title": title, "revision": uuid.uuid4().hex, "created_at": now()}
        seed = {CONTEXT[0]: f"# {title}\n\nProyecto nuevo. Alcance y decisiones pendientes de definir por el usuario.\n",
                CONTEXT[1]: json.dumps({"project_id": identity, "state": "PREPARED", "updated_at": now(), "verification": "NOT_RUN", "pending": ["Define project acceptance criteria"]}, indent=2) + "\n",
                CONTEXT[2]: f"# Continuidad — {title}\n\nWorkspace creado. No se ha ejecutado ni validado un producto.\nSiguiente acción: definir alcance y criterios de aceptación.\n"}
        for relative, text in seed.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("x", encoding="utf-8") as handle:
                handle.write(text)
        atomic(internal / "manifest.json", encoded(record))
        return Workspace(root, self.parent).info()

    def list(self):
        results = []
        for child in sorted(self.parent.iterdir()):
            if child.is_dir() and not linked(child) and (child / ".workspace-service/manifest.json").is_file():
                try:
                    results.append(Workspace(child, self.parent).info())
                except (ServiceError, OSError, ValueError):
                    continue
        return {"workspaces": results}

    def open(self, workspace_id):
        if not isinstance(workspace_id, str) or not re.fullmatch(r"workspace_[0-9a-f]{32}", workspace_id):
            raise ServiceError("invalid_workspace", "Invalid workspace ID")
        for item in self.list()["workspaces"]:
            if item["id"] == workspace_id:
                return Workspace(Path(item["root"]), self.parent)
        raise ServiceError("workspace_not_found", "Workspace is outside this service's explicit parent", 404)


class Workspace:
    def __init__(self, root, parent):
        self.root = Path(root)
        self.parent = Path(parent)
        self.internal = self.root / ".workspace-service"
        self._check_root()
        self.manifest = json.loads((self.internal / "manifest.json").read_text(encoding="utf-8"))
        if Path(self.manifest["root"]) != self.root or not re.fullmatch(r"workspace_[0-9a-f]{32}", self.manifest.get("id", "")):
            raise ServiceError("identity_invalid", "Workspace manifest identity does not match root", 409)
        self.id = self.manifest["id"]

    def _check_root(self):
        if self.root.parent.resolve() != self.parent.resolve() or linked(self.root) or linked(self.internal):
            raise ServiceError("root_invalid", "Workspace boundary changed", 409)
        manifest = self.internal / "manifest.json"
        if linked(manifest) or not manifest.is_file():
            raise ServiceError("identity_missing", "Owned workspace manifest required", 409)

    @contextmanager
    def lock(self):
        self._check_root()
        path = self.internal / "lock"
        if linked(path):
            raise ServiceError("linked_internal", "Internal state must not be a link")
        with path.open("a+b") as handle:
            handle.seek(0)
            if handle.read(1) == b"":
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            try:
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                raise ServiceError("busy", "Another local operation owns this workspace", 409) from None
            try:
                yield
            finally:
                handle.seek(0)
                if os.name == "nt":
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def confirm(self, confirmation, operation):
        if not isinstance(confirmation, dict) or confirmation.get("confirmed") is not True or confirmation.get("operation") != operation or confirmation.get("workspace_id") != self.id:
            raise ServiceError("confirmation_required", "Confirmation must match operation and workspace identity")

    def path(self, relative, directory=False):
        if not isinstance(relative, str) or not relative or "\\" in relative or Path(relative).is_absolute() or PureWindowsPath(relative).drive:
            raise ServiceError("invalid_path", "A nonempty forward-slash relative path is required")
        parts = relative.split("/")
        if any(not part or part in (".", "..") or ":" in part or part.endswith((" ", ".")) or any(ord(c) < 32 for c in part) for part in parts):
            raise ServiceError("invalid_path", "Unsafe path component")
        reserved = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1,10)), *(f"LPT{i}" for i in range(1,10))}
        if any(any(c in '<>"|?*' for c in part) or part.split(".")[0].upper() in reserved for part in parts):
            raise ServiceError("invalid_path", "Device names and ambiguous portable file names are rejected")
        if any(part.casefold() in {".git", ".workspace-service", ".ssh", ".aws", ".config", ".gitmodules", ".gitattributes"} or SENSITIVE.search(part) for part in parts):
            raise ServiceError("path_denied", "Internal Git/service state or credential path is outside scope", 403)
        if parts[0].casefold() == ".bago" and relative not in CONTEXT and not (directory and any(item.startswith(relative + "/") for item in CONTEXT)):
            raise ServiceError("path_denied", "Only the three seeded context documents are in .bago scope", 403)
        candidate = self.root
        for part in parts:
            candidate = candidate / part
            if linked(candidate):
                raise ServiceError("link_denied", "Symlinks/reparse points are outside scope", 403)
        if not candidate.resolve().is_relative_to(self.root.resolve()):
            raise ServiceError("escape_denied", "Path leaves the workspace", 403)
        return candidate

    def read(self, path):
        candidate = self.path(path)
        if not candidate.is_file():
            raise ServiceError("file_not_found", "File does not exist", 404)
        details = candidate.stat()
        if details.st_nlink > 1:
            raise ServiceError("hardlink_denied", "Files with multiple hard links are outside scope", 403)
        if details.st_size > MAX:
            raise ServiceError("file_too_large", "Text file exceeds 1 MiB")
        raw = candidate.read_bytes()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            raise ServiceError("not_utf8", "Only UTF-8 text is supported") from None
        if "\0" in text or SECRET.search(text):
            raise ServiceError("sensitive_content", "Binary/private credential content is outside scope", 403)
        return {"path": path, "text": text, "sha256": sha(raw), "size": len(raw)}

    def info(self):
        self._check_root()
        return dict(self.manifest, context_files=[{"path": item, "sha256": self.read(item)["sha256"]} for item in CONTEXT])

    def list_files(self, directory=""):
        base = self.path(directory, True) if directory else self.root
        if not base.is_dir():
            raise ServiceError("directory_not_found", "Directory does not exist", 404)
        files, excluded = [], []
        for current, dirs, names in os.walk(base, followlinks=False):
            for name in list(dirs):
                relative = (Path(current) / name).relative_to(self.root).as_posix()
                try:
                    self.path(relative, True)
                except ServiceError as error:
                    dirs.remove(name)
                    excluded.append({"path": relative, "reason": error.code})
            for name in sorted(names):
                relative = (Path(current) / name).relative_to(self.root).as_posix()
                try:
                    item = self.read(relative)
                    files.append({key: item[key] for key in ("path", "size", "sha256")})
                except ServiceError as error:
                    excluded.append({"path": relative, "reason": error.code})
                if len(files) + len(excluded) > 10000:
                    raise ServiceError("listing_limit", "Listing exceeds bounded limit")
        return {"files": files, "excluded": excluded}

    def _expected(self, path, expected):
        candidate = self.path(path)
        if candidate.exists():
            if expected is None or self.read(path)["sha256"] != expected:
                raise ServiceError("hash_conflict", "File changed or create would overwrite an existing path", 409)
        elif expected is not None:
            raise ServiceError("hash_conflict", "Expected file no longer exists", 409)
        return candidate

    def _receipt(self, operation, details):
        identity = "receipt_" + uuid.uuid4().hex
        record = {"id": identity, "operation": operation, "workspace_id": self.id, "at": now(), **details}
        directory = self.internal / "receipts"
        if linked(directory):
            raise ServiceError("linked_internal", "Receipt directory must not be a link")
        directory.mkdir(exist_ok=True)
        atomic(directory / (identity + ".json"), encoded(record))
        return record

    def _write(self, path, text, expected):
        if not isinstance(text, str) or len(text.encode("utf-8")) > MAX or "\0" in text or SECRET.search(text):
            raise ServiceError("invalid_text", "Text must be bounded UTF-8 without private credentials")
        target = self._expected(path, expected)
        target.parent.mkdir(parents=True, exist_ok=True)
        atomic(target, text.encode("utf-8"))
        result = self.read(path)
        self._receipt("write", {"path": path, "before_sha256": expected, "after_sha256": result["sha256"]})
        return result

    def write(self, path, text, expected_sha256, confirmation):
        self.confirm(confirmation, "write")
        with self.lock(): return self._write(path, text, expected_sha256)

    def move(self, path, destination, expected_sha256, confirmation):
        self.confirm(confirmation, "move")
        if path in CONTEXT or destination in CONTEXT:
            raise ServiceError("context_preserved", "Seeded context documents can be explicitly edited, not moved")
        with self.lock():
            source = self._expected(path, expected_sha256)
            if expected_sha256 is None or not source.is_file():
                raise ServiceError("file_not_found", "Existing source and hash required", 404)
            target = self.path(destination)
            if target.exists():
                raise ServiceError("destination_exists", "Never overwrite destination", 409)
            target.parent.mkdir(parents=True, exist_ok=True)
            source.rename(target)
            self._receipt("move", {"path": path, "destination": destination, "sha256": expected_sha256})
            return self.read(destination)

    def _trash_paths(self, identity):
        if not isinstance(identity, str) or not re.fullmatch(r"trash_[0-9a-f]{32}", identity):
            raise ServiceError("invalid_trash_id", "Invalid trash identity")
        directory = self.internal / "trash"
        if linked(directory):
            raise ServiceError("linked_internal", "Trash must not be a link")
        content, metadata = directory / (identity + ".data"), directory / (identity + ".json")
        if linked(content) or linked(metadata):
            raise ServiceError("linked_internal", "Trash entry must not be a link")
        return content, metadata

    def trash(self, path, expected_sha256, confirmation):
        self.confirm(confirmation, "trash")
        if path in CONTEXT: raise ServiceError("context_preserved", "Seeded context documents can be edited, not trashed")
        with self.lock():
            source = self._expected(path, expected_sha256)
            if expected_sha256 is None or not source.is_file():
                raise ServiceError("file_not_found", "Existing source and hash required", 404)
            identity = "trash_" + uuid.uuid4().hex
            content, metadata = self._trash_paths(identity)
            record = {"trash_id": identity, "path": path, "sha256": expected_sha256, "revision": uuid.uuid4().hex, "state": "prepared", "at": now()}
            atomic(metadata, encoded(record))
            source.rename(content)
            record["state"] = "trashed"
            atomic(metadata, encoded(record))
            self._receipt("trash", record)
            return record

    def trash_list(self):
        directory = self.internal / "trash"
        if linked(directory): raise ServiceError("linked_internal", "Trash must not be a link")
        items = []
        for metadata in sorted(directory.glob("trash_*.json")):
            content, checked = self._trash_paths(metadata.stem)
            record = json.loads(checked.read_text(encoding="utf-8"))
            record["integrity"] = "PASS" if content.is_file() and sha(content.read_bytes()) == record["sha256"] else "FAIL"
            record["recovery_required"] = record["state"] != "trashed"
            items.append(record)
        return {"items": items}

    def _trash_record(self, identity, expected_revision):
        content, metadata = self._trash_paths(identity)
        if not metadata.is_file() or not content.is_file():
            raise ServiceError("trash_not_found", "Trash entry is missing or needs recovery", 404)
        record = json.loads(metadata.read_text(encoding="utf-8"))
        if record["revision"] != expected_revision or sha(content.read_bytes()) != record["sha256"]:
            raise ServiceError("trash_conflict", "Trash revision or content changed", 409)
        return content, metadata, record

    def restore(self, trash_id, expected_revision, confirmation):
        self.confirm(confirmation, "restore")
        with self.lock():
            content, metadata, record = self._trash_record(trash_id, expected_revision)
            target = self.path(record["path"])
            if target.exists(): raise ServiceError("destination_exists", "Restore must not overwrite a new file", 409)
            target.parent.mkdir(parents=True, exist_ok=True)
            content.rename(target)
            metadata.unlink()
            self._receipt("restore", record)
            return self.read(record["path"])

    def delete_trash(self, trash_id, expected_revision, confirmation):
        self.confirm(confirmation, "delete_trash")
        with self.lock():
            content, metadata, record = self._trash_record(trash_id, expected_revision)
            self._receipt("delete_trash_intent", record)
            content.unlink()
            metadata.unlink()
            return {"deleted": True, "trash_id": trash_id}

    def _git(self, *args, allowed_failure=False, initializing=False, author_name="Workspace Service Fixture", author_email="workspace@example.test"):
        git = shutil.which("git")
        if not git: raise ServiceError("git_unavailable", "Git executable is unavailable", 503)
        if not initializing:
            config = self.root / ".git/config"
            pin = self.internal / "git-config-sha256"
            if linked(self.root / ".git") or linked(config) or linked(pin) or not pin.is_file() or sha(config.read_bytes()) != pin.read_text():
                raise ServiceError("git_config_changed", "Only service-created Git config with unchanged identity is supported", 409)
            if (self.root / ".git/objects/info/alternates").exists() or (self.root / ".git/commondir").exists():
                raise ServiceError("git_external_objects", "External Git directories are outside scope", 403)
            entries = 0
            for current, directories, files in os.walk(self.root / ".git", followlinks=False):
                for name in [*directories, *files]:
                    item = Path(current) / name
                    entries += 1
                    if entries > 10000: raise ServiceError("git_directory_limit", "Git state exceeds this bounded local service")
                    if linked(item) or (item.is_file() and item.stat().st_nlink > 1):
                        raise ServiceError("git_link_denied", "Git state contains linked files outside its private boundary", 403)
            hooks = self.internal / "hooks"
            if linked(hooks) or not hooks.is_dir() or any(hooks.iterdir()):
                raise ServiceError("hooks_changed", "Service hooks directory must remain empty", 409)
        env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, GIT_TERMINAL_PROMPT="0", GIT_ALLOW_PROTOCOL="",
                   GIT_AUTHOR_NAME=author_name, GIT_AUTHOR_EMAIL=author_email,
                   GIT_COMMITTER_NAME=author_name, GIT_COMMITTER_EMAIL=author_email)
        command = [git, "-c", "core.hooksPath=" + str(self.internal / "hooks"), "-c", "core.fsmonitor=false", "-c", "commit.gpgSign=false", "-C", str(self.root), *args]
        process = subprocess.run(command, env=env, capture_output=True, timeout=30)
        self.last_git_result = CommandResult(tuple(command), process.returncode,
                                             process.stdout.decode("utf-8", errors="replace"),
                                             process.stderr.decode("utf-8", errors="replace"))
        if process.returncode and not allowed_failure:
            raise ServiceError("git_failed", "Git operation failed; no success claimed", 409)
        return process.returncode, process.stdout.decode("utf-8", errors="replace")

    def _local_git_policy(self, paths):
        """Extend canonical sync-agent planning for a local-only new repository.

        Exact canonical symbols are retained in sync_primitives.py. Only the
        requirement for a remote and an external validator is inapplicable
        here: no fetch/push/merge is exposed and reviewed local preconditions
        run in git_stage/git_commit. External product tests remain NOT_RUN.
        """
        state = self.git_status()
        _, staged = self._git("diff", "--cached", "--name-only", "-z")
        _, remote_url = self._git("remote", "get-url", "origin", allowed_failure=True)
        snapshot = GitSnapshot(str(self.root), state["branch"], state["head"] or "", "origin", remote_url.strip(), "",
                               tuple(item[3:] for item in state["status"] if len(item) > 3),
                               tuple(path for path in staged.split("\0") if path), None, None, False)
        policy = build_plan(snapshot, base="main", paths=paths, commit=True, push=False, merge_pr=None,
                            preserve_unrelated_dirty=True, validators=(), skip_validation=False)
        policy["canonical_blockers"] = list(policy["blockers"])
        inapplicable = {"no existe el remote 'origin'", "commit sin validadores; proporcionar --validator o --skip-validation explicitamente"}
        policy["blockers"] = [item for item in policy["blockers"] if item not in inapplicable]
        policy["actions"] = [item for item in policy["actions"] if item != "fetch"]
        policy["status"] = "BLOCKED" if policy["blockers"] else "PREPARED"
        policy["adapter"] = "local_only_reviewed_files"
        policy["external_validation"] = "NOT_RUN"
        policy["local_preconditions"] = ["confirmation identity", "expected HEAD", "empty foreign index", "selected file hashes", "selected index tree"]
        return policy

    def _head(self):
        code, output = self._git("rev-parse", "--verify", "HEAD", allowed_failure=True)
        return output.strip() if code == 0 else None

    def git_status(self):
        head = self._head()
        _, branch = self._git("symbolic-ref", "--quiet", "--short", "HEAD", allowed_failure=True)
        _, status = self._git("status", "--porcelain=v1", "-z", "--untracked-files=all")
        _, staged = self._git("diff", "--cached", "--raw", "-z")
        _, conflicts = self._git("diff", "--name-only", "--diff-filter=U", "-z")
        index = self.root / ".git/index"
        return {"head": head, "branch": branch.strip(), "status": status.split("\0")[:-1],
                "index_fingerprint": sha(index.read_bytes()) if index.exists() else None,
                "staged_fingerprint": sha(staged.encode()), "worktree_fingerprint": digest(self.list_files()["files"]),
                "conflicts": [x for x in conflicts.split("\0") if x]}

    def git_init(self, confirmation):
        self.confirm(confirmation, "git_init")
        with self.lock():
            if (self.root / ".git").exists(): raise ServiceError("git_exists", "Never replace an existing Git repository", 409)
            self._git("init", "--initial-branch=main", initializing=True)
            (self.root / ".git/info/exclude").write_text(".workspace-service/\n", encoding="utf-8")
            (self.internal / "git-config-sha256").write_text(sha((self.root / ".git/config").read_bytes()))
            return self.git_status()

    def git_diff(self, paths=None, cached=False):
        paths = paths or [item["path"] for item in self.list_files()["files"]]
        for path in paths:
            target = self.path(path)
            if target.is_file(): self.read(path)
        args = ["diff", "--no-ext-diff", "--no-textconv"] + (["--cached"] if cached else []) + ["--", *(":(literal)" + path for path in paths)]
        _, diff = self._git(*args)
        if len(diff.encode()) > 2 * MAX: raise ServiceError("diff_limit", "Diff exceeds bounded limit")
        return {"head": self._head(), "diff": diff}

    def git_branch(self, name, expected_head, confirmation):
        self.confirm(confirmation, "git_branch")
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9/_-]{0,100}", name) or ".." in name:
            raise ServiceError("invalid_branch", "Invalid bounded branch name")
        with self.lock():
            if self._head() != expected_head or expected_head is None: raise ServiceError("head_conflict", "Expected committed HEAD required", 409)
            self._git("branch", "--", name, expected_head)
            return self.git_status()

    def git_stage(self, paths, expected_head, expected_hashes, confirmation):
        self.confirm(confirmation, "git_stage")
        if not isinstance(paths, list) or not paths or not all(isinstance(x, str) for x in paths) or len(set(paths)) != len(paths) or not isinstance(expected_hashes, dict):
            raise ServiceError("invalid_selection", "Select explicit unique file paths and hashes")
        with self.lock():
            if self._head() != expected_head: raise ServiceError("head_conflict", "HEAD changed", 409)
            _, staged = self._git("diff", "--cached", "--name-only", "-z")
            if staged: raise ServiceError("foreign_index", "Index contains existing changes; preserve them outside this selection", 409)
            policy = self._local_git_policy(paths)
            if policy["blockers"]: raise ServiceError("sync_policy_blocked", "; ".join(policy["blockers"]), 409)
            for path in paths:
                if self.read(path)["sha256"] != expected_hashes.get(path): raise ServiceError("hash_conflict", "Selected file changed", 409)
                _, pending = self._git("status", "--porcelain=v1", "-z", "--", ":(literal)" + path)
                if not pending: raise ServiceError("no_selected_diff", "Selected file is unchanged or ignored; index preserved", 409)
            self._git("add", "--", *(":(literal)" + path for path in paths))
            _, actual = self._git("diff", "--cached", "--name-only", "-z")
            actual_paths = [x for x in actual.split("\0") if x]
            if set(actual_paths) != set(paths): raise ServiceError("index_mismatch", "Some selected files have no diff; review current index", 409)
            for path in paths:
                _, blob = self._git("show", ":" + path)
                if sha(blob.encode("utf-8")) != expected_hashes[path]:
                    raise ServiceError("index_content_mismatch", "Index content differs from reviewed bytes; review retained index", 409)
            record = {"head": expected_head, "paths": sorted(paths), "hashes": {path: expected_hashes[path] for path in paths}, "revision": uuid.uuid4().hex}
            _, tree = self._git("write-tree")
            record["tree"] = tree.strip()
            atomic(self.internal / "selection.json", encoded(record))
            return {"status": self.git_status(), "selection_revision": record["revision"], "paths": record["paths"], "policy": policy}

    def git_commit(self, message, expected_head, selection_revision, confirmation, author_name="Workspace Service Fixture", author_email="workspace@example.test"):
        self.confirm(confirmation, "git_commit")
        if not isinstance(message, str) or not message.strip() or len(message) > 1000 or "\0" in message:
            raise ServiceError("invalid_message", "Commit message is required")
        if not isinstance(author_name, str) or not re.fullmatch(r"[^\x00-\x1f<>]{1,100}", author_name) or not re.fullmatch(r"[^\s<>@]+@[^\s<>@]+\.[^\s<>@]+", author_email):
            raise ServiceError("invalid_author", "Explicit bounded Git author is required")
        with self.lock():
            file = self.internal / "selection.json"
            if linked(file) or not file.is_file(): raise ServiceError("selection_missing", "Stage a reviewed selection first", 409)
            record = json.loads(file.read_text())
            if record["head"] != expected_head or record["revision"] != selection_revision or self._head() != expected_head:
                raise ServiceError("selection_conflict", "HEAD or selection revision changed", 409)
            _, tree = self._git("write-tree")
            if tree.strip() != record["tree"]: raise ServiceError("foreign_index", "Index changed after review", 409)
            for path in record["paths"]:
                if self.read(path)["sha256"] != record["hashes"][path]: raise ServiceError("hash_conflict", "Selected file changed after staging", 409)
            self._git("commit", "--no-verify", "-m", message, author_name=author_name, author_email=author_email)
            action = _action("commit", "PASS", self.last_git_result)
            commit = self._head()
            self._receipt("git_commit", {"head_before": expected_head, "commit": commit, "paths": record["paths"], "action": action})
            file.unlink()
            return {"commit": commit, "head_before": expected_head, "paths": record["paths"], "status": self.git_status()}

    def resolve(self, path, text, expected_sha256, confirmation):
        self.confirm(confirmation, "resolve")
        with self.lock():
            if path not in self.git_status()["conflicts"]: raise ServiceError("not_conflicted", "Path is not a current Git conflict")
            if MERGE_CONFLICT_RE.search(text): raise ServiceError("conflict_markers", "Resolution still contains conflict markers")
            return self._write(path, text, expected_sha256)

    def remote_plan(self, kind, repo, base="", head="", title="", visibility="private"):
        if kind not in {"repo_create", "pr_create", "pr_merge", "conflict_review"} or not isinstance(repo, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
            raise ServiceError("invalid_remote_plan", "Choose a supported plan and OWNER/REPO")
        try:
            for component in repo.split("/"): validate_repository_name(component)
            visibility = normalize_visibility(visibility)
        except ValueError:
            raise ServiceError("invalid_remote_plan", "Invalid repository name or visibility") from None
        return {"operation": kind, "repo": repo, "base": base, "head": head, "title": title,
                "expected_local_head": self._head() if (self.root / ".git").exists() else None,
                "status": "PROPOSED", "executed": False, "visibility": visibility, "remote_execution": "NOT_IMPLEMENTED",
                "closure_requirement": "Remote authorization, expected remote head/base, execution adapter and independent provider receipt"}


def github_read(kind, repo=None):
    gh = shutil.which("gh")
    if not gh: raise ServiceError("gh_unavailable", "GitHub CLI is not installed", 503)
    if kind == "auth":
        process = subprocess.run([gh, "auth", "status", "--json", "hosts"], capture_output=True, timeout=30)
        try:
            info = _extract_auth_info(process.returncode, process.stdout.decode("utf-8", errors="replace"), "")
        except (TypeError, ValueError):
            info = {"authenticated": False, "credentialStorage": "unknown"}
        return {"available": True, "authenticated": info["authenticated"], "credential_storage": info["credentialStorage"], "remote_mutation": False}
    if not isinstance(repo, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
        raise ServiceError("invalid_repo", "Expected OWNER/REPO")
    choices = {"repo": ["repo", "view", repo, "--json", "nameWithOwner,url,defaultBranchRef,isPrivate"],
               "prs": ["pr", "list", "--repo", repo, "--json", "number,title,state,headRefOid,baseRefName,url"]}
    if kind not in choices: raise ServiceError("read_kind_denied", "Only auth, repo and prs read operations are supported")
    process = subprocess.run([gh, *choices[kind]], capture_output=True, timeout=30)
    if process.returncode: raise ServiceError("github_read_failed", "GitHub read did not complete", 503)
    return {"data": json.loads(process.stdout), "remote_mutation": False}


class API:
    def __init__(self, service): self.service = service
    def dispatch(self, method, path, data=None):
        if data is not None and not isinstance(data, dict): raise ServiceError("invalid_body", "Expected JSON object")
        data = data or {}
        path = urlparse(path).path.rstrip("/")
        prefix = "/api/workspaces/v1/workspaces"
        if path == prefix:
            if method == "GET": return 200, self.service.list()
            if method == "POST": return 201, self.service.create(data.get("name"), data.get("title"), data.get("confirmed"))
        if path.startswith(prefix + "/"):
            parts = path[len(prefix) + 1:].split("/")
            workspace = self.service.open(parts[0])
            if len(parts) == 1 and method == "GET": return 200, workspace.info()
            if parts[1:] == ["actions"] and method == "POST":
                operation = data.get("operation")
                allowed = {"list_files", "read", "write", "move", "trash", "trash_list", "restore", "delete_trash", "git_init", "git_status", "git_diff", "git_branch", "git_stage", "git_commit", "resolve", "remote_plan"}
                if operation not in allowed: raise ServiceError("operation_denied", "Unknown workspace action")
                args = {key: value for key, value in data.items() if key != "operation"}
                try: return 200, getattr(workspace, operation)(**args)
                except TypeError: raise ServiceError("invalid_arguments", "Arguments do not match this operation") from None
        raise ServiceError("not_found", "Unknown API route", 404)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parent", required=True)
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create"); create.add_argument("--name", required=True); create.add_argument("--title", required=True); create.add_argument("--confirmed", action="store_true")
    sub.add_parser("list")
    action = sub.add_parser("action"); action.add_argument("--workspace-id", required=True); action.add_argument("--json", required=True, help="JSON file path, or - for stdin")
    remote = sub.add_parser("github-read"); remote.add_argument("--kind", choices=["auth", "repo", "prs"], required=True); remote.add_argument("--repo")
    args = parser.parse_args(argv)
    try:
        service = WorkspaceService(args.parent)
        if args.command == "create": result = service.create(args.name, args.title, args.confirmed)
        elif args.command == "list": result = service.list()
        elif args.command == "github-read": result = github_read(args.kind, args.repo)
        else:
            raw = sys.stdin.read(MAX + 1) if args.json == "-" else Path(args.json).read_text(encoding="utf-8-sig")
            if len(raw.encode()) > MAX: raise ServiceError("body_limit", "Action JSON exceeds limit")
            data = json.loads(raw)
            _, result = API(service).dispatch("POST", "/api/workspaces/v1/workspaces/" + args.workspace_id + "/actions", data)
        print(encoded(result).decode())
        return 0
    except ServiceError as error:
        print(encoded({"error": {"code": error.code, "message": str(error)}}).decode())
        return 2
    except (OSError, ValueError, subprocess.SubprocessError):
        print(encoded({"error": {"code": "operation_failed", "message": "Operation failed; inspect state before any retry"}}).decode())
        return 3


if __name__ == "__main__": raise SystemExit(main())
