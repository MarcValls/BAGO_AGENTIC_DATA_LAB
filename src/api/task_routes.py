"""Explicit saved task operations; generic agent tool execution stays closed."""
from __future__ import annotations

import asyncio
import hashlib
import os
from pathlib import Path
from typing import Any, Callable

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, StrictBool

from src.agent_tasks import TaskDefinition, TaskError, TaskStore


class SaveTaskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    task: TaskDefinition
    expected_revision: str = Field(pattern=r"^[a-f0-9]{64}$")


class RunTaskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    expected_revision: str = Field(pattern=r"^[a-f0-9]{64}$")
    confirmed: StrictBool
    source_run_id: str | None = Field(default=None, pattern=r"^taskrun_[0-9a-f]{32}$")


def default_history_path(directory: Path) -> Path:
    """Override before the first request for isolated tests/local fixtures."""
    override = os.environ.get("BAGO_TASK_HISTORY_PATH")
    if override:
        return Path(override)
    identity = str(directory.resolve())
    if os.name == "nt":
        identity = identity.casefold()
    namespace = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "BAGO" / "AgenticDataLab" / "tasks" / namespace / "history.sqlite3"


def create_task_router(*, agents_dir: Callable[[], Path], load_agent: Callable[[str], Any],
    workspace_root: Callable[[], Path], generate: Callable[..., str], store: TaskStore | None = None, validate_model=None) -> APIRouter:
    router = APIRouter(prefix="/api/agents", tags=["saved-tasks"])

    def repository() -> TaskStore:
        return store if store is not None else TaskStore(default_history_path(agents_dir()))

    def validate_agent(agent_id: str) -> None:
        try:
            load_agent(agent_id)
        except HTTPException as error:
            raise HTTPException(status_code=error.status_code, detail={"code": "agent_not_found" if error.status_code == 404 else "invalid_agent", "message": "No se puede acceder al agente guardado."}) from None

    def failure(error: TaskError) -> HTTPException:
        return HTTPException(status_code=error.status, detail={"code": error.code, "message": error.message})

    @router.get("/{agent_id}/task")
    async def get_task(agent_id: str):
        validate_agent(agent_id)
        try:
            return repository().task(agents_dir(), agent_id)
        except TaskError as error:
            raise failure(error) from None

    @router.put("/{agent_id}/task")
    async def put_task(agent_id: str, request: SaveTaskRequest):
        validate_agent(agent_id)
        try:
            return repository().save_task(agents_dir(), agent_id, request.task, request.expected_revision)
        except TaskError as error:
            raise failure(error) from None
        except OSError:
            raise HTTPException(status_code=500, detail={"code": "task_save_failed", "message": "No se pudo guardar la tarea."}) from None

    @router.get("/{agent_id}/task-runs")
    async def get_runs(agent_id: str, limit: int = Query(default=50, ge=1, le=100)):
        validate_agent(agent_id)
        runs = repository().runs(agent_id, limit)
        return {"runs": runs, "count": len(runs)}

    @router.get("/{agent_id}/task-runs/{run_id}")
    async def get_run(agent_id: str, run_id: str):
        validate_agent(agent_id)
        try:
            return repository().run(agent_id, run_id)
        except TaskError as error:
            raise failure(error) from None

    @router.post("/{agent_id}/task-runs")
    async def run_task(agent_id: str, request: RunTaskRequest):
        validate_agent(agent_id)
        if request.confirmed is not True:
            raise HTTPException(status_code=403, detail={"code": "task_confirmation_required", "message": "Confirma una nueva ejecución de la tarea."})
        current = repository()
        try:
            run = current.start(agents_dir(), agent_id, request.expected_revision, str(workspace_root()), request.source_run_id, validate_model=validate_model)
        except TaskError as error:
            raise failure(error) from None
        except OSError:
            raise HTTPException(status_code=500, detail={"code": "task_run_save_failed", "message": "No se pudo registrar la ejecución; no se contactó al modelo."}) from None
        messages = [{"role": "system", "content": run.pop("_system_prompt") +
            "\n\nYou do not have app-control, file-write, command-execution, or live tool-execution capabilities in this task. Never claim to have performed them. Return a model response only."},
            {"role": "user", "content": run["rendered_prompt"]}]
        try:
            answer = await asyncio.to_thread(generate, run["provider_id"], run["model_id"], messages)
            if not isinstance(answer, str) or not answer.strip():
                raise ValueError("empty answer")
        except Exception:
            # Provider exceptions can contain credentials, URLs or request bodies.
            # Persist only this fixed public error; the attempted snapshot remains.
            return current.finish(agent_id, run["run_id"], error={"code": "task_provider_failed", "message": "El proveedor no devolvió una respuesta. Revisa su conexión y vuelve a intentarlo."})
        return current.finish(agent_id, run["run_id"], answer=answer)

    return router
