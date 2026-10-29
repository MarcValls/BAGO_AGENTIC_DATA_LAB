"""Strict HTTP contract for configured external connections."""
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from pydantic import BaseModel, ConfigDict, Field, StrictBool

from src.connections.security import ConnectionError
from src.connections.service import ConnectionService
from src.connections.freelancer_authorization import FreelancerAuthorizationError, FreelancerReadChallenges


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


class FreelancerConnectionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    name: str = Field(min_length=1, max_length=100)
    environment: Literal["sandbox", "production"]
    credential: str = Field(min_length=1, max_length=8192, repr=False)


class FreelancerReadChallenge(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    conversation_id: str = Field(min_length=1, max_length=200)
    conversation_revision: int = Field(ge=0)
    operation: Literal["projects.search", "project.read", "threads.list", "messages.read"]
    arguments: dict[str, Any]


class FreelancerReadApproval(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    challenge_id: str = Field(min_length=20, max_length=100)
    conversation_id: str = Field(min_length=1, max_length=200)
    conversation_revision: int = Field(ge=0)


def create_connection_router(service=None, *, owned_conversation=None, freelancer_challenges=None):
    service = service or ConnectionService()
    freelancer_challenges = freelancer_challenges or FreelancerReadChallenges()
    router = APIRouter(prefix="/api/connections", tags=["connections"], route_class=BoundedConnectionRoute)

    def safe(error):
        return HTTPException(error.status, detail={"code": error.code, "message": error.message})

    def require_browser_origin(request: Request):
        origin = request.headers.get("origin")
        trusted = getattr(request.app.state, "gex_trusted_origins", ())
        if not origin or origin not in trusted:
            raise HTTPException(403, detail={"code": "origin_denied", "message": "Esta operación requiere el origen local autorizado de BAGO."})

    def require_active_assistant_conversation(conversation_id: str, revision: int):
        if owned_conversation is None:
            raise HTTPException(503, detail={"code": "conversation_authority_unavailable", "message": "No está disponible la autoridad de conversaciones."})
        conversation = owned_conversation(conversation_id, "assistant", "app-assistant")
        if conversation.get("status") != "active" or conversation.get("revision") != revision:
            raise HTTPException(409, detail={"code": "conversation_revision_stale", "message": "El chat cambió o ya no está activo. Vuelve a seleccionar la operación."})
        return conversation

    def no_store(payload):
        return JSONResponse(payload, headers={"Cache-Control": "no-store, private", "Pragma": "no-cache", "Vary": "Origin"})

    @router.get("")
    def connections():
        try:
            return service.all()
        except ConnectionError as error:
            raise safe(error) from None

    @router.post("")
    def create(data: CreateConnection, request: Request):
        try:
            return service.create(data.model_dump())
        except ConnectionError as error:
            raise safe(error) from None

    @router.delete("/{identifier}")
    def delete(identifier: str, request: Request):
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

    @router.get("/freelancer")
    def freelancer_connections():
        try:
            return no_store(service.freelancer_all())
        except ConnectionError as error:
            raise safe(error) from None

    @router.post("/freelancer")
    def freelancer_create(data: FreelancerConnectionCreate, request: Request):
        require_browser_origin(request)
        try:
            return no_store(service.freelancer_create(name=data.name, environment=data.environment,
                                                       credential=data.credential))
        except ConnectionError as error:
            raise safe(error) from None

    @router.post("/freelancer/{identifier}/verify")
    async def freelancer_verify(identifier: str, request: Request):
        require_browser_origin(request)
        try:
            return no_store(await service.freelancer_verify(identifier))
        except ConnectionError as error:
            raise safe(error) from None

    @router.delete("/freelancer/{identifier}")
    def freelancer_delete(identifier: str, request: Request):
        require_browser_origin(request)
        try:
            return no_store(service.freelancer_delete(identifier))
        except ConnectionError as error:
            raise safe(error) from None

    @router.post("/freelancer/{identifier}/challenge")
    def freelancer_challenge(identifier: str, data: FreelancerReadChallenge, request: Request):
        require_browser_origin(request)
        require_active_assistant_conversation(data.conversation_id, data.conversation_revision)
        try:
            record = service.freelancer_require(identifier)
            if record.get("state") != "connected" or type(record.get("account_id")) is not int:
                raise HTTPException(409, detail={"code": "account_unverified", "message": "Verifica primero la cuenta en Configuración."})
            challenge = freelancer_challenges.issue(
                connection_id=record["id"], connection_revision=record["revision"],
                environment=record["environment"], account_id=record["account_id"],
                operation=data.operation, arguments=data.arguments,
                conversation_id=data.conversation_id,
                conversation_revision=data.conversation_revision)
            return no_store(challenge)
        except FreelancerAuthorizationError as error:
            raise HTTPException(error.status, detail={"code": error.code, "message": "La operación no se puede autorizar."}) from None
        except ConnectionError as error:
            raise safe(error) from None

    @router.post("/freelancer/{identifier}/read")
    async def freelancer_read(identifier: str, data: FreelancerReadApproval, request: Request):
        require_browser_origin(request)
        require_active_assistant_conversation(data.conversation_id, data.conversation_revision)
        try:
            record = service.freelancer_require(identifier)
            bound = freelancer_challenges.consume(
                data.challenge_id, connection_id=record["id"],
                connection_revision=record["revision"], environment=record["environment"],
                account_id=record["account_id"], conversation_id=data.conversation_id,
                conversation_revision=data.conversation_revision)
            result = await service.freelancer_read(identifier, operation=bound["operation"],
                                                   arguments=bound["arguments"])
            # A read may finish after the user switches or edits conversations.
            # Do not release private response data to a now-stale chat context.
            require_active_assistant_conversation(data.conversation_id, data.conversation_revision)
            return no_store(result)
        except FreelancerAuthorizationError as error:
            raise HTTPException(error.status, detail={"code": error.code, "message": "La autorización venció o no corresponde a esta lectura."}) from None
        except ConnectionError as error:
            raise safe(error) from None

    return router
