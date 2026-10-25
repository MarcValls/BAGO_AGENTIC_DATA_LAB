"""Fixture-only contract for selecting a capability form, never its execution."""
from types import SimpleNamespace

from fastapi.testclient import TestClient
import pytest

from src.api import server
from src.conversations import ConversationStore


@pytest.fixture
def form_route(tmp_path, monkeypatch):
    store = ConversationStore(tmp_path / "conversations.sqlite3")
    conversation = store.create("assistant", "app-assistant")
    monkeypatch.setattr(server, "CONVERSATIONS", store)
    forbidden_calls = []
    trace_calls = []

    def forbidden(*args, **kwargs):
        forbidden_calls.append((args, kwargs))
        pytest.fail("Selecting a form must not consult a provider, inspect/scan files or grant/consume authority")

    for name in ("current_workspace_root", "_consume_workspace_read_authorization",
                 "_consume_workspace_scan_authorization", "_consume_web_authorization",
                 "scan_code_duplicates", "run_workspace_code_scan", "_read_agent_records"):
        monkeypatch.setattr(server, name, forbidden)
    for name in ("active_selection", "chat_turn", "chat"):
        monkeypatch.setattr(server.provider_runtime, name, forbidden)
    for name in ("WORKSPACE_READ_AUTHORIZATIONS", "WORKSPACE_DIRECTORY_AUTHORIZATIONS", "WEB_READ_AUTHORIZATIONS"):
        monkeypatch.setattr(server, name, SimpleNamespace(issue=forbidden, consume=forbidden))

    def fixture_trace(**kwargs):
        trace_calls.append(kwargs)
        assert kwargs["provider_id"] == "application"
        assert kwargs["model_id"] == "not_used"
        assert kwargs["sources"] == kwargs["read_events"] == []
        return {"trace_id": "trace-r12-fixture", "trace_state": "fixture_only"}

    monkeypatch.setattr(server, "_record_agent_chat_trace", fixture_trace)
    return store, conversation, TestClient(server.app), forbidden_calls, trace_calls


@pytest.mark.parametrize("mode", ["baseline", "bago5"])
@pytest.mark.parametrize("attached_grants", [False, True])
def test_explicit_capability_persists_form_without_using_provider_or_authority(form_route, mode, attached_grants):
    store, conversation, client, forbidden_calls, trace_calls = form_route
    request = {"conversation_id": conversation["id"], "revision": 0,
               "message": "Prepare the synthetic duplicate-code review form.",
               "capability_id": "workspace.scan_duplicates", "cognitive_mode": mode}
    if attached_grants:
        request.update(workspace_read_authorization_id="fixture-unused-read",
                       workspace_scan_authorization_id="fixture-unused-scan",
                       web_read_authorization_id="fixture-unused-web")
    response = client.post("/api/chat/control", json=request)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["operation"] == "workspace_scan"
    assert result["control_capability"] == "workspace.scan_duplicates"
    assert "autoriza" in result["assistant_message"]
    assert result["sources"] == result["read_events"] == []
    assert result["revision"] == 2
    saved = store.get(conversation["id"])
    assert result["conversation"] == saved
    assert [message["role"] for message in saved["messages"]] == ["user", "assistant"]
    assert saved["messages"][0]["content"] == request["message"]
    assert saved["messages"][1]["references"]["control_capability"] == "workspace.scan_duplicates"
    assert saved["messages"][1]["content"] == result["assistant_message"]
    assert len(trace_calls) == 1 and trace_calls[0]["control_operation"] == "workspace_scan"
    assert forbidden_calls == []


@pytest.mark.parametrize("capability", ["mcp.execute", "sandbox.execute", "agent.run",
                                         "workspace.scan_duplicates.extra", "", 12, {}, True])
def test_unknown_capability_fails_closed_before_conversation_or_permission_effects(form_route, capability):
    store, conversation, client, forbidden_calls, trace_calls = form_route
    before = store.get(conversation["id"])
    response = client.post("/api/chat/control", json={"conversation_id": conversation["id"],
        "revision": 0, "message": "Fixture", "capability_id": capability})
    assert response.status_code == 422
    assert store.get(conversation["id"]) == before
    assert forbidden_calls == trace_calls == []


def test_stale_revision_does_not_persist_even_a_valid_capability(form_route):
    store, conversation, client, forbidden_calls, trace_calls = form_route
    before = store.get(conversation["id"])
    response = client.post("/api/chat/control", json={"conversation_id": conversation["id"],
        "revision": 42, "message": "Fixture", "capability_id": "workspace.scan_duplicates"})
    assert response.status_code == 409
    assert store.get(conversation["id"]) == before
    assert forbidden_calls == trace_calls == []


def test_agent_owned_conversation_cannot_receive_the_app_capability_form(form_route):
    store, _, client, forbidden_calls, trace_calls = form_route
    conversation = store.create("agent", "fixture-agent")
    before = store.get(conversation["id"])
    response = client.post("/api/chat/control", json={"conversation_id": conversation["id"],
        "revision": 0, "message": "Fixture", "capability_id": "workspace.scan_duplicates"})
    assert response.status_code == 404
    assert store.get(conversation["id"]) == before
    assert forbidden_calls == trace_calls == []


@pytest.mark.parametrize("include_null", [False, True])
def test_absent_or_null_selection_keeps_the_existing_operation(form_route, monkeypatch, tmp_path, include_null):
    store, conversation, client, forbidden_calls, trace_calls = form_route
    monkeypatch.setattr(server, "current_workspace_root", lambda: tmp_path)
    monkeypatch.setattr(server, "_consume_workspace_read_authorization", lambda *a, **k: [])
    monkeypatch.setattr(server, "_consume_workspace_scan_authorization", lambda *a, **k: [])
    monkeypatch.setattr(server, "_consume_web_authorization", lambda *a, **k: None)
    request = {"conversation_id": conversation["id"], "revision": 0, "message": "hola ayuda", "operation": "help"}
    if include_null:
        request["capability_id"] = None
    response = client.post("/api/chat/control", json=request)
    assert response.status_code == 200
    assert response.json()["operation"] == "help"
    assert "control_capability" not in response.json()
    assert store.get(conversation["id"])["revision"] == 2
    assert trace_calls[0]["control_operation"] == "help"
    assert forbidden_calls == []
