"""Actual control-chat dispatch, mocked inference and transport; no live sending."""
import asyncio
import json
from datetime import datetime, timezone
from src.api import server
from src.communications import CommunicationService
from src.conversations import ConversationStore


def test_orchestrator_prepares_edits_and_restores_reference(monkeypatch, tmp_path):
    service = CommunicationService(tmp_path / "state", workspace_root=tmp_path,
                                   clock=lambda: datetime(2026, 10, 22, 12, tzinfo=timezone.utc))
    contact = service.create_contact("Fixture client", "+34600000001")
    store = ConversationStore(tmp_path / "conversations.sqlite3")
    conv = store.create("assistant", "app-assistant")
    monkeypatch.setattr(server, "CONVERSATIONS", store)
    monkeypatch.setattr(server, "_communication_service", lambda: service)
    monkeypatch.setattr(server.provider_runtime, "active_selection", lambda: {"provider_id": "codex", "model_id": "fixture"})
    fields = {"contact_id": contact["id"], "text": "First draft"}
    seen = []
    def chat(*args, **kwargs):
        seen.append((args, kwargs))
        return {"tool_calls": [{"function": {"name": "resolve_control_request", "arguments": {"decision": "communication_draft", "communication": dict(fields), "reply": "Review"}}}]}
    monkeypatch.setattr(server.provider_runtime, "chat_turn", chat)
    result = asyncio.run(server.control_chat(server.ControlChatRequest(message="Prepara un mensaje al cliente", conversation_id=conv["id"], revision=0)))
    d = result["communication_draft"]
    assert d["state"] == "draft" and service.runs() == []
    assert store.get(conv["id"])["messages"][-1]["references"]["communication_draft"]["id"] == d["id"]
    fields.clear()
    fields.update(draft_id=d["id"], expected_revision=d["revision"], text="Edited draft")
    edited = asyncio.run(server.control_chat(server.ControlChatRequest(message="Cambia el texto", conversation_id=conv["id"], revision=result["revision"])))
    assert edited["communication_draft"]["text"] == "Edited draft"
    assert edited["communication_draft"]["revision"] != d["revision"]
    assert service.runs() == []
    assert "never confirm" in seen[0][0][2][0]["content"]


def test_resolver_rejects_model_approval_and_unknown_fields():
    assert server._control_request_from_arguments({"decision": "send", "reply": "done"}) is None
    resolved = server._control_request_from_arguments({"decision": "communication_draft", "communication": {"confirmed": True}})
    assert resolved["decision"] == "clarify"
