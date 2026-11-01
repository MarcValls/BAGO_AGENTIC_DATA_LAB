import json
from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.whatsapp import WhatsAppSession
from src.api.whatsapp_routes import create_whatsapp_router


@pytest.fixture
def session(tmp_path, monkeypatch):
    monkeypatch.setattr("src.whatsapp.session.find_brave", lambda: "C:/Brave/brave.exe")
    return WhatsAppSession(tmp_path)


def test_unconfigured_has_no_side_effects(session):
    assert session.status()["state"] == "not_configured"
    assert not (session.root / "config.json").exists()


def test_config_survives_new_service(session):
    assert session.configure("BAGO empresa", True)["state"] == "disconnected"
    assert WhatsAppSession(session.root).status()["label"] == "BAGO empresa"


def test_legacy_enabled_is_not_automatic_authority(session):
    (session.root / "config.json").write_text(json.dumps({"label": "Legacy", "enabled": True}))
    assert session.status()["configured"] is True
    assert session.authorization_identity() is None
    session.configure("Explicit connection configuration", True)
    identity = session.authorization_identity()
    assert isinstance(identity, str) and len(identity) == 64
    session.configure("Renamed", True)
    assert session.authorization_identity() == identity
    assert WhatsAppSession(session.root).authorization_identity() == identity
    assert "authorization" not in json.loads((session.root / "config.json").read_text())


@pytest.mark.parametrize("observation,state", [({"authenticated": True, "qr": False}, "connected"),
    ({"authenticated": False, "qr": True}, "linking"), ({}, "unknown"),
    ({"authenticated": True, "qr": True}, "linking")])
def test_fresh_observed_status(session, monkeypatch, observation, state):
    session.configure("Test", True)
    monkeypatch.setattr(session, "_owner", lambda: {"pid": 7, "port": 9333})
    client = Mock()
    client.evaluate.return_value = observation
    monkeypatch.setattr(session, "_client", lambda: client)
    assert session.status()["state"] == state
    client.evaluate.assert_called_once()


def test_probe_failure_never_cached_connected(session, monkeypatch):
    session.configure("Test", True)
    monkeypatch.setattr(session, "_owner", lambda: {"pid": 7})
    monkeypatch.setattr(session, "_client", Mock(side_effect=RuntimeError("SECRET PAGE")))
    result = session.status()
    assert result["state"] == "unknown"
    assert "SECRET" not in json.dumps(result)


def test_missing_brave(session, monkeypatch):
    session.configure("Test", True)
    monkeypatch.setattr("src.whatsapp.session.find_brave", lambda: None)
    assert session.status()["state"] == "unavailable"


@pytest.mark.parametrize("command", [
    'brave.exe --user-data-dir=C:/other --remote-debugging-port=9333',
    'brave.exe --user-data-dir=PROFILE-other --remote-debugging-port=9333',
    'brave.exe --user-data-dir=PROFILE --remote-debugging-port=93330',
    'evil.exe --user-data-dir=PROFILE --remote-debugging-port=9333'])
def test_foreign_profile_never_controlled(session, monkeypatch, command):
    (session.root / "browser.json").write_text(json.dumps({"profile": str(session.profile), "port": 9333, "pid": 7}))
    monkeypatch.setattr("src.whatsapp.session.process_arguments", lambda pid: command.replace("PROFILE", str(session.profile)))
    assert session._owner() is None
    monkeypatch.setattr(session, "_client", Mock(side_effect=AssertionError("MUST NOT CONTROL")))
    session.close()
    session._client.assert_not_called()


def test_exact_owned_profile(session, monkeypatch):
    (session.root / "browser.json").write_text(json.dumps({"profile": str(session.profile), "port": 9333, "pid": 7}))
    monkeypatch.setattr("src.whatsapp.session.process_arguments", lambda pid: f'"C:/Program Files/Brave/brave.exe" "--user-data-dir={session.profile}" --remote-debugging-port=9333')
    assert session._owner()["pid"] == 7


def test_reserved_port_rejected(session, monkeypatch):
    (session.root / "browser.json").write_text(json.dumps({"profile": str(session.profile), "port": 9222, "pid": 7}))
    assert session._owner() is None


def test_api_confirmation_and_redaction(session, monkeypatch):
    app = FastAPI()
    app.include_router(create_whatsapp_router(session))
    client = TestClient(app)
    assert client.post("/api/whatsapp/session/open", json={"confirmed": False}).status_code == 409
    assert client.put("/api/whatsapp/session", json={"label": "x", "enabled": "yes"}).status_code == 422
    assert client.put("/api/whatsapp/session", json={"label": "x", "enabled": True, "url": "bad"}).status_code == 422
    assert client.get("/api/whatsapp/session").json()["state"] == "not_configured"
    monkeypatch.setattr(session, "open", Mock(side_effect=RuntimeError("SECRET")))
    response = client.post("/api/whatsapp/session/open", json={"confirmed": True})
    assert response.status_code == 503 and "SECRET" not in response.text


def test_corrupt_config_unknown(session):
    (session.root / "config.json").write_text("bad json")
    assert session.status()["state"] == "unknown"


def test_router_factory_is_lazy(session):
    factory = Mock(return_value=session)
    app = FastAPI()
    app.include_router(create_whatsapp_router(session_factory=factory))
    factory.assert_not_called()
    assert TestClient(app).get("/api/whatsapp/session").status_code == 200
    factory.assert_called_once()


def test_open_only_owned_profile_and_own_port(session, monkeypatch):
    session.configure("Test", True)
    launcher = Mock(return_value=Mock(pid=12345))
    monkeypatch.setattr("src.whatsapp.session.subprocess.Popen", launcher)
    session.open()
    args = launcher.call_args_list[0][0][0]
    assert f"--user-data-dir={session.profile}" in args
    assert "--remote-debugging-port=9222" not in args
    assert "--remote-debugging-address=127.0.0.1" in args
    assert args[-1] == "https://web.whatsapp.com/"


def test_existing_unowned_browser_not_restarted(session, monkeypatch):
    session.configure("Test", True)
    (session.root / "browser.json").write_text(json.dumps({"pid": 7, "port": 9222, "profile": "foreign"}))
    monkeypatch.setattr("src.whatsapp.session.process_arguments", lambda pid: "foreign.exe")
    launcher = Mock()
    monkeypatch.setattr("src.whatsapp.session.subprocess.Popen", launcher)
    with pytest.raises(ValueError, match="ownership_unproven"):
        session.open()
    launcher.assert_not_called()
