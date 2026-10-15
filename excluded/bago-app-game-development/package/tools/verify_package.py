#!/usr/bin/env python3
"""Verify package file hashes and that the skill's local references resolve."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify(package_root: Path) -> list[str]:
    root = package_root.resolve(strict=True)
    errors: list[str] = []
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        return ["manifest.json missing"]
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"manifest.json unreadable: {exc}"]
    if manifest.get("schema") != "bago.codex.application-game-package.v1":
        errors.append("unsupported package manifest schema")
    entries = manifest.get("files")
    if not isinstance(entries, list) or not entries:
        return errors + ["manifest files must be a non-empty list"]

    listed: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            errors.append("invalid manifest file entry")
            continue
        relative = entry["path"].replace("\\", "/")
        candidate = (root / relative).resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            errors.append(f"path escapes package: {relative}")
            continue
        listed.add(relative)
        if not candidate.is_file():
            errors.append(f"file missing: {relative}")
        elif sha256(candidate) != entry.get("sha256"):
            errors.append(f"SHA-256 mismatch: {relative}")

    skill_dir = root / "skills" / "bago-app-game-development"
    skill_file = skill_dir / "SKILL.md"
    if not skill_file.is_file():
        errors.append("skill SKILL.md missing")
    else:
        text = skill_file.read_text(encoding="utf-8")
        if not text.startswith("---\n") or not re.search(r"(?m)^name:\s*bago-app-game-development\s*$", text):
            errors.append("skill frontmatter/name invalid")
        if not re.search(r"(?m)^description:\s*\S", text):
            errors.append("skill description missing")
        for target in re.findall(r"\]\((references/[^)]+)\)", text):
            if not (skill_dir / target).is_file():
                errors.append(f"skill reference missing: {target}")
    if not (skill_dir / "agents" / "openai.yaml").is_file():
        errors.append("agents/openai.yaml missing")

    actual = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path != manifest_path
        and "__pycache__" not in path.parts and path.suffix != ".pyc"
    }
    for extra in sorted(actual - listed):
        errors.append(f"unmanifested package file: {extra}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package_root", type=Path)
    args = parser.parse_args()
    try:
        errors = verify(args.package_root)
    except (OSError, RuntimeError, ValueError) as exc:
        errors = [str(exc)]
    print(json.dumps({"ok": not errors, "errors": errors}, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
