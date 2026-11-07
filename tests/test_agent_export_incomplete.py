import json

from fastapi.testclient import TestClient

from src.api import server


def test_export_rejects_incomplete_json_instead_of_silent_partial(monkeypatch, tmp_path):
    (tmp_path / "agent_1234abcd.json").write_text(json.dumps({"id": "agent_1234abcd"}), encoding="utf-8")
    (tmp_path / "agent_5678abcd.json").write_text('{"id":', encoding="utf-8")
    monkeypatch.setattr(server, "AGENTS_DIR", tmp_path)

    response = TestClient(server.app).get("/api/agents/export")

    assert response.status_code == 409
    assert "agents" not in response.json()


def test_export_preserves_utf8_profile_content(monkeypatch, tmp_path):
    record = {"id": "agent_1234abcd", "config": {"name": "Àngels", "description": "Revisión de facturas"}}
    (tmp_path / "agent_1234abcd.json").write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(server, "AGENTS_DIR", tmp_path)

    response = TestClient(server.app).get("/api/agents/export")

    assert response.status_code == 200
    assert response.json()["agents"] == [record]
