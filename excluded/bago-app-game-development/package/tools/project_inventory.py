#!/usr/bin/env python3
"""Read-only, bounded inventory of common application and game project markers."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

SKIP_DIRS = {
    ".git", ".hg", ".svn", ".venv", "venv", "env", "node_modules",
    "dist", "build", "out", "target", "coverage", ".next", ".nuxt",
    ".turbo", ".cache", ".godot", "Library", "Binaries", "Intermediate",
    "DerivedDataCache", "Pods", "vendor", "venv312",
}
MAX_FILES = 25_000


def _walk(root: Path, max_depth: int) -> tuple[list[Path], bool]:
    collected: list[Path] = []
    seen = 0
    for current, dirs, files in os.walk(root, topdown=True, followlinks=False):
        here = Path(current)
        depth = len(here.relative_to(root).parts)
        dirs[:] = sorted(
            d for d in dirs
            if d not in SKIP_DIRS and not (here / d).is_symlink()
        )
        if depth >= max_depth:
            dirs.clear()
        for name in sorted(files):
            seen += 1
            if seen > MAX_FILES:
                return collected, True
            candidate = here / name
            if not candidate.is_symlink():
                collected.append(candidate)
    return collected, False


def inspect(root: Path, max_depth: int = 5) -> dict:
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError(f"Not a directory: {root}")

    files, truncated = _walk(root, max_depth)
    rels = {p.relative_to(root).as_posix(): p for p in files}
    found: dict[tuple[str, str], dict[str, str]] = {}

    def add(kind: str, label: str, path: str) -> None:
        found[(kind, label)] = {"kind": kind, "name": label, "marker": path}

    def read_text(rel: str) -> str:
        try:
            return rels[rel].read_text(encoding="utf-8", errors="replace").lower()
        except (KeyError, OSError):
            return ""

    for rel, path in rels.items():
        name = path.name.lower()
        if any(part.lower().endswith((".xcodeproj", ".xcworkspace")) for part in path.parts):
            add("platform", "Apple platform/Xcode", rel)
        if name == "package.json":
            add("platform", "JavaScript/TypeScript", rel)
            raw = read_text(rel)
            for marker, label in (
                ('"next"', "Next.js"), ('"react"', "React"),
                ('"vue"', "Vue"), ('"svelte"', "Svelte"),
                ('"@angular/core"', "Angular"), ('"vite"', "Vite"),
                ('"phaser"', "Phaser"), ('"pixi.js"', "PixiJS"),
                ('"three"', "Three.js"), ('"electron"', "Electron"),
                ('"@tauri-apps/cli"', "Tauri"),
            ):
                if marker in raw:
                    add("framework", label, rel)
        elif name in {"pnpm-lock.yaml", "yarn.lock", "package-lock.json", "bun.lockb", "bun.lock"}:
            add("package-manager", name.split(".")[0], rel)
        elif name in {"pyproject.toml", "requirements.txt", "setup.py"}:
            add("platform", "Python", rel)
            raw = read_text(rel)
            for marker, label in (
                ("fastapi", "FastAPI"), ("django", "Django"),
                ("flask", "Flask"), ("pygame", "Pygame"),
                ("arcade", "Python Arcade"),
            ):
                if marker in raw:
                    add("framework", label, rel)
        elif name == "cargo.toml":
            add("platform", "Rust", rel)
            raw = read_text(rel)
            for marker, label in (("bevy", "Bevy"), ("macroquad", "Macroquad"), ("godot", "godot-rust")):
                if marker in raw:
                    add("framework", label, rel)
        elif name == "package.swift":
            add("platform", "Swift", rel)
        elif name == "pubspec.yaml":
            add("platform", "Dart/Flutter", rel)
        elif name == "project.godot":
            add("game-engine", "Godot", rel)
        elif name.endswith(".uproject"):
            add("game-engine", "Unreal Engine", rel)
        elif name == "projectversion.txt" and path.parent.name.lower() == "projectsettings":
            unity_root = path.parent.parent
            if (root / unity_root / "Assets").is_dir():
                add("game-engine", "Unity", rel)
        elif name in {"settings.gradle", "settings.gradle.kts"}:
            add("platform", "Android/Gradle", rel)
        elif name.endswith(".sln") or name.endswith(".csproj"):
            add("platform", ".NET/C#", rel)

    return {
        "schema": "bago.app_game_inventory.v1",
        "root": str(root),
        "read_only": True,
        "limits": {"max_depth": max_depth, "max_files": MAX_FILES, "excluded_directories": sorted(SKIP_DIRS)},
        "files_seen": len(files),
        "truncated": truncated,
        "detections": sorted(found.values(), key=lambda x: (x["kind"], x["name"], x["marker"])),
        "note": "Markers are discovery hints only; they do not prove dependencies are installed or a runtime/build is usable.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True, help="Project root to inspect")
    parser.add_argument("--max-depth", type=int, default=5, choices=range(1, 12))
    args = parser.parse_args()
    try:
        result = inspect(args.root, args.max_depth)
    except (OSError, RuntimeError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
