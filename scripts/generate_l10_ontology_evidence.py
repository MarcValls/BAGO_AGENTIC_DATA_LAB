"""Generate the reproducible L10 RDF/SPARQL reasoning receipt."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import anyio

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
EVIDENCE_PATH = REPO_ROOT / "evidence" / "l10_ontology_engine.md"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from adapters.bedrock_provider_adapter import (  # noqa: E402
    BedrockProviderAdapter,
    BedrockProviderPolicy,
)
from agent.governed_knowledge_agent import GovernedKnowledgeAgent  # noqa: E402
from metadata.ontology import KnowledgeGraph, OntologyRelation, RelationType  # noqa: E402
from metadata.ontology_engine import OntologyEngine  # noqa: E402
from metadata.schema import AuthorityLevel, KnowledgeAsset, Source  # noqa: E402
from retrieval.governed_rag import GovernedRAG, RetrievalChunk  # noqa: E402


QUERY = "¿Qué sustituye a la política anterior y qué evidencia la valida?"


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
                                "Fixture LLM reasoned over the governed RDF path; "
                                "BAGO retains evidence and contradiction authority."
                            )
                        }
                    ]
                }
            },
            "stopReason": "end_turn",
            "usage": {"inputTokens": 64, "outputTokens": 18},
        }


def build_graph() -> KnowledgeGraph:
    graph = KnowledgeGraph()
    graph.sources.update(
        {
            "source_policy": Source("source_policy", "docs/policy.md", "FILE"),
            "source_evidence": Source("source_evidence", "evidence/policy-receipt.md", "FILE"),
        }
    )
    old_policy = KnowledgeAsset(
        asset_id="policy_v1",
        title="Permit policy v1",
        description="Previous permit policy",
        asset_type="CONTRACT",
        source_id="source_policy",
        version="1.0.0",
        authority=AuthorityLevel.CANONICAL,
        metadata={"provenance": "docs/policy-v1.md"},
    )
    current_policy = KnowledgeAsset(
        asset_id="policy_v2",
        title="Permit policy v2",
        description="Current governed permit policy",
        asset_type="CONTRACT",
        source_id="source_policy",
        version="2.0.0",
        authority=AuthorityLevel.VERIFIED,
        metadata={"provenance": "docs/policy-v2.md"},
    )
    receipt = KnowledgeAsset(
        asset_id="policy_receipt",
        title="Policy v2 validation receipt",
        description="Evidence validating the current policy",
        asset_type="EVIDENCE",
        source_id="source_evidence",
        version="1.0.0",
        authority=AuthorityLevel.VERIFIED,
        metadata={"provenance": "evidence/policy-receipt.md"},
    )
    conflicting_policy = KnowledgeAsset(
        asset_id="candidate_policy",
        title="Candidate policy",
        description="An incompatible experimental policy",
        asset_type="CONTRACT",
        source_id="source_policy",
        version="0.1.0",
        authority=AuthorityLevel.PROPOSED,
        metadata={"provenance": "docs/candidate-policy.md"},
    )
    old_policy.mark_superseded("policy_v2")
    for asset in (old_policy, current_policy, receipt, conflicting_policy):
        graph.add_asset(asset)
    graph.relations.extend(
        [
            OntologyRelation("rel_supersedes", RelationType.SUPERSEDES, "policy_v2", "policy_v1"),
            OntologyRelation("rel_validates", RelationType.VALIDATES, "policy_receipt", "policy_v2"),
            OntologyRelation("rel_contradicts", RelationType.CONTRADICTS, "candidate_policy", "policy_v2"),
        ]
    )
    return graph


def build_retriever() -> GovernedRAG:
    chunks = [
        RetrievalChunk(
            chunk_id="policy-v2-chunk",
            document_id="policy_v2",
            content=(
                "La política de permisos v2 sustituye la política v1; una evidencia "
                "verifica y valida la política vigente."
            ),
            title="Permit policy v2",
            source_uri="docs/policy-v2.md",
            revision="2.0.0",
            authority=AuthorityLevel.VERIFIED,
            metadata={"asset_id": "policy_v2"},
        ),
        RetrievalChunk(
            chunk_id="policy-receipt-chunk",
            document_id="policy_receipt",
            content="La evidencia policy receipt valida la política de permisos v2.",
            title="Policy v2 validation receipt",
            source_uri="evidence/policy-receipt.md",
            revision="1.0.0",
            authority=AuthorityLevel.VERIFIED,
            metadata={"asset_id": "policy_receipt"},
        ),
    ]
    return GovernedRAG(chunks)


async def run_evidence() -> dict[str, Any]:
    engine = OntologyEngine.from_knowledge_graph(build_graph())
    client = FixtureBedrockClient()
    bedrock = BedrockProviderAdapter(
        client=client,
        policy=BedrockProviderPolicy(
            allowed_model_ids=frozenset({"fixture.l10-model"}),
            backoff_seconds=0,
        ),
    )
    agent = GovernedKnowledgeAgent(
        build_retriever(),
        ontology_engine=engine,
        bedrock_adapter=bedrock,
    )
    run = await agent.run(
        QUERY,
        context_revision="l10-local-v1",
        model_id="fixture.l10-model",
        use_bedrock=True,
    )
    ontology = run.ontology
    assert ontology is not None
    prompt = str(client.calls[0]["messages"][0]["content"][0]["text"]) if client.calls else ""
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "local-rdf-sparql-subset-and-injected-llm-fixture",
        "cost_usd": ontology.receipt.cost_usd,
        "aws_live": "NOT_RUN",
        "openmetadata_live": "NOT_RUN",
        "query": QUERY,
        "turtle": engine.graph.to_turtle(),
        "ontology": ontology.to_dict(),
        "agent": run.to_dict(),
        "llm_fixture": {
            "calls": len(client.calls),
            "transport": "injected_fixture_no_aws_call",
            "prompt_contains_ontology_engine": "Ontology Engine" in prompt,
        },
    }


def render_evidence(result: dict[str, Any]) -> str:
    ontology = result["ontology"]
    receipt = ontology["receipt"]
    payload = json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True, default=str)
    return f"""# L10 · Governed Ontology Engine — local RDF/SPARQL evidence

Generated at: `{result['generated_at']}`

This receipt demonstrates the first L10 case over a deterministic local graph:

```text
RAG retrieves governed chunks
  → ontology engine resolves RDF relations
  → inverse/transitive inference materializes paths
  → constraints flag contradictions and missing evidence
  → path + evidence + receipt are passed to the LLM context
```

## Boundary

- Cost: `{result['cost_usd']:.1f} USD`
- RDF store: local in-memory graph; no Docker or paid service
- SPARQL: bounded local `SELECT` subset (triple joins, `FILTER regex`/equality, `LIMIT`)
- LLM: injected Bedrock-shaped fixture; AWS call: `{result['aws_live']}`
- OpenMetadata live: `{result['openmetadata_live']}`
- Fixture received ontology context: `{result['llm_fixture']['prompt_contains_ontology_engine']}`

## Query and receipt

Question: `{result['query']}`

- Receipt: `{receipt['receipt_id']}`
- Outcome: `{receipt['outcome']}`
- Explicit triples: `{receipt['explicit_triples']}`
- Inferred triples: `{receipt['inferred_triples']}`
- Paths found: `{receipt['paths_found']}`
- Contradictions found: `{receipt['contradictions_found']}`
- Evidence refs: `{len(receipt['evidence_refs'])}`

The `CONSTRAINT_VIOLATION` outcome is intentional: the fixture contains an
explicit contradictory candidate so the engine demonstrates detection instead
of silently producing a green answer.

## RDF/Turtle materialization

```turtle
{result['turtle']}
```

## Reasoning result

```text
{ontology['summary']}
```

## Reproduce

```bash
python -m pytest tests/test_l10_ontology_engine.py -q
python scripts/generate_l10_ontology_evidence.py
```

## Full receipt

```json
{payload}
```
"""


def main() -> None:
    result = anyio.run(run_evidence)
    EVIDENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE_PATH.write_text(render_evidence(result), encoding="utf-8")
    print(json.dumps(result["ontology"]["receipt"], indent=2, ensure_ascii=False, sort_keys=True))
    print(f"Evidence: {EVIDENCE_PATH.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
