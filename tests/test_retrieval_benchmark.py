"""Tests for the reproducible L4 benchmark receipt."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from benchmark_retrieval import (  # noqa: E402
    benchmark_cases,
    build_benchmark_corpus,
    render_benchmark,
    run_benchmark,
)


def test_benchmark_covers_required_comparison_dimensions():
    results = run_benchmark()

    assert {result.top_k for result in results} == {1, 3}
    assert {result.filter_name for result in results} == {
        "all-current",
        "canonical-governance",
    }
    assert {result.mode.value for result in results} == {"lexical", "semantic", "hybrid"}
    assert {result.rerank for result in results} == {False, True}
    assert {result.query_count for result in results if result.filter_name == "all-current"} == {9}
    assert {result.query_count for result in results if result.filter_name == "canonical-governance"} == {4}


def test_benchmark_metrics_are_bounded_and_queries_are_labelled():
    results = run_benchmark()

    corpus = build_benchmark_corpus()
    assert len(benchmark_cases()) == 9
    assert len(corpus) >= 30
    corpus_ids = {chunk.chunk_id for chunk in corpus}
    assert all(case.relevant_ids <= corpus_ids for case in benchmark_cases())
    for result in results:
        assert 0.0 <= result.recall <= 1.0
        assert 0.0 <= result.precision <= 1.0
        assert 0.0 <= result.mrr <= 1.0

    all_current_top_1 = {
        (result.recall, result.mrr)
        for result in results
        if result.filter_name == "all-current" and result.top_k == 1
    }
    assert len(all_current_top_1) > 1, "the benchmark must distinguish ranking strategies"


def test_benchmark_render_is_reviewable():
    rendered = render_benchmark(run_benchmark())

    assert "# L4 · Governed RAG benchmark" in rendered
    assert "lexical" in rendered
    assert "semantic" in rendered
    assert "hybrid" in rendered
    assert "top-k values 1 and 3" in rendered
    assert "Recall@1, Recall@3" in rendered
    assert "each filter is scored only against relevant evidence that survives that filter" in rendered
    assert "does not authorize or execute" in rendered
