"""Strict HTTP contract for configured external connections."""
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from pydantic import BaseModel, ConfigDict, Field, StrictBool

from src.connections.security import ConnectionError
from src.connections.service import ConnectionService


class BoundedConnectionRoute(APIRoute):
    def get_route_handler(self):
        original = super().get_route_handler()
        async def handler(request: Request):
            origin = request.headers.get("origin")
            trusted = getattr(request.app.state, "gex_trusted_origins", ())
            if origin and origin not in trusted:
                raise HTTPException(403, detail={"code": "origin_denied", "message": "El origen no está autorizado."})
            size, chunks = 0, []
            async for chunk in request.stream():
                size += len(chunk)
                if size > 80 * 1024:
                    raise HTTPException(413, detail={"code": "request_too_large", "message": "La solicitud supera el límite permitido."})
                chunks.append(chunk)
            request._body = b"".join(chunks)
            try:
                return await original(request)
            except RequestValidationError:
                raise HTTPException(422, detail={"code": "invalid_request", "message": "Los datos no son válidos."}) from None
        return handler


class CreateConnection(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    name: str = Field(max_length=100)
    kind: Literal["docker_mcp", "mcp", "http_api"]
    url: str | None = Field(default=None, max_length=2048)
    profile: str | None = Field(default=None, max_length=80)
    method: Literal["GET", "POST"] = "GET"
    auth_mode: Literal["none", "bearer", "api_key"] = "none"
    credential: str | None = Field(default=None, max_length=8192, repr=False)
    header_name: str | None = Field(default=None, max_length=64)
    allow_private: StrictBool = False


class Confirmation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    confirmed: StrictBool


class InvocationRequest(Confirmation):
    tool_name: str = Field(max_length=200)
    arguments: dict[str, Any]
    effect: Literal["READ", "WRITE"]
    tool_fingerprint: str = Field(max_length=128)


def create_connection_router(service=None):
    service = service or ConnectionService()
    router = APIRouter(prefix="/api/connections", tags=["connections"], route_class=BoundedConnectionRoute)

    def safe(error):
        return HTTPException(error.status, detail={"code": error.code, "message": error.message})

    @router.get("")
    def connections():
        try:
            return service.all()
        except ConnectionError as error:
            raise safe(error) from None

    @router.post("")
    def create(data: CreateConnection):
        try:
            return service.create(data.model_dump())
        except ConnectionError as error:
            raise safe(error) from None

    @router.delete("/{identifier}")
    def delete(identifier: str):
        try:
            return service.delete(identifier)
        except ConnectionError as error:
            raise safe(error) from None

    @router.post("/{identifier}/discover")
    async def discover(identifier: str, data: Confirmation):
        try:
            return await service.discover(identifier, data.confirmed)
        except ConnectionError as error:
            raise safe(error) from None

    @router.post("/{identifier}/invoke")
    async def invoke(identifier: str, data: InvocationRequest):
        try:
            return await service.invoke(identifier, data.model_dump())
        except ConnectionError as error:
            raise safe(error) from None

    return router
