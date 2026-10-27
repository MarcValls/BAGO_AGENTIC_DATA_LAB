"""Durable, server-resolved GEX principal sessions.

Raw API credentials and session tokens are returned only at issuance time. The
SQLite store keeps SHA-256 token digests, principal/workspace bindings,
server-approved agent scopes, expiry and revocation state. Client supplied
principal or workspace claims are never accepted by the resolver.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Iterator

from src.capabilities.manager import workspace_identity


_PRINCIPAL_ID = re.compile(r"^principal_[a-z0-9][a-z0-9_-]{1,63}$")
_AGENT_ID = re.compile(r"^agent_[0-9a-f]{8,32}$")
_API_TOKEN_PREFIX = "bago_gex_key_v1_"
_SESSION_TOKEN_PREFIX = "bago_gex_session_v1_"
_API_TOKEN = re.compile(r"^bago_gex_key_v1_[A-Za-z0-9_-]{43}$")
_SESSION_TOKEN = re.compile(r"^bago_gex_session_v1_[A-Za-z0-9_-]{43}$")
_MIN_TTL_SECONDS = 60
_MAX_TTL_SECONDS = 12 * 60 * 60


class AuthenticationError(ValueError):
    """Credentials, session state, or requested scope could not be verified."""


class IdentityProvisioningError(ValueError):
    """Trusted provisioning input is invalid or conflicts with stored state."""


@dataclass(frozen=True)
class AuthenticatedPrincipal:
    """Identity context resolved exclusively from server-side session records."""

    principal_id: str
    workspace_id: str
    agent_id: str
    session_id: str
    credential_id: str
    issued_at: str
    expires_at: str


def default_identity_database_path() -> Path:
    """Return a portable identity database path outside the project workspace."""
    from src.storage.portable import configured_path
    return configured_path("BAGO_GEX_IDENTITY_DB_PATH", "gex", "identity.sqlite3")


def _timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("timestamps must include a timezone")
    return value.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("ascii", errors="strict")).hexdigest()


def _new_token(prefix: str) -> str:
    return prefix + secrets.token_urlsafe(32)


class GexIdentityStore:
    """SQLite-backed API credential and revocable session registry.

    Provisioning methods are intended for a trusted local control plane or
    operator tool. This class deliberately exposes no public registration or
    login route and never treats client-supplied identity fields as authority.
    """

    def __init__(self, database_path: Path | str):
        self.database_path = Path(database_path).expanduser().resolve()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.database_path, timeout=5, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA synchronous = FULL")
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            yield connection
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS gex_principals (
                    principal_id TEXT PRIMARY KEY,
                    workspace_id TEXT NOT NULL,
                    allowed_agent_ids_json TEXT NOT NULL,
                    active INTEGER NOT NULL CHECK (active IN (0, 1)),
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS gex_api_credentials (
                    credential_id TEXT PRIMARY KEY,
                    token_sha256 TEXT NOT NULL UNIQUE,
                    principal_id TEXT NOT NULL REFERENCES gex_principals(principal_id),
                    created_at TEXT NOT NULL,
                    revoked_at TEXT
                );
                CREATE TABLE IF NOT EXISTS gex_sessions (
                    session_id TEXT PRIMARY KEY,
                    token_sha256 TEXT NOT NULL UNIQUE,
                    credential_id TEXT NOT NULL REFERENCES gex_api_credentials(credential_id),
                    principal_id TEXT NOT NULL REFERENCES gex_principals(principal_id),
                    workspace_id TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    issued_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    revoked_at TEXT
                );
                CREATE INDEX IF NOT EXISTS gex_sessions_principal_idx
                    ON gex_sessions(principal_id, expires_at);
                """
            )

    def provision_principal(
        self,
        *,
        principal_id: str,
        workspace_root: Path | str,
        allowed_agent_ids: list[str] | tuple[str, ...],
        now: datetime | None = None,
    ) -> tuple[str, str]:
        """Create an operator-provisioned identity and return its one-time API key.

        ``workspace_root`` and allowed agents are trusted provisioning inputs,
        not values accepted from a runtime client. Workspace identity is
        derived with the repository's canonical workspace identity function.
        The returned tuple is (credential_id, raw_api_key); only its digest is
        persisted.
        """

        if not isinstance(principal_id, str) or not _PRINCIPAL_ID.fullmatch(principal_id):
            raise IdentityProvisioningError("principal_id has an invalid format")
        if not isinstance(allowed_agent_ids, (list, tuple)) or not allowed_agent_ids:
            raise IdentityProvisioningError("at least one server-approved agent is required")
        agents = tuple(sorted(set(allowed_agent_ids)))
        if any(not isinstance(agent_id, str) or not _AGENT_ID.fullmatch(agent_id) for agent_id in agents):
            raise IdentityProvisioningError("an allowed agent id has an invalid format")
        try:
            workspace_id, _ = workspace_identity(workspace_root)
        except (OSError, TypeError, ValueError) as exc:
            raise IdentityProvisioningError("workspace could not be resolved") from exc

        timestamp = _timestamp(now or datetime.now(timezone.utc))
        credential_id = "gexcred_" + uuid.uuid4().hex
        api_key = _new_token(_API_TOKEN_PREFIX)
        with self._connection() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    "INSERT INTO gex_principals (principal_id, workspace_id, allowed_agent_ids_json, active, created_at) VALUES (?, ?, ?, 1, ?)",
                    (principal_id, workspace_id, json.dumps(agents, separators=(",", ":")), timestamp),
                )
                connection.execute(
                    "INSERT INTO gex_api_credentials (credential_id, token_sha256, principal_id, created_at, revoked_at) VALUES (?, ?, ?, ?, NULL)",
                    (credential_id, _token_digest(api_key), principal_id, timestamp),
                )
                connection.commit()
            except sqlite3.IntegrityError as exc:
                connection.rollback()
                raise IdentityProvisioningError("principal already exists or provisioning conflicted") from exc
            except Exception:
                connection.rollback()
                raise
        return credential_id, api_key

    def authenticate_credential(self, api_key: str) -> dict[str, object]:
        """Resolve trusted scope before inspecting a requested saved agent.

        No raw credential is persisted or returned. Session issuance still
        rechecks credential/scope in its own atomic transaction.
        """
        if not isinstance(api_key, str) or not _API_TOKEN.fullmatch(api_key):
            raise AuthenticationError("invalid API credential")
        with self._connection() as db:
            row = db.execute("""SELECT p.workspace_id,p.allowed_agent_ids_json
                FROM gex_api_credentials c JOIN gex_principals p USING(principal_id)
                WHERE c.token_sha256=? AND c.revoked_at IS NULL AND p.active=1""",
                (_token_digest(api_key),)).fetchone()
        if row is None:
            raise AuthenticationError("invalid or revoked API credential")
        return {"workspace_id": row["workspace_id"], "allowed_agent_ids": json.loads(row["allowed_agent_ids_json"])}

    def create_session(
        self,
        api_key: str,
        *,
        requested_agent_id: str | None = None,
        ttl_seconds: int = 3600,
        now: datetime | None = None,
    ) -> tuple[str, str]:
        """Authenticate an operator-provisioned API key and mint a bounded session."""

        if not isinstance(ttl_seconds, int) or isinstance(ttl_seconds, bool) or not _MIN_TTL_SECONDS <= ttl_seconds <= _MAX_TTL_SECONDS:
            raise AuthenticationError("requested session lifetime is outside policy")
        if not isinstance(api_key, str) or not _API_TOKEN.fullmatch(api_key):
            raise AuthenticationError("invalid API credential")
        instant = now or datetime.now(timezone.utc)
        issued_at = _timestamp(instant)
        expires_at = _timestamp(instant + timedelta(seconds=ttl_seconds))
        token = _new_token(_SESSION_TOKEN_PREFIX)
        session_id = "gexsess_" + uuid.uuid4().hex
        with self._connection() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                credential = connection.execute(
                    """SELECT c.credential_id, c.principal_id, p.workspace_id, p.allowed_agent_ids_json
                       FROM gex_api_credentials c JOIN gex_principals p USING (principal_id)
                       WHERE c.token_sha256 = ? AND c.revoked_at IS NULL AND p.active = 1""",
                    (_token_digest(api_key),),
                ).fetchone()
                if credential is None:
                    connection.rollback()
                    raise AuthenticationError("invalid or revoked API credential")
                allowed_agents = json.loads(credential["allowed_agent_ids_json"])
                if not allowed_agents:
                    connection.rollback()
                    raise AuthenticationError("principal has no authorized agents")
                if requested_agent_id is None:
                    if len(allowed_agents) != 1:
                        connection.rollback()
                        raise AuthenticationError("select an agent from the server-approved session scope")
                    selected_agent = allowed_agents[0]
                elif requested_agent_id in allowed_agents and _AGENT_ID.fullmatch(requested_agent_id):
                    selected_agent = requested_agent_id
                else:
                    connection.rollback()
                    raise AuthenticationError("requested agent is outside the provisioned scope")
                connection.execute(
                    """INSERT INTO gex_sessions
                       (session_id, token_sha256, credential_id, principal_id, workspace_id, agent_id, issued_at, expires_at, revoked_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL)""",
                    (session_id, _token_digest(token), credential["credential_id"], credential["principal_id"],
                     credential["workspace_id"], selected_agent, issued_at, expires_at),
                )
                connection.commit()
            except AuthenticationError:
                raise
            except Exception:
                connection.rollback()
                raise
        return session_id, token

    def authenticate_session(
        self,
        session_token: str,
        *,
        requested_agent_id: str,
        agent_exists: Callable[[str], bool],
        now: datetime | None = None,
    ) -> AuthenticatedPrincipal:
        """Resolve a session into server-owned principal, workspace, and agent."""

        if not isinstance(session_token, str) or not _SESSION_TOKEN.fullmatch(session_token):
            raise AuthenticationError("invalid session credential")
        if not isinstance(requested_agent_id, str) or not _AGENT_ID.fullmatch(requested_agent_id):
            raise AuthenticationError("requested agent is invalid")
        if not callable(agent_exists):
            raise AuthenticationError("server agent resolver is unavailable")
        with self._connection() as connection:
            row = connection.execute(
                """SELECT s.session_id, s.credential_id, s.principal_id, s.workspace_id, s.agent_id,
                          s.issued_at, s.expires_at, s.revoked_at AS session_revoked,
                          c.revoked_at AS credential_revoked, p.workspace_id AS principal_workspace,
                          p.allowed_agent_ids_json, p.active
                   FROM gex_sessions s
                   JOIN gex_api_credentials c USING (credential_id)
                   JOIN gex_principals p USING (principal_id)
                   WHERE s.token_sha256 = ?""",
                (_token_digest(session_token),),
            ).fetchone()
        instant = now or datetime.now(timezone.utc)
        if instant.tzinfo is None:
            raise AuthenticationError("verification time must include a timezone")
        instant = instant.astimezone(timezone.utc)
        if row is None or row["session_revoked"] is not None or row["credential_revoked"] is not None or not row["active"]:
            raise AuthenticationError("session is invalid or revoked")
        if _parse_timestamp(row["expires_at"]) <= instant:
            raise AuthenticationError("session expired")
        if row["workspace_id"] != row["principal_workspace"]:
            raise AuthenticationError("session workspace binding is invalid")
        allowed_agent_ids = json.loads(row["allowed_agent_ids_json"])
        if requested_agent_id not in allowed_agent_ids or requested_agent_id != row["agent_id"]:
            raise AuthenticationError("requested agent is outside the authenticated session scope")
        try:
            exists = agent_exists(requested_agent_id)
        except Exception as exc:
            raise AuthenticationError("server agent resolver failed") from exc
        if exists is not True:
            raise AuthenticationError("requested agent is unavailable")
        return AuthenticatedPrincipal(
            principal_id=row["principal_id"],
            workspace_id=row["workspace_id"],
            agent_id=requested_agent_id,
            session_id=row["session_id"],
            credential_id=row["credential_id"],
            issued_at=row["issued_at"],
            expires_at=row["expires_at"],
        )

    def revoke_session(
        self,
        session_id: str,
        *,
        requester_session_token: str,
        requester_agent_id: str,
        agent_exists: Callable[[str], bool],
        now: datetime | None = None,
    ) -> bool:
        """Revoke one session after resolving the requester from its live token."""

        requester = self.authenticate_session(
            requester_session_token,
            requested_agent_id=requester_agent_id,
            agent_exists=agent_exists,
            now=now,
        )
        timestamp = _timestamp(now or datetime.now(timezone.utc))
        with self._connection() as connection:
            cursor = connection.execute(
                "UPDATE gex_sessions SET revoked_at = ? WHERE session_id = ? AND principal_id = ? AND revoked_at IS NULL",
                (timestamp, session_id, requester.principal_id),
            )
            return cursor.rowcount == 1

    def revoke_api_credential(
        self,
        credential_id: str,
        *,
        requester_session_token: str,
        requester_agent_id: str,
        agent_exists: Callable[[str], bool],
        now: datetime | None = None,
    ) -> bool:
        """Revoke a credential and its sessions after authenticating the requester."""

        requester = self.authenticate_session(
            requester_session_token,
            requested_agent_id=requester_agent_id,
            agent_exists=agent_exists,
            now=now,
        )
        timestamp = _timestamp(now or datetime.now(timezone.utc))
        with self._connection() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                credential = connection.execute(
                    "SELECT principal_id FROM gex_api_credentials WHERE credential_id = ? AND revoked_at IS NULL",
                    (credential_id,),
                ).fetchone()
                if credential is None or credential["principal_id"] != requester.principal_id:
                    connection.rollback()
                    return False
                connection.execute("UPDATE gex_api_credentials SET revoked_at = ? WHERE credential_id = ?", (timestamp, credential_id))
                connection.execute("UPDATE gex_sessions SET revoked_at = ? WHERE credential_id = ? AND revoked_at IS NULL", (timestamp, credential_id))
                connection.commit()
                return True
            except Exception:
                connection.rollback()
                raise

    def deactivate_principal(self, principal_id: str, *, now: datetime | None = None) -> bool:
        """Trusted operator control: disable a principal and revoke all sessions."""

        timestamp = _timestamp(now or datetime.now(timezone.utc))
        with self._connection() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                cursor = connection.execute("UPDATE gex_principals SET active = 0 WHERE principal_id = ? AND active = 1", (principal_id,))
                if cursor.rowcount != 1:
                    connection.rollback()
                    return False
                connection.execute("UPDATE gex_api_credentials SET revoked_at = ? WHERE principal_id = ? AND revoked_at IS NULL", (timestamp, principal_id))
                connection.execute("UPDATE gex_sessions SET revoked_at = ? WHERE principal_id = ? AND revoked_at IS NULL", (timestamp, principal_id))
                connection.commit()
                return True
            except Exception:
                connection.rollback()
                raise
