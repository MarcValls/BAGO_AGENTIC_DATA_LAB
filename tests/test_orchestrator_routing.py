"""End-to-end synthetic checks for BAGO5 routing, return and profile creation."""
import pytest
import asyncio
import json
from pathlib import Path

from src.api import server
from test_agent_delegation import setup


def _new_task_agent(task, tools=()):
    return server.AgentConfig(
        name="Task-scoped fixture agent",
        description="Synthetic agent created for one bounded conversational task.",
        task_scope=task,
        type="tool",
        system_prompt="Synthetic fixture only.",
        provider_id="ollama-cloud",
        model_id="child-fixture",
        tools=list(tools),
    )


def _install_task_agent_factory(f, monkeypatch, tools=()):
    async def generate(task, history, model_id, provider_id, *, task_scoped=False):
        assert task and model_id == "parent-fixture" and provider_id == "ollama-cloud"
        return _new_task_agent(task, tools)

    monkeypatch.setattr(server, "_generate_agent_draft", generate)


def test_agent_without_explicit_saved_task_scope_fails_closed(setup):
    f = setup
    record = server._load_agent(f["agent_id"])
    record.config.task_scope = None
    before = len(f["calls"])
    decision, reason = asyncio.run(server._classify_agent_task_scope(
        "ollama-cloud", "parent-fixture", record, "A synthetic task."
    ))
    assert decision == "unclear" and reason == "saved_task_scope_missing"
    assert len(f["calls"]) == before


@pytest.mark.parametrize("first_decision", ["delegate_agent", "create_agent_for_task"])
def test_orchestrator_persists_tool_free_agent_when_no_profile_fits(setup, first_decision):
    f = setup
    f["file"].unlink()
    task = "Prepare a synthetic monthly summary and list anomalies."
    _install_task_agent_factory(f, f["monkeypatch"])
    fixture_turn = server.provider_runtime.chat_turn

    def route(provider, model, messages, **kwargs):
        names = {item.get("function", {}).get("name") for item in kwargs.get("tools", [])}
        if "resolve_control_request" in names:
            if "Host routing outcome (trusted control result" in messages[0]["content"]:
                decision = "create_agent_for_task"
            else:
                decision = first_decision
            arguments = ({"decision": "delegate_agent", "agent_id": f["agent_id"], "task": task, "reply": "Route this task."}
                         if decision == "delegate_agent" else
                         {"decision": "create_agent_for_task", "task": task, "reply": "No saved profile fits."})
            return {"tool_calls": [{"function": {"name": "resolve_control_request", "arguments": arguments}}]}
        return fixture_turn(provider, model, messages, **kwargs)

    f["monkeypatch"].setattr(server.provider_runtime, "chat_turn", route)
    response = f["client"].post("/api/chat/control", json={
        "message": task, "conversation_id": f["parent"]["id"], "revision": 0,
    })
    assert response.status_code == 200, response.text
    body = response.json()
    delegation = body["agent_delegation"]
    assert body["operation"] == "agent_delegation"
    assert delegation["state"] == "PASSED"
    assert delegation["task"] == task
    created_id = delegation["agent_id"]
    assert created_id != f["agent_id"]
    saved = server._load_agent(created_id)
    assert saved.config.task_scope == task
    assert saved.config.tools == []
    assert delegation["child_conversation_id"]
    assert not delegation["tools_executed"] and not delegation["target_written"]
    assert f["store"].list("agent", created_id)


def test_invalid_model_agent_id_falls_back_to_task_scoped_agent_without_grant(setup):
    f = setup
    f["file"].unlink()
    (f["workspace"] / "hint.txt").write_text("Synthetic summary: 17 units.\n", encoding="utf-8")
    task = "Read hint.txt and report its synthetic summary."
    _install_task_agent_factory(f, f["monkeypatch"])
    fixture_turn = server.provider_runtime.chat_turn
    before = len(server._read_agent_records()[0])
    permit = server.WORKSPACE_READ_AUTHORIZATIONS.issue(
        f["workspace"], owner_kind="assistant", owner_id="app-assistant",
        conversation_id=f["parent"]["id"], revision=0, paths=["hint.txt"],
    )
    read_calls = []
    original_read = server.read_workspace_file

    def tracked_read(*args, **kwargs):
        read_calls.append(args[1] if len(args) > 1 else kwargs)
        return original_read(*args, **kwargs)

    f["monkeypatch"].setattr(server, "read_workspace_file", tracked_read)

    def route(provider, model, messages, **kwargs):
        names = {item.get("function", {}).get("name") for item in kwargs.get("tools", [])}
        if "resolve_control_request" in names:
            return {"tool_calls": [{"function": {"name": "resolve_control_request", "arguments": {
                "decision": "delegate_agent", "agent_id": "agent-not-a-persisted-id",
                "task": task, "reply": "Route this task."
            }}}]}
        if "resolve_agent_scope" in names:
            return {"tool_calls": [{"function": {"name": "resolve_agent_scope", "arguments": {
                "decision": "in_scope", "reason": "The generated task scope matches."
            }}}]}
        return fixture_turn(provider, model, messages, **kwargs)

    f["monkeypatch"].setattr(server.provider_runtime, "chat_turn", route)
    response = f["client"].post("/api/chat/control", json={
        "message": task, "conversation_id": f["parent"]["id"], "revision": 0,
        "workspace_read_authorization_id": permit["authorization_id"],
    })
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["operation"] == "agent_delegation"
    assert body["agent_delegation"]["state"] == "PASSED"
    assert body["agent_delegation"]["task"] == task
    assert len(server._read_agent_records()[0]) == before + 1
    saved = server._load_agent(body["agent_delegation"]["agent_id"])
    assert saved.config.task_scope == task
    assert saved.config.tools == []
    assert body["agent_delegation"]["child_conversation_id"]
    assert not body["agent_delegation"]["tools_executed"]
    assert not body["agent_delegation"]["target_written"]
    assert read_calls == []
    assert body["sources"] == [] and body["read_events"] == []


def test_invalid_agent_id_does_not_override_explicit_named_agent_request(setup):
    f = setup
    task = "Prepare a synthetic monthly summary and list anomalies."
    _install_task_agent_factory(f, f["monkeypatch"])
    before = len(server._read_agent_records()[0])
    f["monkeypatch"].setattr(server.provider_runtime, "chat_turn", lambda *args, **kwargs: {
        "tool_calls": [{"function": {"name": "resolve_control_request", "arguments": {
            "decision": "delegate_agent", "agent_id": "agent-not-a-persisted-id",
            "task": task, "reply": "Route this task."
        }}}]
    })

    response = f["client"].post("/api/chat/control", json={
        "message": f"{task} Delega en el agente Fantasma.",
        "conversation_id": f["parent"]["id"], "revision": 0,
    })
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["operation"] == "chat"
    assert body.get("agent_delegation") is None
    assert "Elige un agente guardado concreto" in body["assistant_message"]
    assert len(server._read_agent_records()[0]) == before


def test_out_of_scope_agent_is_persisted_then_excluded_before_reassignment(setup):
    f = setup
    task = "Prepare a synthetic monthly summary and list anomalies."
    _install_task_agent_factory(f, f["monkeypatch"])
    f["delegation_outcome"] = ["out_of_scope", "completed"]
    fixture_turn = server.provider_runtime.chat_turn
    parent_calls = []

    def route(provider, model, messages, **kwargs):
        names = {item.get("function", {}).get("name") for item in kwargs.get("tools", [])}
        if "resolve_control_request" in names:
            parent_calls.append(messages[0]["content"])
            if "Host routing outcome (trusted control result" in messages[0]["content"]:
                assert f["agent_id"] in messages[0]["content"]
                return {"tool_calls": [{"function": {"name": "resolve_control_request", "arguments": {
                    "decision": "create_agent_for_task", "task": task, "reply": "No other profile fits."
                }}}]}
            return {"tool_calls": [{"function": {"name": "resolve_control_request", "arguments": {
                "decision": "delegate_agent", "agent_id": f["agent_id"], "task": task, "reply": "Route to saved profile."
            }}}]}
        return fixture_turn(provider, model, messages, **kwargs)

    f["monkeypatch"].setattr(server.provider_runtime, "chat_turn", route)
    response = f["client"].post("/api/chat/control", json={
        "message": task, "conversation_id": f["parent"]["id"], "revision": 0,
    })
    assert response.status_code == 200, response.text
    body = response.json()
    final = body["agent_delegation"]
    assert body["operation"] == "agent_delegation"
    assert final["state"] == "PASSED" and final["agent_id"] != f["agent_id"]
    assert final["task"] == task
    assert len(parent_calls) == 2
    parent = f["store"].get(f["parent"]["id"])
    records = [m.get("references", {}).get("agent_delegation", {}) for m in parent["messages"]]
    returned = [item for item in records if item.get("agent_id") == f["agent_id"] and item.get("state") == "OUT_OF_SCOPE"]
    assert returned and returned[-1]["receipt_id"] and returned[-1]["receipt_sha256"]
    assert server._load_agent(final["agent_id"]).config.tools == []


def test_task_created_agent_gets_connected_tools_and_waits_for_effect_review(setup):
    f = setup
    f["file"].unlink()
    task = "Inventory the selected documents and extract the matching invoice values."
    requested_tools = ["document_inventory", "document_extract", "mcp.execute", "sandbox.run"]
    fixture_turn = server.provider_runtime.chat_turn
    draft_modes = []

    async def generate(requested_task, history, model_id, provider_id, *, task_scoped=False):
        draft_modes.append(task_scoped)
        return _new_task_agent(requested_task, requested_tools)

    f["monkeypatch"].setattr(server, "_generate_agent_draft", generate)

    def route(provider, model, messages, **kwargs):
        names = {item.get("function", {}).get("name") for item in kwargs.get("tools", [])}
        if "resolve_control_request" in names:
            return {"tool_calls": [{"function": {"name": "resolve_control_request", "arguments": {
                "decision": "create_agent_for_task", "task": task, "reply": "No saved profile fits."
            }}}]}
        if "resolve_agent_scope" in names:
            return {"tool_calls": [{"function": {"name": "resolve_agent_scope", "arguments": {
                "decision": "in_scope", "reason": "Synthetic task-scoped profile."
            }}}]}
        if model == "child-fixture" and "document_inventory" in names:
            tool_turns = [message for message in messages if message.get("role") == "tool"]
            if not tool_turns:
                return {"tool_calls": [{"function": {"name": "document_inventory", "arguments": {}}}]}
            if len(tool_turns) == 1:
                return {"tool_calls": [{"function": {"name": "document_extract", "arguments": {"paths": ["invoice.txt"]}}}]}
            return {"content": "Invoice total: 17 synthetic units."}
        return fixture_turn(provider, model, messages, **kwargs)

    f["monkeypatch"].setattr(server.provider_runtime, "chat_turn", route)
    response = f["client"].post("/api/chat/control", json={
        "message": task, "conversation_id": f["parent"]["id"], "revision": 0,
    })
    assert response.status_code == 200, response.text
    body = response.json()
    proposal = body["agent_delegation"]
    assert body["operation"] == "agent_delegation"
    assert proposal["state"] == "PROPOSED"
    assert proposal["assigned_tools"] == ["document_inventory", "document_extract"]
    assert proposal["child_conversation_id"] is None
    saved = server._load_agent(proposal["agent_id"])
    assert saved.config.tools == ["document_inventory", "document_extract"]
    assert saved.config.task_scope == task and saved.config.task.prompt == task
    assert draft_modes == [True]

    corpus = f["workspace"] / "corpus"
    (corpus / "invoice.txt").write_text("Invoice SYN-001 total: 17 synthetic units.\n", encoding="utf-8")
    scope = {
        "allow_tools": True, "root": str(corpus), "allow_export": False,
        "expected_output_directory": None, "review_work_id": None,
        "review_candidate_id": None, "review_scope_sha256": None,
        "contact_id": None, "allow_draft": False,
    }
    executed = f["client"].post(
        f"/api/agent-delegations/{proposal['proposal_id']}/execute",
        json={"parent_conversation_id": proposal["parent_conversation_id"],
              "parent_revision": proposal["parent_revision"],
              "proposal_sha256": proposal["proposal_sha256"], "confirm": True, "scope": scope},
    )
    assert executed.status_code == 200, executed.text
    result = executed.json()["agent_delegation"]
    assert result["state"] == "PASSED" and result["tools_executed"] and not result["target_written"]
    receipt_path = f["tmp"] / "traces" / "agent-delegations" / "receipts" / f"{result['receipt_id']}.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert [item["tool_name"] for item in receipt["tool_receipts"]] == ["document_inventory", "document_extract"]
    assert all(item["decision"] == "ALLOW" for item in receipt["tool_receipts"])
    assert receipt["human_scope"]["allow_tools"] is True
    assert receipt["human_scope"]["root"] == str(corpus)


def test_task_scoped_draft_prompt_only_offers_connected_handlers():
    prompt = server._agent_draft_messages("Read the selected documents", task_scoped=True)[0]["content"]
    assert "Tool assignment is not permission" in prompt
    assert "document_inventory" in prompt and "document_extract" in prompt
    assert "mcp.execute" not in prompt and "sandbox.run" not in prompt


def test_unvalidated_auto_created_profile_is_not_replaced_by_repeated_creation(setup):
    f = setup
    f["file"].unlink()
    task = "Summarize a synthetic monthly report."
    generated = []

    async def generate(requested_task, history, model_id, provider_id, *, task_scoped=False):
        generated.append(requested_task)
        return _new_task_agent(requested_task)

    f["monkeypatch"].setattr(server, "_generate_agent_draft", generate)
    f["delegation_outcome"] = ["out_of_scope"]

    def route(provider, model, messages, **kwargs):
        names = {item.get("function", {}).get("name") for item in kwargs.get("tools", [])}
        if "resolve_agent_scope" in names:
            return {"tool_calls": [{"function": {"name": "resolve_agent_scope", "arguments": {
                "decision": "in_scope", "reason": "Synthetic scope classification."
            }}}]}
        if "resolve_agent_result" in names:
            return {"tool_calls": [{"function": {"name": "resolve_agent_result", "arguments": {
                "decision": "out_of_scope", "reason": "Synthetic agent returned the task."
            }}}]}
        assert "resolve_control_request" in names
        if "Host routing outcome (trusted control result" in messages[0]["content"]:
            return {"tool_calls": [{"function": {"name": "resolve_control_request", "arguments": {
                "decision": "create_agent_for_task", "task": task, "reply": "Create a replacement profile."
            }}}]}
        return {"tool_calls": [{"function": {"name": "resolve_control_request", "arguments": {
            "decision": "create_agent_for_task", "task": task, "reply": "No saved profile fits."
        }}}]}

    f["monkeypatch"].setattr(server.provider_runtime, "chat_turn", route)
    response = f["client"].post("/api/chat/control", json={
        "message": task, "conversation_id": f["parent"]["id"], "revision": 0,
    })
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["operation"] == "chat"
    assert "todavía no ha quedado validado" in body["assistant_message"]
    assert generated == [task]
    saved_agents = list(f["file"].parent.glob("*.json"))
    assert len(saved_agents) == 1
    saved = server._load_agent(saved_agents[0].stem)
    assert saved.config.task_scope == task
    assert saved.config.tools == []


def test_auto_created_agent_preserves_full_task_scope_at_chat_limit(setup):
    f = setup
    f["file"].unlink()
    prefix = "Prepare a synthetic summary and preserve every constraint. "
    suffix = " Final constraint: report the result only; do not read or write files."
    task = prefix + ("x" * (8000 - len(prefix) - len(suffix))) + suffix
    assert len(task) == 8000
    _install_task_agent_factory(f, f["monkeypatch"])
    fixture_turn = server.provider_runtime.chat_turn

    def route(provider, model, messages, **kwargs):
        names = {item.get("function", {}).get("name") for item in kwargs.get("tools", [])}
        if "resolve_control_request" in names:
            return {"tool_calls": [{"function": {"name": "resolve_control_request", "arguments": {
                "decision": "create_agent_for_task", "task": task, "reply": "Create a scoped agent."
            }}}]}
        return fixture_turn(provider, model, messages, **kwargs)

    f["monkeypatch"].setattr(server.provider_runtime, "chat_turn", route)
    response = f["client"].post("/api/chat/control", json={
        "message": task, "conversation_id": f["parent"]["id"], "revision": 0,
    })
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["operation"] == "agent_delegation"
    assert body["agent_delegation"]["state"] == "PASSED"
    saved = server._load_agent(body["agent_delegation"]["agent_id"])
    assert saved.config.task_scope == task
    assert saved.config.task.prompt == task
    assert saved.config.tools == []


def test_control_request_prompt_aligns_with_scope_validated_dispatch():
    description = server.CONTROL_REQUEST_TOOL["function"]["description"]
    delegate_contract = description.split("Choose communication_draft", 1)[0]

    assert "only when the host validates the saved task_scope as a match" in delegate_contract
    assert "without a second delegation review" in delegate_contract
    assert "for human review" not in delegate_contract
    assert "Never run a draft" in delegate_contract
    assert "authorize scope or claim execution" in delegate_contract
    assert "without granting tools" not in delegate_contract
    assert "only relevant tools connected to agent chat" in delegate_contract
    assert "explicit effect and folder authorization" in delegate_contract
    assert "creates a task-limited profile and selects only relevant tools connected to agent chat" in delegate_contract
    assert "return the delegation card for explicit effect and folder authorization" in delegate_contract


def test_authorized_workspace_turn_routes_before_any_direct_read(setup):
    f = setup
    (f["workspace"] / "hint.txt").write_text("Synthetic invoice amount: 17 units.\n", encoding="utf-8")
    permit = server.WORKSPACE_READ_AUTHORIZATIONS.issue(
        f["workspace"], owner_kind="assistant", owner_id="app-assistant",
        conversation_id=f["parent"]["id"], revision=0, paths=["hint.txt"],
    )
    task = "Inspect hint.txt and extract the invoice amount."
    _install_task_agent_factory(f, f["monkeypatch"], ["document_inventory", "document_extract"])
    read_calls = []
    original_read = server.read_workspace_file

    def tracked_read(*args, **kwargs):
        read_calls.append(args[1] if len(args) > 1 else kwargs)
        return original_read(*args, **kwargs)

    f["monkeypatch"].setattr(server, "read_workspace_file", tracked_read)

    def route(provider, model, messages, **kwargs):
        names = {item.get("function", {}).get("name") for item in kwargs.get("tools", [])}
        if "read_workspace_file" in names:
            # Reproduce the live failure: the provider chooses the file reader
            # while both routing and data tools are offered in the same round.
            return {"tool_calls": [{"function": {"name": "read_workspace_file",
                "arguments": {"path": "hint.txt"}}}]}
        if "resolve_control_request" in names:
            assert names == {"resolve_control_request"}
            return {"tool_calls": [{"function": {"name": "resolve_control_request", "arguments": {
                "decision": "create_agent_for_task", "task": task, "reply": "Create a task-scoped agent."
            }}}]}
        if "resolve_agent_scope" in names:
            return {"tool_calls": [{"function": {"name": "resolve_agent_scope", "arguments": {
                "decision": "in_scope", "reason": "The generated task scope matches."
            }}}]}
        return {"content": "No additional operation."}

    f["monkeypatch"].setattr(server.provider_runtime, "chat_turn", route)
    response = f["client"].post("/api/chat/control", json={
        "message": task, "conversation_id": f["parent"]["id"], "revision": 0,
        "workspace_read_authorization_id": permit["authorization_id"],
    })
    assert response.status_code == 200, response.text
    body = response.json()
    proposal = body["agent_delegation"]
    assert body["operation"] == "agent_delegation"
    assert proposal["state"] == "PROPOSED"
    assert proposal["assigned_tools"] == ["document_inventory", "document_extract"]
    assert proposal["child_conversation_id"] is None
    assert read_calls == []
    assert body["sources"] == [] and body["read_events"] == []


def test_orchestrator_resolves_file_read_intent_then_calls_only_authorized_reader(setup):
    f = setup
    target = f["workspace"] / "sample_a.py"
    target.write_text("def total():\n    return 17\n", encoding="utf-8")
    permit = server.WORKSPACE_READ_AUTHORIZATIONS.issue(
        f["workspace"], owner_kind="assistant", owner_id="app-assistant",
        conversation_id=f["parent"]["id"], revision=0, paths=["sample_a.py"],
    )
    phases = []

    def route(provider, model, messages, **kwargs):
        names = {item.get("function", {}).get("name") for item in kwargs.get("tools", [])}
        phases.append(names)
        if names == {"resolve_control_request"}:
            return {"tool_calls": [{"id": "route-1", "function": {"name": "resolve_control_request", "arguments": {
                "decision": "workspace_read", "reply": "Voy a consultar el archivo autorizado."
            }}}]}
        assert names == {"read_workspace_file"}
        if not any(message.get("role") == "tool" and message.get("tool_name") == "read_workspace_file" for message in messages):
            return {"tool_calls": [{"id": "read-1", "function": {"name": "read_workspace_file", "arguments": {
                "path": "sample_a.py", "start_line": 1, "end_line": 2
            }}}]}
        tool_result = next(message["content"] for message in reversed(messages)
                           if message.get("role") == "tool" and message.get("tool_name") == "read_workspace_file")
        assert "def total()" in tool_result and "return 17" in tool_result
        return {"content": "sample_a.py define total(), que devuelve 17; contiene dos líneas.", "tool_calls": []}

    f["monkeypatch"].setattr(server.provider_runtime, "chat_turn", route)
    response = f["client"].post("/api/chat/control", json={
        "message": "Inspecciona sample_a.py y resume en una frase qué hace y cuántas líneas tiene.",
        "conversation_id": f["parent"]["id"], "revision": 0,
        "workspace_read_authorization_id": permit["authorization_id"],
    })
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["operation"] == "chat"
    assert body["assistant_message"] == "sample_a.py define total(), que devuelve 17; contiene dos líneas."
    assert phases == [{"resolve_control_request"}, {"read_workspace_file"}, {"read_workspace_file"}]
    assert len(body["sources"]) == 1 and body["sources"][0]["path"] == "sample_a.py"
    assert len(body["read_events"]) == 1 and body["read_events"][0]["decision"] == "ALLOW"
    assert body["provider_response_observation"]["provider_id"] == "ollama-cloud"
    assert body["provider_response_observation"]["model_id"] == "parent-fixture"
    assert body["provider_response_observation"]["observed_at"].endswith("Z")
    assert "development_" not in " ".join(tool for phase in phases for tool in phase)


def test_orchestrator_does_not_read_files_when_workspace_read_permission_is_missing(setup):
    f = setup
    calls = []

    def route(provider, model, messages, **kwargs):
        names = {item.get("function", {}).get("name") for item in kwargs.get("tools", [])}
        calls.append(names)
        return {"tool_calls": [{"id": "route-1", "function": {"name": "resolve_control_request", "arguments": {
            "decision": "workspace_read", "reply": "Voy a consultar el archivo solicitado."
        }}}]}

    f["monkeypatch"].setattr(server.provider_runtime, "chat_turn", route)
    response = f["client"].post("/api/chat/control", json={
        "message": "Lee sample_a.py con la herramienta de lectura de workspace y resúmelo.",
        "conversation_id": f["parent"]["id"], "revision": 0,
    })
    assert response.status_code == 200, response.text
    body = response.json()
    assert "No he leído ningún archivo" in body["assistant_message"]
    assert calls == []
    assert body["sources"] == [] and body["read_events"] == []
    assert "provider_response_observation" not in body


def test_unoffered_workspace_handler_fails_closed_before_route_resolution(setup):
    f = setup
    (f["workspace"] / "hint.txt").write_text("Synthetic invoice amount: 17 units.\n", encoding="utf-8")
    permit = server.WORKSPACE_READ_AUTHORIZATIONS.issue(
        f["workspace"], owner_kind="assistant", owner_id="app-assistant",
        conversation_id=f["parent"]["id"], revision=0, paths=["hint.txt"],
    )
    read_calls = []
    original_read = server.read_workspace_file

    def tracked_read(*args, **kwargs):
        read_calls.append(args[1] if len(args) > 1 else kwargs)
        return original_read(*args, **kwargs)

    f["monkeypatch"].setattr(server, "read_workspace_file", tracked_read)
    f["monkeypatch"].setattr(server.provider_runtime, "chat_turn", lambda *args, **kwargs: {
        "tool_calls": [{"function": {"name": "read_workspace_file", "arguments": {"path": "hint.txt"}}}]
    })
    response = f["client"].post("/api/chat/control", json={
        "message": "Explain the current project behavior.", "conversation_id": f["parent"]["id"], "revision": 0,
        "workspace_read_authorization_id": permit["authorization_id"],
    })
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["operation"] == "chat"
    assert "No ejecuté herramientas" in body["assistant_message"]
    assert read_calls == []
    assert body["sources"] == [] and body["read_events"] == []


def test_explicit_read_request_runs_only_named_authorized_workspace_file_tool(setup):
    f = setup
    target = f["workspace"] / "sample_a.py"
    target.write_text("def total():\n    return 17\n", encoding="utf-8")
    permit = server.WORKSPACE_READ_AUTHORIZATIONS.issue(
        f["workspace"], owner_kind="assistant", owner_id="app-assistant",
        conversation_id=f["parent"]["id"], revision=0, paths=["sample_a.py"],
    )
    phases = []

    def read_only(provider, model, messages, **kwargs):
        names = {item.get("function", {}).get("name") for item in kwargs.get("tools", [])}
        phases.append(names)
        assert names == {"read_workspace_file"}
        prior_read = next((message for message in reversed(messages)
                           if message.get("role") == "tool" and message.get("tool_name") == "read_workspace_file"), None)
        if prior_read is None:
            return {"tool_calls": [{"id": "read-1", "function": {"name": "read_workspace_file", "arguments": {
                "path": "sample_a.py", "start_line": 1
            }}}]}
        result = json.loads(prior_read["content"])
        assert result["total_lines"] == 2
        assert "def total()" in result["content"]
        return {"content": "sample_a.py define total(), que devuelve 17; contiene dos líneas.", "tool_calls": []}

    f["monkeypatch"].setattr(server.provider_runtime, "chat_turn", read_only)
    response = f["client"].post("/api/chat/control", json={
        "message": "Lee únicamente sample_a.py con la herramienta de lectura del workspace. Resume su función y el número total exacto de líneas. No uses herramientas development_*.",
        "conversation_id": f["parent"]["id"], "revision": 0,
        "workspace_read_authorization_id": permit["authorization_id"],
    })
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["assistant_message"] == "sample_a.py define total(), que devuelve 17; contiene dos líneas."
    assert phases == [{"read_workspace_file"}, {"read_workspace_file"}]
    assert [item["path"] for item in body["sources"]] == ["sample_a.py"]
    assert [item["decision"] for item in body["read_events"]] == ["ALLOW"]
    assert body["read_events"][0]["total_lines"] == 2
    assert body["read_events"][0]["truncated"] is False


def test_effective_manual_explains_tool_selection_and_permission_boundary():
    manual = (Path(__file__).resolve().parents[1] / "docs" / "public-web" / "MANUAL.md").read_text(encoding="utf-8")
    assert "sin herramientas asignadas" not in manual
    assert "seleccionar las herramientas necesarias entre las que están conectadas al chat de agentes" in manual
    assert "no inicia el turno hijo hasta que confirmes los permisos y la carpeta" in manual
    assert "Las tareas conversacionales dentro del alcance pueden enviarse sin una tarjeta repetida" in manual
    assert "incluido MCP genérico" in manual
