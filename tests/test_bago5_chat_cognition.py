import asyncio
import json
import math
from pathlib import Path
import pytest

from fastapi import Response

from src.api import server
from src.cognition.bago5_chat import Edge, PROFILE, Relation, UnitKind, build_chat_cognition
from src.conversations import ConversationStore


def test_focus_is_deterministic_bounded_and_changes_with_request():
    compare = build_chat_cognition("Compara opciones y recomienda una con evidencia")
    brief_code = build_chat_cognition("Resume brevemente este código")

    assert compare == build_chat_cognition("Compara opciones y recomienda una con evidencia")
    assert compare["profile"] == PROFILE
    assert compare["capacity"] == 6
    assert len(compare["focus"]) <= compare["capacity"]
    assert {item["id"] for item in compare["focus"]} != {item["id"] for item in brief_code["focus"]}
    assert "Compare the relevant criteria" in compare["prompt_guidance"]
    assert "Prefer a concise response" in brief_code["prompt_guidance"]
    assert "hidden chain-of-thought" in compare["prompt_guidance"]


def test_focus_metadata_does_not_retain_the_user_message():
    marker = "private-marker-qzx-9182"
    plan = build_chat_cognition(f"Analyze this request containing {marker}")

    assert marker not in json.dumps(plan)
    assert all(set(item) == {"id", "kind", "label", "score", "hops", "source"} for item in plan["focus"])


def test_cognitive_graph_uses_typed_units_and_bounded_relations():
    edge = Edge("need", "goal", Relation.TRIGGERS, 0.75)

    assert UnitKind.NEED.value == "need"
    assert edge.relation is Relation.TRIGGERS
    with pytest.raises(ValueError, match="typed relation"):
        Edge("need", "goal", "TRIGGERS", 0.75)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="bounded"):
        Edge("need", "goal", Relation.TRIGGERS, math.inf)


def test_app_chat_applies_and_persists_bago5_context_and_focus_trace(monkeypatch, tmp_path: Path):
    store = ConversationStore(tmp_path / "conversations.sqlite3")
    conversation = store.create("assistant", "app-assistant")
    monkeypatch.setattr(server, "CONVERSATIONS", store)
    monkeypatch.setattr(server, "AGENT_CHAT_TRACE_DIR", tmp_path / "traces")
    monkeypatch.setattr(server, "_selected_model_id", lambda: "test-model")
    calls = []
    monkeypatch.setattr(server.ollama, "chat", lambda model, messages: calls.append((model, messages)) or "Comparison answer")

    result = asyncio.run(server.control_chat(server.ControlChatRequest(
        operation="chat", message="Compare these options with evidence", conversation_id=conversation["id"],
        revision=0, cognitive_mode="bago5",
    )))

    system_prompt = calls[0][1][0]["content"]
    assert "BAGO5 experimental cognitive context" in system_prompt
    assert "Compare the relevant criteria" in system_prompt
    context = result["cognitive_trace"]
    assert context["enabled"] is True
    assert context["mode"] == "bago5"
    assert result["conversation"]["messages"][1]["references"]["cognitive_trace"] == context
    trace_path = tmp_path / "traces" / "cognition" / f"{context['trace_id']}.json"
    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    serialized = json.dumps(trace)
    assert trace["events"][0]["name"] == "chat.cognitive_context"
    assert trace["events"][0]["attributes"]["focus"] == context["focus"]
    assert "Compare these options with evidence" not in serialized
    assert "Comparison answer" not in serialized


def test_agent_chat_baseline_is_recorded_without_cognitive_prompt(monkeypatch, tmp_path: Path):
    class Agent:
        id = "agent-baseline"

        class Config:
            system_prompt = "Answer only the user."
            model_id = "test-model"
            provider_id = "ollama-cloud"

        config = Config()

    store = ConversationStore(tmp_path / "conversations.sqlite3")
    conversation = store.create("agent", "agent-baseline")
    monkeypatch.setattr(server, "CONVERSATIONS", store)
    monkeypatch.setattr(server, "AGENT_CHAT_TRACE_DIR", tmp_path / "traces")
    monkeypatch.setattr(server, "_load_agent", lambda _agent_id: Agent())
    monkeypatch.setattr(server, "export_local_trace_to_otlp", lambda *args, **kwargs: None)
    monkeypatch.setenv("BAGO_OTEL_EXPORTER_OTLP_ENDPOINT", "")
    calls = []
    monkeypatch.setattr(server.ollama, "chat", lambda model, messages: calls.append((model, messages)) or "Baseline answer")

    result = asyncio.run(server.chat_with_agent(
        "agent-baseline",
        server.AgentChatRequest(message="Compare options with evidence", conversation_id=conversation["id"], revision=0),
        Response(),
    ))

    assert "BAGO5 experimental cognitive context" not in calls[0][1][0]["content"]
    assert result["cognitive_trace"]["mode"] == "baseline"
    assert result["cognitive_trace"]["enabled"] is False
    saved = result["conversation"]["messages"][1]["references"]["cognitive_trace"]
    assert saved["focus"] == []


def test_selected_agent_receives_bago5_prompt_guidance(monkeypatch, tmp_path: Path):
    class Agent:
        id = "agent-cognitive"

        class Config:
            system_prompt = "Review only user-supplied evidence."
            model_id = "test-model"
            provider_id = "ollama-cloud"

        config = Config()

    store = ConversationStore(tmp_path / "conversations.sqlite3")
    conversation = store.create("agent", "agent-cognitive")
    monkeypatch.setattr(server, "CONVERSATIONS", store)
    monkeypatch.setattr(server, "AGENT_CHAT_TRACE_DIR", tmp_path / "traces")
    monkeypatch.setattr(server, "_load_agent", lambda _agent_id: Agent())
    monkeypatch.setattr(server, "export_local_trace_to_otlp", lambda *args, **kwargs: None)
    monkeypatch.setenv("BAGO_OTEL_EXPORTER_OTLP_ENDPOINT", "")
    calls = []
    monkeypatch.setattr(server.ollama, "chat", lambda model, messages: calls.append(messages) or "Evidence reviewed.")

    result = asyncio.run(server.chat_with_agent(
        "agent-cognitive",
        server.AgentChatRequest(message="Analyze this with evidence", conversation_id=conversation["id"], revision=0,
                                cognitive_mode="bago5"),
        Response(),
    ))

    assert "BAGO5 experimental cognitive context" in calls[0][0]["content"]
    assert "Separate evidence from inference" in calls[0][0]["content"]
    assert result["cognitive_trace"]["enabled"] is True
    assert result["conversation"]["messages"][1]["references"]["cognitive_trace"]["profile"] == PROFILE
