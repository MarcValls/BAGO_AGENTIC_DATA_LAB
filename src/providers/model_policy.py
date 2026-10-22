"""Persist explicit model eligibility independently of provider credentials."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator

from src.providers import registration

LOCK = threading.RLock()
AGENT_TYPES = ("rag", "tool", "multi-agent")


class ModelUse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider_id: Literal["ollama-cloud", "codex", "openai-platform", "github-copilot"]
    model_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")
    chat: StrictBool = False
    orchestrator: StrictBool = False
    agent_types: list[Literal["rag", "tool", "multi-agent"]] = Field(default_factory=list, max_length=3)

    @model_validator(mode="before")
    @classmethod
    def preserve_legacy_chat_eligibility(cls, value):
        if isinstance(value, dict) and "orchestrator" not in value:
            return {**value, "orchestrator": value.get("chat", False)}
        return value


class Policy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    models: list[ModelUse] = Field(max_length=500)
    main_chat: str | None = Field(default=None, max_length=200)


def path() -> Path:
    return Path(os.environ["BAGO_MODEL_POLICY_PATH"]) if os.environ.get("BAGO_MODEL_POLICY_PATH") else registration.REGISTRY_PATH.with_name("model-policy.json")


def key(item) -> str:
    return f"{item['provider_id']}|{item['model_id']}" if isinstance(item, dict) else f"{item.provider_id}|{item.model_id}"


def read() -> tuple[Policy | None, str]:
    from src.providers.runtime import ProviderRuntimeError
    try:
        raw = path().read_bytes()
    except FileNotFoundError:
        return None, "none"
    except OSError:
        raise ProviderRuntimeError("model_policy_unavailable", "No se pudo leer la selección de modelos.") from None
    try:
        data = json.loads(raw)
        # Policies created before the orchestrator permission existed inherit
        # their previous chat eligibility so upgrades do not lock out models.
        for item in data.get("models", []):
            item.setdefault("orchestrator", item.get("chat", False))
        return Policy.model_validate(data), hashlib.sha256(raw).hexdigest()
    except ValueError:
        raise ProviderRuntimeError("model_policy_invalid", "La selección de modelos guardada no es válida.") from None


def _write(policy: Policy) -> str:
    target = path()
    target.parent.mkdir(parents=True, exist_ok=True)
    raw = policy.model_dump_json(indent=2).encode("utf-8")
    fd, temp = tempfile.mkstemp(prefix="model-policy-", dir=target.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, target)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
    return hashlib.sha256(raw).hexdigest()


def save(policy: Policy, expected_revision: str, catalog: list[dict]) -> dict:
    from src.providers.runtime import ProviderRuntimeError
    keys = [key(item) for item in policy.models]
    if len(set(keys)) != len(keys):
        raise ProviderRuntimeError("duplicate_model", "Un modelo aparece más de una vez.")
    available = {key(item) for item in catalog}
    for item in policy.models:
        if (item.chat or item.orchestrator or item.agent_types) and key(item) not in available:
            raise ProviderRuntimeError("model_unavailable", "Actualiza los modelos: uno de los elegidos ya no está disponible.")
    # The orchestrator is the model pool shown in the main chat selector.
    # Keep the legacy `chat` field synchronized for older clients.
    for item in policy.models:
        item.chat = item.orchestrator
    enabled = {key(item) for item in policy.models if item.orchestrator}
    if (enabled and policy.main_chat not in enabled) or (not enabled and policy.main_chat is not None):
        raise ProviderRuntimeError("main_model_required", "Elige el modelo principal entre los modelos titulares y autorizados como orquestador.")
    with LOCK:
        if read()[1] != expected_revision:
            raise ProviderRuntimeError("model_policy_conflict", "La selección cambió. Actualiza antes de guardar.")
        revision = _write(policy)
    return {**policy.model_dump(), "revision": revision, "configured": True}


def permits(provider_id: str, model_id: str, agent_type: str | None = None) -> bool:
    policy, _ = read()
    if policy is None:
        return True
    item = next((item for item in policy.models if key(item) == f"{provider_id}|{model_id}"), None)
    return bool(item and (agent_type in item.agent_types if agent_type else item.orchestrator))


def permits_orchestrator(provider_id: str, model_id: str) -> bool:
    policy, _ = read()
    if policy is None:
        return True
    item = next((item for item in policy.models if key(item) == f"{provider_id}|{model_id}"), None)
    return bool(item and item.orchestrator)


def assigned(agent_type: str, preferred_provider: str, preferred_model: str) -> tuple[str, str]:
    from src.providers.runtime import ProviderRuntimeError
    policy, _ = read()
    if policy is None:
        return preferred_provider, preferred_model
    pool = [item for item in policy.models if agent_type in item.agent_types]
    if not pool:
        raise ProviderRuntimeError("agent_models_required", f"Activa al menos un modelo para agentes de tipo {agent_type}.")
    choice = next((item for item in pool if key(item) == f"{preferred_provider}|{preferred_model}"), pool[0])
    return choice.provider_id, choice.model_id


def select_main(provider_id: str, model_id: str) -> None:
    from src.providers.runtime import ProviderRuntimeError
    with LOCK:
        policy, _ = read()
        if policy is None or not permits_orchestrator(provider_id, model_id):
            raise ProviderRuntimeError("chat_model_disabled", "Este modelo no está activo para el chat principal.")
        policy.main_chat = f"{provider_id}|{model_id}"
        _write(policy)
