"""L15 OpenTelemetry projection contract tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))

from observability.local_trace import LocalTrace, TraceEvent, TraceKind  # noqa: E402
from observability.otel_bridge import (  # noqa: E402
    RecordingSpanExporter,
    export_local_trace,
    normalize_otlp_http_endpoint,
)


def _trace() -> LocalTrace:
    root = "event-l15-root"
    retrieval = "event-l15-retrieval"
    return LocalTrace(
        trace_id="trace-l15-fixture",
        run_id="run-l15-fixture",
        events=(
            TraceEvent(
                event_id=root,
                trace_id="trace-l15-fixture",
                sequence=0,
                name="agent.run",
                kind=TraceKind.WORKFLOW,
                status="SUCCESS",
                attributes={"query": "local", "count": 1},
                evidence_refs=("receipt://run-l15",),
            ),
            TraceEvent(
                event_id=retrieval,
                trace_id="trace-l15-fixture",
                sequence=1,
                name="retrieval",
                kind=TraceKind.RETRIEVAL,
                status="SUCCESS",
                parent_event_id=root,
                attributes={"hits": 2, "pipeline": ["metadata", "evidence"]},
                evidence_refs=("docs/l15.md#revision=1",),
            ),
            TraceEvent(
                event_id="event-l15-denied",
                trace_id="trace-l15-fixture",
                sequence=2,
                name="permit",
                kind=TraceKind.AUTHORIZATION,
                status="DENIED",
                parent_event_id=retrieval,
                attributes={"decision": "DENY", "reason": {"code": "NO_PERMIT"}},
            ),
        ),
    )


def test_endpoint_normalization_is_explicit_and_deterministic():
    assert normalize_otlp_http_endpoint("http://collector:4318") == (
        "http://collector:4318/v1/traces"
    )
    assert normalize_otlp_http_endpoint("http://collector:4318/v1/traces/") == (
        "http://collector:4318/v1/traces"
    )
    with pytest.raises(ValueError):
        normalize_otlp_http_endpoint("  ")


def test_local_trace_projects_to_parented_spans_without_mutating_source():
    local_trace = _trace()
    before = local_trace.to_json()
    exporter = RecordingSpanExporter()

    receipt = export_local_trace(
        local_trace,
        exporter=exporter,
        endpoint="http://collector:4318",
        service_name="bago-l15-test",
    )

    assert receipt.status == "PASS"
    assert receipt.exported is True
    assert receipt.span_count == 3
    assert exporter.shutdown_called is True
    assert [span.name for span in exporter.spans] == ["agent.run", "retrieval", "permit"]
    assert exporter.spans[0].context.trace_id == exporter.spans[1].context.trace_id
    assert exporter.spans[1].parent.span_id == exporter.spans[0].context.span_id
    assert exporter.spans[2].parent.span_id == exporter.spans[1].context.span_id
    assert exporter.spans[1].attributes["bago.evidence_refs"] == ("docs/l15.md#revision=1",)
    assert local_trace.to_json() == before


def test_timestamped_local_event_preserves_timing_and_returns_export_trace_id():
    start_ns = 1_800_000_000_000_000_000
    end_ns = start_ns + 250_000_000
    event = TraceEvent(
        event_id="event-chat",
        trace_id="trace-chat-local",
        sequence=0,
        name="agent.chat",
        kind=TraceKind.WORKFLOW,
        status="COMPLETED",
        attributes={"model_id": "kimi-k2.6"},
        start_time_unix_nano=start_ns,
        end_time_unix_nano=end_ns,
    )
    local_trace = LocalTrace("trace-chat-local", "run-chat", (event,))
    exporter = RecordingSpanExporter()

    receipt = export_local_trace(
        local_trace,
        exporter=exporter,
        endpoint="http://collector:4318",
    )

    assert receipt.exported is True
    assert receipt.jaeger_trace_id == f"{exporter.spans[0].context.trace_id:032x}"
    assert exporter.spans[0].start_time == start_ns
    assert exporter.spans[0].end_time == end_ns
    assert local_trace.events[0].to_dict()["start_time_unix_nano"] == start_ns


class FailingExporter(SpanExporter):
    def export(self, spans):
        return SpanExportResult.FAILURE

    def shutdown(self, timeout_millis: int = 30_000) -> None:
        return None

    def force_flush(self, timeout_millis: int = 30_000) -> bool:
        return True


def test_exporter_failure_is_reported_and_does_not_become_a_success_claim():
    receipt = export_local_trace(
        _trace(),
        exporter=FailingExporter(),
        endpoint="http://collector:4318",
    )

    assert receipt.status == "FAILURE"
    assert receipt.exported is False
    assert "FAILURE" in receipt.error
