"""Offline L6 tests for the governed AWS Bedrock provider boundary."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from adapters.bedrock_provider_adapter import (  # noqa: E402
    BedrockErrorKind,
    BedrockProviderAdapter,
    BedrockProviderPolicy,
)
from orchestration.state_graph import (  # noqa: E402
    AuthorizationDecision,
    ExecutionOutcome,
)


MODEL_ID = "fixture.bedrock-model"


def _messages(text: str = "hello") -> list[dict]:
    return [{"role": "user", "content": [{"text": text}]}]


def _policy(**overrides) -> BedrockProviderPolicy:
    values = {
        "allowed_model_ids": frozenset({MODEL_ID}),
        "backoff_seconds": 0.01,
    }
    values.update(overrides)
    return BedrockProviderPolicy(**values)


def _request(adapter: BedrockProviderAdapter, *, operation: str = "converse"):
    return adapter.build_execution_request(
        MODEL_ID,
        _messages(),
        proposed_by="test-agent",
        context_revision="ctx-l6-test",
        system=[{"text": "Be concise"}],
        inference_config={"maxTokens": 32, "temperature": 0.0},
        operation=operation,
    )


class FakeProviderError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.response = {"Error": {"Code": code, "Message": code}}


class FakeBedrockClient:
    def __init__(self, responses=None, stream=None) -> None:
        self.responses = list(responses or [])
        self.stream = stream
        self.calls: list[tuple[str, dict]] = []

    def converse(self, **kwargs):
        self.calls.append(("converse", kwargs))
        if self.responses:
            response = self.responses.pop(0)
            if isinstance(response, BaseException):
                raise response
            return response
        return {
            "output": {"message": {"role": "assistant", "content": [{"text": "ok"}]}},
            "stopReason": "end_turn",
            "usage": {"inputTokens": 4, "outputTokens": 2, "totalTokens": 6},
        }

    def converse_stream(self, **kwargs):
        self.calls.append(("converse_stream", kwargs))
        return {"stream": list(self.stream or [])}


def test_request_and_permit_are_bound_to_external_api_and_model_scope():
    adapter = BedrockProviderAdapter(client=FakeBedrockClient(), policy=_policy())

    request = _request(adapter)
    permit = adapter.authorize(request)

    assert request.effect_type.value == "EXTERNAL_API"
    assert request.tool_name == "bedrock.converse"
    assert request.parameters["model_id"] == MODEL_ID
    assert permit.decision is AuthorizationDecision.ALLOW
    assert permit.request_id == request.request_id
    assert f"model_{MODEL_ID}" in permit.constraints


def test_missing_permit_is_denied_before_transport_call():
    client = FakeBedrockClient()
    adapter = BedrockProviderAdapter(client=client, policy=_policy())

    result = adapter.converse(_request(adapter), None)

    assert result.receipt.decision is AuthorizationDecision.DENY
    assert result.receipt.execution_outcome is ExecutionOutcome.FAILURE
    assert result.receipt.actual_effect["called"] is False
    assert result.receipt.error_kind is BedrockErrorKind.AUTHORIZATION
    assert client.calls == []


def test_disallowed_model_denies_even_when_explicit_approval_is_requested():
    client = FakeBedrockClient()
    adapter = BedrockProviderAdapter(
        client=client,
        policy=BedrockProviderPolicy(
            allowed_model_ids=frozenset({"another.model"}),
        ),
    )
    request = _request(adapter)
    permit = adapter.authorize(request, explicit_approval=True)

    result = adapter.converse(request, permit)

    assert permit.decision is AuthorizationDecision.DENY
    assert result.receipt.decision is AuthorizationDecision.DENY
    assert "allowlist" in (result.receipt.error_message or "")
    assert client.calls == []


def test_converse_normalizes_text_usage_and_configured_cost():
    client = FakeBedrockClient(
        responses=[
            {
                "output": {
                    "message": {
                        "role": "assistant",
                        "content": [{"text": "hello "}, {"text": "from Bedrock"}],
                    }
                },
                "stopReason": "end_turn",
                "usage": {"inputTokens": 100, "outputTokens": 50},
            }
        ]
    )
    adapter = BedrockProviderAdapter(
        client=client,
        policy=_policy(input_cost_per_1k_tokens=2.0, output_cost_per_1k_tokens=4.0),
    )
    request = _request(adapter)
    permit = adapter.authorize(request)

    result = adapter.converse(request, permit)

    assert result.text == "hello from Bedrock"
    assert result.stop_reason == "end_turn"
    assert result.usage.input_tokens == 100
    assert result.usage.output_tokens == 50
    assert result.usage.total_tokens == 150
    assert result.receipt.cost_usd == pytest.approx(0.4)
    assert result.receipt.execution_outcome is ExecutionOutcome.SUCCESS
    assert result.receipt.actual_effect["called"] is True
    assert client.calls[0][1]["modelId"] == MODEL_ID
    assert client.calls[0][1]["inferenceConfig"]["maxTokens"] == 32


def test_throttle_retries_with_bounded_backoff_then_succeeds():
    client = FakeBedrockClient(
        responses=[
            FakeProviderError("ThrottlingException"),
            {
                "output": {"message": {"content": [{"text": "recovered"}]}},
                "usage": {"inputTokens": 1, "outputTokens": 1},
            },
        ]
    )
    sleeps: list[float] = []
    adapter = BedrockProviderAdapter(
        client=client,
        policy=_policy(max_attempts=3, backoff_seconds=0.25),
        sleep_fn=sleeps.append,
    )
    request = _request(adapter)

    result = adapter.converse(request, adapter.authorize(request))

    assert result.text == "recovered"
    assert result.receipt.attempts == 2
    assert sleeps == [0.25]
    assert len(client.calls) == 2


def test_timeout_becomes_controlled_failure_after_retry_budget():
    client = FakeBedrockClient(
        responses=[TimeoutError("read timeout"), TimeoutError("read timeout")]
    )
    sleeps: list[float] = []
    adapter = BedrockProviderAdapter(
        client=client,
        policy=_policy(max_attempts=2, backoff_seconds=0.1),
        sleep_fn=sleeps.append,
    )
    request = _request(adapter)

    result = adapter.converse(request, adapter.authorize(request))

    assert result.receipt.execution_outcome is ExecutionOutcome.FAILURE
    assert result.receipt.error_kind is BedrockErrorKind.TIMEOUT
    assert result.receipt.attempts == 2
    assert result.receipt.actual_effect["called"] is True
    assert sleeps == [0.1]


def test_access_denied_is_not_retried():
    client = FakeBedrockClient(responses=[FakeProviderError("AccessDeniedException")])
    sleeps: list[float] = []
    adapter = BedrockProviderAdapter(
        client=client,
        policy=_policy(max_attempts=4),
        sleep_fn=sleeps.append,
    )
    request = _request(adapter)

    result = adapter.converse(request, adapter.authorize(request))

    assert result.receipt.error_kind is BedrockErrorKind.AUTHORIZATION
    assert result.receipt.attempts == 1
    assert sleeps == []
    assert len(client.calls) == 1


def test_local_rate_limit_blocks_second_call_before_transport():
    client = FakeBedrockClient()
    adapter = BedrockProviderAdapter(
        client=client,
        policy=_policy(max_calls_per_window=1),
        monotonic_fn=lambda: 100.0,
    )
    request = _request(adapter)
    permit = adapter.authorize(request)

    first = adapter.converse(request, permit)
    second = adapter.converse(request, permit)

    assert first.receipt.execution_outcome is ExecutionOutcome.SUCCESS
    assert second.receipt.error_kind is BedrockErrorKind.RATE_LIMIT
    assert second.receipt.actual_effect["called"] is False
    assert len(client.calls) == 1


def test_converse_stream_collects_text_usage_and_receipt():
    client = FakeBedrockClient(
        stream=[
            {"messageStart": {"role": "assistant"}},
            {"contentBlockDelta": {"delta": {"text": "streamed "}}},
            {"contentBlockDelta": {"delta": {"text": "answer"}}},
            {"messageStop": {"stopReason": "end_turn"}},
            {"metadata": {"usage": {"inputTokens": 5, "outputTokens": 2}}},
        ]
    )
    adapter = BedrockProviderAdapter(client=client, policy=_policy())
    request = _request(adapter, operation="converse_stream")

    result = adapter.converse_stream(request, adapter.authorize(request))

    assert result.text == "streamed answer"
    assert result.stop_reason == "end_turn"
    assert result.usage.total_tokens == 7
    assert len(result.streamed_events) == 5
    assert result.receipt.execution_outcome is ExecutionOutcome.SUCCESS
    assert client.calls[0][0] == "converse_stream"


def test_malformed_message_is_rejected_before_request_creation():
    adapter = BedrockProviderAdapter(policy=_policy())

    with pytest.raises(ValueError, match="role=user or role=assistant"):
        adapter.build_execution_request(
            MODEL_ID,
            [{"role": "system", "content": [{"text": "bad"}]}],
            proposed_by="test-agent",
            context_revision="ctx-l6-test",
        )
