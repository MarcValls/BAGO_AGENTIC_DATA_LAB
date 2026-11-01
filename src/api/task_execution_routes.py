"""Strict local API surface for prepared task execution workflows."""
from __future__ import annotations

import asyncio
from typing import Any
from urllib.parse import urlsplit

from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictStr

from src.agent_tasks.store import TaskError
from src.agent_tasks.task_execution import (
    PlanAcceptInput, PlanEditInput,
    PlanPrepareInput, StopInput, TaskExecutionService,
)


class TaskErrorBody(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    code: StrictStr
    message: StrictStr
    retryable: StrictBool = False
    details: dict[str, Any] = Field(default_factory=dict)


class TaskErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    error: TaskErrorBody


class PlanPrepareResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    execution_id: StrictStr
    plan_id: StrictStr
    plan_revision: int = Field(ge=1)
    plan_sha256: StrictStr
    status: StrictStr
    created_at: StrictStr
    updated_at: StrictStr
    plan: dict[str, Any] | None
    plan_status: StrictStr
    step_results: dict[str, Any]
    current_step: str | None
    stop_requested: StrictBool
    idempotency_key: str | None
    accepted_plan_sha256: str | None


class ExecutionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    execution_id: StrictStr
    plan_id: StrictStr
    plan_revision: int = Field(ge=1)
    plan_sha256: StrictStr
    status: StrictStr
    created_at: StrictStr
    updated_at: StrictStr
    plan: dict[str, Any] | None
    plan_status: StrictStr
    step_results: dict[str, Any]
    current_step: str | None
    stop_requested: StrictBool
    idempotency_key: str | None
    accepted_plan_sha256: str | None
    events: list[dict[str, Any]] = Field(default_factory=list)
    idempotent_replay: StrictBool | None = None


def create_task_execution_router(*, service: TaskExecutionService) -> APIRouter:
    router = APIRouter(tags=["task-execution"])

    def check_origin(request: Request) -> None:
        origin = request.headers.get("origin")
        if not origin:
            return
        supplied, actual = urlsplit(origin), urlsplit(str(request.base_url))
        if (supplied.scheme, supplied.netloc) != (actual.scheme, actual.netloc):
            raise TaskError("origin_rejected", "El origen de la solicitud no está permitido.", 403)

    def error_response(error: TaskError) -> JSONResponse:
        status = error.status
        retryable = status >= 500 or error.code in {"execution_inconclusive", "adapter_unavailable"}
        body = TaskErrorResponse(error=TaskErrorBody(code=error.code, message=error.message,
            retryable=retryable, details={})).model_dump(mode="json")
        return JSONResponse(status_code=status, content=body)

    @router.post("/api/task-executions/plans", response_model=PlanPrepareResponse)
    async def prepare_plan(body: PlanPrepareInput, request: Request, background_tasks: BackgroundTasks):
        try:
            check_origin(request)
            result, is_new = service.reserve_preparation(body)
            if is_new:
                background_tasks.add_task(service.background_prepare, body, result["execution_id"])
            return PlanPrepareResponse.model_validate(result)
        except TaskError as error:
            return error_response(error)

    @router.put("/api/task-executions/plans/{plan_id}", response_model=PlanPrepareResponse)
    async def revise_plan(plan_id: str, body: PlanEditInput, request: Request):
        try:
            check_origin(request)
            result = await asyncio.to_thread(service.revise, plan_id, body)
            return PlanPrepareResponse.model_validate(result)
        except TaskError as error:
            return error_response(error)

    @router.post("/api/task-executions/plans/{plan_id}/accept", response_model=ExecutionResponse)
    async def accept_plan(plan_id: str, body: PlanAcceptInput, request: Request):
        try:
            check_origin(request)
            result = await asyncio.to_thread(service.accept, plan_id, body)
            return ExecutionResponse.model_validate(result)
        except TaskError as error:
            return error_response(error)

    @router.get("/api/task-executions/{execution_id}", response_model=ExecutionResponse)
    async def get_execution(execution_id: str, request: Request):
        try:
            check_origin(request)
            result = await asyncio.to_thread(service.get, execution_id)
            return ExecutionResponse.model_validate(result)
        except TaskError as error:
            return error_response(error)

    @router.post("/api/task-executions/{execution_id}/stop", response_model=ExecutionResponse)
    async def stop_execution(execution_id: str, body: StopInput, request: Request):
        try:
            check_origin(request)
            result = await asyncio.to_thread(service.stop, execution_id, body.reason)
            return ExecutionResponse.model_validate(result)
        except TaskError as error:
            return error_response(error)

    return router

