#!/usr/bin/env python3
"""Build a single-root installer ZIP with the package and BAGO source archive."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path, PurePosixPath
from zipfile import ZIP_DEFLATED, BadZipFile, ZipFile

from verify_package import sha256, verify


ROOT_NAME = "BAGO_APP_GAME_DEVELOPMENT/"
SOURCE_DIR = ROOT_NAME + "BAGO_BEHAVIOR_SOURCE/"
CONTENTS_MANIFEST = ROOT_NAME + "CONTENTS_MANIFEST.json"
SOURCE_MANIFEST = SOURCE_DIR + "SOURCE_MANIFEST.json"
PACKAGE_SOURCE_PREFIX = "BAGO_APP_GAME_PACKAGE/"
OLD_DISTRIBUTION_MANIFEST = "BAGO_PACKAGE_MANIFEST.json"


def safe_path(name: str) -> bool:
    path = PurePosixPath(name)
    return bool(name) and not path.is_absolute() and ".." not in path.parts and "\\" not in name


def add_file(members: dict[str, bytes], path: str, data: bytes) -> None:
    if not safe_path(path):
        raise ValueError(f"unsafe archive path: {path}")
    if path in members:
        raise ValueError(f"duplicate archive path: {path}")
    members[path] = data


def build(behavior_archive: Path, package_root: Path, output: Path) -> dict[str, object]:
    behavior_archive = behavior_archive.resolve(strict=True)
    package_root = package_root.resolve(strict=True)
    package_errors = verify(package_root)
    if package_errors:
        raise ValueError("package verification failed: " + "; ".join(package_errors))

    members: dict[str, bytes] = {}
    for path in sorted(package_root.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        relative = path.relative_to(package_root).as_posix()
        add_file(members, ROOT_NAME + "package/" + relative, path.read_bytes())

    # Root installer/documentation are distribution adapters, not package payload.
    add_file(members, ROOT_NAME + "install.ps1", (package_root / "install.ps1").read_bytes())
    add_file(members, ROOT_NAME + "README.md", (package_root / "DISTRIBUTION_README.md").read_bytes())

    source_files: list[dict[str, str]] = []
    with ZipFile(behavior_archive, "r") as source:
        bad = source.testzip()
        if bad:
            raise BadZipFile(f"behavior archive failed CRC at {bad}")
        for item in source.infolist():
            name = item.filename
            if item.is_dir() or name == OLD_DISTRIBUTION_MANIFEST or name.startswith(PACKAGE_SOURCE_PREFIX):
                continue
            if not safe_path(name):
                raise ValueError(f"unsafe behavior source path: {name}")
            data = source.read(item)
            relative = PurePosixPath(name).as_posix()
            member = SOURCE_DIR + relative
            add_file(members, member, data)
            source_files.append({"source_path": relative, "archive_path": member, "sha256": hashlib.sha256(data).hexdigest()})

    source_manifest = {
        "schema": "bago.behavior_sources.v1",
        "source_archive_sha256": sha256(behavior_archive),
        "files": sorted(source_files, key=lambda entry: entry["source_path"]),
    }
    add_file(members, SOURCE_MANIFEST, (json.dumps(source_manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    contents_manifest = {
        "schema": "bago.app_game_installer_distribution.v1",
        "source_archive_sha256": sha256(behavior_archive),
        "package_manifest_sha256": sha256(package_root / "manifest.json"),
        "entry_count": len(members),
        "files": [
            {"path": name, "sha256": hashlib.sha256(data).hexdigest()}
            for name, data in sorted(members.items())
        ],
    }
    add_file(members, CONTENTS_MANIFEST, (json.dumps(contents_manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"))

    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix="bago-installer-", suffix=".zip", dir=output.parent)
    os.close(fd)
    temporary = Path(temporary_name)
    try:
        with ZipFile(temporary, "w", ZIP_DEFLATED) as archive:
            for name, data in sorted(members.items()):
                archive.writestr(name, data, compress_type=ZIP_DEFLATED)
        with ZipFile(temporary, "r") as archive:
            bad = archive.testzip()
            if bad:
                raise BadZipFile(f"built installer archive failed CRC at {bad}")
            actual_names = set(archive.namelist())
            if any(not name.startswith(ROOT_NAME) for name in actual_names):
                raise ValueError("distribution has entries outside its single root directory")
        os.replace(temporary, output)
    finally:
        if temporary.exists():
            temporary.unlink()

    return {
        "ok": True,
        "output": str(output),
        "entries": len(members),
        "behavior_source_files": len(source_files),
        "sha256": sha256(output),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--behavior-archive", required=True, type=Path)
    parser.add_argument("--package-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = build(args.behavior_archive, args.package_root, args.output)
    except (OSError, ValueError, BadZipFile) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
