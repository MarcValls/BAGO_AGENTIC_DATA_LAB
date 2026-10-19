"""Write-only provider registration storage for the ADL settings UI.

This module records provider setup metadata and keeps supplied credentials in
an operating-system credential store. It does not authenticate to providers or
make them available to chat/agent execution.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

MODEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")
SERVICE_NAME = "BAGO.AgenticDataLab.ProviderRegistration"
REGISTRY_PATH = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "BAGO" / "AgenticDataLab" / "provider-registry.json"
_LOCK = threading.RLock()

PROVIDER_MODES: dict[str, set[str]] = {
    "codex": {"codex_cli"},
    "openai-platform": {"api_key"},
    "github-copilot": {"copilot_cli", "token"},
    "anthropic": {"api_key"},
    "openrouter": {"api_key"},
    "opencode": {"api_key", "local"},
}
SECRET_MODES = {"api_key", "token"}


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
    if not isinstance(config, dict) or config.get("auth_mode") not in PROVIDER_MODES[provider_id]:
        return {"provider_id": provider_id, "state": "not_configured", "auth_mode": None, "model_id": None, "base_url": None, "has_credential": False}

    mode = config["auth_mode"]
    has_credential = False
    credential_store_state = "not_required"
    if mode in SECRET_MODES:
        try:
            has_credential = bool(_secure_keyring().get_password(SERVICE_NAME, provider_id))
            credential_store_state = "available"
        except RegistrationError:
            credential_store_state = "unavailable"

    state = "configured_unverified"
    if mode in SECRET_MODES and not has_credential:
        state = "needs_authentication" if credential_store_state == "available" else "credential_store_unavailable"
    return {
        "provider_id": provider_id,
        "state": state,
        "auth_mode": mode,
        "model_id": config.get("model_id"),
        "base_url": config.get("base_url"),
        "has_credential": has_credential,
        "credential_store_state": credential_store_state,
        "updated_at": config.get("updated_at"),
        "runtime_support": "not_integrated",
    }


def list_registrations() -> dict[str, Any]:
    with _LOCK:
        providers = _read_registry()
        return {"registrations": [_public_status(provider_id, providers.get(provider_id)) for provider_id in PROVIDER_MODES]}


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
                _secure_keyring().set_password(SERVICE_NAME, provider_id, secret)
            else:
                try:
                    current = _secure_keyring().get_password(SERVICE_NAME, provider_id)
                except RegistrationError:
                    raise
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

        return _public_status(provider_id, providers[provider_id])
