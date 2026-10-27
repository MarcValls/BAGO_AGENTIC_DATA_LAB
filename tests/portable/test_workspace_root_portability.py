from __future__ import annotations

import json
from pathlib import Path

from src.api import server


def test_unconfigured_workspace_defaults_outside_application_source(tmp_path, monkeypatch):
    app = tmp_path / "application"
    app.mkdir()
    config = app / ".bago" / "data" / "config" / "workspace.json"
    default = app / ".bago" / "data" / "workspaces" / "default"
    monkeypatch.setattr(server, "REPO_ROOT", app)
    monkeypatch.setattr(server, "_WORKSPACE_CONFIG_PATH", config)
    monkeypatch.setattr(server, "_DEFAULT_WORKSPACE_ROOT", default)

    result = server._load_workspace_root()

    assert result == default
    assert result.is_dir()
    assert result != app


def test_valid_saved_workspace_root_wins_over_portable_fallback(tmp_path, monkeypatch):
    app = tmp_path / "application"
    app.mkdir()
    config = app / ".bago" / "data" / "config" / "workspace.json"
    selected = tmp_path / "my-project"
    selected.mkdir()
    config.parent.mkdir(parents=True)
    config.write_text(json.dumps({"workspace_root": str(selected)}), encoding="utf-8")
    fallback = app / ".bago" / "data" / "workspaces" / "default"
    monkeypatch.setattr(server, "_WORKSPACE_CONFIG_PATH", config)
    monkeypatch.setattr(server, "_DEFAULT_WORKSPACE_ROOT", fallback)

    assert server._load_workspace_root() == selected
    assert not fallback.exists()
