"""Provider registration metadata and OS credential-store access."""

from __future__ import annotations

import json
import os
import re
import tempfile
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from src.storage.portable import configured_path

MODEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")
SERVICE_NAME = "BAGO.AgenticDataLab.ProviderRegistration"
REGISTRY_PATH = configured_path("BAGO_PROVIDER_REGISTRY_PATH", "providers", "provider-registry.json")
_LOCK = threading.RLock()
_runtime_failures: dict[str, tuple[str, str]] = {}

PROVIDER_MODES: dict[str, set[str]] = {
    "codex": {"codex_cli"},
    "openai-platform": {"api_key"},
    "github-copilot": {"copilot_cli", "token"},
    "anthropic": {"api_key"},
    "openrouter": {"api_key"},
    "opencode": {"api_key", "local"},
}
SECRET_MODES = {"api_key", "token"}
LIVE_PROVIDER_IDS = {"codex", "openai-platform", "github-copilot"}


@dataclass(frozen=True)
class RuntimeRegistration:
    provider_id: str
    model_id: str
    auth_mode: str
    revision: str
    credential: str | None = field(default=None, repr=False)


class RegistrationError(Exception):
    """Safe registration error with no credential or upstream details."""

    def __init__(self, code: str, message: str, status: str = "error") -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _secure_keyring() -> Any:
    try:
        import keyring

        backend = keyring.get_keyring()
        module = backend.__class__.__module__.lower()
        name = backend.__class__.__name__.lower()
        approved = ("win32", "windows", "macos", "secretservice", "kwallet")
        if not any(token in module for token in approved) or name in {"keyring", "nullkeyring"}:
            raise RegistrationError("secure_store_unavailable", "A supported operating-system credential store is unavailable.")
        if float(getattr(backend, "priority", 0)) <= 0:
            raise RegistrationError("secure_store_unavailable", "A supported operating-system credential store is unavailable.")
        return keyring
    except RegistrationError:
        raise
    except Exception:
        raise RegistrationError("secure_store_unavailable", "A supported operating-system credential store is unavailable.") from None


def _read_registry() -> dict[str, dict[str, Any]]:
    try:
        payload = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        providers = payload.get("providers", {}) if isinstance(payload, dict) else {}
        return providers if isinstance(providers, dict) else {}
    except FileNotFoundError:
        return {}
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        raise RegistrationError("registry_unavailable", "Provider registrations could not be read.") from None


def _public_status(provider_id: str, config: Any) -> dict[str, Any]:
    support = "chat_and_agent_runner" if provider_id in LIVE_PROVIDER_IDS else "not_integrated"
    if not isinstance(config, dict) or config.get("auth_mode") not in PROVIDER_MODES[provider_id]:
        return {"provider_id": provider_id, "state": "not_configured", "auth_mode": None, "model_id": None, "base_url": None, "has_credential": False, "runtime_support": support}

    mode = config["auth_mode"]
    has_credential = False
    credential_store_state = "not_required"
    if mode in SECRET_MODES:
        try:
            has_credential = bool(_secure_keyring().get_password(SERVICE_NAME, provider_id))
            credential_store_state = "available"
        except Exception:
            credential_store_state = "unavailable"

    state = "configured_unverified"
    if mode in SECRET_MODES and not has_credential:
        state = "needs_authentication" if credential_store_state == "available" else "credential_store_unavailable"
    if state == "configured_unverified" and config.get("last_verified_model_id") == config.get("model_id") and config.get("model_id"):
        state = "ready"
    if state == "configured_unverified" and config.get("last_error_state") == "needs_authentication":
        state = "needs_authentication"
    failure = _runtime_failures.get(provider_id)
    if failure and failure[0] == config.get("updated_at", "") and state in {"ready", "configured_unverified", "needs_authentication"}:
        state = failure[1]
    return {
        "provider_id": provider_id,
        "state": state,
        "auth_mode": mode,
        "model_id": config.get("model_id"),
        "base_url": config.get("base_url"),
        "has_credential": has_credential,
        "credential_store_state": credential_store_state,
        "updated_at": config.get("updated_at"),
        "last_verified_at": config.get("last_verified_at") if state == "ready" else None,
        "runtime_support": support,
    }


def list_registrations() -> dict[str, Any]:
    with _LOCK:
        providers = _read_registry()
        return {"registrations": [_public_status(provider_id, providers.get(provider_id)) for provider_id in PROVIDER_MODES]}


def status(provider_id: str) -> dict[str, Any]:
    if provider_id not in PROVIDER_MODES:
        raise RegistrationError("invalid_provider", "Unknown provider registration.")
    with _LOCK:
        return _public_status(provider_id, _read_registry().get(provider_id))


def save_registration(
    provider_id: str,
    auth_mode: str,
    model_id: str | None,
    base_url: str | None,
    api_key: str | None,
) -> dict[str, Any]:
    if provider_id not in PROVIDER_MODES or auth_mode not in PROVIDER_MODES[provider_id]:
        raise RegistrationError("invalid_registration_method", "This registration method is not supported for the selected provider.")

    clean_model = (model_id or "").strip()
    if clean_model and not MODEL_RE.fullmatch(clean_model):
        raise RegistrationError("invalid_model_id", "Model identifier is invalid.")

    clean_url = (base_url or "").strip().rstrip("/")
    if clean_url and provider_id != "opencode":
        raise RegistrationError("invalid_base_url", "A custom base URL is only supported for OpenCode registrations.")
    if provider_id == "opencode" and not clean_url:
        raise RegistrationError("invalid_base_url", "Enter the OpenCode server URL.")
    if clean_url:
        try:
            parsed = urlsplit(clean_url)
            _ = parsed.port
        except ValueError:
            raise RegistrationError("invalid_base_url", "Base URL is invalid.") from None
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password:
            raise RegistrationError("invalid_base_url", "Base URL must be an HTTP(S) URL without embedded credentials.")
        if parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise RegistrationError("invalid_base_url", "Remote OpenCode endpoints must use HTTPS.")

    with _LOCK:
        existing = _read_registry()
        if auth_mode in SECRET_MODES:
            if api_key is not None:
                secret = api_key.strip()
                if len(secret) < 8 or len(secret) > 4096 or "\n" in secret or "\r" in secret:
                    raise RegistrationError("invalid_api_key", "Credential is invalid.")
                try:
                    _secure_keyring().set_password(SERVICE_NAME, provider_id, secret)
                except Exception:
                    raise RegistrationError("secure_store_unavailable", "The operating-system credential store could not save the credential.") from None
            else:
                try:
                    current = _secure_keyring().get_password(SERVICE_NAME, provider_id)
                except Exception:
                    raise RegistrationError("secure_store_unavailable", "The operating-system credential store could not read the credential.") from None
                if not current:
                    raise RegistrationError("authentication_required", "Provide a credential before saving this registration.", "needs_authentication")
        elif api_key:
            raise RegistrationError("unexpected_secret", "This registration method does not accept an API key.")

        providers = dict(existing)
        providers[provider_id] = {
            "auth_mode": auth_mode,
            **({"model_id": clean_model} if clean_model else {}),
            **({"base_url": clean_url} if clean_url else {}),
            "updated_at": utc_now(),
        }
        _write_registry(providers)
        return _public_status(provider_id, providers[provider_id])


def get_registration(provider_id: str) -> dict[str, Any]:
    if provider_id not in LIVE_PROVIDER_IDS:
        raise RegistrationError("provider_not_integrated", "This provider is not integrated with ADL chat.")
    with _LOCK:
        config = _read_registry().get(provider_id)
        if not isinstance(config, dict):
            raise RegistrationError("provider_not_configured", "Register this provider before using it.", "needs_authentication")
        return dict(config)


def saved_credential(provider_id: str) -> str | None:
    """Read a saved credential for an internal provider adapter only.

    Callers must never return or log this value through an API response.
    """
    if provider_id not in PROVIDER_MODES:
        raise RegistrationError("invalid_provider", "Unknown provider registration.")
    with _LOCK:
        config = _read_registry().get(provider_id)
        if not isinstance(config, dict) or config.get("auth_mode") not in SECRET_MODES:
            return None
        try:
            return _secure_keyring().get_password(SERVICE_NAME, provider_id)
        except RegistrationError:
            raise
        except Exception:
            raise RegistrationError("secure_store_unavailable", "The operating-system credential store could not read the credential.") from None


def runtime_binding(provider_id: str, model_id: str) -> RuntimeRegistration:
    with _LOCK:
        config = get_registration(provider_id)
        mode = config.get("auth_mode")
        if mode not in PROVIDER_MODES[provider_id]:
            raise RegistrationError("invalid_registration_method", "Unsupported authentication method.")
        if not model_id or config.get("model_id") != model_id:
            raise RegistrationError("model_registration_mismatch", "Select the model saved in this provider registration.")
        try:
            credential = _secure_keyring().get_password(SERVICE_NAME, provider_id) if mode in SECRET_MODES else None
        except Exception:
            raise RegistrationError("secure_store_unavailable", "The operating-system credential store could not read the credential.") from None
        if mode in SECRET_MODES and not credential:
            raise RegistrationError("authentication_required", "Provide a credential before using this provider.", "needs_authentication")
        return RuntimeRegistration(provider_id, model_id, mode, str(config.get("updated_at", "")), credential)


def mark_verified(binding: RuntimeRegistration) -> dict[str, Any]:
    provider_id, model_id = binding.provider_id, binding.model_id
    if provider_id not in LIVE_PROVIDER_IDS:
        raise RegistrationError("provider_not_integrated", "This provider is not integrated with ADL chat.")
    with _LOCK:
        providers = _read_registry()
        config = providers.get(provider_id)
        if not isinstance(config, dict) or config.get("model_id") != model_id or config.get("updated_at", "") != binding.revision:
            raise RegistrationError("registration_changed", "The provider registration changed during the request. Check the current registration again.")
        config = dict(config)
        config["last_verified_model_id"] = model_id
        config["last_verified_at"] = utc_now()
        config.pop("last_error_state", None)
        providers[provider_id] = config
        _write_registry(providers)
        _runtime_failures.pop(provider_id, None)
        return _public_status(provider_id, config)


def mark_failed(binding: RuntimeRegistration, state: str = "error") -> None:
    with _LOCK:
        failure_state = "needs_authentication" if state == "needs_authentication" else "configured_unverified"
        _runtime_failures[binding.provider_id] = (binding.revision, failure_state)
        providers = _read_registry()
        config = providers.get(binding.provider_id)
        if not isinstance(config, dict) or config.get("updated_at", "") != binding.revision:
            return
        config = dict(config)
        config.pop("last_verified_model_id", None)
        config.pop("last_verified_at", None)
        config["last_error_state"] = failure_state
        providers[binding.provider_id] = config
        _write_registry(providers)


def _write_registry(providers: dict[str, dict[str, Any]]) -> None:
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix="provider-registry-", suffix=".tmp", dir=str(REGISTRY_PATH.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump({"schema": "adl.provider_registry.v1", "providers": providers}, stream, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, REGISTRY_PATH)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
