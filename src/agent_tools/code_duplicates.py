"""Bounded, read-only duplicate-code inspection for one authorized directory."""

from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import secrets
import threading
import time
from collections import defaultdict
from pathlib import Path, PurePosixPath
from typing import Any, Sequence

from src.agent_tools.workspace_read import _BLOCKED_DIRECTORY_NAMES, _SENSITIVE_NAME, normalize_workspace_path
from src.sandbox import Capability, SandboxError, SandboxFilesystem, SandboxProfile, SandboxSpecification


SCAN_CODE_DUPLICATES = "scan_code_duplicates"
MAX_SCAN_FILES = 300
MAX_SCAN_FILE_BYTES = 256 * 1024
MAX_SCAN_TOTAL_BYTES = 10 * 1024 * 1024
MAX_SCAN_LINES_PER_FILE = 20_000
MAX_SCAN_TOTAL_LINES = 150_000
MAX_FINDINGS = 200
MIN_EXACT_LINES = 5
SUPPORTED_EXTENSIONS = {".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".java", ".go", ".rs", ".cs", ".cpp", ".c", ".h", ".hpp", ".php", ".rb", ".swift", ".kt", ".kts"}

SCAN_CODE_DUPLICATES_TOOL = {
    "type": "function",
    "function": {
        "name": SCAN_CODE_DUPLICATES,
        "description": "Run a deterministic, read-only duplicate-code scan over one user-authorized project directory. Reports exact repeated source blocks and structurally similar Python functions with project-relative file and line references. Never edits files or runs commands.",
        "parameters": {
            "type": "object",
            "required": ["directory"],
            "properties": {"directory": {"type": "string", "description": "Exact project-relative directory authorized by the user for this conversation turn."}},
        },
    },
}


class WorkspaceDirectoryAuthorizations:
    """Single-use directory grants bound to the owner and revision of one turn."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._grants: dict[str, dict[str, Any]] = {}

    def issue(self, workspace_root: Path | str, *, owner_kind: str, owner_id: str,
              conversation_id: str, revision: int, directories: Sequence[str], ttl_seconds: int = 300) -> dict[str, Any]:
        canonical = validate_workspace_scan_directories(workspace_root, directories)
        token = secrets.token_urlsafe(32)
        grant = {"owner_kind": owner_kind, "owner_id": owner_id, "conversation_id": conversation_id,
                 "revision": revision, "directories": canonical, "expires_at": time.time() + ttl_seconds}
        with self._lock:
            self._grants[token] = grant
        return {"authorization_id": token, "directories": canonical, "expires_in_seconds": ttl_seconds}

    def consume(self, token: str, *, owner_kind: str, owner_id: str, conversation_id: str,
                revision: int) -> list[str] | None:
        with self._lock:
            grant = self._grants.get(token)
            if not grant:
                return None
            if grant["expires_at"] < time.time():
                self._grants.pop(token, None)
                return None
            if any(grant[key] != value for key, value in {
                "owner_kind": owner_kind, "owner_id": owner_id,
                "conversation_id": conversation_id, "revision": revision,
            }.items()):
                return None
            self._grants.pop(token, None)
            return list(grant["directories"])


WORKSPACE_DIRECTORY_AUTHORIZATIONS = WorkspaceDirectoryAuthorizations()


def _blocked_directory(parts: tuple[str, ...]) -> bool:
    return any(part.casefold() in _BLOCKED_DIRECTORY_NAMES or part.startswith(".") or _SENSITIVE_NAME.fullmatch(part)
               for part in parts)


def validate_workspace_scan_directories(workspace_root: Path | str, directories: Sequence[str]) -> list[str]:
    if not isinstance(directories, (list, tuple)) or not 1 <= len(directories) <= 5:
        raise ValueError("Authorize between one and five project directories.")
    filesystem = SandboxFilesystem(SandboxSpecification.from_profile(workspace_root, SandboxProfile.READ_ONLY_AGENT))
    canonical: list[str] = []
    seen: set[str] = set()
    for requested in directories:
        normalized = normalize_workspace_path(requested)
        if normalized is None:
            raise ValueError("Directory paths must be project-relative and cannot contain traversal segments.")
        parts = tuple(PurePosixPath(normalized).parts)
        if _blocked_directory(parts):
            raise ValueError("This directory is outside the code files available for analysis.")
        target = filesystem.resolve_read(normalized)
        if not target.is_dir():
            raise ValueError("Only existing project directories can be authorized for scanning.")
        resolved = filesystem.relative_path(target)
        if _blocked_directory(tuple(PurePosixPath(resolved).parts)):
            raise ValueError("This directory is outside the code files available for analysis.")
        key = os.path.normcase(resolved)
        if key in seen:
            raise ValueError("Authorized directory paths must be unique.")
        seen.add(key)
        canonical.append(resolved)
    return canonical


def _normalize_source_line(line: str) -> str:
    value = line.strip()
    if not value:
        return ""
    if value.startswith(("#", "//", "/*", "<!--", "--")) or re.match(r"^\*\s", value):
        return ""
    return re.sub(r"\s+", " ", value)


def _function_shape(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    body = ast.Module(body=node.body, type_ignores=[])
    for child in ast.walk(body):
        if isinstance(child, ast.Name):
            child.id = "NAME"
        elif isinstance(child, ast.arg):
            child.arg = "ARG"
        elif isinstance(child, ast.Constant):
            child.value = "CONST"
    return ast.dump(body, annotate_fields=True, include_attributes=False)


def scan_code_duplicates(workspace_root: Path | str, arguments: Any,
                         authorized_directories: Sequence[str] = ()) -> tuple[dict[str, Any], dict[str, Any]]:
    """Scan one explicitly authorized directory. Never returns file contents."""
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except (TypeError, ValueError):
            arguments = None
    requested = arguments.get("directory") if isinstance(arguments, dict) else None
    normalized = normalize_workspace_path(requested)

    def denied(message: str, code: str) -> tuple[dict[str, Any], dict[str, Any]]:
        return {"ok": False, "error": message}, {"decision": "DENY", "kind": "directory_code_scan", "path": normalized, "reason_code": code}

    if normalized is None:
        return denied("Provide one project-relative directory path.", "INVALID_DIRECTORY")
    if os.path.normcase(normalized) not in {os.path.normcase(path) for path in authorized_directories}:
        return denied("This directory was not authorized for this message.", "DIRECTORY_NOT_AUTHORIZED")
    try:
        filesystem = SandboxFilesystem(SandboxSpecification.from_profile(workspace_root, SandboxProfile.READ_ONLY_AGENT))
        if Capability.FILESYSTEM_READ not in filesystem.specification.allowed_capabilities:
            return denied("Read-only workspace access is unavailable.", "CAPABILITY_UNAVAILABLE")
        root = filesystem.resolve_read(normalized)
        if not root.is_dir():
            return denied("The authorized path is not a directory.", "NOT_A_DIRECTORY")
        relative_root = filesystem.relative_path(root)
        if _blocked_directory(tuple(PurePosixPath(relative_root).parts)):
            return denied("This directory is outside the files available for code analysis.", "PATH_BLOCKED")
    except (OSError, ValueError):
        return denied("The authorized directory could not be resolved safely.", "DIRECTORY_UNAVAILABLE")
    except Exception as error:
        from src.sandbox import SandboxError
        if isinstance(error, SandboxError):
            return denied("The directory is outside the readable project scope.", "PATH_OUTSIDE_WORKSPACE")
        raise

    files: list[tuple[str, Path, bytes, str]] = []
    total_bytes = 0
    total_lines = 0
    skipped = 0
    truncated = False
    for current, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
        current_path = Path(current)
        dirnames[:] = sorted(name for name in dirnames
                             if name.casefold() not in _BLOCKED_DIRECTORY_NAMES
                             and not name.startswith(".") and not _SENSITIVE_NAME.fullmatch(name)
                             and not (current_path / name).is_symlink())
        for filename in sorted(filenames):
            path = current_path / filename
            if path.suffix.lower() not in SUPPORTED_EXTENSIONS or path.is_symlink() or _SENSITIVE_NAME.fullmatch(filename) or filename.startswith("."):
                skipped += 1
                continue
            if len(files) >= MAX_SCAN_FILES:
                truncated = True
                break
            try:
                relative_candidate = path.relative_to(filesystem.root).as_posix()
                safe_path = filesystem.resolve_read(relative_candidate)
                if path.is_symlink() or safe_path.is_symlink():
                    skipped += 1
                    continue
                before = safe_path.stat()
                if not safe_path.is_file() or before.st_size > MAX_SCAN_FILE_BYTES:
                    skipped += 1
                    continue
                if total_bytes + before.st_size > MAX_SCAN_TOTAL_BYTES:
                    skipped += 1
                    truncated = True
                    break
                with safe_path.open("rb") as stream:
                    opened = os.fstat(stream.fileno())
                    raw = stream.read(MAX_SCAN_FILE_BYTES + 1)
                after = safe_path.stat()
                resolved_after = filesystem.resolve_read(relative_candidate)
                if resolved_after != safe_path or (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns) or (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns) or len(raw) > MAX_SCAN_FILE_BYTES:
                    skipped += 1
                    continue
                text = raw.decode("utf-8")
                if "\x00" in text or re.search(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----|\b(?:api[_-]?key|client[_-]?secret|access[_-]?token|password)\s*[:=]\s*['\"][A-Za-z0-9._~+/=-]{12,}['\"]|\bBearer\s+[A-Za-z0-9._~+/=-]{24,}", text, re.IGNORECASE):
                    skipped += 1
                    continue
                source_line_count = len(text.splitlines())
                if source_line_count > MAX_SCAN_LINES_PER_FILE:
                    skipped += 1
                    truncated = True
                    continue
                if total_lines + source_line_count > MAX_SCAN_TOTAL_LINES:
                    skipped += 1
                    truncated = True
                    break
                rel = filesystem.relative_path(safe_path)
                if not rel.startswith(relative_root.rstrip("/") + "/"):
                    skipped += 1
                    continue
                files.append((rel, path, raw, text))
                total_bytes += len(raw)
                total_lines += source_line_count
            except (OSError, UnicodeDecodeError, ValueError, SandboxError):
                skipped += 1
        if truncated:
            break

    findings: list[dict[str, Any]] = []
    shingles: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for relative, _path, _raw, text in files:
        lines = text.splitlines()
        normalized_lines = [_normalize_source_line(line) for line in lines]
        for start in range(max(0, len(lines) - MIN_EXACT_LINES + 1)):
            block = normalized_lines[start:start + MIN_EXACT_LINES]
            if sum(bool(line) for line in block) < MIN_EXACT_LINES:
                continue
            digest = hashlib.sha256("\n".join(block).encode("utf-8")).hexdigest()
            shingles[digest].append((relative, start + 1))
    seen_pairs: set[tuple[str, int, str, int]] = set()
    for digest, occurrences in shingles.items():
        if len({item[0] for item in occurrences}) < 2 and len(occurrences) < 2:
            continue
        for left_index, left in enumerate(occurrences):
            for right in occurrences[left_index + 1:]:
                if left == right:
                    continue
                first, second = sorted((left, right))
                identity = (first[0], first[1], second[0], second[1])
                if identity in seen_pairs:
                    continue
                seen_pairs.add(identity)
                findings.append({"kind": "exact_block", "similarity": 1.0, "left": {"path": first[0], "start_line": first[1], "end_line": first[1] + MIN_EXACT_LINES - 1}, "right": {"path": second[0], "start_line": second[1], "end_line": second[1] + MIN_EXACT_LINES - 1}, "fingerprint": digest})
                if len(findings) >= MAX_FINDINGS:
                    truncated = True
                    break
            if len(findings) >= MAX_FINDINGS:
                break
        if len(findings) >= MAX_FINDINGS:
            break

    python_shapes: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for relative, _path, _raw, text in files:
        if not relative.lower().endswith(".py"):
            continue
        try:
            tree = ast.parse(text)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and getattr(node, "end_lineno", node.lineno) - node.lineno >= 3:
                    shape = _function_shape(node)
                    python_shapes[hashlib.sha256(shape.encode("utf-8")).hexdigest()].append({"path": relative, "name": node.name, "start_line": node.lineno, "end_line": node.end_lineno})
        except (SyntaxError, ValueError, RecursionError):
            skipped += 1
    for digest, functions in python_shapes.items():
        if len(functions) < 2:
            continue
        for index, left in enumerate(functions):
            for right in functions[index + 1:]:
                findings.append({"kind": "similar_python_function_structure", "similarity": "structural_match_after_identifier_and_literal_normalization", "left": left, "right": right, "fingerprint": digest})
                if len(findings) >= MAX_FINDINGS:
                    truncated = True
                    break
            if len(findings) >= MAX_FINDINGS:
                break
        if len(findings) >= MAX_FINDINGS:
            break

    manifest = [{"path": relative, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)} for relative, _path, raw, _text in files]
    manifest_sha256 = hashlib.sha256(json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    result = {"ok": True, "directory": relative_root, "files_scanned": len(files), "bytes_scanned": total_bytes,
              "files_skipped": skipped, "truncated": truncated, "manifest_sha256": manifest_sha256,
              "lines_scanned": total_lines,
              "findings": findings, "finding_count": len(findings),
              "supported_extensions": sorted(SUPPORTED_EXTENSIONS),
              "method": {"exact": f"normalized repeated {MIN_EXACT_LINES}-line code blocks across supported source files", "similar": "Python function AST structure after identifier and literal normalization"},
              "limitations": ["Structural Python matches can include false positives because identifiers and literals are normalized.", "Non-Python findings are exact repeated line blocks only; semantic equivalence is not assessed.", "No code is changed or executed."]}
    receipt = {"decision": "ALLOW", "kind": "directory_code_scan", "path": relative_root,
               "files_scanned": len(files), "files_skipped": skipped, "bytes_scanned": total_bytes, "lines_scanned": total_lines,
               "finding_count": len(findings), "truncated": truncated, "manifest_sha256": manifest_sha256,
               "files": manifest}
    return result, receipt
