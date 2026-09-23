"""Generate reproducible local observability and evaluation evidence for L12."""

from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
EVIDENCE_PATH = REPO_ROOT / "evidence" / "l12_observability_evals.md"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from adapters.bedrock_provider_adapter import (  # noqa: E402
    BedrockProviderAdapter,
    BedrockProviderPolicy,
)
from agent.governed_knowledge_agent import GovernedKnowledgeAgent  # noqa: E402
from evaluation.local_evals import EvaluationReport, LocalTraceEvaluator  # noqa: E402
from metadata.schema import AuthorityLevel  # noqa: E402
from observability.local_trace import LocalTrace, LocalTraceBuilder  # noqa: E402
from orchestration.state_graph import AuthorizationDecision, Permit  # noqa: E402
from retrieval.governed_rag import GovernedRAG, RetrievalChunk  # noqa: E402
from sandbox import (  # noqa: E402
    Capability,
    ProcessRequest,
    SandboxManager,
    SandboxProfile,
    SandboxRequest,
)


QUERY = "¿Qué evidencia valida la política de permisos?"


class FixtureBedrockClient:
    """Bedrock-shaped local client; it never contacts AWS."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def converse(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        return {
            "output": {"message": {"content": [{"text": "Fixture L12 answer"}]}},
            "stopReason": "end_turn",
            "usage": {"inputTokens": 12, "outputTokens": 4},
        }


def build_retriever() -> GovernedRAG:
    return GovernedRAG(
        [
            RetrievalChunk(
                chunk_id="l12-policy-chunk",
                document_id="l12-policy",
                content="La evidencia local valida la política de permisos gobernados.",
                title="L12 policy",
                source_uri="docs/observability.md",
                revision="l12-v1",
                authority=AuthorityLevel.VERIFIED,
                metadata={"asset_id": "l12-policy"},
            ),
            RetrievalChunk(
                chunk_id="l12-receipt-chunk",
                document_id="l12-receipt",
                content="El receipt enlaza la decisión, el permiso y el efecto real.",
                title="L12 receipt",
                source_uri="evidence/l12-observability.md",
                revision="l12-v1",
                authority=AuthorityLevel.VERIFIED,
                metadata={"asset_id": "l12-receipt"},
            ),
        ]
    )


def build_agent(client: FixtureBedrockClient) -> GovernedKnowledgeAgent:
    adapter = BedrockProviderAdapter(
        client=client,
        policy=BedrockProviderPolicy(
            allowed_model_ids=frozenset({"fixture.l12-model"}),
            backoff_seconds=0,
        ),
    )
    return GovernedKnowledgeAgent(build_retriever(), bedrock_adapter=adapter)


def build_sandbox_result(root: Path):
    tests_dir = root / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_local.py").write_text(
        "def test_local_observability_fixture():\n    assert 2 + 2 == 4\n",
        encoding="utf-8",
    )
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
        rationale="L12 local observability validation",
        constraints=[
            f"sandbox_profile={SandboxProfile.TEST_RUNNER.value}",
            f"workspace_root={root}",
            f"capability={Capability.FILESYSTEM_READ.value}",
            f"capability={Capability.FILESYSTEM_WRITE.value}",
            f"capability={Capability.RUN_TESTS.value}",
            "write_scope=workspace",
            "timeout_seconds=30",
        ],
        issued_at=now.isoformat(),
        expires_at=(now + timedelta(minutes=5)).isoformat(),
        signed_by="bago.l12.local",
    )
    return SandboxManager().execute(
        permit=permit,
        request=SandboxRequest(operation.request_id, root, operation),
    )


def run_demo() -> tuple[LocalTrace, EvaluationReport, dict[str, Any]]:
    client = FixtureBedrockClient()
    run = build_agent(client).run_sync(
        QUERY,
        context_revision="l12-local-v1",
        model_id="fixture.l12-model",
        use_bedrock=True,
    )
    with tempfile.TemporaryDirectory(prefix="bago-l12-observability-") as temporary:
        sandbox_result = build_sandbox_result(Path(temporary))
        trace = LocalTraceBuilder.from_agent_run(
            run,
            sandbox_results=(sandbox_result,),
        )
        report = LocalTraceEvaluator().evaluate(trace, require_sandbox=True)
        payload = {
            "agent": run.to_dict(),
            "bedrock_fixture_calls": len(client.calls),
            "sandbox": sandbox_result.to_dict(),
        }
    if report.status.value != "PASS":
        raise RuntimeError(f"L12 evaluation failed: {report.to_dict()}")
    return trace, report, payload


def _event_rows(trace: LocalTrace) -> str:
    rows = ["| Seq | Event | Kind | Status | Parent | Evidence |", "|---:|---|---|---|---|---|"]
    for event in trace.events:
        refs = ", ".join(event.evidence_refs) or "—"
        parent = event.parent_event_id or "—"
        rows.append(
            f"| {event.sequence} | `{event.name}` | `{event.kind.value}` | `{event.status}` | "
            f"`{parent}` | {refs} |"
        )
    return "\n".join(rows)


def render_evidence(trace: LocalTrace, report: EvaluationReport, payload: dict[str, Any]) -> str:
    generated_at = datetime.now(timezone.utc).isoformat()
    full_payload = {
        "generated_at": generated_at,
        "scope": "local-agent-trace-sandbox-receipt-evaluation",
        "cost_usd": report.cost_usd,
        "aws_live": "NOT_RUN",
        "openmetadata_remote": "NOT_RUN",
        "collector": "NOT_USED; local JSON trace only",
        "trace": trace.to_dict(),
        "evaluation": report.to_dict(),
        "fixtures": payload,
    }
    encoded = json.dumps(full_payload, ensure_ascii=False, indent=2, sort_keys=True, default=str)
    checks = "\n".join(
        f"| `{check.name}` | {'PASS' if check.passed else 'FAIL'} | {check.detail} |"
        for check in report.checks
    )
    return f"""# L12 · Local Observability and Evals

Generated at: `{generated_at}`

This zero-cost evidence composes the existing governed agent and local sandbox
receipts into one ordered trace, then evaluates the governance links locally:

```text
agent run
  → workflow stages
  → retrieval + citations
  → tool proposal + permit
  → execution result
  → sandbox execution
  → receipt + evidence reference
  → deterministic eval
```

## Boundary

- Cost: `{report.cost_usd:.1f} USD`
- Trace storage: local in-memory object serialized as JSON; no collector or SaaS
- Model: injected Bedrock-shaped fixture; AWS live: `{full_payload['aws_live']}`
- Sandbox: `LocalRestrictedBackend` with typed pytest request
- OpenMetadata remote: `{full_payload['openmetadata_remote']}`

## Trace

- Trace: `{trace.trace_id}`
- Agent run: `{trace.run_id}`
- Events: `{len(trace.events)}`
- Evidence references: `{len(trace.evidence_refs)}`

{_event_rows(trace)}

## Evaluation

- Evaluation: `{report.evaluation_id}`
- Status: `{report.status.value}`
- Score: `{report.score:.2f}`

| Check | Status | Detail |
|---|---|---|
{checks}

The evaluator checks trace root and workflow coverage, retrieval citations,
permit linkage, receipt linkage, absence of unauthorized effects and sandbox
receipt linkage. It does not judge LLM answer quality or claim production
observability infrastructure.

## Reproduce

```bash
python -m pytest tests/test_l12_observability.py -q
python scripts/run_l12_observability_evidence.py
```

## Full receipt

```json
{encoded}
```
"""


def main() -> int:
    trace, report, payload = run_demo()
    EVIDENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE_PATH.write_text(render_evidence(trace, report, payload), encoding="utf-8")
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2, sort_keys=True))
    print(f"Evidence: {EVIDENCE_PATH.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
