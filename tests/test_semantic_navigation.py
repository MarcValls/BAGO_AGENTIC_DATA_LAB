import asyncio

from src.api import server
from src.conversations import ConversationStore
from src.providers import ollama


def test_control_request_parser_requires_registered_view_for_navigation():
    assert server._control_request_from_arguments({
        "decision": "navigate", "view": "traces", "reply": ""
    }) == {"decision": "navigate", "view": "traces"}
    assert server._control_request_from_arguments({
        "decision": "navigate", "view": "agent_history", "reply": ""
    }) == {"decision": "clarify", "reply": "No pude identificar una vista registrada. Dime qué quieres encontrar."}
    assert server._control_request_from_arguments({
        "decision": "navigate", "reply": ""
    }) == {"decision": "clarify", "reply": "No pude identificar una vista registrada. Dime qué quieres encontrar."}
    assert server._control_request_from_arguments({
        "decision": "open", "view": "provider_settings", "reply": ""
    }) == {"decision": "navigate", "view": "provider_settings"}


def test_control_request_answer_stays_in_chat_even_with_view_argument():
    assert server._control_request_from_arguments({
        "decision": "answer", "view": "evaluation", "reply": "La vista muestra los checks de una ejecución."
    }) == {"decision": "answer", "reply": "La vista muestra los checks de una ejecución."}


def test_control_request_rejects_unknown_function_shaped_text():
    assert server._control_request_from_turn({
        "content": '{"name":"agent_history","parameters":{"view":"agent_history"}}'
    }) == {"decision": "clarify", "reply": "No pude resolver la solicitud. Cuéntame qué necesitas encontrar."}


def test_control_request_accepts_only_registered_function_shaped_text():
    assert server._control_request_from_turn({
        "content": '{"name":"traces","parameters":{"view":"traces"}}'
    }) == {"decision": "navigate", "view": "traces"}
    assert server._control_request_from_turn({
        "content": '{"name":"agent_history","parameters":{"view":"agent_history"}}'
    }) == {"decision": "clarify", "reply": "No pude resolver la solicitud. Cuéntame qué necesitas encontrar."}


def test_control_chat_does_not_navigate_for_explanation_decision(monkeypatch, tmp_path):
    store = ConversationStore(tmp_path / "conversations.sqlite3")
    conversation = store.create("assistant", "app-assistant")
    monkeypatch.setattr(server, "CONVERSATIONS", store)
    monkeypatch.setattr(server, "_selected_model_id", lambda: "test-local-model")
    monkeypatch.setattr(server, "_record_chat_cognition_trace", lambda **_kwargs: {"trace_id": "trace-test"})
    captured = {}
    def fake_chat_turn(*_args, **kwargs):
        captured.update(kwargs)
        return {
        "tool_calls": [{"function": {"name": "resolve_control_request", "arguments": {
            "decision": "answer", "view": "evaluation", "reply": "La vista muestra los checks de una ejecución."
        }}}]
        }
    monkeypatch.setattr(server.ollama, "chat_turn", fake_chat_turn)

    result = asyncio.run(server.control_chat(server.ControlChatRequest(
        operation="chat", message="¿Qué hace la vista de evaluación?",
        conversation_id=conversation["id"], revision=0,
    )))

    assert result["operation"] == "chat"
    assert "navigation" not in result
    assert result["assistant_message"] == "La vista muestra los checks de una ejecución."
    assert captured["options"] == {"temperature": 0}


def test_control_chat_navigates_only_after_validated_navigation_decision(monkeypatch, tmp_path):
    store = ConversationStore(tmp_path / "conversations.sqlite3")
    conversation = store.create("assistant", "app-assistant")
    monkeypatch.setattr(server, "CONVERSATIONS", store)
    monkeypatch.setattr(server, "_selected_model_id", lambda: "test-local-model")
    monkeypatch.setattr(server.ollama, "chat_turn", lambda *_args, **_kwargs: {
        "tool_calls": [{"function": {"name": "resolve_control_request", "arguments": {
            "decision": "navigate", "view": "cognition_settings", "reply": ""
        }}}]
    })

    result = asyncio.run(server.control_chat(server.ControlChatRequest(
        operation="chat", message="Llévame a los ajustes de razonamiento.",
        conversation_id=conversation["id"], revision=0,
    )))

    assert result["operation"] == "navigate"
    assert result["navigation"] == {"view": "cognition_settings"}


def test_ollama_chat_turn_forwards_routing_options(monkeypatch):
    captured = {}

    def fake_request(method, path, *, payload=None, timeout=20):
        captured.update({"method": method, "path": path, "payload": payload})
        return {"message": {"content": "ok"}}

    monkeypatch.setattr(ollama, "_request", fake_request)
    ollama.chat_turn("local-model", [{"role": "user", "content": "hello"}], options={"temperature": 0})

    assert captured["payload"]["options"] == {"temperature": 0}


def test_workspace_read_tool_loop_does_not_offer_navigation_by_default(monkeypatch):
    captured = {}

    def fake_chat_turn(_model, _messages, *, tools, options=None):
        captured["tools"] = tools
        captured["options"] = options
        return {"content": "Answer"}

    monkeypatch.setattr(server.ollama, "chat_turn", fake_chat_turn)
    result = asyncio.run(server._chat_with_workspace_read(
        "test-model", [{"role": "user", "content": "Read the authorized file."}], [],
    ))

    assert result == ("Answer", [], [], None)
    assert all(tool["function"]["name"] != "resolve_control_request" for tool in captured["tools"])
    assert captured["options"] is None

