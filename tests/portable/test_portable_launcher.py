from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.serve_portable import portable_development_profile


def test_launcher_accepts_only_explicit_migrated_profile_without_rewriting_targets(tmp_path, monkeypatch):
    app, data = tmp_path / "application", tmp_path / "application" / ".bago" / "data"
    app.mkdir()
    profile_path = data / "development" / "profile.json"
    profile_path.parent.mkdir(parents=True)
    payload = {"root": str(tmp_path / "original-authorized-target"),
               "state_root": str(tmp_path / "old-state"), "allowed_paths": ["src", "tests"]}
    exact = json.dumps(payload).encode("utf-8")
    profile_path.write_bytes(exact)
    monkeypatch.setenv("BAGO_APP_ROOT", str(app))
    monkeypatch.delenv("BAGO_DATA_ROOT", raising=False)
    resolved = portable_development_profile(profile_path)
    assert resolved == profile_path
    assert profile_path.read_bytes() == exact
    assert json.loads(profile_path.read_text(encoding="utf-8"))["root"] == str(tmp_path / "original-authorized-target")


def test_launcher_does_not_rebind_external_profile_to_portable_root(tmp_path, monkeypatch):
    app = tmp_path / "application"
    app.mkdir()
    external = tmp_path / "host-profile.json"
    external.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("BAGO_APP_ROOT", str(app))
    monkeypatch.delenv("BAGO_DATA_ROOT", raising=False)
    with pytest.raises(ValueError, match="inside portable data"):
        portable_development_profile(external)
