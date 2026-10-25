"""Read-only, bounded metadata adapters for work history."""
from __future__ import annotations

import math
import os
from pathlib import Path
import re
import sqlite3
import stat
from datetime import datetime, timezone


_FIELDS = (
    "key", "kind", "id", "status", "agent_id", "agent_name",
    "parent_conversation_id", "conversation_id", "message_id", "trace_id",
    "receipt_id", "receipt_sha256", "created_at", "started_at", "completed_at",
    "activity_at", "duration_ms", "cost_usd", "tools_executed", "target_written",
    "tool_receipt_count", "related_key",
)
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}\Z")
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_STATUS = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,63}\Z")
_REPARSE = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)


def _limit(value):
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 10000:
        raise ValueError("work history limit must be an integer in 1..10000")
    return value


def _identifier(value):
    return value if isinstance(value, str) and _ID.fullmatch(value) else None


def _time(value, *, epoch=False):
    if value is None:
        return None
    try:
        if epoch:
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                return None
            parsed = datetime.fromtimestamp(value, timezone.utc)
        else:
            if not isinstance(value, str) or len(value) > 64:
                return None
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                return None
        return parsed.astimezone(timezone.utc).isoformat()
    except (ValueError, OverflowError, OSError):
        return None


def _number(value):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError("invalid measurement")
    return value


def _item(kind, identity, **values):
    identity = _identifier(identity)
    if identity is None:
        raise ValueError("invalid identifier")
    result = dict.fromkeys(_FIELDS)
    result.update(kind=kind, id=identity, key=f"{kind}:{identity}")
    for key in ("agent_id", "parent_conversation_id", "conversation_id", "message_id", "trace_id", "receipt_id"):
        value = values.get(key)
        if value is not None and _identifier(value) is None:
            raise ValueError("invalid identifier")
        result[key] = value
    status_value = values.get("status")
    if status_value is not None and (not isinstance(status_value, str) or not _STATUS.fullmatch(status_value)):
        raise ValueError("invalid status")
    result["status"] = status_value
    name = values.get("agent_name")
    if name is not None:
        if not isinstance(name, str) or len(name) > 256 or any(ord(c) < 32 for c in name):
            raise ValueError("invalid name")
        result["agent_name"] = name
    digest = values.get("receipt_sha256")
    if digest is not None and (not isinstance(digest, str) or not _HASH.fullmatch(digest)):
        raise ValueError("invalid digest")
    result["receipt_sha256"] = digest
    for key in ("created_at", "started_at", "completed_at"):
        result[key] = _time(values.get(key))
    for field in ("completed_at", "started_at", "created_at"):
        result[field] = _time(result[field])
    timestamps = [result[field] for field in ("completed_at", "started_at", "created_at")
                  if result[field] is not None]
    result["activity_at"] = max(timestamps, key=datetime.fromisoformat) if timestamps else None
    for key in ("duration_ms", "cost_usd", "tool_receipt_count"):
        result[key] = _number(values.get(key))
    for key in ("tools_executed", "target_written"):
        value = values.get(key)
        if value is not None and not isinstance(value, bool):
            raise ValueError("invalid boolean")
        result[key] = value
    related = values.get("delegation_id")
    if related is not None:
        if _identifier(related) is None:
            raise ValueError("invalid delegation identifier")
        result["related_key"] = f"delegation:{related}"
    return result


def _result(items=(), state="available", error_code=None, truncated=False):
    return {"items": list(items), "state": state, "error_code": error_code, "truncated": truncated}


def _safe_stat(path, *, directory=False):
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & _REPARSE:
        raise ValueError("unsafe filesystem entry")
    if directory:
        if not stat.S_ISDIR(info.st_mode):
            raise ValueError("expected directory")
    elif not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ValueError("unsafe file")
    return info


def _safe_ancestors(path):
    for parent in path.parents:
        _safe_stat(parent, directory=True)


def _sqlite_metadata(database_path, limit, query, project, parameters=()):
    limit = _limit(limit)
    path = Path(database_path).absolute()
    connection = None
    try:
        _safe_ancestors(path)
        _safe_stat(path)
        connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=1)
        connection.execute("PRAGMA query_only=ON")
        connection.row_factory = sqlite3.Row
        rows = connection.execute(query, (*parameters, limit + 1)).fetchmany(limit + 1)
        truncated = len(rows) > limit
        items = []
        invalid = False
        for row in rows[:limit]:
            try:
                items.append(project(dict(row)))
            except (ValueError, TypeError, OverflowError):
                invalid = True
        return _result(items, "partial" if invalid or truncated else "available",
                       "INVALID_METADATA" if invalid else "READ_LIMIT" if truncated else None, truncated)
    except FileNotFoundError:
        return _result(state="absent", error_code="SOURCE_ABSENT")
    except sqlite3.DatabaseError:
        return _result(state="unavailable", error_code="SQLITE_READ_FAILED")
    except (OSError, ValueError):
        return _result(state="unavailable", error_code="SOURCE_UNREADABLE")
    finally:
        if connection is not None:
            connection.close()


def task_metadata(database_path, limit=10000):
    return _sqlite_metadata(database_path, limit,
        "SELECT run_id, agent_id, status, created_at, completed_at FROM task_runs "
        "ORDER BY run_id LIMIT ?",
        lambda row: _item("task_run", row.pop("run_id"), **row))


def conversation_metadata(database_path, limit=10000):
    trace = "CASE WHEN json_valid(m.references_json) THEN json_extract(m.references_json, '$.trace.trace_id') END"
    delegation = "CASE WHEN json_valid(m.references_json) THEN json_extract(m.references_json, '$.delegation_parent.proposal_id') END"
    query = (
        "SELECT c.owner_id AS agent_id, m.id AS message_id, m.conversation_id, m.status, "
        "m.created_at AS completed_at, " + trace + " AS trace_id, " + delegation + " AS delegation_id "
        "FROM conversations c JOIN messages m ON m.conversation_id = c.id "
        "WHERE c.project_id = ? AND c.owner_kind = 'agent' AND c.status != 'deleted' "
        "AND m.role = 'assistant' AND typeof(" + trace + ") = 'text' "
        "AND length(" + trace + ") BETWEEN 1 AND 128 ORDER BY m.id LIMIT ?"
    )
    def project(row):
        if _identifier(row["trace_id"]) is None:
            raise ValueError("invalid trace identifier")
        return _item("agent_turn", row["message_id"], **row)
    return _sqlite_metadata(database_path, limit, query, project, ("bago-agentic-data-lab:default",))


def evaluation_metadata(database_path, limit=10000):
    query = (
        "SELECT id, agent_id, agent_name, status, duration_ms, started_at, completed_at FROM runs "
        "UNION ALL SELECT a.run_id AS id, NULL AS agent_id, NULL AS agent_name, 'RUNNING' AS status, "
        "NULL AS duration_ms, a.started_at, NULL AS completed_at FROM active_suite_runs a "
        "WHERE NOT EXISTS (SELECT 1 FROM runs r WHERE r.id = a.run_id) ORDER BY id LIMIT ?"
    )
    return _sqlite_metadata(database_path, limit, query,
        lambda row: _item("evaluation", row.pop("id"), **row))


def delegation_metadata(store, limit=10000):
    limit = _limit(limit)
    records = Path(store.directory).absolute() / "records"
    items = []
    invalid = False
    truncated = False
    try:
        _safe_ancestors(records)
        _safe_stat(records, directory=True)
        with os.scandir(records) as entries:
            for index, entry in enumerate(entries):
                if index >= limit:
                    truncated = True
                    break
                try:
                    match = re.fullmatch(r"delegation_([0-9a-f]{32})\.json", entry.name)
                    if match is None:
                        raise ValueError("unexpected record name")
                    identity = entry.name[:-5]
                    path = records / entry.name
                    before = _safe_stat(path)
                    if before.st_size > 4 * 1024 * 1024:
                        raise ValueError("oversized record")
                    record = store._load(identity)
                    after = _safe_stat(path)
                    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
                            after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
                        raise ValueError("record changed")
                    if not isinstance(record, dict) or not isinstance(record.get("binding"), dict):
                        raise ValueError("invalid record")
                    binding = record["binding"]
                    if binding.get("proposal_id") != identity:
                        raise ValueError("record identity mismatch")
                    started = _time(record.get("started_at"), epoch=True)
                    completed = _time(record.get("finished_at"), epoch=True)
                    duration = None
                    if started is not None and completed is not None:
                        duration = (record["finished_at"] - record["started_at"]) * 1000
                    items.append(_item("delegation", identity,
                        status=record.get("state"), agent_id=binding.get("agent_id"),
                        agent_name=binding.get("agent_name"),
                        parent_conversation_id=binding.get("parent_conversation_id"),
                        conversation_id=record.get("child_conversation_id"),
                        trace_id=record.get("child_trace_id"), receipt_id=record.get("receipt_id"),
                        receipt_sha256=record.get("receipt_sha256"),
                        started_at=started, completed_at=completed, duration_ms=duration,
                        tools_executed=record.get("tools_executed"),
                        target_written=record.get("target_written")))
                except (OSError, ValueError, TypeError, KeyError, OverflowError):
                    invalid = True
        return _result(items, "partial" if invalid or truncated else "available",
                       "INVALID_RECORD" if invalid else "READ_LIMIT" if truncated else None, truncated)
    except FileNotFoundError:
        return _result(state="absent", error_code="SOURCE_ABSENT")
    except (OSError, ValueError):
        return _result(items, "partial" if items else "unavailable", "SOURCE_UNREADABLE")


def _legacy_time(value):
    if not isinstance(value, str) or len(value) > 64:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        # Only the legacy writer uses datetime.utcnow() without an offset.
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return _time(parsed.isoformat())
    except (ValueError, OverflowError):
        return None


def legacy_metadata(directory, limit=10000):
    import json

    cap = _limit(limit)
    items = []
    damaged = False
    truncated = False
    directory = Path(directory)
    try:
        _safe_ancestors(directory)
        _safe_stat(directory, directory=True)
        names = []
        with os.scandir(directory) as entries:
            for entry in entries:
                if len(names) == cap:
                    truncated = True
                    break
                names.append(entry.name)
        for name in sorted(names):
            try:
                if not name.endswith(".json"):
                    raise ValueError("invalid record name")
                identity = name[:-5]
                if not identity or _identifier(identity) != identity:
                    raise ValueError("invalid record identity")
                path = directory / name
                _safe_stat(path)
                before = os.stat(path, follow_symlinks=False)
                if before.st_size > 4 * 1024 * 1024:
                    raise ValueError("oversized record")
                flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
                descriptor = os.open(path, flags)
                with os.fdopen(descriptor, "rb") as stream:
                    opened = os.fstat(stream.fileno())
                    if (not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1
                            or getattr(opened, "st_file_attributes", 0) & 0x400
                            or (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino)
                            or opened.st_size > 4 * 1024 * 1024):
                        raise ValueError("unsafe record")
                    raw = stream.read(4 * 1024 * 1024 + 1)
                if len(raw) > 4 * 1024 * 1024:
                    raise ValueError("oversized record")
                record = json.loads(raw)
                if not isinstance(record, dict) or record.get("job_id") != identity:
                    raise ValueError("record identity mismatch")
                items.append(_item(
                    "legacy_job", identity,
                    agent_id=record.get("agent_id"), status=record.get("status"),
                    created_at=_legacy_time(record.get("created_at")),
                    completed_at=_legacy_time(record.get("completed_at")),
                    duration_ms=record.get("duration_ms"), cost_usd=record.get("cost_usd")))
            except (OSError, ValueError, TypeError, UnicodeError, OverflowError, RecursionError):
                damaged = True
    except FileNotFoundError:
        return _result(state="absent")
    except (OSError, ValueError, TypeError):
        return _result(items, "partial" if items else "unavailable", "SOURCE_UNREADABLE", truncated=truncated)
    return _result(items, "partial" if damaged or truncated else "available",
                   "SOURCE_INVALID_RECORD" if damaged else None, truncated=truncated)


def work_history(*, jobs_directory, task_store, conversations, evaluations,
                 delegations, limit=50, offset=0, kind="all"):
    kinds = ("legacy_job", "task_run", "delegation", "agent_turn", "evaluation")
    if type(limit) is not int or not 1 <= limit <= 200:
        raise ValueError("invalid work history limit")
    if type(offset) is not int or not 0 <= offset <= 10000:
        raise ValueError("invalid work history offset")
    if not isinstance(kind, str) or kind not in ("all",) + kinds:
        raise ValueError("invalid work history kind")

    readers = (
        ("legacy_job", lambda: legacy_metadata(jobs_directory, limit=10000)),
        ("task_run", lambda: task_store.work_history_metadata(limit=10000)),
        ("delegation", lambda: delegations.work_history_metadata(limit=10000)),
        ("agent_turn", lambda: conversations.work_history_metadata(limit=10000)),
        ("evaluation", lambda: evaluations.work_history_metadata(limit=10000)),
    )
    sources = []
    items = []
    for source_kind, read in readers:
        try:
            result = read()
            if not isinstance(result, dict):
                raise ValueError("invalid source result")
            state = result.get("state")
            truncated = result.get("truncated")
            records = result.get("items")
            if (state not in ("available", "absent", "partial", "unavailable")
                    or type(truncated) is not bool or not isinstance(records, list)):
                raise ValueError("invalid source result")
            damaged = False
            normalized = []
            for record in records[:10000]:
                try:
                    if not isinstance(record, dict) or record.get("kind") != source_kind:
                        raise ValueError("invalid source item")
                    identity = record.get("id")
                    if not identity or _identifier(identity) != identity:
                        raise ValueError("invalid source identity")
                    values = {field: record.get(field) for field in _FIELDS
                              if field not in ("key", "kind", "id", "activity_at", "related_key")}
                    item = _item(source_kind, identity, **values)
                    item["related_key"] = (record.get("related_key")
                                           if source_kind == "agent_turn" else None)
                    normalized.append(item)
                except (ValueError, TypeError, OverflowError):
                    damaged = True
            truncated = truncated or len(records) > 10000
            if damaged or truncated:
                state = "partial" if normalized or state != "unavailable" else "unavailable"
            if normalized and state in ("absent", "unavailable"):
                state = "partial"
                damaged = True
            error_code = None
            if result.get("error_code") is not None or state in ("partial", "unavailable"):
                error_code = "SOURCE_INVALID_METADATA" if damaged else "SOURCE_UNREADABLE"
            sources.append({"kind": source_kind, "state": state,
                            "error_code": error_code, "truncated": truncated})
            items.extend(normalized)
        except (OSError, ValueError, TypeError, sqlite3.Error, OverflowError):
            sources.append({"kind": source_kind, "state": "unavailable",
                            "error_code": "SOURCE_UNREADABLE", "truncated": False})

    delegation_index = {}
    for item in items:
        if item["kind"] == "delegation":
            delegation_index.setdefault(item["key"], []).append(item)
    candidates = {}
    for turn in items:
        if turn["kind"] != "agent_turn":
            continue
        proposed = turn["related_key"]
        turn["related_key"] = None
        if not isinstance(proposed, str):
            continue
        matches = delegation_index.get(proposed, [])
        if len(matches) != 1:
            continue
        delegation = matches[0]
        if all(turn[field] is not None and turn[field] == delegation[field]
               for field in ("agent_id", "conversation_id", "trace_id")):
            candidates.setdefault(proposed, []).append(turn)
    for key, turns in candidates.items():
        if len(turns) == 1:
            turn = turns[0]
            turn["related_key"] = key
            delegation_index[key][0]["related_key"] = turn["key"]

    selected = [item for item in items if kind == "all" or item["kind"] == kind]
    selected.sort(key=lambda item: item["key"])
    minimum = datetime.min.replace(tzinfo=timezone.utc)

    def activity(item):
        value = _time(item.get("activity_at"))
        return datetime.fromisoformat(value) if value is not None else minimum

    selected.sort(key=activity, reverse=True)
    total = len(selected)
    page = selected[offset:offset + limit]
    has_more = offset + len(page) < total
    return {"schema": "work-history.v1", "items": page, "total": total,
            "limit": limit, "offset": offset, "has_more": has_more,
            "next_offset": offset + len(page) if has_more else None, "sources": sources}

