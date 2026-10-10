"""Read-only SQLite schema and conversation summary for this audit."""

from __future__ import annotations

import json
import os
import sqlite3
from urllib.request import urlopen
from pathlib import Path


conversation_id = "conv_438e701c29684bfab97adbd3abac098b"
api_url = f"http://127.0.0.1:8084/api/conversations/{conversation_id}"
with urlopen(api_url, timeout=5) as response:
    api_conversation = json.load(response)
database = Path(os.environ["LOCALAPPDATA"]) / "BAGO" / "AgenticDataLab" / "conversations" / "library.sqlite3"
uri = database.as_uri() + "?mode=ro"
connection = sqlite3.connect(uri, uri=True)
connection.row_factory = sqlite3.Row
try:
    tables = [row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    schema = {
        table: [row[1] for row in connection.execute(f'PRAGMA table_info("{table}")')]
        for table in tables
    }
    stored_conversation = connection.execute(
        "SELECT * FROM conversations WHERE id=?", (conversation_id,)
    ).fetchone()
    stored_messages = connection.execute(
        "SELECT * FROM messages WHERE conversation_id=? ORDER BY sequence", (conversation_id,)
    ).fetchall()
    stored = dict(stored_conversation) if stored_conversation else None
    api_messages = api_conversation.get("messages", [])
    message_summaries = []
    message_content_matches = len(api_messages) == len(stored_messages)
    references_match = len(api_messages) == len(stored_messages)
    roles_status_match = len(api_messages) == len(stored_messages)
    for api_message, row in zip(api_messages, stored_messages):
        db_message = dict(row)
        try:
            db_references = json.loads(db_message["references_json"] or "{}")
        except (TypeError, json.JSONDecodeError):
            db_references = None
        message_content_matches &= api_message.get("content") == db_message.get("content")
        references_match &= api_message.get("references", {}) == db_references
        roles_status_match &= all(
            api_message.get(key) == db_message.get(key)
            for key in ("sequence", "role", "status")
        )
        message_summaries.append({
            "sequence": api_message.get("sequence"),
            "role": api_message.get("role"),
            "status": api_message.get("status"),
            "trace_id": (db_references or {}).get("trace", {}).get("trace_id"),
            "sources": (db_references or {}).get("sources", []),
        })
    identity_fields = ("id", "project_id", "owner_kind", "owner_id", "status", "revision")
    conversation_identity_matches = bool(stored) and all(
        api_conversation.get(key) == stored.get(key) for key in identity_fields
    )
    result = {
        "api_url": api_url,
        "api_http_status": 200,
        "database_path": str(database),
        "sqlite_uri_mode": "ro",
        "schema": schema,
        "api_message_count": len(api_messages),
        "sqlite_message_count": len(stored_messages),
        "conversation_identity_matches": conversation_identity_matches,
        "message_content_matches_api": bool(message_content_matches),
        "roles_status_sequence_match": bool(roles_status_match),
        "references_match_api": bool(references_match),
        "messages": message_summaries,
    }
    rendered = json.dumps(result, ensure_ascii=False, sort_keys=True, default=str)
    (Path(__file__).resolve().parent / "W04_SQLITE_API_READBACK.json").write_text(
        rendered + "\n", encoding="utf-8"
    )
    print(rendered)
finally:
    connection.close()
