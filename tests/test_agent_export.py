import json
from pathlib import Path

from fastapi.testclient import TestClient

from src.api import server


def test_agent_export_returns_one_json_endpoint_with_saved_records(monkeypatch, tmp_path: Path):
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    record = {
        "id": "agent_export_fixture",
        "config": {"name": "Export fixture", "system_prompt": "Review safely"},
        "created_at": "2026-10-17T12:00:00Z",
    }
    (agents_dir / "agent_export_fixture.json").write_text(
        json.dumps(record), encoding="utf-8"
    )
    monkeypatch.setattr(server, "AGENTS_DIR", agents_dir)

    response = TestClient(server.app).get("/api/agents/export")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert response.json()["agents"] == [record]
    assert sum(
        route.path == "/api/agents/export" and "GET" in getattr(route, "methods", set())
        for route in server.app.routes
    ) == 1
