"""Permanent deletion is tested only against fresh temporary databases."""
from contextlib import closing
import sqlite3

import pytest
from fastapi.testclient import TestClient
from src.api import server
from src.conversations import ConversationStore, ConversationConflict, ConversationNotFound
from src.conversations import library


@pytest.fixture
def data(tmp_path, monkeypatch):
    store = ConversationStore(tmp_path / "isolated.sqlite3")
    conversation = store.create("assistant", "app-assistant", "Synthetic trash")
    message = store.append_message(conversation["id"], 0, "assistant", "Synthetic message", {"cognitive_trace": {"trace_id": "fixture-trace"}})
    trashed = store.set_status(conversation["id"], message["revision"], "deleted")
    monkeypatch.setattr(server, "CONVERSATIONS", store)
    return store, trashed, tmp_path


def counts(store, conversation_id):
    with closing(store._connect()) as db:
        return tuple(db.execute(f"SELECT COUNT(*) FROM {table} WHERE {'id' if table == 'conversations' else 'conversation_id'}=?", (conversation_id,)).fetchone()[0] for table in ("conversations", "messages"))


def test_success_removes_rows_and_message_cognition_refs_but_preserves_external_files(data):
    store, d, root = data
    external = root / "external-trace.json"
    external.write_text('{"preserved":true}')
    unrelated = store.create("agent", "fixture-agent", "Keep this")
    assert store.permanently_delete(d["id"], d["revision"], True) == {"id": d["id"], "status": "permanently_deleted"}
    assert counts(store, d["id"]) == (0, 0)
    assert external.read_text() == '{"preserved":true}'
    assert store.get(unrelated["id"])["title"] == "Keep this"
    with pytest.raises(ConversationNotFound):
        store.restore(d["id"], d["revision"])
    with pytest.raises(ConversationNotFound):
        store.permanently_delete(d["id"], d["revision"], True)


@pytest.mark.parametrize("confirmed", [False, None, "true", 1])
def test_denied_confirmation_never_changes_rows(data, confirmed):
    store, d, _ = data
    with pytest.raises(ValueError):
        store.permanently_delete(d["id"], d["revision"], confirmed)
    assert counts(store, d["id"]) == (1, 1)


@pytest.mark.parametrize("status", ["active", "archived"])
def test_wrong_state_refused(data, status):
    store, d, _ = data
    restored = store.restore(d["id"], d["revision"])
    target = store.set_status(d["id"], restored["revision"], status) if status == "archived" else restored
    with pytest.raises(ConversationConflict):
        store.permanently_delete(d["id"], target["revision"], True)
    assert counts(store, d["id"]) == (1, 1)


def test_stale_revision_refused(data):
    store, d, _ = data
    with pytest.raises(ConversationConflict):
        store.permanently_delete(d["id"], d["revision"] - 1, True)
    assert counts(store, d["id"]) == (1, 1)


def test_other_project_not_found_and_preserved(data, monkeypatch):
    store, d, _ = data
    with monkeypatch.context() as m:
        m.setattr(library, "PROJECT_ID", "another-project")
        foreign = store.create("assistant", "app-assistant")
        foreign = store.set_status(foreign["id"], 0, "deleted")
    with pytest.raises(ConversationNotFound):
        store.permanently_delete(foreign["id"], foreign["revision"], True)
    assert counts(store, foreign["id"]) == (1, 0)
    assert counts(store, d["id"]) == (1, 1)


def test_failure_rolls_back_messages_with_conversation(data):
    store, d, _ = data
    with closing(store._connect()) as db:
        db.execute("CREATE TRIGGER block_delete BEFORE DELETE ON conversations BEGIN SELECT RAISE(ABORT,'fixture failure'); END")
    with pytest.raises(sqlite3.IntegrityError):
        store.permanently_delete(d["id"], d["revision"], True)
    assert counts(store, d["id"]) == (1, 1)
    with closing(store._connect()) as db:
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []


@pytest.mark.parametrize("body", [
    {"expected_revision": 2, "confirmed": False},
    {"expected_revision": 2, "confirmed": "true"},
    {"expected_revision": True, "confirmed": True},
    {"expected_revision": "2", "confirmed": True},
    {"expected_revision": -1, "confirmed": True},
    {"expected_revision": 2, "confirmed": True, "extra": 1},
    {"expected_revision": 2},
])
def test_api_strict_confirmation_and_revision(data, body):
    store, d, _ = data
    client = TestClient(server.app)
    assert client.request("DELETE", f"/api/conversations/{d['id']}", json=body).status_code == 422
    assert counts(store, d["id"]) == (1, 1)


def test_api_success_then_restore_404_and_conflict(data):
    store, d, _ = data
    client = TestClient(server.app)
    route = f"/api/conversations/{d['id']}"
    assert client.request("DELETE", route, json={"expected_revision": d["revision"] - 1, "confirmed": True}).status_code == 409
    assert client.request("DELETE", route, json={"expected_revision": d["revision"], "confirmed": True}).json()["status"] == "permanently_deleted"
    assert client.post(route + "/restore", json={"revision": d["revision"]}).status_code == 404
    assert client.request("DELETE", route, json={"expected_revision": d["revision"], "confirmed": True}).status_code == 404
