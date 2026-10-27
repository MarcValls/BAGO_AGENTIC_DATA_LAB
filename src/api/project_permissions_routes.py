"""Same-origin HTTP surface for explicit project permission settings."""
from __future__ import annotations

import json
import asyncio
from urllib.parse import urlsplit

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from src.project_permissions import PermissionError, ProjectPermissions


_PUT_FIELDS = {"expected_project_id", "expected_binding", "expected_revision", "read_directories", "write_directories", "confirmed"}
_DELETE_FIELDS = {"expected_project_id", "expected_binding", "expected_revision", "confirmed"}
_DIRECTORY_FIELDS = {"expected_project_id", "expected_binding", "expected_revision", "directory"}
_MAX_BODY = 16 * 1024


def create_project_permissions_router(service) -> APIRouter:
    router = APIRouter()

    def response(payload, status: int = 200):
        return JSONResponse(payload, status_code=status, headers={"Cache-Control": "no-store"})

    def trusted_origin(request: Request) -> None:
        origins = request.headers.getlist("origin")
        if len(origins) > 1:
            raise PermissionError("origin_denied", "The browser origin is not trusted.", 403)
        if not origins:
            return
        origin = origins[0]
        actual = urlsplit(origin)
        if actual.scheme not in {"http", "https"} or actual.hostname not in {"localhost", "127.0.0.1", "::1"} or actual.path or actual.query or actual.fragment or actual.username or actual.password:
            raise PermissionError("origin_denied", "The browser origin is not trusted.", 403)
        configured = getattr(request.app.state, "gex_trusted_origins", None)
        if configured is not None and origin not in configured:
            same_origin = (actual.scheme, actual.netloc) == (urlsplit(str(request.base_url)).scheme, urlsplit(str(request.base_url)).netloc)
            if not same_origin:
                raise PermissionError("origin_denied", "The browser origin is not trusted.", 403)
        elif configured is None:
            same_origin = (actual.scheme, actual.netloc) == (urlsplit(str(request.base_url)).scheme, urlsplit(str(request.base_url)).netloc)
            if not same_origin:
                raise PermissionError("origin_denied", "The browser origin is not trusted.", 403)

    async def read_json(request: Request, allowed: set[str]) -> dict:
        if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/json":
            raise PermissionError("invalid_permission_request", "The permission request is invalid.", 422)
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                if int(content_length) > _MAX_BODY or int(content_length) < 0:
                    raise ValueError
            except ValueError:
                raise PermissionError("invalid_permission_request", "The permission request is invalid.", 422) from None
        raw = bytearray()
        async for chunk in request.stream():
            if len(raw) + len(chunk) > _MAX_BODY:
                raise PermissionError("invalid_permission_request", "The permission request is invalid.", 422)
            raw.extend(chunk)

        def unique_object(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("duplicate field")
                result[key] = value
            return result

        try:
            value = json.loads(bytes(raw), object_pairs_hook=unique_object)
        except (ValueError, UnicodeError, json.JSONDecodeError):
            raise PermissionError("invalid_permission_request", "The permission request is invalid.", 422) from None
        if not isinstance(value, dict) or set(value) != allowed:
            raise PermissionError("invalid_permission_request", "The permission request is invalid.", 422)
        for key in ("expected_project_id", "expected_binding", "expected_revision"):
            if key in value and (not isinstance(value[key], str) or not value[key] or len(value[key]) > 512):
                raise PermissionError("invalid_permission_request", "The permission request is invalid.", 422)
        if "confirmed" in value and value["confirmed"] is not True:
            raise PermissionError("permission_not_confirmed", "Explicit confirmation is required to change project permissions.", 422)
        if "read_directories" in value and (not isinstance(value["read_directories"], list) or any(not isinstance(item, str) for item in value["read_directories"])):
            raise PermissionError("invalid_permission_request", "The permission request is invalid.", 422)
        if "write_directories" in value and (not isinstance(value["write_directories"], list) or any(not isinstance(item, str) for item in value["write_directories"])):
            raise PermissionError("invalid_permission_request", "The permission request is invalid.", 422)
        if "directory" in value and (not isinstance(value["directory"], str) or not value["directory"] or len(value["directory"]) > 4096):
            raise PermissionError("invalid_permission_request", "The permission request is invalid.", 422)
        return value

    @router.get("/api/project-permissions")
    async def get_project_permissions(request: Request):
        try:
            trusted_origin(request)
            return response(await asyncio.to_thread(service().snapshot))
        except PermissionError as error:
            return response({"detail": {"code": error.code, "message": error.message}}, error.status)
        except Exception:
            return response({"detail": {"code": "project_policy_unavailable", "message": "The project permission state is unavailable."}}, 503)

    @router.put("/api/project-permissions")
    async def put_project_permissions(request: Request):
        try:
            trusted_origin(request)
            body = await read_json(request, _PUT_FIELDS)
            result = await asyncio.to_thread(lambda: service().save(**body))
            return response(result)
        except PermissionError as error:
            return response({"detail": {"code": error.code, "message": error.message}}, error.status)
        except Exception:
            return response({"detail": {"code": "project_policy_unavailable", "message": "The project permission state is unavailable."}}, 503)

    @router.delete("/api/project-permissions")
    async def delete_project_permissions(request: Request):
        try:
            trusted_origin(request)
            body = await read_json(request, _DELETE_FIELDS)
            result = await asyncio.to_thread(lambda: service().revoke(**body))
            return response(result)
        except PermissionError as error:
            return response({"detail": {"code": error.code, "message": error.message}}, error.status)
        except Exception:
            return response({"detail": {"code": "project_policy_unavailable", "message": "The project permission state is unavailable."}}, 503)

    @router.post("/api/project-permissions/directories")
    async def browse_project_directories(request: Request):
        try:
            trusted_origin(request)
            body = await read_json(request, _DIRECTORY_FIELDS)
            result = await asyncio.to_thread(lambda: service().browse_directories(**body))
            return response(result)
        except PermissionError as error:
            return response({"detail": {"code": error.code, "message": error.message}}, error.status)
        except Exception:
            return response({"detail": {"code": "directory_listing_unavailable", "message": "The project directory metadata is unavailable."}}, 503)

    return router
