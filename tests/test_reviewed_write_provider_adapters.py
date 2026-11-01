"""Actual adapter boundaries with simulated host/SDK; no inference or effects."""
import asyncio
import json
from types import SimpleNamespace

import pytest
from src.providers import codex, github_copilot, registration


def schema(name):
    return {"type": "function", "function": {"name": name, "description": "Bounded ADL proposal", "parameters": {"type": "object", "properties": {}, "additionalProperties": False}}}


@pytest.mark.parametrize("name", ["public_web_read", "propose_workspace_write", "resolve_agent_scope", "resolve_agent_result"])
def test_codex_exposes_only_explicit_proposal_schema(monkeypatch, tmp_path, name):
    captured = {}
    class Client:
        cwd = str(tmp_path)
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def request(self, method, params, **_):
            captured[method] = params
            if method == "account/read": return {"account": {"type": "chatgpt"}}
            if method == "thread/start": return {"thread": {"id": "fixture-thread"}}
            return {}
        def notification(self, _deadline):
            if not captured.get("answered"):
                captured["answered"] = True
                return {"method": "item/completed", "params": {"threadId": "fixture-thread", "item": {"type": "agentMessage", "text": json.dumps({"content": "Review only", "tool_calls": [{"name": name, "arguments": "{}"}]})}}}
            return {"method": "turn/completed", "params": {"threadId": "fixture-thread", "turn": {"status": "completed"}}}
    monkeypatch.setattr(codex, "CodexClient", Client)
    result = codex.chat_turn("fixture-model", [{"role": "user", "content": "Prepare only"}], tools=[schema(name)])
    assert result["tool_calls"][0]["function"] == {"name": name, "arguments": {}}
    assert captured["turn/start"]["sandboxPolicy"] == {"type": "readOnly", "networkAccess": False}
    assert captured["thread/start"]["config"]["features"]["shell_tool"] is False
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("name", ["public_web_read", "propose_workspace_write"])
def test_copilot_proposals_are_captured_without_effect(monkeypatch, tmp_path, name):
    copilot = pytest.importorskip("copilot")
    from copilot.tools import ToolInvocation
    captured = {}
    class Session:
        async def send_and_wait(self, _prompt, **_):
            captured["session"]["tools"][0].handler(ToolInvocation(arguments={}))
            await asyncio.Event().wait()
        async def abort(self): captured["aborted"] = True
        async def destroy(self): captured["destroyed"] = True
    class Client:
        def __init__(self, config): captured["config"] = config
        async def __aenter__(self): return self
        async def __aexit__(self, *_): pass
        async def create_session(self, **kwargs):
            captured["session"] = kwargs
            return Session()
    monkeypatch.setattr(copilot, "CopilotClient", Client)
    binding = SimpleNamespace(auth_mode="copilot_cli", credential=None)
    result = github_copilot.chat_turn("fixture-model", [{"role": "user", "content": "Prepare only"}], tools=[schema(name)], binding=binding)
    assert result["tool_calls"][0]["function"] == {"name": name, "arguments": {}}
    assert captured["aborted"] and captured["destroyed"]
    assert captured["session"]["on_permission_request"](SimpleNamespace(kind="shell"), {}).kind == "reject"
    assert captured["session"]["mcp_servers"] == {} and captured["session"]["enable_config_discovery"] is False
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("adapter", ["codex", "copilot"])
def test_arbitrary_apply_or_native_effect_tool_not_admitted(adapter):
    with pytest.raises(registration.RegistrationError) as caught:
        if adapter == "codex":
            codex.chat_turn("fixture-model", [], tools=[schema("apply_write")])
        else:
            github_copilot.chat_turn("fixture-model", [], tools=[schema("apply_write")], binding=SimpleNamespace(auth_mode="copilot_cli", credential=None))
    assert caught.value.code == "invalid_tool_name"
