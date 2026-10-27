from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

from scripts import migrate_portable_data as migration


def _mapping(path: Path, entries):
    path.write_text(json.dumps({"version": 1, "entries": entries}), encoding="utf-8")


def test_explicit_plan_and_apply_copy_file_and_sqlite_without_mutating_sources(tmp_path):
    source = tmp_path / "legacy"
    source.mkdir()
    document = source / "settings.json"
    document.write_text('{"theme":"dark"}\n', encoding="utf-8")
    database = source / "library.sqlite3"
    with sqlite3.connect(database) as db:
        db.execute("CREATE TABLE conversations (id TEXT PRIMARY KEY, content TEXT NOT NULL)")
        db.execute("INSERT INTO conversations VALUES (?, ?)", ("conv_kept", "original bytes stay"))
    original_hash = hashlib.sha256(database.read_bytes()).hexdigest()
    mapping_path = tmp_path / "map.json"
    _mapping(mapping_path, [
        {"source": str(document), "target": "config/settings.json", "kind": "file"},
        {"source": str(database), "target": "conversations/library.sqlite3", "kind": "sqlite"},
    ])
    destination = tmp_path / "portable-data"
    plan_path = tmp_path / "plan.json"
    planned = migration.create_plan(mapping_path, destination, plan_path)
    assert planned["entry_count"] == 2
    assert not destination.exists()
    result = migration.apply_plan(plan_path)
    assert result["status"] == "APPLIED"
    assert (destination / "config/settings.json").read_bytes() == document.read_bytes()
    with sqlite3.connect(destination / "conversations/library.sqlite3") as db:
        assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert db.execute("SELECT id,content FROM conversations").fetchall() == [("conv_kept", "original bytes stay")]
    assert hashlib.sha256(database.read_bytes()).hexdigest() == original_hash


def test_plan_rejects_overlapping_targets_and_existing_file_conflicts_before_writes(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("retained", encoding="utf-8")
    mapping_path = tmp_path / "map.json"
    destination = tmp_path / "data"
    _mapping(mapping_path, [
        {"source": str(source), "target": "one", "kind": "file"},
        {"source": str(source), "target": "one/child", "kind": "file"},
    ])
    with pytest.raises(migration.MigrationError, match="target_collision"):
        migration.create_plan(mapping_path, destination, tmp_path / "plan.json")
    assert not destination.exists()
    assert not (tmp_path / "plan.json").exists()
    destination.mkdir()
    (destination / "one").write_text("different", encoding="utf-8")
    _mapping(mapping_path, [{"source": str(source), "target": "one", "kind": "file"}])
    with pytest.raises(migration.MigrationError, match="target_conflict"):
        migration.create_plan(mapping_path, destination, tmp_path / "plan2.json")
    assert (destination / "one").read_text(encoding="utf-8") == "different"
    assert not (tmp_path / "plan2.json").exists()


def test_apply_merges_missing_files_into_existing_data_root_without_overwrite(tmp_path):
    source = tmp_path / "legacy"
    source.mkdir()
    copied = source / "copy.json"
    copied.write_text('{"kept":true}\n', encoding="utf-8")
    same = source / "same.json"
    same.write_text('{"same":true}\n', encoding="utf-8")
    destination = tmp_path / "app" / ".bago" / "data"
    destination.mkdir(parents=True)
    (destination / "agents").mkdir()
    (destination / "config.json").write_bytes(same.read_bytes())
    (destination / "unrelated.txt").write_text("preserve", encoding="utf-8")
    mapping_path = tmp_path / "map.json"
    _mapping(mapping_path, [
        {"source": str(copied), "target": "conversations/library.json", "kind": "file"},
        {"source": str(same), "target": "config.json", "kind": "file"},
    ])
    plan_path = tmp_path / "plan.json"
    planned = migration.create_plan(mapping_path, destination, plan_path)
    assert planned["entry_count"] == 2
    result = migration.apply_plan(plan_path)
    assert result["status"] == "APPLIED"
    assert result["new_entry_count"] == 1
    assert result["already_present_count"] == 1
    assert (destination / "conversations/library.json").read_bytes() == copied.read_bytes()
    assert (destination / "config.json").read_bytes() == same.read_bytes()
    assert (destination / "unrelated.txt").read_text(encoding="utf-8") == "preserve"
    assert (destination / "agents").is_dir()


def test_target_collision_rejects_child_added_before_file_parent(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("retained", encoding="utf-8")
    mapping_path = tmp_path / "map.json"
    _mapping(mapping_path, [
        {"source": str(source), "target": "one/child", "kind": "file"},
        {"source": str(source), "target": "one", "kind": "file"},
    ])
    with pytest.raises(migration.MigrationError, match="target_collision"):
        migration.create_plan(mapping_path, tmp_path / "data", tmp_path / "plan.json")
    assert not (tmp_path / "data").exists()
    assert not (tmp_path / "plan.json").exists()


def test_apply_refuses_changed_source_and_keeps_destination_absent(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("before", encoding="utf-8")
    mapping_path = tmp_path / "map.json"
    _mapping(mapping_path, [{"source": str(source), "target": "file.txt", "kind": "file"}])
    destination, plan_path = tmp_path / "portable-data", tmp_path / "plan.json"
    migration.create_plan(mapping_path, destination, plan_path)
    source.write_text("after", encoding="utf-8")
    with pytest.raises(migration.MigrationError, match="plan_changed"):
        migration.apply_plan(plan_path)
    assert not destination.exists()


def test_apply_detects_sqlite_change_even_when_row_counts_are_unchanged(tmp_path):
    source = tmp_path / "history.sqlite3"
    with sqlite3.connect(source) as db:
        db.execute("CREATE TABLE records (id TEXT PRIMARY KEY, content TEXT NOT NULL)")
        db.execute("INSERT INTO records VALUES ('one', 'before')")
    mapping_path = tmp_path / "map.json"
    _mapping(mapping_path, [{"source": str(source), "target": "history.sqlite3", "kind": "sqlite"}])
    destination, plan_path = tmp_path / "data", tmp_path / "plan.json"
    migration.create_plan(mapping_path, destination, plan_path)
    with sqlite3.connect(source) as db:
        db.execute("UPDATE records SET content='after' WHERE id='one'")
    with pytest.raises(migration.MigrationError, match="plan_changed"):
        migration.apply_plan(plan_path)
    assert not destination.exists()


def test_inventory_is_explicit_and_does_not_read_unlisted_neighbor(tmp_path):
    source = tmp_path / "selected.txt"
    source.write_text("selected", encoding="utf-8")
    (tmp_path / "not-selected.txt").write_text("never discovered", encoding="utf-8")
    mapping_path = tmp_path / "map.json"
    _mapping(mapping_path, [{"source": str(source), "target": "selected.txt", "kind": "file"}])
    result = migration.inventory(mapping_path)
    assert result["count"] == 1
    assert result["entries"][0]["source_name"] == "selected.txt"
    assert all("not-selected" not in json.dumps(entry) for entry in result["entries"])


def test_private_adl_owned_file_requires_two_explicit_opt_ins_and_preserves_bytes(tmp_path):
    owned = tmp_path / "ADL-state" / "whatsapp"
    owned.mkdir(parents=True)
    profile = owned / "credentials.json"
    private_bytes = b'{"session":"opaque-owned-session-bytes"}\r\n'
    profile.write_bytes(private_bytes)
    mapping_path = tmp_path / "private-map.json"
    _mapping(mapping_path, [{"source": str(profile), "target": "whatsapp/credentials.json",
                             "kind": "file", "private_owned": True}])
    destination, plan_path = tmp_path / "portable-data", tmp_path / "private-plan.json"
    with pytest.raises(migration.MigrationError, match="private_file_opt_in_required"):
        migration.create_plan(mapping_path, destination, plan_path, private_owned_roots=(owned,))
    with pytest.raises(migration.MigrationError, match="private_file_outside_owned_root"):
        migration.create_plan(mapping_path, destination, plan_path, include_private_owned=True)
    planned = migration.create_plan(mapping_path, destination, plan_path, include_private_owned=True,
                                    private_owned_roots=(owned,))
    assert planned["private_file_count"] == 1
    with pytest.raises(migration.MigrationError, match="private_file_approval_mismatch"):
        migration.apply_plan(plan_path, private_owned_roots=(owned,))
    copied = migration.apply_plan(plan_path, include_private_owned=True, private_owned_roots=(owned,))
    assert copied["status"] == "APPLIED"
    assert (destination / "whatsapp/credentials.json").read_bytes() == private_bytes
    assert profile.read_bytes() == private_bytes
    assert "opaque-owned-session-bytes" not in json.dumps(copied)


@pytest.mark.parametrize("forbidden_component", ["Browser", ".codex", "BraveSoftware"])
def test_private_opt_in_never_allows_general_browser_or_codex_state(tmp_path, forbidden_component):
    source = tmp_path / forbidden_component / "private.json"
    source.parent.mkdir()
    source.write_text('{"opaque":"value"}', encoding="utf-8")
    mapping_path = tmp_path / "mapping.json"
    _mapping(mapping_path, [{"source": str(source), "target": "private.json", "kind": "file", "private_owned": True}])
    with pytest.raises(migration.MigrationError, match="general_browser_or_codex_state_denied"):
        migration.create_plan(mapping_path, tmp_path / "portable-data", tmp_path / "plan.json",
                              include_private_owned=True, private_owned_roots=(tmp_path,))


def test_migration_entry_budget_is_large_but_finite():
    assert migration.MAX_ENTRIES == 100_000
    assert migration.MAX_TOTAL_BYTES < float("inf")


def test_plan_accepts_more_than_the_legacy_500_entry_limit(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("owned", encoding="utf-8")
    entries = [{"source": str(source), "target": f"files/{index:04}.txt", "kind": "file"} for index in range(501)]
    mapping_path = tmp_path / "many.json"
    _mapping(mapping_path, entries)
    result = migration.create_plan(mapping_path, tmp_path / "data", tmp_path / "plan.json")
    assert result["entry_count"] == 501


def test_failed_copy_keeps_stage_and_does_not_promote_destination(tmp_path, monkeypatch):
    source = tmp_path / "source.txt"
    source.write_text("retained", encoding="utf-8")
    mapping_path = tmp_path / "mapping.json"
    _mapping(mapping_path, [{"source": str(source), "target": "file.txt", "kind": "file"}])
    destination, plan_path = tmp_path / "portable-data", tmp_path / "plan.json"
    migration.create_plan(mapping_path, destination, plan_path)

    def fail_copy(*_args, **_kwargs):
        raise OSError("copy failed")

    monkeypatch.setattr(migration.shutil, "copyfile", fail_copy)
    with pytest.raises(migration.MigrationError, match="migration_stage_retained"):
        migration.apply_plan(plan_path)
    assert not destination.exists()
    stages = list(tmp_path.glob(".portable-data.portable-stage-*"))
    assert len(stages) == 1
    assert stages[0].is_dir()
