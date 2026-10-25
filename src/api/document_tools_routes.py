"""Local directory browsing and explicit grants, restricted to configured roots."""
from pathlib import Path
from urllib.parse import urlsplit
import asyncio

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field

from src.agent_tools.document_tools import DOCUMENT_AUTHORIZATIONS, DocumentAccessError, browse


class DocumentGrantRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    owner_id: str = Field(min_length=1, max_length=128)
    conversation_id: str = Field(min_length=1, max_length=128)
    revision: int = Field(ge=0)
    root: str = Field(min_length=1, max_length=1024)
    confirmed: bool = Field(strict=True)
    allow_export: bool = Field(default=False, strict=True)
    expected_output_directory: str | None = Field(default=None, max_length=1024)
    review_work_id: str | None = Field(default=None,max_length=128)
    review_candidate_id: str | None = Field(default=None,max_length=64)
    review_scope_sha256: str | None = Field(default=None,max_length=64)
    contact_id: str | None = Field(default=None,max_length=128)
    allow_draft: bool = Field(default=False,strict=True)


def create_document_tools_router(*, workspace_root, load_agent, owned_conversation, evidence_root,communications=None):
    router = APIRouter()

    def origin_check(request):
        origin = request.headers.get("origin")
        if origin and (urlsplit(origin).scheme, urlsplit(origin).netloc) != (urlsplit(str(request.base_url)).scheme, urlsplit(str(request.base_url)).netloc):
            raise HTTPException(403, detail={"code": "origin_rejected", "message": "Origen no permitido."})

    @router.get("/api/document-tools/folders")
    async def folders(request: Request, path: str | None = None):
        origin_check(request)
        try:
            return await asyncio.to_thread(browse, path, workspace_root())
        except (OSError, ValueError) as error:
            raise HTTPException(422, detail={"code": getattr(error, "code", "document_folder_unavailable"),
                "message": "No se puede explorar esa carpeta dentro del alcance permitido."}) from None

    @router.post("/api/document-tools/authorizations")
    async def authorize(body: DocumentGrantRequest, request: Request):
        origin_check(request)
        record = load_agent(body.owner_id)
        conversation = owned_conversation(body.conversation_id, "agent", body.owner_id)
        if conversation["revision"] != body.revision or conversation.get("status") != "active":
            raise HTTPException(409, detail={"code": "document_conversation_conflict", "message": "La conversación cambió; revisa la carpeta antes de enviar."})
        try:
            return await asyncio.to_thread(DOCUMENT_AUTHORIZATIONS.issue, workspace=workspace_root(),
                owner_id=body.owner_id, conversation_id=body.conversation_id, revision=body.revision,
                root=body.root, confirmed=body.confirmed, allow_export=body.allow_export,
                expected_output_directory=body.expected_output_directory,
                communications=communications() if communications is not None else None,
                review_work_id=body.review_work_id,contact_id=body.contact_id,allow_draft=body.allow_draft,
                review_candidate_id=body.review_candidate_id,review_scope_sha256=body.review_scope_sha256,
                assigned=getattr(record.config, "tools", []), evidence_root=evidence_root())
        except (OSError, ValueError) as error:
            raise HTTPException(422, detail={"code": getattr(error, "code", "document_authorization_failed"),
                "message": "No se pudo autorizar la carpeta. Comprueba alcance, límites y herramientas asignadas."}) from None

    @router.get("/api/document-tools/reports/{receipt_id}")
    async def report(receipt_id: str, owner_id: str, conversation_id: str, request: Request):
        origin_check(request)
        load_agent(owner_id)
        owned_conversation(conversation_id, "agent", owner_id)
        try:
            path = await asyncio.to_thread(DOCUMENT_AUTHORIZATIONS.report, receipt_id,
                                          owner_id=owner_id, conversation_id=conversation_id)
            return FileResponse(path, filename=path.name, headers={"Cache-Control": "no-store"})
        except (OSError, ValueError) as error:
            raise HTTPException(404, detail={"code": getattr(error, "code", "document_report_unavailable"), "message": "El informe ya no está disponible o cambió."}) from None

    return router
