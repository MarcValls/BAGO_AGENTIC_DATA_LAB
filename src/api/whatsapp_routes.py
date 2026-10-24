"""Explicit, local session lifecycle API. Does not expose a send endpoint."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictBool
from src.api.connection_routes import BoundedConnectionRoute
from src.whatsapp import WhatsAppSession


class SessionConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    label: str = Field(min_length=1, max_length=100)
    enabled: StrictBool


class Confirmation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    confirmed: StrictBool


def create_whatsapp_router(session=None, session_factory=None):
    def current():
        return session if session is not None else (session_factory() if session_factory else WhatsAppSession())
    router = APIRouter(prefix="/api/whatsapp/session", tags=["whatsapp"], route_class=BoundedConnectionRoute)

    def perform(action, *args):
        try:
            return action(*args)
        except ValueError:
            raise HTTPException(409, detail={"code": "session_action_rejected", "message": "Revise la configuración y la propiedad del navegador."}) from None
        except Exception:
            raise HTTPException(503, detail={"code": "session_unavailable", "message": "No se pudo comprobar la sesión."}) from None

    @router.get("")
    def status():
        return perform(lambda: current().status())

    @router.put("")
    def configure(body: SessionConfig):
        return perform(lambda: current().configure(body.label, body.enabled))

    @router.post("/open")
    def open_session(body: Confirmation):
        if not body.confirmed:
            raise HTTPException(409, detail="confirmation_required")
        return perform(lambda: current().open())

    @router.post("/close")
    def close_session(body: Confirmation):
        if not body.confirmed:
            raise HTTPException(409, detail="confirmation_required")
        return perform(lambda: current().close())

    return router
