"""Translate ADL function names at provider transports, without executing tools."""
from __future__ import annotations

import json
import re
from typing import Any

from src.providers.registration import RegistrationError

ALIASES = {"sandbox.run": "adl_sandbox_run"}


def wire_name(name: str) -> str:
    name = ALIASES.get(name, name)
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", name):
        raise RegistrationError("invalid_tool_name", "The requested tool name is not supported by this provider.")
    return name


def adl_name(name: str) -> str:
    return next((key for key, value in ALIASES.items() if value == name), name)


def arguments_object(arguments: Any) -> dict[str, Any]:
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except (ValueError, TypeError):
            arguments = None
    if not isinstance(arguments, dict):
        raise RegistrationError("provider_response_invalid", "The provider returned invalid tool arguments.")
    return arguments


def wire_tools(tools: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    return [{"type": "function", "function": {**tool["function"], "name": wire_name(tool["function"]["name"])}} for tool in tools or []]


def wire_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for message in messages:
        item: dict[str, Any] = {"role": message["role"], "content": message.get("content") or ""}
        if message.get("tool_calls"):
            item["tool_calls"] = [{"id": call["id"], "type": "function", "function": {
                "name": wire_name(call["function"]["name"]),
                "arguments": json.dumps(arguments_object(call["function"]["arguments"]), ensure_ascii=False),
            }} for call in message["tool_calls"]]
        if message["role"] == "tool":
            if not message.get("tool_call_id"):
                raise RegistrationError("invalid_tool_result", "The tool result is missing its provider call identifier.")
            item["tool_call_id"] = message["tool_call_id"]
        result.append(item)
    return result
