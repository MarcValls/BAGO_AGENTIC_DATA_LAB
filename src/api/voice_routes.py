"""Same-origin chat endpoints for the separately installed local voice runtime."""
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

from src.voice_bridge import VoiceBridge, VoiceBridgeError, MAX_AUDIO_BYTES


class SpeakRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=3000)
    voice: str = Field(default="alex", pattern="^(alex|dora|santa)$")
    speed: float = Field(default=0.95, ge=0.7, le=1.3)


def create_voice_router(bridge: VoiceBridge) -> APIRouter:
    router = APIRouter()

    def check_origin(request: Request) -> None:
        origin = request.headers.get("origin")
        try:
            base = urlsplit(str(request.base_url))
        except ValueError as exc:
            raise HTTPException(403, detail={"code": "host_rejected"}) from exc
        # Voice is a local capability; do not trust a caller-supplied Host as
        # proof that an arbitrary matching Origin is local.
        if (base.scheme not in {"http", "https"} or
                base.hostname not in {"localhost", "127.0.0.1", "::1"} or
                base.username is not None or base.password is not None):
            raise HTTPException(403, detail={"code": "host_rejected"})
        try:
            base_port = base.port
        except ValueError as exc:
            raise HTTPException(403, detail={"code": "host_rejected"}) from exc
        if origin:
            try:
                supplied = urlsplit(origin)
                supplied_port = supplied.port
            except ValueError as exc:
                raise HTTPException(403, detail={"code": "origin_rejected"}) from exc
            if (supplied.scheme != base.scheme or supplied.hostname != base.hostname or
                    supplied_port != base_port or supplied.username is not None or
                    supplied.password is not None or supplied.path or supplied.query or supplied.fragment):
                raise HTTPException(403, detail={"code": "origin_rejected"})

    def run(action):
        try:
            return action()
        except VoiceBridgeError as exc:
            raise HTTPException(exc.status, detail={"code": exc.code}) from exc

    @router.get("/api/voice/status")
    def voice_status(request: Request):
        check_origin(request)
        return run(bridge.status)

    @router.post("/api/voice/speak")
    def speak(body: SpeakRequest, request: Request):
        check_origin(request)
        if not body.text.strip():
            raise HTTPException(422, detail={"code": "voice_text_empty"})
        return run(lambda: bridge.speak(body.text, body.voice, body.speed))

    @router.get("/api/voice/requests/{request_id}")
    def request_status(request_id: str, request: Request):
        check_origin(request)
        return run(lambda: bridge.request_status(request_id))

    @router.post("/api/voice/transcribe")
    async def transcribe(request: Request):
        check_origin(request)
        content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().casefold()
        if content_type not in {"audio/webm", "audio/ogg", "audio/wav", "audio/mp4"}:
            raise HTTPException(415, detail={"code": "voice_audio_format_unsupported"})
        try:
            declared = int(request.headers.get("content-length", "0"))
        except ValueError as exc:
            raise HTTPException(400, detail={"code": "voice_request_invalid"}) from exc
        if declared <= 0 or declared > MAX_AUDIO_BYTES:
            raise HTTPException(413, detail={"code": "voice_audio_too_large"})
        audio = await request.body()
        if len(audio) != declared or len(audio) > MAX_AUDIO_BYTES:
            raise HTTPException(413, detail={"code": "voice_audio_too_large"})
        return await run_in_threadpool(run, lambda: bridge.transcribe(audio, content_type))

    return router
