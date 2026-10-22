from fastapi.testclient import TestClient
import pytest

import src.api.server as server
from src.api.server import app


def test_agent_runner_websocket_remains_closed_before_provider_or_ber(monkeypatch):
    client = TestClient(app)

    def unexpected_runner(*_args, **_kwargs):
        pytest.fail("Malformed input must be rejected before the runner is created.")

    monkeypatch.setattr(server, "AgentRunner", unexpected_runner)
    monkeypatch.setattr(server, "BerClient", unexpected_runner)

    with client.websocket_connect(
        "/ws/agents/run",
        headers={"origin": "http://127.0.0.1:8080"},
    ) as websocket:
        websocket.send_text("{malformed json")
        message = websocket.receive_json()

    assert message["type"] == "error"
    assert message["code"] == "execution_unavailable"
