"""API contract tests for the fixed local source-to-grounded-answer route."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from src.api import server
from src.knowledge import local_rag
from src.retrieval.sqlite_vector_store import SQLiteVectorStore


def _setup(tmp_path: Path, monkeypatch, content: str = "# Local policy\n\nThe local retention period is 30 days. Keep a review receipt."):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "policy.md").write_text(content, encoding="utf-8")
    db, traces = tmp_path / "knowledge.sqlite3", tmp_path / "traces"
    monkeypatch.setattr(server, "current_workspace_root", lambda: workspace)
    monkeypatch.setattr(local_rag, "_database_path", lambda: db)
    monkeypatch.setattr(local_rag, "_trace_dir", lambda: traces)
    calls: list[tuple[str, str, list[dict[str, str]]]] = []
    monkeypatch.setattr(server.provider_runtime, "active_selection", lambda: {"provider_id": "fixture", "model_id": "fixture-model"})
    def generate(provider, model, messages):
        calls.append((provider, model, messages))
        return "El periodo es 30 días [policy.md#revision=" + hashlib.sha256((workspace / "policy.md").read_bytes()).hexdigest() + "]."
    monkeypatch.setattr(server.provider_runtime, "chat", generate)
    return workspace, db, traces, calls


def _request(**overrides):
    body = {"path": "policy.md", "question": "¿Cuál es el periodo de retención?", "source_authority": "VERIFIED", "minimum_authority": "VERIFIED"}
    return {**body, **overrides}


def test_ingest_answer_returns_persisted_source_citations_and_trace(tmp_path, monkeypatch):
    _, db, traces, calls = _setup(tmp_path, monkeypatch)
    response = TestClient(server.app).post("/api/knowledge/ingest-and-answer", json=_request())
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["status"] == "answered"
    assert len(calls) == 1
    assert result["ingestion"]["source_sha256"] == result["ingestion"]["source_revision"]
    assert result["retrieval"]["hits"]
    hit = result["retrieval"]["hits"][0]
    assert hit["evidence"]["source_uri"] == "policy.md"
    assert hit["evidence"]["revision"] == result["ingestion"]["source_sha256"]
    assert result["generation"]["provider_id"] == "fixture"
    assert result["trace"]["sha256"] == hashlib.sha256((traces / f"{result['run_id']}.json").read_bytes()).hexdigest()
    assert json.loads((traces / f"{result['run_id']}.json").read_text())["run_id"] == result["run_id"]
    first_fingerprint = result["ingestion"]["index_fingerprint"]
    reopened = SQLiteVectorStore(db)
    assert reopened.index_fingerprint == first_fingerprint
    duplicate = TestClient(server.app).post("/api/knowledge/ingest-and-answer", json=_request())
    assert duplicate.json()["ingestion"]["idempotent"] is True
    assert duplicate.json()["ingestion"]["source_id"] == result["ingestion"]["source_id"]
    assert duplicate.json()["ingestion"]["index_fingerprint"] == first_fingerprint


def test_authority_filter_runs_before_ranking_and_skips_provider(tmp_path, monkeypatch):
    _, _, _, calls = _setup(tmp_path, monkeypatch)
    response = TestClient(server.app).post("/api/knowledge/ingest-and-answer", json=_request(source_authority="PROPOSED", minimum_authority="VERIFIED"))
    result = response.json()
    assert response.status_code == 200
    assert result["status"] == "no_evidence"
    assert result["retrieval"]["eligible_count"] == 0
    assert result["retrieval"]["filtered_count"] == 1
    assert result["generation"] is None
    assert calls == []
    assert Path(result["trace"]["path"]).is_file()


def test_changed_file_creates_revision_and_supersedes_prior_chunks(tmp_path, monkeypatch):
    workspace, db, _, _ = _setup(tmp_path, monkeypatch)
    client = TestClient(server.app)
    first = client.post("/api/knowledge/ingest-and-answer", json=_request()).json()
    (workspace / "policy.md").write_text("# Local policy\n\nThe local retention period is 60 days. Keep a review receipt.", encoding="utf-8")
    second = client.post("/api/knowledge/ingest-and-answer", json=_request()).json()
    assert second["ingestion"]["source_sha256"] != first["ingestion"]["source_sha256"]
    assert second["ingestion"]["source_revision"] != first["ingestion"]["source_revision"]
    with sqlite3.connect(db) as conn:
        old = conn.execute("SELECT validity FROM vector_chunks WHERE revision=?", (first["ingestion"]["source_sha256"],)).fetchone()
        versions = conn.execute("SELECT COUNT(*) FROM knowledge_sources WHERE source_path='policy.md'").fetchone()[0]
    assert old == ("SUPERSEDED",)
    assert versions == 2


def test_rejects_unsafe_paths_and_extra_request_fields_without_ingestion(tmp_path, monkeypatch):
    workspace, db, traces, _ = _setup(tmp_path, monkeypatch)
    client = TestClient(server.app)
    for payload in (_request(path="../outside.md"), _request(path=".env"), {**_request(), "url": "https://example.invalid"}):
        response = client.post("/api/knowledge/ingest-and-answer", json=payload)
        assert response.status_code == 422
    secret = workspace / "secrets.md"
    secret.write_text("password = \"012345678901234567890123\"", encoding="utf-8")
    assert client.post("/api/knowledge/ingest-and-answer", json=_request(path="secrets.md")).status_code == 422
    assert not db.exists()
    assert not list(traces.glob("*.json"))


def test_symlink_source_is_rejected(tmp_path, monkeypatch):
    workspace, db, _, _ = _setup(tmp_path, monkeypatch)
    outside = tmp_path / "outside.md"
    outside.write_text("secret content", encoding="utf-8")
    try:
        (workspace / "alias.md").symlink_to(outside)
    except OSError as error:
        import pytest
        pytest.skip(f"symlink creation is not permitted on this Windows host: {error}")
    response = TestClient(server.app).post("/api/knowledge/ingest-and-answer", json=_request(path="alias.md"))
    assert response.status_code == 422
    assert not db.exists()


def test_provider_failure_has_failed_status_and_durable_trace(tmp_path, monkeypatch):
    _, _, traces, calls = _setup(tmp_path, monkeypatch)
    def fail(*args):
        calls.append(args)
        raise RuntimeError("provider offline")
    monkeypatch.setattr(server.provider_runtime, "chat", fail)
    result = TestClient(server.app).post("/api/knowledge/ingest-and-answer", json=_request()).json()
    assert result["status"] == "failed"
    assert result["error"]["code"] == "provider_error"
    assert result["generation"] is None
    assert Path(result["trace"]["path"]).is_file()
    assert json.loads(Path(result["trace"]["path"]).read_text())["status"] == "failed"


def test_database_persistence_failure_never_reports_answered_and_writes_failure_trace(tmp_path, monkeypatch):
    workspace, _, traces, calls = _setup(tmp_path, monkeypatch)
    blocker = tmp_path / "db-is-file"
    blocker.write_text("block", encoding="utf-8")
    monkeypatch.setattr(local_rag, "_database_path", lambda: blocker / "knowledge.sqlite3")
    result = TestClient(server.app).post("/api/knowledge/ingest-and-answer", json=_request()).json()
    assert result["status"] == "failed"
    assert result["generation"] is None
    assert calls == []
    assert list(traces.glob("*.json"))
