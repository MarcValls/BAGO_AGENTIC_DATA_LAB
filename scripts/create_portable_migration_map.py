"""Create a filename-only, allowlisted migration map for legacy ADL stores.

The command never reads file contents and never chooses an arbitrary tree.
Its output contains absolute source paths and portable relative targets; review
that map before passing it to ``migrate_portable_data.py``.
"""
from __future__ import annotations

import argparse
import json
import os
import stat
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.migrate_portable_data import MigrationError, _reject_reparse, _target_parts


FIXED_APPDATA = {
    "active-provider.json": ("providers/active-provider.json", "file"),
    "provider-registry.json": ("providers/provider-registry.json", "file"),
    "model-policy.json": ("providers/model-policy.json", "file"),
    "workspace.json": ("config/workspace.json", "file"),
    "project-folders-v1/registry.json": ("config/project-folders-v1/registry.json", "file"),
    "contacts/contacts.sqlite3": ("contacts/contacts.sqlite3", "sqlite"),
    "communications/communications.sqlite3": ("communications/communications.sqlite3", "sqlite"),
    "conversations/library.sqlite3": ("conversations/library.sqlite3", "sqlite"),
    "gex/identity.sqlite3": ("gex/identity.sqlite3", "sqlite"),
    "knowledge/local-knowledge.sqlite3": ("knowledge/local-knowledge.sqlite3", "sqlite"),
}
PATTERNS_APPDATA = (
    ("capabilities/*/capabilities.sqlite3", "capabilities/{relative}", "sqlite", False),
    ("evaluations/*/evaluation.sqlite3", "evaluations/{relative}", "sqlite", False),
    ("evaluations/*/traces/*.json", "evaluations/{relative}", "file", False),
    ("tasks/*/history.sqlite3", "tasks/{relative}", "sqlite", False),
    ("gex/runtime/**/*.json", "gex/runtime/{relative}", "file", False),
    ("gex/runtime/**/*.sqlite3", "gex/runtime/{relative}", "sqlite", False),
    ("gex/runtime/**/*.db", "gex/runtime/{relative}", "sqlite", False),
    ("web-research/**/*.json", "web-research/{relative}", "file", False),
    ("document-exports/**/*", "document-exports/{relative}", "file", False),
    ("whatsapp/**/*", "whatsapp/{relative}", "file", True),
)
APP_ROOT_FILES = {
    "l2_etl_metadata.db": ("etl/metadata.sqlite3", "sqlite"),
    ".bago/knowledge/ontology.sqlite3": ("knowledge/ontology.sqlite3", "sqlite"),
}
APP_ROOT_PATTERNS = (
    ("agents/created/**/*.json", "agents/created/{relative}", "file"),
    (".bago/traces/agent-chat/**/*.json", "traces/agent-chat/{relative}", "file"),
    (".bago/traces/workspace-scans/**/*.json", "traces/workspace-scans/{relative}", "file"),
    (".bago/traces/mcp-governance/**/*.json", "traces/mcp-governance/{relative}", "file"),
    (".bago/traces/ontology/**/*.json", "traces/ontology/{relative}", "file"),
    (".bago/traces/grounded-rag/**/*.json", "traces/grounded-rag/{relative}", "file"),
    (".bago/runtime/connections/registry.json", "connections/registry.json", "file"),
    (".bago/traces/external-connections/**/*.json", "traces/external-connections/{relative}", "file"),
    ("jobs/history/*.json", "jobs/history/{relative}", "file"),
)
SKIP_NAMES = {"lock", "worker.lock", "-wal", "-shm"}


def _regular_files(root: Path, pattern: str) -> list[Path]:
    base = root.resolve(strict=True)
    matches: list[Path] = []
    for candidate in base.glob(pattern):
        _reject_reparse(candidate)
        try:
            info = candidate.lstat()
        except OSError as error:
            raise MigrationError("source_inspection_failed") from error
        if not stat.S_ISREG(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            continue
        if candidate.name.casefold() in SKIP_NAMES or candidate.name.endswith(("-wal", "-shm", ".tmp")):
            continue
        matches.append(candidate.resolve(strict=True))
    return sorted(matches, key=lambda item: item.relative_to(base).as_posix().casefold())


def _append(entries: list[dict], source: Path, target: str, kind: str, private: bool = False) -> None:
    _target_parts(target)
    entries.append({"source": str(source), "target": target.replace("\\", "/"), "kind": kind,
                    **({"private_owned": True} if private else {})})


def build_map(app_data_root: Path, application_root: Path, *, include_whatsapp: bool = False) -> dict:
    for root in (app_data_root, application_root):
        if not root.is_absolute():
            raise MigrationError("source_root_must_be_absolute")
    if not application_root.is_dir():
        raise MigrationError("application_root_unavailable")
    app_data_available = app_data_root.is_dir()
    if app_data_root.exists() and not app_data_available:
        raise MigrationError("source_root_unavailable")
    _reject_reparse(application_root)
    if app_data_available:
        _reject_reparse(app_data_root)
    entries: list[dict] = []
    if app_data_available:
        for relative, (target, kind) in FIXED_APPDATA.items():
            path = app_data_root / Path(relative)
            if path.exists():
                _reject_reparse(path)
                if not path.is_file():
                    raise MigrationError("source_file_type_denied")
                _append(entries, path.resolve(strict=True), target, kind)
        for pattern, target_template, kind, private in PATTERNS_APPDATA:
            if private and not include_whatsapp:
                continue
            for path in _regular_files(app_data_root, pattern):
                relative = path.relative_to(app_data_root.resolve(strict=True)).as_posix()
                # Preserve workspace IDs, evaluation traces and nested report paths.
                if pattern.startswith("capabilities/"):
                    suffix = relative.removeprefix("capabilities/")
                elif pattern.startswith("evaluations/"):
                    suffix = relative.removeprefix("evaluations/")
                elif pattern.startswith("tasks/"):
                    suffix = relative.removeprefix("tasks/")
                elif pattern.startswith("gex/runtime/"):
                    suffix = relative.removeprefix("gex/runtime/")
                elif pattern.startswith("web-research/"):
                    suffix = relative.removeprefix("web-research/")
                elif pattern.startswith("document-exports/"):
                    suffix = relative.removeprefix("document-exports/")
                else:
                    suffix = relative.removeprefix("whatsapp/")
                _append(entries, path, target_template.format(relative=suffix), kind, private)
    for relative, (target, kind) in APP_ROOT_FILES.items():
        path = application_root / Path(relative)
        if path.exists():
            _reject_reparse(path)
            if not path.is_file():
                raise MigrationError("source_file_type_denied")
            _append(entries, path.resolve(strict=True), target, kind)
    for pattern, target_template, kind in APP_ROOT_PATTERNS:
        for path in _regular_files(application_root, pattern):
            if pattern.startswith("agents/"):
                prefix = "agents/created/"
            elif pattern.startswith("jobs/"):
                prefix = "jobs/history/"
            elif pattern.startswith(".bago/runtime/connections/"):
                prefix = ".bago/runtime/connections/"
            elif pattern.startswith(".bago/traces/external-connections/"):
                prefix = ".bago/traces/external-connections/"
            else:
                prefix = pattern.split("**", 1)[0]
            relative = path.relative_to(application_root.resolve(strict=True)).as_posix()
            suffix = relative.removeprefix(prefix).lstrip("/")
            if "{relative}" in target_template:
                _append(entries, path, target_template.format(relative=suffix), kind)
            else:
                _append(entries, path, target_template, kind)
    targets = [entry["target"].casefold() for entry in entries]
    if len(targets) != len(set(targets)):
        raise MigrationError("target_collision")
    return {"version": 1, "entries": entries,
            "scope": "allowlisted ADL-owned files only; source contents are not read",
            "whatsapp_session_included": include_whatsapp,
            "excluded": ["OS credential keyring", "transient locks", "SQLite WAL/SHM sidecars",
                         "browser executable/profile outside the ADL-owned whatsapp directory"]}


def build_existing_portable_map(source_data_root: Path, *, include_whatsapp: bool = False) -> dict:
    """Map the complete legacy portable data tree, excluding transient locks.

    WhatsApp session files are listed only on explicit opt-in and are marked
    private_owned so the migration plan/apply command requires the same opt-in.
    """
    if not source_data_root.is_absolute():
        raise MigrationError("source_root_must_be_absolute")
    _reject_reparse(source_data_root)
    root = source_data_root.resolve(strict=True)
    if not root.is_dir():
        raise MigrationError("source_root_unavailable")
    entries: list[dict] = []
    for path in _regular_files(root, "**/*"):
        relative = path.relative_to(root).as_posix()
        parts = relative.split("/")
        if any(part.casefold() in {"cache", "code cache", "gpucache", "shadercache", "grshadercache", "dawnwebgpu", "crashpad"} for part in parts):
            continue
        private = parts[0].casefold() == "whatsapp"
        if private and not include_whatsapp:
            continue
        suffix = path.suffix.casefold()
        kind = "sqlite" if suffix in {".db", ".sqlite", ".sqlite3"} else "file"
        _append(entries, path, relative, kind, private)
    return {"version": 1, "entries": entries,
            "scope": "complete existing portable data tree excluding transient/cache files; contents are not read",
            "whatsapp_session_included": include_whatsapp,
            "excluded": ["SQLite WAL/SHM sidecars", "transient locks", "browser caches", "OS credential keyring"]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app-data-root", type=Path, default=None)
    parser.add_argument("--application-root", type=Path, default=None)
    parser.add_argument("--portable-data-root", type=Path, default=None,
                        help="map an existing .bago/data tree in full instead of scanning legacy roots")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--include-whatsapp-session", action="store_true",
                        help="list the ADL-owned WhatsApp session files as private_owned; apply still requires separate opt-in")
    args = parser.parse_args(argv)
    try:
        if args.portable_data_root:
            result = build_existing_portable_map(args.portable_data_root.expanduser().absolute(),
                                                 include_whatsapp=args.include_whatsapp_session)
        else:
            if args.application_root is None:
                parser.error("--application-root is required unless --portable-data-root is used")
            app_data = args.app_data_root or Path(os.environ.get("LOCALAPPDATA", Path.home())) / "BAGO" / "AgenticDataLab"
            result = build_map(app_data.expanduser().absolute(), args.application_root.expanduser().absolute(),
                               include_whatsapp=args.include_whatsapp_session)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        print(json.dumps({"status": "PREPARED", "entry_count": len(result["entries"]),
                          "whatsapp_session_included": result["whatsapp_session_included"]}, sort_keys=True))
        return 0
    except (MigrationError, OSError, ValueError) as error:
        print(json.dumps({"status": "DENIED", "code": str(error)}, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
