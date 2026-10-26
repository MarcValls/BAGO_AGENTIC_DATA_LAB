"""L15 OpenTelemetry projection contract tests."""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

from opentelemetry import context as otel_context, trace as otel_trace
from opentelemetry.trace import NonRecordingSpan, SpanContext, StatusCode, TraceFlags

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


def test_child_before_parent_is_causal_and_ids_survive_reordering():
    source = _trace()
    # Deliberately contradictory sequence and wall-clock order: neither is causal.
    events = tuple(
        replace(event, sequence=10 - index,
                start_time_unix_nano=1_800_000_000_000_000_000 - index * 100,
                end_time_unix_nano=1_800_000_000_000_000_050 - index * 100)
        for index, event in enumerate(source.events)
    )
    source = replace(source, events=events)
    before = source.to_json()
    first, second = RecordingSpanExporter(), RecordingSpanExporter()
    assert export_local_trace(source, exporter=first).exported
    assert export_local_trace(replace(source, events=events[::-1]), exporter=second).exported
    assert [span.name for span in second.spans] == ["agent.run", "retrieval", "permit"]
    identities = lambda exporter: {
        span.attributes["bago.event_id"]: (span.context.trace_id, span.context.span_id)
        for span in exporter.spans
    }
    assert identities(first) == identities(second)
    assert second.spans[1].parent.span_id == second.spans[0].context.span_id
    assert second.spans[2].parent.span_id == second.spans[1].context.span_id
    assert source.to_json() == before


@pytest.mark.parametrize("defect", [
    "duplicate", "trace_id", "missing_parent", "cycle", "self_cycle",
    "inverted_interval", "partial_interval", "negative_interval", "float_interval",
])
def test_whole_graph_is_rejected_before_any_export(defect):
    source = _trace()
    root, child, last = source.events
    if defect == "duplicate":
        events = (root, child, last, last)
    elif defect == "trace_id":
        events = (root, child, replace(last, trace_id="foreign-trace"))
    elif defect == "missing_parent":
        events = (root, child, replace(last, parent_event_id="absent"))
    elif defect == "cycle":
        events = (root, replace(child, parent_event_id=last.event_id), last)
    elif defect == "self_cycle":
        events = (root, child, replace(last, parent_event_id=last.event_id))
    else:
        # Simulate malformed deserialized evidence, bypassing dataclass guards.
        last = replace(last)
        start, end = {
            "inverted_interval": (20, 10),
            "partial_interval": (10, None),
            "negative_interval": (-1, 10),
            "float_interval": (1.5, 10),
        }[defect]
        object.__setattr__(last, "start_time_unix_nano", start)
        object.__setattr__(last, "end_time_unix_nano", end)
        events = (root, child, last)
    exporter = RecordingSpanExporter()
    with pytest.raises(ValueError):
        export_local_trace(replace(source, events=events), exporter=exporter)
    assert exporter.spans == []
    assert exporter.export_results == []
    assert exporter.shutdown_called is False


def test_ambient_trace_is_not_inherited_even_when_not_sampled():
    ambient = SpanContext(
        trace_id=123, span_id=456, is_remote=True, trace_flags=TraceFlags(0),
    )
    token = otel_context.attach(otel_trace.set_span_in_context(NonRecordingSpan(ambient)))
    try:
        exporter = RecordingSpanExporter()
        assert export_local_trace(_trace(), exporter=exporter).exported
        assert exporter.spans[0].parent is None
        assert exporter.spans[0].context.trace_id != ambient.trace_id
        assert otel_trace.get_current_span().get_span_context() == ambient
    finally:
        otel_context.detach(token)


def test_projection_timing_is_explicit_and_native_timestamps_are_exact():
    source = _trace()
    start = 1_800_000_000_000_000_000
    native = replace(source.events[1], start_time_unix_nano=start,
                     end_time_unix_nano=start + 120_000_000)
    source = replace(source, events=(source.events[0], native, source.events[2]))
    exporter = RecordingSpanExporter()
    assert export_local_trace(source, exporter=exporter).exported
    root, child, _ = exporter.spans
    assert root.attributes["timing_source"] == "projection"
    assert root.attributes["duration_measured"] is False
    assert child.attributes["timing_source"] == "native"
    assert child.attributes["duration_measured"] is True
    assert child.start_time == start
    assert child.end_time == start + 120_000_000
    projected = replace(native, attributes={"timing_source": "projection"})
    exporter = RecordingSpanExporter()
    assert export_local_trace(replace(source, events=(source.events[0], projected)),
                              exporter=exporter).exported
    assert exporter.spans[1].attributes["duration_measured"] is False
    assert exporter.spans[1].start_time == start


class FirstFailureExporter(RecordingSpanExporter):
    def export(self, spans):
        super().export(spans)
        result = SpanExportResult.FAILURE if len(self.spans) == 1 else SpanExportResult.SUCCESS
        self.export_results[-1] = result
        return result


def test_early_export_failure_cannot_be_hidden_by_later_success():
    exporter = FirstFailureExporter()
    receipt = export_local_trace(_trace(), exporter=exporter)
    assert exporter.export_results == [
        SpanExportResult.FAILURE, SpanExportResult.SUCCESS, SpanExportResult.SUCCESS,
    ]
    assert receipt.exported is False
    assert receipt.status == "FAILURE"
    assert "FAILURE" in receipt.error
    assert receipt.jaeger_trace_id is None


@pytest.mark.parametrize("status", [
    "FAILED", "FAIL", "FAILURE", "DENY", "DENIED", "CANCELLED", "INCOMPLETE",
    "SUCCEEDED", "RUNNING",
])
def test_status_mapping_is_honest(status):
    source = _trace()
    exporter = RecordingSpanExporter()
    event = replace(source.events[0], status=status)
    assert export_local_trace(replace(source, events=(event,)), exporter=exporter).exported
    expected = (StatusCode.OK if status == "SUCCEEDED" else
                StatusCode.UNSET if status == "RUNNING" else StatusCode.ERROR)
    assert exporter.spans[0].status.status_code is expected
    assert exporter.spans[0].attributes["bago.status"] == status


@pytest.mark.parametrize("phase", ["export", "flush", "shutdown"])
def test_exporter_exceptions_are_sanitized_in_receipt_and_logs(phase, caplog):
    canary = "SECRET-exporter-payload-do-not-disclose"

    class RaisingExporter(RecordingSpanExporter):
        def export(self, spans):
            if phase == "export":
                raise RuntimeError(canary)
            return super().export(spans)

        def force_flush(self, timeout_millis=30_000):
            if phase == "flush":
                raise RuntimeError(canary)
            return True

        def shutdown(self, timeout_millis=30_000):
            if phase == "shutdown":
                raise RuntimeError(canary)
            super().shutdown(timeout_millis)

    receipt = export_local_trace(_trace(), exporter=RaisingExporter())
    assert receipt.exported is False
    assert receipt.status == "FAILURE"
    assert receipt.error
    assert canary not in str(receipt.to_dict())
    assert canary not in caplog.text

