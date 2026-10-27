from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.storage.portable import StoragePathError, data_path, data_root, relocate_owned_path, storage_status


def _clear_store_overrides(monkeypatch):
    for name in (
        "BAGO_DATA_ROOT", "BAGO_CONVERSATION_DB_PATH", "BAGO_CAPABILITY_DB_PATH",
        "BAGO_AGENT_EVALUATION_DB_PATH", "BAGO_TASK_HISTORY_PATH", "BAGO_CONTACTS_STATE_DIR",
        "BAGO_COMMUNICATIONS_STATE_DIR", "BAGO_PROVIDER_REGISTRY_PATH", "BAGO_MODEL_POLICY_PATH",
        "BAGO_GEX_STATE_DIR", "BAGO_GEX_IDENTITY_DB_PATH", "ADL_KNOWLEDGE_DB",
        "ADL_ONTOLOGY_DB", "BAGO_WHATSAPP_STATE_DIR", "BAGO_WEB_RESEARCH_STATE_DIR",
        "BAGO_DOCUMENT_OUTPUT_ROOT", "ADL_KNOWLEDGE_TRACE_DIR", "ADL_ONTOLOGY_TRACE_DIR",
        "BAGO_OLLAMA_CONFIG_PATH",
    ):
        monkeypatch.delenv(name, raising=False)


def test_default_data_root_is_below_application_copy_and_is_read_only(tmp_path, monkeypatch):
    app = tmp_path / "copy"
    app.mkdir()
    monkeypatch.setenv("BAGO_APP_ROOT", str(app))
    _clear_store_overrides(monkeypatch)

    assert data_root() == app / ".bago" / "data"
    assert data_path("conversations", "library.sqlite3") == app / ".bago" / "data" / "conversations" / "library.sqlite3"
    assert not (app / ".bago").exists()


def test_all_reported_default_stores_share_the_portable_root(tmp_path, monkeypatch):
    app = tmp_path / "copy"
    app.mkdir()
    monkeypatch.setenv("BAGO_APP_ROOT", str(app))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "legacy-localappdata"))
    _clear_store_overrides(monkeypatch)

    status = storage_status()
    root = Path(status["data_root"])
    assert status["mode"] == "portable"
    assert status["data_root_exists"] is False
    assert status["external_overrides"] == []
    assert status["resolver_creates_directories"] is False
    assert all(Path(value).is_relative_to(root) for value in status["effective_paths"].values())
    assert not (tmp_path / "legacy-localappdata").exists()


def test_explicit_data_root_is_reported_without_reading_or_creating_it(tmp_path, monkeypatch):
    app = tmp_path / "copy"
    app.mkdir()
    external = tmp_path / "shared-data"
    monkeypatch.setenv("BAGO_APP_ROOT", str(app))
    monkeypatch.setenv("BAGO_DATA_ROOT", str(external))
    _clear_store_overrides(monkeypatch)
    monkeypatch.setenv("BAGO_DATA_ROOT", str(external))

    status = storage_status()
    assert Path(status["data_root"]) == external
    assert status["mode"] == "external_data_root"
    assert status["data_root_exists"] is False
    assert not external.exists()


def test_explicit_storage_alias_relocates_only_matching_owned_path(tmp_path, monkeypatch):
    app = tmp_path / "copy"
    app.mkdir()
    data = app / ".bago" / "data"
    data.mkdir(parents=True)
    old_root = tmp_path / "old-instance" / ".bago" / "data" / "development"
    alias_file = data / "storage-aliases.json"
    alias_file.write_text(json.dumps({"version": 1, "aliases": [
        {"source_prefix": str(old_root), "target_prefix": "development"},
    ]}), encoding="utf-8")
    monkeypatch.setenv("BAGO_APP_ROOT", str(app))
    _clear_store_overrides(monkeypatch)

    relocated = relocate_owned_path(old_root / "run-1" / "state.json")
    unrelated = relocate_owned_path(tmp_path / "other-project" / "state.json")

    assert relocated == data / "development" / "run-1" / "state.json"
    assert unrelated == tmp_path / "other-project" / "state.json"


def test_storage_alias_rejects_traversal_and_does_not_create_target(tmp_path, monkeypatch):
    app = tmp_path / "copy"
    app.mkdir()
    data = app / ".bago" / "data"
    data.mkdir(parents=True)
    alias_file = data / "storage-aliases.json"
    alias_file.write_text(json.dumps({"version": 1, "aliases": [
        {"source_prefix": str(tmp_path / "legacy"), "target_prefix": "../outside"},
    ]}), encoding="utf-8")
    monkeypatch.setenv("BAGO_APP_ROOT", str(app))
    _clear_store_overrides(monkeypatch)

    with pytest.raises(StoragePathError, match="unsafe_data_path"):
        relocate_owned_path(tmp_path / "legacy" / "state.json")
    assert not (tmp_path / "outside").exists()


@pytest.mark.parametrize("parts", [(), ("..", "outside"), ("folder\\..\\outside",), ("C:", "outside"), ("NUL",)])
def test_rejects_unsafe_data_path_components(tmp_path, monkeypatch, parts):
    app = tmp_path / "copy"
    app.mkdir()
    monkeypatch.setenv("BAGO_APP_ROOT", str(app))
    _clear_store_overrides(monkeypatch)

    with pytest.raises(StoragePathError):
        data_path(*parts)
