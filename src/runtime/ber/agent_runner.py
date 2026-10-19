"""Server-owned, single-action Agent Runner boundary over BAGO BER.

This module deliberately has no SandboxManager or legacy execution fallback.
Model output is untrusted and must become one typed operation before BER can
prepare it. Human decisions are bound to the server-held proposal/challenge.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import uuid
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from src.context.workspace_binding import WorkspaceBinding, WorkspaceBindingError, bind_workspace, workspace_binding_is_governed
from src.observability.ber_effect_trace import local_trace_from_ber_effect
from src.runtime.ber import BerClient, BerRuntimeError
from src.runtime.ber.client import ARTIFACT_SHA256


MAX_TASK_CHARS = 8_000
MAX_WRITE_CHARS = 32_000
ALLOWED_EFFECTS = frozenset({"filesystem.read", "filesystem.write", "process.inspect", "process.execute"})
BLOCKED_EFFECTS = frozenset({"filesystem.delete", "process.terminate"})
_GIT_INSPECT_ARGV = {
    ("status", "--porcelain=v1", "--untracked-files=all"),
    ("diff", "--name-only"),
    ("rev-parse", "HEAD"),
    ("rev-parse", "--show-toplevel"),
    ("rev-parse", "--abbrev-ref", "HEAD"),
    ("branch", "--show-current"),
}


class AgentRunnerError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _safe_text(value: Any, name: str, *, limit: int = 512) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit or "\x00" in value:
        raise AgentRunnerError("invalid_proposal", f"The proposed {name} is invalid.")
    return value.strip()


def _parse_tool_arguments(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, json.JSONDecodeError):
            raise AgentRunnerError("invalid_proposal", "The provider returned an invalid action proposal.") from None
    if not isinstance(value, dict):
        raise AgentRunnerError("invalid_proposal", "The provider returned an invalid action proposal.")
    return value


def typed_ber_operation(proposal: Mapping[str, Any], *, workspace: Path) -> dict[str, Any]:
    """Map one strict tool proposal to the BER operation envelope."""
    if set(proposal) != {"effect_id", "target", "arguments"}:
        raise AgentRunnerError("unsupported_proposal_shape", "The proposed action has unsupported fields.")
    effect_id = proposal.get("effect_id")
    if not isinstance(effect_id, str) or effect_id in BLOCKED_EFFECTS or effect_id not in ALLOWED_EFFECTS:
        raise AgentRunnerError("effect_not_allowed", "The proposed effect is not available in the BER Agent Runner profile.")
    raw_target = proposal.get("target")
    raw_arguments = proposal.get("arguments")
    if not isinstance(raw_target, dict) or not isinstance(raw_arguments, dict):
        raise AgentRunnerError("invalid_proposal", "The proposed target and arguments must be objects.")

    if effect_id in {"filesystem.read", "filesystem.write"}:
        if set(raw_target) != {"path"}:
            raise AgentRunnerError("invalid_proposal", "Filesystem actions require one workspace-relative path.")
        path = _safe_text(raw_target.get("path"), "path")
        canonical = path.replace("\\", "/")
        if canonical.startswith("/") or re.match(r"^[A-Za-z]:", canonical) or any(part in {"", ".", ".."} for part in canonical.split("/")):
            raise AgentRunnerError("invalid_proposal", "Filesystem paths must be canonical and workspace-relative.")
        target: dict[str, Any] = {"path": canonical}
        if effect_id == "filesystem.read":
            if raw_arguments:
                raise AgentRunnerError("invalid_proposal", "Filesystem reads do not accept arguments.")
            arguments: dict[str, Any] = {}
        else:
            allowed_keys = {"content", "expected_exists", "expected_sha256"}
            if set(raw_arguments) - allowed_keys or not isinstance(raw_arguments.get("content"), str):
                raise AgentRunnerError("invalid_proposal", "Filesystem writes require bounded text content and supported preconditions.")
            content = raw_arguments["content"]
            if len(content) > MAX_WRITE_CHARS:
                raise AgentRunnerError("proposal_too_large", "The proposed file content exceeds the Agent Runner limit.")
            expected_exists = raw_arguments.get("expected_exists", False)
            if not isinstance(expected_exists, bool):
                raise AgentRunnerError("invalid_proposal", "The write precondition is invalid.")
            expected_digest = raw_arguments.get("expected_sha256")
            if expected_exists:
                if not isinstance(expected_digest, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", expected_digest):
                    raise AgentRunnerError("invalid_proposal", "Modifying a file requires its expected SHA-256.")
            elif expected_digest is not None:
                raise AgentRunnerError("invalid_proposal", "A create operation cannot include an existing-file SHA-256.")
            arguments = {"content": content, "expected_exists": expected_exists}
            if expected_digest is not None:
                arguments["expected_sha256"] = expected_digest.lower()
        return {"effect_id": effect_id, "target": target, "arguments": arguments}

    if effect_id == "process.inspect":
        if set(raw_target) != {"executable"} or set(raw_arguments) != {"argv"}:
            raise AgentRunnerError("invalid_proposal", "Process inspection requires a typed executable and argument list.")
        executable = _safe_text(raw_target.get("executable"), "executable", limit=80)
        argv = raw_arguments.get("argv")
        if executable != "git" or not isinstance(argv, list) or not all(isinstance(item, str) for item in argv) or tuple(argv) not in _GIT_INSPECT_ARGV:
            raise AgentRunnerError("process_profile_denied", "That process inspection is not in the fixed read-only profile.")
        return {"effect_id": effect_id, "target": {"executable": executable, "cwd": str(workspace)}, "arguments": {"argv": argv}}

    if set(raw_target) != {"executable"} or set(raw_arguments) != {"argv"}:
        raise AgentRunnerError("invalid_proposal", "Process execution requires a typed executable and argument list.")
    executable = _safe_text(raw_target.get("executable"), "executable", limit=512)
    argv = raw_arguments.get("argv")
    if executable != sys.executable or not isinstance(argv, list) or not all(isinstance(item, str) and "\x00" not in item and len(item) <= 4096 for item in argv):
        raise AgentRunnerError("process_profile_denied", "Only the typed pytest process operation is available.")
    if len(argv) < 2 or argv[:2] != ["-m", "pytest"] or len(argv) > 130:
        raise AgentRunnerError("process_profile_denied", "Only the typed pytest process operation is available.")
    return {"effect_id": effect_id, "target": {"executable": sys.executable, "cwd": str(workspace)}, "arguments": {"argv": argv}}


def _tool_schema() -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": "sandbox.run",
            "description": "Propose one typed filesystem or bounded process operation for BER review. Never propose delete, terminate, shell, command, script, or unregistered effects.",
            "parameters": {
                "type": "object", "additionalProperties": False,
                "required": ["effect_id", "target", "arguments"],
                "properties": {
                    "effect_id": {"type": "string", "enum": sorted(ALLOWED_EFFECTS)},
                    "target": {"type": "object"},
                    "arguments": {"type": "object"},
                },
            },
        },
    }


def _receipt_success(prepared: Mapping[str, Any], execution: Mapping[str, Any]) -> bool:
    request_id = prepared.get("request_id")
    effect_id = prepared.get("effect_id")
    result = execution.get("result")
    if not isinstance(request_id, str) or not request_id or not isinstance(effect_id, str):
        return False
    if execution.get("request_id") != request_id or execution.get("effect_id") != effect_id or not isinstance(result, Mapping):
        return False
    receipt_id = execution.get("receipt_id")
    if not isinstance(receipt_id, str) or not receipt_id or result.get("receipt_id") != receipt_id:
        return False
    if result.get("effect_id") != effect_id or result.get("executed") is not True or result.get("ok") is not True:
        return False
    if not isinstance(execution.get("ber_execution_id"), str) or not execution.get("ber_execution_id"):
        return False
    return True


def _public_execution(execution: Mapping[str, Any]) -> dict[str, Any]:
    authorization = execution.get("authorization")
    authorization = authorization if isinstance(authorization, Mapping) else {}
    return {
        "request_id": execution.get("request_id"),
        "receipt_id": execution.get("receipt_id"),
        "ber_execution_id": execution.get("ber_execution_id"),
        "authorization": {
            key: authorization[key]
            for key in ("state", "permit_id", "decision_id", "proof_id")
            if key in authorization
        },
        "verified_success": False,
    }


class AgentRunner:
    """One WebSocket run with one server-owned BAGO BER client and proposal."""

    def __init__(
        self,
        *,
        load_agent: Callable[[str], Any],
        workspace_root: Callable[[], Path],
        provider_status: Callable[[], Mapping[str, Any]],
        provider_chat_turn: Callable[..., Mapping[str, Any]],
        provider_resolver: Callable[[str], tuple[Callable[[], Mapping[str, Any]], Callable[..., Mapping[str, Any]]]] | None = None,
        ber_client_factory: Callable[..., Any] = BerClient,
        binding_factory: Callable[..., WorkspaceBinding] = bind_workspace,
    ) -> None:
        self._load_agent = load_agent
        self._workspace_root = workspace_root
        self._provider_status = provider_status
        self._provider_chat_turn = provider_chat_turn
        self._provider_resolver = provider_resolver
        self._ber_client_factory = ber_client_factory
        self._binding_factory = binding_factory
        self._client: Any | None = None
        self._binding: WorkspaceBinding | None = None
        self._pending: dict[str, Any] | None = None
        self._run_id = "run_" + uuid.uuid4().hex
        self._agent: Any | None = None

    def _require_current_workspace(self) -> WorkspaceBinding:
        binding = self._binding
        if binding is None or not workspace_binding_is_governed(binding):
            raise AgentRunnerError("workspace_stale", "The bound workspace changed. No further action was executed.")
        return binding

    def start(self, *, agent_id: str, task: str) -> dict[str, Any]:
        if not isinstance(task, str) or not task.strip() or len(task) > MAX_TASK_CHARS:
            raise AgentRunnerError("invalid_task", "Enter a task of up to 8000 characters.")
        try:
            self._agent = self._load_agent(agent_id)
        except Exception:
            raise AgentRunnerError("agent_unavailable", "The saved agent profile could not be loaded.") from None
        config = getattr(self._agent, "config", None)
        provider_id = getattr(config, "provider_id", None) if config is not None else None
        provider_id = provider_id or "ollama-cloud"
        if config is None or provider_id not in {"ollama-cloud", "openai-platform", "github-copilot"}:
            raise AgentRunnerError("provider_unavailable", "The saved agent provider is not available to this runner.")
        if provider_id != "ollama-cloud" and self._provider_resolver is None:
            raise AgentRunnerError("provider_unavailable", "This runner has no route for the saved provider.")
        try:
            if self._provider_resolver:
                status_fn, chat_fn = self._provider_resolver(provider_id)
            else:
                status_fn, chat_fn = self._provider_status, self._provider_chat_turn
            provider = status_fn()
        except Exception:
            raise AgentRunnerError("provider_unavailable", "The configured provider is unavailable.") from None
        if not isinstance(provider, Mapping) or provider.get("state") not in {"configured_unverified", "ready"}:
            raise AgentRunnerError("provider_unavailable", "Configure and verify the saved agent provider before running it.")
        model_id = getattr(config, "model_id", None) or provider.get("model_id")
        if not isinstance(model_id, str) or not model_id:
            raise AgentRunnerError("provider_unavailable", "Select a model for the saved agent before running it.")

        try:
            root = Path(self._workspace_root()).expanduser().resolve(strict=True)
            self._binding = self._binding_factory(root, context_revision="adl-agent-runner-v1")
            if not workspace_binding_is_governed(self._binding):
                raise AgentRunnerError("workspace_stale", "The selected workspace could not be bound safely.")
            self._client = self._ber_client_factory(workspace=self._binding.repository_root)
            ber_status = self._client.start()
            if not isinstance(ber_status, Mapping) or ber_status.get("healthy") is not True:
                raise AgentRunnerError("ber_unavailable", "The pinned BAGO Embedded Runtime is unavailable.")
        except AgentRunnerError:
            self.close()
            raise
        except (OSError, ValueError, WorkspaceBindingError, BerRuntimeError):
            self.close()
            raise AgentRunnerError("runtime_unavailable", "The workspace or pinned BAGO Embedded Runtime is unavailable.") from None

        registered_tools = getattr(config, "tools", [])
        can_propose = isinstance(registered_tools, list) and "sandbox.run" in registered_tools
        messages = [
            {"role": "system", "content": str(getattr(config, "system_prompt", "")) + "\n\n" + (
                "You may propose at most one typed BAGO BER operation using the provided sandbox.run function. The server validates every field and BAGO BER owns authorization and execution. Never claim an operation happened before a matching BER receipt. No shell, command string, delete, terminate, credential access, or other effect is available."
                if can_propose else "This saved profile has no registered BER action tool. Answer the task without proposing or claiming material effects."
            )},
            {"role": "user", "content": task.strip()},
        ]
        try:
            message = chat_fn(
                model_id,
                messages,
                tools=[_tool_schema()] if can_propose else None,
                options={"temperature": 0},
            )
        except Exception:
            self.close()
            raise AgentRunnerError("provider_error", "The configured provider could not complete this task.") from None
        if not isinstance(message, Mapping):
            self.close()
            raise AgentRunnerError("provider_error", "The configured provider returned an invalid response.")
        calls = message.get("tool_calls")
        if not isinstance(calls, list) or not calls:
            answer = message.get("content")
            if not isinstance(answer, str):
                self.close()
                raise AgentRunnerError("provider_response_invalid", "The provider returned neither an answer nor a valid action proposal.")
            self.close()
            return {"type": "task_result", "run_id": self._run_id, "task_status": "answered", "effect_status": "not_started", "answer": answer[:16_000]}
        if not can_propose or len(calls) != 1:
            self.close()
            raise AgentRunnerError("unsupported_proposal", "The profile or provider returned an unsupported number of actions.")
        call = calls[0]
        function = call.get("function") if isinstance(call, Mapping) else None
        if not isinstance(function, Mapping) or function.get("name") != "sandbox.run":
            self.close()
            raise AgentRunnerError("tool_not_registered", "The provider requested a tool that is not registered for this saved profile.")
        proposal = _parse_tool_arguments(function.get("arguments"))
        try:
            binding = self._require_current_workspace()
            operation = typed_ber_operation(proposal, workspace=binding.repository_root)
            prepared = self._client.prepare(operation)
        except AgentRunnerError:
            self.close()
            raise
        except Exception:
            self.close()
            raise AgentRunnerError("ber_prepare_failed", "BAGO BER could not prepare the proposed action.") from None
        if not isinstance(prepared, Mapping) or prepared.get("effect_id") != operation["effect_id"] or not isinstance(prepared.get("request_id"), str) or not prepared.get("request_id") or not isinstance(prepared.get("challenge_id"), str) or not prepared.get("challenge_id") or not isinstance(prepared.get("approval_required"), bool):
            self.close()
            raise AgentRunnerError("ber_prepare_invalid", "BAGO BER returned an incomplete or mismatched proposal.")
        proposal_id = "proposal_" + uuid.uuid4().hex
        operation_digest = hashlib.sha256(json.dumps(operation, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()
        self._pending = {"proposal_id": proposal_id, "operation": operation, "operation_digest": operation_digest, "prepared": dict(prepared)}
        return {
            "type": "proposal",
            "run_id": self._run_id,
            "agent_id": agent_id,
            "proposal_id": proposal_id,
            "request_id": prepared["request_id"],
            "effect_id": prepared["effect_id"],
            "approval_required": prepared["approval_required"],
            "target": dict(operation["target"]),
            "arguments": dict(operation["arguments"]),
            "operation_sha256": operation_digest,
            "world_state_digest": prepared.get("world_state_digest"),
            "expires_at": prepared.get("expires_at"),
            "task_status": "awaiting_review",
            "effect_status": "proposed",
        }

    def decide(self, *, proposal_id: str, decision: str, connected: bool = True) -> dict[str, Any]:
        pending = self._pending
        if pending is None or proposal_id != pending["proposal_id"]:
            raise AgentRunnerError("proposal_not_pending", "This proposal is no longer pending or does not match this run.")
        if not isinstance(decision, str) or decision not in {"approve", "reject", "cancel"}:
            raise AgentRunnerError("invalid_decision", "Decision must be approve, reject, or cancel.")
        # Consume before any operation; replay cannot reuse a challenge.
        self._pending = None
        if decision == "reject":
            self.close()
            return {"type": "rejected", "run_id": self._run_id, "proposal_id": proposal_id, "request_id": pending["prepared"]["request_id"], "effect_status": "not_executed"}
        if decision == "cancel":
            self.close()
            return {"type": "cancelled", "run_id": self._run_id, "proposal_id": proposal_id, "request_id": pending["prepared"]["request_id"], "effect_status": "not_executed"}
        if not connected:
            self.close()
            raise AgentRunnerError("client_disconnected", "The client disconnected before the action could execute.")
        try:
            self._require_current_workspace()
            operation_digest = hashlib.sha256(json.dumps(pending["operation"], sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()
            if operation_digest != pending["operation_digest"]:
                raise AgentRunnerError("proposal_changed", "The reviewed operation no longer matches the prepared proposal.")
            prepared = pending["prepared"]
            approval = None
            if prepared["approval_required"]:
                approval = self._client.approve(prepared["challenge_id"], channel="ui-react")
                if not isinstance(approval, Mapping) or approval.get("request_id") != prepared["request_id"] or approval.get("state") not in {"approved", "authorized", "ALLOW"}:
                    self.close()
                    return {"type": "authorization_denied", "run_id": self._run_id, "proposal_id": proposal_id, "request_id": prepared["request_id"], "authorization": {"state": approval.get("state") if isinstance(approval, Mapping) else "unknown", "decision_id": approval.get("decision_id") if isinstance(approval, Mapping) else None}, "effect_status": "not_executed"}
            self._require_current_workspace()
            execution = self._client.execute(prepared["challenge_id"])
            if not isinstance(execution, Mapping):
                self.close()
                raise AgentRunnerError("ber_execution_invalid", "BAGO BER returned an invalid execution response.")
            public = _public_execution(execution)
            verified = _receipt_success(prepared, execution)
            public["verified_success"] = verified
            public["authorization"].update({
                key: approval[key]
                for key in ("state", "decision_id", "proof_id")
                if isinstance(approval, Mapping) and key in approval and key not in public["authorization"]
            })
            trace = None
            try:
                trace = local_trace_from_ber_effect(
                    prepared,
                    approval,
                    execution,
                    artifact_sha256=ARTIFACT_SHA256,
                ).to_dict()
            except (TypeError, ValueError):
                # A malformed/missing BER execution identity cannot be repaired
                # into a trace or promoted to success.
                verified = False
                public["verified_success"] = False
            self.close()
            return {
                "type": "completed" if verified else "execution_unverified",
                "run_id": self._run_id,
                "proposal_id": proposal_id,
                "request_id": prepared["request_id"],
                "effect_id": prepared["effect_id"],
                "approval": {key: approval[key] for key in ("state", "request_id", "decision_id", "proof_id") if isinstance(approval, Mapping) and key in approval} if approval else None,
                "execution": public,
                "trace": trace,
                "task_status": "effect_completed" if verified else "effect_unverified",
                "effect_status": "success" if verified else "unverified",
            }
        except AgentRunnerError:
            self.close()
            raise
        except Exception:
            self.close()
            raise AgentRunnerError("ber_execution_failed", "BAGO BER could not complete the prepared action. No success is recorded.") from None

    def close(self) -> None:
        self._pending = None
        client = self._client
        self._client = None
        if client is not None:
            try:
                client.close()
            except Exception:
                pass


__all__ = ["AgentRunner", "AgentRunnerError", "typed_ber_operation"]
