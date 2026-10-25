"""Same-origin transport for confirmed initialization of an exact project folder."""
import asyncio
import json
from pathlib import Path
import threading
from urllib.parse import urlsplit

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from src.project_folders import ProjectFolderError, ProjectFolders
from src.workspace_sdk import ServiceError


def create_project_folder_router(*, workspace_root, set_workspace_root, pick_directory,
                                 state_directory, binding_identity, legacy_parent=lambda: None,
                                 binding_lock=None):
    router = APIRouter()
    instances, instance_lock = {}, threading.RLock()

    def service():
        directory = Path(state_directory() if callable(state_directory) else state_directory).absolute()
        with instance_lock:
            key = str(directory)
            if key not in instances:
                instances[key] = ProjectFolders(state_directory=directory, workspace_root=workspace_root,
                    set_workspace_root=set_workspace_root, pick_directory=pick_directory,
                    binding_identity=binding_identity, legacy_parent=legacy_parent, binding_lock=binding_lock)
            return instances[key]

    @router.api_route('/api/project-folders/v1/{path:path}', methods=['GET', 'POST'])
    async def dispatch(path: str, request: Request):
        headers = {'Cache-Control': 'no-store'}

        def error(code, message, status, receipt=None):
            body = {'code': code, 'message': message}
            if receipt is not None:
                body['receipt'] = receipt
            return JSONResponse({'error': body}, status, headers=headers)

        origin = request.headers.get('origin')
        if origin:
            try:
                actual, expected = urlsplit(origin), urlsplit(str(request.base_url))
            except ValueError:
                return error('origin_rejected', 'Origen no permitido.', 403)
            if (actual.scheme, actual.netloc) != (expected.scheme, expected.netloc):
                return error('origin_rejected', 'Origen no permitido.', 403)
        body = {}
        if request.method == 'POST':
            raw = await request.body()
            if len(raw) > 1024 * 1024:
                return error('body_too_large', 'Solicitud demasiado grande.', 413)
            try:
                if request.headers.get('content-type', '').split(';')[0].lower().strip() != 'application/json':
                    raise ValueError()
                body = json.loads(raw)
                if not isinstance(body, dict):
                    raise ValueError()
            except (ValueError, TypeError):
                return error('invalid_body', 'Se requiere un objeto JSON.', 400)
        try:
            owner = service()
            if request.method == 'GET' and path == 'config':
                payload = owner.config()
            elif request.method == 'GET' and path == 'workspaces':
                payload = await asyncio.to_thread(owner.workspaces)
            elif request.method == 'POST' and path == 'browse':
                if body:
                    raise ProjectFolderError('invalid_body', 'Examinar no admite campos adicionales.', 422)
                payload = await asyncio.to_thread(owner.browse)
            elif request.method == 'POST' and path == 'plans':
                if set(body) - {'mode', 'path', 'name', 'title', 'expected_workspace_root'}:
                    raise ProjectFolderError('invalid_body', 'El plan contiene campos no admitidos.', 422)
                if not all(isinstance(body.get(key, ''), str) for key in ('mode', 'path', 'name', 'title', 'expected_workspace_root')):
                    raise ProjectFolderError('invalid_body', 'Los campos del plan deben ser texto.', 422)
                payload = await asyncio.to_thread(owner.prepare, mode=body.get('mode', 'existing'),
                    path=body.get('path', ''), name=body.get('name', ''), title=body.get('title', ''),
                    expected_workspace_root=body.get('expected_workspace_root', ''))
            elif request.method == 'POST' and path.startswith('plans/') and path.count('/') == 2 and path.endswith('/apply'):
                if set(body) != {'plan_sha256', 'confirmed'}:
                    raise ProjectFolderError('invalid_body', 'Confirma únicamente el hash del plan exacto.', 422)
                payload = await asyncio.to_thread(owner.apply, path.split('/')[1], **body)
            elif request.method == 'POST' and path.startswith('workspaces/') and path.count('/') == 2 and path.endswith('/actions'):
                status, payload = await asyncio.to_thread(owner.action, path.split('/')[1], body)
                return JSONResponse(payload, status, headers=headers)
            else:
                return error('not_found', 'Ruta no encontrada.', 404)
            return JSONResponse(payload, headers=headers)
        except ProjectFolderError as failure:
            return error(failure.code, str(failure), failure.status, failure.receipt)
        except ServiceError as failure:
            return error(failure.code, str(failure), failure.status)
        except Exception:
            return error('project_folder_unavailable', 'Operación incompleta. Revisa el estado antes de reintentar.', 503)

    return router
