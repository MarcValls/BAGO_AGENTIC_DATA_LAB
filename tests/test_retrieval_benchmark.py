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

    assert {result.top_k for result in results} == {10, 25, 50, 100}
    assert {result.filter_name for result in results} == {
        "all-current",
        "canonical-governance",
    }
    assert {result.mode.value for result in results} == {"lexical", "semantic", "hybrid"}
    assert {result.rerank for result in results} == {False, True}


def test_benchmark_metrics_are_bounded_and_queries_are_labelled():
    results = run_benchmark()

    assert len(benchmark_cases()) == 5
    assert len(build_benchmark_corpus()) == 12
    for result in results:
        assert 0.0 <= result.recall <= 1.0
        assert 0.0 <= result.precision <= 1.0
        assert 0.0 <= result.mrr <= 1.0


def test_benchmark_render_is_reviewable():
    rendered = render_benchmark(run_benchmark())

    assert "# L4 · Governed RAG benchmark" in rendered
    assert "lexical" in rendered
    assert "semantic" in rendered
    assert "hybrid" in rendered
    assert "top-k values 10, 25, 50 and 100" in rendered
    assert "does not authorize or execute" in rendered
