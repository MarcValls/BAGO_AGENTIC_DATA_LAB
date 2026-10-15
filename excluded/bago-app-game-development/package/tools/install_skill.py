#!/usr/bin/env python3
"""Install this package's Codex skill at the effective CODEX_HOME path."""
from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
from pathlib import Path


SKILL_NAME = "bago-app-game-development"


def install(codex_home: Path) -> Path:
    package_root = Path(__file__).resolve().parents[1]
    source = package_root / "skills" / SKILL_NAME
    if not (source / "SKILL.md").is_file():
        raise FileNotFoundError(f"skill source missing: {source / 'SKILL.md'}")

    codex_home = codex_home.expanduser().resolve()
    skills_root = codex_home / "skills"
    destination = skills_root / SKILL_NAME
    if destination.exists():
        raise FileExistsError(f"refusing to overwrite existing skill: {destination}")
    skills_root.mkdir(parents=True, exist_ok=True)

    staging = Path(tempfile.mkdtemp(prefix=f".{SKILL_NAME}-", dir=skills_root))
    staged_skill = staging / SKILL_NAME
    try:
        shutil.copytree(source, staged_skill)
        if destination.exists():
            raise FileExistsError(f"destination appeared during install: {destination}")
        os.rename(staged_skill, destination)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex-home", type=Path, help="Codex home directory (defaults to CODEX_HOME or USERPROFILE/.codex)")
    args = parser.parse_args()
    configured_home = args.codex_home or (
        Path(os.environ["CODEX_HOME"])
        if os.environ.get("CODEX_HOME")
        else Path(os.environ["USERPROFILE"]) / ".codex"
        if os.environ.get("USERPROFILE")
        else None
    )
    if configured_home is None:
        parser.error("set CODEX_HOME or USERPROFILE, or pass --codex-home")
    try:
        destination = install(configured_home)
    except (OSError, RuntimeError) as exc:
        print(f"installation failed: {exc}", file=sys.stderr)
        return 1
    print(f"installed: {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
