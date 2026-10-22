"""Server-side dispatch for providers available to saved agents."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
import json
import os
import tempfile
from typing import Any

from src.providers import codex, github_copilot, ollama, openai_platform, registration, model_policy

SELECTION_PATH = registration.REGISTRY_PATH.with_name("active-provider.json")


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
    if provider_id == "codex":
        try:
            session = codex.session_status()
            item["has_session"] = session["authenticated"]
            if not session["authenticated"]:
                item["state"] = "needs_authentication"
        except registration.RegistrationError as error:
            item.update(state=error.status, message=error.message, has_session=False)
    return item


def active_provider_id() -> str:
    return active_selection()["provider_id"]


def assert_agent_model(config: dict[str, Any]) -> None:
    """Apply role eligibility at request entry without rewriting saved profiles."""
    if model_policy.read()[0] is None:
        return
    provider_id = config.get("provider_id") or "ollama-cloud"
    model_id = config.get("model_id") or status(provider_id).get("model_id")
    if not model_id or not model_policy.permits(provider_id, model_id, config.get("type")):
        raise ProviderRuntimeError("agent_model_disabled", "El modelo no está activo para este tipo de agente. Selecciona uno permitido en su perfil.")


def active_selection() -> dict[str, str]:
    policy, _ = model_policy.read()
    if policy is not None:
        if not policy.main_chat or not any(model_policy.key(item) == policy.main_chat and item.orchestrator for item in policy.models):
            raise ProviderRuntimeError("chat_models_required", "Activa un modelo para el chat principal.")
        provider_id, model_id = policy.main_chat.split("|", 1)
        current = status(provider_id)
        if current.get("state") not in {"ready", "configured_unverified"}:
            raise ProviderRuntimeError("provider_not_configured", "El proveedor del modelo principal no está disponible.")
        return {"provider_id": provider_id, "model_id": model_id, "label": current.get("label", provider_id), "state": current["state"] if current.get("model_id") == model_id else "configured_unverified"}
    try:
        selection = json.loads(SELECTION_PATH.read_text(encoding="utf-8"))
        provider_id = selection["provider_id"]
    except FileNotFoundError:
        provider_id = "ollama-cloud"
        selection = {}
    except (OSError, ValueError, KeyError, TypeError):
        raise ProviderRuntimeError("active_provider_unavailable", "No se pudo leer el proveedor seleccionado para ADL.") from None
    if provider_id not in {"ollama-cloud", *registration.LIVE_PROVIDER_IDS}:
        raise ProviderRuntimeError("active_provider_unavailable", "El proveedor seleccionado para ADL no está disponible.")
    current = status(provider_id)
    model_id = selection.get("model_id") or current.get("model_id")
    if not isinstance(model_id, str) or not model_id:
        raise ProviderRuntimeError("model_selection_required", "Selecciona un modelo para el chat del orquestador.", current.get("state", "not_configured"))
    if current.get("state") not in {"ready", "configured_unverified"} or current.get("model_id") != model_id:
        raise ProviderRuntimeError("provider_not_configured", "Configura y registra el modelo antes de usarlo en el chat del orquestador.", current.get("state", "not_configured"))
    return {"provider_id": provider_id, "model_id": model_id, "label": current.get("label", provider_id), "state": current.get("state", "configured_unverified")}


def select_provider(provider_id: str, model_id: str | None = None) -> dict[str, Any]:
    current = status(provider_id)
    selected_model = model_id or current.get("model_id")
    if current.get("state") not in {"ready", "configured_unverified"} or not selected_model or current.get("model_id") != selected_model:
        raise ProviderRuntimeError("provider_not_configured", "Configura el proveedor y selecciona un modelo antes de usarlo en el chat de ADL.")
    SELECTION_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix="active-provider-", suffix=".tmp", dir=SELECTION_PATH.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump({"schema": "adl.active_provider.v1", "provider_id": provider_id, "model_id": selected_model}, stream)
        os.replace(temporary, SELECTION_PATH)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return {**current, "model_id": selected_model, "active_for_chat": True}


def select_chat_model(provider_id: str, model_id: str) -> dict[str, Any]:
    """Select a catalog-listed model for the orchestrator, retaining provider credentials."""
    if model_policy.read()[0] is not None:
        if not any(item["provider_id"] == provider_id and item["model_id"] == model_id for item in model_catalog()["models"]):
            raise ProviderRuntimeError("model_unavailable", "Ese modelo ya no está disponible.")
        model_policy.select_main(provider_id, model_id)
        return active_selection()
    if provider_id == "codex":
        config = registration.get_registration(provider_id)
        catalog = codex.session_status(include_models=True)
        if not catalog.get("authenticated") or model_id not in {item["model_id"] for item in catalog["models"]}:
            raise ProviderRuntimeError("model_unavailable", "Ese modelo no aparece en el catálogo de tu sesión de Codex.")
        registration.save_registration(provider_id, config["auth_mode"], model_id, None, None)
    elif provider_id == "ollama-cloud":
        current = ollama.status()
        if current.get("state") not in {"ready", "configured_unverified"} or model_id not in {item["model_id"] for item in ollama.discover_models()["models"]}:
            raise ProviderRuntimeError("model_unavailable", "Ese modelo no aparece entre los modelos disponibles de Ollama.")
        ollama.save_config(current["auth_mode"], model_id, None)
    else:
        current = status(provider_id)
        if current.get("model_id") != model_id:
            raise ProviderRuntimeError("model_unavailable", "Este proveedor solo tiene registrado el modelo indicado en Provider Settings.")
    return select_provider(provider_id, model_id)


def chat_turn(provider_id: str, model_id: str, messages: list[dict[str, Any]], *, require_text: bool = False, **kwargs: Any) -> Mapping[str, Any]:
    if provider_id == "ollama-cloud":
        return ollama.chat_turn(model_id, messages, **kwargs)
    binding = None
    try:
        current = registration.get_registration(provider_id)
        alternate = current.get("model_id") != model_id
        if alternate:
            policy, _ = model_policy.read()
            if policy is None or not any(item.provider_id == provider_id and item.model_id == model_id and (item.chat or item.orchestrator or item.agent_types) for item in policy.models):
                raise ProviderRuntimeError("model_registration_mismatch", "El modelo no está activo en la selección de modelos.")
            binding = replace(registration.runtime_binding(provider_id, current.get("model_id")), model_id=model_id)
        else:
            binding = registration.runtime_binding(provider_id, model_id)
        if provider_id == "openai-platform":
            result = openai_platform.chat_turn(model_id, messages, binding=binding, **kwargs)
        elif provider_id == "github-copilot":
            result = github_copilot.chat_turn(model_id, messages, binding=binding, **kwargs)
        elif provider_id == "codex":
            result = codex.chat_turn(model_id, messages, binding=binding, **kwargs)
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
        if alternate:
            if registration.get_registration(provider_id).get("updated_at", "") != binding.revision:
                raise ProviderRuntimeError("registration_changed", "El registro cambió durante la solicitud.")
        else:
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


def model_catalog() -> dict[str, Any]:
    """Discover each provider independently; one unavailable service cannot hide the rest."""
    entries, warnings = [], []
    for provider_id, label in (("ollama-cloud", "Ollama"), ("codex", "OpenAI Codex"), ("openai-platform", "OpenAI Platform"), ("github-copilot", "GitHub Copilot")):
        current = None
        try:
            current = status(provider_id)
            if current.get("state") not in {"ready", "configured_unverified"}:
                continue
            if provider_id == "ollama-cloud":
                models = ollama.discover_models()["models"]
            elif provider_id == "codex":
                models = codex.session_status(include_models=True)["models"]
            elif provider_id == "github-copilot":
                config = registration.get_registration(provider_id)
                models = github_copilot.discover_models(config["auth_mode"], registration.saved_credential(provider_id))["models"]
            else:
                models = [{"model_id": current["model_id"]}] if current.get("model_id") else []
            entries.extend({"provider_id": provider_id, "model_id": item["model_id"], "display_name": item.get("display_name", item["model_id"]), "label": label, "state": current["state"] if item["model_id"] == current.get("model_id") else "configured_unverified"} for item in models)
        except (ollama.ProviderError, registration.RegistrationError, ProviderRuntimeError):
            warnings.append(f"No se pudieron cargar los modelos de {label}.")
            if current and current.get("state") in {"ready", "configured_unverified"} and current.get("model_id"):
                entries.append({"provider_id": provider_id, "model_id": current["model_id"], "display_name": current["model_id"], "label": label, "state": current["state"]})
    return {"models": entries, "warnings": warnings}


def verify(provider_id: str, model_id: str | None = None) -> dict[str, Any]:
    if provider_id == "ollama-cloud":
        current = ollama.status()
        selected = model_id or current.get("model_id")
        if not isinstance(selected, str) or not selected or selected != current.get("model_id"):
            raise ProviderRuntimeError("model_registration_mismatch", "Save the selected Ollama model before checking access.")
        try:
            return ollama.verify(selected)
        except ollama.ProviderError as error:
            raise ProviderRuntimeError(error.code, error.message, error.status) from None
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
