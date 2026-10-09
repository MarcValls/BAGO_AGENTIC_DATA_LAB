import asyncio
import json
from pathlib import Path

from fastapi import Response

from src.api import server


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
    monkeypatch.setattr(server.ollama, "chat", lambda model, messages: calls.append((model, messages)) or "Finding reviewed.")
    monkeypatch.setattr(server, "AGENT_CHAT_TRACE_DIR", tmp_path)
    monkeypatch.setattr(server, "export_local_trace_to_otlp", lambda *args, **kwargs: None)
    monkeypatch.setenv("BAGO_OTEL_EXPORTER_OTLP_ENDPOINT", "")

    response = Response()
    result = asyncio.run(server.chat_with_agent(
        "agent-demo",
        server.AgentChatRequest(message="P1-02 run token demo-20261009"),
        response,
    ))

    assert calls[0][0] == "kimi-k2.6"
    assert result == {"agent_id": "agent-demo", "assistant_message": "Finding reviewed.", "source": "ollama"}
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
