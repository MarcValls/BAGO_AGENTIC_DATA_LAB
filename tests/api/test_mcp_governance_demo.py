"""API-level checks for the fixed, repository-local MCP governance demo."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from fastapi.testclient import TestClient

from src.api import server


def test_fixed_fixture_runs_read_and_denies_write_before_transport(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(server, "_MCP_GOVERNANCE_EVIDENCE_DIR", tmp_path)
    response = TestClient(server.app).post("/api/demo/mcp-governance")

    assert response.status_code == 200, response.text
    result = response.json()
    assert result["status"] == "completed"
    assert result["transport"] == "stdio"
    assert result["source_kind"] == "repository_local_fixture"
    assert {tool["name"] for tool in result["discovered"]} == {
        "get_lab_status",
        "propose_lab_note",
    }
    assert result["registered"] == [
        {"name": "get_lab_status", "effect_type": "READ"},
        {"name": "propose_lab_note", "effect_type": "WRITE"},
    ]
    assert result["read_call"]["decision"] == "ALLOW"
    assert result["read_call"]["actual_effect"]["called"] is True
    assert result["read_call"]["transport_call_count"] == 1
    assert result["read_call"]["request_id"]
    assert result["read_call"]["permit_id"]
    assert result["read_call"]["execution_outcome"] == "SUCCESS"
    assert result["write_call"]["decision"] == "REQUIRE_HUMAN"
    assert result["write_call"]["actual_effect"]["called"] is False
    assert result["write_call"]["transport_call_count"] == 0
    assert result["write_call"]["request_id"]
    assert result["write_call"]["permit_id"]
    assert result["trace"]["trace_id"]
    assert any(event["kind"] == "mcp_discovery" for event in result["trace"]["events"])

    evidence_path = tmp_path / f"{result['run_id']}.json"
    evidence_bytes = evidence_path.read_bytes()
    persisted = json.loads(evidence_bytes)
    assert result["evidence"]["path"] == f".bago/data/traces/mcp-governance/{result['run_id']}.json"
    assert result["evidence"]["sha256"] == hashlib.sha256(evidence_bytes).hexdigest()
    assert persisted["read_call"]["receipt_id"] == result["read_call"]["receipt_id"]
    assert persisted["write_call"]["receipt_id"] == result["write_call"]["receipt_id"]


def test_endpoint_rejects_arbitrary_request_fields(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(server, "_MCP_GOVERNANCE_EVIDENCE_DIR", tmp_path)
    response = TestClient(server.app).post(
        "/api/demo/mcp-governance", json={"server_url": "https://example.invalid"}
    )

    assert response.status_code == 422
    assert not list(tmp_path.glob("*.json"))


def test_endpoint_rejects_non_object_body(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(server, "_MCP_GOVERNANCE_EVIDENCE_DIR", tmp_path)
    response = TestClient(server.app).post("/api/demo/mcp-governance", json=[])

    assert response.status_code == 422
    assert not list(tmp_path.glob("*.json"))


def test_evidence_persistence_failure_never_reports_completion(tmp_path: Path, monkeypatch) -> None:
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("block", encoding="utf-8")
    monkeypatch.setattr(server, "_MCP_GOVERNANCE_EVIDENCE_DIR", blocker)

    response = TestClient(server.app).post("/api/demo/mcp-governance")

    assert response.status_code == 500
    assert "evidence persistence failed" in response.json()["detail"]


def test_repeated_runs_create_unique_evidence(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(server, "_MCP_GOVERNANCE_EVIDENCE_DIR", tmp_path)
    client = TestClient(server.app)

    first = client.post("/api/demo/mcp-governance")
    second = client.post("/api/demo/mcp-governance")

    assert first.status_code == second.status_code == 200
    first_result, second_result = first.json(), second.json()
    assert first_result["run_id"] != second_result["run_id"]
    assert first_result["evidence"]["path"] != second_result["evidence"]["path"]
    assert len(list(tmp_path.glob("*.json"))) == 2
