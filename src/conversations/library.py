"""Local, project-scoped conversation persistence for BAGO Agentic Data Lab."""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

OwnerKind = Literal["assistant", "agent"]
PROJECT_ID = "bago-agentic-data-lab:default"


class ConversationNotFound(Exception):
    pass


class ConversationConflict(Exception):
    pass


def default_database_path() -> Path:
    """Resolve a per-user database outside the repository and other ADL stores."""
    override = os.environ.get("BAGO_CONVERSATION_DB_PATH")
    if override:
        return Path(override).expanduser().resolve()
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        root = Path(local_app_data)
    else:
        root = Path.home() / ".local" / "share"
    return root / "BAGO" / "AgenticDataLab" / "conversations" / "library.sqlite3"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class ConversationStore:
    def __init__(self, database_path: Path | str | None = None) -> None:
        self.database_path = Path(database_path) if database_path else default_database_path()

    def _connect(self) -> sqlite3.Connection:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.database_path, timeout=10, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                owner_kind TEXT NOT NULL CHECK (owner_kind IN ('assistant', 'agent')),
                owner_id TEXT NOT NULL,
                title TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived', 'deleted')),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                revision INTEGER NOT NULL DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_conversations_owner_recent
                ON conversations(project_id, owner_kind, owner_id, status, updated_at DESC);
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL REFERENCES conversations(id),
                sequence INTEGER NOT NULL,
                role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'complete',
                references_json TEXT NOT NULL DEFAULT '{}',
                UNIQUE(conversation_id, sequence)
            );
            CREATE INDEX IF NOT EXISTS idx_messages_conversation_sequence
                ON messages(conversation_id, sequence);
            """
        )
        return connection

    @staticmethod
    def _decode_conversation(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"], "project_id": row["project_id"], "owner_kind": row["owner_kind"],
            "owner_id": row["owner_id"], "title": row["title"], "status": row["status"],
            "created_at": row["created_at"], "updated_at": row["updated_at"], "revision": row["revision"],
        }

    @staticmethod
    def _decode_message(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"], "sequence": row["sequence"], "role": row["role"],
            "content": row["content"], "created_at": row["created_at"], "status": row["status"],
            "references": json.loads(row["references_json"]),
        }

    def create(self, owner_kind: OwnerKind, owner_id: str, title: str = "New conversation") -> dict[str, Any]:
        if owner_kind == "assistant":
            owner_id = "app-assistant"
        conversation_id = "conv_" + uuid.uuid4().hex
        now = _now()
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO conversations (id, project_id, owner_kind, owner_id, title, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (conversation_id, PROJECT_ID, owner_kind, owner_id, title.strip()[:160] or "New conversation", now, now),
            )
            row = connection.execute("SELECT * FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
        return self._decode_conversation(row)

    def list(self, owner_kind: OwnerKind | None = None, owner_id: str | None = None, status: str = "active", limit: int = 100) -> list[dict[str, Any]]:
        clauses = ["project_id = ?"]
        values: list[Any] = [PROJECT_ID]
        if status == "all":
            clauses.append("status != 'deleted'")
        else:
            clauses.append("status = ?")
            values.append(status)
        if owner_kind:
            clauses.append("owner_kind = ?")
            values.append(owner_kind)
        if owner_id:
            clauses.append("owner_id = ?")
            values.append(owner_id)
        values.append(max(1, min(limit, 200)))
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM conversations WHERE {' AND '.join(clauses)} ORDER BY updated_at DESC LIMIT ?", values
            ).fetchall()
        return [self._decode_conversation(row) for row in rows]

    def get(self, conversation_id: str, include_messages: bool = True) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM conversations WHERE id = ? AND project_id = ? AND status != 'deleted'",
                (conversation_id, PROJECT_ID),
            ).fetchone()
            if row is None:
                raise ConversationNotFound(conversation_id)
            result = self._decode_conversation(row)
            if include_messages:
                messages = connection.execute(
                    "SELECT * FROM messages WHERE conversation_id = ? ORDER BY sequence", (conversation_id,)
                ).fetchall()
                result["messages"] = [self._decode_message(message) for message in messages]
        return result

    def append_message(
        self, conversation_id: str, expected_revision: int, role: Literal["user", "assistant"],
        content: str, references: dict[str, Any] | None = None, status: str = "complete",
    ) -> dict[str, Any]:
        now = _now()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT revision, status FROM conversations WHERE id = ? AND project_id = ?",
                (conversation_id, PROJECT_ID),
            ).fetchone()
            if row is None or row["status"] == "deleted":
                connection.rollback()
                raise ConversationNotFound(conversation_id)
            if row["revision"] != expected_revision:
                connection.rollback()
                raise ConversationConflict(conversation_id)
            sequence = connection.execute(
                "SELECT COALESCE(MAX(sequence), 0) + 1 FROM messages WHERE conversation_id = ?", (conversation_id,)
            ).fetchone()[0]
            message_id = "msg_" + uuid.uuid4().hex
            connection.execute(
                "INSERT INTO messages (id, conversation_id, sequence, role, content, created_at, status, references_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (message_id, conversation_id, sequence, role, content, now, status, json.dumps(references or {}, ensure_ascii=False)),
            )
            next_revision = expected_revision + 1
            changed = connection.execute(
                "UPDATE conversations SET updated_at = ?, revision = ? WHERE id = ? AND revision = ?",
                (now, next_revision, conversation_id, expected_revision),
            ).rowcount
            if not changed:
                connection.rollback()
                raise ConversationConflict(conversation_id)
            if role == "user" and sequence == 1:
                title = " ".join(content.strip().split())[:70] or "New conversation"
                connection.execute("UPDATE conversations SET title = ? WHERE id = ?", (title, conversation_id))
            saved = connection.execute("SELECT * FROM messages WHERE id = ?", (message_id,)).fetchone()
            connection.commit()
        return {**self._decode_message(saved), "revision": next_revision}

    def rename(self, conversation_id: str, expected_revision: int, title: str) -> dict[str, Any]:
        title = " ".join(title.strip().split())[:160]
        if not title:
            raise ValueError("A conversation title is required.")
        return self._change_status_or_title(conversation_id, expected_revision, title=title)

    def set_status(self, conversation_id: str, expected_revision: int, status: Literal["active", "archived", "deleted"]) -> dict[str, Any]:
        return self._change_status_or_title(conversation_id, expected_revision, status=status)

    def _change_status_or_title(self, conversation_id: str, expected_revision: int, *, title: str | None = None, status: str | None = None) -> dict[str, Any]:
        assignments = ["updated_at = ?", "revision = revision + 1"]
        values: list[Any] = [_now()]
        if title is not None:
            assignments.append("title = ?")
            values.append(title)
        if status is not None:
            assignments.append("status = ?")
            values.append(status)
        values.extend([conversation_id, PROJECT_ID, expected_revision])
        with self._connect() as connection:
            changed = connection.execute(
                f"UPDATE conversations SET {', '.join(assignments)} WHERE id = ? AND project_id = ? AND revision = ? AND status != 'deleted'",
                values,
            ).rowcount
            if not changed:
                exists = connection.execute("SELECT 1 FROM conversations WHERE id = ? AND project_id = ?", (conversation_id, PROJECT_ID)).fetchone()
                if exists is None:
                    raise ConversationNotFound(conversation_id)
                raise ConversationConflict(conversation_id)
        if status == "deleted":
            return {"id": conversation_id, "status": status, "revision": expected_revision + 1}
        return self.get(conversation_id)

    def restore(self, conversation_id: str, expected_revision: int) -> dict[str, Any]:
        with self._connect() as connection:
            changed = connection.execute(
                "UPDATE conversations SET status = 'active', updated_at = ?, revision = revision + 1 WHERE id = ? AND project_id = ? AND revision = ? AND status IN ('archived', 'deleted')",
                (_now(), conversation_id, PROJECT_ID, expected_revision),
            ).rowcount
            if not changed:
                exists = connection.execute("SELECT 1 FROM conversations WHERE id = ? AND project_id = ?", (conversation_id, PROJECT_ID)).fetchone()
                if exists is None:
                    raise ConversationNotFound(conversation_id)
                raise ConversationConflict(conversation_id)
        return self.get(conversation_id)

    def history(self, conversation_id: str, limit: int = 30) -> list[dict[str, str]]:
        conversation = self.get(conversation_id)
        return [
            {"role": message["role"], "content": message["content"]}
            for message in conversation["messages"][-max(1, min(limit, 60)):]
        ]
