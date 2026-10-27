"""Connection registry, credential isolation and observed governed receipts."""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

from src.providers.registration import _secure_keyring
from src.storage.portable import data_path
from .security import ConnectionError, TIMEOUT, bounded_json, client_for, validate_url
from .transports import list_tools, session_for

ROOT = Path(__file__).resolve().parents[2]
SERVICE = "BAGO.AgenticDataLab.ExternalConnections"
LOCK = threading.RLock()


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def redact(value, secret):
    if not secret:
        return value
    if isinstance(value, str):
        return value.replace(secret, "[REDACTED]")
    if isinstance(value, list):
        return [redact(v, secret) for v in value]
    if isinstance(value, dict):
        return {redact(k, secret): redact(v, secret) for k, v in value.items()}
    return value


def connection_error(error):
    """AnyIO task groups wrap failures; retain only our sanitized errors."""
    if isinstance(error, ConnectionError):
        return error
    for nested in getattr(error, "exceptions", ()):
        found = connection_error(nested)
        if found:
            return found
    return None


def schema_check(schema):
    # No network retrieval of untrusted JSON Schema references.
    def walk(value):
        if isinstance(value, dict):
            if "$ref" in value or "$dynamicRef" in value:
                raise ConnectionError("schema_reference_denied", "El esquema contiene referencias no admitidas.")
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)
    bounded_json(schema)
    walk(schema)
    try:
        jsonschema.Draft202012Validator.check_schema(schema)
    except (jsonschema.SchemaError, RecursionError):
        raise ConnectionError("invalid_schema", "El servidor publicó un esquema no válido.", 502) from None


class ConnectionService:
    def __init__(self, registry_path=None, evidence_dir=None):
        self.registry_path = registry_path or data_path("connections", "registry.json")
        self.evidence_dir = evidence_dir or data_path("traces", "external-connections")

    def _read(self):
        try:
            return json.loads(self.registry_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except (OSError, ValueError):
            raise ConnectionError("registry_unavailable", "No se pudo leer el registro de conexiones.", 503) from None

    def _write(self, records):
        try:
            self.registry_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.registry_path.with_suffix(".tmp")
            temporary.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
            temporary.replace(self.registry_path)
        except OSError:
            raise ConnectionError("registry_unavailable", "No se pudo guardar el registro de conexiones.", 503) from None

    def public(self, record):
        result = {k: v for k, v in record.items() if not k.startswith("_")}
        result["tools"] = [{k: v for k, v in tool.items() if not k.startswith("_")} for tool in record["tools"]]
        return result

    def all(self):
        with LOCK:
            return {"connections": [self.public(r) for r in self._read().values()]}

    def require(self, connection_id):
        with LOCK:
            record = self._read().get(connection_id)
        if record is None:
            raise ConnectionError("connection_not_found", "No existe esta conexión.", 404)
        return record

    def create(self, data):
        name, kind = data["name"].strip(), data["kind"]
        mode = data.get("auth_mode", "none")
        secret = data.get("credential") or ""
        url, profile = data.get("url"), data.get("profile")
        if not name or len(name) > 100 or any(c in name for c in "\r\n"):
            raise ConnectionError("invalid_name", "Introduce un nombre de hasta 100 caracteres.")
        header = data.get("header_name")
        if kind == "docker_mcp":
            if (not profile or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}", profile)
                    or url or mode != "none" or secret or header):
                raise ConnectionError("invalid_docker_profile", "Docker requiere un perfil válido y no admite URL ni credenciales.")
        else:
            if not url or profile:
                raise ConnectionError("invalid_endpoint", "Introduce la URL del servicio.")
            url = validate_url(url, data.get("allow_private", False))
        if mode == "none" and (secret or header):
            raise ConnectionError("unexpected_credential", "Este método no utiliza credenciales.")
        if mode != "none" and (not secret or len(secret) > 8192 or any(c in secret for c in "\r\n")):
            raise ConnectionError("invalid_credential", "Introduce una credencial válida.")
        if mode == "api_key":
            header = header or "X-API-Key"
            if (not re.fullmatch(r"[A-Za-z][A-Za-z0-9-]{0,63}", header)
                    or header.lower() in {"host", "content-length", "connection", "transfer-encoding", "accept", "content-type", "cookie", "proxy-authorization"}
                    or header.lower().startswith("mcp-")):
                raise ConnectionError("invalid_header", "El nombre de cabecera no está permitido.")
        elif header:
            raise ConnectionError("invalid_header", "La cabecera personalizada es solo para API key.")
        if secret and any(secret in str(value) for value in (name, url or "", profile or "", header or "")):
            raise ConnectionError("credential_location", "La credencial solo puede aparecer en el campo seguro.")
        identifier = "conn_" + uuid.uuid4().hex
        record = dict(id=identifier, name=name, kind=kind, url=url, profile=profile,
                      method=data.get("method", "GET") if kind == "http_api" else None,
                      auth_mode=mode, header_name=header, allow_private=data.get("allow_private", False),
                      state="configured", has_credential=bool(secret), tools=[], last_checked_at=None,
                      last_error=None, revision=uuid.uuid4().hex)
        if secret:
            try:
                _secure_keyring().set_password(SERVICE, identifier, secret)
            except Exception:
                raise ConnectionError("secure_store_unavailable", "No está disponible el almacén seguro de credenciales.", 503) from None
        with LOCK:
            records = self._read()
            records[identifier] = record
            self._write(records)
        return self.public(record)

    def delete(self, identifier):
        with LOCK:
            records = self._read()
            record = records.get(identifier)
            if record is None:
                raise ConnectionError("connection_not_found", "No existe esta conexión.", 404)
            if record["has_credential"]:
                try:
                    _secure_keyring().delete_password(SERVICE, identifier)
                except Exception:
                    raise ConnectionError("secure_store_unavailable", "No se pudo eliminar la credencial del almacén seguro.", 503) from None
            del records[identifier]
            self._write(records)
        return {"deleted": True}

    def credentials(self, record):
        if record["auth_mode"] == "none":
            return {}, ""
        try:
            secret = _secure_keyring().get_password(SERVICE, record["id"])
        except Exception:
            secret = None
        if not secret:
            raise ConnectionError("credential_unavailable", "No se pudo obtener la credencial segura.", 503)
        return ({"Authorization": "Bearer " + secret} if record["auth_mode"] == "bearer"
                else {record["header_name"]: secret}), secret

    def _update(self, record, **changes):
        with LOCK:
            records = self._read()
            if record["id"] not in records or records[record["id"]]["revision"] != record["revision"]:
                raise ConnectionError("connection_changed", "La conexión ha cambiado. Vuelve a seleccionarla.", 409)
            records[record["id"]].update(changes)
            self._write(records)
            record.update(changes)

    def descriptor(self, record, tool):
        schema_check(tool.input_schema)
        payload = tool.to_dict()
        return dict(name=tool.name, description=tool.description, input_schema=dict(tool.input_schema),
                    fingerprint=digest({"revision": record["revision"], "descriptor": payload}), _descriptor=payload)

    async def discover(self, identifier, confirmed):
        record = self.require(identifier)
        if confirmed is not True:
            raise ConnectionError("confirmation_required", "Confirma el descubrimiento antes de conectar.", 403)
        headers, secret = self.credentials(record)
        try:
            if record["kind"] == "http_api":
                schema = {"type": "object", "additionalProperties": {"type": ["string", "number", "boolean", "null"]}} if record["method"] == "GET" else {"type": "object"}
                from src.adapters.mcp_adapter import CapabilityDescriptor
                tool = CapabilityDescriptor(record["id"], "http_request", record["method"] + " al endpoint configurado", schema)
                tools = [self.descriptor(record, tool)]
                self._update(record, tools=tools)
            else:
                from src.adapters.mcp_adapter import GovernedMCPAdapter
                async with asyncio.timeout(TIMEOUT):
                    async with session_for(record, headers) as session:
                        adapter = GovernedMCPAdapter(record["id"])
                        discovered = adapter.discover_tools(await list_tools(session))
                        tools = [self.descriptor(record, t) for t in discovered]
                tools = redact(tools, secret)
                self._update(record, tools=tools, state="connected", last_checked_at=now(), last_error=None)
        except ConnectionError as error:
            self._update(record, state="error", last_error={"code": error.code, "message": error.message})
            raise
        except Exception as error:
            safe = connection_error(error)
            if safe:
                self._update(record, state="error", last_error={"code": safe.code, "message": safe.message})
                raise safe from None
            self._update(record, state="error", last_error={"code": "discovery_failed", "message": "No se pudo descubrir el servicio."})
            raise ConnectionError("discovery_failed", "No se pudo descubrir el servicio.", 502) from None
        return {"connection": self.public(record), "tools": self.public(record)["tools"]}

    def receipt(self, record, tool, *, decision="DENY", outcome="DENIED", called=False, result=None, error=None, adapter_receipt=None, secret=""):
        run_id, receipt_id, trace_id = (prefix + uuid.uuid4().hex for prefix in ("connection_run_", "connection_receipt_", "trace_"))
        payload = dict(run_id=run_id, connection_id=record["id"], tool_name=tool,
                       decision=decision, execution_outcome=outcome, actual_effect={"called": called},
                       receipt_id=receipt_id, trace_id=trace_id)
        if result is not None:
            payload["result"] = result
        if error:
            payload["error"] = error
        payload = redact(payload, secret)
        evidence = {**payload, "timestamp": now(), "connection_revision": record["revision"],
                    "adapter_receipt": redact(adapter_receipt, secret),
                    "scope": "Observed transport call/result; remote claims and business effects are not independently validated."}
        raw = json.dumps(evidence, ensure_ascii=False, indent=2).encode("utf-8")
        try:
            self.evidence_dir.mkdir(parents=True, exist_ok=True)
            path = self.evidence_dir / (run_id + ".json")
            path.write_bytes(raw)
        except OSError:
            raise ConnectionError("evidence_unavailable", "No se pudo conservar la evidencia; no se confirma el resultado.", 503) from None
        payload["evidence"] = {"path": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path), "sha256": hashlib.sha256(raw).hexdigest()}
        return payload

    async def invoke(self, identifier, data):
        record = self.require(identifier)
        tool_name, args = data["tool_name"], data["arguments"]
        called, secret = False, ""
        if data["confirmed"] is not True:
            return self.receipt(record, tool_name, error={"code": "confirmation_required", "message": "La operación requiere confirmación explícita."})
        try:
            bounded_json(args)
            tool = next((t for t in record["tools"] if t["name"] == tool_name), None)
            if tool is None or tool["fingerprint"] != data["tool_fingerprint"]:
                raise ConnectionError("stale_tool", "Descubre y selecciona de nuevo la herramienta.", 409)
            schema_check(tool["input_schema"])
            if not jsonschema.Draft202012Validator(tool["input_schema"]).is_valid(args):
                raise ConnectionError("invalid_arguments", "Los argumentos no cumplen el esquema de la herramienta.")
            if record["kind"] == "http_api" and data["effect"] != ("READ" if record["method"] == "GET" else "WRITE"):
                raise ConnectionError("effect_mismatch", "GET requiere READ; POST requiere WRITE.")
            headers, secret = self.credentials(record)
            from src.adapters.mcp_adapter import GovernedMCPAdapter, MCPGovernancePolicy
            adapter = GovernedMCPAdapter(record["id"], policy=MCPGovernancePolicy(auto_allow_effects=frozenset(), timeout_seconds=TIMEOUT))

            async def execute(session, descriptors):
                nonlocal called
                latest = self.require(record["id"])
                if latest["revision"] != record["revision"]:
                    raise ConnectionError("connection_changed", "La conexión ha cambiado. Vuelve a descubrirla.", 409)
                adapter.discover_tools(descriptors)
                adapter.register_tool(tool_name, effect_type=data["effect"], approved_by="adl.local_user")
                request = adapter.build_execution_request(tool_name, args, proposed_by="adl.local_user", context_revision=record["revision"], request_id="connection_request_" + uuid.uuid4().hex)
                permit = adapter.authorize(request, explicit_approval=True, signed_by="adl.local_user")
                class Observed:
                    async def call_tool(self, name, arguments):
                        nonlocal called
                        if self_service.require(record["id"])["revision"] != record["revision"]:
                            raise ConnectionError("connection_changed", "La conexión ha cambiado.", 409)
                        called = True
                        return await session.call_tool(name=name, arguments=arguments)
                self_service = self
                receipt = await adapter.call(Observed(), request, permit)
                if (receipt is None or receipt.request_id != request.request_id or receipt.permit_id != permit.permit_id
                        or receipt.tool_name != tool_name or receipt.server_name != record["id"]
                        or bool(receipt.actual_effect.get("called")) != called or not receipt.receipt_id):
                    raise ConnectionError("receipt_mismatch", "La evidencia de ejecución no coincide con la solicitud.", 502)
                if len(json.dumps(receipt.to_dict(), default=str).encode("utf-8")) > 2 * 1024 * 1024:
                    raise ConnectionError("response_too_large", "La respuesta supera el límite de 2 MiB.", 502)
                return receipt

            async with asyncio.timeout(TIMEOUT + 2):
                if record["kind"] == "http_api":
                    class API:
                        async def call_tool(self, name, arguments):
                            async with client_for(record, headers=headers) as client:
                                response = await client.request(record["method"], record["url"], params=arguments if record["method"] == "GET" else None,
                                                                json=arguments if record["method"] == "POST" else None)
                                response.raise_for_status()
                                try:
                                    content = response.json()
                                except ValueError:
                                    content = response.text
                                return {"status_code": response.status_code, "body": content}
                    descriptor = tool["_descriptor"]
                    receipt = await execute(API(), [{"name": descriptor["name"], "description": descriptor["description"], "inputSchema": descriptor["input_schema"]}])
                else:
                    async with session_for(record, headers) as session:
                        fresh_adapter = GovernedMCPAdapter(record["id"])
                        discovered = await list_tools(session)
                        fresh = fresh_adapter.discover_tools(discovered)
                        current = next((self.descriptor(record, t) for t in fresh if t.name == tool_name), None)
                        if current is None or current["fingerprint"] != tool["fingerprint"]:
                            raise ConnectionError("stale_tool", "El esquema remoto ha cambiado; vuelve a descubrirlo.", 409)
                        receipt = await execute(session, discovered)
            success = receipt.execution_outcome.value == "SUCCESS"
            self._update(record, state="connected" if success else "error", last_checked_at=now(), last_error=None if success else {"code": "invocation_failed", "message": "El servicio no completó la operación."})
            raw_receipt = receipt.to_dict()
            if not success:
                raw_receipt["error_message"] = "El servicio no completó la operación."
            outcome = "SUCCESS" if success else "DENIED" if not called and receipt.decision.value != "ALLOW" else "ERROR"
            return self.receipt(record, tool_name, decision=receipt.decision.value, outcome=outcome, called=called,
                                result=receipt.result if success else None, error=None if success else {"code": "invocation_failed", "message": "El servicio no completó la operación."},
                                adapter_receipt=raw_receipt, secret=secret)
        except ConnectionError as error:
            return self.receipt(record, tool_name, decision="ALLOW" if called else "DENY", outcome="ERROR" if called else "DENIED", called=called,
                                error={"code": error.code, "message": error.message}, secret=secret)
        except Exception as error:
            safe = connection_error(error)
            if safe:
                return self.receipt(record, tool_name, decision="ALLOW" if called else "DENY", outcome="ERROR" if called else "DENIED", called=called,
                                    error={"code": safe.code, "message": safe.message}, secret=secret)
            return self.receipt(record, tool_name, decision="ALLOW", outcome="ERROR", called=called,
                                error={"code": "transport_failed", "message": "No se pudo completar la conexión o la operación."}, secret=secret)
