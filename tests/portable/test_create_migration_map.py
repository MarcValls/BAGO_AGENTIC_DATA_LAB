from __future__ import annotations

from pathlib import Path

from scripts.create_portable_migration_map import build_existing_portable_map, build_map


def test_map_includes_allowlisted_adl_files_without_reading_unlisted_neighbors(tmp_path):
    app_data = tmp_path / "legacy-data"
    application = tmp_path / "application"
    (app_data / "conversations").mkdir(parents=True)
    (app_data / "capabilities" / "workspace_123").mkdir(parents=True)
    (app_data / "communications").mkdir()
    (application / "agents" / "created").mkdir(parents=True)
    (application / ".bago" / "knowledge").mkdir(parents=True)
    (app_data / "conversations" / "library.sqlite3").write_bytes(b"db-bytes")
    (app_data / "capabilities" / "workspace_123" / "capabilities.sqlite3").write_bytes(b"db-bytes")
    (app_data / "communications" / "worker.lock").write_text("transient", encoding="utf-8")
    (app_data / "unlisted-secrets.txt").write_text("never selected", encoding="utf-8")
    (application / "agents" / "created" / "agent.json").write_text("{}", encoding="utf-8")
    (application / ".bago" / "knowledge" / "ontology.sqlite3").write_bytes(b"db-bytes")

    result = build_map(app_data, application)
    rows = {row["target"]: row for row in result["entries"]}

    assert rows["conversations/library.sqlite3"]["kind"] == "sqlite"
    assert rows["capabilities/workspace_123/capabilities.sqlite3"]["kind"] == "sqlite"
    assert rows["agents/created/agent.json"]["kind"] == "file"
    assert rows["knowledge/ontology.sqlite3"]["kind"] == "sqlite"
    assert not any("worker.lock" in row["source"] or "unlisted-secrets" in row["source"] for row in rows.values())
    assert result["scope"].endswith("source contents are not read")


def test_map_allows_an_absent_legacy_appdata_root(tmp_path):
    app_data = tmp_path / "absent-appdata"
    application = tmp_path / "application"
    (application / "agents" / "created").mkdir(parents=True)
    (application / "agents" / "created" / "agent.json").write_text("{}", encoding="utf-8")

    result = build_map(app_data, application)

    assert [entry["target"] for entry in result["entries"]] == ["agents/created/agent.json"]
    assert not app_data.exists()


def test_whatsapp_session_files_require_separate_private_owned_opt_in(tmp_path):
    app_data = tmp_path / "legacy-data"
    application = tmp_path / "application"
    (app_data / "whatsapp" / "brave-profile" / "Default").mkdir(parents=True)
    application.mkdir()
    cookie_file = app_data / "whatsapp" / "brave-profile" / "Default" / "Cookies"
    cookie_file.write_bytes(b"opaque-session-data")

    omitted = build_map(app_data, application)
    included = build_map(app_data, application, include_whatsapp=True)

    assert not any("Cookies" in row["source"] for row in omitted["entries"])
    selected = next(row for row in included["entries"] if row["target"].endswith("Cookies"))
    assert selected["private_owned"] is True
    assert selected["target"] == "whatsapp/brave-profile/Default/Cookies"
    assert included["whatsapp_session_included"] is True


def test_existing_portable_tree_maps_relative_state_and_omits_cache_and_transient_files(tmp_path):
    source = tmp_path / "legacy" / ".bago" / "data"
    (source / "development" / "candidate").mkdir(parents=True)
    (source / "traces").mkdir()
    (source / "whatsapp" / "brave-profile" / "Default" / "Cache").mkdir(parents=True)
    (source / "development" / "candidate" / "receipt.json").write_text("{}", encoding="utf-8")
    (source / "traces" / "ledger.sqlite3").write_bytes(b"sqlite")
    (source / "traces" / "worker.lock").write_text("lock", encoding="utf-8")
    (source / "whatsapp" / "brave-profile" / "Default" / "Cookies").write_bytes(b"private")
    (source / "whatsapp" / "brave-profile" / "Default" / "Cache" / "cache.bin").write_bytes(b"cache")

    result = build_existing_portable_map(source)
    targets = {row["target"]: row for row in result["entries"]}

    assert targets["development/candidate/receipt.json"]["kind"] == "file"
    assert targets["traces/ledger.sqlite3"]["kind"] == "sqlite"
    assert "traces/worker.lock" not in targets
    assert "whatsapp/brave-profile/Default/Cookies" not in targets
    assert not any("cache.bin" in target for target in targets)

    opted_in = build_existing_portable_map(source, include_whatsapp=True)
    cookie = next(row for row in opted_in["entries"] if row["target"].endswith("Cookies"))
    assert cookie["private_owned"] is True
    assert not any("cache.bin" in row["target"] for row in opted_in["entries"])
