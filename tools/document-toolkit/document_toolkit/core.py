"""Bounded byte identities and deterministic documentary operations.

Design references: ADL SandboxFilesystem and Suite stable-read contracts.
This implementation is original; no external source code is vendored.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path, PureWindowsPath
import base64
import csv
import hashlib
import importlib.util
import io
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import time
import uuid

SCHEMA = "document-toolkit.result.v1"
OPERATIONS = ("inventory", "extract", "relate", "plan-rename", "export")
FORMATS = (".pdf", ".docx", ".xlsx", ".csv", ".eml", ".txt", ".png")


@dataclass(frozen=True)
class Limits:
    max_files: int = 100
    max_bytes: int = 32 * 1024 * 1024
    max_file_bytes: int = 8 * 1024 * 1024
    max_pages: int = 50
    max_cells: int = 10000
    max_chars: int = 100000
    max_seconds: int = 30

    def __post_init__(self):
        ceilings = {"max_files": 1000, "max_bytes": 256 * 1024 * 1024,
                    "max_file_bytes": 32 * 1024 * 1024, "max_pages": 500,
                    "max_cells": 100000, "max_chars": 1000000, "max_seconds": 120}
        for name, ceiling in ceilings.items():
            value = getattr(self, name)
            if type(value) is not int or not 1 <= value <= ceiling:
                raise ValueError(f"invalid limit: {name}")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf8")


class DocumentError(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _no_links(path):
    for part in (path, *path.parents):
        value = part.lstat()
        if stat.S_ISLNK(value.st_mode) or getattr(value, "st_file_attributes", 0) & 0x400:
            raise DocumentError("LINK_REJECTED")


def _root(value):
    path = Path(value).absolute()
    _no_links(path)
    if not path.is_dir():
        raise DocumentError("ROOT_NOT_DIRECTORY")
    return path.resolve(strict=True)


def _relative(value):
    if not isinstance(value, str) or not value or len(value) > 1024 or "\x00" in value:
        raise DocumentError("INVALID_PATH")
    p = PureWindowsPath(value)
    normalized = value.replace("\\", "/")
    if p.drive or p.root or normalized.startswith("/") or ":" in normalized:
        raise DocumentError("ABSOLUTE_OR_ADS_PATH")
    if any(part in ("", ".", "..") for part in normalized.split("/")):
        raise DocumentError("PATH_TRAVERSAL")
    return normalized


def stable_read(root, relative, maximum):
    """Read bytes once with path, opened handle and post-read identity agreement."""
    relative = _relative(relative)
    path = root / relative
    _no_links(path)
    if not path.resolve(strict=True).is_relative_to(root):
        raise DocumentError("PATH_ESCAPE")
    before = path.stat()
    # Windows/Python can expose different ctime semantics through stat and fstat.
    # Compare shared identity across APIs, and each API's ctime within itself.
    identity = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns)
    if not stat.S_ISREG(before.st_mode):
        raise DocumentError("NOT_REGULAR_FILE")
    if before.st_size > maximum:
        raise DocumentError("FILE_BYTE_LIMIT")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    fd = os.open(path, flags)
    with os.fdopen(fd, "rb") as stream:
        opened = os.fstat(stream.fileno())
        if identity(opened) != identity(before):
            raise DocumentError("SOURCE_CHANGED")
        data = stream.read(maximum + 1)
        after = os.fstat(stream.fileno())
    _no_links(path)
    if len(data) > maximum:
        raise DocumentError("FILE_BYTE_LIMIT")
    final = path.stat()
    if (identity(before) != identity(after) or identity(after) != identity(final)
            or before.st_ctime_ns != final.st_ctime_ns or opened.st_ctime_ns != after.st_ctime_ns
            or len(data) != after.st_size):
        raise DocumentError("SOURCE_CHANGED")
    return data


def _source(path, data):
    sha = digest(data)
    return {"source_id": "source_" + digest(canonical([path, sha]))[:24], "path": path,
            "sha256": sha, "bytes": len(data), "format": Path(path).suffix.lower()}


def capabilities():
    pdf = importlib.util.find_spec("pypdf") is not None
    pillow = importlib.util.find_spec("PIL") is not None
    tesseract = shutil.which("tesseract")
    from .windows_ocr import probe
    winrt = probe() if pillow and not tesseract else {"available": False, "recognition_verified": False, "check": "not_selected"}
    return {"schema": "document-toolkit.capabilities.v1", "version": "0.2.0",
            "operations": list(OPERATIONS), "formats": {
                name: {"available": pdf if name == ".pdf" else bool(pillow and (tesseract or winrt["available"])) if name == ".png" else True,
                       "dependency": "pypdf==6.13.1" if name == ".pdf" else "Pillow==12.2.0 and Tesseract or Windows WinRT OCR" if name == ".png" else "Python standard library"}
                for name in FORMATS}, "ocr_backends": {"tesseract": {"available": bool(tesseract), "recognition_verified": False}, "windows-winrt": winrt}, "ocr_executable_available": bool(tesseract), "source_writes": False}


def _paths(root, requested, limits, started, errors):
    if requested is not None:
        if not isinstance(requested, list) or not 1 <= len(requested) <= limits.max_files or len(set(requested)) != len(requested):
            raise DocumentError("INVALID_PATH_SELECTION")
        return [_relative(p) for p in requested]
    result = []
    for directory, folders, files in os.walk(root, followlinks=False):
        if time.monotonic() - started > limits.max_seconds:
            errors.append({"path": None, "code": "TIME_LIMIT"})
            break
        folders.sort()
        safe = []
        for name in folders:
            target = Path(directory) / name
            try:
                _no_links(target)
                if name not in {".git", ".venv", "node_modules", "__pycache__"}:
                    safe.append(name)
            except (OSError, DocumentError):
                errors.append({"path": target.relative_to(root).as_posix(), "code": "LINK_REJECTED"})
        folders[:] = safe
        for name in sorted(files):
            if len(result) >= limits.max_files:
                errors.append({"path": None, "code": "FILE_COUNT_LIMIT"})
                return result
            result.append((Path(directory) / name).relative_to(root).as_posix())
    return result


def _parse_isolated(data, suffix, limits, remaining):
    payload = {"bytes": base64.b64encode(data).decode("ascii"), "suffix": suffix, "limits": asdict(limits)}
    env = dict(os.environ)
    env["PYTHONPATH"] = str(Path(__file__).resolve().parent.parent) + os.pathsep + env.get("PYTHONPATH", "")
    try:
        proc = subprocess.run([sys.executable, "-m", "document_toolkit.parsers"], input=json.dumps(payload),
                              capture_output=True, text=True, encoding="utf8", timeout=max(.1, remaining), env=env)
    except subprocess.TimeoutExpired:
        raise DocumentError("PARSER_TIMEOUT") from None
    if proc.returncode:
        raise DocumentError("PARSER_FAILED")
    result = json.loads(proc.stdout)
    if result.get("error"):
        raise DocumentError(result["error"])
    return result


def _verify_bundle(root, bundle, limits):
    if not isinstance(bundle, dict) or bundle.get("schema") != SCHEMA or bundle.get("operation") != "extract":
        raise DocumentError("EXTRACTION_BUNDLE_REQUIRED")
    records = bundle.get("records")
    if not isinstance(records, list) or len(records) > limits.max_files:
        raise DocumentError("INVALID_RECORDS")
    expected = bundle.get("bundle_sha256")
    if len(canonical(records)) > limits.max_bytes:
        raise DocumentError("BUNDLE_BYTE_LIMIT")
    if expected != digest(canonical(records)):
        raise DocumentError("BUNDLE_INTEGRITY")
    total = 0
    characters = 0
    for record in records:
        source = record.get("source", {})
        raw = stable_read(root, source.get("path"), min(limits.max_file_bytes, limits.max_bytes-total))
        total += len(raw)
        if source != _source(source["path"], raw):
            raise DocumentError("STALE_SOURCE")
        segments = record.get("segments")
        if not isinstance(segments, list) or len(segments) > limits.max_cells:
            raise DocumentError("MISSING_PROVENANCE")
        for segment in segments:
            if not segment.get("location") or not isinstance(segment.get("text"), str):
                raise DocumentError("MISSING_PROVENANCE")
            characters += len(segment["text"])
            if characters > limits.max_chars:
                raise DocumentError("TOTAL_CHARACTER_LIMIT")
    return records


def _relations(records, limits):
    """Candidate links only. Amount equality never establishes a payment."""
    facts = []
    for record in records:
        for index, segment in enumerate(record["segments"]):
            text = segment["text"]
            references = sorted(set(re.findall(r"\b(?:INV|FAC|FACTURA|REF)[- :]*([A-Z0-9][A-Z0-9/-]{2,30})\b", text, re.I)))
            amounts = []
            for currency, amount in re.findall(r"\b(EUR|USD|GBP)\s+(-?\d+(?:[.,]\d{1,2})?)\b", text, re.I):
                try:
                    amounts.append({"currency": currency.upper(), "amount": str(Decimal(amount.replace(",", ".")))})
                except InvalidOperation:
                    pass
            if references or amounts:
                facts.append({"source_id": record["source"]["source_id"], "source_sha256": record["source"]["sha256"],
                              "segment_index": index, "location": segment["location"], "references": references, "amounts": amounts})
    links = []
    comparisons = 0
    for i, left in enumerate(facts):
        for right in facts[i+1:]:
            comparisons += 1
            if comparisons > limits.max_cells:
                return facts, links, True
            if left["source_id"] == right["source_id"]:
                continue
            common = sorted(set(left["references"]) & set(right["references"]))
            shared = [amount for amount in left["amounts"] if amount in right["amounts"]]
            if common or shared:
                links.append({"state": "CANDIDATE", "payment_confirmed": False, "matching_references": common,
                              "matching_amounts": shared, "evidence": [left, right],
                              "uncertainty": "Potential relation; identity, date, tax and settlement require review."})
                if len(links) >= limits.max_cells:
                    return facts, links, True
    return facts, links, False


def _rename_plan(root, entries, limits):
    if not isinstance(entries, list) or not 1 <= len(entries) <= limits.max_files:
        raise DocumentError("INVALID_RENAME_PLAN")
    targets, sources, result, total = set(), set(), [], 0
    for entry in entries:
        if not isinstance(entry, dict):
            raise DocumentError("INVALID_RENAME_ENTRY")
        source, target = _relative(entry.get("path")), _relative(entry.get("destination"))
        for part in target.split("/"):
            if re.search(r'[<>:"|?*\x00-\x1f]', part) or part.endswith((".", " ")) or re.fullmatch(r"(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?", part, re.I):
                raise DocumentError("INVALID_WINDOWS_NAME")
        key = target.casefold()
        if key in targets or source in sources or (root/target).exists() or key == source.casefold():
            raise DocumentError("RENAME_COLLISION")
        data = stable_read(root, source, min(limits.max_file_bytes, limits.max_bytes-total))
        total += len(data)
        if digest(data) != entry.get("expected_sha256"):
            raise DocumentError("STALE_SOURCE")
        targets.add(key); sources.add(source)
        result.append({"path": source, "destination": target, "expected_sha256": digest(data), "state": "PROPOSED"})
    return result


def _export(root, records, arguments, limits):
    destination = Path(arguments.get("destination", "")).absolute()
    if not arguments.get("destination") or destination.exists():
        raise DocumentError("OUTPUT_EXISTS_OR_MISSING")
    _no_links(destination.parent)
    if destination.parent.resolve().is_relative_to(root):
        raise DocumentError("OUTPUT_MUST_BE_OUTSIDE_SOURCE_ROOT")
    output_format = arguments.get("format", "json")
    if output_format == "json":
        payload = canonical({"schema": "document-toolkit.export.v1", "records": records})
    elif output_format == "csv":
        stream = io.StringIO(newline=""); writer = csv.writer(stream)
        writer.writerow(["source_path", "source_sha256", "location", "text"])
        def cell(value):
            value = str(value)
            return "'" + value if value.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")) else value
        for record in records:
            for segment in record["segments"]:
                writer.writerow([cell(record["source"]["path"]), record["source"]["sha256"], cell(json.dumps(segment["location"])), cell(segment["text"])])
        payload = stream.getvalue().encode("utf-8-sig")
    else:
        raise DocumentError("INVALID_EXPORT_FORMAT")
    if len(payload) > limits.max_bytes:
        raise DocumentError("OUTPUT_BYTE_LIMIT")
    # O_EXCL prevents an existing artifact being overwritten by a competing writer.
    with destination.open("xb") as output:
        output.write(payload); output.flush(); os.fsync(output.fileno())
    observed = destination.read_bytes()
    if observed != payload:
        raise DocumentError("OUTPUT_READBACK_FAILED")
    return {"path": str(destination), "sha256": digest(observed), "bytes": len(observed), "effect": "CREATED"}


def execute(operation, root, arguments=None, *, limits=None):
    """Execute one bounded operation, reporting per-file failures and source identities.

    Input corpus selection belongs to the caller. This API grants no ADL permissions.
    Extraction records can be resumed only after their source hashes are checked.
    """
    limits = limits or Limits()
    args = arguments if isinstance(arguments, dict) else {} if arguments is None else None
    result = {"schema": SCHEMA, "version": "0.2.0", "operation": operation, "run_id": uuid.uuid4().hex,
              "state": "FAILED", "limits": asdict(limits), "records": [], "errors": [], "truncated": False,
              "source_writes": False, "capability_validation": "NOT_IMPLIED"}
    started = time.monotonic()
    try:
        if args is None or operation not in OPERATIONS:
            raise DocumentError("INVALID_OPERATION_OR_ARGUMENTS")
        bound = _root(root)
        if operation in ("inventory", "extract"):
            paths = _paths(bound, args.get("paths"), limits, started, result["errors"])
            prior = {}
            if args.get("resume") is not None:
                prior = {r["source"]["path"]: r for r in _verify_bundle(bound, args["resume"], limits)}
            total, chars = 0, 0
            for relative in paths:
                if time.monotonic()-started >= limits.max_seconds:
                    result["errors"].append({"path": relative, "code": "TIME_LIMIT"}); break
                try:
                    if total >= limits.max_bytes:
                        raise DocumentError("TOTAL_BYTE_LIMIT")
                    data = stable_read(bound, relative, min(limits.max_file_bytes, limits.max_bytes-total))
                    total += len(data)
                    source = _source(relative, data)
                    if operation == "inventory":
                        record = {"source": source}
                    elif relative in prior:
                        record = prior[relative]
                    else:
                        parsed = _parse_isolated(data, source["format"], limits, limits.max_seconds-(time.monotonic()-started))
                        record = {"source": source, **parsed}
                    if operation == "extract":
                        size = sum(len(s["text"]) for s in record["segments"])
                        if chars + size > limits.max_chars:
                            raise DocumentError("TOTAL_CHARACTER_LIMIT")
                        chars += size
                    result["records"].append(record)
                except (OSError, ValueError) as error:
                    result["errors"].append({"path": relative, "code": getattr(error, "code", "READ_OR_FORMAT_ERROR")})
            result["coverage"] = {"selected": len(paths), "completed": len(result["records"]), "bytes_read": total}
        elif operation in ("relate", "export"):
            records = _verify_bundle(bound, args.get("bundle"), limits)
            if operation == "relate":
                facts, links, truncated = _relations(records, limits)
                result.update(facts=facts, relations=links, truncated=truncated, conclusions_confirmed=False)
            else:
                result["output"] = _export(bound, records, args, limits)
        elif operation == "plan-rename":
            result["plan"] = _rename_plan(bound, args.get("entries"), limits)
        result["truncated"] |= any(r.get("truncated", False) for r in result["records"]) or any(e["code"].endswith("LIMIT") for e in result["errors"])
        result["state"] = "PARTIAL" if result["errors"] or result["truncated"] else "EXECUTED"
        if result["errors"] and not result["records"]:
            result["state"] = "FAILED"
    except (OSError, ValueError, TypeError, KeyError) as error:
        result["errors"].append({"path": None, "code": getattr(error, "code", "INVALID_REQUEST")})
    result["bundle_sha256"] = digest(canonical(result["records"]))
    result["elapsed_seconds"] = round(time.monotonic()-started, 4)
    return result
