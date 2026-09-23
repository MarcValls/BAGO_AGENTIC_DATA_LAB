"""Run the public, zero-cost BAGO end-to-end demonstration.

The demo composes already verified local boundaries.  It uses deterministic
fixtures, an injected Bedrock-shaped client and the local restricted sandbox;
it never needs credentials, Docker, network access or a paid service.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
EVIDENCE_PATH = REPO_ROOT / "evidence" / "public_e2e_demo.md"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from adapters.bedrock_provider_adapter import (  # noqa: E402
    BedrockProviderAdapter,
    BedrockProviderPolicy,
)
from agent.governed_knowledge_agent import AgentRun, GovernedKnowledgeAgent  # noqa: E402
from evaluation.local_evals import EvaluationReport, LocalTraceEvaluator  # noqa: E402
from metadata.ontology import KnowledgeGraph, OntologyRelation, RelationType  # noqa: E402
from metadata.ontology_engine import OntologyEngine, OntologyReasoningResult  # noqa: E402
from metadata.schema import AuthorityLevel, KnowledgeAsset, Source  # noqa: E402
from observability.local_trace import LocalTrace, LocalTraceBuilder  # noqa: E402
from src.orchestration.state_graph import AuthorizationDecision, Permit  # noqa: E402
from retrieval.governed_rag import GovernedRAG, RetrievalChunk  # noqa: E402
from sandbox import (  # noqa: E402
    Capability,
    ProcessRequest,
    SandboxExecutionResult,
    SandboxManager,
    SandboxProfile,
    SandboxRequest,
)


QUERY = "¿Qué sustituye a la política anterior y qué evidencia la valida?"
MODEL_ID = "fixture.public-e2e"
CONTEXT_REVISION = "public-e2e-v1"


class FixtureBedrockClient:
    """Bedrock-shaped local client; it never contacts AWS."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def converse(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        return {
            "output": {
                "message": {
                    "content": [
                        {
                            "text": (
                                "La política vigente sustituye a la anterior y la "
                                "evidencia enlazada valida esa relación."
                            )
                        }
                    ]
                }
            },
            "stopReason": "end_turn",
            "usage": {"inputTokens": 64, "outputTokens": 19},
        }


def build_graph() -> KnowledgeGraph:
    """Build the small public fixture graph used by the E2E run."""

    graph = KnowledgeGraph()
    graph.sources.update(
        {
            "public_policy_source": Source(
                "public_policy_source", "fixtures/public-policy.md", "FILE"
            ),
            "public_evidence_source": Source(
                "public_evidence_source", "fixtures/public-policy-receipt.md", "FILE"
            ),
        }
    )
    old_policy = KnowledgeAsset(
        asset_id="public_policy_v1",
        title="Public permit policy v1",
        description="Previous policy version in the public fixture.",
        asset_type="CONTRACT",
        source_id="public_policy_source",
        version="1.0.0",
        authority=AuthorityLevel.CANONICAL,
        metadata={"provenance": "fixtures/public-policy-v1.md"},
    )
    current_policy = KnowledgeAsset(
        asset_id="public_policy_v2",
        title="Public permit policy v2",
        description="Current governed policy version in the public fixture.",
        asset_type="CONTRACT",
        source_id="public_policy_source",
        version="2.0.0",
        authority=AuthorityLevel.VERIFIED,
        metadata={"provenance": "fixtures/public-policy-v2.md"},
    )
    validation_receipt = KnowledgeAsset(
        asset_id="public_policy_receipt",
        title="Public policy v2 validation receipt",
        description="Evidence that validates the current policy.",
        asset_type="EVIDENCE",
        source_id="public_evidence_source",
        version="1.0.0",
        authority=AuthorityLevel.VERIFIED,
        metadata={"provenance": "fixtures/public-policy-receipt.md"},
    )
    old_policy.mark_superseded(current_policy.asset_id)
    for asset in (old_policy, current_policy, validation_receipt):
        graph.add_asset(asset)
    graph.relations.extend(
        [
            OntologyRelation(
                "public_supersedes",
                RelationType.SUPERSEDES,
                current_policy.asset_id,
                old_policy.asset_id,
            ),
            OntologyRelation(
                "public_validates",
                RelationType.VALIDATES,
                validation_receipt.asset_id,
                current_policy.asset_id,
            ),
        ]
    )
    return graph


def build_retriever() -> GovernedRAG:
    return GovernedRAG(
        [
            RetrievalChunk(
                chunk_id="public-policy-v2-chunk",
                document_id="public_policy_v2",
                content=(
                    "La política de permisos v2 sustituye la política v1 y es la "
                    "versión vigente gobernada."
                ),
                title="Public permit policy v2",
                source_uri="fixtures/public-policy-v2.md",
                revision="2.0.0",
                authority=AuthorityLevel.VERIFIED,
                metadata={"asset_id": "public_policy_v2"},
            ),
            RetrievalChunk(
                chunk_id="public-policy-receipt-chunk",
                document_id="public_policy_receipt",
                content="La evidencia pública valida la política de permisos v2.",
                title="Public policy validation receipt",
                source_uri="fixtures/public-policy-receipt.md",
                revision="1.0.0",
                authority=AuthorityLevel.VERIFIED,
                metadata={"asset_id": "public_policy_receipt"},
            ),
        ]
    )


def build_agent(client: FixtureBedrockClient) -> GovernedKnowledgeAgent:
    adapter = BedrockProviderAdapter(
        client=client,
        policy=BedrockProviderPolicy(
            allowed_model_ids=frozenset({MODEL_ID}),
            backoff_seconds=0,
        ),
    )
    return GovernedKnowledgeAgent(
        build_retriever(),
        ontology_engine=OntologyEngine.from_knowledge_graph(build_graph()),
        bedrock_adapter=adapter,
    )


def build_sandbox_result(root: Path) -> SandboxExecutionResult:
    """Run one typed pytest operation inside the local restricted backend."""

    tests_dir = root / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_public_fixture.py").write_text(
        "def test_public_fixture():\n    assert 'BAGO' == 'BAGO'\n",
        encoding="utf-8",
    )
    operation = ProcessRequest(
        "public-e2e-sandbox-request",
        Capability.RUN_TESTS,
        "pytest",
        arguments=("-q", "tests"),
    )
    now = datetime.now(timezone.utc)
    permit = Permit(
        permit_id="public-e2e-sandbox-permit",
        request_id=operation.request_id,
        decision=AuthorizationDecision.ALLOW,
        rationale="Public E2E demo: run the generated fixture test.",
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
        signed_by="bago.public-e2e",
    )
    return SandboxManager().execute(
        permit=permit,
        request=SandboxRequest(operation.request_id, root, operation),
    )


def run_demo() -> dict[str, Any]:
    """Execute the complete local chain and return its evidence objects."""

    client = FixtureBedrockClient()
    run = build_agent(client).run_sync(
        QUERY,
        context_revision=CONTEXT_REVISION,
        model_id=MODEL_ID,
        use_bedrock=True,
    )
    ontology = run.ontology
    if ontology is None:
        raise RuntimeError("public E2E agent did not produce ontology reasoning")

    with tempfile.TemporaryDirectory(prefix="bago-public-e2e-") as temporary:
        sandbox_result = build_sandbox_result(Path(temporary))
        trace = LocalTraceBuilder.from_agent_run(
            run,
            sandbox_results=(sandbox_result,),
        )
        report = LocalTraceEvaluator().evaluate(trace, require_sandbox=True)

    if run.status.value != "COMPLETED":
        raise RuntimeError(f"public E2E agent failed: {run.to_dict()}")
    if ontology.receipt.outcome != "SUCCESS":
        raise RuntimeError(f"public E2E ontology reasoning failed: {ontology.to_dict()}")
    if not sandbox_result.ok:
        raise RuntimeError(f"public E2E sandbox failed: {sandbox_result.to_dict()}")
    if report.status.value != "PASS":
        raise RuntimeError(f"public E2E evaluation failed: {report.to_dict()}")

    return {
        "status": "PASS",
        "agent_run": run,
        "ontology": ontology,
        "sandbox": sandbox_result,
        "trace": trace,
        "evaluation": report,
        "fixture_calls": len(client.calls),
    }


def summary(result: dict[str, Any]) -> dict[str, Any]:
    run: AgentRun = result["agent_run"]
    ontology: OntologyReasoningResult = result["ontology"]
    sandbox: SandboxExecutionResult = result["sandbox"]
    trace: LocalTrace = result["trace"]
    evaluation: EvaluationReport = result["evaluation"]
    return {
        "status": result["status"],
        "scope": "public-zero-cost-local-e2e",
        "cost_usd": evaluation.cost_usd,
        "agent_status": run.status.value,
        "retrieval_hits": len(run.retrieval.hits),
        "ontology_outcome": ontology.receipt.outcome,
        "ontology_paths": ontology.receipt.paths_found,
        "ontology_inferred_triples": ontology.receipt.inferred_triples,
        "ontology_contradictions": ontology.receipt.contradictions_found,
        "sandbox_status": sandbox.receipt.status.value,
        "sandbox_exit_code": sandbox.receipt.exit_code,
        "sandbox_profile": sandbox.receipt.profile,
        "trace_events": len(trace.events),
        "evaluation_status": evaluation.status.value,
        "evaluation_score": evaluation.score,
        "evaluation_checks": [
            {"name": check.name, "passed": check.passed}
            for check in evaluation.checks
        ],
        "fixture_calls": result["fixture_calls"],
        "aws_live": "NOT_RUN",
        "openmetadata_live": "NOT_RUN",
    }


def render_evidence(result: dict[str, Any]) -> str:
    report: EvaluationReport = result["evaluation"]
    trace: LocalTrace = result["trace"]
    ontology: OntologyReasoningResult = result["ontology"]
    sandbox: SandboxExecutionResult = result["sandbox"]
    generated_at = datetime.now(timezone.utc).isoformat()
    checks = "\n".join(
        f"| `{check.name}` | {'PASS' if check.passed else 'FAIL'} | {check.detail} |"
        for check in report.checks
    )
    evidence_payload = summary(result)
    evidence_payload.update(
        {
            "query": QUERY,
            "context_revision": CONTEXT_REVISION,
            "model": MODEL_ID,
            "trace_event_names": list(trace.names),
            "ontology_evidence_refs": list(ontology.receipt.evidence_refs),
            "sandbox_evidence_refs": list(sandbox.receipt.evidence_refs),
        }
    )
    encoded = json.dumps(evidence_payload, ensure_ascii=False, indent=2, sort_keys=True)
    return f"""# L13 · Public E2E Demo — reproducible local evidence

Generated at: `{generated_at}`

This is the public clone-and-run path for the BAGO Agentic Data Lab. It uses
only committed code and deterministic local fixtures:

```text
Governed RAG
  → Ontology Engine (RDF/Turtle + bounded SPARQL + inference)
  → injected Bedrock-shaped LLM context
  → LocalRestrictedBackend with typed pytest
  → LocalTraceBuilder
  → LocalTraceEvaluator
```

## Boundary

- Cost: `0.0 USD`
- Credentials: none
- Network: not required by the demo
- AWS live: `NOT_RUN`
- OpenMetadata live: `NOT_RUN`
- LLM transport: injected fixture; no AWS request is made
- Sandbox: `LocalRestrictedBackend`, workspace write scope, network deny
- CI: GitHub Actions runs the same tests, README check, demo check and compile check

## Result

- Overall status: `{result['status']}`
- Agent status: `{result['agent_run'].status.value}`
- Ontology outcome: `{ontology.receipt.outcome}`
- Ontology paths: `{ontology.receipt.paths_found}`
- Inferred triples: `{ontology.receipt.inferred_triples}`
- Contradictions: `{ontology.receipt.contradictions_found}`
- Sandbox status: `{sandbox.receipt.status.value}`
- Sandbox exit code: `{sandbox.receipt.exit_code}`
- Trace events: `{len(trace.events)}`
- Evaluation: `{report.status.value}` (`{report.score:.2f}`)

| Check | Status | Detail |
|---|---|---|
{checks}

## Reproduce from a public clone

```bash
python -m pip install -r requirements.txt
python scripts/run_public_e2e_demo.py --check
python -m pytest tests -q
python scripts/generate_dynamic_readme.py --check --skip-tests
```

The generated evidence is intentionally scoped to this local fixture. It does
not promote AWS, remote OpenMetadata, commercetools or production observability
claims to `VALIDATED`.

## Stable summary

```json
{encoded}
```
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="execute the demo and fail unless every local gate passes",
    )
    parser.add_argument(
        "--write-evidence",
        action="store_true",
        help="write evidence/public_e2e_demo.md after a passing run",
    )
    args = parser.parse_args(argv)
    result = run_demo()
    if args.write_evidence:
        EVIDENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
        EVIDENCE_PATH.write_text(render_evidence(result), encoding="utf-8")
    print(json.dumps(summary(result), ensure_ascii=False, indent=2, sort_keys=True))
    if args.write_evidence:
        print(f"Evidence: {EVIDENCE_PATH.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
