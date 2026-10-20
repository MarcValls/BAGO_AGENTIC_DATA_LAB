"""Provider contract checks with simulated HTTP/SDK responses, never live credentials."""
from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from src.api import server
from src.conversations import ConversationStore
from src.providers import github_copilot, openai_platform, registration, runtime
from src.runtime.ber.agent_runner import _tool_schema

SECRET = "TEST_CREDENTIAL_NEVER_EXPOSE"


@pytest.fixture
def registry(monkeypatch, tmp_path):
    secrets = {}
    keyring = SimpleNamespace(
        get_password=lambda service, user: secrets.get((service, user)),
        set_password=lambda service, user, secret: secrets.__setitem__((service, user), secret),
    )
    monkeypatch.setattr(registration, "REGISTRY_PATH", tmp_path / "registry.json")
    monkeypatch.setattr(registration, "_secure_keyring", lambda: keyring)
    return tmp_path


def saved(provider="openai-platform", mode="api_key"):
    return registration.save_registration(provider, mode, "gpt-test", None, SECRET if mode in {"api_key", "token"} else None)


def completion(content="OK", calls=None):
    return {"choices": [{"finish_reason": "tool_calls" if calls else "stop", "message": {"content": content, "tool_calls": calls or []}}]}


def http_response(body=None, status=200):
    return SimpleNamespace(status_code=status, ok=200 <= status < 300, json=lambda: body)


def test_support_is_visible_before_registration_and_other_providers_remain_separate(registry):
    for provider in ("openai-platform", "github-copilot"):
        status = registration.status(provider)
        assert status["state"] == "not_configured"
        assert status["runtime_support"] == "chat_and_agent_runner"
    assert registration.status("codex")["runtime_support"] == "chat_and_agent_runner"


def test_live_check_performs_inference_and_only_persists_non_secret_confirmation(registry, monkeypatch):
    saved()
    calls = []
    def post(url, **kwargs):
        calls.append((url, kwargs))
        return http_response(completion())
    monkeypatch.setattr(openai_platform.requests, "post", post)
    result = runtime.verify("openai-platform")
    assert result["state"] == "ready" and result["generation_performed"] is True
    assert result["last_verified_at"]
    url, request = calls[0]
    assert url == "https://api.openai.com/v1/chat/completions"
    assert request["allow_redirects"] is False
    assert request["headers"]["Authorization"] == f"Bearer {SECRET}"
    assert request["json"]["messages"][-1]["role"] == "user"
    assert request["json"]["max_completion_tokens"] == 1024
    assert SECRET not in json.dumps(result)
    assert SECRET not in registration.REGISTRY_PATH.read_text(encoding="utf-8")


def test_failed_authentication_removes_previous_ready_state(registry, monkeypatch):
    saved()
    monkeypatch.setattr(openai_platform.requests, "post", lambda *args, **kwargs: http_response(completion()))
    runtime.verify("openai-platform")
    monkeypatch.setattr(openai_platform.requests, "post", lambda *args, **kwargs: http_response({"error": SECRET}, 401))
    with pytest.raises(runtime.ProviderRuntimeError) as failure:
        runtime.verify("openai-platform")
    assert SECRET not in str(failure.value)
    status = registration.status("openai-platform")
    assert status["state"] == "needs_authentication" and not status["last_verified_at"]


def test_in_flight_request_cannot_verify_a_replaced_credential(registry, monkeypatch):
    saved()
    def post(*args, **kwargs):
        registration.save_registration("openai-platform", "api_key", "gpt-test", None, "REPLACEMENT_TEST_SECRET")
        return http_response(completion())
    monkeypatch.setattr(openai_platform.requests, "post", post)
    with pytest.raises(runtime.ProviderRuntimeError, match="changed"):
        runtime.verify("openai-platform")
    assert registration.status("openai-platform")["state"] == "configured_unverified"


@pytest.mark.parametrize("body", [None, {"choices": []}, completion(content=123), completion(content=""), {"choices": [{"finish_reason": "length", "message": {"content": ""}}]}])
def test_invalid_or_incomplete_responses_never_confirm_access(registry, monkeypatch, body):
    saved()
    monkeypatch.setattr(openai_platform.requests, "post", lambda *args, **kwargs: http_response(body))
    with pytest.raises(runtime.ProviderRuntimeError):
        runtime.verify("openai-platform")
    assert registration.status("openai-platform")["state"] == "configured_unverified"


def test_malformed_tool_name_after_a_success_clears_ready(registry, monkeypatch):
    saved()
    monkeypatch.setattr(openai_platform.requests, "post", lambda *args, **kwargs: http_response(completion()))
    runtime.verify("openai-platform")
    assert registration.status("openai-platform")["state"] == "ready"
    malformed = completion("", [{"id": "bad-1", "function": {"name": {}, "arguments": "{}"}}])
    monkeypatch.setattr(openai_platform.requests, "post", lambda *args, **kwargs: http_response(malformed))
    with pytest.raises(runtime.ProviderRuntimeError) as error:
        runtime.verify("openai-platform")
    assert error.value.code == "provider_response_invalid"
    assert registration.status("openai-platform")["state"] == "configured_unverified"


def test_unexpected_adapter_error_is_safe_and_clears_ready(registry, monkeypatch):
    saved()
    monkeypatch.setattr(openai_platform, "chat_turn", lambda *args, **kwargs: {"content": "OK"})
    runtime.verify("openai-platform")
    def unexpected(*args, **kwargs):
        raise TypeError(SECRET)
    monkeypatch.setattr(openai_platform, "chat_turn", unexpected)
    with pytest.raises(runtime.ProviderRuntimeError) as error:
        runtime.verify("openai-platform")
    assert SECRET not in str(error.value)
    assert registration.status("openai-platform")["state"] == "configured_unverified"


def test_openai_tool_names_are_adapted_and_return_to_the_original_ber_contract(registry, monkeypatch):
    saved()
    proposal = {"effect_id": "filesystem.read", "target": {"path": "seed.txt"}, "arguments": {}}
    def post(*args, **kwargs):
        assert kwargs["json"]["tools"][0]["function"]["name"] == "adl_sandbox_run"
        return http_response(completion("", [{"id": "call-1", "type": "function", "function": {"name": "adl_sandbox_run", "arguments": json.dumps(proposal)}}]))
    monkeypatch.setattr(openai_platform.requests, "post", post)
    turn = runtime.chat_turn("openai-platform", "gpt-test", [{"role": "user", "content": "Inspect seed.txt"}], tools=[_tool_schema()])
    assert turn["tool_calls"][0]["function"] == {"name": "sandbox.run", "arguments": proposal}


def test_openai_workspace_loop_returns_real_authorized_read_to_the_same_call(registry, monkeypatch):
    saved()
    (registry / "evidence.txt").write_text("authorized evidence", encoding="utf-8")
    calls = []
    def post(*args, **kwargs):
        messages = kwargs["json"]["messages"]
        calls.append(messages)
        if len(calls) == 1:
            return http_response(completion("", [{"id": "read-1", "type": "function", "function": {"name": "read_workspace_file", "arguments": '{"path":"evidence.txt"}'}}]))
        assert messages[-1]["tool_call_id"] == "read-1"
        assert "authorized evidence" in messages[-1]["content"]
        assert isinstance(messages[-2]["tool_calls"][0]["function"]["arguments"], str)
        assert "tool_name" not in messages[-1]
        return http_response(completion("Read the authorized evidence."))
    monkeypatch.setattr(openai_platform.requests, "post", post)
    answer, sources, events, _ = asyncio.run(server._chat_with_workspace_read(
        "gpt-test", [{"role": "user", "content": "Read the file"}], ["evidence.txt"],
        provider_id="openai-platform", workspace_root=registry,
    ))
    assert answer == "Read the authorized evidence."
    assert sources and events[0]["decision"] == "ALLOW" and len(calls) == 2


def test_bounded_tool_loop_final_answer_never_falls_back_to_another_provider(registry, monkeypatch):
    monkeypatch.setattr(server, "MAX_TOOL_ROUNDS", 1)
    monkeypatch.setattr(runtime, "chat_turn", lambda *args, **kwargs: {"tool_calls": [{"function": {"name": "unknown", "arguments": {}}}]})
    calls = []
    monkeypatch.setattr(runtime, "chat", lambda provider, model, messages: calls.append(provider) or "Done")
    answer, _, _, _ = asyncio.run(server._chat_with_workspace_read("gpt-test", [], [], provider_id="github-copilot", workspace_root=registry))
    assert answer == "Done" and calls == ["github-copilot"]


@pytest.mark.parametrize("mode", ["copilot_cli", "token"])
def test_copilot_sdk_only_exposes_capture_tools_and_rejects_runtime_effects(registry, monkeypatch, mode):
    copilot = pytest.importorskip("copilot")
    from copilot.tools import ToolInvocation
    saved("github-copilot", mode)
    monkeypatch.setenv("GITHUB_TOKEN", "AMBIENT_SECRET_MUST_NOT_BE_USED")
    captured_config = {}
    proposal = {"effect_id": "filesystem.write", "target": {"path": "never-created.txt"}, "arguments": {"content": "x"}}
    class Session:
        async def send_and_wait(self, prompt, **kwargs):
            captured_config["session"]["tools"][0].handler(ToolInvocation(arguments=proposal))
            await asyncio.Event().wait()
        async def abort(self):
            captured_config["aborted"] = True
        async def destroy(self):
            captured_config["destroyed"] = True
    class Client:
        def __init__(self, config):
            captured_config["client"] = config
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            return None
        async def create_session(self, **kwargs):
            captured_config["session"] = kwargs
            return Session()
    monkeypatch.setattr(copilot, "CopilotClient", Client)
    turn = runtime.chat_turn("github-copilot", "gpt-test", [{"role": "system", "content": "Saved ADL profile"}, {"role": "user", "content": "Propose a file"}], tools=[_tool_schema()])
    session, config = captured_config["session"], captured_config["client"]
    assert session["available_tools"] == ["adl_sandbox_run"]
    assert session["on_permission_request"](SimpleNamespace(kind="shell"), {}).kind == "reject"
    assert session["enable_config_discovery"] is False and session["mcp_servers"] == {}
    assert "Saved ADL profile" in session["system_message"]["content"]
    assert "GITHUB_TOKEN" not in config.env
    assert config.github_token == (SECRET if mode == "token" else None)
    assert config.use_logged_in_user is (mode == "copilot_cli")
    assert captured_config["aborted"] and captured_config["destroyed"]
    assert not (registry / "never-created.txt").exists()
    assert turn["tool_calls"][0]["function"] == {"name": "sandbox.run", "arguments": proposal}


def test_registered_agent_saves_selected_provider_and_rejects_model_mismatch(registry, monkeypatch):
    saved()
    monkeypatch.setattr(server, "AGENTS_DIR", registry / "agents")
    payload = {"name": "GPT agent", "description": "Review evidence", "type": "tool", "system_prompt": "Review only", "provider_id": "openai-platform", "model_id": "gpt-test"}
    result = asyncio.run(server.create_agent(server.AgentCreateRequest(**payload)))
    assert result.config.provider_id == "openai-platform" and result.config.model_id == "gpt-test"
    payload["model_id"] = "another-model"
    with pytest.raises(server.HTTPException) as failure:
        asyncio.run(server.create_agent(server.AgentCreateRequest(**payload)))
    assert failure.value.detail["code"] == "model_registration_mismatch"


@pytest.mark.parametrize("provider_id", ["openai-platform", "github-copilot"])
def test_http_registration_verify_profile_and_agent_chat_use_selected_provider(registry, monkeypatch, provider_id):
    adapter = openai_platform if provider_id == "openai-platform" else github_copilot
    calls = []
    def simulate_provider(model, messages, **kwargs):
        calls.append((kwargs["binding"].provider_id, model))
        return {"content": "Provider response", "tool_calls": []}
    monkeypatch.setattr(adapter, "chat_turn", simulate_provider)
    monkeypatch.setattr(server, "AGENTS_DIR", registry / "agents")
    monkeypatch.setattr(server, "AGENT_CHAT_TRACE_DIR", registry / "traces")
    monkeypatch.setattr(server, "current_workspace_root", lambda: registry)
    monkeypatch.setenv("BAGO_OTEL_EXPORTER_OTLP_ENDPOINT", "")
    store = ConversationStore(registry / "conversations.sqlite3")
    monkeypatch.setattr(server, "CONVERSATIONS", store)
    with TestClient(server.app) as client:
        mode = "api_key" if provider_id == "openai-platform" else "token"
        result = client.put(f"/api/providers/registry/{provider_id}", json={"auth_mode": mode, "model_id": "gpt-test", "api_key": SECRET})
        assert result.status_code == 200 and result.json()["state"] == "configured_unverified"
        result = client.post(f"/api/providers/registry/{provider_id}/verify", json={"model_id": "gpt-test"})
        assert result.status_code == 200 and result.json()["generation_performed"] is True
        result = client.post("/api/agents/create", json={"name": "Provider agent", "description": "Review", "type": "tool", "system_prompt": "Review", "provider_id": provider_id, "model_id": "gpt-test"})
        assert result.status_code == 200
        agent_id = result.json()["id"]
        conversation = store.create("agent", agent_id)
        result = client.post(f"/api/agents/{agent_id}/chat", json={"message": "Hello", "conversation_id": conversation["id"], "revision": 0})
        assert result.status_code == 200
        assert result.json()["provider_id"] == provider_id and result.json()["source"] == provider_id
        assert result.json()["conversation"]["messages"][-1]["content"] == "Provider response"
        assert SECRET not in result.text
    assert calls == [(provider_id, "gpt-test"), (provider_id, "gpt-test")]


def test_editing_legacy_agent_does_not_require_or_pin_a_provider(registry, monkeypatch):
    monkeypatch.setattr(server, "AGENTS_DIR", registry / "agents")
    config = server.AgentConfig(name="Legacy", description="Review", type="tool", system_prompt="Review only")
    current = server._write_agent(config)
    def unexpected_status(*args):
        pytest.fail("Editing an unchanged legacy provider pair must not require configured credentials")
    monkeypatch.setattr(runtime, "status", unexpected_status)
    updated = asyncio.run(server.update_agent(current.id, config.model_copy(update={"name": "Renamed"})))
    assert updated.config.name == "Renamed"
    assert updated.config.provider_id is None and updated.config.model_id is None
