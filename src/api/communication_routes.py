"""HTTP editing and explicit human confirmation; chat exposes editing only."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictStr
from src.communications import CommunicationError
from src.api.connection_routes import BoundedConnectionRoute


class ContactRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    phone: str


class DraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    contact_id: str
    text: str
    attachments: list[str] = Field(default_factory=list)
    schedule: dict = Field(default_factory=lambda: {"kind": "now"})
    conversation_id: str | None = None


class DraftEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: str
    contact_id: str | None = None
    text: str | None = None
    attachments: list[str] | None = None
    schedule: dict | None = None
    conversation_id: str | None = None


class Confirmation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    expected_revision: str
    confirmed: bool


class WhatsAppAuthorization(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    enabled: StrictBool
    expected_project_id: StrictStr
    expected_binding: StrictStr
    expected_session_identity: StrictStr
    expected_authorization_revision: StrictStr


def create_communication_router(service=None, service_factory=None):
    router = APIRouter(prefix="/api/communications", tags=["communications"], route_class=BoundedConnectionRoute)

    def call(method, *args, **kwargs):
        try:
            target = service if service is not None else service_factory()
            return getattr(target, method)(*args, **kwargs)
        except CommunicationError as error:
            raise HTTPException(error.status, detail={"code": "communication_error", "message": str(error)}) from None

    @router.get("/contacts")
    def contacts():
        return {"contacts": call("contacts")}

    @router.get("/whatsapp-authorization")
    def whatsapp_authorization():
        return call("whatsapp_authorization")

    @router.put("/whatsapp-authorization")
    def configure_whatsapp_authorization(body: WhatsAppAuthorization):
        return call("set_whatsapp_authorization", **body.model_dump())

    @router.post("/contacts")
    def contact(body: ContactRequest):
        return call("create_contact", **body.model_dump())

    @router.get("/drafts")
    def drafts():
        return {"drafts": call("drafts")}

    @router.post("/drafts")
    def create(body: DraftRequest):
        return call("create_draft", **body.model_dump())

    @router.get("/drafts/{draft_id}")
    def get(draft_id: str):
        return call("get_draft", draft_id)

    @router.patch("/drafts/{draft_id}")
    def edit(draft_id: str, body: DraftEdit):
        return call("update_draft", draft_id, **body.model_dump(exclude_unset=True))

    @router.post("/drafts/{draft_id}/confirm")
    def confirm(draft_id: str, body: Confirmation):
        return call("confirm", draft_id, **body.model_dump())

    @router.post("/drafts/{draft_id}/cancel")
    def cancel(draft_id: str, body: Confirmation):
        return call("cancel", draft_id, **body.model_dump())

    @router.get("/runs")
    def runs():
        return {"runs": call("runs")}

    return router
