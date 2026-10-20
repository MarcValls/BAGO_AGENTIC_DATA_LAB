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
        assert params == {"type": "chatgpt", "codexStreamlinedLogin": True}
        return {"type": "chatgpt", "loginId": "login-test", "authUrl": self.auth_url}

    def notification(self, _deadline: float) -> dict:
        return {"method": "account/login/completed", "params": {"loginId": "login-test", "success": True}}

    def close(self) -> None:
        self.closed = True


@pytest.fixture(autouse=True)
def isolated_login_flows(monkeypatch):
    monkeypatch.setattr(codex, "_LOGIN_FLOWS", {})


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


def test_codex_login_rejects_non_openai_authorization_url(monkeypatch):
    client = FakeCodexClient("https://attacker.invalid/login")
    monkeypatch.setattr(codex, "CodexClient", lambda: client)

    with pytest.raises(registration.RegistrationError, match="válido"):
        codex.start_login()
    assert client.closed
