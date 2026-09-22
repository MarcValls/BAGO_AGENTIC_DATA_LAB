"""Compare the local BAGO ETL/RAG path with a Bedrock KB-shaped fixture.

The comparison uses one query and the same labelled references on both sides.
The Knowledge Base client is injected and deterministic: this proves the
adapter contract and citation normalization, not AWS relevance or latency.
"""

from __future__ import annotations

import sys
import time
import json
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from adapters.bedrock_kb_adapter import (  # noqa: E402
    BedrockKBAdapter,
    BedrockKnowledgeBasePolicy,
)
from retrieval.governed_rag import GovernedRAG, load_sqlite_chunks  # noqa: E402


QUERY = "How does BAGO enforce ExecutionRequest Permit and evidence receipts?"
KB_ID = "kb-fixture-bago"
MODEL_ARN = "arn:aws:bedrock:eu-west-1::foundation-model/fixture-model"


def _fixture_reference(hit, index: int) -> dict:
    return {
        "content": {"text": hit.chunk.content},
        "location": {
            "s3Location": {
                "uri": f"s3://fixture-bedrock-kb/{hit.chunk.document_id}.md"
            }
        },
        "score": round(max(0.0, 1.0 - index * 0.08), 4),
        "metadata": {
            "chunk_id": hit.chunk.chunk_id,
            "document_id": hit.chunk.document_id,
            "source_uri": hit.evidence.source_uri,
            "revision": hit.evidence.revision,
            "authority": hit.chunk.authority.value,
        },
    }


class FixtureKnowledgeBaseClient:
    """Shape-compatible client double for bedrock-agent-runtime."""

    def __init__(self, references: list[dict]) -> None:
        self.references = references
        self.calls = 0

    def retrieve_and_generate(self, **kwargs):
        self.calls += 1
        return {
            "output": {
                "text": (
                    "BAGO requires an EXTERNAL_API request to pass through a "
                    "Permit before execution, then records evidence in a receipt."
                )
            },
            "citations": [{"retrievedReferences": self.references}],
            "sessionId": "fixture-session-l7",
        }


def _compact(text: str, limit: int = 700) -> str:
    compacted = " ".join(text.split())
    return compacted if len(compacted) <= limit else compacted[: limit - 3] + "..."


def build_comparison() -> dict:
    chunks = load_sqlite_chunks(REPO_ROOT / "l2_etl_metadata.db")
    local_retriever = GovernedRAG(chunks)
    local_started = time.perf_counter()
    local_result = local_retriever.retrieve(QUERY, top_k=3)
    local_latency_ms = (time.perf_counter() - local_started) * 1000

    references = [
        _fixture_reference(hit, index)
        for index, hit in enumerate(local_result.hits)
    ]
    client = FixtureKnowledgeBaseClient(references)
    adapter = BedrockKBAdapter(
        policy=BedrockKnowledgeBasePolicy(
            knowledge_base_id=KB_ID,
            region_name="fixture-region",
            generation_model_arn=MODEL_ARN,
            retrieve_and_generate_cost_usd=0.0,
        ),
        client=client,
    )
    request = adapter.build_request(
        QUERY,
        operation="retrieve_and_generate",
        proposed_by="l7-comparison",
        context_revision="fixture-v1",
    )
    permit = adapter.authorize(request)
    kb_started = time.perf_counter()
    kb_result = adapter.retrieve_and_generate(request, permit)
    kb_latency_ms = (time.perf_counter() - kb_started) * 1000

    local_ids = [hit.chunk.chunk_id for hit in local_result.hits]
    kb_ids = [hit.metadata.get("chunk_id", hit.chunk_id) for hit in kb_result.hits]
    overlap = len(set(local_ids) & set(kb_ids))
    return {
        "query": QUERY,
        "local": {
            "backend": "SQLite ETL (65 chunks) + GovernedRAG hybrid",
            "latency_ms": local_latency_ms,
            "ids": local_ids,
            "citations": list(local_result.citations),
            "context": local_result.assemble_context(max_chars=1500),
            "pipeline": list(local_result.pipeline),
        },
        "bedrock_kb": {
            "backend": "bedrock-agent-runtime fixture",
            "latency_ms": kb_latency_ms,
            "ids": kb_ids,
            "citations": list(kb_result.citations),
            "answer": kb_result.answer,
            "receipt": kb_result.receipt.to_dict(),
            "client_calls": client.calls,
        },
        "overlap": overlap,
        "candidate_count": max(len(local_ids), len(kb_ids)),
    }


def render_comparison(result: dict) -> str:
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    local = result["local"]
    kb = result["bedrock_kb"]
    lines = [
        "# L7 · BAGO ETL vs Bedrock Knowledge Base",
        "",
        f"Generated: {generated}",
        "",
        "> Scope: one identical query through the local BAGO ETL/RAG path and an injected Bedrock Knowledge Base client fixture.",
        "> The Bedrock side is not an AWS measurement: no credentials, network, managed KB, cloud latency or current price was used.",
        "",
        f"## Query\n\n`{result['query']}`",
        "",
        "## Comparison",
        "",
        "| Dimension | BAGO ETL + GovernedRAG | Bedrock Knowledge Base fixture |",
        "|---|---|---|",
        f"| Retrieval backend | {local['backend']} | {kb['backend']} |",
        f"| Returned references | {len(local['ids'])} | {len(kb['ids'])} |",
        f"| Reference overlap | {result['overlap']}/{result['candidate_count']} | {result['overlap']}/{result['candidate_count']} |",
        f"| Local fixture latency (ms) | {local['latency_ms']:.3f} | {kb['latency_ms']:.3f} |",
        "| Authority/provenance | BAGO metadata gate + ETL URI/revision | KB metadata + citation URI normalized by adapter |",
        "| Cost evidence | Local execution; no cloud inference cost | Receipt rate configured as $0.00 fixture; live price NOT_RUN |",
        "",
        "## Local BAGO context",
        "",
        f"Pipeline: `{', '.join(local['pipeline'])}`",
        "",
        _compact(local["context"]),
        "",
        "Citations:",
    ]
    lines.extend(f"- `{citation}`" for citation in local["citations"])
    lines.extend(
        [
            "",
            "## Bedrock-shaped answer and receipt",
            "",
            kb["answer"],
            "",
            "Citations:",
        ]
    )
    lines.extend(f"- `{citation}`" for citation in kb["citations"])
    lines.extend(
        [
            "",
            "Receipt summary:",
            "",
            "```json",
            json.dumps(kb["receipt"], indent=2, ensure_ascii=False),
            "```",
            "",
            "## Interpretation",
            "",
            "- BAGO ETL preserves local control over ingestion, metadata filtering and evidence references.",
            "- Bedrock Knowledge Bases provide managed retrieval/generation, but the provider boundary still needs BAGO permits, allowlists and receipts.",
            "- The matching references prove the comparison contract and citation normalization only; they do not prove equal ranking quality.",
            "- Live AWS validation remains `NOT_RUN` until IAM, data source, vector store, model access and credentials are supplied.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    result = build_comparison()
    output = REPO_ROOT / "evidence" / "bago_etl_vs_bedrock_kb_comparison.md"
    output.write_text(render_comparison(result), encoding="utf-8")
    print(output)
    print(
        f"query overlap={result['overlap']}/{result['candidate_count']} "
        f"local_ms={result['local']['latency_ms']:.3f} "
        f"kb_fixture_ms={result['bedrock_kb']['latency_ms']:.3f}"
    )


if __name__ == "__main__":
    main()
