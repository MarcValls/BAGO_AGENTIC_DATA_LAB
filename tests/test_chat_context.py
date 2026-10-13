from pathlib import Path

from fastapi.testclient import TestClient

from src.api import server
from src.conversations import ConversationStore
from src.cognition.bago5_chat import MAX_EXPANSIONS, MAX_FOCUS_UNITS, MAX_HOPS, PROFILE


def test_context_reports_bound_locations_without_creating_missing_paths(monkeypatch, tmp_path):
    workspace = tmp_path / "bound-workspace"
    database = tmp_path / "outside-workspace" / "history.sqlite3"
    trace_root = tmp_path / "configured-traces"
    monkeypatch.setattr(server, "REPO_ROOT", workspace)
    monkeypatch.setattr(server, "CONVERSATIONS", ConversationStore(database))
    monkeypatch.setattr(server, "AGENT_CHAT_TRACE_DIR", trace_root)
    monkeypatch.setenv("BAGO_CONVERSATION_DB_PATH", str(tmp_path / "unused.sqlite3"))

    def no_creation(*args, **kwargs):
        raise AssertionError("metadata endpoint must not create storage")

    with TestClient(server.app) as client:
        monkeypatch.setattr(Path, "mkdir", no_creation)
        response = client.get("/api/chat/context")

    assert response.status_code == 200
    payload = response.json()
    assert payload["workspace_root"] == str(workspace.resolve())
    assert payload["cognition"] == {
        "profile": PROFILE, "capacity": MAX_FOCUS_UNITS,
        "max_hops": MAX_HOPS, "max_expansions": MAX_EXPANSIONS,
    }
    paths = {item["id"]: item for item in payload["paths"]}
    expected_paths = {
        "project-context": workspace / ".bago/context/PROJECT_CONTEXT.md",
        "project-state": workspace / ".bago/state/PROJECT_STATE.json",
        "active-handoff": workspace / ".bago/runtime/ACTIVE_HANDOFF.md",
        "conversations": database,
        "cognition-traces": trace_root / "cognition",
    }
    assert set(paths) == set(expected_paths)
    for location_id, path in expected_paths.items():
        assert paths[location_id]["path"] == str(path.resolve())
        assert paths[location_id]["state"] == "absent"
        assert paths[location_id]["label"] and paths[location_id]["purpose"]
        assert not path.exists()
    assert payload["memory"]["kind"] == "conversation_history"
    assert payload["memory"]["state"] == "absent"
    assert "not connected" in payload["memory"]["description"]


def test_context_checks_presence_without_disclosing_contents_or_provider_credentials(monkeypatch, tmp_path):
    workspace = tmp_path / "workspace"
    context = workspace / ".bago/context/PROJECT_CONTEXT.md"
    context.parent.mkdir(parents=True)
    context.write_text("PRIVATE_CONTEXT_SENTINEL", encoding="utf-8")
    database = tmp_path / "history.sqlite3"
    database.write_bytes(b"PRIVATE_CONVERSATION_SENTINEL")
    trace_root = tmp_path / "traces"
    (trace_root / "cognition").mkdir(parents=True)
    monkeypatch.setattr(server, "REPO_ROOT", workspace)
    monkeypatch.setattr(server, "CONVERSATIONS", ConversationStore(database))
    monkeypatch.setattr(server, "AGENT_CHAT_TRACE_DIR", trace_root)
    monkeypatch.setenv("OLLAMA_API_KEY", "PRIVATE_PROVIDER_SENTINEL")

    def no_storage_read(*args, **kwargs):
        raise AssertionError("metadata endpoint must not read stored content")

    monkeypatch.setattr(server.CONVERSATIONS, "_connect", no_storage_read)
    with TestClient(server.app) as client:
        monkeypatch.setattr(Path, "read_text", no_storage_read)
        monkeypatch.setattr(Path, "read_bytes", no_storage_read)
        response = client.get("/api/chat/context")

    assert response.status_code == 200
    payload = response.json()
    paths = {item["id"]: item for item in payload["paths"]}
    assert paths["project-context"]["state"] == "present"
    assert paths["project-state"]["state"] == "absent"
    assert paths["active-handoff"]["state"] == "absent"
    assert paths["conversations"]["state"] == "present"
    assert paths["cognition-traces"]["state"] == "present"
    assert payload["memory"]["state"] == "present"
    assert "PRIVATE_" not in response.text
