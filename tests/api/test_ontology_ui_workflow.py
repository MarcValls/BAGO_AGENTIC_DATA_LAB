"""Adversarial API tests for proposal-only ontology approval and local query."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from fastapi.testclient import TestClient

from src.api import server
from src.metadata import ontology_runtime


CONTENT = """# BAGO Authorization Contract

Contract IMPLEMENTS Component.
Permit AUTHORIZES Execution.
Execution GENERATES Evidence.
Provider SERVES Model.
"""


def _setup(tmp_path: Path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "relations.md").write_text(CONTENT, encoding="utf-8")
    db, traces = tmp_path / "ontology.sqlite3", tmp_path / "traces"
    monkeypatch.setattr(server, "current_workspace_root", lambda: workspace)
    monkeypatch.setattr(ontology_runtime, "_db_path", lambda: db)
    monkeypatch.setattr(ontology_runtime, "_trace_dir", lambda: traces)
    return workspace, db, traces, TestClient(server.app)


def _propose(client):
    response = client.post("/api/ontology/proposals", json={"path": "relations.md"})
    assert response.status_code == 200, response.text
    return response.json()


def test_proposal_is_not_accepted_until_exact_selected_id_and_query_has_provenance(tmp_path, monkeypatch):
    workspace, db, traces, client = _setup(tmp_path, monkeypatch)
    proposal = _propose(client)
    assert proposal["source"]["sha256"] == hashlib.sha256((workspace / "relations.md").read_bytes()).hexdigest()
    assert len(proposal["relations"]) == 4
    assert all(item["validator"]["status"] == "PASS" for item in proposal["relations"])
    assert all(item["evidence"]["line_number"] for item in proposal["relations"])
    with __import__("sqlite3").connect(db) as conn:
        assert conn.execute("select count(*) from ontology_accepted").fetchone()[0] == 0
    selected = next(item for item in proposal["relations"] if item["type"] == "IMPLEMENTS")
    approved = client.post(f"/api/ontology/proposals/{proposal['proposal_id']}/approve", json={"proposal_ids": [selected["proposal_id"]]})
    assert approved.status_code == 200, approved.text
    assert approved.json()["accepted_ids"] == [selected["proposal_id"]]
    result = client.post("/api/ontology/query", json={"query": "Contract implements Component"})
    assert result.status_code == 200, result.text
    payload = result.json()
    assert payload["graph_fingerprint"] == approved.json()["graph_fingerprint"]
    assert payload["evidence_refs"]
    evidence = payload["evidence_refs"][0]
    assert evidence["source_sha256"] == proposal["source"]["sha256"]
    assert evidence["trace_ref"] != evidence["receipt_id"]
    approval_trace_path = traces / f"{evidence['trace_ref']}.json"
    assert approval_trace_path.is_file()
    approval_trace = json.loads(approval_trace_path.read_text(encoding="utf-8"))
    assert approval_trace["trace_id"] == evidence["trace_ref"]
    assert approval_trace["receipt_id"] == evidence["receipt_id"]
    with __import__("sqlite3").connect(db) as conn:
        receipt_row = conn.execute("select kind,payload from ontology_receipts where receipt_id=?", (evidence["receipt_id"],)).fetchone()
        assert receipt_row[0] == "approval"
        receipt = json.loads(receipt_row[1])
    assert receipt["receipt_id"] == evidence["receipt_id"]
    assert receipt["trace_id"] == evidence["trace_ref"]
    assert Path(payload["trace"]["path"]).is_file()
    trace_bytes = Path(payload["trace"]["path"]).read_bytes()
    assert hashlib.sha256(trace_bytes).hexdigest() == payload["trace"]["sha256"]
    assert json.loads(trace_bytes)["receipt_id"] == payload["receipt"]["receipt_id"]
    assert proposal["trace"]["sha256"] == hashlib.sha256(Path(proposal["trace"]["path"]).read_bytes()).hexdigest()


def test_unselected_proposals_do_not_persist_and_unknown_duplicate_or_empty_fail_closed(tmp_path, monkeypatch):
    _, db, _, client = _setup(tmp_path, monkeypatch)
    proposal = _propose(client)
    selected = proposal["relations"][0]["proposal_id"]
    for ids in ([], [selected, selected], ["proposal_unknown"]):
        response = client.post(f"/api/ontology/proposals/{proposal['proposal_id']}/approve", json={"proposal_ids": ids})
        assert response.status_code == 422
    with __import__("sqlite3").connect(db) as conn:
        accepted = {row[0] for row in conn.execute("select proposal_id from ontology_accepted")}
    assert accepted == set()


def test_stale_source_and_unsafe_paths_are_rejected(tmp_path, monkeypatch):
    workspace, _, _, client = _setup(tmp_path, monkeypatch)
    proposal = _propose(client)
    (workspace / "relations.md").write_text(CONTENT + "\nChanged.", encoding="utf-8")
    response = client.post(f"/api/ontology/proposals/{proposal['proposal_id']}/approve", json={"proposal_ids": [proposal["relations"][0]["proposal_id"]]})
    assert response.status_code == 422 and "stale" in response.json()["detail"]
    for path in ("../outside.md", ".bago/secret.md", "relations.pdf"):
        rejected = client.post("/api/ontology/proposals", json={"path": path})
        assert rejected.status_code == 422


def test_validator_failed_proposal_cannot_be_approved(tmp_path, monkeypatch):
    _, db, _, client = _setup(tmp_path, monkeypatch)
    proposal = _propose(client)
    target = proposal["relations"][0]["proposal_id"]
    with __import__("sqlite3").connect(db) as conn:
        stored = json.loads(conn.execute("select payload from ontology_proposals where proposal_id=?", (proposal["proposal_id"],)).fetchone()[0])
        next(item for item in stored["relations"] if item["proposal_id"] == target)["validator"] = {"status": "FAIL", "reason": "test rejection"}
        conn.execute("update ontology_proposals set payload=? where proposal_id=?", (json.dumps(stored, sort_keys=True), proposal["proposal_id"]))
    response = client.post(f"/api/ontology/proposals/{proposal['proposal_id']}/approve", json={"proposal_ids": [target]})
    assert response.status_code == 422
    with __import__("sqlite3").connect(db) as conn:
        assert conn.execute("select count(*) from ontology_accepted").fetchone()[0] == 0


def test_sqlite_failure_does_not_return_success(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    monkeypatch.setattr(ontology_runtime, "_connect", lambda: (_ for _ in ()).throw(__import__("sqlite3").OperationalError("disk full")))
    response = TestClient(server.app).post("/api/ontology/proposals", json={"path": "relations.md"})
    assert response.status_code == 422
    assert "persistence failed" in response.json()["detail"]
