#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import datetime as dt
import fnmatch
import hashlib
import json
import os
import sys
from pathlib import Path

VERSION = "0.1.0"
STATE_DIR = ".codex-team"


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def read_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=2, sort_keys=True, ensure_ascii=False)
        f.write("\n")
    tmp.replace(path)


def canonical_bytes(data) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_obj(data) -> str:
    return hashlib.sha256(canonical_bytes(data)).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def root_path(args) -> Path:
    return Path(args.root).resolve()


def state_path(root: Path) -> Path:
    return root / STATE_DIR / "state.json"


def events_path(root: Path) -> Path:
    return root / STATE_DIR / "events.jsonl"


def append_event(root: Path, kind: str, **payload) -> None:
    p = events_path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    event = {"at": now_iso(), "kind": kind, **payload}
    with p.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(event, sort_keys=True, ensure_ascii=False) + "\n")


def load_state(root: Path):
    p = state_path(root)
    if not p.exists():
        raise SystemExit(f"STATE_MISSING: {p}. Run init first.")
    return read_json(p)


def save_state(root: Path, state) -> None:
    state["updated_at"] = now_iso()
    write_json(state_path(root), state)


def work_map(state):
    return {w["id"]: w for w in state["mission"]["work_items"]}


def refresh_ready(state) -> None:
    statuses = state["work_status"]
    for w in state["mission"]["work_items"]:
        wid = w["id"]
        current = statuses[wid]["status"]
        if current in {"DONE", "CLAIMED", "BLOCKED", "FAILED", "INVALIDATED"}:
            continue
        deps_done = all(statuses[d]["status"] == "DONE" for d in w.get("depends_on", []))
        statuses[wid]["status"] = "READY" if deps_done else "PENDING"


def wildcard_prefix(pattern: str) -> str:
    p = pattern.replace("\\", "/")
    idx = len(p)
    for token in ("*", "?", "["):
        pos = p.find(token)
        if pos != -1:
            idx = min(idx, pos)
    prefix = p[:idx].rstrip("/")
    return prefix


def scopes_overlap(a: str, b: str) -> bool:
    pa, pb = wildcard_prefix(a), wildcard_prefix(b)
    if not pa or not pb:
        return True
    if pa == pb:
        return True
    return pa.startswith(pb + "/") or pb.startswith(pa + "/")


def item_conflict(a, b) -> bool:
    return any(scopes_overlap(sa, sb) for sa in a.get("write_scopes", []) for sb in b.get("write_scopes", []))


def path_matches_scope(path: str, scope: str) -> bool:
    p = path.replace("\\", "/").lstrip("./")
    s = scope.replace("\\", "/").lstrip("./")
    if fnmatch.fnmatchcase(p, s):
        return True
    prefix = wildcard_prefix(s)
    return bool(prefix and (p == prefix or p.startswith(prefix + "/")))


def validate_changed_files(work, changed_files):
    scopes = work.get("write_scopes", [])
    bad = [p for p in changed_files if not any(path_matches_scope(p, s) for s in scopes)]
    return bad


def handoff_payload_hash(handoff) -> str:
    data = copy.deepcopy(handoff)
    data.pop("payload_sha256", None)
    return sha256_obj(data)


def validate_handoff(root: Path, state, wid: str):
    errors = []
    wm = work_map(state)
    if wid not in wm:
        return [f"unknown work id {wid}"]
    hp = root / STATE_DIR / "handoffs" / f"{wid}.json"
    if not hp.exists():
        return [f"missing handoff {hp}"]
    try:
        h = read_json(hp)
    except Exception as e:
        return [f"invalid JSON {hp}: {e}"]
    required = ["work_id", "role", "status", "changed_files", "outputs", "verification", "residual_risks", "next_consumers", "payload_sha256"]
    for k in required:
        if k not in h:
            errors.append(f"{wid}: missing {k}")
    if errors:
        return errors
    work = wm[wid]
    if h["work_id"] != wid:
        errors.append(f"{wid}: handoff work_id mismatch")
    if h["role"] != work["role"]:
        errors.append(f"{wid}: role mismatch {h['role']} != {work['role']}")
    if h["status"] != "DONE":
        errors.append(f"{wid}: handoff status must be DONE")
    bad = validate_changed_files(work, h.get("changed_files", []))
    if bad:
        errors.append(f"{wid}: changed files outside scope: {bad}")
    expected = handoff_payload_hash(h)
    if h.get("payload_sha256") != expected:
        errors.append(f"{wid}: payload_sha256 mismatch")
    if any(v.get("result") == "FAIL" for v in h.get("verification", []) if isinstance(v, dict)):
        errors.append(f"{wid}: verification contains FAIL")
    next_known = set(wm)
    unknown_consumers = [x for x in h.get("next_consumers", []) if x not in next_known]
    if unknown_consumers:
        errors.append(f"{wid}: unknown next consumers {unknown_consumers}")
    return errors


def cmd_init(args):
    root = root_path(args)
    sp = state_path(root)
    if sp.exists() and not args.force:
        raise SystemExit(f"STATE_EXISTS: {sp}; use --force to replace")
    mission_path = Path(args.mission).resolve()
    mission = read_json(mission_path)
    ids = [w["id"] for w in mission["work_items"]]
    if len(ids) != len(set(ids)):
        raise SystemExit("MISSION_INVALID: duplicate work item ids")
    idset = set(ids)
    for w in mission["work_items"]:
        missing = [d for d in w.get("depends_on", []) if d not in idset]
        if missing:
            raise SystemExit(f"MISSION_INVALID: {w['id']} missing deps {missing}")
    status = {}
    for w in mission["work_items"]:
        status[w["id"]] = {"status": "READY" if not w.get("depends_on") else "PENDING", "agent": None, "claimed_at": None, "done_at": None}
    state = {
        "protocol_version": VERSION,
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "mission_source": str(mission_path),
        "mission_sha256": sha256_file(mission_path),
        "mission": mission,
        "work_status": status,
        "terminal_gate": "OPEN"
    }
    (root / STATE_DIR / "handoffs").mkdir(parents=True, exist_ok=True)
    (root / STATE_DIR / "change_requests").mkdir(parents=True, exist_ok=True)
    save_state(root, state)
    append_event(root, "MISSION_INIT", mission_id=mission["mission_id"], mission_sha256=state["mission_sha256"])
    print(f"PASS init {mission['mission_id']} -> {sp}")


def cmd_ready(args):
    root = root_path(args)
    state = load_state(root)
    refresh_ready(state)
    save_state(root, state)
    ready = [w for w in state["mission"]["work_items"] if state["work_status"][w["id"]]["status"] == "READY"]
    if not ready:
        print("READY: none")
        return
    for w in ready:
        print(f"READY {w['id']} [{w['role']}] {w['title']}")


def safe_batches(ready, max_concurrency):
    remaining = list(ready)
    batches = []
    while remaining:
        batch = []
        kept = []
        for w in remaining:
            if len(batch) < max_concurrency and all(not item_conflict(w, x) for x in batch):
                batch.append(w)
            else:
                kept.append(w)
        batches.append(batch)
        remaining = kept
    return batches


def cmd_pair(args):
    root = root_path(args)
    state = load_state(root)
    refresh_ready(state)
    save_state(root, state)
    ready = [w for w in state["mission"]["work_items"] if state["work_status"][w["id"]]["status"] == "READY"]
    max_c = args.max_concurrency or state["mission"].get("max_concurrency", 3)
    batches = safe_batches(ready, max_c)
    if not batches:
        print("PAIR: none")
        return
    for i, batch in enumerate(batches, 1):
        ids = ", ".join(f"{w['id']}:{w['role']}" for w in batch)
        print(f"BATCH {i} SAFE_PARALLEL <= {max_c}: {ids}")


def cmd_claim(args):
    root = root_path(args)
    state = load_state(root)
    refresh_ready(state)
    wm = work_map(state)
    if args.work_id not in wm:
        raise SystemExit(f"UNKNOWN_WORK_ID: {args.work_id}")
    s = state["work_status"][args.work_id]
    if s["status"] != "READY":
        raise SystemExit(f"NOT_READY: {args.work_id} is {s['status']}")
    work = wm[args.work_id]
    for other_id, os_ in state["work_status"].items():
        if os_["status"] == "CLAIMED" and item_conflict(work, wm[other_id]):
            raise SystemExit(f"SCOPE_CONFLICT: {args.work_id} overlaps active {other_id}")
    s.update({"status": "CLAIMED", "agent": args.agent, "claimed_at": now_iso()})
    save_state(root, state)
    append_event(root, "CLAIM", work_id=args.work_id, agent=args.agent, role=work["role"])
    print(f"PASS claim {args.work_id} -> {args.agent}")


def cmd_handoff(args):
    root = root_path(args)
    state = load_state(root)
    wm = work_map(state)
    wid = args.work_id
    if wid not in wm:
        raise SystemExit(f"UNKNOWN_WORK_ID: {wid}")
    if state["work_status"][wid]["status"] != "CLAIMED":
        raise SystemExit(f"NOT_CLAIMED: {wid}")
    draft = read_json(Path(args.file).resolve())
    work = wm[wid]
    draft["work_id"] = wid
    draft["role"] = work["role"]
    draft["status"] = "DONE"
    draft.setdefault("changed_files", [])
    draft.setdefault("outputs", [])
    draft.setdefault("verification", [])
    draft.setdefault("residual_risks", [])
    draft.setdefault("next_consumers", [w["id"] for w in state["mission"]["work_items"] if wid in w.get("depends_on", [])])
    bad = validate_changed_files(work, draft["changed_files"])
    if bad:
        raise SystemExit(f"OUT_OF_SCOPE_CHANGED_FILES: {bad}")
    if not draft["verification"]:
        raise SystemExit("HANDOFF_INVALID: verification must contain at least one command/result")
    fails = [x for x in draft["verification"] if x.get("result") == "FAIL"]
    if fails:
        raise SystemExit("HANDOFF_INVALID: verification contains FAIL")
    for out in draft["outputs"]:
        p = out.get("path")
        if p:
            full = root / p
            if full.is_file():
                out["sha256"] = sha256_file(full)
    draft["payload_sha256"] = handoff_payload_hash(draft)
    hp = root / STATE_DIR / "handoffs" / f"{wid}.json"
    write_json(hp, draft)
    errors = validate_handoff(root, state, wid)
    if errors:
        hp.unlink(missing_ok=True)
        raise SystemExit("HANDOFF_INVALID: " + "; ".join(errors))
    state["work_status"][wid]["status"] = "DONE"
    state["work_status"][wid]["done_at"] = now_iso()
    refresh_ready(state)
    terminal = state["mission"].get("terminal_work_items", [])
    if terminal and all(state["work_status"][x]["status"] == "DONE" for x in terminal):
        state["terminal_gate"] = "DONE"
    save_state(root, state)
    append_event(root, "HANDOFF_DONE", work_id=wid, payload_sha256=draft["payload_sha256"])
    print(f"PASS handoff {wid} -> {hp}")


def cmd_status(args):
    root = root_path(args)
    state = load_state(root)
    refresh_ready(state)
    save_state(root, state)
    total = len(state["work_status"])
    done = sum(1 for x in state["work_status"].values() if x["status"] == "DONE")
    pct = int(round((done / total) * 100)) if total else 100
    blocks = 20
    fill = int(round(blocks * pct / 100))
    bar = "█" * fill + "░" * (blocks - fill)
    print(f"{state['mission']['mission_id']} [{bar}] {pct}% ({done}/{total}) gate={state['terminal_gate']}")
    for w in state["mission"]["work_items"]:
        s = state["work_status"][w["id"]]
        agent = f" agent={s['agent']}" if s.get("agent") else ""
        print(f"{w['id']} {s['status']:<11} {w['role']}{agent} :: {w['title']}")


def cmd_verify(args):
    root = root_path(args)
    state = load_state(root)
    errors = []
    warnings = []
    wm = work_map(state)
    # Done handoffs and dependency order.
    for wid, st in state["work_status"].items():
        if wid not in wm:
            errors.append(f"state contains unknown work id {wid}")
            continue
        if st["status"] == "DONE":
            errors.extend(validate_handoff(root, state, wid))
        if st["status"] in {"READY", "CLAIMED", "DONE"}:
            not_done = [d for d in wm[wid].get("depends_on", []) if state["work_status"][d]["status"] != "DONE"]
            if not_done:
                errors.append(f"{wid}: active/completed with incomplete deps {not_done}")
    # Active write-scope conflicts.
    claimed = [wid for wid, st in state["work_status"].items() if st["status"] == "CLAIMED"]
    for i, a in enumerate(claimed):
        for b in claimed[i + 1:]:
            if item_conflict(wm[a], wm[b]):
                errors.append(f"active scope conflict: {a} <-> {b}")
    # Handoff artifacts without matching DONE state.
    hd = root / STATE_DIR / "handoffs"
    if hd.exists():
        for hp in hd.glob("*.json"):
            wid = hp.stem
            if wid not in state["work_status"]:
                warnings.append(f"orphan handoff {hp.name}")
            elif state["work_status"][wid]["status"] != "DONE":
                warnings.append(f"handoff exists but state is {state['work_status'][wid]['status']}: {wid}")
    if errors:
        print("FAIL verify")
        for e in errors:
            print(f"ERROR {e}")
        for w in warnings:
            print(f"WARN {w}")
        raise SystemExit(2)
    print("PASS verify")
    for w in warnings:
        print(f"WARN {w}")



def cmd_note(args):
    root = root_path(args)
    state = load_state(root)
    known_agents = {v.get("agent") for v in state["work_status"].values() if v.get("agent")}
    if args.from_agent not in known_agents:
        raise SystemExit(f"UNKNOWN_FROM_AGENT: {args.from_agent}")
    append_event(root, "COORDINATION_NOTE", from_agent=args.from_agent, to_agent=args.to_agent, note_kind=args.kind, text=args.text)
    print(f"PASS note {args.from_agent} -> {args.to_agent} [{args.kind}]")


def cmd_inspect(args):
    root = root_path(args)
    state = load_state(root)
    wm = work_map(state)
    if args.work_id not in wm:
        raise SystemExit(f"UNKNOWN_WORK_ID: {args.work_id}")
    out = copy.deepcopy(wm[args.work_id])
    out["runtime"] = state["work_status"][args.work_id]
    print(json.dumps(out, indent=2, sort_keys=True, ensure_ascii=False))

def parser():
    p = argparse.ArgumentParser(description="BAGO Codex team coordination protocol")
    p.add_argument("--root", default=".", help="target repository root (default: current directory)")
    sp = p.add_subparsers(dest="cmd", required=True)

    x = sp.add_parser("init")
    x.add_argument("--mission", required=True)
    x.add_argument("--force", action="store_true")
    x.set_defaults(func=cmd_init)

    x = sp.add_parser("ready")
    x.set_defaults(func=cmd_ready)

    x = sp.add_parser("pair")
    x.add_argument("--max-concurrency", type=int)
    x.set_defaults(func=cmd_pair)

    x = sp.add_parser("claim")
    x.add_argument("work_id")
    x.add_argument("--agent", required=True)
    x.set_defaults(func=cmd_claim)

    x = sp.add_parser("handoff")
    x.add_argument("work_id")
    x.add_argument("--file", required=True)
    x.set_defaults(func=cmd_handoff)

    x = sp.add_parser("status")
    x.set_defaults(func=cmd_status)

    x = sp.add_parser("verify")
    x.set_defaults(func=cmd_verify)

    x = sp.add_parser("note")
    x.add_argument("--from-agent", required=True)
    x.add_argument("--to-agent", required=True)
    x.add_argument("--kind", default="INFO", choices=["INFO", "BLOCKER", "CONTRACT", "RISK", "QUESTION"])
    x.add_argument("--text", required=True)
    x.set_defaults(func=cmd_note)

    x = sp.add_parser("inspect")
    x.add_argument("work_id")
    x.set_defaults(func=cmd_inspect)
    return p


def main():
    args = parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
