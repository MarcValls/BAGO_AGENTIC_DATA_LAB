"""Project BAGO's deterministic local trace into OpenTelemetry spans.

The local ``LocalTrace`` remains the evidence source of truth.  This module
only projects already-created events into an observability backend; it cannot
authorize, execute or alter a governed run.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from opentelemetry import trace as otel_trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, Span, TracerProvider
from opentelemetry.sdk.trace.export import (
    SimpleSpanProcessor,
    SpanExportResult,
    SpanExporter,
)
from opentelemetry.trace import Status, StatusCode, set_span_in_context

from .local_trace import LocalTrace, TraceEvent


DEFAULT_OTLP_HTTP_ENDPOINT = "http://localhost:4318/v1/traces"
DEFAULT_SERVICE_NAME = "bago-agentic-data-lab"
_KEY_PATTERN = re.compile(r"[^a-zA-Z0-9_.-]+")


@dataclass(frozen=True)
class OTelExportReceipt:
    """Reviewable result of projecting one ``LocalTrace``."""

    trace_id: str
    endpoint: str
    service_name: str
    span_count: int
    exported: bool
    status: str
    error: str = ""
    cost_usd: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "endpoint": self.endpoint,
            "service_name": self.service_name,
            "span_count": self.span_count,
            "exported": self.exported,
            "status": self.status,
            "error": self.error,
            "cost_usd": self.cost_usd,
        }


class RecordingSpanExporter(SpanExporter):
    """Small in-memory exporter used by unit tests and dry-run checks."""

    def __init__(self) -> None:
        self.spans: list[ReadableSpan] = []
        self.export_results: list[SpanExportResult] = []
        self.shutdown_called = False

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        self.spans.extend(spans)
        self.export_results.append(SpanExportResult.SUCCESS)
        return SpanExportResult.SUCCESS

    def shutdown(self, timeout_millis: int = 30_000) -> None:
        self.shutdown_called = True

    def force_flush(self, timeout_millis: int = 30_000) -> bool:
        return True


class _CapturingExporter(SpanExporter):
    """Capture exporter failures that the SDK otherwise logs and swallows."""

    def __init__(self, delegate: SpanExporter) -> None:
        self.delegate = delegate
        self.last_result = SpanExportResult.SUCCESS

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        self.last_result = self.delegate.export(spans)
        return self.last_result

    def shutdown(self, timeout_millis: int = 30_000) -> None:
        try:
            self.delegate.shutdown(timeout_millis=timeout_millis)
        except TypeError:
            # OTLP HTTP exporters before/after the SDK signature transition
            # expose ``shutdown(self)`` without the timeout keyword.
            self.delegate.shutdown()

    def force_flush(self, timeout_millis: int = 30_000) -> bool:
        return self.delegate.force_flush(timeout_millis=timeout_millis)


def normalize_otlp_http_endpoint(endpoint: str) -> str:
    """Normalize an OTLP HTTP endpoint to the traces path."""

    normalized = endpoint.strip().rstrip("/")
    if not normalized:
        raise ValueError("OTLP endpoint is required")
    if not normalized.endswith("/v1/traces"):
        normalized += "/v1/traces"
    return normalized


def _json_value(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _attribute_value(value: Any) -> str | bool | int | float | tuple[str, ...]:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, float):
        return value
    if isinstance(value, str):
        return value
    if isinstance(value, Mapping):
        return _json_value(value)
    if isinstance(value, (list, tuple, set, frozenset)):
        return tuple(str(item) for item in value)
    return str(value)


def _span_attributes(local_trace: LocalTrace, event: TraceEvent) -> dict[str, Any]:
    attributes: dict[str, Any] = {
        "bago.trace_id": local_trace.trace_id,
        "bago.run_id": local_trace.run_id,
        "bago.event_id": event.event_id,
        "bago.sequence": event.sequence,
        "bago.kind": event.kind.value,
        "bago.status": event.status,
        "bago.evidence_refs": tuple(event.evidence_refs),
    }
    for key, value in event.attributes.items():
        safe_key = _KEY_PATTERN.sub("_", str(key)).strip("_") or "attribute"
        attributes[f"bago.event.{safe_key}"] = _attribute_value(value)
    return attributes


def _set_status(span: Span, status: str) -> None:
    normalized = status.upper()
    if normalized in {"SUCCESS", "PASS", "COMPLETED", "ALLOW"}:
        span.set_status(Status(StatusCode.OK))
    elif normalized in {"FAILURE", "ERROR", "CONSTRAINT_VIOLATION"}:
        span.set_status(Status(StatusCode.ERROR, description=normalized))
    else:
        span.set_status(Status(StatusCode.UNSET, description=normalized))


def export_local_trace(
    local_trace: LocalTrace,
    *,
    exporter: SpanExporter,
    endpoint: str = DEFAULT_OTLP_HTTP_ENDPOINT,
    service_name: str = DEFAULT_SERVICE_NAME,
) -> OTelExportReceipt:
    """Export one local trace using an injected or OTLP exporter.

    Parent links are reconstructed from ``TraceEvent.parent_event_id``.  The
    function fails closed for exporter failures and never changes the source
    ``LocalTrace``.
    """

    if not service_name.strip():
        raise ValueError("service_name is required")
    normalized_endpoint = normalize_otlp_http_endpoint(endpoint)
    capturing = _CapturingExporter(exporter)
    provider = TracerProvider(
        resource=Resource.create(
            {
                "service.name": service_name,
                "service.version": "l15",
                "bago.observability.scope": "local",
            }
        ),
        shutdown_on_exit=False,
    )
    processor = SimpleSpanProcessor(capturing)
    provider.add_span_processor(processor)
    tracer = provider.get_tracer("bago.observability", "l15")
    spans_by_event_id: dict[str, Span] = {}
    error = ""

    try:
        for event in local_trace.events:
            parent = spans_by_event_id.get(event.parent_event_id or "")
            context = set_span_in_context(parent) if parent is not None else None
            span = tracer.start_span(
                event.name,
                context=context,
                attributes=_span_attributes(local_trace, event),
            )
            _set_status(span, event.status)
            span.end()
            spans_by_event_id[event.event_id] = span
        flushed = processor.force_flush()
        if not flushed:
            error = "OpenTelemetry span processor did not flush"
        if capturing.last_result is SpanExportResult.FAILURE:
            error = "OpenTelemetry exporter returned FAILURE"
    except Exception as exc:  # pragma: no cover - exercised by live exporter failures
        error = f"{type(exc).__name__}: {exc}"
    finally:
        provider.shutdown()

    exported = not error and len(spans_by_event_id) == len(local_trace.events)
    return OTelExportReceipt(
        trace_id=local_trace.trace_id,
        endpoint=normalized_endpoint,
        service_name=service_name,
        span_count=len(local_trace.events),
        exported=exported,
        status="PASS" if exported else "FAILURE",
        error=error,
    )


def export_local_trace_to_otlp(
    local_trace: LocalTrace,
    *,
    endpoint: str = DEFAULT_OTLP_HTTP_ENDPOINT,
    service_name: str = DEFAULT_SERVICE_NAME,
    timeout: float = 10.0,
) -> OTelExportReceipt:
    """Export one ``LocalTrace`` to an OTLP/HTTP collector."""

    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

    normalized_endpoint = normalize_otlp_http_endpoint(endpoint)
    exporter = OTLPSpanExporter(endpoint=normalized_endpoint, timeout=timeout)
    return export_local_trace(
        local_trace,
        exporter=exporter,
        endpoint=normalized_endpoint,
        service_name=service_name,
    )


__all__ = [
    "DEFAULT_OTLP_HTTP_ENDPOINT",
    "DEFAULT_SERVICE_NAME",
    "OTelExportReceipt",
    "RecordingSpanExporter",
    "export_local_trace",
    "export_local_trace_to_otlp",
    "normalize_otlp_http_endpoint",
]
