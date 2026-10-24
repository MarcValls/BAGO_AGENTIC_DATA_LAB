"""Export tracked public source only; never mounts/copies the user's profile."""
import argparse
import fnmatch
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import re

ROOT = Path(__file__).resolve().parent
TOP = {"src", "tests", "scripts", "frontend", "runtime", ".github"}
SINGLE = {"requirements.txt", "requirements-test.txt", "requirements-whatsapp.txt", "SECURITY.md", "README.md", "demo.py", "Dockerfile.ui", "pyproject.toml", "pytest.ini", "docs/governed-execution/GEX_V1_SCHEMA.json", "docs/public-web/MANUAL.md"}
# Public, versioned replay fixture required by test_chat_inspection.py. Historical
# source identity only; inclusion never claims a new provider execution.
SINGLE.add("docs/verification/readme-corporate-20261022/demo/trace-496fac766f384348.json")
DENY_PARTS = {".git", ".worktrees", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache", "dist", ".build", "build", "coverage", ".cache", "evidence", "traces", "profiles", "output", "demo_output", "private-evidence", "screenshots", "archive", "archives", "history"}
DENY_NAMES = (".env", ".env.*", "*.sqlite*", "*.db", "*.pem", "*.key", "*.pfx", "*credentials*", "*client_secret*", "*oauth*.json")


APPROVED_HISTORY = "src/contacts_service/history/UPSTREAM_SOURCE.py"


def allowed(path, *, approved_history=False):
    parts = Path(path).parts
    frontend_code = path.startswith(("frontend/src/", "frontend/packages/", "frontend/tests/")) and Path(path).suffix in {".ts", ".tsx", ".js", ".mjs", ".css", ".svg", ".html"}
    denied = DENY_PARTS - {"evidence"} if frontend_code else DENY_PARTS
    if path == APPROVED_HISTORY and approved_history:
        denied = denied - {"history"}
    if not parts or any(p.casefold() in denied or p.casefold().startswith("private") for p in parts):
        return False
    if frontend_code:
        return True
    if any(fnmatch.fnmatch(parts[-1].casefold(), pattern) for pattern in DENY_NAMES):
        return False
    if parts[0] == "frontend":
        return len(parts) > 1 and (parts[1] in {"src", "public", "tests", "packages"} or
            (len(parts) == 2 and (parts[1] in {"package.json", "package-lock.json", "index.html", "ui-kit-preview.html", "vite.config.ts", "vitest.config.ts"} or parts[1].startswith("tsconfig"))))
    return path in SINGLE or parts[0] in TOP or path.startswith(".bago/team/kit/")


def snapshot_paths(source, snapshots):
    source = source.resolve(strict=True)
    names = set()
    identities = []
    for supplied in snapshots:
        snapshot = supplied.resolve(strict=True)
        if supplied.is_symlink() or not snapshot.is_relative_to(source):
            raise ValueError("Snapshot must belong to the identified source checkout")
        raw = snapshot.read_bytes()
        payload = json.loads(raw)
        for item in payload["files"]:
            name = item["path"]
            path = Path(name)
            if path.is_absolute() or path.as_posix() != name or not path.name or "\\" in name or ":" in name or ".." in path.parts:
                raise ValueError("Noncanonical snapshot path")
            if item.get("deleted"):
                continue
            original = source / path
            if original.is_symlink() or not original.resolve().is_relative_to(source):
                raise ValueError("Linked snapshot source")
            if not original.is_file() or hashlib.sha256(original.read_bytes()).hexdigest() != item["sha256"]:
                raise ValueError("Snapshot source changed: " + name)
            if allowed(name, approved_history=True):
                names.add(name)
        identities.append({"path": snapshot.relative_to(source).as_posix(), "sha256": hashlib.sha256(raw).hexdigest()})
    return names, identities


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--candidate-id", required=True)
    parser.add_argument("--include-snapshot", action="append", type=Path, default=[], help="Explicit immutable phase snapshot admitting reviewed new files")
    args = parser.parse_args()
    source = args.source.resolve(strict=True)
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,47}", args.candidate_id):
        raise SystemExit("Candidate ID must contain lowercase letters/digits/hyphens, maximum48characters")
    target = ROOT / "context-public/repository"
    if target.exists():
        raise SystemExit("Preserve existing context: use a new bundle directory for another export.")
    names = subprocess.check_output(["git", "ls-files", "-z"], cwd=source).decode().split("\0")
    files = []
    extra, snapshot_identities = snapshot_paths(source, args.include_snapshot)
    selected = sorted({name for name in names if allowed(name)} | extra)
    print(json.dumps({"selected_tracked_public_paths": len(selected)}), flush=True)
    for name in selected:
        original = source / name
        if original.is_symlink() or not original.resolve().is_relative_to(source):
            raise SystemExit("Refuse linked source path: " + name)
        if not original.is_file():
            continue
        destination = target / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original, destination)
        files.append({"path": name, "sha256": hashlib.sha256(destination.read_bytes()).hexdigest()})
        if len(files) % 100 == 0:
            print(json.dumps({"copied": len(files)}), flush=True)
    result = {"candidate_id": args.candidate_id, "source": str(source), "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source, text=True).strip(),
              "working_bytes": True, "only_git_tracked": not bool(snapshot_identities), "reviewed_phase_snapshots": snapshot_identities, "files": files,
              "excluded": sorted(DENY_PARTS), "note": "Untracked files require an explicit hash-verified phase snapshot; stale source and private paths are not admitted."}
    manifest_path = ROOT / "context-public/SOURCE_MANIFEST.json"
    manifest_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    (ROOT / "context-public/EXPORT_IDENTITY.json").write_text(json.dumps({"candidate_id": args.candidate_id, "source_manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest()}, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"exported_files": len(files), "head": result["head"], "target": str(target)}))


if __name__ == "__main__":
    main()
