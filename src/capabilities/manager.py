"""Project-scoped inventory and durable proposals that never grant authority."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal


class CapabilityNotFound(Exception):
    pass


class CapabilityProposalNotFound(Exception):
    pass


class CapabilityProposalConflict(Exception):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _timestamp(value: datetime | None = None) -> str:
    return (value or _utcnow()).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def workspace_identity(workspace_root: Path | str) -> tuple[str, Path]:
    """Return a stable opaque id for the resolved workspace; never expose its path."""
    root = Path(workspace_root).resolve()
    identity = str(root).casefold() if os.name == "nt" else str(root)
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    return f"workspace_{digest[:32]}", root


def default_database_path(workspace_root: Path | str) -> Path:
    override = os.environ.get("BAGO_CAPABILITY_DB_PATH")
    if override:
        return Path(override).expanduser().resolve()
    local_app_data = os.environ.get("LOCALAPPDATA")
    base = Path(local_app_data) if local_app_data else Path.home() / ".local" / "share"
    workspace_id, _ = workspace_identity(workspace_root)
    return base / "BAGO" / "AgenticDataLab" / "capabilities" / workspace_id / "capabilities.sqlite3"


def _source_fingerprint(root: Path, relative_path: str) -> str | None:
    try:
        content = (root / relative_path).read_bytes()
    except OSError:
        return None
    return hashlib.sha256(content).hexdigest()


def capability_catalog(workspace_root: Path | str) -> dict[str, Any]:
    """Describe only the implemented wiring observed in this backend snapshot."""
    workspace_id, root = workspace_identity(workspace_root)
    specifications = [
        {
            "id": "workspace.read_text",
            "name": "Read bounded workspace text",
            "provider": "BAGO workspace reader",
            "effect": "READ",
            "status": "AVAILABLE",
            "integration": "CONNECTED",
            "summary": "Reads one bounded UTF-8 text range through the agent chat when the user opts in for that turn.",
            "limits": {"requires_user_opt_in": True, "max_file_bytes": 262144, "max_lines": 250, "read_only": True},
            "source_paths": ["src/agent_tools/workspace_read.py", "src/api/server.py"],
        },
        {
            "id": "agent.evaluate",
            "name": "Evaluate an existing agent",
            "provider": "Configured Ollama provider",
            "effect": "MODEL_INFERENCE",
            "status": "AVAILABLE",
            "integration": "CONNECTED",
            "summary": "Runs one configured-provider inference for each case after explicit user confirmation and grades declared text checks.",
            "limits": {"requires_explicit_run": True, "max_cases": 10, "tools": False, "creates_jobs": False, "workspace_writes": False, "cost_status": "not_reported"},
            "source_paths": ["src/evaluation/agent_lab.py", "src/api/server.py"],
        },
        {
            "id": "mcp.execute",
            "name": "Governed MCP adapter",
            "provider": "MCP adapter",
            "effect": "EXTERNAL_ACTION",
            "status": "UNAVAILABLE",
            "integration": "MODULE_PRESENT_NOT_CONNECTED",
            "summary": "Registry and adapter code exist, but the product API has no connected registry or MCP call path.",
            "limits": {"invocation_available": False},
            "source_paths": ["src/adapters/mcp_adapter.py"],
        },
        {
            "id": "sandbox.execute",
            "name": "Sandbox execution components",
            "provider": "Sandbox manager",
            "effect": "EXECUTE",
            "status": "UNAVAILABLE",
            "integration": "MODULE_PRESENT_NOT_CONNECTED",
            "summary": "Sandbox and execution gateway modules exist, but are not wired to the product Agent Runner.",
            "limits": {"invocation_available": False},
            "source_paths": ["src/execution/gateway.py", "src/sandbox/manager.py"],
        },
        {
            "id": "agent.run",
            "name": "Agent Runner execution",
            "provider": "Agent Runner WebSocket",
            "effect": "EXECUTE",
            "status": "UNAVAILABLE",
            "integration": "FAIL_CLOSED",
            "summary": "The product runner rejects requests with execution_unavailable; no governed execution is registered.",
            "limits": {"invocation_available": False, "creates_jobs": False},
            "source_paths": ["src/api/server.py"],
        },
    ]
    for item in specifications:
        paths = item.pop("source_paths")
        sources = {path: _source_fingerprint(root, path) for path in paths}
        item["source_fingerprints"] = sources
        item["source_available"] = all(sources.values())
        fingerprint_data = {**item, "workspace_id": workspace_id}
        item["fingerprint"] = hashlib.sha256(
            json.dumps(fingerprint_data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        ).hexdigest()
    return {
        "workspace_id": workspace_id,
        "generated_at": _timestamp(),
        "capabilities": specifications,
        "authority_notice": "Catalog status describes integration only. It does not grant authorization or enable execution.",
    }


class CapabilityStore:
    """SQLite proposal persistence isolated by workspace and revision."""

    def __init__(self, workspace_root: Path | str, database_path: Path | str | None = None) -> None:
        self.workspace_id, self.workspace_root = workspace_identity(workspace_root)
        self.database_path = Path(database_path) if database_path else default_database_path(workspace_root)

    def _connect(self) -> sqlite3.Connection:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.database_path, timeout=10, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 10000")
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS capability_proposals (
                id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                capability_id TEXT NOT NULL,
                capability_fingerprint TEXT NOT NULL,
                effect TEXT NOT NULL,
                summary TEXT NOT NULL,
                requested_scope TEXT NOT NULL,
                conversation_id TEXT,
                status TEXT NOT NULL CHECK (status IN ('PENDING_REVIEW', 'CANCELLED', 'EXPIRED')),
                revision INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_capability_proposals_workspace_status
                ON capability_proposals(workspace_id, status, created_at DESC);
            CREATE TABLE IF NOT EXISTS capability_proposal_events (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                proposal_id TEXT NOT NULL,
                workspace_id TEXT NOT NULL,
                event_type TEXT NOT NULL CHECK (event_type IN ('PROPOSED', 'CANCELLED', 'EXPIRED')),
                revision INTEGER NOT NULL,
                occurred_at TEXT NOT NULL,
                details_json TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_capability_proposal_events_workspace
                ON capability_proposal_events(workspace_id, proposal_id, sequence);
            """
        )
        return connection

    def _expire_due(self, connection: sqlite3.Connection) -> None:
        now = _timestamp()
        rows = connection.execute(
            "SELECT id, revision FROM capability_proposals WHERE workspace_id = ? AND status = 'PENDING_REVIEW' AND expires_at <= ?",
            (self.workspace_id, now),
        ).fetchall()
        for row in rows:
            next_revision = row["revision"] + 1
            connection.execute(
                "UPDATE capability_proposals SET status = 'EXPIRED', revision = ?, updated_at = ? WHERE id = ? AND workspace_id = ? AND revision = ?",
                (next_revision, now, row["id"], self.workspace_id, row["revision"]),
            )
            connection.execute(
                "INSERT INTO capability_proposal_events (proposal_id, workspace_id, event_type, revision, occurred_at, details_json) VALUES (?, ?, 'EXPIRED', ?, ?, '{}')",
                (row["id"], self.workspace_id, next_revision, now),
            )

    @staticmethod
    def _decode(row: sqlite3.Row) -> dict[str, Any]:
        return {key: row[key] for key in row.keys()}

    def list_proposals(self, status: Literal["PENDING_REVIEW", "CANCELLED", "EXPIRED", "all"] = "all", limit: int = 100) -> list[dict[str, Any]]:
        clauses = ["workspace_id = ?"]
        values: list[Any] = [self.workspace_id]
        if status != "all":
            clauses.append("status = ?")
            values.append(status)
        values.append(max(1, min(limit, 100)))
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._expire_due(connection)
            rows = connection.execute(
                f"SELECT * FROM capability_proposals WHERE {' AND '.join(clauses)} ORDER BY created_at DESC LIMIT ?",
                values,
            ).fetchall()
            connection.commit()
        return [self._decode(row) for row in rows]

    def create_proposal(
        self,
        *,
        capability_id: str,
        summary: str,
        requested_scope: str,
        conversation_id: str | None = None,
    ) -> dict[str, Any]:
        catalog = capability_catalog(self.workspace_root)["capabilities"]
        capability = next((item for item in catalog if item["id"] == capability_id), None)
        if capability is None:
            raise CapabilityNotFound(capability_id)
        proposal_id = "proposal_" + uuid.uuid4().hex
        now = _utcnow()
        created_at = _timestamp(now)
        expires_at = _timestamp(now + timedelta(days=7))
        data = (
            proposal_id, self.workspace_id, capability_id, capability["fingerprint"], capability["effect"],
            summary, requested_scope, conversation_id, "PENDING_REVIEW", 0, created_at, expires_at, created_at,
        )
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "INSERT INTO capability_proposals (id, workspace_id, capability_id, capability_fingerprint, effect, summary, requested_scope, conversation_id, status, revision, created_at, expires_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                data,
            )
            connection.execute(
                "INSERT INTO capability_proposal_events (proposal_id, workspace_id, event_type, revision, occurred_at, details_json) VALUES (?, ?, 'PROPOSED', 0, ?, ?)",
                (proposal_id, self.workspace_id, created_at, json.dumps({"capability_id": capability_id, "effect": capability["effect"]}, sort_keys=True)),
            )
            row = connection.execute("SELECT * FROM capability_proposals WHERE id = ?", (proposal_id,)).fetchone()
            connection.commit()
        return self._decode(row)

    def cancel_proposal(self, proposal_id: str, expected_revision: int) -> dict[str, Any]:
        now = _timestamp()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._expire_due(connection)
            row = connection.execute(
                "SELECT * FROM capability_proposals WHERE id = ? AND workspace_id = ?",
                (proposal_id, self.workspace_id),
            ).fetchone()
            if row is None:
                connection.rollback()
                raise CapabilityProposalNotFound(proposal_id)
            if row["status"] != "PENDING_REVIEW" or row["revision"] != expected_revision:
                connection.commit()
                raise CapabilityProposalConflict(proposal_id)
            connection.execute(
                "UPDATE capability_proposals SET status = 'CANCELLED', revision = revision + 1, updated_at = ? WHERE id = ? AND workspace_id = ? AND revision = ?",
                (now, proposal_id, self.workspace_id, expected_revision),
            )
            connection.execute(
                "INSERT INTO capability_proposal_events (proposal_id, workspace_id, event_type, revision, occurred_at, details_json) VALUES (?, ?, 'CANCELLED', ?, ?, '{}')",
                (proposal_id, self.workspace_id, expected_revision + 1, now),
            )
            saved = connection.execute("SELECT * FROM capability_proposals WHERE id = ?", (proposal_id,)).fetchone()
            connection.commit()
        return self._decode(saved)
