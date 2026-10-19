"""OpenAI Platform Chat Completions adapter used by saved ADL agents."""
from __future__ import annotations

from typing import Any

import requests

from src.providers import registration
from src.providers.tool_protocol import adl_name, arguments_object, wire_messages, wire_tools


def chat_turn(model_id: str, messages: list[dict[str, Any]], *, tools: list[dict[str, Any]] | None = None, options: dict[str, Any] | None = None, binding: registration.RuntimeRegistration | None = None) -> dict[str, Any]:
    binding = binding or registration.runtime_binding("openai-platform", model_id)
    if not binding.credential:
        raise registration.RegistrationError("authentication_required", "Provide an OpenAI API key before using this provider.", "needs_authentication")
    if binding.model_id != model_id or binding.provider_id != "openai-platform":
        raise registration.RegistrationError("model_registration_mismatch", "Use the model saved in the OpenAI registration.")
    payload: dict[str, Any] = {"model": model_id, "messages": wire_messages(messages), "stream": False, "store": False}
    if tools:
        payload["tools"] = wire_tools(tools)
    if options:
        # GPT-5 family Chat Completions uses the default sampling behavior and
        # may reject temperature. Keep only the bounded completion cap here.
        for key in ("max_completion_tokens",):
            if key in options:
                payload[key] = options[key]
    try:
        response = requests.post("https://api.openai.com/v1/chat/completions", json=payload,
                                 headers={"Authorization": f"Bearer {binding.credential}", "Content-Type": "application/json"}, timeout=(10, 90), allow_redirects=False)
    except requests.RequestException:
        raise registration.RegistrationError("provider_unreachable", "OpenAI Platform could not be reached.", "error") from None
    if response.status_code in {401, 403}:
        raise registration.RegistrationError("authentication_failed", "OpenAI rejected the saved credential. Check its project access.", "needs_authentication")
    if response.status_code == 429:
        raise registration.RegistrationError("provider_rate_limited", "OpenAI rate-limited this request.", "error")
    if not response.ok:
        raise registration.RegistrationError("provider_request_failed", "OpenAI could not complete this request for the selected model.", "error")
    try:
        data = response.json()
        choice = data["choices"][0]
        message = choice["message"]
        if not isinstance(message, dict) or choice.get("finish_reason") in {"length", "content_filter"}:
            raise ValueError("Incomplete response")
    except (ValueError, KeyError, IndexError, TypeError):
        raise registration.RegistrationError("provider_response_invalid", "OpenAI returned an invalid response.", "error") from None
    calls = message.get("tool_calls") or []
    content = message.get("content") or message.get("refusal") or ""
    if not isinstance(content, str) or not isinstance(calls, list) or len(calls) > 8:
        raise registration.RegistrationError("provider_response_invalid", "OpenAI returned an invalid response.")
    allowed = {tool["function"]["name"] for tool in tools or []}
    normalized = []
    for call in calls:
        if not isinstance(call, dict) or not isinstance(call.get("function"), dict) or not isinstance(call.get("id"), str) or not call["id"]:
            raise registration.RegistrationError("provider_response_invalid", "OpenAI returned an invalid tool call.")
        function = call["function"]
        if not isinstance(function.get("name"), str) or not function["name"]:
            raise registration.RegistrationError("provider_response_invalid", "OpenAI returned an invalid tool name.")
        name = adl_name(function["name"])
        if name not in allowed:
            raise registration.RegistrationError("provider_response_invalid", "OpenAI requested a tool that is not available to this agent.")
        normalized.append({"id": call["id"], "type": "function", "function": {"name": name, "arguments": arguments_object(function.get("arguments"))}})
    return {"content": content, "tool_calls": normalized}
