"""Independent final-candidate probes; no provider credentials or user state."""
import json
import sqlite3
from copy import deepcopy

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from src.agent_tasks import TaskDefinition, TaskStore, task_revision
from src.api.task_routes import create_task_router


A, B = "agent_abcdef12", "agent_abcdef34"
INITIAL = {"prompt": "Periodo {{inicio}}", "dates": [
    {"key": "inicio", "label": "Inicio", "value": "2026-10-01"},
    {"key": "fin", "label": "Fin", "value": "2026-10-31"}]}


@pytest.fixture
def isolated(tmp_path):
    directory = tmp_path / "agents"
    directory.mkdir()
    for identity in (A, B):
        (directory / f"{identity}.json").write_text(json.dumps({"id": identity,
            "created_at": "2026-01-01T00:00:00Z", "custom_metadata": {"keep": True},
            "config": {"name": identity, "description": "Retain description", "task": INITIAL,
                "provider_id": "local-fixture", "model_id": "independent", "system_prompt": "Fixed system", "tools": []}}), encoding="utf-8")
    store = TaskStore(tmp_path / "history.sqlite3")
    calls = []

    def generate(provider, model, messages):
        # Inspect persisted attempt inside inference, then change its future draft.
        pending = TaskStore(store.database_path).runs(A, 50)[0]
        assert pending["status"] == "running" and pending["completed_at"] is None
        calls.append((provider, model, messages, pending))
        return "<img src=x onerror=alert(1)>"

    def load(identity):
        if identity not in (A, B):
            raise HTTPException(status_code=404)

    app = FastAPI()
    app.include_router(create_task_router(agents_dir=lambda: directory, load_agent=load,
        workspace_root=lambda: tmp_path, generate=generate, store=store))
    return TestClient(app), store, directory, calls


def revision(client, identity=A):
    return client.get(f"/api/agents/{identity}/task").json()["revision"]


def dispatch(client, **fields):
    return client.post(f"/api/agents/{A}/task-runs", json={
        "expected_revision": revision(client), "confirmed": True, **fields})


def test_independent_dates_durable_relaunch_and_immutable_history(isolated):
    client, store, directory, calls = isolated
    profile_before = json.loads((directory / f"{A}.json").read_text(encoding="utf-8"))
    first = dispatch(client).json()
    original_bytes = json.dumps(first, sort_keys=True)
    assert calls[0][0:2] == ("local-fixture", "independent")
    assert calls[0][2][1]["content"] == "Periodo 2026-10-01\n\nFechas de la tarea:\n- Fin (fin): 2026-10-31"
    assert "file-write" in calls[0][2][0]["content"]
    updated = deepcopy(INITIAL)
    updated["dates"][0]["value"], updated["dates"][1]["value"] = "2027-02-01", "2027-02-28"
    old_revision = revision(client)
    saved = client.put(f"/api/agents/{A}/task", json={"task": updated, "expected_revision": old_revision})
    assert saved.status_code == 200 and len(calls) == 1
    profile_after = json.loads((directory / f"{A}.json").read_text(encoding="utf-8"))
    profile_after["config"]["task"] = INITIAL
    assert profile_after == profile_before
    second = dispatch(client, source_run_id=first["run_id"]).json()
    assert second["run_id"] != first["run_id"] and second["source_run_id"] == first["run_id"]
    assert "2027-02-01" in calls[1][2][1]["content"] and "2027-02-28" in calls[1][2][1]["content"]
    assert second["task_revision"] == task_revision(updated)
    assert json.dumps(TaskStore(store.database_path).run(A, first["run_id"]), sort_keys=True) == original_bytes
    assert first["created_at"] <= first["completed_at"] and second["created_at"] <= second["completed_at"]
    assert client.post(f"/api/agents/{B}/task-runs", json={"expected_revision": revision(client, B), "confirmed": True, "source_run_id": first["run_id"]}).status_code == 404
    assert len(calls) == 2
    for method in ("PUT", "PATCH", "DELETE"):
        assert client.request(method, f"/api/agents/{A}/task-runs/{first['run_id']}", json={"completed_at": "changed"}).status_code == 405
    with sqlite3.connect(store.database_path) as db:
        for column in ("run_id", "agent_id", "snapshot", "created_at", "completed_at", "answer", "status"):
            with pytest.raises(sqlite3.IntegrityError):
                db.execute(f"UPDATE task_runs SET {column}=? WHERE run_id=?", ("forged", first["run_id"]))
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("DELETE FROM task_runs WHERE run_id=?", (first["run_id"],))


def test_independent_denials_and_metadata_never_dispatch(isolated):
    client, store, directory, calls = isolated
    client.get(f"/api/agents/{A}/task-runs")
    client.get(f"/api/agents/{B}/task")
    for invalid in (False, 0, 1, "true", None):
        assert dispatch(client, confirmed=invalid).status_code in (403, 422)
    for field in ("created_at", "completed_at", "status", "answer", "task_snapshot", "provider_id", "model_id", "workspace_root"):
        assert dispatch(client, **{field: "client-forged"}).status_code == 422
    assert dispatch(client, expected_revision="0" * 64).status_code == 409
    assert client.put(f"/api/agents/{A}/task", json={"expected_revision": "0" * 64, "task": INITIAL}).status_code == 409
    unknown = {"prompt": "Evalua {{missing}}", "dates": []}
    assert client.put(f"/api/agents/{A}/task", json={"expected_revision": revision(client), "task": unknown}).status_code == 200
    assert dispatch(client).status_code == 422
    assert calls == [] and store.runs(A, 50) == []


def test_independent_atomic_edit_survives_inflight_snapshot(tmp_path):
    directory = tmp_path / "agents"
    directory.mkdir()
    (directory / f"{A}.json").write_text(json.dumps({"id": A, "config": {"task": INITIAL,
        "provider_id": "fixture", "model_id": "fixture", "system_prompt": "Fixed"}}), encoding="utf-8")
    store = TaskStore(tmp_path / "history.sqlite3")
    original = store.start(directory, A, task_revision(INITIAL), str(tmp_path), None)
    after = {"prompt": "Future {{fin}}", "dates": [{"key": "fin", "label": "Fin", "value": "2028-02-29"}]}
    store.save_task(directory, A, TaskDefinition.model_validate(after), task_revision(INITIAL))
    assert TaskStore(store.database_path).run(A, original["run_id"])["task_snapshot"] == INITIAL
    finalized = store.finish(A, original["run_id"], answer="Old snapshot")
    assert finalized["task_snapshot"] == INITIAL
    assert store.task(directory, A)["task"] == after
    with pytest.raises(Exception) as caught:
        store.finish(A, original["run_id"], answer="Forged second completion")
    assert caught.value.code == "task_run_finalized"
    assert store.run(A, original["run_id"]) == finalized
