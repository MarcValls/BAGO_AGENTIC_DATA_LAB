from __future__ import annotations

import io
import time

from copilot import client as copilot_client
from fastapi.testclient import TestClient

from src.api import server
from src.providers import github_copilot


class _LoginProcess:
    def __init__(self) -> None:
        self.stdout = io.StringIO("Open https://github.com/login/device and enter code: AB12-CD34\n")
        self.returncode = 0
        self.terminated = False

    def wait(self) -> int:
        return self.returncode

    def terminate(self) -> None:
        self.terminated = True


def test_device_login_exposes_code_and_confirms_session(monkeypatch) -> None:
    process = _LoginProcess()
    popen_args = []

    monkeypatch.setattr(copilot_client, "_get_bundled_cli_path", lambda: "copilot.exe")
    monkeypatch.setattr(github_copilot.os.path, "isfile", lambda _path: True)
    monkeypatch.setattr(github_copilot.subprocess, "Popen", lambda *args, **kwargs: popen_args.append((args, kwargs)) or process)
    monkeypatch.setattr(github_copilot, "auth_status", lambda: {"authenticated": True})
    with github_copilot._LOGIN_LOCK:
        github_copilot._LOGIN_FLOWS.clear()

    login = github_copilot.start_login()

    assert login["user_code"] == "AB12-CD34"
    assert login["verification_uri"] == "https://github.com/login/device"
    assert popen_args[0][0][0] == ["copilot.exe", "login", "--device-code"]
    assert popen_args[0][1].get("shell", False) is False

    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        status = github_copilot.login_status(login["login_id"])
        if status["state"] == "completed":
            break
        time.sleep(0.01)

    assert status["state"] == "completed"
    assert not process.terminated


def test_copilot_session_endpoint_uses_auth_adapter(monkeypatch) -> None:
    monkeypatch.setattr(github_copilot, "auth_status", lambda: {"authenticated": False})

    response = TestClient(server.app).get("/api/providers/github-copilot/session")

    assert response.status_code == 200
    assert response.json() == {"authenticated": False}


def test_copilot_models_endpoint_returns_available_model_choices(monkeypatch) -> None:
    expected = {"provider_id": "github-copilot", "models": [{
        "provider_id": "github-copilot", "model_id": "gpt-example", "display_name": "GPT Example",
        "source": "github_copilot_sdk", "availability_confidence": "listed",
    }], "source": "github_copilot_sdk", "availability_confidence": "listed"}
    monkeypatch.setattr(github_copilot, "discover_models", lambda auth_mode, api_key: expected)

    response = TestClient(server.app).post("/api/providers/github-copilot/models", json={"auth_mode": "copilot_cli"})

    assert response.status_code == 200
    assert response.json() == expected
