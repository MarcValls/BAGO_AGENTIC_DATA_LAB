"""Thin ADL adapter over the independently runnable Contacts Service SDK."""
import asyncio
from contextlib import asynccontextmanager
import json
import os
from pathlib import Path
import threading
from urllib.parse import urlsplit

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse


def create_contacts_router(state_dir=None, api=None):
    instance = api
    lock = threading.Lock()
    service_error_type = ()
    if api is not None:
        from src.contacts_service.core import ServiceError
        service_error_type = ServiceError

    @asynccontextmanager
    async def lifespan(_app):
        nonlocal instance
        try:
            yield
        finally:
            if instance is not None:
                await asyncio.to_thread(instance.google.close)
                if api is None:
                    instance = None

    router = APIRouter(lifespan=lifespan)

    def sdk():
        nonlocal instance, service_error_type
        if instance is None:
            with lock:
                if instance is None:
                    from src.contacts_service.core import API, Contacts, ServiceError
                    service_error_type = ServiceError
                    from src.services.contacts_bridge import contacts_root
                    root = Path(state_dir) if state_dir is not None else contacts_root()
                    instance = API(Contacts(root))
        return instance

    @router.post('/api/contacts/v1/google/configure-file')
    async def configure_google_file(request: Request):
        headers = {'Cache-Control': 'no-store'}
        origin = request.headers.get('origin')
        if origin:
            actual = urlsplit(origin)
            expected = urlsplit(str(request.base_url))
            if (actual.scheme, actual.netloc) != (expected.scheme, expected.netloc):
                return JSONResponse({'error': {'code': 'origin_rejected', 'message': 'Origen de navegador no permitido.'}}, 403, headers=headers)
        raw = bytearray()
        async for chunk in request.stream():
            raw.extend(chunk)
            if len(raw) > 131072:
                return JSONResponse({'error': {'code': 'body_too_large', 'message': 'El archivo OAuth supera el límite permitido.'}}, 413, headers=headers)
        try:
            if request.headers.get('content-type', '').split(';')[0].strip().lower() != 'application/json':
                raise ValueError()
            body = json.loads(raw)
            client_json = body['client_json']
            if not isinstance(body, dict) or not isinstance(client_json, dict):
                raise ValueError()
        except (ValueError, TypeError, KeyError):
            return JSONResponse({'error': {'code': 'invalid_body', 'message': 'Selecciona un archivo JSON OAuth de escritorio válido.'}}, 400, headers=headers)
        try:
            payload = await asyncio.to_thread(lambda: sdk().google.configure({'client_json': client_json}))
            return JSONResponse(payload, 200, headers=headers)
        except Exception as error:
            if service_error_type and isinstance(error, service_error_type):
                return JSONResponse({'error': {'code': error.code, 'message': str(error)}}, error.status, headers=headers)
            return JSONResponse({'error': {'code': 'service_unavailable', 'message': 'No se pudo guardar la configuración local de Google.'}}, 503, headers=headers)

    @router.api_route('/api/contacts/v1/{path:path}', methods=['GET', 'POST', 'PUT', 'DELETE'])
    async def dispatch(path: str, request: Request):
        headers = {'Cache-Control': 'no-store'}
        origin = request.headers.get('origin')
        if origin:
            actual = urlsplit(origin)
            expected = urlsplit(str(request.base_url))
            if (actual.scheme, actual.netloc) != (expected.scheme, expected.netloc):
                return JSONResponse({'error': {'code': 'origin_rejected', 'message': 'Origen de navegador no permitido.'}}, 403, headers=headers)
        body = None
        if request.method != 'GET':
            raw = await request.body()
            if len(raw) > 1024 * 1024:
                return JSONResponse({'error': {'code': 'body_too_large', 'message': 'Solicitud demasiado grande.'}}, 413, headers=headers)
            try:
                if request.headers.get('content-type', '').split(';')[0].strip().lower() != 'application/json':
                    raise ValueError()
                body = json.loads(raw)
                if not isinstance(body, dict):
                    raise ValueError()
            except (ValueError, TypeError):
                return JSONResponse({'error': {'code': 'invalid_body', 'message': 'Se requiere un objeto JSON válido.'}}, 400, headers=headers)
        try:
            target = request.url.path + ('?' + request.url.query if request.url.query else '')
            status, payload = await asyncio.to_thread(lambda: sdk().dispatch(request.method, target, body))
            return JSONResponse(payload, status, headers=headers)
        except Exception as error:
            if service_error_type and isinstance(error, service_error_type):
                return JSONResponse({'error': {'code': error.code, 'message': str(error)}}, error.status, headers=headers)
            return JSONResponse({'error': {'code': 'service_unavailable', 'message': 'No se pudo completar la operación del servicio de contactos.'}}, 503, headers=headers)

    return router
