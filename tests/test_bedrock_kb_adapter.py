"""Offline governance and normalization tests for the L7 Knowledge Base adapter."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from adapters.bedrock_kb_adapter import (  # noqa: E402
    BedrockKBAdapter,
    BedrockErrorKind,
    BedrockKnowledgeBasePolicy,
)
from orchestration.state_graph import (  # noqa: E402
    AuthorizationDecision,
    ExecutionOutcome,
)


KB_ID = "kb-fixture-001"
MODEL_ARN = "arn:aws:bedrock:eu-west-1::foundation-model/fixture-model"


def _policy(**overrides) -> BedrockKnowledgeBasePolicy:
    values = {
        "knowledge_base_id": KB_ID,
        "generation_model_arn": MODEL_ARN,
        "backoff_seconds": 0.01,
    }
    values.update(overrides)
    return BedrockKnowledgeBasePolicy(**values)


def _reference(
    chunk_id: str = "kb-permit",
    text: str = "A Permit authorizes an execution.",
    score: float = 0.92,
) -> dict:
    return {
        "content": {"text": text},
        "location": {"s3Location": {"uri": f"s3://fixture-kb/{chunk_id}.md"}},
        "score": score,
        "metadata": {
            "chunk_id": chunk_id,
            "authority": "CANONICAL",
            "domain": "governance",
        },
    }


def _retrieve_response() -> dict:
    return {
        "retrievalResults": [
            _reference(),
            _reference(
                "kb-receipt",
                "A receipt records the outcome and evidence references.",
                0.81,
            ),
        ]
    }


class FakeProviderError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.response = {"Error": {"Code": code, "Message": code}}


class FakeKnowledgeBaseClient:
    def __init__(self, *, retrieve=None, generated=None) -> None:
        self.retrieve_responses = list(retrieve or [_retrieve_response()])
        self.generated_responses = list(generated or [])
        self.calls: list[tuple[str, dict]] = []

    def retrieve(self, **kwargs):
        self.calls.append(("retrieve", kwargs))
        response = self.retrieve_responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response

    def retrieve_and_generate(self, **kwargs):
        self.calls.append(("retrieve_and_generate", kwargs))
        response = self.generated_responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response


def _request(adapter: BedrockKBAdapter, *, operation: str = "retrieve", **kwargs):
    return adapter.build_request(
        "How does BAGO preserve evidence?",
        proposed_by="test-agent",
        context_revision="ctx-l7-test",
        operation=operation,
        **kwargs,
    )


def test_request_and_permit_are_scoped_to_knowledge_base_and_operation():
    adapter = BedrockKBAdapter(policy=_policy(), client=FakeKnowledgeBaseClient())

    request = _request(adapter)
    permit = adapter.authorize(request)

    assert request.effect_type.value == "EXTERNAL_API"
    assert request.tool_name == "bedrock.knowledge_base.retrieve"
    assert request.parameters["knowledge_base_id"] == KB_ID
    assert permit.decision is AuthorizationDecision.ALLOW
    assert permit.request_id == request.request_id
    assert f"knowledge_base_{KB_ID}" in permit.constraints


def test_missing_permit_denies_before_bedrock_transport():
    client = FakeKnowledgeBaseClient()
    adapter = BedrockKBAdapter(policy=_policy(), client=client)

    result = adapter.retrieve(_request(adapter), None)

    assert result.receipt.decision is AuthorizationDecision.DENY
    assert result.receipt.execution_outcome is ExecutionOutcome.FAILURE
    assert result.receipt.actual_effect["called"] is False
    assert result.receipt.error_kind is BedrockErrorKind.AUTHORIZATION
    assert client.calls == []


def test_disallowed_knowledge_base_is_denied_even_with_explicit_approval():
    client = FakeKnowledgeBaseClient()
    adapter = BedrockKBAdapter(
        policy=_policy(allowed_knowledge_base_ids=frozenset({"another-kb"})),
        client=client,
    )
    request = _request(adapter)
    permit = adapter.authorize(request, explicit_approval=True)

    result = adapter.retrieve(request, permit)

    assert permit.decision is AuthorizationDecision.DENY
    assert result.receipt.decision is AuthorizationDecision.DENY
    assert "allowlist" in (result.receipt.error_message or "")
    assert client.calls == []


def test_retrieve_normalizes_references_and_metadata_filter_payload():
    client = FakeKnowledgeBaseClient()
    adapter = BedrockKBAdapter(policy=_policy(), client=client)
    request = _request(
        adapter,
        number_of_results=2,
        search_type="HYBRID",
        metadata_filter={"equals": {"key": "domain", "value": "governance"}},
    )

    result = adapter.retrieve(request, adapter.authorize(request))

    assert result.receipt.execution_outcome is ExecutionOutcome.SUCCESS
    assert result.receipt.result_count == 2
    assert [hit.chunk_id for hit in result.hits] == ["kb-permit", "kb-receipt"]
    assert result.hits[0].source_uri == "s3://fixture-kb/kb-permit.md"
    assert "kb=kb-fixture-001" in result.citations[0]
    payload = client.calls[0][1]
    vector = payload["retrievalConfiguration"]["vectorSearchConfiguration"]
    assert payload["knowledgeBaseId"] == KB_ID
    assert payload["retrievalQuery"]["text"] == "How does BAGO preserve evidence?"
    assert vector["numberOfResults"] == 2
    assert vector["overrideSearchType"] == "HYBRID"
    assert vector["filter"]["equals"]["key"] == "domain"


def test_retrieve_and_generate_returns_answer_citations_and_session():
    generated = {
        "output": {"text": "BAGO links the answer to retrieved evidence."},
        "citations": [
            {
                "generatedResponsePart": {
                    "textResponsePart": {"text": "BAGO links the answer."}
                },
                "retrievedReferences": [_reference()],
            }
        ],
        "sessionId": "session-fixture-1",
    }
    client = FakeKnowledgeBaseClient(generated=[generated])
    adapter = BedrockKBAdapter(policy=_policy(), client=client)
    request = _request(
        adapter,
        operation="retrieve_and_generate",
        generation_configuration={"inferenceConfig": {"maxTokens": 128}},
    )

    result = adapter.retrieve_and_generate(request, adapter.authorize(request))

    assert result.answer == "BAGO links the answer to retrieved evidence."
    assert result.session_id == "session-fixture-1"
    assert len(result.citations) == 1
    assert result.receipt.actual_effect["operation"] == "retrieve_and_generate"
    payload = client.calls[0][1]
    config = payload["retrieveAndGenerateConfiguration"]
    assert config["type"] == "KNOWLEDGE_BASE"
    assert config["knowledgeBaseConfiguration"]["knowledgeBaseId"] == KB_ID
    assert config["knowledgeBaseConfiguration"]["modelArn"] == MODEL_ARN
    assert config["knowledgeBaseConfiguration"]["generationConfiguration"]["inferenceConfig"]["maxTokens"] == 128


def test_retrieve_and_generate_requires_a_model_arn():
    adapter = BedrockKBAdapter(policy=_policy(generation_model_arn=""))

    with pytest.raises(ValueError, match="model_arn is required"):
        _request(adapter, operation="retrieve_and_generate")


def test_throttle_retries_with_bounded_backoff_then_succeeds():
    client = FakeKnowledgeBaseClient(
        retrieve=[FakeProviderError("ThrottlingException"), _retrieve_response()]
    )
    sleeps: list[float] = []
    adapter = BedrockKBAdapter(
        policy=_policy(max_attempts=3, backoff_seconds=0.25),
        client=client,
        sleep_fn=sleeps.append,
    )
    request = _request(adapter)

    result = adapter.retrieve(request, adapter.authorize(request))

    assert result.receipt.execution_outcome is ExecutionOutcome.SUCCESS
    assert result.receipt.attempts == 2
    assert sleeps == [0.25]
    assert len(client.calls) == 2


def test_access_denied_is_not_retried():
    client = FakeKnowledgeBaseClient(retrieve=[FakeProviderError("AccessDeniedException")])
    sleeps: list[float] = []
    adapter = BedrockKBAdapter(
        policy=_policy(max_attempts=4),
        client=client,
        sleep_fn=sleeps.append,
    )
    request = _request(adapter)

    result = adapter.retrieve(request, adapter.authorize(request))

    assert result.receipt.execution_outcome is ExecutionOutcome.FAILURE
    assert result.receipt.error_kind is BedrockErrorKind.AUTHORIZATION
    assert result.receipt.attempts == 1
    assert sleeps == []


def test_local_rate_limit_blocks_second_query_before_transport():
    client = FakeKnowledgeBaseClient()
    adapter = BedrockKBAdapter(
        policy=_policy(max_calls_per_window=1),
        client=client,
        monotonic_fn=lambda: 100.0,
    )
    request = _request(adapter)
    permit = adapter.authorize(request)

    first = adapter.retrieve(request, permit)
    second = adapter.retrieve(request, permit)

    assert first.receipt.execution_outcome is ExecutionOutcome.SUCCESS
    assert second.receipt.error_kind is BedrockErrorKind.RATE_LIMIT
    assert second.receipt.actual_effect["called"] is False
    assert len(client.calls) == 1


def test_duplicate_references_are_deduplicated_and_citations_remain_stable():
    duplicate_response = {"retrievalResults": [_reference(), _reference()]}
    client = FakeKnowledgeBaseClient(retrieve=[duplicate_response])
    adapter = BedrockKBAdapter(policy=_policy(), client=client)
    request = _request(adapter)

    result = adapter.retrieve(request, adapter.authorize(request))

    assert len(result.hits) == 1
    assert result.receipt.result_count == 1
    assert result.citations[0].endswith("&chunk=kb-permit")
