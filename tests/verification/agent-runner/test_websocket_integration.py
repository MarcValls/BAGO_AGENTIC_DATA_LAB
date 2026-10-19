from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from fastapi.testclient import TestClient

import src.api.server as server


class FakeBerClient:
    def __init__(self, *, workspace: Path) -> None:
        self.workspace = workspace
        self.calls: list[tuple[str, Any]] = []
        self.closed = False

    def start(self) -> dict[str, Any]:
        self.calls.append(("start", None))
        return {"healthy": True}

    def prepare(self, operation: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(("prepare", operation))
        return {
            "challenge_id": "server-only-challenge",
            "request_id": "request-fixture-1",
            "effect_id": operation["effect_id"],
            "approval_required": True,
            "world_state_digest": "world-fixture-1",
            "expires_at": "2030-01-01T00:00:00Z",
        }

    def approve(self, challenge_id: str, *, channel: str) -> dict[str, Any]:
        self.calls.append(("approve", (challenge_id, channel)))
        return {"request_id": "request-fixture-1", "state": "approved", "decision_id": "decision-fixture-1", "proof_id": "proof-fixture-1", "permit_token": "private-token"}

    def execute(self, challenge_id: str) -> dict[str, Any]:
        self.calls.append(("execute", challenge_id))
        return {
            "request_id": "request-fixture-1",
            "effect_id": "filesystem.write",
            "ber_execution_id": "execution-fixture-1",
            "receipt_id": "receipt-fixture-1",
            "authorization": {"state": "consumed", "permit_id": "permit-fixture-1", "permit_token": "private-token"},
            "result": {"receipt_id": "receipt-fixture-1", "effect_id": "filesystem.write", "executed": True, "ok": True},
        }

    def close(self) -> None:
        self.closed = True
        self.calls.append(("close", None))


def _workspace(root: Path) -> Path:
    root.mkdir()
    subprocess.run(["git", "init", str(root)], check=True, capture_output=True, text=True)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "ADL verifier"], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.email", "adl-verifier@example.invalid"], check=True)
    (root / "tracked.txt").write_text("fixture", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "tracked.txt"], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-m", "fixture"], check=True, capture_output=True, text=True)
    return root


def test_websocket_uses_persisted_profile_server_challenge_and_exact_receipt(monkeypatch, tmp_path: Path) -> None:
    workspace = _workspace(tmp_path / "workspace")
    agent_id = "agent_fixture_0123456789"
    profile = SimpleNamespace(config=SimpleNamespace(
        provider_id="ollama-cloud", model_id="fixture-model", system_prompt="saved system prompt", tools=["sandbox.run"]
    ))
    ber_clients: list[FakeBerClient] = []

    monkeypatch.setattr(server, "_load_agent", lambda requested: profile if requested == agent_id else None)
    monkeypatch.setattr(server, "current_workspace_root", lambda: workspace)
    monkeypatch.setattr(server.ollama, "status", lambda: {"state": "ready", "provider_id": "ollama-cloud", "model_id": "fixture-model"})
    monkeypatch.setattr(server.ollama, "chat_turn", lambda *_args, **_kwargs: {
        "content": "",
        "tool_calls": [{"function": {"name": "sandbox.run", "arguments": {
            "effect_id": "filesystem.write", "target": {"path": "reports/fixture.txt"},
            "arguments": {"content": "fixture only", "expected_exists": False},
        }}}],
    })

    def make_ber(**kwargs: Any) -> FakeBerClient:
        client = FakeBerClient(**kwargs)
        ber_clients.append(client)
        return client

    monkeypatch.setattr(server, "BerClient", make_ber)

    with TestClient(server.app) as client:
        with client.websocket_connect("/ws/agents/run", headers={"origin": "http://127.0.0.1:8080"}) as websocket:
            websocket.send_json({"type": "start", "agent_id": agent_id, "task": "Review the fixture."})
            proposal = websocket.receive_json()
            assert proposal["type"] == "proposal"
            assert proposal["effect_status"] == "proposed"
            assert proposal["effect_id"] == "filesystem.write"
            assert proposal["request_id"] == "request-fixture-1"
            assert "challenge_id" not in proposal
            assert "permit_token" not in str(proposal)

            websocket.send_json({"type": "decision", "proposal_id": proposal["proposal_id"], "decision": "approve"})
            outcome = websocket.receive_json()
            assert outcome["type"] == "completed"
            assert outcome["execution"]["verified_success"] is True
            assert outcome["request_id"] == proposal["request_id"]
            assert outcome["execution"]["receipt_id"] == "receipt-fixture-1"
            assert outcome["trace"]["run_id"] == "execution-fixture-1"
            assert "challenge_id" not in str(outcome)
            assert "permit_token" not in str(outcome)

    assert len(ber_clients) == 1
    calls = ber_clients[0].calls
    assert ("approve", ("server-only-challenge", "ui-react")) in calls
    assert ("execute", "server-only-challenge") in calls
    assert calls.index(("approve", ("server-only-challenge", "ui-react"))) < calls.index(("execute", "server-only-challenge"))
    assert ber_clients[0].closed is True


def test_websocket_disconnect_before_decision_closes_ber_without_effect(monkeypatch, tmp_path: Path) -> None:
    workspace = _workspace(tmp_path / "disconnect-workspace")
    agent_id = "agent_fixture_0123456789"
    profile = SimpleNamespace(config=SimpleNamespace(
        provider_id="ollama-cloud", model_id="fixture-model", system_prompt="saved system prompt", tools=["sandbox.run"]
    ))
    ber_clients: list[FakeBerClient] = []
    monkeypatch.setattr(server, "_load_agent", lambda _requested: profile)
    monkeypatch.setattr(server, "current_workspace_root", lambda: workspace)
    monkeypatch.setattr(server.ollama, "status", lambda: {"state": "ready", "provider_id": "ollama-cloud", "model_id": "fixture-model"})
    monkeypatch.setattr(server.ollama, "chat_turn", lambda *_args, **_kwargs: {
        "content": "",
        "tool_calls": [{"function": {"name": "sandbox.run", "arguments": {
            "effect_id": "filesystem.write", "target": {"path": "reports/fixture.txt"},
            "arguments": {"content": "fixture only", "expected_exists": False},
        }}}],
    })

    def make_ber(**kwargs: Any) -> FakeBerClient:
        client = FakeBerClient(**kwargs)
        ber_clients.append(client)
        return client

    monkeypatch.setattr(server, "BerClient", make_ber)
    with TestClient(server.app) as client:
        with client.websocket_connect("/ws/agents/run", headers={"origin": "http://127.0.0.1:8080"}) as websocket:
            websocket.send_json({"type": "start", "agent_id": agent_id, "task": "Review the fixture."})
            proposal = websocket.receive_json()
            assert proposal["type"] == "proposal"
            websocket.close(code=1000)

    assert len(ber_clients) == 1
    assert ber_clients[0].closed is True
    assert not any(name in {"approve", "execute"} for name, _ in ber_clients[0].calls)


def test_websocket_rejects_client_authored_profile_or_workspace_fields(monkeypatch) -> None:
    client = TestClient(server.app)
    with client.websocket_connect("/ws/agents/run", headers={"origin": "http://127.0.0.1:8080"}) as websocket:
        websocket.send_json({
            "type": "start", "agent_id": "agent_fixture_0123456789", "task": "Do not execute.",
            "provider_id": "attacker-provider", "model_id": "attacker-model", "workspace": "C:/outside",
        })
        result = websocket.receive_json()
    assert result["type"] == "error"
    assert result["code"] == "invalid_message"


def test_actual_git_head_drift_invalidates_the_bound_proposal(tmp_path: Path) -> None:
    from src.runtime.ber.agent_runner import AgentRunner, AgentRunnerError

    workspace = _workspace(tmp_path / "drift-workspace")
    profile = SimpleNamespace(config=SimpleNamespace(
        provider_id="ollama-cloud", model_id="fixture-model", system_prompt="", tools=["sandbox.run"]
    ))
    ber = FakeBerClient(workspace=workspace)
    runner = AgentRunner(
        load_agent=lambda _agent_id: profile,
        workspace_root=lambda: workspace,
        provider_status=lambda: {"state": "ready", "model_id": "fixture-model"},
        provider_chat_turn=lambda *_args, **_kwargs: {"content": "", "tool_calls": [{"function": {"name": "sandbox.run", "arguments": {
            "effect_id": "filesystem.write", "target": {"path": "output.txt"},
            "arguments": {"content": "fixture only", "expected_exists": False},
        }}}]},
        ber_client_factory=lambda **_kwargs: ber,
    )
    proposal = runner.start(agent_id="agent_fixture", task="Prepare the test proposal.")

    (workspace / "head-drift.txt").write_text("synthetic drift", encoding="utf-8")
    subprocess.run(["git", "-C", str(workspace), "add", "head-drift.txt"], check=True)
    subprocess.run(["git", "-C", str(workspace), "commit", "-m", "synthetic drift"], check=True, capture_output=True, text=True)

    try:
        runner.decide(proposal_id=proposal["proposal_id"], decision="approve")
    except AgentRunnerError as error:
        assert error.code == "workspace_stale"
    else:
        raise AssertionError("stale workspace proposal was not rejected")
    assert not any(name in {"approve", "execute"} for name, _ in ber.calls)
    assert ber.closed is True


def test_container_provider_status_is_unsupported_without_auth_or_network(monkeypatch, tmp_path: Path) -> None:
    from src.providers import ollama

    monkeypatch.setenv("BAGO_RUNTIME_MODE", "container")
    monkeypatch.setattr(ollama, "CONFIG_PATH", tmp_path / "no-provider-config.json")
    status = ollama.status()
    assert status["state"] == "unsupported_runtime"
    assert status["runtime_mode"] == "container"
    assert status["model_id"] is None
