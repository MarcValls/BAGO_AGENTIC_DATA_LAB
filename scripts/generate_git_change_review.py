#!/usr/bin/env python3
"""Generate a local Git review snapshot and embed it in the BAGO Layer HTML."""
from __future__ import annotations

import datetime as dt
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "bago-layer"
HTML = OUT / "git-change-review.html"
JSON_OUT = OUT / "git-change-review.v1.json"


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=ROOT)


def text(value: bytes) -> str:
    return value.decode("utf-8", errors="replace")


def changes() -> list[dict]:
    records = git("status", "--porcelain=v1", "-z", "--untracked-files=all").split(b"\0")
    result: list[dict] = []
    i = 0
    while i < len(records):
        record = records[i]
        i += 1
        if not record:
            continue
        xy = record[:2].decode("ascii", errors="replace")
        path = text(record[3:])
        old_path = None
        if "R" in xy or "C" in xy:
            if i < len(records):
                # In porcelain -z, rename/copy entries list destination first,
                # then the original path.
                old_path = text(records[i])
                i += 1
        result.append({
            "path": path,
            "old_path": old_path,
            "status": xy.strip() or "?",
            "staged": xy[0] not in " ?",
            "unstaged": xy[1] not in " ?",
            "untracked": xy == "??",
        })
    return result


def refs() -> list[dict]:
    current = text(git("branch", "--show-current")).strip()
    raw = text(git("for-each-ref", "--format=%(refname:short)%09%(objectname)%09%(upstream:short)%09%(upstream:track)", "refs/heads", "refs/remotes"))
    branches = []
    for line in raw.splitlines():
        name, sha, upstream, tracking = (line.split("\t") + ["", "", "", ""])[:4]
        if name.endswith("/HEAD"):
            continue
        branches.append({
            "name": name,
            "kind": "remote" if name.startswith("origin/") else "local",
            "sha": sha,
            "upstream": upstream or None,
            "tracking": tracking.strip() or None,
            "is_current": name == current,
        })
    return branches


def commits() -> list[dict]:
    raw = git("log", "--all", "-n", "30", "--date=iso-strict", "--format=%H%x00%h%x00%aI%x00%an%x00%s%x1e")
    items = []
    for record in raw.split(b"\x1e"):
        fields = record.strip(b"\r\n\0").split(b"\0")
        if len(fields) != 5 or not fields[0]:
            continue
        sha, short, date, author, subject = map(text, fields)
        items.append({"sha": sha, "short_sha": short, "date": date, "author": author, "subject": subject})
    return items


def snapshot() -> dict:
    branch = text(git("branch", "--show-current")).strip() or "(detached HEAD)"
    head = text(git("rev-parse", "HEAD")).strip()
    upstream = None
    ahead = behind = None
    try:
        upstream = text(git("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}")).strip()
        counts = text(git("rev-list", "--left-right", "--count", f"{upstream}...HEAD")).split()
        behind, ahead = int(counts[0]), int(counts[1])
    except (subprocess.CalledProcessError, IndexError, ValueError):
        pass
    unresolved = len([x for x in git("ls-files", "-u", "-z").split(b"\0") if x])
    merge_in_progress = (ROOT / ".git" / "MERGE_HEAD").exists()
    merge_target = text(git("rev-parse", "MERGE_HEAD")).strip() if merge_in_progress else None
    return {
        "contract": "urn:bago-layer:git-change-review:v1",
        "contract_version": 1,
        "source": {
            "kind": "git_worktree_snapshot",
            "captured_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "repository": {"name": ROOT.name},
            "scope": "local checkout; branch refs, current worktree and index",
        },
        "checkout": {
            "branch": branch,
            "head": {"sha": head, "short_sha": head[:12]},
            "upstream": {"name": upstream, "ahead": ahead, "behind": behind},
            "merge": {"in_progress": merge_in_progress, "target_sha": merge_target, "unresolved_index_entries": unresolved},
        },
        "changes": changes(),
        "branches": refs(),
        "commits": commits(),
        "integration": {"status": "PROPOSED", "consumer": "BAGO Layer", "entrypoint": "window.BagoLayerChangeReview.mount(snapshot)"},
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    data = snapshot()
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    JSON_OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    template = HTML.read_text(encoding="utf-8")
    start, end = "<!-- SNAPSHOT:START -->", "<!-- SNAPSHOT:END -->"
    before, rest = template.split(start, 1)
    _, after = rest.split(end, 1)
    HTML.write_text(before + start + f"\n<script type=\"application/json\" id=\"git-state\">{payload}</script>\n" + end + after, encoding="utf-8")
    print(f"Generated {JSON_OUT.relative_to(ROOT)} and {HTML.relative_to(ROOT)}")
    print(f"branch={data['checkout']['branch']} changes={len(data['changes'])} branches={len(data['branches'])} commits={len(data['commits'])}")


if __name__ == "__main__":
    main()
