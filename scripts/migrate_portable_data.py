"""Plan and safely migrate explicitly enumerated ADL-owned portable stores.

No source is discovered automatically. Originals are never edited or removed.
The tool is not a sandbox and requires the owning runtime to be quiescent.
Failed staging directories are retained and their unique names are reported.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import hashlib
import json
import os
import re
import shutil
import struct
import sqlite3
import stat
import sys
import uuid
from pathlib import Path
from typing import Any

MAX_ENTRIES = 100_000
MAX_MAPPING_BYTES = 128 * 1024 * 1024
MAX_TOTAL_BYTES = 5 * 1024 * 1024 * 1024
MAX_FILE_BYTES = 2 * 1024 * 1024 * 1024
PRIVATE_NAME = re.compile(r"(?i)(^\.env(?:\.|$)|credential|secret|password|private.?key|token|auth)")
BLOCKED_COMPONENTS = frozenset({
    ".codex", ".mozilla", "browser", "browsers", "google", "mozillaprofiles",
    "bravesoftware", "brave-browser", "chrome", "chromium", "firefox", "edge",
})
_RESERVED = re.compile(r"(?i)^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?$")


class MigrationError(ValueError):
    pass


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _reject_reparse(path: Path) -> None:
    absolute = Path(os.path.abspath(os.fspath(path)))
    for current in reversed((absolute, *absolute.parents)):
        try:
            info = current.lstat()
        except FileNotFoundError:
            continue
        except OSError as error:
            raise MigrationError("source_or_destination_inspection_failed") from error
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise MigrationError("reparse_path_denied")


def _target_parts(value: Any) -> tuple[str, ...]:
    if not isinstance(value, str) or not value or value.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", value):
        raise MigrationError("invalid_target")
    parts = tuple(value.replace("\\", "/").split("/"))
    for part in parts:
        if (not part or part in {".", ".."} or part != part.rstrip(" .") or ":" in part
                or any(ord(char) < 32 or char in '<>"|?*' for char in part) or _RESERVED.fullmatch(part)):
            raise MigrationError("invalid_target")
    return parts


def _sqlite_facts(path: Path) -> tuple[dict[str, int], str]:
    uri = path.as_uri() + "?mode=ro"
    try:
        with closing(sqlite3.connect(uri, uri=True, timeout=10)) as db:
            result = db.execute("PRAGMA integrity_check").fetchone()
            if not result or result[0] != "ok":
                raise MigrationError("sqlite_integrity_check_failed")
            tables = [row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
            if len(tables) > 10000:
                raise MigrationError("sqlite_table_limit_exceeded")
            rows: dict[str, int] = {}
            logical = hashlib.sha256()
            for name in sorted(tables):
                quoted_table = '"' + name.replace('"', '""') + '"'
                schema = db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone()
                logical.update(name.encode("utf-8")); logical.update(b"\x00")
                logical.update((schema[0] or "").encode("utf-8")); logical.update(b"\x00")
                columns = [item[1] for item in db.execute(f"PRAGMA table_info({quoted_table})")]
                if not columns:
                    rows[name] = 0
                    continue
                try:
                    cursor = db.execute(f"SELECT * FROM {quoted_table} ORDER BY rowid")
                except sqlite3.Error:
                    quoted_columns = ",".join('"' + column.replace('"', '""') + '"' for column in columns)
                    cursor = db.execute(f"SELECT * FROM {quoted_table} ORDER BY {quoted_columns}")
                count = 0
                for row in cursor:
                    count += 1
                    logical.update(struct.pack(">I", len(row)))
                    for value in row:
                        if value is None:
                            logical.update(b"N")
                        elif isinstance(value, bytes):
                            logical.update(b"B" + struct.pack(">Q", len(value)) + value)
                        elif isinstance(value, str):
                            encoded = value.encode("utf-8")
                            logical.update(b"S" + struct.pack(">Q", len(encoded)) + encoded)
                        elif isinstance(value, int):
                            encoded = str(value).encode("ascii")
                            logical.update(b"I" + struct.pack(">Q", len(encoded)) + encoded)
                        else:
                            encoded = repr(value).encode("ascii")
                            logical.update(b"F" + struct.pack(">Q", len(encoded)) + encoded)
                rows[name] = count
            return rows, logical.hexdigest()
    except sqlite3.Error as error:
        raise MigrationError("sqlite_read_failed") from error


def _read_mapping(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    try:
        if path.stat().st_size > MAX_MAPPING_BYTES:
            raise MigrationError("mapping_size_limit")
        raw = json.loads(path.read_text(encoding="utf-8"))
    except MigrationError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise MigrationError("mapping_invalid") from error
    if not isinstance(raw, dict) or set(raw) != {"version", "entries"} or raw.get("version") != 1:
        raise MigrationError("mapping_invalid")
    entries = raw.get("entries")
    if not isinstance(entries, list) or not 1 <= len(entries) <= MAX_ENTRIES:
        raise MigrationError("mapping_entry_limit")
    return raw, entries


def _private_roots(values: list[Path] | tuple[Path, ...]) -> tuple[Path, ...]:
    if len(values) > 20:
        raise MigrationError("private_root_limit")
    roots: list[Path] = []
    for raw in values:
        if not raw.is_absolute():
            raise MigrationError("private_root_must_be_absolute")
        _reject_reparse(raw)
        try:
            root = raw.resolve(strict=True)
        except (OSError, RuntimeError) as error:
            raise MigrationError("private_root_unavailable") from error
        if not root.is_dir() or _forbidden_general_state(root):
            raise MigrationError("private_root_not_owned_state")
        if root not in roots:
            roots.append(root)
    return tuple(roots)


def _forbidden_general_state(path: Path) -> bool:
    return any(part.casefold() in BLOCKED_COMPONENTS for part in path.parts)


def _private_allowed(source: Path, private_owned: bool, include_private_owned: bool,
                     private_roots: tuple[Path, ...]) -> None:
    if _forbidden_general_state(source):
        raise MigrationError("general_browser_or_codex_state_denied")
    requires_opt_in = any(PRIVATE_NAME.search(part) for part in source.parts)
    if not private_owned:
        if requires_opt_in:
            raise MigrationError("private_file_requires_explicit_approval")
        return
    if not include_private_owned:
        raise MigrationError("private_file_opt_in_required")
    if not any(source == root or root in source.parents for root in private_roots):
        raise MigrationError("private_file_outside_owned_root")


def _preflight(mapping_path: Path, destination: Path, *, include_private_owned: bool = False,
               private_owned_roots: tuple[Path, ...] = ()) -> dict[str, Any]:
    _reject_reparse(mapping_path)
    _reject_reparse(destination)
    if not destination.is_absolute():
        destination = (Path.cwd() / destination).absolute()
    destination = Path(os.path.abspath(destination))
    destination_existed = destination.exists()
    if destination_existed and not destination.is_dir():
        raise MigrationError("destination_not_directory")
    if not destination.parent.is_dir():
        raise MigrationError("destination_parent_unavailable")
    _, raw_entries = _read_mapping(mapping_path)
    entries: list[dict[str, Any]] = []
    targets: set[tuple[str, ...]] = set()
    implicit_directories: set[tuple[str, ...]] = set()
    total = 0
    for raw in raw_entries:
        if not isinstance(raw, dict) or set(raw) not in ({"source", "target", "kind"}, {"source", "target", "kind", "private_owned"}):
            raise MigrationError("mapping_entry_invalid")
        source_text, kind = raw["source"], raw["kind"]
        private_owned = raw.get("private_owned", False)
        if not isinstance(source_text, str) or kind not in {"file", "sqlite"} or type(private_owned) is not bool:
            raise MigrationError("mapping_entry_invalid")
        source_raw = Path(source_text).expanduser()
        if not source_raw.is_absolute():
            raise MigrationError("source_must_be_absolute")
        _reject_reparse(source_raw)
        try:
            source = source_raw.resolve(strict=True)
            info = source.lstat()
        except (OSError, RuntimeError) as error:
            raise MigrationError("source_unavailable") from error
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or getattr(info, "st_file_attributes", 0) & 0x400:
            raise MigrationError("source_file_type_denied")
        _private_allowed(source, private_owned, include_private_owned, private_owned_roots)
        if info.st_size > MAX_FILE_BYTES:
            raise MigrationError("file_size_limit")
        total += info.st_size
        if total > MAX_TOTAL_BYTES:
            raise MigrationError("total_size_limit")
        parts = _target_parts(raw["target"])
        folded = tuple(part.casefold() for part in parts)
        has_file_ancestor = any(folded[:index] in targets for index in range(1, len(folded)))
        if folded in targets or folded in implicit_directories or has_file_ancestor:
            raise MigrationError("target_collision")
        targets.add(folded)
        implicit_directories.update(folded[:index] for index in range(1, len(folded)))
        facts, logical_sha256 = _sqlite_facts(source) if kind == "sqlite" else (None, None)
        existing_target = destination.joinpath(*parts)
        _reject_reparse(existing_target)
        target_state = "missing"
        if existing_target.exists():
            if not existing_target.is_file():
                raise MigrationError("target_conflict")
            if kind == "sqlite":
                existing_rows, existing_logical_sha256 = _sqlite_facts(existing_target)
                identical = (existing_rows == facts and existing_logical_sha256 == logical_sha256)
            else:
                identical = _hash_file(existing_target) == _hash_file(source)
            if not identical:
                raise MigrationError("target_conflict")
            target_state = "identical"
        entries.append({"source": str(source), "target": "/".join(parts), "kind": kind, "private_owned": private_owned,
                        "size_bytes": info.st_size, "source_sha256": _hash_file(source),
                        "table_rows": facts, "sqlite_logical_sha256": logical_sha256,
                        "target_state": target_state})
    return {"version": 1, "destination": str(destination), "entries": entries,
            "total_source_bytes": total, "private_owned_roots": [str(path) for path in private_owned_roots],
            "private_files_authorized": include_private_owned, "runtime_quiescence_required": True,
            "destination_existed": destination_existed}


def _plan_digest(plan: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical(plan)).hexdigest()


def inventory(mapping_path: Path, *, include_private_owned: bool = False,
              private_owned_roots: tuple[Path, ...] = ()) -> dict[str, Any]:
    _, entries = _read_mapping(mapping_path)
    private_owned_roots = _private_roots(private_owned_roots)
    result = []
    for raw in entries:
        if not isinstance(raw, dict) or set(raw) not in ({"source", "target", "kind"}, {"source", "target", "kind", "private_owned"}):
            raise MigrationError("mapping_entry_invalid")
        source = Path(raw["source"]).expanduser()
        _reject_reparse(source)
        if not source.is_absolute() or not source.is_file() or source.is_symlink():
            raise MigrationError("source_unavailable")
        private_owned = raw.get("private_owned", False)
        if type(private_owned) is not bool:
            raise MigrationError("mapping_entry_invalid")
        _private_allowed(source, private_owned, include_private_owned, private_owned_roots)
        result.append({"source_name": source.name, "target": "/".join(_target_parts(raw["target"])),
                       "kind": raw["kind"], "size_bytes": source.stat().st_size,
                       "private_owned": private_owned})
    return {"version": 1, "count": len(result), "entries": result}


def create_plan(mapping_path: Path, destination: Path, output: Path, *, include_private_owned: bool = False,
                private_owned_roots: tuple[Path, ...] = ()) -> dict[str, Any]:
    private_owned_roots = _private_roots(private_owned_roots)
    plan = _preflight(mapping_path, destination, include_private_owned=include_private_owned,
                      private_owned_roots=private_owned_roots)
    digest = _plan_digest(plan)
    saved = {**plan, "plan_sha256": digest}
    output = output.expanduser().absolute()
    _reject_reparse(output)
    if output.exists():
        raise MigrationError("plan_destination_exists")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + ".tmp-" + uuid.uuid4().hex)
    temporary.write_bytes(_canonical(saved) + b"\n")
    os.replace(temporary, output)
    return {"plan_sha256": digest, "entry_count": len(plan["entries"]), "total_source_bytes": plan["total_source_bytes"],
            "private_file_count": sum(1 for item in plan["entries"] if item["private_owned"])}


def apply_plan(plan_path: Path, *, include_private_owned: bool = False,
               private_owned_roots: tuple[Path, ...] = ()) -> dict[str, Any]:
    private_owned_roots = _private_roots(private_owned_roots)
    _reject_reparse(plan_path)
    try:
        saved = json.loads(plan_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise MigrationError("plan_invalid") from error
    if not isinstance(saved, dict) or "plan_sha256" not in saved:
        raise MigrationError("plan_invalid")
    expected = saved.pop("plan_sha256")
    if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected) or _plan_digest(saved) != expected:
        raise MigrationError("plan_digest_mismatch")
    destination = Path(saved.get("destination", ""))
    recorded_roots = saved.get("private_owned_roots")
    if not isinstance(recorded_roots, list) or not all(isinstance(item, str) for item in recorded_roots):
        raise MigrationError("plan_invalid")
    if recorded_roots != [str(path) for path in private_owned_roots]:
        raise MigrationError("private_root_approval_mismatch")
    if saved.get("private_files_authorized") is not include_private_owned:
        raise MigrationError("private_file_approval_mismatch")
    # Revalidate every source, target and destination before creating the staging root.
    entries = saved.get("entries")
    if not isinstance(entries, list) or not 1 <= len(entries) <= MAX_ENTRIES:
        raise MigrationError("plan_invalid")
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"source", "target", "kind", "private_owned", "size_bytes", "source_sha256", "table_rows", "sqlite_logical_sha256", "target_state"}:
            raise MigrationError("plan_invalid")
    mapping_temp = {"version": 1, "entries": [{"source": item["source"], "target": item["target"], "kind": item["kind"],
        "private_owned": item["private_owned"]} for item in entries]}
    # Validation operates on a temporary mapping file adjacent to the plan, then removes only that exact file.
    validate_path = plan_path.with_name(".portable-validate-" + uuid.uuid4().hex + ".json")
    try:
        validate_path.write_bytes(_canonical(mapping_temp))
        fresh = _preflight(validate_path, destination, include_private_owned=include_private_owned,
                           private_owned_roots=private_owned_roots)
    finally:
        validate_path.unlink(missing_ok=True)
    if len(fresh["entries"]) != len(entries):
        raise MigrationError("plan_changed")
    for old, new in zip(entries, fresh["entries"]):
        if any(old[key] != new[key] for key in ("source", "target", "kind", "private_owned", "size_bytes", "source_sha256", "table_rows", "sqlite_logical_sha256", "target_state")):
            raise MigrationError("plan_changed")
    if saved.get("destination_existed") is not fresh.get("destination_existed"):
        raise MigrationError("plan_changed")
    stage = destination.with_name("." + destination.name + ".portable-stage-" + uuid.uuid4().hex)
    stage.mkdir(parents=False, exist_ok=False)
    try:
        copied = []
        for item in entries:
            if item["target_state"] == "identical":
                copied.append({"target": item["target"], "kind": item["kind"], "size_bytes": item["size_bytes"],
                               "already_present": True, "table_rows": item["table_rows"],
                               "sqlite_logical_sha256": item["sqlite_logical_sha256"]})
                continue
            source = Path(item["source"])
            target = stage.joinpath(*_target_parts(item["target"]))
            target.parent.mkdir(parents=True, exist_ok=True)
            if item["kind"] == "sqlite":
                source_db = sqlite3.connect(source.as_uri() + "?mode=ro", uri=True, timeout=10)
                target_db = sqlite3.connect(target, timeout=10)
                try:
                    source_db.backup(target_db)
                    integrity = target_db.execute("PRAGMA integrity_check").fetchone()
                    copied_rows, copied_logical_sha256 = _sqlite_facts(target)
                    if (not integrity or integrity[0] != "ok" or copied_rows != item["table_rows"]
                            or copied_logical_sha256 != item["sqlite_logical_sha256"]):
                        raise MigrationError("sqlite_copy_verification_failed")
                finally:
                    target_db.close()
                    source_db.close()
            else:
                shutil.copyfile(source, target)
                if _hash_file(target) != item["source_sha256"]:
                    raise MigrationError("file_copy_verification_failed")
            copied.append({"target": item["target"], "kind": item["kind"], "size_bytes": target.stat().st_size,
                           "already_present": False,
                           "sha256": _hash_file(target) if item["kind"] == "file" else None,
                           "table_rows": item["table_rows"],
                           "sqlite_logical_sha256": item["sqlite_logical_sha256"]})
        if not saved.get("destination_existed"):
            # Atomic promotion fails if another process created the destination meanwhile.
            os.rename(stage, destination)
        else:
            # Merge only into missing paths. Hard-link promotion is atomic and
            # refuses to overwrite an entry created after preflight.
            for item in entries:
                if item["target_state"] == "identical":
                    continue
                parts = _target_parts(item["target"])
                staged_file = stage.joinpath(*parts)
                final_file = destination.joinpath(*parts)
                final_file.parent.mkdir(parents=True, exist_ok=True)
                _reject_reparse(final_file)
                if final_file.exists():
                    raise MigrationError("target_appeared_after_preflight")
                os.link(staged_file, final_file)
            shutil.rmtree(stage)
    except Exception as error:
        code = str(error) if isinstance(error, MigrationError) else "copy_failed"
        raise MigrationError(f"migration_stage_retained:{stage.name}:{code}") from None
    return {"status": "APPLIED", "destination": str(destination), "plan_sha256": expected,
            "entry_count": len(copied), "private_file_count": sum(1 for item in entries if item["private_owned"]),
            "new_entry_count": sum(1 for item in copied if not item["already_present"]),
            "already_present_count": sum(1 for item in copied if item["already_present"]), "entries": copied}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    inv = sub.add_parser("inventory")
    inv.add_argument("--mapping", required=True, type=Path)
    inv.add_argument("--include-private-owned", action="store_true")
    inv.add_argument("--private-owned-root", action="append", default=[], type=Path)
    plan = sub.add_parser("plan")
    plan.add_argument("--mapping", required=True, type=Path)
    plan.add_argument("--destination", required=True, type=Path)
    plan.add_argument("--output", required=True, type=Path)
    plan.add_argument("--include-private-owned", action="store_true")
    plan.add_argument("--private-owned-root", action="append", default=[], type=Path)
    apply = sub.add_parser("apply")
    apply.add_argument("--plan", required=True, type=Path)
    apply.add_argument("--include-private-owned", action="store_true")
    apply.add_argument("--private-owned-root", action="append", default=[], type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "inventory":
            result = inventory(args.mapping, include_private_owned=args.include_private_owned,
                               private_owned_roots=tuple(args.private_owned_root))
        elif args.command == "plan":
            result = create_plan(args.mapping, args.destination, args.output,
                                 include_private_owned=args.include_private_owned,
                                 private_owned_roots=tuple(args.private_owned_root))
        else:
            result = apply_plan(args.plan, include_private_owned=args.include_private_owned,
                                private_owned_roots=tuple(args.private_owned_root))
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except MigrationError as error:
        print(json.dumps({"status": "DENIED", "code": str(error)}, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
