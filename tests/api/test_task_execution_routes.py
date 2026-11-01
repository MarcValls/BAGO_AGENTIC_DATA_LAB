from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.agent_tasks.store import TaskError, TaskStore
from src.agent_tasks.task_execution import (PlanAcceptInput, PlanPrepareInput, TaskExecutionAdapters,
    TaskExecutionService, build_host_task_execution_adapters)
from src.agent_tools.agent_services import AgentServiceSession, execute_filesystem, review_filesystem
from src.api.task_execution_routes import create_task_execution_router
from src.project_permissions import ProjectContext, ProjectPermissions


AUTHOR = "agent_12345678"
REVIEWER = "agent_87654321"
PROFILE_SHA = hashlib.sha256(b"saved agent profile bytes").hexdigest()
REVIEWER_SHA = hashlib.sha256(b"reviewer profile bytes").hexdigest()


def _permissions(root: Path, *, read: list[str], write: list[str]) -> ProjectPermissions:
    (root / ".bago" / "state").mkdir(parents=True, exist_ok=True)
    binding = json.dumps({"project_id": "project-test", "root": str(root)}, sort_keys=True, separators=(",", ":"))
    context = ProjectContext("project-test", root, binding, "Temporary scoped project")
    service = ProjectPermissions(lambda: context)
    initial = service.snapshot()
    service.save(expected_project_id="project-test", expected_binding=binding, expected_revision=initial["revision"],
        read_directories=read, write_directories=write, confirmed=True)
    return service


def _covered(scopes: list[str], path: str) -> bool:
    normalized = path or "."
    return any(scope == "." or normalized == scope or normalized.startswith(scope.rstrip("/") + "/") for scope in scopes)


def _adapter_bundle(tmp_path: Path, *, permissions: ProjectPermissions, kind: str, dev_service=None,
    filesystem_target: str = "allowed/result.txt"):
    workspace = tmp_path
    task_state = tmp_path / "task-state"
    task_state.mkdir(exist_ok=True)
    project = permissions.snapshot()
    observed = {"probes": 0, "generations": 0, "executions": 0}
    conversation_id = "task-conversation-0001"

    def snapshot():
        return permissions.snapshot()

    def current_agent(agent_id):
        return {"agent_id": AUTHOR, "profile_sha256": PROFILE_SHA, "type": "tool", "tools": ["filesystem_plan", "development_prepare"]}

    def select_agent(selection, task, model_selection):
        observed["selected_model"] = (model_selection.provider_id, model_selection.model_id)
        return {"agent_id": AUTHOR, "profile_sha256": PROFILE_SHA, "type": "tool", "task_scope": "scoped filesystem and code operations",
            "tools": ["filesystem_plan", "development_prepare"], "created_for_task": selection.mode == "auto"}

    def generate(provider, model, messages):
        observed["generations"] += 1
        if kind == "filesystem":
            steps = [{"step_id": "write-output", "type": "filesystem", "operation": "write",
                "arguments": {"target": filesystem_target, "content": "written by the accepted plan"}, "depends_on": []}]
        else:
            source_path = tmp_path / "src" / "sample.py"
            old = source_path.read_bytes()
            steps = [{"step_id": "patch-source", "type": "development", "operation": "development_prepare",
                "arguments": {"changes": [{"path": "src/sample.py", "old_sha256": hashlib.sha256(old).hexdigest(),
                    "content": "VALUE = 2\n"}]}, "depends_on": []}]
        return json.dumps({"steps": steps})

    def prepare_step(proposal, context):
        if proposal["type"] == "filesystem":
            args = proposal["arguments"]
            target = args.get("target") or args.get("path") or "."
            required_kind = "read" if proposal["operation"] in {"read", "inventory"} else "write"
            scope_path = target.rpartition("/")[0] or "."
            available = project["read_directories"] if required_kind == "read" else project["write_directories"]
            required = [{"kind": required_kind, "path": scope_path}]
            granted = [{"kind": required_kind, "path": item} for item in available if _covered([item], scope_path)]
            if not granted:
                return {**proposal, "status": "DENIED", "reason_code": "scope_denied", "prepared_ref": None,
                    "prepared_sha256": None, "expected_inputs": [], "expected_outputs": [],
                    "required_scopes": required, "granted_scopes": [], "required_checks": []}
            session = AgentServiceSession(workspace=workspace, root=project["root"], owner_id=AUTHOR,
                conversation_id=conversation_id, communications=None, project_permissions=permissions)
            result, tool_receipt = session.invoke("filesystem_plan", {"operation": proposal["operation"], **args}, ["filesystem_plan"])
            if not result.get("proposal_id") or result.get("executed") is not False:
                raise AssertionError(f"filesystem plan was not prepared without effects: {tool_receipt}")
            plan = result["plan"]
            inputs = []
            source_snapshot = plan.get("source_snapshot")
            if source_snapshot and proposal["arguments"].get("source"):
                inputs.append({"path": proposal["arguments"]["source"], "sha256": source_snapshot["sha256"]})
            outputs = []
            if proposal["operation"] in {"write", "edit"}:
                outputs.append({"path": plan["target"], "sha256": hashlib.sha256(plan["content"].encode()).hexdigest()})
            return {**proposal, "status": "READY", "prepared_ref": result["proposal_id"], "prepared_sha256": plan["sha256"],
                "expected_inputs": inputs, "expected_outputs": outputs, "required_scopes": required,
                "granted_scopes": granted, "required_checks": []}

        assert dev_service is not None
        if project["root"] != str(dev_service.root):
            return {**proposal, "status": "DENIED", "reason_code": "project_binding_mismatch", "prepared_ref": None,
                "prepared_sha256": None, "expected_inputs": [], "expected_outputs": [],
                "required_scopes": [{"kind": "write", "path": "src"}], "granted_scopes": [], "required_checks": []}
        # The DevelopmentService indexes/copies its bounded candidate source tree.
        # Require an explicit project READ grant for that root before invoking it.
        if not _covered(project["read_directories"], "."):
            return {**proposal, "status": "DENIED", "reason_code": "scope_denied", "prepared_ref": None,
                "prepared_sha256": None, "expected_inputs": [], "expected_outputs": [],
                "required_scopes": [{"kind": "read", "path": "."}, {"kind": "write", "path": "src"}],
                "granted_scopes": [], "required_checks": ["unit"]}
        prepared, _ = dev_service.invoke("development_prepare", proposal["arguments"], owner_id=AUTHOR,
            conversation_id=conversation_id, root=dev_service.root)
        assert prepared["ok"], prepared
        change = prepared["change"]
        checked, _ = dev_service.invoke("development_check", {"change_id": change["change_id"], "check_id": "unit"},
            owner_id=AUTHOR, conversation_id=conversation_id, root=dev_service.root)
        assert checked["check"]["status"] == "PASS", checked
        reviewed, _ = dev_service.invoke("development_review", {"change_id": change["change_id"], "approve": True,
            "reason": "Reviewed exact patch and required check."}, owner_id=REVIEWER,
            conversation_id=conversation_id, root=dev_service.root)
        assert reviewed["ok"], reviewed
        return {**proposal, "status": "READY", "prepared_ref": change["change_id"],
            "prepared_sha256": change["patch_sha256"],
            "expected_inputs": [{"path": row["path"], "sha256": row["old_sha256"]} for row in change["changes"]],
            "expected_outputs": [{"path": row["path"], "sha256": row["new_sha256"]} for row in change["changes"]],
            "required_scopes": [{"kind": "read", "path": "."}, {"kind": "write", "path": "src"}],
            "granted_scopes": [{"kind": "read", "path": "."}, {"kind": "write", "path": "src"}],
            "required_checks": ["unit"]}

    def validate_step(step, context):
        latest = permissions.snapshot()
        bound = context["project"]
        if any(latest[key] != bound[key] for key in ("project_id", "root", "binding", "revision")):
            from src.agent_tasks.store import TaskError
            raise TaskError("permissions_revision_changed", "Project permission revision changed.", 409)
        if step["type"] == "filesystem":
            for scope in step["required_scopes"]:
                current = latest["read_directories"] if scope["kind"] == "read" else latest["write_directories"]
                if not _covered(current, scope["path"]):
                    from src.agent_tasks.store import TaskError
                    raise TaskError("scope_denied", "Current project permission does not cover this operation.", 403)
        elif dev_service is not None:
            change = dev_service.inspect(step["prepared_ref"])
            if change.get("patch_sha256") != step["prepared_sha256"] or not change.get("apply_eligible"):
                from src.agent_tasks.store import TaskError
                raise TaskError("required_check_failed", "Development candidate lost its checks or independent review.", 409)

    def execute_step(step, context):
        observed["executions"] += 1
        if step["type"] == "filesystem":
            proposal_id = step["prepared_ref"]
            from src.agent_tools.document_tools import toolkit
            toolkit()
            reviewed = review_filesystem(workspace=workspace, proposal_id=proposal_id, owner_id=AUTHOR,
                conversation_id=conversation_id, revision=0, project_permissions=permissions)
            receipt = execute_filesystem(workspace=workspace, proposal_id=proposal_id, owner_id=AUTHOR,
                conversation_id=conversation_id, revision=0, review_token=reviewed["review_token"],
                plan_sha256=step["prepared_sha256"], confirmed=True, project_permissions=permissions)
            native = receipt.get("receipt", {})
            readback = native.get("readback", {})
            outputs = ([{"path": native["target"], "sha256": readback["sha256"]}]
                if native.get("target") and isinstance(readback.get("sha256"), str) else [])
            return {"status": "PASS" if receipt.get("status") == "VERIFIED" else "FAIL",
                "effect_executed": receipt.get("status") == "VERIFIED", "receipt_id": receipt.get("receipt", {}).get("receipt_id"),
                "receipt_sha256": receipt.get("receipt", {}).get("sha256"), "operation": step["operation"], "outputs": outputs}
        applied = dev_service.apply(step["prepared_ref"], step["prepared_sha256"], True)
        return {"status": "PASS" if applied.get("status") == "APPLIED" else "FAIL", "effect_executed": applied.get("status") == "APPLIED",
            "receipt_id": applied.get("apply_receipt", {}).get("receipt_id"), "patch_sha256": applied.get("patch_sha256"),
            "outputs": [{"path": item["path"], "sha256": item["new_sha256"]}
                for item in applied.get("apply_receipt", {}).get("files", [])]}

    adapters = TaskExecutionAdapters(
        project_snapshot=snapshot,
        current_agent=current_agent,
        select_agent=select_agent,
        model_catalog=lambda: {"models": [{"provider_id": "codex", "model_id": "operation-local-test-model",
            "state": "configured_unverified", "orchestrator_enabled": True, "agent_types": ["tool"]}]},
        model_eligible=lambda provider, model, role: True,
        probe_model=lambda provider, model: {"status": "PASS", "generation_sha256": hashlib.sha256(b"provider probe response").hexdigest()},
        generate_plan=generate,
        prepare_step=prepare_step,
        review_plan=lambda plan, context: {"status": "approved", "reviewer_id": REVIEWER, "reviewer_sha256": REVIEWER_SHA,
            "receipt": {"review_id": "plan-review-local"}},
        validate_step=validate_step,
        execute_step=execute_step,
    )
    service = TaskExecutionService(TaskStore(task_state / "task-history.sqlite3"), adapters)
    app = FastAPI()
    app.include_router(create_task_execution_router(service=service))
    return TestClient(app), observed, project


def _prepare(client: TestClient, project: dict, task_text: str):
    response = client.post("/api/task-executions/plans", json={
        "request_id": "7aa022ef-4132-458d-8d9b-58e4b3638cee", "task_text": task_text,
        "expected_project_id": project["project_id"], "expected_binding": project["binding"],
        "expected_permissions_revision": project["revision"], "model_selection": {"mode": "auto"},
        "agent_selection": {"mode": "auto"},
    })
    assert response.status_code == 200, response.text
    prepared = response.json()
    assert prepared["execution_id"]
    if prepared["status"] == "PREPARING":
        prepared = client.get(f"/api/task-executions/{prepared['execution_id']}").json()
    return prepared


def test_api_persists_plan_before_single_acceptance_and_executes_real_filesystem_service(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "allowed").mkdir()
    permissions = _permissions(project, read=["allowed"], write=["allowed"])
    client, observed, initial = _adapter_bundle(project, permissions=permissions, kind="filesystem")
    prepared = _prepare(client, initial, "Create allowed/result.txt containing a short status")
    assert prepared["status"] == "AWAITING_ACCEPTANCE"
    assert prepared["execution_id"].startswith("taskexec_")
    assert not (project / "allowed/result.txt").exists()
    fetched = client.get(f"/api/task-executions/{prepared['execution_id']}")
    assert fetched.status_code == 200 and fetched.json()["plan_sha256"] == prepared["plan_sha256"]
    accepted = client.post(f"/api/task-executions/plans/{prepared['plan_id']}/accept", json={
        "expected_plan_sha256": prepared["plan_sha256"], "expected_plan_revision": 1,
        "idempotency_key": "56a4813e-30c2-48a4-a139-91ca11d18bf9", "confirmed": True,
    })
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["status"] == "SUCCEEDED"
    assert (project / "allowed/result.txt").read_text(encoding="utf-8") == "written by the accepted plan"
    replay = client.post(f"/api/task-executions/plans/{prepared['plan_id']}/accept", json={
        "expected_plan_sha256": prepared["plan_sha256"], "expected_plan_revision": 1,
        "idempotency_key": "56a4813e-30c2-48a4-a139-91ca11d18bf9", "confirmed": True,
    })
    assert replay.status_code == 200 and replay.json()["idempotent_replay"] is True
    assert observed["executions"] == 1


def test_api_out_of_scope_filesystem_path_is_denied_without_write(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "allowed").mkdir()
    (project / "denied").mkdir()
    permissions = _permissions(project, read=["allowed"], write=["allowed"])
    client, observed, initial = _adapter_bundle(project, permissions=permissions, kind="filesystem",
        filesystem_target="denied/escape.txt")
    prepared = _prepare(client, initial, "Write a file under denied/")
    assert prepared["status"] == "DENIED"
    assert prepared["plan"]["steps"][0]["status"] == "DENIED"
    assert not (project / "denied/escape.txt").exists()
    assert observed["executions"] == 0


def test_development_service_check_review_and_apply_runs_only_after_acceptance(tmp_path):
    project = tmp_path / "project"
    source_dir = project / "src"
    source_dir.mkdir(parents=True)
    source = source_dir / "sample.py"
    source.write_text("VALUE = 1\n", encoding="utf-8")
    permissions = _permissions(project, read=["."], write=["src"])
    profile = tmp_path / "development-profile.json"
    profile.write_text(json.dumps({"root": str(project), "state_root": str(tmp_path / "development-state"),
        "allowed_paths": ["src/sample.py"], "checks": {"unit": [sys.executable, "-B", "-c", "print('bounded check PASS')"]},
        "required_checks": ["unit"]}), encoding="utf-8")
    from src.development import DevelopmentService
    development = DevelopmentService(profile)
    client, observed, initial = _adapter_bundle(project, permissions=permissions, kind="development", dev_service=development)
    before = source.read_text(encoding="utf-8")
    prepared = _prepare(client, initial, "Change src/sample.py from VALUE = 1 to VALUE = 2")
    assert prepared["status"] == "AWAITING_ACCEPTANCE"
    assert source.read_text(encoding="utf-8") == before
    assert prepared["plan"]["required_checks"] == ["unit"]
    accepted = client.post(f"/api/task-executions/plans/{prepared['plan_id']}/accept", json={
        "expected_plan_sha256": prepared["plan_sha256"], "expected_plan_revision": 1,
        "idempotency_key": "b3262bc4-b8fb-4e99-91e7-3a33653e8e10", "confirmed": True,
    })
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["status"] == "SUCCEEDED"
    assert source.read_text(encoding="utf-8") == "VALUE = 2\n"
    assert observed["executions"] == 1


def test_production_adapter_factory_executes_scoped_filesystem_write(tmp_path):
    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / "allowed").mkdir()
    permissions = _permissions(project_root, read=["allowed"], write=["allowed"])
    snapshot = permissions.snapshot()
    task_state = tmp_path / "controller-state"
    task_state.mkdir()
    output = project_root / "allowed" / "factory-output.txt"
    selection_tools = ["filesystem_plan"]

    def generate(provider, model, messages):
        return json.dumps({"steps": [{"step_id": "write-one", "type": "filesystem", "operation": "write",
            "arguments": {"target": "allowed/factory-output.txt", "content": "factory execution\n"}, "depends_on": []}]})

    adapters = build_host_task_execution_adapters(
        project_snapshot=permissions.snapshot,
        current_agent=lambda agent_id: {"agent_id": AUTHOR, "profile_sha256": PROFILE_SHA,
            "type": "tool", "tools": ["filesystem_plan"]},
        select_agent=lambda selection, task, model_selection: {"agent_id": AUTHOR, "profile_sha256": PROFILE_SHA,
            "type": "tool", "tools": list(selection_tools), "task_scope": "one output",
            "created_for_task": selection.mode == "auto"},
        model_catalog=lambda: {"models": [{"provider_id": "codex", "model_id": "factory-test",
            "state": "configured_unverified", "orchestrator_enabled": True, "agent_types": ["tool"]}]},
        model_eligible=lambda provider, model, role: True,
        probe_model=lambda provider, model: {"status": "PASS", "generation_sha256": hashlib.sha256(b"probe").hexdigest()},
        generate_plan=generate,
        review_plan=lambda plan, context: {"status": "approved", "reviewer_id": REVIEWER,
            "reviewer_sha256": REVIEWER_SHA, "receipt": {"review_id": "factory-plan-review"}},
        workspace_root=lambda: tmp_path,
        project_permissions=lambda: permissions,
        development_service=lambda: None,
        development_reviewer=lambda change, context: {"reviewer_id": REVIEWER},
    )
    service = TaskExecutionService(TaskStore(task_state / "task-history.sqlite3"), adapters)
    request = PlanPrepareInput.model_validate({"request_id": "7aa022ef-4132-458d-8d9b-58e4b3638cee",
        "task_text": "Write one file through the production filesystem adapter", "expected_project_id": snapshot["project_id"],
        "expected_binding": snapshot["binding"], "expected_permissions_revision": snapshot["revision"],
        "model_selection": {"mode": "auto"}, "agent_selection": {"mode": "auto"}})
    prepared = service.prepare(request)
    assert prepared["status"] == "AWAITING_ACCEPTANCE"
    assert not output.exists()
    result = service.accept(prepared["plan_id"], PlanAcceptInput(expected_plan_sha256=prepared["plan_sha256"],
        expected_plan_revision=1, idempotency_key="b3262bc4-b8fb-4e99-91e7-3a33653e8e10", confirmed=True))
    assert result["status"] == "SUCCEEDED", result
    assert output.read_text(encoding="utf-8") == "factory execution\n"
    selection_tools.clear()
    denied_request = request.model_copy(update={"request_id": "00000000-0000-4000-8000-000000000002"})
    denied = service.prepare(denied_request)
    denied_step = denied["plan"]["steps"][0]
    assert denied_step["status"] == "DENIED"
    assert denied_step["reason_code"] == "agent_tool_not_assigned"
    assert denied_step["required_scopes"] == [{"kind": "write", "path": "allowed"}]
    assert denied_step["granted_scopes"] == denied_step["required_scopes"]


def test_production_adapter_factory_runs_development_checks_review_and_apply(tmp_path):
    project_root = tmp_path / "project"
    source = project_root / "src" / "sample.py"
    source.parent.mkdir(parents=True)
    source.write_text("VALUE = 1\n", encoding="utf-8")
    permissions = _permissions(project_root, read=["."], write=["src"])
    snapshot = permissions.snapshot()
    profile = tmp_path / "development-profile.json"
    profile.write_text(json.dumps({"root": str(project_root), "state_root": str(tmp_path / "dev-state"),
        "allowed_paths": ["src/sample.py"], "checks": {"unit": [sys.executable, "-B", "-c", "print('PASS')"]},
        "required_checks": ["unit"]}), encoding="utf-8")
    from src.development import DevelopmentService
    development = DevelopmentService(profile)
    def generate(provider, model, messages):
        current_sha = hashlib.sha256(source.read_bytes()).hexdigest()
        next_value = "2" if source.read_text(encoding="utf-8").strip() == "VALUE = 1" else "3"
        return json.dumps({"steps": [{"step_id": "change-source", "type": "development", "operation": "development_prepare",
            "arguments": {"changes": [{"path": "src/sample.py", "old_sha256": current_sha,
                "content": f"VALUE = {next_value}\n"}]},
            "depends_on": []}]})

    review_state = {"status": "approved"}

    adapters = build_host_task_execution_adapters(
        project_snapshot=permissions.snapshot,
        current_agent=lambda agent_id: {"agent_id": AUTHOR, "profile_sha256": PROFILE_SHA,
            "type": "tool", "tools": ["development_prepare", "development_read"]},
        select_agent=lambda selection, task, model_selection: {"agent_id": AUTHOR, "profile_sha256": PROFILE_SHA,
            "type": "tool", "tools": ["development_prepare", "development_read"], "task_scope": "one source change"},
        model_catalog=lambda: {"models": [{"provider_id": "codex", "model_id": "factory-test",
            "state": "ready", "orchestrator_enabled": True, "agent_types": ["tool"]}]},
        model_eligible=lambda provider, model, role: True,
        probe_model=lambda provider, model: {"status": "PASS", "generation_sha256": hashlib.sha256(b"probe").hexdigest()},
        generate_plan=generate,
        review_plan=lambda plan, context: {"status": "approved", "reviewer_id": REVIEWER,
            "reviewer_sha256": REVIEWER_SHA, "receipt": {"review_id": "factory-plan-review"}},
        workspace_root=lambda: tmp_path,
        project_permissions=lambda: permissions,
        development_service=lambda: development,
        development_reviewer=lambda change, context: {"status": review_state["status"], "reviewer_id": REVIEWER,
            "reviewer_sha256": REVIEWER_SHA, "receipt": {"review_id": "dev-review"}, "reason": "Checked exact patch."},
    )
    store = TaskStore(tmp_path / "controller-state" / "task-history.sqlite3")
    service = TaskExecutionService(store, adapters)
    request = PlanPrepareInput.model_validate({"request_id": "7aa022ef-4132-458d-8d9b-58e4b3638cee",
        "task_text": "Change one allowed source file", "expected_project_id": snapshot["project_id"],
        "expected_binding": snapshot["binding"], "expected_permissions_revision": snapshot["revision"],
        "model_selection": {"mode": "auto"}, "agent_selection": {"mode": "auto"}})
    prepared = service.prepare(request)
    assert prepared["plan"]["required_checks"] == ["unit"]
    assert source.read_text(encoding="utf-8") == "VALUE = 1\n"
    result = service.accept(prepared["plan_id"], PlanAcceptInput(expected_plan_sha256=prepared["plan_sha256"],
        expected_plan_revision=1, idempotency_key="b3262bc4-b8fb-4e99-91e7-3a33653e8e10", confirmed=True))
    assert result["status"] == "SUCCEEDED", result
    assert source.read_text(encoding="utf-8") == "VALUE = 2\n"
    review_state["status"] = "rejected"
    rejected_request = request.model_copy(update={"request_id": "00000000-0000-4000-8000-000000000002"})
    with pytest.raises(TaskError, match="no aprobó"):
        service.prepare(rejected_request)
    assert source.read_text(encoding="utf-8") == "VALUE = 2\n"


def test_api_rejects_extra_fields_and_foreign_origin_before_adapters(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "allowed").mkdir()
    permissions = _permissions(project, read=["."], write=["."])
    client, observed, snapshot = _adapter_bundle(project, permissions=permissions, kind="filesystem")
    body = {"request_id": "7aa022ef-4132-458d-8d9b-58e4b3638cee", "task_text": "Create one file",
        "expected_project_id": snapshot["project_id"], "expected_binding": snapshot["binding"],
        "expected_permissions_revision": snapshot["revision"], "model_selection": {"mode": "auto"},
        "agent_selection": {"mode": "auto"}, "allow_all": True}
    assert client.post("/api/task-executions/plans", json=body).status_code == 422
    assert client.post("/api/task-executions/plans", json={k:v for k,v in body.items() if k != "allow_all"},
        headers={"origin": "http://foreign.invalid"}).status_code == 403
    assert observed["generations"] == 0


def test_post_returns_durable_preparing_id_before_plan_is_ready(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    permissions = _permissions(project, read=["."], write=["."])
    client, _, snapshot = _adapter_bundle(project, permissions=permissions, kind="filesystem")
    response = client.post("/api/task-executions/plans", json={
        "request_id": "7aa022ef-4132-458d-8d9b-58e4b3638cee", "task_text": "Create one bounded file",
        "expected_project_id": snapshot["project_id"], "expected_binding": snapshot["binding"],
        "expected_permissions_revision": snapshot["revision"], "model_selection": {"mode": "auto"},
        "agent_selection": {"mode": "auto"}})
    assert response.status_code == 200
    reserved = response.json()
    assert reserved["status"] == "PREPARING"
    assert reserved["plan"] is None
    assert reserved["execution_id"].startswith("taskexec_")
    recovered = client.get(f"/api/task-executions/{reserved['execution_id']}")
    assert recovered.status_code == 200
    assert recovered.json()["status"] in {"AWAITING_ACCEPTANCE", "FAILED_NO_EFFECT", "INCONCLUSIVE"}

