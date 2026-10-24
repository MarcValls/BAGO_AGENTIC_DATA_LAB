import asyncio
import json

import pytest
from fastapi import HTTPException

from src.api import server
from src.conversations import ConversationStore
from src.providers import ollama


@pytest.mark.parametrize("state,message", [
    ("error", "Secure credential storage is unavailable."),
    ("needs_authentication", "Ollama rejected the configured authentication."),
    ("local_service_unavailable", None),
    ("unsupported_runtime", None),
    ("future_unknown_state", None),
])
def test_selected_model_preserves_provider_failure_with_configured_model(monkeypatch, state, message):
    monkeypatch.setattr(ollama, "status", lambda: {"model_id": "test-model", "state": state, "message": message})
    with pytest.raises(HTTPException) as failure:
        server._selected_model_id()
    assert failure.value.detail["state"] == state
    assert "Choose an Ollama model" not in failure.value.detail["message"]
    if message:
        assert failure.value.detail["message"] == message


@pytest.mark.parametrize("state", ["ready", "configured_unverified"])
def test_only_ready_and_unverified_configurations_admit_selected_model(monkeypatch, state):
    monkeypatch.setattr(ollama, "status", lambda: {"model_id": "test-model", "state": state})
    assert server._selected_model_id() == "test-model"
    monkeypatch.setattr(ollama, "status", lambda: {"model_id": None, "state": state})
    with pytest.raises(HTTPException) as failure:
        server._selected_model_id()
    assert failure.value.detail["code"] == "model_selection_required"


@pytest.fixture
def provider(monkeypatch, tmp_path):
    config = tmp_path / "ollama.json"
    config.write_text(json.dumps({"auth_mode": "api_key", "model_id": "test-model"}), encoding="utf-8")
    monkeypatch.setattr(ollama, "CONFIG_PATH", config)
    monkeypatch.setattr(ollama, "_get_api_key", lambda required=True: "PRIVATE_KEY_SENTINEL")
    monkeypatch.setattr(ollama, "_last_successful_model_call", None)
    monkeypatch.setattr(ollama, "_last_successful_at", None)
    monkeypatch.setattr(ollama, "_authentication_failed", False)
    monkeypatch.setenv("BAGO_RUNTIME_MODE", "host")
    return ollama


def test_authentication_failure_survives_status_until_save_or_success(provider, monkeypatch):
    real_request = provider._request
    monkeypatch.setattr(provider, "_request", lambda *args, **kwargs: {"message": {"content": "Success"}})
    assert provider.chat("test-model", []) == "Success"
    assert provider.status()["state"] == "ready"

    class UnauthorizedSession:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def request(self, *args, **kwargs):
            return type("Response", (), {"status_code": 401})()

    monkeypatch.setattr(provider, "_request", real_request)
    monkeypatch.setattr(provider.requests, "Session", UnauthorizedSession)
    with pytest.raises(provider.ProviderError) as failure:
        provider.chat("test-model", [])
    assert failure.value.code == "authentication_failed"
    assert provider._last_successful_model_call is None
    assert provider._last_successful_at is None
    for _ in range(2):
        status = provider.status()
        assert status["state"] == "needs_authentication"
        assert "rejected" in status["message"]
        assert "PRIVATE_KEY_SENTINEL" not in json.dumps(status)
    saved = provider.save_config("api_key", "test-model", None)
    assert saved["state"] == "configured_unverified"
    assert saved["auth_mode"] == "api_key"
    with pytest.raises(provider.ProviderError):
        provider.chat("test-model", [])
    assert provider.status()["state"] == "needs_authentication"
    monkeypatch.setattr(provider, "_request", lambda *args, **kwargs: {"message": {"content": "Recovered"}})
    assert provider.chat("test-model", []) == "Recovered"
    assert provider.status()["state"] == "ready"


@pytest.mark.parametrize("result", [{}, {"message": {"content": ""}}, {"message": {"tool_calls": [{"function": {"name": "example"}}]}}])
def test_failed_text_generation_clears_previous_success(provider, monkeypatch, result):
    monkeypatch.setattr(provider, "_last_successful_model_call", "test-model")
    monkeypatch.setattr(provider, "_last_successful_at", "earlier-success")
    monkeypatch.setattr(provider, "_request", lambda *args, **kwargs: result)
    with pytest.raises(provider.ProviderError):
        provider.chat("test-model", [])
    assert provider.status()["state"] == "configured_unverified"
    assert provider._last_successful_model_call is None
    assert provider._last_successful_at is None


@pytest.mark.parametrize("mode", ["baseline", "bago5"])
def test_help_uses_model_and_persists_focus_only_when_cognition_enabled(monkeypatch, tmp_path, mode):
    store = ConversationStore(tmp_path / "chat.sqlite3")
    conversation = store.create("assistant", "app-assistant")
    monkeypatch.setattr(server, "CONVERSATIONS", store)
    monkeypatch.setattr(server, "AGENT_CHAT_TRACE_DIR", tmp_path / "traces")
    monkeypatch.setattr(server.provider_runtime, "active_selection", lambda: {
        "provider_id": "ollama-cloud", "model_id": "test-model",
        "label": "Fixture Ollama", "state": "configured_unverified",
    })
    calls = []
    monkeypatch.setattr(server.ollama, "chat", lambda model, messages: calls.append(messages) or "Experimental greeting")
    result = asyncio.run(server.control_chat(server.ControlChatRequest(
        operation="help", message="Hola, compara opciones con evidencia", cognitive_mode=mode,
        conversation_id=conversation["id"], revision=0,
    )))
    assert result["revision"] == 2
    if mode == "baseline":
        assert calls == []
        assert result["operation"] == "help"
        assert "cognitive_trace" not in result
        assert not (tmp_path / "traces" / "cognition").exists()
        control_trace=json.loads((tmp_path / "traces" / (result["trace"]["trace_id"]+".json")).read_bytes())
        assert control_trace['events'][0]['name']=='assistant.control'
        assert control_trace['events'][0]['attributes']['model_invoked'] is False
    else:
        assert len(calls) == 1
        assert "BAGO5 experimental cognitive context" in calls[0][0]["content"]
        assert result["operation"] == "chat"
        assert result["assistant_message"] == "Experimental greeting"
        focus = result["cognitive_trace"]
        assert focus["enabled"] and focus["mode"] == "bago5" and focus["focus"]
        assert result["conversation"]["messages"][1]["references"]["cognitive_trace"] == focus
        trace = tmp_path / "traces" / "cognition" / f"{focus['trace_id']}.json"
        assert trace.is_file()
        assert "Experimental greeting" not in trace.read_text(encoding="utf-8")
