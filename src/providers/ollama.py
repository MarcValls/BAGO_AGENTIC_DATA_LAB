"""Ollama Cloud and local signed-in CLI-session adapter.

Secrets are write-only through the API and live in an OS credential backend.
This module never reads Ollama CLI authentication files.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import requests

PROVIDER_ID = "ollama-cloud"
CLOUD_BASE = "https://ollama.com/api"
LOCAL_BASE = "http://127.0.0.1:11434/api"
SERVICE_NAME = "BAGO.AgentChat.OllamaCloud"
MODEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")
CONFIG_PATH = Path(__file__).resolve().parents[2] / ".bago" / "providers" / "ollama.json"


class ProviderError(Exception):
    """Safe, user-displayable provider error with no upstream body."""

    def __init__(self, code: str, message: str, status: str = "error") -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_model_id(value: str) -> str:
    model_id = value.strip()
    if not MODEL_RE.fullmatch(model_id):
        raise ProviderError("invalid_model_id", "Model identifier is invalid.")
    return model_id


def _runtime_is_supported() -> bool:
    # The Docker image cannot access the host OS credential vault or the
    # host's loopback Ollama service. Keep provider setup host-native for v1.
    return os.environ.get("BAGO_RUNTIME_MODE", "host").lower() != "container"


def _require_supported_runtime() -> None:
    if not _runtime_is_supported():
        raise ProviderError(
            "unsupported_runtime",
            "Ollama provider setup is unavailable in the container runtime. Start the app on this computer with scripts/run-local-ui.ps1.",
        )


def _secure_keyring() -> Any:
    try:
        import keyring

        backend = keyring.get_keyring()
        module = backend.__class__.__module__.lower()
        name = backend.__class__.__name__.lower()
        # Fail closed for null, fail, plaintext, and unknown third-party stores.
        approved = ("win32", "windows", "macos", "secretservice", "kwallet")
        if not any(token in module for token in approved) or name in {"keyring", "nullkeyring"}:
            raise ProviderError("secure_store_unavailable", "A supported operating-system credential store is unavailable.")
        if float(getattr(backend, "priority", 0)) <= 0:
            raise ProviderError("secure_store_unavailable", "A supported operating-system credential store is unavailable.")
        return keyring
    except ProviderError:
        raise
    except Exception:
        raise ProviderError("secure_store_unavailable", "A supported operating-system credential store is unavailable.") from None


def _read_config() -> dict[str, str] | None:
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        mode = data.get("auth_mode")
        if mode not in {"api_key", "local_cli"}:
            return None
        model_id = data.get("model_id")
        if model_id is not None:
            validate_model_id(model_id)
        return {"auth_mode": mode, **({"model_id": model_id} if model_id else {})}
    except FileNotFoundError:
        return None
    except (OSError, ValueError, TypeError, ProviderError):
        return None


def save_config(auth_mode: Literal["api_key", "local_cli"], model_id: str | None, api_key: str | None) -> dict[str, Any]:
    global _last_successful_model_call, _last_successful_at
    _require_supported_runtime()
    if model_id:
        model_id = validate_model_id(model_id)
    if auth_mode == "api_key":
        if api_key is not None:
            secret = api_key.strip()
            if len(secret) < 8 or len(secret) > 4096 or "\n" in secret or "\r" in secret:
                raise ProviderError("invalid_api_key", "API key is invalid.")
            _secure_keyring().set_password(SERVICE_NAME, "cloud-api-key", secret)
        else:
            # Retaining an existing key is permitted, but never read it back to callers.
            if not _get_api_key(required=False):
                raise ProviderError("authentication_required", "Provide an Ollama Cloud API key.", "needs_authentication")
    elif api_key:
        raise ProviderError("unexpected_secret", "An API key can only be used with api_key mode.")

    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {"auth_mode": auth_mode, "updated_at": utc_now()}
    if model_id:
        payload["model_id"] = model_id
    fd, temp_name = tempfile.mkstemp(prefix="ollama-", suffix=".tmp", dir=str(CONFIG_PATH.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, CONFIG_PATH)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
    _last_successful_model_call = None
    _last_successful_at = None
    return status()


def _get_api_key(required: bool = True) -> str | None:
    try:
        secret = _secure_keyring().get_password(SERVICE_NAME, "cloud-api-key")
    except ProviderError:
        raise
    except Exception:
        raise ProviderError("secure_store_unavailable", "A supported operating-system credential store is unavailable.") from None
    if not secret and required:
        raise ProviderError("authentication_required", "Ollama Cloud authentication is required.", "needs_authentication")
    return secret


_last_successful_model_call: str | None = None


def status() -> dict[str, Any]:
    config = _read_config()
    if not _runtime_is_supported():
        return {
            "provider_id": PROVIDER_ID,
            "state": "unsupported_runtime",
            "runtime_mode": "container",
            "auth_mode": config.get("auth_mode") if config else None,
            "model_id": config.get("model_id") if config else None,
            "message": "Configure Ollama from the host-local app so the OS credential store and local Ollama service are reachable.",
        }
    if not config:
        return {"provider_id": PROVIDER_ID, "state": "not_configured", "runtime_mode": "host", "auth_mode": None, "model_id": None}
    mode = config["auth_mode"]
    base = {"provider_id": PROVIDER_ID, "runtime_mode": "host", "auth_mode": mode, "model_id": config.get("model_id")}
    if mode == "api_key":
        try:
            key_present = bool(_get_api_key(required=False))
        except ProviderError:
            return {**base, "state": "error", "message": "Secure credential storage is unavailable."}
        if not key_present:
            return {**base, "state": "needs_authentication"}
    else:
        try:
            _request("GET", "/tags", timeout=1.5)
        except ProviderError as error:
            if error.code in {"provider_unavailable", "provider_timeout"}:
                return {**base, "state": "local_service_unavailable"}
            if error.status == "needs_authentication":
                return {**base, "state": "needs_authentication"}
            return {**base, "state": "error", "message": error.message}
    if config.get("model_id") and _last_successful_model_call == config["model_id"]:
        return {**base, "state": "ready", "last_verified_at": _last_successful_at}
    return {**base, "state": "configured_unverified"}


_last_successful_at: str | None = None


def _request(method: str, path: str, *, payload: dict[str, Any] | None = None, timeout: float = 20) -> dict[str, Any]:
    _require_supported_runtime()
    config = _read_config()
    if not config:
        raise ProviderError("not_configured", "Configure Ollama before using the model.", "not_configured")
    mode = config["auth_mode"]
    base = LOCAL_BASE if mode == "local_cli" else CLOUD_BASE
    headers = {"Accept": "application/json"}
    if mode == "api_key":
        headers["Authorization"] = f"Bearer {_get_api_key()}"
    try:
        with requests.Session() as session:
            if mode == "local_cli":
                session.trust_env = False
            response = session.request(method, f"{base}/{path.lstrip('/')}", headers=headers, json=payload, timeout=timeout)
    except requests.Timeout:
        raise ProviderError("provider_timeout", "Ollama did not respond before the timeout.") from None
    except requests.RequestException:
        raise ProviderError("provider_unavailable", "Ollama could not be reached.") from None
    if response.status_code in (401, 403):
        raise ProviderError("authentication_failed", "Ollama rejected the configured authentication.", "needs_authentication")
    if response.status_code == 404:
        raise ProviderError("model_or_endpoint_unavailable", "The requested Ollama model or endpoint is unavailable.")
    if not response.ok:
        raise ProviderError("provider_error", "Ollama returned an error.")
    try:
        result = response.json()
    except ValueError:
        raise ProviderError("invalid_provider_response", "Ollama returned an invalid response.") from None
    if not isinstance(result, dict):
        raise ProviderError("invalid_provider_response", "Ollama returned an invalid response.")
    return result


def discover_models() -> dict[str, Any]:
    config = _read_config()
    if not config:
        return {"provider_id": PROVIDER_ID, "models": [], "source": "none", "availability_confidence": "none"}
    if config["auth_mode"] == "api_key":
        result = _request("GET", "/tags", timeout=10)
        source = "ollama_cloud_api"
    else:
        result = _request("GET", "/tags", timeout=3)
        source = "local_ollama_service"
    raw = result.get("models", [])
    models = []
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict) or not isinstance(item.get("name"), str):
                continue
            model_id = item["name"]
            try:
                validate_model_id(model_id)
            except ProviderError:
                continue
            models.append({"provider_id": PROVIDER_ID, "model_id": model_id, "display_name": model_id, "source": source, "availability_confidence": "listed"})
    return {"provider_id": PROVIDER_ID, "models": models, "source": source, "availability_confidence": "listed" if models else "none"}


def verify(model_id: str | None = None) -> dict[str, Any]:
    """Non-generative verification; no inference tokens are consumed."""
    config = _read_config()
    if not config:
        raise ProviderError("not_configured", "Configure Ollama before verification.", "not_configured")
    models = discover_models()
    selected = validate_model_id(model_id or config.get("model_id") or "") if (model_id or config.get("model_id")) else None
    found = selected is not None and any(m["model_id"] == selected for m in models["models"])
    if selected and not found:
        return {"provider_id": PROVIDER_ID, "state": "configured_unverified", "model_id": selected, "model_available": False, "generation_performed": False}
    return {"provider_id": PROVIDER_ID, "state": "configured_unverified", "model_id": selected, "model_available": found if selected else None, "generation_performed": False}


def chat(model_id: str, messages: list[dict[str, str]]) -> str:
    global _last_successful_model_call, _last_successful_at
    model_id = validate_model_id(model_id)
    _last_successful_model_call = None
    _last_successful_at = None
    response = _request("POST", "/chat", payload={"model": model_id, "messages": messages, "stream": False}, timeout=120)
    message = response.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str) or not content.strip():
        raise ProviderError("empty_model_response", "Ollama returned no assistant response.")
    _last_successful_model_call = model_id
    _last_successful_at = utc_now()
    return content.strip()
