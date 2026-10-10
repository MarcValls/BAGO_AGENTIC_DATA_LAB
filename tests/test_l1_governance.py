"""Behavioral evidence for the original L1 governance reference claims.

These tests call production boundaries. Some controls live in later modules
(sandbox, retrieval, MCP and Bedrock); their passing tests do not prove that
the L1 StateGraph is wired to those boundaries. The goal evidence records that
integration boundary explicitly.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

import anyio

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.adapters.bedrock_provider_adapter import (
    BedrockErrorKind,
    BedrockProviderAdapter,
    BedrockProviderPolicy,
)
from src.adapters.mcp_adapter import GovernedMCPAdapter
from src.execution import ExecutionGateway
from metadata.schema import AuthorityLevel
from orchestration.state_graph import (
    AuthorizationDecision as MCPAuthorizationDecision,
    EffectType as MCPEffectType,
    ExecutionOutcome as MCPExecutionOutcome,
    ExecutionRequest as MCPExecutionRequest,
)
from src.orchestration.state_graph import (
    AgentState,
    AuthorizationDecision,
    EffectType,
    ExecutionOutcome,
    ExecutionRequest,
    Permit,
    authorization_gate,
    build_governed_agent_graph,
    execute_actions,
)
from retrieval.governed_rag import GovernedRAG, MetadataFilter, RetrievalChunk
from src.sandbox import (
    Capability,
    FilesystemOperation,
    FilesystemRequest,
    SandboxManager,
    SandboxRequest,
    SandboxStatus,
)


def _permit_for_read(root: Path, request_id: str) -> Permit:
    now = datetime.now(timezone.utc)
    return Permit(
        permit_id=f"permit-{request_id}",
        request_id=request_id,
        decision=AuthorizationDecision.ALLOW,
        rationale="bounded test read",
        constraints=[
            "sandbox_profile=read_only_agent",
            f"workspace_root={root.resolve()}",
            f"capability={Capability.FILESYSTEM_READ.value}",
        ],
        issued_at=now.isoformat(),
        expires_at=(now + timedelta(minutes=5)).isoformat(),
        signed_by="l1-test-authority",
    )


def test_langgraph_cannot_execute_directly():
    """A material request through the compiled graph receives no permit/receipt."""
    result = build_governed_agent_graph().invoke(
        AgentState(query="Crea un archivo de prueba")
    )

    assert result["intent"] == "action"
    assert result["proposed_actions"]
    assert result["authorization_denials"]
    assert result["permits_issued"] == []
    assert result["execution_receipts"] == []

    # No human-approval or registered-capability input exists in this graph.
    # Every non-read effect must therefore fail closed at the production gate.
    for effect in (
        EffectType.WRITE,
        EffectType.CREATE,
        EffectType.DELETE,
        EffectType.EXTERNAL_API,
        EffectType.EXTERNAL_TOOL,
    ):
        request = ExecutionRequest(
            request_id=f"req-{effect.value.lower()}",
            tool_name="test-tool",
            effect_type=effect,
            parameters={},
            proposed_by="l1-test",
            context_revision="test-v1",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        decision = authorization_gate({"proposed_actions": [request]})
        assert decision["authorization_denials"], effect
        assert decision["permits_issued"] == [], effect


def test_permit_reuse_denied(tmp_path: Path):
    """The real gateway/sandbox boundary rejects a consumed permit on replay."""
    (tmp_path / "input.txt").write_text("read once", encoding="utf-8")
    operation = FilesystemRequest(
        "req-replay", FilesystemOperation.READ, "input.txt"
    )
    sandbox_request = SandboxRequest(
        request_id=operation.request_id,
        workspace_root=tmp_path,
        operation=operation,
    )
    execution_request = ExecutionRequest(
        request_id=operation.request_id,
        tool_name="filesystem.read",
        effect_type=EffectType.READ,
        parameters={"path": "input.txt"},
        proposed_by="l1-test",
        context_revision="test-v1",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
    permit = _permit_for_read(tmp_path, operation.request_id)
    gateway = ExecutionGateway(sandbox_manager=SandboxManager())

    first = gateway.execute(
        request=execution_request,
        permit=permit,
        sandbox_request=sandbox_request,
    )
    replay = gateway.execute(
        request=execution_request,
        permit=permit,
        sandbox_request=sandbox_request,
    )

    assert first.ok
    assert first.value == "read once"
    assert replay.receipt.status is SandboxStatus.DENIED
    assert replay.receipt.error_code == "PERMIT_REPLAY"
    assert replay.receipt.evidence_refs


def test_document_without_provenance_rejected():
    """GovernedRAG filters a chunk missing source URI or revision metadata."""
    chunk = RetrievalChunk(
        chunk_id="chunk-no-provenance",
        document_id="doc-1",
        content="A useful governed fact.",
    )

    response = GovernedRAG([chunk]).retrieve("governed fact")

    assert response.eligible_count == 0
    assert response.filtered_count == 1
    assert response.hits == ()


def test_superseded_chunk_filtered_in_retrieval():
    """The production metadata gate excludes superseded evidence before ranking."""
    chunks = [
        RetrievalChunk(
            chunk_id="chunk-v1",
            document_id="policy",
            content="Governed permit controls execution.",
            source_uri="docs/policy-v1.md",
            revision="v1",
            authority=AuthorityLevel.CANONICAL,
            validity="SUPERSEDED",
            domain="governance",
        ),
        RetrievalChunk(
            chunk_id="chunk-v2",
            document_id="policy",
            content="Governed permit controls execution.",
            source_uri="docs/policy-v2.md",
            revision="v2",
            authority=AuthorityLevel.CANONICAL,
            validity="CURRENT",
            domain="governance",
        ),
    ]

    response = GovernedRAG(chunks).retrieve(
        "governed permit execution",
        metadata_filter=MetadataFilter(
            minimum_authority=AuthorityLevel.CANONICAL,
            allowed_domains=("governance",),
        ),
        top_k=10,
    )

    assert response.eligible_count == 1
    assert response.filtered_count == 1
    assert [hit.chunk.chunk_id for hit in response.hits] == ["chunk-v2"]
    assert response.hits[0].evidence.revision == "v2"


def test_mcp_tool_unregistered_denied():
    """A discovered but unregistered MCP tool is denied before transport."""
    adapter = GovernedMCPAdapter("l1-test-server")
    adapter.discover_tools(
        [
            {
                "name": "external_api_caller",
                "description": "test tool",
                "inputSchema": {"type": "object", "properties": {}},
            }
        ]
    )
    request = MCPExecutionRequest(
        request_id="mcp-unregistered-1",
        tool_name="external_api_caller",
        effect_type=MCPEffectType.READ,
        parameters={},
        proposed_by="l1-test",
        context_revision="test-v1",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
    calls: list[str] = []

    class Session:
        async def call_tool(self, **kwargs):
            calls.append(kwargs["name"])
            raise AssertionError("unregistered MCP tool reached transport")

    receipt = anyio.run(adapter.call, Session(), request, None)

    assert receipt.decision.value == MCPAuthorizationDecision.DENY.value
    assert receipt.execution_outcome.value == MCPExecutionOutcome.FAILURE.value
    assert receipt.actual_effect["called"] is False
    assert "not registered" in (receipt.error_message or "")
    assert calls == []


def test_bedrock_provider_timeout_controlled_failure():
    """An injected provider timeout follows the real retry and receipt path."""
    model_id = "fixture.bedrock-model"

    class TimeoutClient:
        def __init__(self) -> None:
            self.calls = 0

        def converse(self, **kwargs):
            self.calls += 1
            raise TimeoutError("read timeout")

    client = TimeoutClient()
    adapter = BedrockProviderAdapter(
        client=client,
        policy=BedrockProviderPolicy(
            allowed_model_ids=frozenset({model_id}),
            max_attempts=2,
            backoff_seconds=0,
        ),
        sleep_fn=lambda _delay: None,
    )
    request = adapter.build_execution_request(
        model_id,
        [{"role": "user", "content": [{"text": "test timeout"}]}],
        proposed_by="l1-test",
        context_revision="test-v1",
    )
    permit = adapter.authorize(request)

    result = adapter.converse(request, permit)

    assert result.receipt.execution_outcome.value == ExecutionOutcome.FAILURE.value
    assert result.receipt.error_kind is BedrockErrorKind.TIMEOUT
    assert result.receipt.attempts == 2
    assert result.receipt.actual_effect["called"] is True
    assert result.receipt.receipt_id
    assert client.calls == 2


def test_governed_agent_graph_end_to_end():
    """The compiled graph completes its safe retrieval-only path."""
    result = build_governed_agent_graph().invoke(
        AgentState(query="Explica qué es BAGO")
    )

    assert result["final_response"]
    assert result["intent"] == "retrieval"
    assert result["retrieved_chunks"]
    assert result["requires_action"] is False
    assert result["proposed_actions"] == []
    assert result["permits_issued"] == []
    assert result["execution_receipts"] == []


def test_unbound_graph_executor_does_not_fabricate_success_receipt():
    """A valid permit alone cannot produce a synthetic execution receipt."""
    request = ExecutionRequest(
        request_id="req-unbound-executor",
        tool_name="filesystem.read",
        effect_type=EffectType.READ,
        parameters={"path": "input.txt"},
        proposed_by="l1-test",
        context_revision="test-v1",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
    gate_result = authorization_gate({"proposed_actions": [request]})
    assert len(gate_result["permits_issued"]) == 1

    execution_result = execute_actions(
        {"permits_issued": gate_result["permits_issued"]}
    )

    assert execution_result["execution_receipts"] == []
    assert len(execution_result["execution_failures"]) == 1
    assert "ExecutionGateway is not bound" in execution_result["execution_failures"][0]
