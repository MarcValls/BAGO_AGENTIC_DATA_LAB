"""Persistent, deterministic evaluation suites for existing ADL agents.

The store contains only suites, bounded answer previews and grading results.
Provider calls and trace emission are orchestrated by the API layer.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable


class SuiteNotFound(Exception):
    pass


class RunNotFound(Exception):
    pass


class SuiteConflict(Exception):
    pass


class EvaluationValidationError(ValueError):
    pass


_CREDENTIAL_RE = re.compile(
    r"(?:api[_ -]?key|access[_ -]?token|client[_ -]?secret|password|authorization|credential)\s*[:=]\s*\S+|"
    r"\bBearer\s+\S+|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|"
    r"\b(?:github_pat_|gh[pousr]_?|xox[baprs]-|AIza|ya29\.|AKIA|ASIA|sk-|rk-)[A-Za-z0-9_./+=-]{12,}\b|"
    r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b|"
    r"\b[A-Fa-f0-9]{32,}\b",
    re.IGNORECASE,
)
_OPAQUE_VALUE_RE = re.compile(r"(?<![A-Za-z0-9])[A-Za-z0-9_+/=-]{32,}(?![A-Za-z0-9])")


def _has_high_entropy_opaque_value(value: str) -> bool:
    for match in _OPAQUE_VALUE_RE.finditer(value):
        candidate = match.group(0)
        if not (any(char.islower() for char in candidate) and any(char.isupper() for char in candidate) and any(char.isdigit() for char in candidate)):
            continue
        counts = {char: candidate.count(char) for char in set(candidate)}
        entropy = -sum((count / len(candidate)) * math.log2(count / len(candidate)) for count in counts.values())
        if entropy >= 3.5:
            return True
    return False


def contains_credential(value: str) -> bool:
    return bool(_CREDENTIAL_RE.search(value)) or _has_high_entropy_opaque_value(value)


def redact_credentials(value: str) -> str:
    redacted = _CREDENTIAL_RE.sub("[REDACTED]", value)
    return _OPAQUE_VALUE_RE.sub(lambda match: "[REDACTED]" if _has_high_entropy_opaque_value(match.group(0)) else match.group(0), redacted)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def default_database_path(workspace_root: Path | str) -> Path:
    override = os.environ.get("BAGO_AGENT_EVALUATION_DB_PATH")
    if override:
        return Path(override).expanduser().resolve()
    root = Path(workspace_root).resolve()
    identity = str(root).casefold() if os.name == "nt" else str(root)
    workspace_id = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:32]
    local_app_data = os.environ.get("LOCALAPPDATA")
    base = Path(local_app_data) if local_app_data else Path.home() / ".local" / "share"
    return base / "BAGO" / "AgenticDataLab" / "evaluations" / workspace_id / "evaluation.sqlite3"


def validate_cases(cases: Any) -> list[dict[str, Any]]:
    if not isinstance(cases, list) or not 1 <= len(cases) <= 10:
        raise EvaluationValidationError("A suite must contain between 1 and 10 cases.")
    clean: list[dict[str, Any]] = []
    identifiers: set[str] = set()
    for raw in cases:
        if not isinstance(raw, dict) or set(raw) - {"id", "name", "prompt", "must_include", "must_not_include"}:
            raise EvaluationValidationError("Case fields are invalid.")
        case_id = raw.get("id") or "case_" + uuid.uuid4().hex[:16]
        name, prompt = raw.get("name"), raw.get("prompt")
        if not isinstance(case_id, str) or not re.fullmatch(r"case_[A-Za-z0-9_-]{1,64}", case_id) or case_id in identifiers:
            raise EvaluationValidationError("Case IDs must be unique and valid.")
        if not isinstance(name, str) or not name.strip() or len(name) > 100:
            raise EvaluationValidationError("Case name must contain 1 to 100 characters.")
        if not isinstance(prompt, str) or not 1 <= len(prompt.strip()) <= 4000:
            raise EvaluationValidationError("Case prompt must contain 1 to 4000 characters.")
        if contains_credential(prompt):
            raise EvaluationValidationError("Case prompts must not contain credentials.")
        assertions: dict[str, list[str]] = {}
        for field in ("must_include", "must_not_include"):
            values = raw.get(field, [])
            if not isinstance(values, list) or len(values) > 8 or any(not isinstance(v, str) or not 1 <= len(v.strip()) <= 240 for v in values):
                raise EvaluationValidationError("Each assertion list may contain up to 8 strings of 1 to 240 characters.")
            assertions[field] = [v.strip() for v in values]
            if any(contains_credential(value) for value in assertions[field]):
                raise EvaluationValidationError("Assertions must not contain credentials.")
        identifiers.add(case_id)
        clean.append({"id": case_id, "name": name.strip(), "prompt": prompt.strip(), **assertions})
    return clean


def evaluate_answer(answer: str, case: dict[str, Any], trace_saved: bool) -> tuple[list[dict[str, Any]], str]:
    checks = [{"name": "response_non_empty", "passed": bool(answer.strip()), "detail": "Response is non-empty." if answer.strip() else "Response is empty."}]
    folded = answer.casefold()
    for phrase in case["must_include"]:
        found = phrase.casefold() in folded
        checks.append({"name": "must_include", "passed": found, "detail": f"Required text {'found' if found else 'not found'}: {phrase}"})
    for phrase in case["must_not_include"]:
        absent = phrase.casefold() not in folded
        checks.append({"name": "must_not_include", "passed": absent, "detail": f"Forbidden text {'absent' if absent else 'found'}: {phrase}"})
    checks.append({"name": "trace_local_saved", "passed": trace_saved, "detail": "Local trace saved." if trace_saved else "Local trace could not be saved."})
    return checks, "PASS" if all(check["passed"] for check in checks) else "FAIL"


def overall_status(statuses: Iterable[str]) -> str:
    values = list(statuses)
    complete = [value for value in values if value in {"PASS", "FAIL"}]
    errors = sum(value == "ERROR" for value in values)
    if not complete:
        return "ERROR"
    if errors and complete:
        return "PARTIAL"
    return "PASS" if all(value == "PASS" for value in complete) else "FAIL"


def config_fingerprint(config: dict[str, Any]) -> str:
    encoded = json.dumps(config, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class EvaluationStore:
    """Workspace-isolated SQLite suites and immutable run snapshots."""

    def __init__(self, workspace_root: Path | str, database_path: Path | str | None = None) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.database_path = Path(database_path) if database_path else default_database_path(workspace_root)

    def _connect(self) -> sqlite3.Connection:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.database_path, timeout=10, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=10000")
        connection.executescript("""
        CREATE TABLE IF NOT EXISTS suites (
          id TEXT NOT NULL, name TEXT NOT NULL, agent_id TEXT NOT NULL, version INTEGER NOT NULL,
          revision INTEGER NOT NULL, cases_json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
          PRIMARY KEY(id, version)
        );
        CREATE TABLE IF NOT EXISTS suite_heads (
          id TEXT PRIMARY KEY, version INTEGER NOT NULL, revision INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS runs (
          id TEXT PRIMARY KEY, suite_id TEXT NOT NULL, suite_version INTEGER NOT NULL,
          suite_name TEXT NOT NULL, agent_id TEXT NOT NULL, agent_name TEXT NOT NULL,
          agent_config_fingerprint TEXT NOT NULL, provider_id TEXT NOT NULL, model_id TEXT NOT NULL,
          status TEXT NOT NULL, total_cases INTEGER NOT NULL, passed_cases INTEGER NOT NULL,
          failed_cases INTEGER NOT NULL, error_cases INTEGER NOT NULL, duration_ms INTEGER NOT NULL,
          started_at TEXT NOT NULL, completed_at TEXT NOT NULL, payload_json TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS active_suite_runs (
          suite_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, started_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_eval_runs_started ON runs(started_at DESC);
        """)
        return connection

    def acquire_suite_run(self, suite_id: str, run_id: str) -> bool:
        now = datetime.now(timezone.utc)
        started = now.isoformat(timespec="milliseconds").replace("+00:00", "Z")
        expired = (now - timedelta(minutes=30)).isoformat(timespec="milliseconds").replace("+00:00", "Z")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("DELETE FROM active_suite_runs WHERE started_at < ?", (expired,))
            try:
                db.execute("INSERT INTO active_suite_runs VALUES (?, ?, ?)", (suite_id, run_id, started))
            except sqlite3.IntegrityError:
                db.rollback()
                return False
            db.commit()
        return True

    def release_suite_run(self, suite_id: str, run_id: str) -> None:
        with self._connect() as db:
            db.execute("DELETE FROM active_suite_runs WHERE suite_id=? AND run_id=?", (suite_id, run_id))

    @staticmethod
    def _decode_suite(row: sqlite3.Row) -> dict[str, Any]:
        return {"id": row["id"], "name": row["name"], "agent_id": row["agent_id"], "version": row["version"],
                "revision": row["revision"], "cases": json.loads(row["cases_json"]),
                "created_at": row["created_at"], "updated_at": row["updated_at"]}

    def list_suites(self) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute("SELECT s.* FROM suites s JOIN suite_heads h ON h.id=s.id AND h.version=s.version ORDER BY s.updated_at DESC").fetchall()
        return [self._decode_suite(row) for row in rows]

    def get_suite(self, suite_id: str, version: int | None = None) -> dict[str, Any]:
        with self._connect() as db:
            if version is None:
                row = db.execute("SELECT s.* FROM suites s JOIN suite_heads h ON h.id=s.id AND h.version=s.version WHERE s.id=?", (suite_id,)).fetchone()
            else:
                row = db.execute("SELECT * FROM suites WHERE id=? AND version=?", (suite_id, version)).fetchone()
        if row is None:
            raise SuiteNotFound(suite_id)
        return self._decode_suite(row)

    def create_suite(self, name: str, agent_id: str, cases: Any) -> dict[str, Any]:
        cases = validate_cases(cases)
        name = _validate_name(name)
        now, suite_id = utc_now(), "evalsuite_" + uuid.uuid4().hex
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("INSERT INTO suites VALUES (?, ?, ?, 1, 0, ?, ?, ?)", (suite_id, name, agent_id, json.dumps(cases, ensure_ascii=False), now, now))
            db.execute("INSERT INTO suite_heads VALUES (?, 1, 0)", (suite_id,))
            db.commit()
        return self.get_suite(suite_id)

    def update_suite(self, suite_id: str, name: str, agent_id: str, cases: Any, expected_revision: int) -> dict[str, Any]:
        cases, name, now = validate_cases(cases), _validate_name(name), utc_now()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            head = db.execute("SELECT * FROM suite_heads WHERE id=?", (suite_id,)).fetchone()
            if head is None:
                db.rollback()
                raise SuiteNotFound(suite_id)
            if head["revision"] != expected_revision:
                db.rollback()
                raise SuiteConflict(suite_id)
            version, revision = head["version"] + 1, head["revision"] + 1
            db.execute("INSERT INTO suites VALUES (?, ?, ?, ?, ?, ?, (SELECT created_at FROM suites WHERE id=? AND version=?), ?)",
                       (suite_id, name, agent_id, version, revision, json.dumps(cases, ensure_ascii=False), suite_id, head["version"], now))
            db.execute("UPDATE suite_heads SET version=?, revision=? WHERE id=? AND revision=?", (version, revision, suite_id, expected_revision))
            if db.total_changes < 2:
                db.rollback()
                raise SuiteConflict(suite_id)
            db.commit()
        return self.get_suite(suite_id)

    def save_run(self, run: dict[str, Any]) -> dict[str, Any]:
        with self._connect() as db:
            db.execute("INSERT INTO runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (run["id"], run["suite_id"], run["suite_version"], run["suite_name"], run["agent_id"], run["agent_name"],
                 run["agent_config_fingerprint"], run["provider_id"], run["model_id"], run["status"], run["total_cases"],
                 run["passed_cases"], run["failed_cases"], run["error_cases"], run["duration_ms"], run["started_at"], run["completed_at"],
                 json.dumps(run, ensure_ascii=False, separators=(",", ":"))))
        return run

    def list_runs(self, limit: int = 50) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 100))
        with self._connect() as db:
            rows = db.execute("SELECT payload_json FROM runs ORDER BY started_at DESC LIMIT ?", (limit,)).fetchall()
        return [json.loads(row[0]) for row in rows]

    def get_run(self, run_id: str) -> dict[str, Any]:
        with self._connect() as db:
            row = db.execute("SELECT payload_json FROM runs WHERE id=?", (run_id,)).fetchone()
        if row is None:
            raise RunNotFound(run_id)
        return json.loads(row[0])


def _validate_name(name: str) -> str:
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 100:
        raise EvaluationValidationError("Suite name must contain 1 to 100 characters.")
    return name.strip()
