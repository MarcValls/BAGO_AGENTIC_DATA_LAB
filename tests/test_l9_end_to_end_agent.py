"""L9 end-to-end governed-agent tests using only injected/offline transports."""

from __future__ import annotations

import sys
from pathlib import Path

import anyio
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from adapters.bedrock_provider_adapter import (  # noqa: E402
    BedrockProviderAdapter,
    BedrockProviderPolicy,
)
from adapters.mcp_adapter import GovernedMCPAdapter  # noqa: E402
from agent.governed_knowledge_agent import (  # noqa: E402
    AgentRunStatus,
    GovernedKnowledgeAgent,
)
from metadata.schema import AuthorityLevel  # noqa: E402
from orchestration.state_graph import EffectType, ExecutionOutcome  # noqa: E402
from retrieval.governed_rag import GovernedRAG, RetrievalChunk  # noqa: E402


def _corpus() -> list[RetrievalChunk]:
    return [
        RetrievalChunk(
            chunk_id="session-manager",
            document_id="bago-runtime",
            content="session_manager owns the governed session context and receipts.",
            title="session_manager",
            source_uri="docs/runtime/session_manager.md",
            revision="rc6",
            authority=AuthorityLevel.CANONICAL,
            metadata={"domain": "runtime"},
            domain="runtime",
        ),
        RetrievalChunk(
            chunk_id="workspace-binding",
            document_id="bago-runtime",
            content="workspace_binding binds an execution request to its project context.",
            title="workspace binding",
            source_uri="docs/runtime/workspace_binding.md",
            revision="rc6",
            authority=AuthorityLevel.VERIFIED,
            metadata={"domain": "runtime"},
            domain="runtime",
        ),
        RetrievalChunk(
            chunk_id="canon-rc6",
            document_id="bago-canon",
            content="RC6 requires permits before material effects and receipts after execution.",
            title="BAGO canon RC6",
            source_uri="docs/CANON_BAGO_1.0-RC6.md",
            revision="rc6",
            authority=AuthorityLevel.CANONICAL,
            metadata={"domain": "governance"},
            domain="governance",
        ),
    ]


def _mcp_adapter() -> GovernedMCPAdapter:
    adapter = GovernedMCPAdapter("l9-test-server")
    adapter.discover_tools(
        [
            {
                "name": "get_lab_status",
                "description": "read status",
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": "propose_lab_note",
                "description": "write proposal",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "content": {"type": "string"},
                    },
                    "required": ["path", "content"],
                    "additionalProperties": False,
                },
            },
        ]
    )
    adapter.register_tool(
        "get_lab_status",
        effect_type=EffectType.READ,
        approved_by="l9-test-policy",
    )
    adapter.register_tool(
        "propose_lab_note",
        effect_type=EffectType.WRITE,
        approved_by="l9-test-policy",
    )
    return adapter


class FakeMCPSession:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def call_tool(self, **kwargs):
        self.calls.append(kwargs)
        return {"status": "ok", "tool": kwargs["name"]}


class FakeBedrockClient:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def converse(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "output": {
                "message": {
                    "content": [{"text": "Fixture model answer; citations remain BAGO-owned."}]
                }
            },
            "stopReason": "end_turn",
            "usage": {"inputTokens": 8, "outputTokens": 7},
        }


def _agent(*, mcp=False, session=None, bedrock=None) -> GovernedKnowledgeAgent:
    return GovernedKnowledgeAgent(
        GovernedRAG(_corpus()),
        mcp_adapter=_mcp_adapter() if mcp else None,
        mcp_session=session,
        bedrock_adapter=bedrock,
    )


def _invoke(agent: GovernedKnowledgeAgent, query: str, **kwargs):
    async def call():
        return await agent.run(query, **kwargs)

    return anyio.run(call)


def test_technical_query_retrieves_citations_and_executes_scoped_read():
    session = FakeMCPSession()
    result = _invoke(
        _agent(mcp=True, session=session),
        "¿Cómo funciona session_manager en BAGO?",
    )

    assert result.status is AgentRunStatus.COMPLETED
    assert result.intent.value == "reasoning"
    assert result.citations
    read = next(item for item in result.proposals if item.request.tool_name == "get_lab_status")
    assert read.decision.value == "ALLOW"
    assert read.called is True
    assert read.outcome is ExecutionOutcome.SUCCESS
    assert len(result.mcp_receipts) == 1
    assert session.calls == [{"name": "get_lab_status", "arguments": {}}]


def test_implementation_query_proposes_create_and_blocks_mcp_write_before_transport():
    session = FakeMCPSession()
    result = _invoke(
        _agent(mcp=True, session=session),
        "Crea un test para workspace_binding",
    )

    assert result.status is AgentRunStatus.PENDING_AUTHORIZATION
    file_proposal = next(item for item in result.proposals if item.request.tool_name == "file_creator")
    assert file_proposal.request.effect_type is EffectType.CREATE
    assert file_proposal.decision.value == "REQUIRE_HUMAN"
    assert "WorkspaceBinding.from_git" in file_proposal.request.parameters["content"]
    assert "workspace_binding_is_governed(binding)" in file_proposal.request.parameters["content"]
    compile(file_proposal.request.parameters["content"], "<workspace_binding proposal>", "exec")
    mcp_write = next(item for item in result.proposals if item.request.tool_name == "propose_lab_note")
    assert mcp_write.decision.value == "REQUIRE_HUMAN"
    assert mcp_write.called is False
    assert session.calls == []
    assert any(receipt.tool_name == "file_creator" for receipt in result.decision_receipts)
    assert any(receipt.tool_name == "propose_lab_note" for receipt in result.mcp_receipts)
    assert all(receipt.actual_effect["called"] is False for receipt in result.mcp_receipts)
    assert "no se creó ningún archivo" in result.answer


def test_architecture_query_prepares_external_issue_without_sending_it():
    result = _invoke(_agent(), "¿BAGO cumple el canon RC6?")

    assert result.status is AgentRunStatus.PENDING_AUTHORIZATION
    issue = next(item for item in result.proposals if item.request.tool_name == "github.create_issue")
    assert issue.request.effect_type is EffectType.EXTERNAL_API
    assert issue.decision.value == "REQUIRE_HUMAN"
    assert issue.called is False
    assert result.decision_receipts[0].actual_effect["called"] is False
    assert "no se envió ningún issue" in result.answer


def test_bedrock_generation_is_a_scoped_provider_call_with_tool_config():
    client = FakeBedrockClient()
    adapter = BedrockProviderAdapter(
        client=client,
        policy=BedrockProviderPolicy(
            allowed_model_ids=frozenset({"fixture.model"}),
            backoff_seconds=0,
        ),
    )
    result = _invoke(
        _agent(bedrock=adapter),
        "¿Cómo funciona session_manager en BAGO?",
        model_id="fixture.model",
        use_bedrock=True,
    )

    assert result.status is AgentRunStatus.COMPLETED
    provider = next(item for item in result.proposals if item.transport == "bedrock")
    assert provider.decision.value == "ALLOW"
    assert provider.called is True
    assert provider.outcome is ExecutionOutcome.SUCCESS
    assert result.provider_result is not None
    assert result.provider_result.receipt.actual_effect["called"] is True
    assert client.calls[0]["toolConfig"]["tools"]
    assert "Fixture model answer" in result.answer


def test_bedrock_requested_without_model_is_reported_without_transport():
    result = _invoke(
        _agent(bedrock=BedrockProviderAdapter()),
        "¿Cómo funciona session_manager en BAGO?",
        use_bedrock=True,
    )

    assert result.status is AgentRunStatus.FAILED
    assert result.errors == ("Bedrock requested without model_id",)


def test_run_id_is_stable_for_same_query_and_context_revision():
    agent = _agent()
    first = _invoke(agent, "¿Qué exige el canon RC6?", context_revision="ctx-test")
    second = _invoke(agent, "¿Qué exige el canon RC6?", context_revision="ctx-test")

    assert first.run_id == second.run_id
    assert first.citations == second.citations


def test_empty_query_is_rejected_before_graph_execution():
    with pytest.raises(ValueError, match="vacío"):
        _invoke(_agent(), "   ")
