"""Atomic agent task edits and durable, append-only task run snapshots."""
from __future__ import annotations

import hashlib
import json
import errno
import os
import re
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TaskDate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    key: str = Field(pattern=r"^[a-z][a-z0-9_]{0,39}$")
    label: str = Field(min_length=1, max_length=80)
    value: str

    @field_validator("label")
    @classmethod
    def label_required(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Date label is required.")
        return value.strip()

    @field_validator("value")
    @classmethod
    def calendar_date(cls, value: str) -> str:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError("Use a YYYY-MM-DD date.")
        date.fromisoformat(value)
        return value


class TaskDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    prompt: str = Field(min_length=1, max_length=8000)
    dates: list[TaskDate] = Field(default_factory=list, max_length=8)

    @field_validator("prompt")
    @classmethod
    def prompt_required(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Task prompt is required.")
        return value.strip()

    @field_validator("dates")
    @classmethod
    def unique_dates(cls, value: list[TaskDate]) -> list[TaskDate]:
        if len({item.key for item in value}) != len(value):
            raise ValueError("Date keys must be unique.")
        return value


class TaskError(Exception):
    def __init__(self, code: str, message: str, status: int = 422):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


def task_revision(task: TaskDefinition | dict[str, Any] | None) -> str:
    value = task.model_dump() if isinstance(task, TaskDefinition) else task
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def render_task(task: TaskDefinition) -> str:
    dates = {item.key: item for item in task.dates}
    used: set[str] = set()

    def substitute(match: re.Match[str]) -> str:
        key = match.group(1).strip()
        if key not in dates:
            raise TaskError("unknown_task_date", "La tarea hace referencia a una fecha que no existe.")
        used.add(key)
        return dates[key].value

    prompt = re.sub(r"\{\{([^{}]*)\}\}", substitute, task.prompt)
    remaining = [item for item in task.dates if item.key not in used]
    if remaining:
        prompt += "\n\nFechas de la tarea:\n" + "\n".join(f"- {item.label} ({item.key}): {item.value}" for item in remaining)
    return prompt


_LOCK = threading.RLock()


@contextmanager
def agent_lock(directory: Path, agent_id: str):
    """Serialize task/profile writes, including across local server processes."""
    if not re.fullmatch(r"agent_[0-9a-f]{8,32}", agent_id):
        raise TaskError("agent_not_found", "Agente no encontrado.", 404)
    with _LOCK:
        locks = directory / ".task-locks"
        locks.mkdir(parents=True, exist_ok=True)
        with (locks / f"{agent_id}.lock").open("a+b") as stream:
            stream.seek(0, os.SEEK_END)
            if stream.tell() == 0:
                stream.write(b"0")
                stream.flush()
            stream.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_LOCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                stream.seek(0)
                if os.name == "nt":
                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def _digest_json(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


class TaskStore:
    def work_history_metadata(self, limit=10000):
        """Read bounded run metadata without creating or migrating storage."""
        from ..work_history import task_metadata

        return task_metadata(self.database_path, limit)

    def __init__(self, database_path: Path | str):
        self.database_path = Path(database_path)

    @contextmanager
    def _db(self):
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.database_path, timeout=20)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                connection.execute("""CREATE TABLE IF NOT EXISTS task_runs (
                    run_id TEXT PRIMARY KEY, agent_id TEXT NOT NULL,
                    snapshot TEXT NOT NULL, created_at TEXT NOT NULL,
                    completed_at TEXT, status TEXT NOT NULL,
                    answer TEXT, error TEXT)""")
                connection.execute("""CREATE TRIGGER IF NOT EXISTS immutable_task_snapshot
                    BEFORE UPDATE OF run_id, agent_id, snapshot, created_at ON task_runs
                    BEGIN SELECT RAISE(ABORT, 'immutable task snapshot'); END""")
                connection.execute("""CREATE TRIGGER IF NOT EXISTS immutable_finished_task_run
                    BEFORE UPDATE ON task_runs WHEN OLD.status != 'running'
                    BEGIN SELECT RAISE(ABORT, 'finished task run'); END""")
                connection.execute("""CREATE TRIGGER IF NOT EXISTS no_delete_task_runs
                    BEFORE DELETE ON task_runs
                    BEGIN SELECT RAISE(ABORT, 'immutable task history'); END""")
                connection.execute("""CREATE TABLE IF NOT EXISTS task_reviews (
                    review_id TEXT PRIMARY KEY, source_agent_id TEXT NOT NULL,
                    source_run_id TEXT NOT NULL, snapshot TEXT NOT NULL, created_at TEXT NOT NULL,
                    completed_at TEXT, status TEXT NOT NULL, answer TEXT, error TEXT)""")
                connection.execute("""CREATE TRIGGER IF NOT EXISTS immutable_task_review_snapshot
                    BEFORE UPDATE OF review_id, source_agent_id, source_run_id, snapshot, created_at ON task_reviews
                    BEGIN SELECT RAISE(ABORT, 'immutable task review snapshot'); END""")
                connection.execute("""CREATE TRIGGER IF NOT EXISTS immutable_finished_task_review
                    BEFORE UPDATE ON task_reviews WHEN OLD.status != 'running'
                    BEGIN SELECT RAISE(ABORT, 'finished task review'); END""")
                connection.execute("""CREATE TRIGGER IF NOT EXISTS no_delete_task_reviews
                    BEFORE DELETE ON task_reviews
                    BEGIN SELECT RAISE(ABORT, 'immutable task reviews'); END""")
                connection.execute("""CREATE TABLE IF NOT EXISTS task_executions (
                    execution_id TEXT PRIMARY KEY, plan_id TEXT NOT NULL UNIQUE,
                    request_id TEXT NOT NULL UNIQUE, request_sha256 TEXT NOT NULL,
                    plan_revision INTEGER NOT NULL, plan_sha256 TEXT NOT NULL,
                    status TEXT NOT NULL, idempotency_key TEXT UNIQUE,
                    accepted_plan_sha256 TEXT, stop_requested INTEGER NOT NULL DEFAULT 0,
                    record_json TEXT NOT NULL, created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL)""")
                connection.execute("""CREATE TABLE IF NOT EXISTS task_execution_events (
                    event_id TEXT PRIMARY KEY, execution_id TEXT NOT NULL,
                    event_type TEXT NOT NULL, payload_json TEXT NOT NULL,
                    payload_sha256 TEXT NOT NULL, created_at TEXT NOT NULL,
                    FOREIGN KEY(execution_id) REFERENCES task_executions(execution_id))""")
                connection.execute("""CREATE TRIGGER IF NOT EXISTS immutable_task_execution_events_update
                    BEFORE UPDATE ON task_execution_events
                    BEGIN SELECT RAISE(ABORT, 'immutable task execution event'); END""")
                connection.execute("""CREATE TRIGGER IF NOT EXISTS immutable_task_execution_events_delete
                    BEFORE DELETE ON task_execution_events
                    BEGIN SELECT RAISE(ABORT, 'immutable task execution event'); END""")
                yield connection
        finally:
            connection.close()

    def read_agent(self, directory: Path, agent_id: str) -> dict[str, Any]:
        if not re.fullmatch(r"agent_[0-9a-f]{8,32}", agent_id):
            raise TaskError("agent_not_found", "Agente no encontrado.", 404)
        try:
            record = json.loads((directory / f"{agent_id}.json").read_text(encoding="utf-8"))
            if record["id"] != agent_id or not isinstance(record["config"], dict):
                raise ValueError()
            task = record["config"].get("task")
            if task is not None:
                TaskDefinition.model_validate(task)
            return record
        except FileNotFoundError:
            raise TaskError("agent_not_found", "Agente no encontrado.", 404) from None
        except (KeyError, TypeError, ValueError, OSError):
            raise TaskError("invalid_agent", "No se puede leer la configuración del agente.", 500) from None

    def task(self, directory: Path, agent_id: str) -> dict[str, Any]:
        record = self.read_agent(directory, agent_id)
        value = record["config"].get("task")
        return {"agent_id": agent_id, "task": value, "revision": task_revision(value)}

    def save_task(self, directory: Path, agent_id: str, task: TaskDefinition, expected_revision: str) -> dict[str, Any]:
        with agent_lock(directory, agent_id):
            record = self.read_agent(directory, agent_id)
            if task_revision(record["config"].get("task")) != expected_revision:
                raise TaskError("task_revision_conflict", "La tarea ha cambiado. Actualiza antes de guardar.", 409)
            record["config"]["task"] = task.model_dump()
            target = directory / f"{agent_id}.json"
            temporary = directory / f".{agent_id}.{uuid.uuid4().hex}.tmp"
            try:
                with temporary.open("x", encoding="utf-8") as stream:
                    json.dump(record, stream, ensure_ascii=False, indent=2)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, target)
            finally:
                temporary.unlink(missing_ok=True)
            return {"agent_id": agent_id, "task": task.model_dump(), "revision": task_revision(task)}

    def start(self, directory: Path, agent_id: str, revision: str, workspace_root: str, source_run_id: str | None, *, validate_model=None) -> dict[str, Any]:
        with agent_lock(directory, agent_id):
            agent = self.read_agent(directory, agent_id)
            config = agent["config"]
            if task_revision(config.get("task")) != revision:
                raise TaskError("task_revision_conflict", "Guarda la versión actual antes de ejecutar.", 409)
            if config.get("task") is None:
                raise TaskError("task_required", "Guarda una tarea antes de ejecutarla.", 409)
            if not config.get("provider_id") or not config.get("model_id"):
                raise TaskError("agent_model_required", "Selecciona proveedor y modelo en el perfil del agente.", 409)
            if validate_model is not None:
                validate_model(config)
            task = TaskDefinition.model_validate(config["task"])
            rendered = render_task(task)
            if source_run_id is not None:
                self.run(agent_id, source_run_id)
            snapshot = {"task_revision": revision, "task_snapshot": task.model_dump(), "rendered_prompt": rendered,
                "provider_id": config["provider_id"], "model_id": config["model_id"], "workspace_root": workspace_root,
                "source_run_id": source_run_id}
            run_id, created = f"taskrun_{uuid.uuid4().hex}", _now()
            with self._db() as db:
                db.execute("INSERT INTO task_runs VALUES (?, ?, ?, ?, NULL, 'running', NULL, NULL)",
                    (run_id, agent_id, json.dumps(snapshot, ensure_ascii=False), created))
            return {**self.run(agent_id, run_id), "_system_prompt": config.get("system_prompt", "")}

    def finish(self, agent_id: str, run_id: str, *, answer: str | None = None, error: dict[str, str] | None = None) -> dict[str, Any]:
        with self._db() as db:
            cursor = db.execute("UPDATE task_runs SET completed_at=?, status=?, answer=?, error=? WHERE run_id=? AND agent_id=? AND status='running'",
                (_now(), "failed" if error else "answered", answer, json.dumps(error) if error else None, run_id, agent_id))
            if cursor.rowcount != 1:
                raise TaskError("task_run_finalized", "La ejecución ya terminó o no existe.", 409)
        return self.run(agent_id, run_id)

    @staticmethod
    def _decode(row: sqlite3.Row) -> dict[str, Any]:
        return {"run_id": row["run_id"], "agent_id": row["agent_id"], **json.loads(row["snapshot"]),
            "created_at": row["created_at"], "completed_at": row["completed_at"], "status": row["status"],
            "answer": row["answer"], "error": json.loads(row["error"]) if row["error"] else None}

    def run(self, agent_id: str, run_id: str) -> dict[str, Any]:
        with self._db() as db:
            row = db.execute("SELECT * FROM task_runs WHERE agent_id=? AND run_id=?", (agent_id, run_id)).fetchone()
        if row is None:
            raise TaskError("task_run_not_found", "Ejecución no encontrada para este agente.", 404)
        return self._decode(row)

    def runs(self, agent_id: str, limit: int) -> list[dict[str, Any]]:
        with self._db() as db:
            rows = db.execute("SELECT * FROM task_runs WHERE agent_id=? ORDER BY created_at DESC, rowid DESC LIMIT ?", (agent_id, limit)).fetchall()
        return [self._decode(row) for row in rows]

    def review_source(self, agent_id: str, run_id: str) -> dict[str, Any]:
        source = self.run(agent_id, run_id)
        if source["status"] != "answered" or not isinstance(source["answer"], str) or not source["answer"].strip():
            raise TaskError("task_review_answer_required", "La revisión requiere una respuesta terminada del agente.", 409)
        return source

    def review_context(self, directory: Path, agent_id: str, run_id: str) -> dict[str, Any]:
        source = self.review_source(agent_id, run_id)
        reviewers, unavailable = [], 0
        for path in sorted(directory.glob("agent_*.json")):
            if path.stem == agent_id:
                continue
            try:
                profile = self.read_agent(directory, path.stem)
                config = profile["config"]
                if not config.get("provider_id") or not config.get("model_id"):
                    unavailable += 1
                    continue
                reviewers.append({"agent_id": path.stem, "name": str(config.get("name", path.stem)),
                    "profile_sha256": task_revision(profile), "provider_id": config["provider_id"], "model_id": config["model_id"]})
            except TaskError:
                unavailable += 1
        return {"source_run": source, "source_sha256": task_revision(source), "reviewers": reviewers,
            "unavailable_reviewer_count": unavailable, "reviews": self.reviews(agent_id, run_id)}

    def start_review(self, directory: Path, agent_id: str, run_id: str, reviewer_agent_id: str,
        expected_source_sha256: str, expected_reviewer_sha256: str, workspace_root: str, *, validate_model=None) -> dict[str, Any]:
        if reviewer_agent_id == agent_id:
            raise TaskError("task_review_same_agent", "Selecciona un agente guardado distinto del autor.", 409)
        with agent_lock(directory, reviewer_agent_id):
            source = self.review_source(agent_id, run_id)
            if task_revision(source) != expected_source_sha256:
                raise TaskError("task_review_source_changed", "La ejecución cambió. Actualiza antes de revisar.", 409)
            profile = self.read_agent(directory, reviewer_agent_id)
            if task_revision(profile) != expected_reviewer_sha256:
                raise TaskError("task_review_profile_changed", "El perfil revisor cambió. Selecciónalo de nuevo.", 409)
            config = profile["config"]
            if not config.get("provider_id") or not config.get("model_id"):
                raise TaskError("agent_model_required", "Selecciona proveedor y modelo en el perfil revisor.", 409)
            if validate_model is not None:
                validate_model(config)
            user_message = json.dumps({"source_agent_id": agent_id, "source_run_id": run_id,
                "source_sha256": expected_source_sha256, "source_snapshot": source}, sort_keys=True, ensure_ascii=False)
            if len(user_message) > 120_000:
                raise TaskError("task_review_source_too_large", "La respuesta supera el límite de revisión textual; no se enviará parcialmente.", 413)
            system_prompt = str(config.get("system_prompt") or "")
            snapshot = {"source_sha256": expected_source_sha256, "source_snapshot": source,
                "reviewer_agent_id": reviewer_agent_id, "reviewer_profile_sha256": expected_reviewer_sha256,
                "reviewer_name": str(config.get("name", reviewer_agent_id)), "provider_id": config["provider_id"],
                "model_id": config["model_id"], "workspace_root": workspace_root, "review_request": user_message,
                "review_policy": "model-only-independent-task-review.v1",
                "reviewer_system_prompt_sha256": hashlib.sha256(system_prompt.encode()).hexdigest()}
            review_id, created = f"taskreview_{uuid.uuid4().hex}", _now()
            with self._db() as db:
                db.execute("INSERT INTO task_reviews VALUES (?, ?, ?, ?, ?, NULL, 'running', NULL, NULL)",
                    (review_id, agent_id, run_id, json.dumps(snapshot, ensure_ascii=False), created))
            return {**self.review(agent_id, run_id, review_id), "_system_prompt": system_prompt}

    @staticmethod
    def _decode_review(row: sqlite3.Row) -> dict[str, Any]:
        return {"review_id": row["review_id"], "source_agent_id": row["source_agent_id"], "source_run_id": row["source_run_id"],
            **json.loads(row["snapshot"]), "created_at": row["created_at"], "completed_at": row["completed_at"],
            "status": row["status"], "answer": row["answer"], "error": json.loads(row["error"]) if row["error"] else None}

    def review(self, agent_id: str, run_id: str, review_id: str) -> dict[str, Any]:
        with self._db() as db:
            row = db.execute("SELECT * FROM task_reviews WHERE source_agent_id=? AND source_run_id=? AND review_id=?",
                (agent_id, run_id, review_id)).fetchone()
        if row is None:
            raise TaskError("task_review_not_found", "Revisión no encontrada para esta ejecución.", 404)
        return self._decode_review(row)

    def reviews(self, agent_id: str, run_id: str) -> list[dict[str, Any]]:
        with self._db() as db:
            rows = db.execute("SELECT * FROM task_reviews WHERE source_agent_id=? AND source_run_id=? ORDER BY created_at DESC, rowid DESC LIMIT 50",
                (agent_id, run_id)).fetchall()
        return [self._decode_review(row) for row in rows]

    def finish_review(self, agent_id: str, run_id: str, review_id: str, *, answer: str | None = None,
        error: dict[str, str] | None = None) -> dict[str, Any]:
        with self._db() as db:
            cursor = db.execute("UPDATE task_reviews SET completed_at=?, status=?, answer=?, error=? WHERE review_id=? AND source_agent_id=? AND source_run_id=? AND status='running'",
                (_now(), "failed" if error else "answered", answer, json.dumps(error) if error else None, review_id, agent_id, run_id))
            if cursor.rowcount != 1:
                raise TaskError("task_review_finalized", "La revisión ya terminó o no existe.", 409)
        return self.review(agent_id, run_id, review_id)

    @staticmethod
    def _append_execution_event(db: sqlite3.Connection, execution_id: str, event_type: str, payload: dict[str, Any]) -> None:
        encoded = _canonical_json(payload)
        db.execute("INSERT INTO task_execution_events VALUES (?, ?, ?, ?, ?, ?)",
            (f"tevent_{uuid.uuid4().hex}", execution_id, event_type, encoded,
             hashlib.sha256(encoded.encode("utf-8")).hexdigest(), _now()))

    @staticmethod
    def _decode_execution(row: sqlite3.Row) -> dict[str, Any]:
        record = json.loads(row["record_json"])
        record.update({"execution_id": row["execution_id"], "plan_id": row["plan_id"],
            "request_sha256": row["request_sha256"],
            "plan_revision": row["plan_revision"], "plan_sha256": row["plan_sha256"],
            "status": row["status"], "idempotency_key": row["idempotency_key"],
            "accepted_plan_sha256": row["accepted_plan_sha256"],
            "stop_requested": bool(row["stop_requested"]),
            "created_at": row["created_at"], "updated_at": row["updated_at"]})
        return record

    def create_execution(self, *, request_id: str, request_sha256: str, plan_id: str,
        plan_sha256: str, record: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        """Persist one prepared plan, deduplicating only an identical request body."""
        now = _now()
        encoded = _canonical_json(record)
        with self._db() as db:
            existing = db.execute("SELECT * FROM task_executions WHERE request_id=?", (request_id,)).fetchone()
            if existing is not None:
                if existing["request_sha256"] != request_sha256:
                    raise TaskError("idempotency_conflict", "Este request_id ya se usó con una solicitud distinta.", 409)
                return self._decode_execution(existing), False
            execution_id = f"taskexec_{uuid.uuid4().hex}"
            db.execute("INSERT INTO task_executions VALUES (?, ?, ?, ?, 1, ?, 'AWAITING_ACCEPTANCE', NULL, NULL, 0, ?, ?, ?)",
                (execution_id, plan_id, request_id, request_sha256, plan_sha256, encoded, now, now))
            self._append_execution_event(db, execution_id, "PREPARED", {
                "plan_id": plan_id, "plan_sha256": plan_sha256, "request_sha256": request_sha256})
            row = db.execute("SELECT * FROM task_executions WHERE execution_id=?", (execution_id,)).fetchone()
        return self._decode_execution(row), True

    def reserve_execution(self, *, request_id: str, request_sha256: str, plan_id: str,
        preparation_owner: str | None = None) -> tuple[dict[str, Any], bool]:
        """Reserve the request before provider calls, preventing concurrent duplicate preparation."""
        now = _now()
        record = {"plan": None, "plan_status": "PREPARING", "step_results": {}, "current_step": None,
            "accepted_at": None, "stop_reason": None, "preparation_owner": preparation_owner}
        with self._db() as db:
            existing = db.execute("SELECT * FROM task_executions WHERE request_id=?", (request_id,)).fetchone()
            if existing is not None:
                if existing["request_sha256"] != request_sha256:
                    raise TaskError("idempotency_conflict", "Este request_id ya se usó con una solicitud distinta.", 409)
                return self._decode_execution(existing), False
            execution_id = f"taskexec_{uuid.uuid4().hex}"
            db.execute("INSERT INTO task_executions VALUES (?, ?, ?, ?, 1, ?, 'PREPARING', NULL, NULL, 0, ?, ?, ?)",
                (execution_id, plan_id, request_id, request_sha256, "0" * 64, _canonical_json(record), now, now))
            self._append_execution_event(db, execution_id, "PREPARATION_RESERVED", {"plan_id": plan_id, "request_sha256": request_sha256})
            row = db.execute("SELECT * FROM task_executions WHERE execution_id=?", (execution_id,)).fetchone()
        return self._decode_execution(row), True

    def finish_execution_preparation(self, execution_id: str, *, plan: dict[str, Any], plan_sha256: str,
        status: str = "AWAITING_ACCEPTANCE") -> dict[str, Any]:
        if status not in {"AWAITING_ACCEPTANCE", "DENIED"}:
            raise TaskError("plan_stale", "Estado de preparación no válido.", 500)
        now = _now()
        with self._db() as db:
            row = db.execute("SELECT * FROM task_executions WHERE execution_id=?", (execution_id,)).fetchone()
            if row is None:
                raise TaskError("execution_not_found", "No se encontró la ejecución solicitada.", 404)
            if row["status"] != "PREPARING" or row["stop_requested"]:
                raise TaskError("plan_not_editable", "La preparación ya no puede completarse.", 409)
            record = json.loads(row["record_json"])
            record["plan"] = plan
            record["plan_status"] = status
            changed = db.execute("UPDATE task_executions SET status=?, plan_sha256=?, record_json=?, updated_at=? WHERE execution_id=? AND status='PREPARING' AND stop_requested=0",
                (status, plan_sha256, _canonical_json(record), now, execution_id))
            if changed.rowcount != 1:
                raise TaskError("plan_not_editable", "La preparación se detuvo antes de quedar lista.", 409)
            self._append_execution_event(db, execution_id, "PLAN_PREPARED" if status == "AWAITING_ACCEPTANCE" else "PLAN_DENIED",
                {"plan_sha256": plan_sha256, "plan_status": status})
            updated = db.execute("SELECT * FROM task_executions WHERE execution_id=?", (execution_id,)).fetchone()
        return self._decode_execution(updated)

    def begin_preparation_action(self, execution_id: str, action: str) -> None:
        now = _now()
        with self._db() as db:
            row = db.execute("SELECT * FROM task_executions WHERE execution_id=?", (execution_id,)).fetchone()
            if row is None:
                raise TaskError("execution_not_found", "No se encontró la ejecución solicitada.", 404)
            record = json.loads(row["record_json"])
            if row["status"] != "PREPARING" or row["stop_requested"]:
                raise TaskError("stop_requested" if row["stop_requested"] else "plan_not_editable",
                    "La preparación se detuvo antes de la siguiente etapa.", 409)
            record["preparation_action"] = action
            changed = db.execute("UPDATE task_executions SET record_json=?, updated_at=? WHERE execution_id=? AND status='PREPARING' AND stop_requested=0",
                (_canonical_json(record), now, execution_id))
            if changed.rowcount != 1:
                raise TaskError("stop_requested", "La preparación recibió STOP antes de la siguiente etapa.", 409)

    def end_preparation_action(self, execution_id: str) -> None:
        now = _now()
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT status,stop_requested,record_json FROM task_executions WHERE execution_id=?", (execution_id,)).fetchone()
            if row is None:
                return
            record = json.loads(row["record_json"])
            record["preparation_action"] = None
            if row["status"] == "STOP_REQUESTED" and row["stop_requested"]:
                record["plan_status"] = "STOPPED_BEFORE_EFFECT"
                record["preparation_failure"] = "stop_requested_after_preparation_action"
                changed = db.execute("UPDATE task_executions SET status='STOPPED_BEFORE_EFFECT', record_json=?, updated_at=? WHERE execution_id=? AND status='STOP_REQUESTED' AND stop_requested=1",
                    (_canonical_json(record), now, execution_id))
                if changed.rowcount:
                    self._append_execution_event(db, execution_id, "PREPARATION_STOPPED_AFTER_ACTION",
                        {"reason_code": "stop_requested_after_preparation_action"})
            elif row["status"] == "PREPARING" and not row["stop_requested"]:
                db.execute("UPDATE task_executions SET record_json=?, updated_at=? WHERE execution_id=? AND status='PREPARING' AND stop_requested=0",
                    (_canonical_json(record), now, execution_id))

    def fail_execution_preparation(self, execution_id: str, reason_code: str) -> dict[str, Any]:
        now = _now()
        with self._db() as db:
            row = db.execute("SELECT * FROM task_executions WHERE execution_id=?", (execution_id,)).fetchone()
            if row is None:
                raise TaskError("execution_not_found", "No se encontró la ejecución solicitada.", 404)
            if row["status"] == "STOP_REQUESTED" and row["stop_requested"]:
                record = json.loads(row["record_json"])
                if record.get("preparation_action") is not None:
                    return self._decode_execution(row)
                record["plan_status"] = "STOPPED_BEFORE_EFFECT"
                record["preparation_failure"] = "stop_requested_after_preparation"
                changed = db.execute("UPDATE task_executions SET status='STOPPED_BEFORE_EFFECT', record_json=?, updated_at=? WHERE execution_id=? AND status='STOP_REQUESTED' AND stop_requested=1 AND json_extract(record_json, '$.preparation_action') IS NULL",
                    (_canonical_json(record), now, execution_id))
                if changed.rowcount:
                    self._append_execution_event(db, execution_id, "PREPARATION_STOPPED",
                        {"reason_code": "stop_requested_after_preparation"})
                updated = db.execute("SELECT * FROM task_executions WHERE execution_id=?", (execution_id,)).fetchone()
                return self._decode_execution(updated)
            if row["status"] != "PREPARING" or row["stop_requested"]:
                return self._decode_execution(row)
            record = json.loads(row["record_json"])
            record["plan_status"] = "FAILED_NO_EFFECT"
            record["preparation_failure"] = reason_code[:80]
            db.execute("UPDATE task_executions SET status='FAILED_NO_EFFECT', record_json=?, updated_at=? WHERE execution_id=? AND status='PREPARING' AND stop_requested=0",
                (_canonical_json(record), now, execution_id))
            self._append_execution_event(db, execution_id, "PREPARATION_FAILED", {"reason_code": reason_code[:80]})
            updated = db.execute("SELECT * FROM task_executions WHERE execution_id=?", (execution_id,)).fetchone()
        return self._decode_execution(updated)

    def reconcile_orphaned_executions(self, active_owner: str) -> int:
        """Mark work owned by confirmed-dead processes inconclusive, never replay it."""
        now = _now()
        count = 0
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            rows = db.execute("SELECT execution_id,status,stop_requested,record_json FROM task_executions WHERE status IN ('PREPARING','ACCEPTED','RUNNING','STOP_REQUESTED')").fetchall()
            for row in rows:
                record = json.loads(row["record_json"])
                previous_status = row["status"]
                if previous_status == "STOP_REQUESTED" and (not row["stop_requested"] or record.get("preparation_action") is None):
                    continue
                preparation_owner = previous_status in {"PREPARING", "STOP_REQUESTED"}
                owner_key = "preparation_owner" if preparation_owner else "dispatch_owner"
                owner = record.get(owner_key)
                if owner == active_owner:
                    continue
                owner_pid = self._owner_pid(owner)
                if owner_pid is None:
                    # Legacy/malformed ownership is not proof that a worker exited.
                    continue
                if self._process_is_alive(owner_pid):
                    # Another live application worker may still own this operation.
                    continue
                terminal_status = "STOPPED_BEFORE_EFFECT" if previous_status == "STOP_REQUESTED" else "INCONCLUSIVE"
                reason_code = "stopped_preparation_owner_exited" if previous_status == "STOP_REQUESTED" else "owner_process_exited"
                record["plan_status"] = terminal_status
                record["recovery"] = {"reason_code": reason_code,
                    "previous_status": previous_status, "recorded_at": now}
                changed = db.execute(
                    "UPDATE task_executions SET status=?, record_json=?, updated_at=? "
                    "WHERE execution_id=? AND status=? AND stop_requested=? "
                    f"AND json_extract(record_json, '$.{owner_key}')=?",
                    (terminal_status, _canonical_json(record), now, row["execution_id"], previous_status,
                        1 if previous_status == "STOP_REQUESTED" else 0, owner))
                if changed.rowcount:
                    event = ("PREPARATION_STOPPED_AFTER_PROCESS_EXIT" if previous_status == "STOP_REQUESTED"
                        else "PREPARATION_INTERRUPTED" if previous_status == "PREPARING" else "EXECUTION_INTERRUPTED")
                    self._append_execution_event(db, row["execution_id"], event,
                        {"reason_code": reason_code, "previous_status": previous_status})
                    count += 1
        return count

    def reconcile_orphaned_preparations(self, active_owner: str) -> int:
        """Compatibility alias for reconciliation of all owner-bound execution states."""
        return self.reconcile_orphaned_executions(active_owner)

    @staticmethod
    def _owner_pid(owner: Any) -> int | None:
        if not isinstance(owner, str):
            return None
        pid_text, separator, token = owner.partition(":")
        if not separator or not token:
            return None
        try:
            pid = int(pid_text)
        except ValueError:
            return None
        return pid if pid > 0 else None

    @staticmethod
    def _process_is_alive(pid: int) -> bool:
        if pid <= 0:
            return False
        if os.name == "nt":
            # Windows interprets os.kill(pid, 0) as CTRL_C_EVENT, which can
            # interrupt the caller's console. Query process state without
            # sending any signal instead.
            import ctypes
            from ctypes import wintypes

            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            query_limited_information = 0x1000
            invalid_parameter = 87
            not_found = 1168
            still_active = 259
            kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            kernel32.OpenProcess.restype = wintypes.HANDLE
            kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
            kernel32.GetExitCodeProcess.restype = wintypes.BOOL
            kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
            kernel32.CloseHandle.restype = wintypes.BOOL
            handle = kernel32.OpenProcess(query_limited_information, False, pid)
            if not handle:
                # Only explicit invalid/missing PID errors prove absence. Access
                # denied and unfamiliar failures are treated conservatively.
                return ctypes.get_last_error() not in {invalid_parameter, not_found}
            try:
                exit_code = wintypes.DWORD()
                if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                    return True
                return exit_code.value == still_active
            finally:
                kernel32.CloseHandle(handle)
        try:
            os.kill(pid, 0)
            return True
        except OSError as error:
            if error.errno == errno.ESRCH or getattr(error, "winerror", None) in {87, 1168}:
                return False
            # Access denied and unknown OS errors are not proof that the owner is dead.
            return True

    def execution(self, execution_id: str) -> dict[str, Any]:
        with self._db() as db:
            row = db.execute("SELECT * FROM task_executions WHERE execution_id=?", (execution_id,)).fetchone()
        if row is None:
            raise TaskError("execution_not_found", "No se encontró la ejecución solicitada.", 404)
        return self._decode_execution(row)

    def execution_by_plan(self, plan_id: str) -> dict[str, Any]:
        with self._db() as db:
            row = db.execute("SELECT * FROM task_executions WHERE plan_id=?", (plan_id,)).fetchone()
        if row is None:
            raise TaskError("plan_not_found", "No se encontró el plan solicitado.", 404)
        return self._decode_execution(row)

    def revise_execution_plan(self, plan_id: str, expected_sha256: str, plan: dict[str, Any], plan_sha256: str) -> dict[str, Any]:
        with self._db() as db:
            row = db.execute("SELECT * FROM task_executions WHERE plan_id=?", (plan_id,)).fetchone()
            if row is None:
                raise TaskError("plan_not_found", "No se encontró el plan solicitado.", 404)
            if row["status"] != "AWAITING_ACCEPTANCE" or row["stop_requested"]:
                raise TaskError("plan_not_editable", "El plan ya no se puede editar.", 409)
            if row["plan_sha256"] != expected_sha256:
                raise TaskError("plan_hash_mismatch", "El plan cambió. Vuelve a cargarlo antes de editar.", 409)
            record = json.loads(row["record_json"])
            record["plan"] = plan
            record["derived_checks"] = []
            record["review"] = {"status": "not_run", "reviewer_id": None, "reviewer_sha256": None}
            revision = row["plan_revision"] + 1
            encoded = _canonical_json(record)
            now = _now()
            changed = db.execute("UPDATE task_executions SET record_json=?, plan_revision=?, plan_sha256=?, updated_at=? WHERE plan_id=? AND plan_sha256=? AND status='AWAITING_ACCEPTANCE'",
                (encoded, revision, plan_sha256, now, plan_id, expected_sha256))
            if changed.rowcount != 1:
                raise TaskError("plan_hash_mismatch", "El plan cambió durante la edición; vuelve a prepararlo.", 409)
            self._append_execution_event(db, row["execution_id"], "PLAN_REVISED", {"plan_revision": revision, "plan_sha256": plan_sha256})
            updated = db.execute("SELECT * FROM task_executions WHERE plan_id=?", (plan_id,)).fetchone()
        return self._decode_execution(updated)

    def accept_execution(self, plan_id: str, expected_sha256: str, expected_revision: int,
        idempotency_key: str, *, dispatch_owner: str) -> tuple[dict[str, Any], bool]:
        if self._owner_pid(dispatch_owner) is None:
            raise TaskError("execution_owner_missing", "No se pudo registrar el propietario de la ejecución.", 503)
        with self._db() as db:
            prior = db.execute("SELECT * FROM task_executions WHERE idempotency_key=?", (idempotency_key,)).fetchone()
            if prior is not None:
                if prior["plan_id"] != plan_id or prior["accepted_plan_sha256"] != expected_sha256:
                    raise TaskError("idempotency_conflict", "La clave de aceptación ya está vinculada a otro plan.", 409)
                return self._decode_execution(prior), False
            row = db.execute("SELECT * FROM task_executions WHERE plan_id=?", (plan_id,)).fetchone()
            if row is None:
                raise TaskError("plan_not_found", "No se encontró el plan solicitado.", 404)
            if row["stop_requested"] or row["status"] == "STOPPED_BEFORE_EFFECT":
                raise TaskError("stop_requested", "La tarea se detuvo antes de aceptar el plan.", 409)
            if row["status"] != "AWAITING_ACCEPTANCE":
                raise TaskError("plan_not_editable", "El plan no está esperando aceptación.", 409)
            if row["plan_sha256"] != expected_sha256 or row["plan_revision"] != expected_revision:
                raise TaskError("plan_hash_mismatch", "El plan visible ya cambió; revisa su versión actual.", 409)
            record = json.loads(row["record_json"])
            record["accepted_at"] = _now()
            record["dispatch_owner"] = dispatch_owner
            encoded = _canonical_json(record)
            changed = db.execute("UPDATE task_executions SET status='ACCEPTED', idempotency_key=?, accepted_plan_sha256=?, record_json=?, updated_at=? WHERE plan_id=? AND status='AWAITING_ACCEPTANCE' AND plan_sha256=? AND plan_revision=? AND stop_requested=0",
                (idempotency_key, expected_sha256, encoded, _now(), plan_id, expected_sha256, expected_revision))
            if changed.rowcount != 1:
                raise TaskError("plan_hash_mismatch", "El plan o su estado cambió antes de aceptar.", 409)
            self._append_execution_event(db, row["execution_id"], "ACCEPTED", {"plan_sha256": expected_sha256, "idempotency_key": idempotency_key})
            result = db.execute("SELECT * FROM task_executions WHERE plan_id=?", (plan_id,)).fetchone()
        return self._decode_execution(result), True

    def set_execution_status(self, execution_id: str, status: str, *, event: str | None = None,
        payload: dict[str, Any] | None = None) -> dict[str, Any]:
        now = _now()
        with self._db() as db:
            row = db.execute("SELECT * FROM task_executions WHERE execution_id=?", (execution_id,)).fetchone()
            if row is None:
                raise TaskError("execution_not_found", "No se encontró la ejecución solicitada.", 404)
            record = json.loads(row["record_json"])
            record["status_updated_at"] = now
            encoded = _canonical_json(record)
            db.execute("UPDATE task_executions SET status=?, record_json=?, updated_at=? WHERE execution_id=?",
                (status, encoded, now, execution_id))
            self._append_execution_event(db, execution_id, event or status, payload or {})
            updated = db.execute("SELECT * FROM task_executions WHERE execution_id=?", (execution_id,)).fetchone()
        return self._decode_execution(updated)

    def begin_execution_step(self, execution_id: str, step_id: str) -> dict[str, Any]:
        now = _now()
        with self._db() as db:
            row = db.execute("SELECT * FROM task_executions WHERE execution_id=?", (execution_id,)).fetchone()
            if row is None:
                raise TaskError("execution_not_found", "No se encontró la ejecución solicitada.", 404)
            record = json.loads(row["record_json"])
            record["current_step"] = step_id
            changed = db.execute("UPDATE task_executions SET record_json=?, updated_at=? WHERE execution_id=? AND status='RUNNING' AND stop_requested=0 AND json_extract(record_json, '$.current_step') IS NULL",
                (_canonical_json(record), now, execution_id))
            if changed.rowcount != 1:
                latest = db.execute("SELECT stop_requested,status FROM task_executions WHERE execution_id=?", (execution_id,)).fetchone()
                if latest is None:
                    raise TaskError("execution_not_found", "No se encontró la ejecución solicitada.", 404)
                if latest["stop_requested"] or latest["status"] in {"STOP_REQUESTED", "STOPPED_BEFORE_EFFECT"}:
                    raise TaskError("stop_requested", "La ejecución recibió STOP antes de admitir el siguiente paso.", 409)
                raise TaskError("execution_not_running", "La ejecución no está en estado RUNNING para iniciar un paso.", 409)
            self._append_execution_event(db, execution_id, "STEP_STARTED", {"step_id": step_id})
            updated = db.execute("SELECT * FROM task_executions WHERE execution_id=?", (execution_id,)).fetchone()
        return self._decode_execution(updated)

    def complete_execution_step(self, execution_id: str, step_id: str, *, status: str,
        receipt: dict[str, Any] | None, reason_code: str | None = None) -> dict[str, Any]:
        now = _now()
        with self._db() as db:
            row = db.execute("SELECT * FROM task_executions WHERE execution_id=?", (execution_id,)).fetchone()
            if row is None:
                raise TaskError("execution_not_found", "No se encontró la ejecución solicitada.", 404)
            record = json.loads(row["record_json"])
            results = record.setdefault("step_results", {})
            if step_id in results:
                prior = results[step_id]
                candidate_sha = _digest_json(receipt) if receipt is not None else None
                if prior.get("receipt_sha256") != candidate_sha:
                    raise TaskError("step_receipt_conflict", "El paso ya tiene un recibo distinto; no se repetirá.", 409)
                return self._decode_execution(row)
            receipt_sha256 = _digest_json(receipt) if receipt is not None else None
            results[step_id] = {"step_id": step_id, "status": status, "receipt": receipt,
                "receipt_sha256": receipt_sha256, "reason_code": reason_code, "completed_at": now}
            record["current_step"] = None
            db.execute("UPDATE task_executions SET record_json=?, updated_at=? WHERE execution_id=?",
                (_canonical_json(record), now, execution_id))
            self._append_execution_event(db, execution_id, "STEP_COMPLETED", {
                "step_id": step_id, "status": status, "receipt_sha256": receipt_sha256, "reason_code": reason_code})
            updated = db.execute("SELECT * FROM task_executions WHERE execution_id=?", (execution_id,)).fetchone()
        return self._decode_execution(updated)

    def request_execution_stop(self, execution_id: str, reason: str) -> dict[str, Any]:
        now = _now()
        with self._db() as db:
            row = db.execute("SELECT * FROM task_executions WHERE execution_id=?", (execution_id,)).fetchone()
            if row is None:
                raise TaskError("execution_not_found", "No se encontró la ejecución solicitada.", 404)
            if row["status"] in {"SUCCEEDED", "FAILED_NO_EFFECT", "PARTIAL", "INCONCLUSIVE", "STOPPED_BEFORE_EFFECT", "STALE", "DENIED"}:
                return self._decode_execution(row)
            record = json.loads(row["record_json"])
            record["stop_reason"] = reason
            record["stop_requested_at"] = now
            in_preparation_action = bool(record.get("preparation_action"))
            status = "STOP_REQUESTED" if in_preparation_action or row["status"] == "RUNNING" else "STOPPED_BEFORE_EFFECT"
            db.execute("UPDATE task_executions SET status=?, stop_requested=1, record_json=?, updated_at=? WHERE execution_id=?",
                (status, _canonical_json(record), now, execution_id))
            self._append_execution_event(db, execution_id, status, {"reason": reason, "current_step": record.get("current_step")})
            updated = db.execute("SELECT * FROM task_executions WHERE execution_id=?", (execution_id,)).fetchone()
        return self._decode_execution(updated)

    def execution_stop_requested(self, execution_id: str) -> bool:
        with self._db() as db:
            row = db.execute("SELECT stop_requested FROM task_executions WHERE execution_id=?", (execution_id,)).fetchone()
        if row is None:
            raise TaskError("execution_not_found", "No se encontró la ejecución solicitada.", 404)
        return bool(row["stop_requested"])

    def list_execution_events(self, execution_id: str) -> list[dict[str, Any]]:
        with self._db() as db:
            rows = db.execute("SELECT event_id,event_type,payload_json,payload_sha256,created_at FROM task_execution_events WHERE execution_id=? ORDER BY created_at,event_id", (execution_id,)).fetchall()
        events = []
        for row in rows:
            raw = row["payload_json"]
            events.append({"event_id": row["event_id"], "event_type": row["event_type"],
                "payload": json.loads(raw), "payload_sha256": row["payload_sha256"], "created_at": row["created_at"]})
        return events
