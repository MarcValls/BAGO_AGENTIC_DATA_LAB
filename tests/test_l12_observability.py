"""L12 local trace and deterministic evaluation contracts."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))

from adapters.bedrock_provider_adapter import (  # noqa: E402
    BedrockProviderAdapter,
    BedrockProviderPolicy,
)
from agent.governed_knowledge_agent import GovernedKnowledgeAgent  # noqa: E402
from evaluation.local_evals import EvaluationStatus, LocalTraceEvaluator  # noqa: E402
from metadata.schema import AuthorityLevel  # noqa: E402
from observability.local_trace import LocalTrace, LocalTraceBuilder, TraceEvent, TraceKind  # noqa: E402
from orchestration.state_graph import AuthorizationDecision, Permit  # noqa: E402
from retrieval.governed_rag import GovernedRAG, RetrievalChunk  # noqa: E402
from sandbox import (  # noqa: E402
    Capability,
    ProcessRequest,
    SandboxManager,
    SandboxProfile,
    SandboxRequest,
)


class FixtureBedrockClient:
    def converse(self, **kwargs):
        return {
            "output": {"message": {"content": [{"text": "local fixture answer"}]}},
            "stopReason": "end_turn",
            "usage": {"inputTokens": 8, "outputTokens": 3},
        }


def _run():
    retriever = GovernedRAG(
        [
            RetrievalChunk(
                chunk_id="observability-policy",
                document_id="observability-policy",
                content="La evidencia local valida la política de permisos gobernados.",
                title="Observability policy",
                source_uri="docs/observability.md",
                revision="l12-v1",
                authority=AuthorityLevel.VERIFIED,
                metadata={"asset_id": "observability-policy"},
            )
        ]
    )
    adapter = BedrockProviderAdapter(
        client=FixtureBedrockClient(),
        policy=BedrockProviderPolicy(
            allowed_model_ids=frozenset({"fixture.l12-model"}),
            backoff_seconds=0,
        ),
    )
    return GovernedKnowledgeAgent(retriever, bedrock_adapter=adapter).run_sync(
        "¿Qué evidencia valida la política de permisos?",
        context_revision="l12-local-v1",
        model_id="fixture.l12-model",
        use_bedrock=True,
    )


def _sandbox_result(tmp_path: Path):
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_local.py").write_text("def test_local():\n    assert True\n", encoding="utf-8")
    operation = ProcessRequest(
        "l12-sandbox-request",
        Capability.RUN_TESTS,
        "pytest",
        arguments=("-q", "tests"),
    )
    now = datetime.now(timezone.utc)
    permit = Permit(
        permit_id="l12-sandbox-permit",
        request_id=operation.request_id,
        decision=AuthorizationDecision.ALLOW,
        rationale="L12 local observability fixture",
        constraints=[
            f"sandbox_profile={SandboxProfile.TEST_RUNNER.value}",
            f"workspace_root={tmp_path}",
            f"capability={Capability.FILESYSTEM_READ.value}",
            f"capability={Capability.FILESYSTEM_WRITE.value}",
            f"capability={Capability.RUN_TESTS.value}",
            "write_scope=workspace",
            "timeout_seconds=30",
        ],
        issued_at=now.isoformat(),
        expires_at=(now + timedelta(minutes=5)).isoformat(),
        signed_by="l12-test-authority",
    )
    return SandboxManager().execute(
        permit=permit,
        request=SandboxRequest(operation.request_id, tmp_path, operation),
    )


def test_builder_captures_workflow_retrieval_permit_and_receipt():
    trace = LocalTraceBuilder.from_agent_run(_run())

    assert {
        "agent.run",
        "classify_intent",
        "retrieve_context",
        "retrieval",
        "reason_and_propose",
        "authorize",
        "tool_call",
        "permit",
        "execute",
        "receipt",
        "verify_and_respond",
    }.issubset(set(trace.names))
    tool = next(event for event in trace.events if event.kind is TraceKind.TOOL)
    assert tool.attributes["permit_id"]
    assert tool.attributes["receipt_id"]
    assert trace.evidence_refs


def test_evaluator_passes_complete_agent_to_sandbox_chain(tmp_path: Path):
    trace = LocalTraceBuilder.from_agent_run(
        _run(),
        sandbox_results=(_sandbox_result(tmp_path),),
    )

    report = LocalTraceEvaluator().evaluate(trace, require_sandbox=True)

    assert report.status is EvaluationStatus.PASS
    assert report.score == pytest.approx(1.0)
    assert all(check.passed for check in report.checks)


def test_evaluator_detects_missing_receipt():
    trace = LocalTraceBuilder.from_agent_run(_run())
    events = tuple(
        TraceEvent(
            event_id=event.event_id,
            trace_id=event.trace_id,
            sequence=event.sequence,
            name=event.name,
            kind=event.kind,
            status=event.status,
            parent_event_id=event.parent_event_id,
            attributes={**event.attributes, "receipt_id": "", "called": True, "outcome": "SUCCESS"}
            if event.kind is TraceKind.TOOL
            else event.attributes,
            evidence_refs=event.evidence_refs,
        )
        for event in trace.events
        if event.kind is not TraceKind.RECEIPT
    )
    report = LocalTraceEvaluator().evaluate(
        LocalTrace(trace.trace_id, trace.run_id, events, trace.cost_usd)
    )

    assert report.status is EvaluationStatus.FAIL
    assert not next(check for check in report.checks if check.name == "receipt_linkage").passed


def test_evaluator_detects_unauthorized_effect():
    trace = LocalTraceBuilder.from_agent_run(_run())
    events = tuple(
        TraceEvent(
            event_id=event.event_id,
            trace_id=event.trace_id,
            sequence=event.sequence,
            name=event.name,
            kind=event.kind,
            status=event.status,
            parent_event_id=event.parent_event_id,
            attributes={**event.attributes, "decision": "REQUIRE_HUMAN", "called": True}
            if event.kind is TraceKind.TOOL
            else event.attributes,
            evidence_refs=event.evidence_refs,
        )
        for event in trace.events
    )
    report = LocalTraceEvaluator().evaluate(
        LocalTrace(trace.trace_id, trace.run_id, events, trace.cost_usd)
    )

    assert report.status is EvaluationStatus.FAIL
    assert not next(check for check in report.checks if check.name == "no_unauthorized_effect").passed


def test_trace_serializes_to_json(tmp_path: Path):
    trace = LocalTraceBuilder.from_agent_run(
        _run(),
        sandbox_results=(_sandbox_result(tmp_path),),
    )

    decoded = json.loads(trace.to_json())

    assert decoded["trace_id"] == trace.trace_id
    assert decoded["event_count"] == len(trace.events)
    assert decoded["cost_usd"] == 0.0
