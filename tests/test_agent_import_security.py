"""Regression tests for imported-agent origin checks and collision safety."""
import json
import uuid

import pytest
from fastapi.testclient import TestClient

from src.api import server


@pytest.fixture
def isolated_import(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "AGENTS_DIR", tmp_path)
    return TestClient(server.app), tmp_path


def exported_agent():
    return {"id": "agent_12345678", "created_at": "2026-01-01T00:00:00Z", "config": {
        "name": "Import fixture", "description": "Example", "type": "tool", "system_prompt": "Help", "tools": [],
        "task": {"prompt": "At {{date}}", "dates": [{"key": "date", "label": "Date", "value": "2026-11-10"}]},
    }}


@pytest.mark.parametrize("origin,content_type,expected", [
    ("https://untrusted.example", "text/plain", 403),
    ("https://untrusted.example", "application/json", 403),
    ("null", "application/json", 403),
    ("http://127.0.0.1:8080", "text/plain", 415),
])
def test_import_rejects_cross_origin_or_non_json_without_effect(isolated_import, origin, content_type, expected):
    client, directory = isolated_import
    response = client.post("/api/agents/import", content=json.dumps({"agents": [exported_agent()]}),
                           headers={"Origin": origin, "Content-Type": content_type})
    assert response.status_code == expected
    assert list(directory.iterdir()) == []


def test_allowed_json_import_preserves_task(isolated_import):
    client, directory = isolated_import
    response = client.post("/api/agents/import", json={"agents": [exported_agent()]},
                           headers={"Origin": "http://127.0.0.1:8080"})
    assert response.status_code == 200
    saved = json.loads((directory / (response.json()["agent_ids"][0] + ".json")).read_text(encoding="utf-8"))
    assert saved["config"]["task"] == exported_agent()["config"]["task"]


def test_import_does_not_overwrite_existing_identity(isolated_import, monkeypatch):
    client, directory = isolated_import
    existing_id = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    original = directory / ("agent_" + existing_id.hex + ".json")
    original.write_bytes(b"original profile")
    monkeypatch.setattr(server.uuid, "uuid4", lambda: existing_id)
    response = client.post("/api/agents/import", json={"agents": [exported_agent()]})
    assert response.status_code == 500
    assert response.json()["detail"]["imported_ids"] == []
    assert original.read_bytes() == b"original profile"
    assert not list(directory.glob(".agent-import-*.tmp"))
