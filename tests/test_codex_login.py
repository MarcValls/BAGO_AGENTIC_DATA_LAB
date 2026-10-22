from __future__ import annotations

import time

import pytest

from src.providers import codex, registration


class FakeCodexClient:
    def __init__(self, auth_url: str = "https://auth.openai.com/oauth/authorize?state=test") -> None:
        self.auth_url = auth_url
        self.closed = False

    def request(self, method: str, params: dict) -> dict:
        assert method == "account/login/start"
        assert params == {"type": "chatgpt", "codexStreamlinedLogin": True, "useHostedLoginSuccessPage": True}
        return {"type": "chatgpt", "loginId": "login-test", "authUrl": self.auth_url}

    def notification(self, _deadline: float) -> dict:
        return {"method": "account/login/completed", "params": {"loginId": "login-test", "success": True}}

    def close(self) -> None:
        self.closed = True


@pytest.fixture(autouse=True)
def isolated_login_flows(monkeypatch, tmp_path):
    monkeypatch.setattr(codex, "_LOGIN_FLOWS", {})
    monkeypatch.setattr(registration, "REGISTRY_PATH", tmp_path / "registry.json")
    monkeypatch.setattr(registration, "_runtime_failures", {})


def test_codex_login_waits_for_native_chatgpt_completion(monkeypatch):
    client = FakeCodexClient()
    monkeypatch.setattr(codex, "CodexClient", lambda: client)

    started = codex.start_login()
    assert started == {
        "login_id": "login-test",
        "auth_url": "https://auth.openai.com/oauth/authorize?state=test",
        "state": "pending",
    }

    deadline = time.monotonic() + 1
    while (codex.login_status("login-test")["state"] == "pending" or not client.closed) and time.monotonic() < deadline:
        time.sleep(0.01)
    assert codex.login_status("login-test")["state"] == "completed"
    assert client.closed


@pytest.mark.parametrize("url", ["https://attacker.invalid/login", "https://auth.openai.com:invalid/login", "https://user@auth.openai.com/login"])
def test_codex_login_rejects_non_openai_authorization_url(monkeypatch, url):
    client = FakeCodexClient(url)
    monkeypatch.setattr(codex, "CodexClient", lambda: client)

    with pytest.raises(registration.RegistrationError, match="válido"):
        codex.start_login()
    assert client.closed


def test_codex_api_key_login_uses_native_api_and_invalidates_old_verification(monkeypatch):
    registration.save_registration("codex", "codex_cli", "codex-test", None, None)
    registration.mark_verified(registration.runtime_binding("codex", "codex-test"))
    calls = []

    class ApiClient(FakeCodexClient):
        def request(self, method, params):
            calls.append((method, params))
            if method == "account/login/start":
                return {"type": "apiKey"}
            assert method == "account/read"
            return {"account": {"type": "apiKey"}}

    client = ApiClient()
    monkeypatch.setattr(codex, "CodexClient", lambda: client)
    result = codex.start_login("api_key", "TEST_API_KEY_FIXTURE")
    assert calls[0] == ("account/login/start", {"type": "apiKey", "apiKey": "TEST_API_KEY_FIXTURE"})
    assert result["state"] == "completed" and client.closed
    assert result["registration"]["state"] == "configured_unverified"
    assert "TEST_API_KEY_FIXTURE" not in str(result)
    assert "TEST_API_KEY_FIXTURE" not in registration.REGISTRY_PATH.read_text()


@pytest.mark.parametrize("mode,key", [("api_key", None), ("api_key", "short"), ("api_key", "invalid\nkey"), ("chatgpt", "TEST_API_KEY_FIXTURE"), ("unknown", None)])
def test_codex_rejects_invalid_login_before_starting_process(monkeypatch, mode, key):
    monkeypatch.setattr(codex, "CodexClient", lambda: pytest.fail("Must not launch Codex"))
    with pytest.raises(registration.RegistrationError):
        codex.start_login(mode, key)


def test_codex_api_session_can_discover_models_without_returning_credentials(monkeypatch):
    class SessionClient(FakeCodexClient):
        def request(self, method, params):
            if method == "account/read":
                return {"account": {"type": "apiKey", "apiKey": "TEST_SECRET_NOT_PUBLIC"}}
            assert method == "model/list"
            return {"data": [{"model": "codex-test", "displayName": "Codex test"}]}

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            self.close()

    monkeypatch.setattr(codex, "CodexClient", SessionClient)
    result = codex.session_status(include_models=True)
    assert result["authenticated"] and result["auth_mode"] == "api_key"
    assert result["models"][0]["model_id"] == "codex-test"
    assert "TEST_SECRET_NOT_PUBLIC" not in str(result)


def test_codex_login_endpoint_delegates_and_redacts_invalid_credentials(monkeypatch):
    from fastapi.testclient import TestClient
    from src.api.server import app

    calls = []
    monkeypatch.setattr(codex, "start_login", lambda *args: calls.append(args) or {"state": "completed"})
    with TestClient(app) as client:
        result = client.post("/api/providers/codex/login", json={"auth_mode": "api_key", "api_key": "TEST_API_KEY_FIXTURE"})
        assert result.status_code == 200
        assert calls == [("api_key", "TEST_API_KEY_FIXTURE")]
        assert "TEST_API_KEY_FIXTURE" not in result.text
        invalid = client.post("/api/providers/codex/login", json={"auth_mode": "invalid", "api_key": "TEST_API_KEY_FIXTURE"})
        assert invalid.status_code == 422
        assert "TEST_API_KEY_FIXTURE" not in invalid.text
