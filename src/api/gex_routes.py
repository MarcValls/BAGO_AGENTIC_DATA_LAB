"""JSON-only authenticated GEX routes; no legacy execution entry point."""
from __future__ import annotations

from contextlib import asynccontextmanager
import os
from pathlib import Path
import re
import sqlite3
import threading
from urllib.parse import urlsplit

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from src.execution.gex_control import CONTRACT, FIXTURE_ID, ControlError, GexControl, strict_json
from src.execution.ledger.sqlite_ledger import StoreUnavailableError, LedgerError


def create_gex_router(*, load_agent, provider_resolver):
    """One lazy lifetime instance, recovered only once under an OS owner lock.

    W10 sets app.state.gex_trusted_origins to the server's validated CORS list.
    Explicit non-browser Bearer clients may omit Origin. A supplied Origin must
    always match the trusted list, independently of authentication.
    """
    holder, initialization_lock = {}, threading.Lock()

    @asynccontextmanager
    async def lifespan(_app):
        try:
            yield
        finally:
            if holder.get("control"):
                holder["control"].close()
            holder.clear()

    router = APIRouter(prefix="/api/gex", tags=["governed-fixture"], lifespan=lifespan)
    # Exposed only to local host integration/tests, never through HTTP.
    router.gex_holder = holder

    def control():
        with initialization_lock:
            if holder.get("control") is not None:
                return holder["control"]
            if "error" in holder:
                raise ControlError(holder["error"], 503)
            workspace = os.environ.get("BAGO_GEX_WORKSPACE_ROOT")
            state = os.environ.get("BAGO_GEX_STATE_DIR")
            if not state:
                base = Path(os.environ["LOCALAPPDATA"]) if os.environ.get("LOCALAPPDATA") else Path.home() / ".local/share"
                state = str(base / "BAGO/AgenticDataLab/gex/runtime")
            if not workspace:
                holder["error"] = "CONFIGURATION_REQUIRED"
                raise ControlError(holder["error"], 503)
            try:
                holder["control"] = GexControl(state_dir=state, workspace_root=workspace,
                    load_agent=load_agent, provider_resolver=provider_resolver)
                return holder["control"]
            except ControlError as exc:
                holder["error"] = exc.code
            except (StoreUnavailableError, sqlite3.Error, OSError):
                holder["error"] = "STORE_UNAVAILABLE_FAIL_CLOSED"
            except Exception:
                holder["error"] = "CONFIGURATION_INVALID"
            raise ControlError(holder["error"], 503)

    def response(value, status=200):
        return JSONResponse(value, status_code=status, headers={"Cache-Control": "no-store"})

    def error_response(error):
        detail = {"code": error.code, "message": "La operación gobernada no pudo completarse: " + error.code,
                  "persisted": error.persisted}
        if error.view is not None:
            detail["view"] = error.view
            detail["request_id"] = error.view["request_id"]
        return response({"detail": detail}, error.status)

    def trusted_origin(request):
        if len(request.headers.getlist("origin")) > 1:
            raise ControlError("ORIGIN_DENIED", 403)
        origin = request.headers.get("origin")
        if not origin:
            return
        defaults = ["http://localhost:8080", "http://127.0.0.1:8080", "http://localhost:5173", "http://127.0.0.1:5173"]
        port = os.environ.get("BAGO_API_PORT", "8080")
        if port.isdigit() and 1 <= int(port) <= 65535:
            defaults += ["http://localhost:" + port, "http://127.0.0.1:" + port]
        origins = getattr(request.app.state, "gex_trusted_origins", None)
        if origins is None:
            origins = os.environ.get("BAGO_CORS_ORIGINS", ",".join(defaults)).split(",")
        parsed = urlsplit(origin)
        if origin not in origins or parsed.scheme not in {"http", "https"} or parsed.hostname not in {"localhost", "127.0.0.1", "::1"} or parsed.path or parsed.query or parsed.fragment or parsed.username or parsed.password:
            raise ControlError("ORIGIN_DENIED", 403)

    def bearer(request):
        values = request.headers.getlist("authorization")
        if len(values) != 1 or not re.fullmatch(r"Bearer [A-Za-z0-9_-]{1,160}", values[0]):
            raise ControlError("AUTHENTICATION_REQUIRED", 401)
        return values[0][7:]

    async def body(request, fields, required):
        if request.headers.get("content-type", "").split(";")[0].lower() != "application/json":
            raise ControlError("INVALID_REQUEST", 422)
        raw = bytearray()
        async for chunk in request.stream():
            raw.extend(chunk)
            if len(raw) > 32768:
                raise ControlError("INVALID_REQUEST", 422)
        try:
            value = strict_json(bytes(raw))
        except Exception:
            raise ControlError("INVALID_REQUEST", 422) from None
        if not isinstance(value, dict) or set(value) - set(fields) or not set(required).issubset(value):
            raise ControlError("INVALID_REQUEST", 422)
        return value

    def text(value, maximum):
        if not isinstance(value, str) or not 1 <= len(value.strip()) <= maximum:
            raise ControlError("INVALID_REQUEST", 422)
        return value.strip()

    async def invoke(request, operation):
        try:
            if request.method in {"POST", "DELETE", "PUT", "PATCH"}:
                trusted_origin(request)
            return await operation()
        except ControlError as exc:
            # Persist only a sanitized code, never credential headers or body.
            if not exc.persisted and holder.get("control"):
                try:
                    await run_in_threadpool(holder["control"].ledger.record_ingress_denial, exc.code)
                except Exception:
                    return error_response(ControlError("STORE_UNAVAILABLE_FAIL_CLOSED", 503))
            return error_response(exc)
        except (StoreUnavailableError, sqlite3.Error, OSError):
            return error_response(ControlError("STORE_UNAVAILABLE_FAIL_CLOSED", 503))
        except LedgerError:
            return error_response(ControlError("DURABLE_INTEGRITY_INVALID", 409))
        except Exception:
            return error_response(ControlError("CONTROL_UNAVAILABLE_FAIL_CLOSED", 503))

    def session(request):
        token = bearer(request)
        agent_id = request.headers.get("x-gex-agent-id", "")
        if not re.fullmatch(r"agent_[0-9a-f]{8,32}", agent_id):
            raise ControlError("AUTHENTICATION_REQUIRED", 401)
        current = control()
        principal = current.authenticate(token, agent_id)
        return current, principal, token

    @router.get("/status")
    async def status():
        reason = None
        try:
            await run_in_threadpool(lambda: control().check_runtime())
            state = "READY"
        except ControlError as exc:
            reason = exc.code
            state = "UNCONFIGURED" if reason in {"CONFIGURATION_REQUIRED", "CONFIGURATION_INVALID", "NOT_PROVISIONED", "SIGNING_KEY_INVALID", "STATE_INSIDE_WORKSPACE", "WORKSPACE_INVALID"} else "UNAVAILABLE"
        return response({"contract_version": CONTRACT, "state": state, "capability_id": "fixture.read", "fixture_id": FIXTURE_ID,
            "effect": "READ", "synthetic": True, "requires_approval": True, "supported_profile": "single-process-local", "reason_code": reason})

    @router.post("/sessions")
    async def create_session(request: Request):
        async def operation():
            token = bearer(request)
            value = await body(request, {"agent_id", "ttl_seconds"}, {"agent_id"})
            agent_id = text(value["agent_id"], 64)
            ttl = value.get("ttl_seconds", 3600)
            if not re.fullmatch(r"agent_[0-9a-f]{8,32}", agent_id) or type(ttl) is not int or not 60 <= ttl <= 43200:
                raise ControlError("INVALID_REQUEST", 422)
            result = await run_in_threadpool(lambda: control().create_session(token, agent_id, ttl))
            return response(result, 201)
        return await invoke(request, operation)

    @router.delete("/sessions/current")
    async def revoke(request: Request):
        async def operation():
            current, principal, token = await run_in_threadpool(session, request)
            return response(await run_in_threadpool(current.revoke, token, principal))
        return await invoke(request, operation)

    @router.post("/requests")
    async def propose(request: Request):
        async def operation():
            current, principal, _ = await run_in_threadpool(session, request)
            value = await body(request, {"task"}, {"task"})
            return response(await run_in_threadpool(current.propose, text(value["task"], 4000), principal), 201)
        return await invoke(request, operation)

    @router.get("/requests/{request_id}")
    async def retrieve(request_id: str, request: Request):
        async def operation():
            current, principal, _ = await run_in_threadpool(session, request)
            if len(request_id) > 64:
                raise ControlError("REQUEST_NOT_FOUND", 404)
            return response(await run_in_threadpool(current.get, request_id, principal))
        return await invoke(request, operation)

    @router.post("/requests/{request_id}/decision")
    async def decide(request_id: str, request: Request):
        async def operation():
            current, principal, token = await run_in_threadpool(session, request)
            if len(request_id) > 64:
                raise ControlError("REQUEST_NOT_FOUND", 404)
            value = await body(request, {"request_digest", "decision", "reason"}, {"request_digest", "decision", "reason"})
            if not isinstance(value["request_digest"], str) or not re.fullmatch(r"[0-9a-f]{64}", value["request_digest"]) or value["decision"] not in {"APPROVED", "REJECTED", "CANCELLED"}:
                raise ControlError("INVALID_REQUEST", 422)
            return response(await run_in_threadpool(current.decide, request_id, value["request_digest"], value["decision"], text(value["reason"], 1000), principal, token))
        return await invoke(request, operation)

    return router
