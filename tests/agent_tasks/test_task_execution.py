from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
import subprocess
import sys
import threading

import pytest

from src.agent_tasks.store import TaskError, TaskStore
from src.agent_tasks.task_execution import (
    AgentSelection, ModelSelection, PlanAcceptInput, PlanPrepareInput,
    PlanEditInput, TaskExecutionAdapters, TaskExecutionService,
    build_host_task_execution_adapters, digest,
)
from src.project_permissions import ProjectContext, ProjectPermissions


PROJECT = {"project_id": "p1", "root": "C:/project", "binding": "C:/project",
    "revision": "a" * 64, "read_directories": ["."], "write_directories": ["."]}
AGENT_ID = "agent_12345678"
PROFILE_SHA = hashlib.sha256(b"agent-profile").hexdigest()
REVIEWER_ID = "agent_87654321"
REVIEWER_SHA = hashlib.sha256(b"reviewer-profile").hexdigest()


def make_service(tmp_path, *, steps=None, project=None, prepare_step=None, execute_step=None, review_plan=None):
    calls = {"probe": 0, "generate": 0, "execute": 0, "select": 0}
    current_project = dict(project or PROJECT)
    proposed = steps or [{"step_id": "s1", "type": "filesystem", "operation": "write",
        "arguments": {"target": "out.txt", "content": "done"}, "depends_on": []}]

    def select_agent(selection, task_text, model_selection):
        calls["select"] += 1
        calls["selected_model"] = (model_selection.provider_id, model_selection.model_id)
        return {"agent_id": AGENT_ID, "profile_sha256": PROFILE_SHA, "task_scope": "bounded file task",
            "tools": ["filesystem_plan"], "type": "tool", "created_for_task": selection.mode == "auto"}

    def probe(provider, model):
        calls["probe"] += 1
        return {"status": "PASS", "generation_sha256": hashlib.sha256(b"actual operation-local generation").hexdigest()}

    def generate(provider, model, messages):
        calls["generate"] += 1
        return json.dumps({"steps": proposed})

    def compile_step(step, context):
        if prepare_step:
            return prepare_step(step, context)
        return {**step, "status": "READY", "prepared_ref": "local-prepared", "prepared_sha256": "b" * 64,
            "expected_inputs": [], "expected_outputs": [], "required_scopes": [{"kind": "write", "path": "."}],
            "granted_scopes": [{"kind": "write", "path": "."}], "required_checks": []}

    def execute(step, context):
        calls["execute"] += 1
        if execute_step:
            return execute_step(step, context)
        return {"status": "PASS", "effect_executed": True, "receipt_id": "receipt-1"}

    adapters = TaskExecutionAdapters(
        project_snapshot=lambda: dict(current_project),
        current_agent=lambda agent_id: {"agent_id": AGENT_ID, "profile_sha256": PROFILE_SHA},
        select_agent=select_agent,
        model_catalog=lambda: {"models": [{"provider_id": "codex", "model_id": "gpt-test", "state": "configured_unverified",
            "orchestrator_enabled": True, "agent_types": ["tool"]}]},
        model_eligible=lambda provider, model, role: True,
        probe_model=probe,
        generate_plan=generate,
        prepare_step=compile_step,
        review_plan=review_plan or (lambda plan, context: {"status": "approved", "reviewer_id": REVIEWER_ID,
            "reviewer_sha256": REVIEWER_SHA, "receipt": {"review_id": "review-1"}}),
        validate_step=lambda step, context: None,
        execute_step=execute,
    )
    service = TaskExecutionService(TaskStore(tmp_path / "tasks.sqlite3"), adapters)
    request = PlanPrepareInput.model_validate({
        "request_id": "7aa022ef-4132-458d-8d9b-58e4b3638cee", "task_text": "Create one bounded output file",
        "expected_project_id": "p1", "expected_binding": "C:/project", "expected_permissions_revision": "a" * 64,
        "model_selection": {"mode": "auto"}, "agent_selection": {"mode": "auto"},
    })
    return service, request, calls, current_project


def test_preparation_is_durable_and_duplicate_request_does_not_call_provider_again(tmp_path):
    service, request, calls, _ = make_service(tmp_path)
    prepared = service.prepare(request)
    assert prepared["status"] == "AWAITING_ACCEPTANCE"
    assert prepared["execution_id"].startswith("taskexec_")
    assert service.get(prepared["execution_id"])["plan"]["review"]["status"] == "approved"
    repeated = service.prepare(request)
    assert repeated["execution_id"] == prepared["execution_id"]
    assert calls == {"probe": 1, "generate": 1, "execute": 0, "select": 1, "selected_model": (None, None)}


def test_explicit_model_selection_is_passed_to_agent_selection_callback(tmp_path):
    service, request, calls, _ = make_service(tmp_path)
    request = request.model_copy(update={"model_selection": ModelSelection(
        mode="explicit", provider_id="codex", model_id="gpt-test")})

    prepared = service.prepare(request)

    assert prepared["status"] == "AWAITING_ACCEPTANCE"
    assert calls["selected_model"] == ("codex", "gpt-test")


def test_original_task_objective_is_hashed_and_reaches_prepare_and_independent_review(tmp_path):
    objective = "Inspect the CSV and produce a scoped summary without editing source files."
    observations = {"prepare": [], "review": []}

    def prepare_step(step, context):
        observations["prepare"].append(context.get("task_text"))
        return {**step, "status": "READY", "prepared_ref": "objective-bound-plan",
            "prepared_sha256": "b" * 64, "expected_inputs": [], "expected_outputs": [],
            "required_scopes": [{"kind": "write", "path": "."}],
            "granted_scopes": [{"kind": "write", "path": "."}], "required_checks": []}

    def review_plan(plan, context):
        observations["review"].append({"plan": plan.get("task_text"), "context": context.get("task_text")})
        return {"status": "approved", "reviewer_id": REVIEWER_ID,
            "reviewer_sha256": REVIEWER_SHA, "receipt": {"review_id": "objective-review"}}

    service, request, _, _ = make_service(tmp_path, prepare_step=prepare_step, review_plan=review_plan)
    request = request.model_copy(update={"task_text": objective})
    prepared = service.prepare(request)

    assert prepared["plan"]["task_text"] == objective
    assert prepared["plan_sha256"] == digest(prepared["plan"])
    assert observations["prepare"] == [objective]
    assert observations["review"] == [{"plan": objective, "context": objective}]

    revised = service.revise(prepared["plan_id"], PlanEditInput(
        expected_plan_sha256=prepared["plan_sha256"], steps=[{
            "step_id": "s1", "type": "filesystem", "operation": "write",
            "arguments": {"target": "out.txt", "content": "done"}, "depends_on": []}]))
    assert revised["plan"]["task_text"] == objective
    assert revised["plan_sha256"] == digest(revised["plan"])
    assert observations["prepare"] == [objective, objective]
    assert observations["review"][-1] == {"plan": objective, "context": objective}


def test_rejected_plan_review_is_durable_diagnostic_only_and_never_accepted(tmp_path):
    proposed = [{"step_id": "inventory", "type": "filesystem", "operation": "inventory",
        "arguments": {"path": "demo-usuario"}, "depends_on": []}]
    reviewed = {}
    raw_secret = "sk-review-secret-1234567890"
    short_secrets = ("tiny-password", "short-key")

    def reject(plan, context):
        reviewed["plan"] = plan
        return {"status": "rejected", "reviewer_id": REVIEWER_ID, "reviewer_sha256": REVIEWER_SHA,
            "reason": f'Rejected because api_key={raw_secret}; Bearer abcdefghijklmnopqrstuvwxyz0123456789; JSON {{"password":"{short_secrets[0]}", \'api_key\': \'{short_secrets[1]}\'}}',
            "receipt": {"plan_sha256": digest(plan), "provider_id": "codex", "model_id": "gpt-test",
                "reviewer_id": REVIEWER_ID, "reviewer_sha256": REVIEWER_SHA, "reason": raw_secret}}

    service, request, calls, _ = make_service(tmp_path, steps=proposed, review_plan=reject)
    reserved_ids = []
    original_reserve = service.store.reserve_execution

    def capture_reservation(**kwargs):
        reserved, created = original_reserve(**kwargs)
        reserved_ids.append(reserved["execution_id"])
        return reserved, created

    service.store.reserve_execution = capture_reservation
    with pytest.raises(TaskError, match="no lo aprobó"):
        service.prepare(request)
    result = service.get(reserved_ids[0])

    assert result["status"] == "FAILED_NO_EFFECT"
    assert result["plan_status"] == "FAILED_NO_EFFECT"
    assert result["plan"] is None
    assert result["step_results"] == {}
    assert calls["execute"] == 0
    events = result["events"]
    rejection = next(event["payload"] for event in events if event["event_type"] == "PLAN_REVIEW_NON_APPROVED")
    assert rejection["status"] == "rejected"
    assert rejection["plan_sha256"] == digest(reviewed["plan"])
    assert rejection["plan_summary"]["steps"] == [{
        "step_id": "inventory", "type": "filesystem", "operation": "inventory",
        "argument_keys": ["path"], "depends_on": [], "status": "READY", "reason_code": None,
        "prepared_sha256": "b" * 64, "required_checks": [], "expected_input_count": 0,
        "expected_output_count": 0,
    }]
    assert "scopes" not in rejection["plan_summary"]
    assert "arguments" not in json.dumps(rejection)
    assert raw_secret not in json.dumps(rejection)
    assert "abcdefghijklmnopqrstuvwxyz0123456789" not in json.dumps(rejection)
    assert all(secret not in json.dumps(rejection) for secret in short_secrets)
    assert "api_key=[REDACTED]" in rejection["review"]["reason"]
    assert rejection["review"]["reviewer_id"] == REVIEWER_ID
    assert rejection["review"]["reviewer_sha256"] == REVIEWER_SHA
    assert any(event["event_type"] == "PREPARATION_FAILED" for event in events)
    with pytest.raises(TaskError):
        service.accept(result["plan_id"], PlanAcceptInput(expected_plan_sha256=result["plan_sha256"],
            expected_plan_revision=1, idempotency_key="56a4813e-30c2-48a4-a139-91ca11d18bf9", confirmed=True))
    assert calls["execute"] == 0


def test_rejected_plan_review_is_retained_but_stop_remains_terminal(tmp_path):
    reserved_ids = []
    service = None

    def reject_after_stop(plan, context):
        service.store.request_execution_stop(reserved_ids[0], "test_stop")
        return {"status": "rejected", "reviewer_id": REVIEWER_ID, "reviewer_sha256": REVIEWER_SHA,
            "reason": "Rejected plan after STOP", "receipt": {"plan_sha256": digest(plan)}}

    service, request, calls, _ = make_service(tmp_path, review_plan=reject_after_stop)
    original_reserve = service.store.reserve_execution

    def capture_reservation(**kwargs):
        reserved, created = original_reserve(**kwargs)
        reserved_ids.append(reserved["execution_id"])
        return reserved, created

    service.store.reserve_execution = capture_reservation
    with pytest.raises(TaskError):
        service.prepare(request)
    result = service.get(reserved_ids[0])

    assert result["status"] == "STOPPED_BEFORE_EFFECT"
    assert result["plan_status"] == "STOPPED_BEFORE_EFFECT"
    assert result["plan"] is None
    assert result["step_results"] == {}
    assert calls["execute"] == 0
    events = service.store.list_execution_events(reserved_ids[0])
    assert any(event["event_type"] == "PLAN_REVIEW_NON_APPROVED" for event in events)
    assert any(event["event_type"] == "PREPARATION_STOPPED_AFTER_ACTION" for event in events)


def test_real_host_inventory_returns_native_result_with_exact_read_subdirectory_scope(tmp_path, monkeypatch):
    project_root = tmp_path / "project"
    demo = project_root / "demo-usuario"
    demo.mkdir(parents=True)
    (demo / "sample.txt").write_text("inventory fixture", encoding="utf-8")
    (project_root / "outside.txt").write_text("not inventoried", encoding="utf-8")
    (project_root / ".bago" / "state").mkdir(parents=True)
    binding = json.dumps({"project_id": "inventory-project", "root": str(project_root)},
        sort_keys=True, separators=(",", ":"))
    context = ProjectContext("inventory-project", project_root, binding, "Temporary inventory test")
    permissions = ProjectPermissions(lambda: context)
    initial = permissions.snapshot()
    permissions.save(expected_project_id="inventory-project", expected_binding=binding,
        expected_revision=initial["revision"], read_directories=["demo-usuario"],
        write_directories=[], confirmed=True)
    snapshot = permissions.snapshot()
    author = "agent_12345678"
    reviewer = "agent_87654321"
    profile_sha = hashlib.sha256(b"inventory-profile").hexdigest()
    reviewer_sha = hashlib.sha256(b"inventory-reviewer").hexdigest()
    review_observed = {}
    native_reads = []
    from src.agent_tools.agent_services import AgentServiceSession
    original_invoke = AgentServiceSession.invoke

    def record_native_inventory(session, name, args, assigned):
        result, native = original_invoke(session, name, args, assigned)
        if name == "filesystem_inventory":
            native_reads.append(result)
        return result, native

    monkeypatch.setattr(AgentServiceSession, "invoke", record_native_inventory)

    def generate(provider, model, messages):
        return json.dumps({"steps": [{"step_id": "inventory-subdir", "type": "filesystem",
            "operation": "inventory", "arguments": {"path": "demo-usuario"}, "depends_on": []}]})

    def review(plan, review_context):
        review_observed["plan"] = plan
        return {"status": "approved", "reviewer_id": reviewer, "reviewer_sha256": reviewer_sha,
            "receipt": {"plan_sha256": digest(plan)}}

    adapters = build_host_task_execution_adapters(
        project_snapshot=permissions.snapshot,
        current_agent=lambda agent_id: {"agent_id": author, "profile_sha256": profile_sha,
            "type": "tool", "tools": ["filesystem_inventory"]},
        select_agent=lambda selection, task_text, model_selection: {"agent_id": author,
            "profile_sha256": profile_sha, "type": "tool", "tools": ["filesystem_inventory"],
            "task_scope": "Inventory names and hashes under demo-usuario.", "created_for_task": True},
        model_catalog=lambda: {"models": [{"provider_id": "codex", "model_id": "inventory-test",
            "state": "ready", "orchestrator_enabled": True, "agent_types": ["tool"]}]},
        model_eligible=lambda provider, model, role: True,
        probe_model=lambda provider, model: {"status": "PASS",
            "generation_sha256": hashlib.sha256(b"probe").hexdigest()},
        generate_plan=generate,
        review_plan=review,
        workspace_root=lambda: tmp_path,
        project_permissions=lambda: permissions,
        development_service=lambda: None,
        development_reviewer=lambda change, review_context: {"status": "approved", "reviewer_id": reviewer,
            "reviewer_sha256": reviewer_sha, "receipt": {"review_id": "not-used"}},
    )
    service = TaskExecutionService(TaskStore(tmp_path / "task-state" / "tasks.sqlite3"), adapters)
    request = PlanPrepareInput.model_validate({"request_id": "7aa022ef-4132-458d-8d9b-58e4b3638cee",
        "task_text": "Inventory demo-usuario without reading file text or changing files.",
        "expected_project_id": snapshot["project_id"], "expected_binding": snapshot["binding"],
        "expected_permissions_revision": snapshot["revision"], "model_selection": {"mode": "explicit",
            "provider_id": "codex", "model_id": "inventory-test"}, "agent_selection": {"mode": "auto"}})

    prepared = service.prepare(request)

    assert prepared["status"] == "AWAITING_ACCEPTANCE"
    step = prepared["plan"]["steps"][0]
    expected_scope = [{"kind": "read", "path": "demo-usuario"}]
    assert step["required_scopes"] == expected_scope
    assert step["granted_scopes"] == expected_scope
    assert permissions.snapshot()["read_directories"] == ["demo-usuario"]
    assert permissions.snapshot()["write_directories"] == []
    accepted = service.accept(prepared["plan_id"], PlanAcceptInput(
        expected_plan_sha256=prepared["plan_sha256"], expected_plan_revision=1,
        idempotency_key="b3262bc4-b8fb-4e99-91e7-3a33653e8e10", confirmed=True))
    assert accepted["status"] == "SUCCEEDED"
    receipt = accepted["step_results"]["inventory-subdir"]["receipt"]
    assert receipt["operation"] == "inventory"
    assert receipt["effect_executed"] is False
    assert re.fullmatch(r"[a-f0-9]{64}", receipt["inventory_sha256"])
    assert receipt["inventory"] == native_reads[-1]
    assert len(native_reads) == 2  # One existing preparation read and one accepted execution read.
    inventory = receipt["inventory"]
    assert inventory["root"] == str(project_root)
    assert inventory["recursive"] is False
    assert len(inventory["entries"]) == 1
    entry = inventory["entries"][0]
    assert {key: entry[key] for key in ("path", "kind")} == {"path": "demo-usuario/sample.txt", "kind": "file"}
    snapshot = entry["snapshot"]
    assert set(snapshot) == {"sha256", "size", "mtime_ns", "inode"}
    assert snapshot["sha256"] == hashlib.sha256(b"inventory fixture").hexdigest()
    assert snapshot["size"] == len(b"inventory fixture")
    assert type(snapshot["mtime_ns"]) is int
    assert type(snapshot["inode"]) is int
    assert receipt["inventory_sha256"] == digest(inventory)
    assert "inventory fixture" not in json.dumps(inventory)
    assert review_observed["plan"]["scopes"] == {"requested": expected_scope, "granted": expected_scope}
    assert permissions.snapshot()["read_directories"] == ["demo-usuario"]
    assert permissions.snapshot()["write_directories"] == []

    stopped_request = request.model_copy(update={"request_id": "00000000-0000-4000-8000-000000000003"})
    stopped_plan = service.prepare(stopped_request)
    stopped = service.stop(stopped_plan["execution_id"], "user_stop")
    assert stopped["status"] == "STOPPED_BEFORE_EFFECT"
    assert stopped["step_results"] == {}
    assert len(native_reads) == 3  # STOP prevents the second, accepted-execution read.
    with pytest.raises(TaskError):
        service.accept(stopped_plan["plan_id"], PlanAcceptInput(expected_plan_sha256=stopped_plan["plan_sha256"],
            expected_plan_revision=1, idempotency_key="b3262bc4-b8fb-4e99-91e7-3a33653e8e11", confirmed=True))
    assert len(native_reads) == 3


def test_single_acceptance_executes_once_and_idempotent_replay_returns_saved_receipt(tmp_path):
    service, request, calls, _ = make_service(tmp_path)
    prepared = service.prepare(request)
    accept = PlanAcceptInput(expected_plan_sha256=prepared["plan_sha256"], expected_plan_revision=1,
        idempotency_key="56a4813e-30c2-48a4-a139-91ca11d18bf9", confirmed=True)
    done = service.accept(prepared["plan_id"], accept)
    replay = service.accept(prepared["plan_id"], accept)
    assert done["status"] == "SUCCEEDED"
    assert done["step_results"]["s1"]["receipt"]["receipt_id"] == "receipt-1"
    assert replay["idempotent_replay"] is True
    assert calls["execute"] == 1


def test_changed_request_body_with_same_request_id_is_rejected(tmp_path):
    service, request, _, _ = make_service(tmp_path)
    service.prepare(request)
    changed = request.model_copy(update={"task_text": "Different operation"})
    with pytest.raises(TaskError, match="request_id"):
        service.prepare(changed)


def test_auto_model_candidates_preserve_host_catalog_order_within_readiness_tier(tmp_path):
    service, _, _, _ = make_service(tmp_path)
    service.adapters.model_catalog = lambda: {"models": [
        {"provider_id": "codex", "model_id": "configured-default", "state": "configured_unverified",
            "orchestrator_enabled": True, "agent_types": ["tool"]},
        {"provider_id": "codex", "model_id": "alphabetically-first-but-not-default", "state": "configured_unverified",
            "orchestrator_enabled": True, "agent_types": ["tool"]},
    ]}
    candidates = service._model_candidates(ModelSelection(mode="auto"), "tool")
    assert [item["model_id"] for item in candidates] == ["configured-default", "alphabetically-first-but-not-default"]


def test_same_acceptance_key_cannot_bind_another_plan(tmp_path):
    service, request, _, _ = make_service(tmp_path)
    first = service.prepare(request)
    accepted = PlanAcceptInput(expected_plan_sha256=first["plan_sha256"], expected_plan_revision=1,
        idempotency_key="56a4813e-30c2-48a4-a139-91ca11d18bf9", confirmed=True)
    service.accept(first["plan_id"], accepted)
    second_request = request.model_copy(update={"request_id": "00000000-0000-4000-8000-000000000001"})
    second = service.prepare(second_request)
    reused = PlanAcceptInput(expected_plan_sha256=second["plan_sha256"], expected_plan_revision=1,
        idempotency_key=accepted.idempotency_key, confirmed=True)
    with pytest.raises(TaskError, match="clave"):
        service.accept(second["plan_id"], reused)


def test_project_or_profile_revision_drift_stops_before_dispatch(tmp_path):
    service, request, calls, current_project = make_service(tmp_path)
    prepared = service.prepare(request)
    current_project["revision"] = "c" * 64
    accept = PlanAcceptInput(expected_plan_sha256=prepared["plan_sha256"], expected_plan_revision=1,
        idempotency_key="56a4813e-30c2-48a4-a139-91ca11d18bf9", confirmed=True)
    result = service.accept(prepared["plan_id"], accept)
    assert result["status"] == "STALE"
    assert calls["execute"] == 0


def test_stop_before_accept_and_invalid_model_probe_cannot_execute(tmp_path):
    service, request, calls, _ = make_service(tmp_path)
    prepared = service.prepare(request)
    stopped = service.stop(prepared["execution_id"], "user_stop")
    assert stopped["status"] == "STOPPED_BEFORE_EFFECT"
    accept = PlanAcceptInput(expected_plan_sha256=prepared["plan_sha256"], expected_plan_revision=1,
        idempotency_key="56a4813e-30c2-48a4-a139-91ca11d18bf9", confirmed=True)
    with pytest.raises(TaskError, match="detuvo"):
        service.accept(prepared["plan_id"], accept)
    assert calls["execute"] == 0


def test_stop_recorded_before_step_admission_wins_atomically(tmp_path):
    service, request, _, _ = make_service(tmp_path)
    prepared = service.prepare(request)
    service.store.set_execution_status(prepared["execution_id"], "RUNNING")
    stopped = service.stop(prepared["execution_id"], "user_stop")
    assert stopped["status"] == "STOP_REQUESTED"
    with pytest.raises(TaskError, match="STOP"):
        service.store.begin_execution_step(prepared["execution_id"], "s1")
    latest = service.store.execution(prepared["execution_id"])
    assert latest["current_step"] is None
    assert latest["stop_requested"] is True


def test_reserved_preparation_exposes_id_and_stop_prevents_agent_or_provider_work(tmp_path):
    service, request, calls, _ = make_service(tmp_path)
    reserved, is_new = service.reserve_preparation(request)
    assert is_new is True
    assert reserved["status"] == "PREPARING" and reserved["plan"] is None
    stopped = service.stop(reserved["execution_id"], "user_stop")
    assert stopped["status"] == "STOPPED_BEFORE_EFFECT"
    result = service.complete_preparation(request, reserved["execution_id"])
    assert result["status"] == "STOPPED_BEFORE_EFFECT"
    assert calls == {"probe": 0, "generate": 0, "execute": 0, "select": 0}


def test_stop_during_inflight_preparation_finalizes_after_callback_returns(tmp_path):
    service, request, calls, _ = make_service(tmp_path)
    entered = threading.Event()
    release = threading.Event()
    worker_result = []
    worker_error = []
    original_generate = service.adapters.generate_plan

    def delayed_generate(provider, model, messages):
        entered.set()
        if not release.wait(timeout=10):
            raise RuntimeError("test release timeout")
        return original_generate(provider, model, messages)

    service.adapters.generate_plan = delayed_generate
    reserved, is_new = service.reserve_preparation(request)
    assert is_new is True

    def run_background():
        try:
            worker_result.append(service.background_prepare(request, reserved["execution_id"]))
        except Exception as error:
            worker_error.append(error)

    worker = threading.Thread(target=run_background, daemon=True)
    worker.start()
    assert entered.wait(timeout=5)
    stopped = service.stop(reserved["execution_id"], "user_stop")
    assert stopped["status"] == "STOP_REQUESTED"
    release.set()
    worker.join(timeout=10)

    assert worker.is_alive() is False
    assert worker_error == []
    assert worker_result[0]["status"] == "STOPPED_BEFORE_EFFECT"
    recovered = service.get(reserved["execution_id"])
    assert recovered["status"] == "STOPPED_BEFORE_EFFECT"
    assert recovered["plan_status"] == "STOPPED_BEFORE_EFFECT"
    assert recovered["plan"] is None
    assert calls["generate"] == 1
    assert calls["execute"] == 0
    after = service.complete_preparation(request, reserved["execution_id"])
    assert after["status"] == "STOPPED_BEFORE_EFFECT"
    assert calls["generate"] == 1


def test_stopped_preparation_with_confirmed_dead_owner_is_terminal(tmp_path, monkeypatch):
    store = TaskStore(tmp_path / "stopped-owner.sqlite3")
    reserved, _ = store.reserve_execution(request_id="7aa022ef-4132-458d-8d9b-58e4b3638cee",
        request_sha256="d" * 64, plan_id="taskplan_" + "d" * 32,
        preparation_owner="42424242:stopped-worker")
    store.begin_preparation_action(reserved["execution_id"], "generate_plan")
    assert store.request_execution_stop(reserved["execution_id"], "user_stop")["status"] == "STOP_REQUESTED"
    monkeypatch.setattr(TaskStore, "_process_is_alive", staticmethod(lambda pid: False))

    assert store.reconcile_orphaned_executions("new-process") == 1
    recovered = store.execution(reserved["execution_id"])
    assert recovered["status"] == "STOPPED_BEFORE_EFFECT"
    assert recovered["plan_status"] == "STOPPED_BEFORE_EFFECT"
    assert recovered["stop_requested"] is True


def test_orphaned_preparation_after_process_restart_is_inconclusive_not_replayed(tmp_path, monkeypatch):
    store = TaskStore(tmp_path / "orphan.sqlite3")
    reserved, created = store.reserve_execution(request_id="7aa022ef-4132-458d-8d9b-58e4b3638cee",
        request_sha256="d" * 64, plan_id="taskplan_" + "a" * 32,
        preparation_owner="42424242:dead-worker")
    assert created is True
    monkeypatch.setattr(TaskStore, "_process_is_alive", staticmethod(lambda pid: False))
    assert store.reconcile_orphaned_executions("new-process") == 1
    recovered = store.execution(reserved["execution_id"])
    assert recovered["status"] == "INCONCLUSIVE"
    assert recovered["plan"] is None


def test_unknown_owner_is_not_treated_as_proof_of_process_exit(tmp_path):
    store = TaskStore(tmp_path / "unknown-owner.sqlite3")
    reserved, _ = store.reserve_execution(request_id="7aa022ef-4132-458d-8d9b-58e4b3638cee",
        request_sha256="d" * 64, plan_id="taskplan_" + "c" * 32, preparation_owner="legacy-unknown")
    assert store.reconcile_orphaned_executions("new-process") == 0
    assert store.execution(reserved["execution_id"])["status"] == "PREPARING"


def test_reconciliation_does_not_mark_another_live_worker_orphaned(tmp_path):
    store = TaskStore(tmp_path / "live-owner.sqlite3")
    reserved, _ = store.reserve_execution(request_id="7aa022ef-4132-458d-8d9b-58e4b3638cee",
        request_sha256="d" * 64, plan_id="taskplan_" + "b" * 32,
        preparation_owner=f"{os.getpid()}:other-worker-token")
    assert store.reconcile_orphaned_preparations(f"{os.getpid()}:this-worker-token") == 0
    assert store.execution(reserved["execution_id"])["status"] == "PREPARING"


def test_windows_process_liveness_uses_query_not_os_kill(monkeypatch):
    if os.name != "nt":
        pytest.skip("Windows signal semantics only")
    monkeypatch.setattr(os, "kill", lambda *args: pytest.fail("os.kill must not be called on Windows"))
    assert TaskStore._process_is_alive(os.getpid()) is True


def test_process_liveness_tracks_an_isolated_child_before_and_after_exit():
    flags = 0
    if os.name == "nt":
        flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
    child = subprocess.Popen([sys.executable, "-B", "-c", "import time; time.sleep(30)"],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=flags)
    try:
        assert TaskStore._process_is_alive(child.pid) is True
    finally:
        child.terminate()
        child.wait(timeout=10)
    assert TaskStore._process_is_alive(child.pid) is False


def _child_crash_after_accept(db_path, plan_id, plan_sha256, idempotency_key, mode, marker):
    code = r'''import os, sys
from pathlib import Path
from src.agent_tasks.store import TaskStore
db_path, plan_id, plan_sha256, idempotency_key, mode, marker = sys.argv[1:]
store = TaskStore(db_path)
record, created = store.accept_execution(plan_id, plan_sha256, 1, idempotency_key,
    dispatch_owner=f"{os.getpid()}:isolated-crash-worker")
if not created:
    os._exit(91)
if mode == "running":
    store.set_execution_status(record["execution_id"], "RUNNING", event="RUNNING")
    store.begin_execution_step(record["execution_id"], "s1")
    Path(marker).write_text("effect already occurred", encoding="utf-8")
os._exit(72 if mode == "accepted" else 73)
'''
    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
    child = subprocess.Popen([sys.executable, "-B", "-c", code, str(db_path), plan_id,
        plan_sha256, idempotency_key, mode, str(marker)], cwd=Path(__file__).resolve().parents[2],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=creationflags)
    return child.pid, child.wait(timeout=15)


@pytest.mark.parametrize(("mode", "expected_exit"), [("accepted", 72), ("running", 73)])
def test_dead_acceptance_or_dispatch_owner_becomes_inconclusive_and_replay_never_executes(
        tmp_path, mode, expected_exit):
    service, request, calls, _ = make_service(tmp_path)
    prepared = service.prepare(request)
    idempotency_key = "56a4813e-30c2-48a4-a139-91ca11d18bf9"
    marker = tmp_path / "out.txt"
    child_pid, exit_code = _child_crash_after_accept(service.store.database_path,
        prepared["plan_id"], prepared["plan_sha256"], idempotency_key, mode, marker)
    assert exit_code == expected_exit
    assert TaskStore._process_is_alive(child_pid) is False
    marker_sha256 = hashlib.sha256(marker.read_bytes()).hexdigest() if marker.exists() else None

    restarted = TaskExecutionService(TaskStore(service.store.database_path), service.adapters)
    recovered = restarted.get(prepared["execution_id"])
    assert recovered["status"] == "INCONCLUSIVE"
    stored = restarted.store.execution(prepared["execution_id"])
    assert stored["recovery"]["previous_status"] == mode.upper()

    replay = restarted.accept(prepared["plan_id"], PlanAcceptInput(
        expected_plan_sha256=prepared["plan_sha256"], expected_plan_revision=1,
        idempotency_key=idempotency_key, confirmed=True))
    assert replay["status"] == "INCONCLUSIVE"
    assert replay["idempotent_replay"] is True
    assert calls["execute"] == 0
    if mode == "accepted":
        assert marker.exists() is False
    else:
        assert marker.read_text(encoding="utf-8") == "effect already occurred"
        assert hashlib.sha256(marker.read_bytes()).hexdigest() == marker_sha256


def test_accept_dispatch_task_error_is_reconciled_and_never_replayed(tmp_path):
    service, request, calls, _ = make_service(tmp_path)
    prepared = service.prepare(request)
    service.adapters.project_snapshot = lambda: (_ for _ in ()).throw(
        TaskError("project_binding_changed", "binding changed", 409))
    accept = PlanAcceptInput(expected_plan_sha256=prepared["plan_sha256"], expected_plan_revision=1,
        idempotency_key="56a4813e-30c2-48a4-a139-91ca11d18bf9", confirmed=True)
    result = service.accept(prepared["plan_id"], accept)
    replay = service.accept(prepared["plan_id"], accept)
    assert result["status"] == "STALE"
    assert replay["status"] == "STALE" and replay["idempotent_replay"] is True
    assert calls["execute"] == 0


def test_revised_development_plan_rejects_its_author_as_reviewer(tmp_path):
    development = [{"step_id": "dev1", "type": "development", "operation": "development_read",
        "arguments": {"path": "src/app.py"}, "depends_on": []}]
    reviewer = {"id": REVIEWER_ID}

    def review(plan, context):
        return {"status": "approved", "reviewer_id": reviewer["id"],
            "reviewer_sha256": REVIEWER_SHA, "receipt": {"review_id": "review-dev"}}

    service, request, _, _ = make_service(tmp_path, steps=development, review_plan=review)
    prepared = service.prepare(request)
    reviewer["id"] = AGENT_ID
    edit = PlanEditInput(expected_plan_sha256=prepared["plan_sha256"], steps=[
        {"step_id": "dev1", "type": "development", "operation": "development_read",
            "arguments": {"path": "src/app.py"}, "depends_on": []}])
    with pytest.raises(TaskError, match="otro revisor"):
        service.revise(prepared["plan_id"], edit)

