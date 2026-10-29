"""Freelancer API read transport candidate; not a new authorization boundary.

Dormant until the ADL host wires it behind its existing permission/receipt path.
The host must resolve credentials from its secure store and authorize the exact
operation, arguments, account, environment and connection revision before calling.
No route, CLI, secret persistence, receipt store or write operation is installed.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any, Callable

_ORIGINS = {
    "sandbox": "https://www.freelancer-sandbox.com",
    "production": "https://www.freelancer.com",
}
_LIMIT = 2 * 1024 * 1024
_TIMEOUT = 20
_OPERATIONS = frozenset({
    "account.read", "projects.search", "project.read", "threads.list", "messages.read",
})


class FreelancerReadError(Exception):
    """Sanitized error: never includes credentials or remote response text."""
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _integer(value: Any, minimum: int, maximum: int) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise FreelancerReadError("invalid_arguments")
    return value


def _text(value: Any, maximum: int) -> str:
    if (not isinstance(value, str) or not value.strip() or len(value) > maximum
            or any(ord(c) < 32 or ord(c) == 127 for c in value)):
        raise FreelancerReadError("invalid_arguments")
    return value.strip()


def _keys(args: dict[str, Any], allowed: set[str], required: set[str] = frozenset()) -> None:
    if not required <= args.keys() or args.keys() - allowed:
        raise FreelancerReadError("invalid_arguments")


def build_read_request(operation: str, arguments: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Map a finite operation to a fixed path. No raw URLs/methods are accepted."""
    if not isinstance(operation, str) or operation not in _OPERATIONS:
        raise FreelancerReadError("operation_unavailable")
    if type(arguments) is not dict:
        raise FreelancerReadError("invalid_arguments")
    args = arguments.copy()
    if operation == "account.read":
        _keys(args, set())
        return "/api/users/0.1/self/", {}
    if operation == "project.read":
        _keys(args, {"project_id"}, {"project_id"})
        project_id = _integer(args["project_id"], 1, 2**53 - 1)
        return f"/api/projects/0.1/projects/{project_id}/", {"full_description": "true"}
    if operation == "projects.search":
        _keys(args, {"query", "limit", "offset", "active_only"}, {"query"})
        active = args.get("active_only", False)
        if type(active) is not bool:
            raise FreelancerReadError("invalid_arguments")
        endpoint = "active" if active else "all"
        return f"/api/projects/0.1/projects/{endpoint}/", {
            "query": _text(args["query"], 200),
            "limit": _integer(args.get("limit", 10), 1, 20),
            "offset": _integer(args.get("offset", 0), 0, 5000),
            "full_description": "true",
        }
    if operation == "threads.list":
        # `count` is the SDK's supported bounded thread-list parameter.
        _keys(args, {"count"})
        return "/api/messages/0.1/threads/", {
            "count": _integer(args.get("count", 10), 1, 20),
        }
    _keys(args, {"thread_id", "limit", "offset"}, {"thread_id"})
    return "/api/messages/0.1/messages/", {
        "threads[]": [_integer(args["thread_id"], 1, 2**53 - 1)],
        "limit": _integer(args.get("limit", 10), 1, 20),
        "offset": _integer(args.get("offset", 0), 0, 5000),
    }


def tool_specs() -> list[dict[str, Any]]:
    """Local descriptors, not evidence of connection or permission to execute."""
    positive_id = {"type": "integer", "minimum": 1, "maximum": 2**53 - 1}
    pagination = {
        "limit": {"type": "integer", "minimum": 1, "maximum": 20},
        "offset": {"type": "integer", "minimum": 0, "maximum": 5000},
    }
    specs = [
        ("account.read", {}, [], "Read the authenticated account identity"),
        ("projects.search", {"query": {"type": "string", "minLength": 1, "maxLength": 200},
                             "active_only": {"type": "boolean"}, **pagination}, ["query"], "Search projects"),
        ("project.read", {"project_id": positive_id}, ["project_id"], "Read a project"),
        ("threads.list", {"count": {"type": "integer", "minimum": 1, "maximum": 20}}, [], "List conversation metadata"),
        ("messages.read", {"thread_id": positive_id, **pagination}, ["thread_id"], "Read one selected conversation"),
    ]
    return [{"name": name, "description": description, "effect": "READ",
             "input_schema": {"type": "object", "properties": properties,
                              "required": required, "additionalProperties": False}}
            for name, properties, required, description in specs]


def _client_factory(record: dict[str, Any], *, headers: dict[str, str]):
    # Reuse ADL's fixed-endpoint, DNS-pinned HTTPS transport, limits and no retries.
    from .security import client_for
    return client_for(record, headers=headers)


def _reject_constant(value: str):
    raise ValueError("non-finite JSON")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON member")
        result[key] = value
    return result


def _pick(record: Any, fields: tuple[str, ...]) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise FreelancerReadError("invalid_response")
    # IDs are essential for linking output to a subsequent authorized selection.
    if type(record.get("id")) is not int or record["id"] <= 0:
        raise FreelancerReadError("invalid_response")
    return {key: record[key] for key in fields if key in record}


_PROJECT_FIELDS = (
    "id", "title", "preview_description", "description", "status", "sub_status",
    "time_submitted", "time_updated", "type", "budget", "currency", "local", "language",
)


def _project_result(operation: str, result: Any, arguments: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(result, dict):
        raise FreelancerReadError("invalid_response")
    if operation == "account.read":
        return _pick(result, ("id", "username", "display_name"))
    if operation == "project.read":
        projected = _pick(result, _PROJECT_FIELDS)
        if projected["id"] != arguments["project_id"]:
            raise FreelancerReadError("response_scope_mismatch")
        return projected
    field, fields, maximum = {
        "projects.search": ("projects", _PROJECT_FIELDS, arguments.get("limit", 10)),
        "threads.list": ("threads", ("id", "context", "context_type", "thread_type", "members", "time_updated"), arguments.get("count", 10)),
        "messages.read": ("messages", ("id", "thread_id", "from_user", "message", "time_created"), arguments.get("limit", 10)),
    }[operation]
    rows = result.get(field)
    if not isinstance(rows, list) or len(rows) > maximum:
        raise FreelancerReadError("invalid_response")
    output = [_pick(row, fields) for row in rows]
    if operation == "messages.read" and any(
            type(row.get("thread_id")) is not int or row["thread_id"] != arguments["thread_id"]
            for row in output):
        raise FreelancerReadError("response_scope_mismatch")
    return {field: output}


class FreelancerReadAdapter:
    """Transport only; a trusted host supplies token and performs authorization.

    Sandbox is the default. A successful read is not an authorization decision,
    proof of job availability, message delivery, spending, or client competence.
    """
    __slots__ = ("_token", "_environment", "_factory")

    def __init__(self, oauth_token: str, *, environment: str = "sandbox",
                 _client_factory_override: Callable | None = None):
        if not isinstance(environment, str) or environment not in _ORIGINS:
            raise FreelancerReadError("invalid_environment")
        if (not isinstance(oauth_token, str) or not oauth_token or len(oauth_token) > 8192
                or any(not 33 <= ord(c) <= 126 for c in oauth_token)):
            raise FreelancerReadError("credential_unavailable")
        self._token = oauth_token
        self._environment = environment
        # Test injection is Python-host-only, not part of a tool/API input schema.
        self._factory = _client_factory_override or _client_factory

    def __repr__(self) -> str:
        return f"<FreelancerReadAdapter environment={self._environment} credential=REDACTED>"

    async def read(self, operation: str, arguments: dict[str, Any]) -> dict[str, Any]:
        path, params = build_read_request(operation, arguments)
        # Snapshot prevents caller mutation while the transport awaits.
        arguments = arguments.copy()
        if self._token in json.dumps(params, ensure_ascii=False):
            raise FreelancerReadError("credential_in_arguments")
        url = _ORIGINS[self._environment] + path
        headers = {"Freelancer-OAuth-V1": self._token, "Accept": "application/json"}
        try:
            async with asyncio.timeout(_TIMEOUT):
                async with self._factory({"url": url, "allow_private": False}, headers=headers) as client:
                    response = await client.get(url, params=params)
            status = response.status_code
            if 300 <= status < 400:
                raise FreelancerReadError("redirect_denied")
            if status != 200:
                code = {401: "authentication_failed", 403: "access_denied", 404: "not_found",
                        429: "rate_limited"}.get(status, "http_error")
                raise FreelancerReadError(code)
            raw = response.content
            if len(raw) > _LIMIT:
                raise FreelancerReadError("response_too_large")
            body = json.loads(raw, parse_constant=_reject_constant, object_pairs_hook=_unique_object)
            if not isinstance(body, dict) or body.get("status") != "success" or "result" not in body:
                raise FreelancerReadError("invalid_response")
            if self._token in json.dumps(body, ensure_ascii=False):
                raise FreelancerReadError("credential_in_response")
            result = _project_result(operation, body["result"], arguments)
            return {"operation": operation, "environment": self._environment,
                    "http_status": status, "data": result, "untrusted_remote_data": True}
        except FreelancerReadError:
            raise
        except (TimeoutError, asyncio.TimeoutError):
            raise FreelancerReadError("timeout") from None
        except Exception:
            # No remote body, URL query, token or transport exception in diagnostics.
            raise FreelancerReadError("transport_or_response_error") from None
