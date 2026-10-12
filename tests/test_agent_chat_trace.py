import asyncio
import hashlib
import json
from pathlib import Path

from fastapi import Response

from src.api import server
from src.conversations import ConversationStore


def test_agent_chat_pins_profile_model_and_returns_trace_headers(monkeypatch, tmp_path: Path):
    class Agent:
        id = "agent-demo"

        class Config:
            system_prompt = "Review only supplied findings."
            model_id = "kimi-k2.6"
            provider_id = "ollama-cloud"

        config = Config()

    calls = []
    monkeypatch.setattr(server, "_load_agent", lambda _agent_id: Agent())
    store = ConversationStore(tmp_path / "conversations.sqlite3")
    conversation = store.create("agent", "agent-demo")
    monkeypatch.setattr(server, "CONVERSATIONS", store)
    monkeypatch.setattr(server.ollama, "chat", lambda model, messages: calls.append((model, messages)) or "Finding reviewed.")
    monkeypatch.setattr(server, "AGENT_CHAT_TRACE_DIR", tmp_path)
    monkeypatch.setattr(server, "export_local_trace_to_otlp", lambda *args, **kwargs: None)
    monkeypatch.setenv("BAGO_OTEL_EXPORTER_OTLP_ENDPOINT", "")

    response = Response()
    result = asyncio.run(server.chat_with_agent(
        "agent-demo",
        server.AgentChatRequest(message="P1-02 run token demo-20261009", conversation_id=conversation["id"], revision=0),
        response,
    ))

    assert calls[0][0] == "kimi-k2.6"
    assert result["agent_id"] == "agent-demo"
    assert result["assistant_message"] == "Finding reviewed."
    assert result["conversation"]["messages"][1]["content"] == "Finding reviewed."
    assert result["conversation"]["messages"][1]["references"]["trace"]["trace_id"] == response.headers["X-Bago-Trace-Id"]
    assert response.headers["X-Bago-Trace-State"] == "local_only"
    assert response.headers["X-Bago-Trace-Id"].startswith("trace-")
    files = list(tmp_path.glob("trace-*.json"))
    assert len(files) == 1
    trace = json.loads(files[0].read_text(encoding="utf-8"))
    serialized = json.dumps(trace)
    assert response.headers["X-Bago-Trace-Id"] == trace["trace_id"]
    assert trace["events"][0]["attributes"]["model_id"] == "kimi-k2.6"
    assert "P1-02 run token" not in serialized
    assert "Finding reviewed." not in serialized


def test_real_agent_tool_loop_traces_allowed_and_denied_exact_file_reads(monkeypatch, tmp_path: Path):
    (tmp_path / "evidence.txt").write_text("Finding P1-02 is reproducible.\nSecond line.\n", encoding="utf-8")
    (tmp_path / "outside.txt").write_text("unapproved secret evidence", encoding="utf-8")

    class Agent:
        id = "agent-auditor"

        class Config:
            system_prompt = "Audit only files returned by the read tool."
            model_id = "kimi-k2.6"
            provider_id = "ollama-cloud"

        config = Config()

    store = ConversationStore(tmp_path / "conversations.sqlite3")
    conversation = store.create("agent", "agent-auditor")
    monkeypatch.setattr(server, "CONVERSATIONS", store)
    monkeypatch.setattr(server, "_load_agent", lambda _agent_id: Agent())
    monkeypatch.setattr(server, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(server, "AGENT_CHAT_TRACE_DIR", tmp_path / "traces")
    monkeypatch.setattr(server, "export_local_trace_to_otlp", lambda *args, **kwargs: None)
    monkeypatch.setenv("BAGO_OTEL_EXPORTER_OTLP_ENDPOINT", "")
    grant = server.WORKSPACE_READ_AUTHORIZATIONS.issue(
        tmp_path, owner_kind="agent", owner_id="agent-auditor", conversation_id=conversation["id"],
        revision=0, paths=["evidence.txt"],
    )
    provider_calls = []
    turns = iter([
        {"tool_calls": [
            {"function": {"name": "read_workspace_file", "arguments": {"path": "evidence.txt", "start_line": 1, "end_line": 1}}},
            {"function": {"name": "read_workspace_file", "arguments": {"path": "outside.txt"}}},
        ]},
        {"content": "The authorized evidence supports the finding; the other path was denied."},
    ])

    def chat_turn(model, messages, **kwargs):
        provider_calls.append((model, messages, kwargs))
        return next(turns)

    monkeypatch.setattr(server.ollama, "chat_turn", chat_turn)
    response = Response()
    result = asyncio.run(server.chat_with_agent("agent-auditor", server.AgentChatRequest(
        message="Inspect evidence and try the unapproved control file.", conversation_id=conversation["id"], revision=0,
        workspace_read_authorization_id=grant["authorization_id"],
    ), response))

    assert result["assistant_message"].startswith("The authorized evidence")
    assert result["sources"][0]["content_sha256"] == hashlib.sha256("1: Finding P1-02 is reproducible.".encode()).hexdigest()
    assert [item["decision"] for item in result["read_events"]] == ["ALLOW", "DENY"]
    assert result["read_events"][1]["reason_code"] == "PATH_NOT_AUTHORIZED"
    second_model_messages = provider_calls[1][1]
    assert any("Finding P1-02 is reproducible." in str(item.get("content")) for item in second_model_messages)
    assert "unapproved secret evidence" not in str(second_model_messages)
    trace = json.loads(next((tmp_path / "traces").glob("trace-*.json")).read_text(encoding="utf-8"))
    assert trace["events"][0]["attributes"]["model_id"] == "kimi-k2.6"
    reads = [event for event in trace["events"] if event["name"] == "workspace.read"]
    assert [event["status"] for event in reads] == ["ALLOW", "DENY"]
    assert all(event["parent_event_id"] == trace["events"][0]["event_id"] for event in reads)
    assert reads[0]["attributes"]["file_sha256"] == hashlib.sha256((tmp_path / "evidence.txt").read_bytes()).hexdigest()
