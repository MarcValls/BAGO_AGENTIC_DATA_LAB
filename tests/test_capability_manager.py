import asyncio
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.capabilities import CapabilityNotFound, CapabilityProposalConflict, CapabilityStore, capability_catalog
from src.capabilities.manager import default_database_path
from src.api import server
from src.conversations import ConversationStore


def test_default_database_is_local_and_workspace_scoped(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    monkeypatch.delenv("BAGO_CAPABILITY_DB_PATH", raising=False)

    first = default_database_path(tmp_path / "workspace-one")
    second = default_database_path(tmp_path / "workspace-two")
    assert first.is_relative_to(tmp_path / "local" / "BAGO" / "AgenticDataLab" / "capabilities")
    assert first != second
    assert first.name == "capabilities.sqlite3"


def test_catalog_reports_connected_and_unavailable_capabilities_truthfully(tmp_path: Path):
    catalog = capability_catalog(tmp_path)
    by_id = {item["id"]: item for item in catalog["capabilities"]}

    assert by_id["workspace.read_text"]["status"] == "AVAILABLE"
    assert by_id["workspace.read_text"]["limits"]["requires_user_opt_in"] is True
    assert by_id["workspace.read_text"]["limits"]["read_only"] is True
    assert by_id["mcp.execute"]["integration"] == "MODULE_PRESENT_NOT_CONNECTED"
    assert by_id["sandbox.execute"]["status"] == "UNAVAILABLE"
    assert by_id["agent.run"]["integration"] == "FAIL_CLOSED"
    assert all("fingerprint" in item and len(item["fingerprint"]) == 64 for item in by_id.values())
    assert "does not grant authorization" in catalog["authority_notice"]


def test_proposals_persist_by_workspace_and_cancellation_is_revision_checked(tmp_path: Path):
    database = tmp_path / "shared-test.sqlite3"
    first = CapabilityStore(tmp_path / "workspace-one", database)
    other_workspace = CapabilityStore(tmp_path / "workspace-two", database)
    proposal = first.create_proposal(
        capability_id="agent.run", summary="Review possible runner enablement", requested_scope="This workspace only",
    )

    assert proposal["status"] == "PENDING_REVIEW"
    assert proposal["effect"] == "EXECUTE"
    assert proposal["revision"] == 0
    assert other_workspace.list_proposals() == []
    assert CapabilityStore(tmp_path / "workspace-one", database).list_proposals()[0] == proposal

    cancelled = first.cancel_proposal(proposal["id"], 0)
    assert cancelled["status"] == "CANCELLED"
    assert cancelled["revision"] == 1
    with pytest.raises(CapabilityProposalConflict):
        first.cancel_proposal(proposal["id"], 0)

    with sqlite3.connect(database) as connection:
        events = connection.execute(
            "SELECT event_type, revision FROM capability_proposal_events WHERE proposal_id = ? ORDER BY sequence",
            (proposal["id"],),
        ).fetchall()
        tables = {
            row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
            if not row[0].startswith("sqlite_")
        }
    assert events == [("PROPOSED", 0), ("CANCELLED", 1)]
    assert tables == {"capability_proposals", "capability_proposal_events"}


def test_unknown_capability_cannot_be_proposed(tmp_path: Path):
    store = CapabilityStore(tmp_path, tmp_path / "caps.sqlite3")
    with pytest.raises(CapabilityNotFound):
        store.create_proposal(capability_id="unknown.tool", summary="Enable it", requested_scope="Everywhere")
    assert store.list_proposals() == []


def test_expired_proposal_becomes_terminal_and_is_recorded(tmp_path: Path):
    database = tmp_path / "expires.sqlite3"
    store = CapabilityStore(tmp_path, database)
    proposal = store.create_proposal(
        capability_id="workspace.read_text", summary="Inspect one file", requested_scope="One bounded read",
    )
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE capability_proposals SET expires_at = '2000-01-01T00:00:00.000Z' WHERE id = ?",
            (proposal["id"],),
        )

    expired = store.list_proposals(status="EXPIRED")
    assert len(expired) == 1
    assert expired[0]["status"] == "EXPIRED"
    assert expired[0]["revision"] == 1
    with sqlite3.connect(database) as connection:
        event = connection.execute(
            "SELECT event_type FROM capability_proposal_events WHERE proposal_id = ? ORDER BY sequence DESC LIMIT 1",
            (proposal["id"],),
        ).fetchone()
    assert event == ("EXPIRED",)


def test_capability_api_lists_and_persists_proposals_without_execution(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(server, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(server, "CAPABILITIES", CapabilityStore(tmp_path, tmp_path / "api.sqlite3"))
    monkeypatch.setattr(server, "CONVERSATIONS", ConversationStore(tmp_path / "conversations.sqlite3"))
    client = TestClient(server.app)
    jobs_before = asyncio.run(server.jobs_list(limit=100))["jobs"]
    conversation = server.CONVERSATIONS.create("assistant", "app-assistant")

    catalog_response = client.get("/api/capabilities")
    assert catalog_response.status_code == 200
    assert {item["id"] for item in catalog_response.json()["capabilities"]} == {
        "workspace.read_text", "mcp.execute", "sandbox.execute", "agent.run",
    }

    created = client.post("/api/capabilities/proposals", json={
        "capability_id": "agent.run",
        "summary": "Evaluate a future governed runner",
        "requested_scope": "Read-only validation for this workspace",
        "conversation_id": conversation["id"],
    })
    assert created.status_code == 200
    body = created.json()
    assert body["proposal"]["status"] == "PENDING_REVIEW"
    assert body["proposal"]["conversation_id"] == conversation["id"]
    assert body["authority_notice"].startswith("Proposal saved for review only")

    listed = client.get("/api/capabilities/proposals?status=PENDING_REVIEW")
    assert listed.status_code == 200
    assert listed.json()["proposals"] == [body["proposal"]]

    cancelled = client.post(
        f"/api/capabilities/proposals/{body['proposal']['id']}/cancel", json={"revision": 0},
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["proposal"]["status"] == "CANCELLED"
    assert "no permission, job, or execution" in cancelled.json()["authority_notice"]
    assert asyncio.run(server.jobs_list(limit=100))["jobs"] == jobs_before


@pytest.mark.parametrize("payload", [
    {"capability_id": "unknown.tool", "summary": "x", "requested_scope": "y"},
    {"capability_id": "agent.run", "summary": "x", "requested_scope": "y", "authorization": True},
    {"capability_id": "agent.run", "summary": "\u0000bad", "requested_scope": "y"},
    {"capability_id": "agent.run", "summary": "api_key=do-not-save", "requested_scope": "y"},
])
def test_api_rejects_unknown_or_overpowered_proposal_input(monkeypatch, tmp_path: Path, payload):
    monkeypatch.setattr(server, "CAPABILITIES", CapabilityStore(tmp_path, tmp_path / "invalid.sqlite3"))
    response = TestClient(server.app).post("/api/capabilities/proposals", json=payload)
    assert response.status_code in {404, 422}
    assert server.CAPABILITIES.list_proposals() == []


def test_arbitrary_model_tool_output_cannot_create_a_capability_proposal(monkeypatch, tmp_path: Path):
    store = CapabilityStore(tmp_path, tmp_path / "model-output.sqlite3")
    monkeypatch.setattr(server, "CAPABILITIES", store)
    responses = iter([
        {"tool_calls": [{"function": {
            "name": "capability.create_proposal",
            "arguments": {"capability_id": "agent.run", "summary": "Enable", "requested_scope": "all"},
        }}]},
        {"content": "I cannot create that proposal from model output."},
    ])
    monkeypatch.setattr(server.ollama, "chat_turn", lambda *args, **kwargs: next(responses))

    answer, sources = asyncio.run(server._chat_with_workspace_read(
        "gemma4:31b", [{"role": "user", "content": "Enable agent execution"}],
    ))

    assert answer == "I cannot create that proposal from model output."
    assert sources == []
    assert store.list_proposals() == []
