from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from src.runtime.ber import agent_runner as runner_module
from src.runtime.ber.agent_runner import AgentRunner, AgentRunnerError, typed_ber_operation


class FakeBerClient:
    def __init__(self, *, workspace: Path, prepared: dict[str, Any] | None = None, execution: dict[str, Any] | None = None, approval: dict[str, Any] | None = None) -> None:
        self.workspace = workspace
        self.prepared = prepared or {
            "challenge_id": "challenge-1", "request_id": "request-1", "effect_id": "filesystem.write",
            "approval_required": True, "world_state_digest": "world-1", "expires_at": "2030-01-01T00:00:00Z",
        }
        result = {"receipt_id": "receipt-1", "effect_id": self.prepared["effect_id"], "executed": True, "ok": True}
        self.execution = execution or {
            "ber_execution_id": "ber-exec-1", "request_id": self.prepared["request_id"], "effect_id": self.prepared["effect_id"], "receipt_id": "receipt-1",
            "authorization": {"state": "consumed", "permit_id": "permit-1", "decision_id": "decision-1", "proof_id": "proof-1", "permit_token": "must-not-leak"},
            "result": result,
        }
        self.approval = approval or {"challenge_id": "challenge-1", "request_id": self.prepared["request_id"], "state": "approved", "decision_id": "decision-1", "proof_id": "proof-1", "permit_token": "must-not-leak"}
        self.calls: list[tuple[str, Any]] = []
        self.closed = False

    def start(self) -> dict[str, Any]:
        self.calls.append(("start", None))
        return {"healthy": True}

    def prepare(self, operation: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(("prepare", operation))
        return dict(self.prepared)

    def approve(self, challenge_id: str, *, channel: str) -> dict[str, Any]:
        self.calls.append(("approve", (challenge_id, channel)))
        return dict(self.approval)

    def execute(self, challenge_id: str) -> dict[str, Any]:
        self.calls.append(("execute", challenge_id))
        return self.execution

    def close(self) -> None:
        self.closed = True
        self.calls.append(("close", None))


def _workspace(tmp_path: Path) -> Path:
    root = tmp_path / "workspace"
    root.mkdir(parents=True)
    subprocess.run(["git", "init", str(root)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "ADL tests"], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.email", "adl-tests@example.invalid"], check=True)
    (root / "seed.txt").write_text("seed", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "seed.txt"], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-m", "seed"], check=True, stdout=subprocess.DEVNULL)
    return root


def _proposal(effect: str = "filesystem.write", *, target: dict[str, Any] | None = None, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    if target is None:
        target = {"path": "output.txt"}
    if arguments is None:
        arguments = {"content": "approved bytes", "expected_exists": False}
    return {"effect_id": effect, "target": target, "arguments": arguments}


def _runner(tmp_path: Path, *, proposal: dict[str, Any] | None = None, client: FakeBerClient | None = None, provider_response: dict[str, Any] | None = None, provider_status: dict[str, Any] | None = None, tools: list[str] | None = None) -> tuple[AgentRunner, FakeBerClient, dict[str, Any]]:
    root = _workspace(tmp_path)
    profile = SimpleNamespace(
        id="agent_0123456789abcdef",
        config=SimpleNamespace(provider_id="ollama-cloud", model_id="model-test", system_prompt="saved profile prompt", tools=tools if tools is not None else ["sandbox.run"]),
    )
    ber = client or FakeBerClient(workspace=root)
    response = provider_response or {"content": "", "tool_calls": [{"function": {"name": "sandbox.run", "arguments": proposal or _proposal()}}]}
    runner = AgentRunner(
        load_agent=lambda _agent_id: profile,
        workspace_root=lambda: root,
        provider_status=lambda: provider_status or {"state": "ready", "model_id": "configured-model"},
        provider_chat_turn=lambda model_id, messages, **kwargs: response,
        ber_client_factory=lambda **kwargs: ber,
    )
    return runner, ber, {"root": root, "profile": profile}


def test_model_proposal_is_prepared_by_ber_and_success_requires_exact_receipt(tmp_path: Path) -> None:
    runner, ber, context = _runner(tmp_path)
    proposal = runner.start(agent_id=context["profile"].id, task="Write the approved report.")
    assert proposal["type"] == "proposal"
    assert proposal["request_id"] == "request-1"
    assert proposal["effect_status"] == "proposed"
    assert "challenge_id" not in proposal
    assert [name for name, _ in ber.calls] == ["start", "prepare"]
    assert ber.calls[1][1]["effect_id"] == "filesystem.write"
    result = runner.decide(proposal_id=proposal["proposal_id"], decision="approve")
    assert result["type"] == "completed"
    assert result["execution"]["verified_success"] is True
    assert result["execution"]["receipt_id"] == "receipt-1"
    assert result["trace"]["run_id"] == "ber-exec-1"
    assert result["trace"]["event_count"] == 4
    assert "permit_token" not in str(result)
    assert [name for name, _ in ber.calls].count("execute") == 1
    assert ("approve", ("challenge-1", "ui-react")) in ber.calls
    assert ("execute", "challenge-1") in ber.calls
    with pytest.raises(AgentRunnerError, match="no longer pending"):
        runner.decide(proposal_id=proposal["proposal_id"], decision="approve")


@pytest.mark.parametrize("decision", ["reject", "cancel"])
def test_rejection_and_cancellation_do_not_approve_or_execute(tmp_path: Path, decision: str) -> None:
    runner, ber, context = _runner(tmp_path)
    proposal = runner.start(agent_id=context["profile"].id, task="Prepare the requested change.")
    result = runner.decide(proposal_id=proposal["proposal_id"], decision=decision)
    assert result["type"] == ("rejected" if decision == "reject" else "cancelled")
    assert result["effect_status"] == "not_executed"
    assert not any(name in {"approve", "execute"} for name, _ in ber.calls)


@pytest.mark.parametrize("provider_id", ["openai-platform", "github-copilot"])
def test_saved_provider_is_resolved_without_using_legacy_callbacks(tmp_path: Path, provider_id: str) -> None:
    runner, ber, context = _runner(tmp_path)
    context["profile"].config.provider_id = provider_id
    calls = []
    runner._provider_resolver = lambda selected: (
        lambda: {"state": "configured_unverified", "model_id": "model-test"},
        lambda model, messages, **kwargs: calls.append((selected, model)) or {"content": "Provider answer"},
    )
    result = runner.start(agent_id=context["profile"].id, task="Answer this task")
    assert calls == [(provider_id, "model-test")]
    assert result["answer"] == "Provider answer" and result["effect_status"] == "not_started"
    assert not any(name in {"prepare", "approve", "execute"} for name, _ in ber.calls)


def test_non_ollama_profile_without_dispatcher_cannot_use_legacy_callbacks(tmp_path: Path) -> None:
    runner, ber, context = _runner(tmp_path)
    context["profile"].config.provider_id = "github-copilot"
    with pytest.raises(AgentRunnerError, match="no route"):
        runner.start(agent_id=context["profile"].id, task="Answer")
    assert ber.calls == []


@pytest.mark.parametrize("proposal", [
    {"effect_id": "filesystem.delete", "target": {"path": "x"}, "arguments": {}},
    {"effect_id": "process.terminate", "target": {"pid": 1}, "arguments": {}},
    {"effect_id": "process.execute", "target": {"executable": "cmd.exe", "command": "whoami"}, "arguments": {"command": "whoami"}},
    {"effect_id": "filesystem.write", "target": {"path": "../outside"}, "arguments": {"content": "x", "expected_exists": False}},
    {"effect_id": "unknown.effect", "target": {}, "arguments": {}},
])
def test_blocked_effects_shell_shapes_and_invalid_paths_never_reach_ber_prepare(tmp_path: Path, proposal: dict[str, Any]) -> None:
    runner, ber, context = _runner(tmp_path, proposal=proposal)
    with pytest.raises(AgentRunnerError):
        runner.start(agent_id=context["profile"].id, task="Run this action.")
    assert not any(name == "prepare" or name == "execute" for name, _ in ber.calls)


def test_process_commands_are_typed_and_allowlisted(tmp_path: Path) -> None:
    root = _workspace(tmp_path)
    inspect = typed_ber_operation(_proposal("process.inspect", target={"executable": "git"}, arguments={"argv": ["status", "--porcelain=v1", "--untracked-files=all"]}), workspace=root)
    assert inspect == {"effect_id": "process.inspect", "target": {"executable": "git", "cwd": str(root)}, "arguments": {"argv": ["status", "--porcelain=v1", "--untracked-files=all"]}}
    pytest_op = typed_ber_operation(_proposal("process.execute", target={"executable": sys.executable}, arguments={"argv": ["-m", "pytest", "-q", "tests"]}), workspace=root)
    assert pytest_op["arguments"]["argv"][:2] == ["-m", "pytest"]
    with pytest.raises(AgentRunnerError, match="fixed read-only profile"):
        typed_ber_operation(_proposal("process.inspect", target={"executable": "git"}, arguments={"argv": ["status", "--untracked-files=all"]}), workspace=root)
    with pytest.raises(AgentRunnerError, match="typed pytest"):
        typed_ber_operation(_proposal("process.execute", target={"executable": sys.executable}, arguments={"argv": ["-c", "print(1)"]}), workspace=root)


def test_approval_is_bound_to_server_held_request_and_uses_no_client_permit(tmp_path: Path) -> None:
    client = FakeBerClient(workspace=tmp_path)
    client.approval["request_id"] = "request-other"
    runner, ber, context = _runner(tmp_path, client=client)
    proposal = runner.start(agent_id=context["profile"].id, task="Write the approved report.")
    result = runner.decide(proposal_id=proposal["proposal_id"], decision="approve")
    assert result["type"] == "authorization_denied"
    assert not any(name == "execute" for name, _ in ber.calls)
    assert ("approve", ("challenge-1", "ui-react")) in ber.calls
    assert "permit_token" not in str(result)


@pytest.mark.parametrize("mutation", ["missing", "request", "outer_receipt", "outer_effect", "effect", "not_executed"])
def test_missing_or_mismatched_receipt_never_records_success(tmp_path: Path, mutation: str) -> None:
    client = FakeBerClient(workspace=tmp_path)
    execution = client.execution
    if mutation == "missing":
        execution["receipt_id"] = ""
        execution["result"]["receipt_id"] = ""
    elif mutation == "request":
        execution["request_id"] = "request-other"
    elif mutation == "outer_receipt":
        execution["receipt_id"] = "receipt-other"
    elif mutation == "outer_effect":
        execution["effect_id"] = "filesystem.delete"
    elif mutation == "effect":
        execution["result"]["effect_id"] = "filesystem.delete"
    elif mutation == "not_executed":
        execution["result"]["executed"] = False
    runner, _, context = _runner(tmp_path, client=client)
    proposal = runner.start(agent_id=context["profile"].id, task="Write the approved report.")
    result = runner.decide(proposal_id=proposal["proposal_id"], decision="approve")
    assert result["type"] == "execution_unverified"
    assert result["effect_status"] == "unverified"
    assert result["execution"]["verified_success"] is False


def test_ber_execution_error_never_records_success(tmp_path: Path) -> None:
    client = FakeBerClient(workspace=tmp_path)

    def fail_execution(_challenge_id: str) -> dict[str, Any]:
        raise RuntimeError("provider credential detail must not escape")

    client.execute = fail_execution  # type: ignore[method-assign]
    runner, ber, context = _runner(tmp_path, client=client)
    proposal = runner.start(agent_id=context["profile"].id, task="Write the approved report.")
    with pytest.raises(AgentRunnerError, match="could not complete") as error:
        runner.decide(proposal_id=proposal["proposal_id"], decision="approve")
    assert "credential detail" not in str(error.value)
    assert ber.closed is True


def test_stale_workspace_and_disconnect_fail_before_execution(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    runner, ber, context = _runner(tmp_path)
    proposal = runner.start(agent_id=context["profile"].id, task="Write the approved report.")
    calls = iter([False])
    monkeypatch.setattr(runner_module, "workspace_binding_is_governed", lambda _binding: next(calls))
    with pytest.raises(AgentRunnerError, match="workspace changed"):
        runner.decide(proposal_id=proposal["proposal_id"], decision="approve")
    assert not any(name in {"approve", "execute"} for name, _ in ber.calls)

    monkeypatch.undo()
    disconnected_runner, disconnected_ber, disconnected_context = _runner(tmp_path / "other")
    disconnected_proposal = disconnected_runner.start(agent_id=disconnected_context["profile"].id, task="Write the approved report.")
    with pytest.raises(AgentRunnerError, match="disconnected"):
        disconnected_runner.decide(proposal_id=disconnected_proposal["proposal_id"], decision="approve", connected=False)
    assert not any(name in {"approve", "execute"} for name, _ in disconnected_ber.calls)


def test_provider_and_runtime_errors_are_redacted_and_do_not_make_success(tmp_path: Path) -> None:
    runner, ber, context = _runner(tmp_path, provider_response={"content": None, "tool_calls": []})
    with pytest.raises(AgentRunnerError):
        runner.start(agent_id=context["profile"].id, task="Do work.")
    assert not any(name in {"prepare", "execute"} for name, _ in ber.calls)

    root = _workspace(tmp_path / "provider")
    profile = SimpleNamespace(id="agent_0123456789abcdef", config=SimpleNamespace(provider_id="ollama-cloud", model_id="model", system_prompt="", tools=["sandbox.run"]))
    def failed_provider(*_args: Any, **_kwargs: Any) -> Any:
        raise RuntimeError("Bearer super-secret-provider-token")
    no_client: list[Any] = []
    failing = AgentRunner(
        load_agent=lambda _agent_id: profile,
        workspace_root=lambda: root,
        provider_status=lambda: {"state": "ready", "model_id": "model"},
        provider_chat_turn=failed_provider,
        ber_client_factory=lambda **_kwargs: no_client.append(FakeBerClient(workspace=root)) or no_client[-1],
    )
    with pytest.raises(AgentRunnerError) as error:
        failing.start(agent_id=profile.id, task="Do work.")
    assert "super-secret-provider-token" not in str(error.value)
    assert no_client[0].closed is True


def test_unavailable_provider_and_profile_without_registered_ber_tool_fail_closed(tmp_path: Path) -> None:
    runner, ber, context = _runner(tmp_path, provider_status={"state": "unsupported_runtime"})
    with pytest.raises(AgentRunnerError, match="provider"):
        runner.start(agent_id=context["profile"].id, task="Do work.")
    assert not ber.calls

    no_tool, no_tool_ber, no_tool_context = _runner(tmp_path / "no-tool", tools=[])
    proposal_response = {"content": "", "tool_calls": [{"function": {"name": "sandbox.run", "arguments": _proposal()}}]}
    no_tool._provider_chat_turn = lambda *_args, **_kwargs: proposal_response
    with pytest.raises(AgentRunnerError, match="unsupported number"):
        no_tool.start(agent_id=no_tool_context["profile"].id, task="Do work.")
    assert not any(name in {"prepare", "execute"} for name, _ in no_tool_ber.calls)
