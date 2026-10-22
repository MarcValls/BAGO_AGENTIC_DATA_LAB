"""Isolated saved-task contracts; no live provider or user records are touched."""
import json
import sqlite3
from pathlib import Path

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from src.agent_tasks import TaskDefinition, TaskStore, render_task, task_revision
from src.api.task_routes import create_task_router, default_history_path


AGENT = "agent_12345678"
OTHER = "agent_87654321"
TASK = {"prompt": "Revisa desde {{desde}}", "dates": [
    {"key": "desde", "label": "Desde", "value": "2026-10-20"},
    {"key": "hasta", "label": "Hasta", "value": "2026-10-24"}]}


@pytest.fixture
def fixture(tmp_path):
    directory = tmp_path / "agents"
    directory.mkdir()
    records = {}
    for agent_id in (AGENT, OTHER):
        record = {"id": agent_id, "created_at": "2020-01-01T00:00:00Z", "config": {
            "name": "Fixture", "description": "Existing description", "type": "rag", "system_prompt": "Be precise.",
            "provider_id": "codex", "model_id": "test-model", "tools": [], "task": TASK}}
        path = directory / f"{agent_id}.json"
        path.write_text(json.dumps(record), encoding="utf-8")
        records[agent_id] = record
    calls = []
    store = TaskStore(tmp_path / "tasks.sqlite3")

    def load(agent_id):
        if agent_id not in records:
            raise HTTPException(status_code=404)
        return records[agent_id]

    def generate(provider, model, messages):
        calls.append((provider, model, messages))
        return "Respuesta de prueba"

    app = FastAPI()
    app.include_router(create_task_router(agents_dir=lambda: directory, load_agent=load,
        workspace_root=lambda: tmp_path / "workspace", generate=lambda *args: generate(*args), store=store))
    return {"client": TestClient(app), "store": store, "calls": calls, "directory": directory,
        "records": records, "app": app, "root": tmp_path}


def task(client, agent_id=AGENT):
    return client.get(f"/api/agents/{agent_id}/task").json()


def invoke(client, **extra):
    return client.post(f"/api/agents/{AGENT}/task-runs", json={
        "expected_revision": task(client)["revision"], "confirmed": True, **extra})


def test_metadata_and_save_are_no_inference_and_preserve_profile(fixture):
    client, calls = fixture["client"], fixture["calls"]
    before = json.loads((fixture["directory"] / f"{AGENT}.json").read_text())
    state = task(client)
    changed = {**TASK, "prompt": "Otro trabajo"}
    saved = client.put(f"/api/agents/{AGENT}/task", json={"task": changed, "expected_revision": state["revision"]})
    assert saved.status_code == 200
    assert saved.json()["revision"] != state["revision"]
    after = json.loads((fixture["directory"] / f"{AGENT}.json").read_text())
    after["config"]["task"] = before["config"]["task"]
    assert after == before
    assert client.get(f"/api/agents/{AGENT}/task-runs").json() == {"runs": [], "count": 0}
    assert not calls
    assert TaskStore(fixture["store"].database_path).task(fixture["directory"], AGENT)["task"] == changed


def test_stale_save_and_run_are_rejected_without_calls(fixture):
    client = fixture["client"]
    stale = "0" * 64
    assert client.put(f"/api/agents/{AGENT}/task", json={"task": TASK, "expected_revision": stale}).status_code == 409
    assert invoke(client, expected_revision=stale).status_code == 409
    assert not fixture["calls"]


@pytest.mark.parametrize("confirmed,status", [(False, 403), ("true", 422), (1, 422)])
def test_explicit_literal_confirmation_required(fixture, confirmed, status):
    assert invoke(fixture["client"], confirmed=confirmed).status_code == status
    assert not fixture["calls"]


def test_actual_provider_input_and_durable_snapshot(fixture):
    client = fixture["client"]
    response = invoke(client)
    assert response.status_code == 200
    run = response.json()
    assert run["status"] == "answered" and run["answer"] == "Respuesta de prueba"
    assert run["created_at"].endswith("+00:00") and run["completed_at"].endswith("+00:00")
    provider, model, messages = fixture["calls"][0]
    assert (provider, model) == ("codex", "test-model")
    assert messages[1]["content"] == "Revisa desde 2026-10-20\n\nFechas de la tarea:\n- Hasta (hasta): 2026-10-24"
    assert "no" in messages[0]["content"] and "command-execution" in messages[0]["content"]
    assert run["task_snapshot"] == TASK
    reopened = TaskStore(fixture["store"].database_path)
    assert reopened.run(AGENT, run["run_id"]) == run
    with sqlite3.connect(fixture["store"].database_path) as db:
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("UPDATE task_runs SET snapshot='{}' WHERE run_id=?", (run["run_id"],))
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("UPDATE task_runs SET completed_at='fake' WHERE run_id=?", (run["run_id"],))


def test_edit_and_relaunch_do_not_change_historical_dates(fixture):
    client = fixture["client"]
    first = invoke(client).json()
    changed = json.loads(json.dumps(TASK))
    changed["dates"][0]["value"] = "2027-01-02"
    client.put(f"/api/agents/{AGENT}/task", json={"task": changed, "expected_revision": task(client)["revision"]})
    assert len(fixture["calls"]) == 1
    second = invoke(client, source_run_id=first["run_id"]).json()
    assert second["run_id"] != first["run_id"]
    assert second["source_run_id"] == first["run_id"]
    assert second["task_snapshot"]["dates"][0]["value"] == "2027-01-02"
    assert client.get(f"/api/agents/{AGENT}/task-runs/{first['run_id']}").json() == first
    assert client.get(f"/api/agents/{AGENT}/task-runs").json()["runs"] == [second, first]
    for method in ("put", "patch", "delete"):
        assert getattr(client, method)(f"/api/agents/{AGENT}/task-runs/{first['run_id']}").status_code == 405


def test_run_ownership_and_client_history_fields(fixture):
    client = fixture["client"]
    first = invoke(client).json()
    assert client.get(f"/api/agents/{OTHER}/task-runs/{first['run_id']}").status_code == 404
    assert client.post(f"/api/agents/{OTHER}/task-runs", json={"expected_revision": task(client, OTHER)["revision"],
        "confirmed": True, "source_run_id": first["run_id"]}).status_code == 404
    for field in ("status", "created_at", "completed_at", "task_snapshot", "answer"):
        assert invoke(client, **{field: "fake"}).status_code == 422
    assert len(fixture["calls"]) == 1


@pytest.mark.parametrize("changes", [
    {"prompt": " "}, {"dates": [{"key": "a", "label": "A", "value": "2026-02-30"}]},
    {"dates": [{"key": "A", "label": "A", "value": "2026-01-01"}]},
    {"dates": [{"key": "a", "label": "A", "value": "2026-1-1"}]},
    {"dates": [{"key": "a", "label": "A", "value": "2026-01-01"}] * 2},
    {"dates": [{"key": f"d{i}", "label": "A", "value": "2026-01-01"} for i in range(9)]},
])
def test_task_validation(changes):
    with pytest.raises(ValidationError):
        TaskDefinition.model_validate({**TASK, **changes})


def test_unknown_reference_prevents_dispatch_and_history(fixture):
    client = fixture["client"]
    client.put(f"/api/agents/{AGENT}/task", json={"task": {"prompt": "Desde {{missing}}", "dates": []}, "expected_revision": task(client)["revision"]})
    assert invoke(client).status_code == 422
    assert not fixture["calls"]
    assert fixture["store"].runs(AGENT, 50) == []


def test_provider_failure_persists_safe_error_after_durable_start(fixture):
    store = fixture["store"]
    def failing(provider, model, messages):
        assert store.runs(AGENT, 50)[0]["status"] == "running"
        raise RuntimeError("Bearer super-secret-token")
    app = FastAPI()
    app.include_router(create_task_router(agents_dir=lambda: fixture["directory"], load_agent=lambda _: None,
        workspace_root=lambda: fixture["root"], generate=failing, store=store))
    run = invoke(TestClient(app)).json()
    assert run["status"] == "failed" and run["answer"] is None and run["completed_at"]
    assert "super-secret" not in json.dumps(run)
    assert "super-secret" not in fixture["store"].database_path.read_bytes().decode(errors="ignore")


def test_inflight_snapshot_survives_concurrent_task_edit(fixture):
    store = fixture["store"]
    def editing(provider, model, messages):
        store.save_task(fixture["directory"], AGENT, TaskDefinition(prompt="Next", dates=[]), task_revision(TASK))
        return "Old task answered"
    app = FastAPI()
    app.include_router(create_task_router(agents_dir=lambda: fixture["directory"], load_agent=lambda _: None,
        workspace_root=lambda: fixture["root"], generate=editing, store=store))
    run = invoke(TestClient(app)).json()
    assert run["task_snapshot"] == TASK
    assert store.task(fixture["directory"], AGENT)["task"]["prompt"] == "Next"


def test_server_creates_default_task_preserves_legacy_and_profile_updates(monkeypatch, tmp_path):
    from src.api import server
    directory = tmp_path / "agents"
    directory.mkdir()
    monkeypatch.setattr(server, "AGENTS_DIR", directory)
    monkeypatch.setenv("BAGO_TASK_HISTORY_PATH", str(tmp_path / "history.sqlite3"))
    monkeypatch.setattr(server.provider_runtime, "status", lambda _: {"state": "ready", "model_id": "test-model"})
    client = TestClient(server.app)
    config = {"name": "Test", "description": "Do this task", "type": "rag", "system_prompt": "Be precise", "tools": []}
    response = client.post("/api/agents/create", json=config)
    assert response.status_code == 200
    created = response.json()
    agent_id = created["id"]
    assert created["config"]["task"] == {"prompt": config["description"], "dates": []}
    loaded = task(client, agent_id)
    assert client.put(f"/api/agents/{agent_id}/task", json={"task": TASK, "expected_revision": loaded["revision"]}).status_code == 200
    updated = client.put(f"/api/agents/{agent_id}", json={**config, "name": "Renamed"})
    assert updated.status_code == 200 and updated.json()["config"]["task"] == TASK
    exported = client.get("/api/agents/export").json()["agents"][0]
    assert exported["config"]["task"] == TASK and exported["created_at"] == created["created_at"]
    path = directory / f"{agent_id}.json"
    legacy = json.loads(path.read_text())
    legacy["config"].pop("task")
    path.write_text(json.dumps(legacy), encoding="utf-8")
    before = path.read_bytes()
    assert task(client, agent_id)["task"] is None
    assert client.get(f"/api/agents/{agent_id}").status_code == 200
    assert path.read_bytes() == before
    assert client.post(f"/api/agents/{agent_id}/task-runs", json={"expected_revision": task_revision(None), "confirmed": True}).status_code == 409


def test_default_history_is_namespaced_by_agent_record_directory(monkeypatch, tmp_path):
    monkeypatch.delenv("BAGO_TASK_HISTORY_PATH", raising=False)
    first = default_history_path(tmp_path / "checkout-one" / "agents")
    second = default_history_path(tmp_path / "checkout-two" / "agents")
    assert first != second
    assert first == default_history_path(tmp_path / "checkout-one" / "agents")
    monkeypatch.setenv("BAGO_TASK_HISTORY_PATH", str(tmp_path / "explicit.sqlite3"))
    assert default_history_path(tmp_path / "anything") == tmp_path / "explicit.sqlite3"
