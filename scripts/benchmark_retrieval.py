"""Generate a reproducible offline benchmark for the L4 retriever."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Iterable, Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
OUTPUT_PATH = REPO_ROOT / "evidence" / "retrieval_benchmark_results.md"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from metadata.schema import AuthorityLevel, ValidityStatus  # noqa: E402
from retrieval.governed_rag import (  # noqa: E402
    GovernedRAG,
    MetadataFilter,
    RetrievalChunk,
    RetrievalMode,
    RetrievalResponse,
)


@dataclass(frozen=True)
class BenchmarkCase:
    query: str
    relevant_ids: frozenset[str]


@dataclass(frozen=True)
class BenchmarkResult:
    mode: RetrievalMode
    rerank: bool
    filter_name: str
    top_k: int
    recall: float
    precision: float
    mrr: float


def _chunk(
    chunk_id: str,
    content: str,
    *,
    domain: str,
    authority: AuthorityLevel,
    validity: ValidityStatus = ValidityStatus.CURRENT,
) -> RetrievalChunk:
    return RetrievalChunk(
        chunk_id=chunk_id,
        document_id=f"doc-{chunk_id}",
        content=content,
        title=chunk_id.replace("-", " "),
        source_uri=f"benchmark://{chunk_id}",
        revision="v1",
        authority=authority,
        validity=validity,
        domain=domain,
        created_at="2026-09-21T12:00:00Z",
        metadata={"classification": ["BENCHMARK"]},
    )


def build_benchmark_corpus() -> list[RetrievalChunk]:
    """Use a small labelled corpus so metrics do not depend on a cloud model."""

    return [
        _chunk(
            "auth-permit",
            "A canonical Permit authorizes an Execution through the gateway.",
            domain="governance",
            authority=AuthorityLevel.CANONICAL,
        ),
        _chunk(
            "auth-boundary",
            "The AuthorizationBoundary validates action limits before effects.",
            domain="governance",
            authority=AuthorityLevel.CANONICAL,
        ),
        _chunk(
            "retrieval-hybrid",
            "Hybrid retrieval combines BM25 lexical matching with semantic embeddings.",
            domain="retrieval",
            authority=AuthorityLevel.VERIFIED,
        ),
        _chunk(
            "retrieval-rerank",
            "A reranker improves the final context order after candidate retrieval.",
            domain="retrieval",
            authority=AuthorityLevel.VERIFIED,
        ),
        _chunk(
            "evidence-lineage",
            "Evidence maps every claim to a chunk, source and revision.",
            domain="evidence",
            authority=AuthorityLevel.VERIFIED,
        ),
        _chunk(
            "evidence-receipt",
            "Receipts record the actual outcome and evidence references.",
            domain="evidence",
            authority=AuthorityLevel.VERIFIED,
        ),
        _chunk(
            "etl-idempotency",
            "Content hashing makes ETL ingestion idempotent and deduplicated.",
            domain="etl",
            authority=AuthorityLevel.VERIFIED,
        ),
        _chunk(
            "mcp-registration",
            "MCP tools need explicit registration and effect classification.",
            domain="mcp",
            authority=AuthorityLevel.PROPOSED,
        ),
        _chunk(
            "bedrock-provider",
            "A Bedrock provider adapter must preserve timeout and receipt boundaries.",
            domain="providers",
            authority=AuthorityLevel.PROPOSED,
        ),
        _chunk(
            "superseded-policy",
            "An old policy is superseded and must not be used as current authority.",
            domain="governance",
            authority=AuthorityLevel.CANONICAL,
            validity=ValidityStatus.SUPERSEDED,
        ),
        _chunk(
            "career-market",
            "The portfolio roadmap maps skills to AI engineering vacancies.",
            domain="career",
            authority=AuthorityLevel.PROPOSED,
        ),
        _chunk(
            "testing-contract",
            "CRIT P0 tests protect governed execution contracts.",
            domain="testing",
            authority=AuthorityLevel.VERIFIED,
        ),
    ]


def benchmark_cases() -> tuple[BenchmarkCase, ...]:
    return (
        BenchmarkCase("permit authorizes execution", frozenset({"auth-permit"})),
        BenchmarkCase("metadata hybrid semantic retrieval", frozenset({"retrieval-hybrid"})),
        BenchmarkCase("claim source revision evidence", frozenset({"evidence-lineage"})),
        BenchmarkCase("idempotent content hash ingestion", frozenset({"etl-idempotency"})),
        BenchmarkCase("registered MCP tools", frozenset({"mcp-registration"})),
    )


def _metrics(response: RetrievalResponse, relevant_ids: frozenset[str]) -> tuple[float, float, float]:
    returned = [hit.chunk.chunk_id for hit in response.hits]
    relevant_returned = sum(chunk_id in relevant_ids for chunk_id in returned)
    recall = relevant_returned / len(relevant_ids)
    precision = relevant_returned / max(len(returned), 1)
    reciprocal_rank = 0.0
    for rank, chunk_id in enumerate(returned, start=1):
        if chunk_id in relevant_ids:
            reciprocal_rank = 1.0 / rank
            break
    return recall, precision, reciprocal_rank


def run_benchmark(
    chunks: Iterable[RetrievalChunk] | None = None,
    *,
    top_ks: Sequence[int] = (10, 25, 50, 100),
) -> list[BenchmarkResult]:
    retriever = GovernedRAG(chunks or build_benchmark_corpus())
    filters: Mapping[str, MetadataFilter] = {
        "all-current": MetadataFilter(),
        "canonical-governance": MetadataFilter(
            minimum_authority=AuthorityLevel.CANONICAL,
            allowed_domains=("governance",),
        ),
    }
    results: list[BenchmarkResult] = []
    for filter_name, metadata_filter in filters.items():
        for mode in RetrievalMode:
            for rerank in (False, True):
                for top_k in top_ks:
                    metrics = [
                        _metrics(
                            retriever.retrieve(
                                case.query,
                                mode=mode,
                                top_k=top_k,
                                metadata_filter=metadata_filter,
                                rerank=rerank,
                            ),
                            case.relevant_ids,
                        )
                        for case in benchmark_cases()
                    ]
                    results.append(
                        BenchmarkResult(
                            mode=mode,
                            rerank=rerank,
                            filter_name=filter_name,
                            top_k=top_k,
                            recall=mean(item[0] for item in metrics),
                            precision=mean(item[1] for item in metrics),
                            mrr=mean(item[2] for item in metrics),
                        )
                    )
    return results


def _pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def render_benchmark(results: Sequence[BenchmarkResult]) -> str:
    generated = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    lines = [
        "# L4 · Governed RAG benchmark",
        "",
        "Generated by `scripts/benchmark_retrieval.py` from the deterministic",
        "labelled corpus in the same script. This is an offline engineering",
        "benchmark, not a claim of production embedding quality.",
        "",
        "## Contract covered",
        "",
        "- lexical BM25-like retrieval vs deterministic hash-semantic retrieval",
        "- hybrid score fusion with deterministic reranking on/off",
        "- top-k values 10, 25, 50 and 100",
        "- current-all vs canonical-governance metadata filtering",
        "- metrics: mean Recall@k, Precision@k and MRR@k over five labelled queries",
        "",
        f"Generated at: `{generated}`",
        "",
        "## Results",
        "",
        "| Filter | Mode | Rerank | k | Recall | Precision | MRR |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for result in results:
        lines.append(
            f"| {result.filter_name} | {result.mode.value} | "
            f"{'yes' if result.rerank else 'no'} | {result.top_k} | "
            f"{_pct(result.recall)} | {_pct(result.precision)} | {_pct(result.mrr)} |"
        )
    lines.extend(
        [
            "",
            "## Governance interpretation",
            "",
            "The metadata filter runs before ranking and removes superseded or",
            "below-authority chunks; ranking cannot reintroduce a filtered chunk.",
            "Every returned hit carries `chunk_id`, `document_id`, `source_uri` and",
            "`revision` through its evidence reference. Retrieval proposes context",
            "only; it does not authorize or execute an external effect.",
            "",
            "## Limitations",
            "",
            "The semantic baseline uses feature hashing so the result is reproducible",
            "without a model download. A production embedding adapter and a real",
            "cross-encoder remain later validation work; this receipt must not be",
            "read as evidence that a cloud model was evaluated.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    results = run_benchmark()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(render_benchmark(results), encoding="utf-8")
    print(f"Generated {OUTPUT_PATH.relative_to(REPO_ROOT)}")
    print(f"Rows: {len(results)} | queries: {len(benchmark_cases())}")


if __name__ == "__main__":
    main()
