"""Read-only verification of the source and owned stores of a running ADL copy."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from urllib.request import Request, urlopen


def _same(first: str | Path, second: str | Path) -> bool:
    return os.path.normcase(str(Path(first).resolve())) == os.path.normcase(str(Path(second).resolve()))


def inspect(url: str, source: Path, data: Path, workspace: Path | None = None) -> dict:
    def get(route):
        request = Request(url.rstrip("/") + route, headers={"Cache-Control": "no-cache"})
        with urlopen(request, timeout=15) as response:
            return json.load(response)

    identity = get("/api/runtime/storage")
    context = get("/api/chat/context")
    assert identity["application_root_matches_source"] is True, "application/source mismatch"
    assert _same(identity["effective_source_root"], source), "unexpected loaded source"
    assert _same(identity["application_root"], source), "unexpected application root"
    assert _same(identity["data_root"], data), "unexpected data root"
    assert identity["external_overrides"] == [], "a store still uses an external override"
    assert identity["mode"] == "portable", "runtime uses an explicit data override"
    actual_hash = hashlib.sha256((source / "src/api/server.py").read_bytes()).hexdigest()
    assert identity["server_source_sha256_at_import"] == actual_hash, "loaded server is stale"
    data = data.resolve()
    verified = {}
    for name, value in identity["effective_paths"].items():
        if value is None:
            continue
        path = Path(value).resolve()
        assert path.is_relative_to(data), f"store outside owned data: {name}"
        verified[name] = path.relative_to(data).as_posix()
    if workspace is not None:
        assert _same(context["workspace_root"], workspace), "selected project changed"
        active = get("/api/project-folders/v1/active")
        assert _same(active["root"], workspace), "active project root differs"
        project_id = active.get("project_id")
    else:
        project_id = None
    return {
        "status": "PASS", "classification": "LIVE_READ_ONLY_RUNTIME_IDENTITY",
        "process_id": identity["process_id"], "source_root": str(source.resolve()),
        "data_root": str(data), "server_source_sha256": actual_hash,
        "verified_store_paths": verified, "selected_project_id": project_id,
        "host_bound_profile_configured": identity["host_bound_profile_configured"],
        "scope": "source identity and reported core paths; not tool execution or cross-machine authentication",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--data-root", required=True, type=Path)
    parser.add_argument("--workspace-root", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = inspect(args.url, args.source_root, args.data_root, args.workspace_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    print(json.dumps({"status": result["status"], "stores": len(result["verified_store_paths"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
