"""Reviewed profile deletion. Conversation, task and trace history stay intact."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictBool

from src.agent_tasks import agent_lock
from src.api.connection_routes import BoundedConnectionRoute
from src.api.task_routes import default_history_path


class DeleteProfileRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    confirmed: StrictBool
    expected_revision: str = Field(pattern=r"^[a-f0-9]{64}$")


def _fail(code, message, status=409):
    raise HTTPException(status, detail={"code": code, "message": message})


def _identity(agent_id):
    if not re.fullmatch(r"agent_[0-9a-f]{8,32}", agent_id):
        _fail("agent_not_found", "Agente no encontrado.", 404)


def _recovery_io_path(path):
    """Explicit extended Windows IO; keep logical paths for ownership validation."""
    path = Path(path).absolute()
    if os.name != 'nt' or str(path).startswith('\\\\?\\'):
        return path
    value = str(path)
    return Path('\\\\?\\UNC\\' + value[2:] if value.startswith('\\\\') else '\\\\?\\' + value)


def _read_profile(directory, agent_id, load_agent):
    if not re.fullmatch(r"agent_[0-9a-f]{8,32}", agent_id):
        _fail("agent_not_found", "Agente no encontrado.", 404)
    path = directory / f"{agent_id}.json"
    if path.is_symlink() or (path.exists() and getattr(path.stat(), "st_file_attributes", 0) & 1024):
        _fail("unsafe_profile", "La ruta del perfil no es un archivo ordinario.")
    load_agent(agent_id)
    try:
        raw = path.read_bytes()
        if json.loads(raw)["id"] != agent_id:
            raise ValueError()
        return path, raw, hashlib.sha256(raw).hexdigest()
    except FileNotFoundError:
        _fail("agent_not_found", "Agente no encontrado.", 404)
    except (OSError, ValueError, KeyError):
        _fail("invalid_profile", "No se pudo comprobar el perfil.", 503)


def active_work(agent_id, *, agents_dir, jobs_dir, gex_state_dir):
    """Read complete durable sources, not a truncated recent-jobs page."""
    reasons = []
    try:
        database = default_history_path(agents_dir)
        if database.exists():
            with sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True) as db:
                if db.execute("SELECT 1 FROM task_runs WHERE agent_id=? AND status='running' LIMIT 1", (agent_id,)).fetchone():
                    reasons.append("saved_task_running")
        if jobs_dir.exists():
            for path in jobs_dir.glob("*.json"):
                job = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(job, dict) or "agent_id" not in job or "status" not in job:
                    raise ValueError()
                if job["agent_id"] == agent_id and job["status"] in {"running", "pending", "queued"}:
                    reasons.append("job_active")
        ledger = gex_state_dir / "execution.sqlite3"
        if ledger.exists():
            with sqlite3.connect(ledger.resolve().as_uri() + "?mode=ro", uri=True) as db:
                for (raw,) in db.execute("SELECT record_json FROM control_records WHERE agent_id=?", (agent_id,)):
                    if json.loads(raw).get("state") in {"APPROVED", "RUNNING"}:
                        reasons.append("governed_execution_active")
    except (OSError, ValueError, sqlite3.Error):
        _fail("activity_unknown", "No se pudo comprobar todo el trabajo activo. El perfil se conserva.", 503)
    return sorted(set(reasons))


def create_agent_management_router(*, agents_dir, load_agent, jobs_dir=None, active_check=None):
    router = APIRouter(prefix="/api/agents", tags=["agent-management"], route_class=BoundedConnectionRoute)

    def blockers(agent_id):
        if active_check is not None:
            return active_check(agent_id)
        from src import jobs
        from src.storage.portable import configured_path
        state = configured_path("BAGO_GEX_STATE_DIR", "gex", "runtime")
        return active_work(agent_id, agents_dir=agents_dir(), jobs_dir=Path(jobs_dir or jobs.JOBS_DIR), gex_state_dir=state)

    @router.get("/{agent_id}/deletion-review")
    def review(agent_id: str):
        _identity(agent_id)
        with agent_lock(agents_dir(), agent_id):
            _, raw, revision = _read_profile(agents_dir(), agent_id, load_agent)
            profile = json.loads(raw)
            active = blockers(agent_id)
            return {"agent_id": agent_id, "name": profile["config"]["name"], "revision": revision,
                    "deletable": not active, "blockers": active,
                    "preserved": ["conversations", "traces", "task_runs", "evaluations", "jobs"]}

    @router.delete("/{agent_id}")
    def delete(agent_id: str, request: DeleteProfileRequest):
        _identity(agent_id)
        if request.confirmed is not True:
            _fail("confirmation_required", "Confirma expresamente la eliminación del perfil.", 403)
        with agent_lock(agents_dir(), agent_id):
            path, raw, revision = _read_profile(agents_dir(), agent_id, load_agent)
            if revision != request.expected_revision:
                _fail("profile_revision_conflict", "El perfil cambió. Actualiza y revisa de nuevo antes de eliminar.")
            if blockers(agent_id):
                _fail("agent_busy", "Hay trabajo activo de este agente. Espera a que termine antes de eliminar.")
            try:
                # Keep an exact local recovery copy before removing the selectable profile.
                archive = agents_dir() / ".deleted" / f"{agent_id}-{revision}.json"
                archive_io = _recovery_io_path(archive)
                _recovery_io_path(archive.parent).mkdir(parents=True, exist_ok=True)
                if archive.parent.resolve().parent != agents_dir().resolve() or archive_io.is_symlink():
                    _fail("archive_unsafe", "La carpeta de recuperación no es segura.", 503)
                if archive_io.exists() and getattr(archive_io.lstat(), "st_file_attributes", 0) & 1024:
                    _fail("archive_unsafe", "La copia de recuperación no es un archivo ordinario.", 503)
                with archive_io.open("xb") as stream:
                    stream.write(raw)
                    stream.flush()
                    os.fsync(stream.fileno())
            except FileExistsError:
                pass  # Revalidate an existing recovery copy below; never overwrite it.
            except OSError:
                _fail("archive_failed", "No se pudo conservar el perfil. No se eliminó.", 503)
            try:
                if archive_io.read_bytes() != raw:
                    _fail("archive_conflict", "La copia de recuperación no coincide. El perfil se conserva.", 503)
            except OSError:
                _fail("archive_failed", "No se pudo comprobar la copia. El perfil se conserva.", 503)
            try:
                if hashlib.sha256(path.read_bytes()).hexdigest() != revision:
                    _fail("profile_revision_conflict", "El perfil cambió durante la operación.")
                path.unlink()
            except OSError:
                _fail("delete_failed", "No se pudo eliminar el perfil.", 503)
            return {"id": agent_id, "state": "deleted", "revision": revision,
                    "deleted_at": datetime.now(timezone.utc).isoformat(), "history_preserved": True}

    return router
