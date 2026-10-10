from fastapi.testclient import TestClient

from src.api.server import app


def test_agent_runner_websocket_fails_closed_without_starting_a_job():
    client = TestClient(app)

    with client.websocket_connect(
        "/ws/agents/run",
        headers={"origin": "http://127.0.0.1:8080"},
    ) as websocket:
        message = websocket.receive_json()

    assert message["type"] == "error"
    assert message["code"] == "execution_unavailable"
    assert "No job was started or recorded" in message["data"]
