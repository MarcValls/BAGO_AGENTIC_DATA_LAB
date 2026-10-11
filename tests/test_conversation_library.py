import asyncio
from pathlib import Path

import pytest

from src.conversations import ConversationConflict, ConversationNotFound, ConversationStore
from src.conversations.library import PROJECT_ID, default_database_path
from src.api import server


def test_default_database_is_per_user_and_outside_repository(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    monkeypatch.delenv("BAGO_CONVERSATION_DB_PATH", raising=False)

    assert default_database_path() == tmp_path / "local" / "BAGO" / "AgenticDataLab" / "conversations" / "library.sqlite3"


def test_owner_scoping_restart_and_message_references_are_persistent(tmp_path: Path):
    database = tmp_path / "library.sqlite3"
    store = ConversationStore(database)
    assistant = store.create("assistant", "ignored", "New conversation")
    agent_one = store.create("agent", "agent-1", "New conversation")
    agent_two = store.create("agent", "agent-1", "Second conversation")

    user = store.append_message(assistant["id"], 0, "user", "Review P1-02")
    assistant_message = store.append_message(
        assistant["id"], user["revision"], "assistant", "Reviewed the supplied excerpt.",
        {"sources": [{"path": "demo.txt", "start_line": 2, "end_line": 3}], "trace": {"trace_id": "trace-demo"}},
    )
    assert assistant_message["sequence"] == 2

    reopened = ConversationStore(database)
    saved = reopened.get(assistant["id"])
    assert saved["project_id"] == PROJECT_ID
    assert saved["messages"][1]["references"]["trace"]["trace_id"] == "trace-demo"
    assert saved["messages"][1]["references"]["sources"][0]["path"] == "demo.txt"
    assert reopened.get(agent_one["id"])["messages"] == []
    assert reopened.get(agent_two["id"])["id"] != reopened.get(agent_one["id"])["id"]


def test_revision_conflicts_and_rename_archive_delete_restore(tmp_path: Path):
    store = ConversationStore(tmp_path / "library.sqlite3")
    conversation = store.create("agent", "agent-a")
    user = store.append_message(conversation["id"], 0, "user", "Hello")
    store.append_message(conversation["id"], user["revision"], "assistant", "Hi")

    with pytest.raises(ConversationConflict):
        store.rename(conversation["id"], 0, "Stale title")

    renamed = store.rename(conversation["id"], 2, "  Reviewed   finding  ")
    assert renamed["title"] == "Reviewed finding"
    archived = store.set_status(conversation["id"], 3, "archived")
    assert archived["status"] == "archived"
    deleted = store.set_status(conversation["id"], 4, "deleted")
    assert deleted["status"] == "deleted"
    with pytest.raises(ConversationNotFound):
        store.get(conversation["id"])

    restored = store.restore(conversation["id"], 5)
    assert restored["status"] == "active"
    assert len(restored["messages"]) == 2


def test_app_assistant_uses_saved_history_and_returns_saved_turn(monkeypatch, tmp_path: Path):
    store = ConversationStore(tmp_path / "library.sqlite3")
    conversation = store.create("assistant", "app-assistant")
    monkeypatch.setattr(server, "CONVERSATIONS", store)
    monkeypatch.setattr(server, "_selected_model_id", lambda: "gemma4:31b-cloud")
    calls = []
    answers = iter(["First answer", "Second answer"])
    monkeypatch.setattr(server.ollama, "chat", lambda model, messages: calls.append(messages) or next(answers))

    first = asyncio.run(server.control_chat(server.ControlChatRequest(
        operation="chat", message="Remember this phrase", conversation_id=conversation["id"], revision=0,
    )))
    second = asyncio.run(server.control_chat(server.ControlChatRequest(
        operation="chat", message="What phrase?", conversation_id=conversation["id"], revision=first["revision"],
    )))

    assert second["revision"] == 4
    assert [message["content"] for message in second["conversation"]["messages"]] == [
        "Remember this phrase", "First answer", "What phrase?", "Second answer",
    ]
    assert any(item == {"role": "assistant", "content": "First answer"} for item in calls[1])
    assert any(item == {"role": "user", "content": "Remember this phrase"} for item in calls[1])
    system_prompt = calls[0][0]["content"]
    assert "help the user design a new agent" in system_prompt
    assert "it is saved only after the user reviews it and explicitly chooses Create agent" in system_prompt
    assert "Never claim that agent creation is unavailable" in system_prompt
    assert "You cannot start jobs or modify files" in system_prompt


def test_app_assistant_greeting_explains_agent_creation_without_model_claims(monkeypatch, tmp_path: Path):
    store = ConversationStore(tmp_path / "conversations.sqlite3")
    conversation = store.create("assistant", "app-assistant")
    monkeypatch.setattr(server, "CONVERSATIONS", store)
    monkeypatch.setattr(server.ollama, "chat", lambda *args, **kwargs: pytest.fail("greeting must use the authoritative capability response"))

    response = asyncio.run(server.control_chat(server.ControlChatRequest(
        operation="help", message="Hola", conversation_id=conversation["id"], revision=0,
    )))

    assert response["operation"] == "help"
    assert "ayudarte a crear uno desde este chat" in response["assistant_message"]
    assert "borrador editable" in response["assistant_message"]
    assert "solo se guarda cuando lo revisas" in response["assistant_message"]
    assert "no inicia trabajos ni modifica archivos" in response["assistant_message"]
    assert [message["role"] for message in response["conversation"]["messages"]] == ["user", "assistant"]

