from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from src.api.server import app


def test_runtime_storage_reports_effective_portable_paths_without_creating_them(tmp_path, monkeypatch):
    app_root = tmp_path / "application-copy"
    app_root.mkdir()
    monkeypatch.setenv("BAGO_APP_ROOT", str(app_root))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "old-localappdata"))
    monkeypatch.delenv("BAGO_DATA_ROOT", raising=False)
    for name in (
        "BAGO_CONVERSATION_DB_PATH", "BAGO_CAPABILITY_DB_PATH", "BAGO_AGENT_EVALUATION_DB_PATH",
        "BAGO_TASK_HISTORY_PATH", "BAGO_CONTACTS_STATE_DIR", "BAGO_COMMUNICATIONS_STATE_DIR",
        "BAGO_PROVIDER_REGISTRY_PATH", "BAGO_MODEL_POLICY_PATH", "BAGO_GEX_STATE_DIR",
        "BAGO_GEX_IDENTITY_DB_PATH", "ADL_KNOWLEDGE_DB", "ADL_ONTOLOGY_DB",
        "ADL_KNOWLEDGE_TRACE_DIR", "ADL_ONTOLOGY_TRACE_DIR", "BAGO_WHATSAPP_STATE_DIR",
        "BAGO_WEB_RESEARCH_STATE_DIR", "BAGO_DOCUMENT_OUTPUT_ROOT", "BAGO_OLLAMA_CONFIG_PATH",
        "ADL_ETL_METADATA_DB",
    ):
        monkeypatch.delenv(name, raising=False)

    response = TestClient(app).get("/api/runtime/storage")

    assert response.status_code == 200
    body = response.json()
    data_root = app_root / ".bago" / "data"
    assert Path(body["application_root"]) == app_root
    assert Path(body["data_root"]) == data_root
    assert body["mode"] == "portable"
    assert body["external_overrides"] == []
    assert body["process_id"] > 0
    assert body["server_source_sha256_at_import"]
    assert Path(body["server_source_path"]).name == "server.py"
    assert body["data_root_exists"] is False
    assert all(Path(path).is_relative_to(data_root) for path in body["effective_paths"].values())
    assert not data_root.exists()


def test_runtime_storage_flags_per_store_path_escaping_common_root(tmp_path, monkeypatch):
    app_root = tmp_path / "application-copy"
    app_root.mkdir()
    monkeypatch.setenv("BAGO_APP_ROOT", str(app_root))
    monkeypatch.delenv("BAGO_DATA_ROOT", raising=False)
    external = tmp_path / "legacy" / "library.sqlite3"
    monkeypatch.setenv("BAGO_CONVERSATION_DB_PATH", str(external))

    body = TestClient(app).get("/api/runtime/storage").json()

    assert "BAGO_CONVERSATION_DB_PATH" in body["external_overrides"]
    assert Path(body["effective_paths"]["conversations"]) == external
    assert not external.parent.exists()
