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
    query_count: int
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
    """Build a labelled corpus with hard negatives and no external model."""

    records = [
        (
            "permit-effect",
            "A valid permit grants authority for one operation; the gateway checks it before the operation executes.",
            "governance",
            AuthorityLevel.CANONICAL,
        ),
        (
            "action-scope",
            "The authorization boundary rejects actions outside the permitted scope before any external effect.",
            "governance",
            AuthorityLevel.CANONICAL,
        ),
        (
            "approval-step",
            "Record explicit human approval before an irreversible operation or external state change.",
            "governance",
            AuthorityLevel.CANONICAL,
        ),
        (
            "current-revision",
            "Only current verified policy revisions may justify a change; superseded rules cannot authorize it.",
            "governance",
            AuthorityLevel.CANONICAL,
        ),
        (
            "denied-permit",
            "A denied permit blocks the requested operation and records the rejected effect.",
            "governance",
            AuthorityLevel.CANONICAL,
        ),
        (
            "evidence-lineage",
            "An evidence receipt links each claim to its chunk, source URI and exact revision.",
            "evidence",
            AuthorityLevel.VERIFIED,
        ),
        (
            "etl-dedupe",
            "The ETL pipeline hashes normalized content to detect duplicates and avoid ingesting it twice.",
            "etl",
            AuthorityLevel.VERIFIED,
        ),
        (
            "mcp-effects",
            "MCP tool registration records effect classification so external side effects can be governed.",
            "mcp",
            AuthorityLevel.VERIFIED,
        ),
        (
            "chunk-overlap",
            "The chunker repeats a bounded tail from one text segment at the start of the next segment.",
            "etl",
            AuthorityLevel.VERIFIED,
        ),
        (
            "hybrid-fusion",
            "Hybrid retrieval fuses keyword BM25 and vector candidates before ranking the final list.",
            "retrieval",
            AuthorityLevel.VERIFIED,
        ),
        (
            "semantic-retrieval",
            "The semantic index compares query and document vectors to retrieve related passages.",
            "retrieval",
            AuthorityLevel.VERIFIED,
        ),
        (
            "provider-timeout",
            "Provider adapters enforce request timeouts and preserve a receipt for each invocation.",
            "providers",
            AuthorityLevel.PROPOSED,
        ),
        # Hard negatives deliberately share query vocabulary without answering the labelled question.
        ("permit-template", "A portfolio template explains how to request a permit for an operation; it does not grant authority.", "career", AuthorityLevel.PROPOSED),
        ("scope-report", "The monthly report measures the scope of completed gateway operations and external effects.", "analytics", AuthorityLevel.VERIFIED),
        ("approval-training", "Training material describes approval workflows and irreversible changes in a sample environment.", "training", AuthorityLevel.PROPOSED),
        ("policy-archive", "The policy archive stores revisions and superseded rules for historical comparison only.", "archive", AuthorityLevel.VERIFIED),
        ("permit-audit", "Auditors review permit requests, operation records, and gateway logs after execution.", "audit", AuthorityLevel.VERIFIED),
        ("receipt-storage", "Receipts are stored with timestamps and outcome codes for later inspection.", "evidence", AuthorityLevel.VERIFIED),
        ("etl-schedule", "A local scheduler starts the ETL pipeline each weekday and records job status.", "etl", AuthorityLevel.VERIFIED),
        ("hash-collision", "A content hash is useful for indexing but collisions require checking the original document.", "etl", AuthorityLevel.VERIFIED),
        ("mcp-transport", "MCP uses a transport protocol to exchange tool descriptions and invocation messages.", "mcp", AuthorityLevel.VERIFIED),
        ("tool-effects-guide", "A guide lists common side effects of writing files, sending messages, and updating records.", "mcp", AuthorityLevel.VERIFIED),
        ("text-boundaries", "Text segmentation splits a long report at paragraph boundaries without adding repeated text.", "etl", AuthorityLevel.VERIFIED),
        ("chunk-size", "The chunker limits each text segment to a configured maximum number of characters.", "etl", AuthorityLevel.VERIFIED),
        ("bm25-guide", "BM25 ranks documents from lexical term frequency and corpus document frequency.", "retrieval", AuthorityLevel.VERIFIED),
        ("vector-guide", "Vector search compares embeddings to find passages with similar representations.", "retrieval", AuthorityLevel.VERIFIED),
        ("rerank-guide", "A reranker sorts candidate passages after retrieval using an additional relevance score.", "retrieval", AuthorityLevel.VERIFIED),
        ("cloud-timeouts", "Cloud networking guidance recommends retries, timeouts, and circuit breakers for remote calls.", "providers", AuthorityLevel.PROPOSED),
        ("interview-roadmap", "The career roadmap lists AI engineering skills, interviews and portfolio milestones.", "career", AuthorityLevel.PROPOSED),
        ("database-index", "Database indexes accelerate lookups over document identifiers and metadata fields.", "storage", AuthorityLevel.VERIFIED),
        ("release-notes", "Release notes summarize features, resolved defects, and compatibility changes.", "product", AuthorityLevel.VERIFIED),
        ("market-report", "Market analysis compares current demand for data and artificial intelligence roles.", "career", AuthorityLevel.PROPOSED),
        ("test-report", "The test report records passed cases, skipped cases, and known limitations.", "testing", AuthorityLevel.VERIFIED),
    ]
    return [
        _chunk(chunk_id, content, domain=domain, authority=authority)
        for chunk_id, content, domain, authority in records
    ]


def benchmark_cases() -> tuple[BenchmarkCase, ...]:
    return (
        BenchmarkCase(
            "what grants authority for a specific operation at the gateway",
            frozenset({"permit-effect"}),
        ),
        BenchmarkCase(
            "how are actions outside authorization limits rejected before external changes",
            frozenset({"action-scope", "denied-permit"}),
        ),
        BenchmarkCase(
            "which human decision must precede an irreversible state change",
            frozenset({"approval-step"}),
        ),
        BenchmarkCase(
            "can outdated rules justify a change under the current policy",
            frozenset({"current-revision"}),
        ),
        BenchmarkCase(
            "trace this claim back to its exact source version",
            frozenset({"evidence-lineage"}),
        ),
        BenchmarkCase(
            "avoid storing the same input document more than once",
            frozenset({"etl-dedupe"}),
        ),
        BenchmarkCase(
            "how are tool calls that modify outside systems categorized",
            frozenset({"mcp-effects"}),
        ),
        BenchmarkCase(
            "keep repeated context where adjacent text segments meet",
            frozenset({"chunk-overlap"}),
        ),
        BenchmarkCase(
            "combine exact terms and related concepts into a unified ranking",
            frozenset({"hybrid-fusion", "semantic-retrieval"}),
        ),
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
    top_ks: Sequence[int] = (1, 3),
) -> list[BenchmarkResult]:
    corpus = tuple(chunks) if chunks is not None else tuple(build_benchmark_corpus())
    retriever = GovernedRAG(corpus)
    filters: Mapping[str, MetadataFilter] = {
        "all-current": MetadataFilter(),
        "canonical-governance": MetadataFilter(
            minimum_authority=AuthorityLevel.CANONICAL,
            allowed_domains=("governance",),
        ),
    }
    results: list[BenchmarkResult] = []
    for filter_name, metadata_filter in filters.items():
        eligible_ids = {
            chunk.chunk_id for chunk in corpus if metadata_filter.allows(chunk)
        }
        cases = [
            (case, case.relevant_ids & eligible_ids)
            for case in benchmark_cases()
        ]
        cases = [(case, relevant_ids) for case, relevant_ids in cases if relevant_ids]
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
                            relevant_ids,
                        )
                        for case, relevant_ids in cases
                    ]
                    results.append(
                        BenchmarkResult(
                            mode=mode,
                            rerank=rerank,
                            filter_name=filter_name,
                            top_k=top_k,
                            query_count=len(metrics),
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
        "- top-k values 1 and 3, chosen to expose ranking misses",
        "- current-all vs canonical-governance metadata filtering",
        "- metrics: Recall@1, Recall@3, Precision@k and MRR@k over difficult labelled queries",
        "- each filter is scored only against relevant evidence that survives that filter",
        "",
        f"Generated at: `{generated}`",
        "",
        "## Results",
        "",
        "| Filter | Mode | Rerank | k | Queries | Recall@k | Precision@k | MRR@k |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for result in results:
        lines.append(
            f"| {result.filter_name} | {result.mode.value} | "
            f"{'yes' if result.rerank else 'no'} | {result.top_k} | {result.query_count} | "
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
