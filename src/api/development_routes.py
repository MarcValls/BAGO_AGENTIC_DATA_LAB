"""Explicit local host review of staged development changes; no model apply tool."""
import asyncio
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field


class ApplyDevelopmentRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_sha256: str = Field(pattern='^[a-f0-9]{64}$')
    confirmed: bool = Field(strict=True)


def create_development_router(service=None):
    router = APIRouter()

    def instance():
        if service is not None:
            return service()
        from src.development import DevelopmentService
        return DevelopmentService()

    def origin_check(request):
        origin = request.headers.get('origin')
        if origin and urlsplit(origin).netloc != urlsplit(str(request.base_url)).netloc:
            raise HTTPException(403, detail={'code': 'origin_rejected'})

    async def call(request, method, *args, **kwargs):
        origin_check(request)
        try:
            return await asyncio.to_thread(getattr(instance(), method), *args, **kwargs)
        except (OSError, ValueError, RuntimeError) as error:
            raise HTTPException(409, detail={'code': getattr(error, 'code', 'development_unavailable'),
                'message': str(error)[:300]}) from None

    @router.get('/api/development/changes')
    async def changes(request: Request):
        return {'changes': await call(request, 'list_changes')}

    @router.get('/api/development/changes/{change_id}')
    async def inspect(change_id: str, request: Request):
        return await call(request, 'inspect', change_id)

    @router.post('/api/development/changes/{change_id}/apply')
    async def apply(change_id: str, body: ApplyDevelopmentRequest, request: Request):
        return await call(request, 'apply', change_id, **body.model_dump())

    @router.post('/api/development/changes/{change_id}/rollback')
    async def rollback(change_id: str, body: ApplyDevelopmentRequest, request: Request):
        return await call(request, 'rollback', change_id, **body.model_dump())

    return router
