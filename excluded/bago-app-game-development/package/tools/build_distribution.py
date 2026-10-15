#!/usr/bin/env python3
"""Merge the app/game package into a prior BAGO behavior ZIP, preserving paths."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path, PurePosixPath
from zipfile import ZIP_DEFLATED, BadZipFile, ZipFile

from verify_package import sha256, verify

PACKAGE_PREFIX = "BAGO_APP_GAME_PACKAGE/"
DIST_MANIFEST = "BAGO_PACKAGE_MANIFEST.json"


def safe_member(name: str) -> bool:
    path = PurePosixPath(name)
    return not path.is_absolute() and ".." not in path.parts and "" not in path.parts


def build(base_archive: Path, package_root: Path, output: Path) -> dict:
    base_archive = base_archive.resolve(strict=True)
    package_root = package_root.resolve(strict=True)
    errors = verify(package_root)
    if errors:
        raise ValueError("package verification failed: " + "; ".join(errors))
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    base_hash = sha256(base_archive)
    previous_distribution_hash = None
    with ZipFile(base_archive, "r") as source:
        bad = source.testzip()
        if bad:
            raise BadZipFile(f"base archive failed CRC at {bad}")
        if DIST_MANIFEST in source.namelist():
            try:
                previous = json.loads(source.read(DIST_MANIFEST).decode("utf-8"))
                if previous.get("schema") == "bago.behavior_distribution.v1":
                    previous_distribution_hash = base_hash
                    base_hash = previous.get("base_archive_sha256", base_hash)
            except (UnicodeDecodeError, json.JSONDecodeError):
                pass
        members: dict[str, tuple[bytes, int]] = {}
        for item in source.infolist():
            if item.is_dir() or item.filename in {DIST_MANIFEST} or item.filename.startswith(PACKAGE_PREFIX):
                continue
            if not safe_member(item.filename):
                raise ValueError(f"unsafe base path: {item.filename}")
            members[item.filename] = (source.read(item.filename), item.compress_type)

    for path in sorted(
        p for p in package_root.rglob("*")
        if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"
    ):
        relative = path.relative_to(package_root).as_posix()
        member = PACKAGE_PREFIX + relative
        if not safe_member(member) or member in members:
            raise ValueError(f"unsafe or duplicate package path: {member}")
        members[member] = (path.read_bytes(), ZIP_DEFLATED)

    manifest = {
        "schema": "bago.behavior_distribution.v1",
        "base_archive_sha256": base_hash,
        "previous_distribution_sha256": previous_distribution_hash,
        "package_manifest_sha256": sha256(package_root / "manifest.json"),
        "entry_count": len(members),
        "files": [
            {"path": name, "sha256": hashlib.sha256(data).hexdigest()}
            for name, (data, _compression) in sorted(members.items())
        ],
    }
    members[DIST_MANIFEST] = (json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8") + b"\n", ZIP_DEFLATED)

    fd, temp_name = tempfile.mkstemp(prefix="bago-package-", suffix=".zip", dir=output.parent)
    os.close(fd)
    temp_path = Path(temp_name)
    try:
        with ZipFile(temp_path, "w", ZIP_DEFLATED) as archive:
            for name, (data, compression) in sorted(members.items()):
                info = archive.writestr(name, data, compress_type=compression)
        with ZipFile(temp_path, "r") as archive:
            bad = archive.testzip()
            if bad:
                raise BadZipFile(f"built archive failed CRC at {bad}")
        os.replace(temp_path, output)
    finally:
        if temp_path.exists():
            temp_path.unlink()
    return {"ok": True, "output": str(output), "entries": len(members), "sha256": sha256(output)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-archive", required=True, type=Path)
    parser.add_argument("--package-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = build(args.base_archive, args.package_root, args.output)
    except (OSError, ValueError, BadZipFile) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
