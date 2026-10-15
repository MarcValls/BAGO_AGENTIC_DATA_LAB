#!/usr/bin/env python3
"""Generate or check the deterministic SHA-256 source manifest."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def render_manifest(root: Path) -> bytes:
    files = [
        path for path in sorted(root.rglob("*"))
        if path.is_file() and path.name != "manifest.json"
        and "__pycache__" not in path.parts and path.suffix != ".pyc"
    ]
    data = {
        "schema": "bago.codex.application-game-package.v1",
        "name": "bago-app-game-development",
        "version": "1.0.0",
        "files": [
            {"path": path.relative_to(root).as_posix(), "sha256": file_hash(path)}
            for path in files
        ],
    }
    return (json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package_root", type=Path)
    parser.add_argument("--check", action="store_true", help="fail if manifest differs; do not write")
    args = parser.parse_args()
    root = args.package_root.resolve(strict=True)
    if not root.is_dir():
        parser.error("package_root must be a directory")
    manifest = root / "manifest.json"
    expected = render_manifest(root)
    if args.check:
        actual = manifest.read_bytes() if manifest.is_file() else b""
        ok = actual == expected
        print(json.dumps({"ok": ok, "mode": "check", "manifest": str(manifest)}))
        return 0 if ok else 1

    fd, temp_name = tempfile.mkstemp(prefix="manifest-", suffix=".tmp", dir=root)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(expected)
        os.replace(temp_name, manifest)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
    print(json.dumps({"ok": True, "mode": "write", "manifest": str(manifest), "files": len(json.loads(expected)["files"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
