"""Thin same-origin transport for the independently executable Workspace SDK."""
import asyncio
import json
import os
import re
from pathlib import Path
from urllib.parse import urlsplit
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse


def validate_workspace_proposal(data):
    if not isinstance(data, dict) or set(data) - {'intent', 'name', 'path'}:
        raise ValueError('Unknown workspace proposal fields')
    if data.get('intent') not in {'manage', 'create', 'open', 'files', 'git'}:
        raise ValueError('Invalid workspace intent')
    if 'name' in data and (not isinstance(data['name'], str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}', data['name'])):
        raise ValueError('Invalid proposed name')
    if 'path' in data:
        path = data['path']
        if not isinstance(path, str) or not path or len(path) > 240 or path.startswith('/') or '\\' in path or ':' in path or any(part in ('', '.', '..') for part in path.split('/')) or any(ord(c) < 32 for c in path):
            raise ValueError('Invalid proposed path')
    return dict(data)


def create_workspaces_router(parent=None):
    router = APIRouter()

    @router.api_route('/api/workspaces/v1/{path:path}', methods=['GET', 'POST'])
    async def dispatch(path: str, request: Request):
        headers = {'Cache-Control': 'no-store'}
        origin = request.headers.get('origin')
        if origin:
            actual, expected = urlsplit(origin), urlsplit(str(request.base_url))
            if (actual.scheme, actual.netloc) != (expected.scheme, expected.netloc):
                return JSONResponse({'error': {'code': 'origin_rejected', 'message': 'Origen no permitido.'}}, 403, headers=headers)
        configured = parent or os.getenv('BAGO_WORKSPACE_PARENT')
        if path == 'config' and request.method == 'GET':
            return JSONResponse({'configured': bool(configured), 'parent': str(configured) if configured else None,
                                 'scope': 'new_service_created_workspaces', 'remote_execution': False}, headers=headers)
        if not configured:
            return JSONResponse({'error': {'code': 'workspace_parent_required', 'message': 'Configura BAGO_WORKSPACE_PARENT con una carpeta padre dedicada y existente.'}}, 503, headers=headers)
        body = None
        if request.method == 'POST':
            raw = await request.body()
            if len(raw) > 1024 * 1024:
                return JSONResponse({'error': {'code': 'body_too_large', 'message': 'Solicitud demasiado grande.'}}, 413, headers=headers)
            try:
                if request.headers.get('content-type', '').split(';')[0].lower().strip() != 'application/json': raise ValueError()
                body = json.loads(raw)
                if not isinstance(body, dict): raise ValueError()
            except (ValueError, TypeError):
                return JSONResponse({'error': {'code': 'invalid_body', 'message': 'Se requiere un objeto JSON.'}}, 400, headers=headers)
        from src.workspace_sdk import API, ServiceError, WorkspaceService
        try:
            status, payload = await asyncio.to_thread(lambda: API(WorkspaceService(Path(configured))).dispatch(request.method, request.url.path, body))
            return JSONResponse(payload, status, headers=headers)
        except ServiceError as error:
            return JSONResponse({'error': {'code': error.code, 'message': str(error)}}, error.status, headers=headers)
        except Exception:
            return JSONResponse({'error': {'code': 'workspace_unavailable', 'message': 'Operación incompleta. Revisa el estado antes de reintentar.'}}, 503, headers=headers)

    return router
