"""Server-side dispatch for providers available to saved agents."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from src.providers import github_copilot, ollama, openai_platform, registration


class ProviderRuntimeError(RuntimeError):
    def __init__(self, code: str, message: str, status: str = "error") -> None:
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


def _record_failure(binding: registration.RuntimeRegistration | None, state: str = "error") -> None:
    if binding is not None:
        try:
            registration.mark_failed(binding, state)
        except (registration.RegistrationError, OSError):
            # The process-local failure marker still prevents a stale ready
            # status if persisting the failure is temporarily unavailable.
            pass


def status(provider_id: str) -> dict[str, Any]:
    if provider_id == "ollama-cloud":
        return ollama.status()
    item = registration.status(provider_id)
    if item.get("runtime_support") != "chat_and_agent_runner":
        raise ProviderRuntimeError("provider_unavailable", "The selected provider is not integrated with agent chat.")
    return item


def chat_turn(provider_id: str, model_id: str, messages: list[dict[str, Any]], *, require_text: bool = False, **kwargs: Any) -> Mapping[str, Any]:
    if provider_id == "ollama-cloud":
        return ollama.chat_turn(model_id, messages, **kwargs)
    binding = None
    try:
        binding = registration.runtime_binding(provider_id, model_id)
        if provider_id == "openai-platform":
            result = openai_platform.chat_turn(model_id, messages, binding=binding, **kwargs)
        elif provider_id == "github-copilot":
            result = github_copilot.chat_turn(model_id, messages, binding=binding, **kwargs)
        else:
            raise ProviderRuntimeError("provider_unavailable", "This provider is not integrated with agent chat.")
        if not isinstance(result, Mapping):
            raise ProviderRuntimeError("provider_response_invalid", "The provider returned an invalid response.")
        content = result.get("content")
        calls = result.get("tool_calls")
        if not (isinstance(content, str) and content.strip()) and not (isinstance(calls, list) and calls):
            raise ProviderRuntimeError("empty_model_response", "The provider returned no assistant response.")
        if require_text and (not isinstance(content, str) or not content.strip() or calls):
            raise ProviderRuntimeError("empty_model_response", "The provider returned no final text response.")
        registration.mark_verified(binding)
        return result
    except (registration.RegistrationError, ProviderRuntimeError) as error:
        _record_failure(binding, error.status)
        raise ProviderRuntimeError(error.code, error.message, error.status) from None
    except Exception:
        _record_failure(binding)
        raise ProviderRuntimeError("provider_error", "The selected provider could not complete the request.") from None


def chat(provider_id: str, model_id: str, messages: list[dict[str, Any]]) -> str:
    if provider_id == "ollama-cloud":
        return ollama.chat(model_id, messages)
    result = chat_turn(provider_id, model_id, messages, require_text=True)
    content = result.get("content")
    if not isinstance(content, str) or not content.strip():
        raise ProviderRuntimeError("empty_model_response", "The provider returned no assistant response.")
    return content.strip()


def resolve(provider_id: str):
    return (lambda: status(provider_id), lambda model, messages, **kwargs: chat_turn(provider_id, model, messages, **kwargs))


def verify(provider_id: str, model_id: str | None = None) -> dict[str, Any]:
    config = registration.get_registration(provider_id)
    selected = model_id or config.get("model_id")
    if not isinstance(selected, str) or not selected or selected != config.get("model_id"):
        raise ProviderRuntimeError("model_registration_mismatch", "Select the model saved in this provider registration.")
    result = chat_turn(provider_id, selected, [
        {"role": "system", "content": "Reply with the single word OK."},
        {"role": "user", "content": "Connection check. Reply only OK."},
    ], require_text=True, options={"max_completion_tokens": 1024})
    if not isinstance(result.get("content"), str) or not result["content"].strip():
        raise ProviderRuntimeError("empty_model_response", "The provider returned no response to the live check.")
    return {**registration.status(provider_id), "usage": "minimal_inference", "generation_performed": True}
