"""Atomic agent task edits and durable, append-only task run snapshots."""
from __future__ import annotations

import hashlib
import json
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
