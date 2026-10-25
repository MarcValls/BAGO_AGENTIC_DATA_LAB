"""Project BAGO's deterministic local trace into OpenTelemetry spans.

The local ``LocalTrace`` remains the evidence source of truth.  This module
only projects already-created events into an observability backend; it cannot
authorize, execute or alter a governed run.
"""

from __future__ import annotations

import hashlib
import json
import re
import os
import sqlite3
from pathlib import Path
from collections import deque
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from opentelemetry import trace as otel_trace
from opentelemetry.context import Context
from opentelemetry.sdk.trace.id_generator import IdGenerator
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
    jaeger_trace_id: str | None = None

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
            "jaeger_trace_id": self.jaeger_trace_id,
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
        self.trace_ids: list[str] = []

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        self.trace_ids.extend(
            f"{span.context.trace_id:032x}"
            for span in spans
            if span.context is not None
        )
        try:
            result = self.delegate.export(spans)
        except Exception:
            # Do not let SDK exception logging disclose exporter payloads or secrets.
            result = SpanExportResult.FAILURE
        if result is not SpanExportResult.SUCCESS:
            self.last_result = SpanExportResult.FAILURE
        return result

    def shutdown(self, timeout_millis: int = 30_000) -> None:
        try:
            self.delegate.shutdown(timeout_millis=timeout_millis)
        except TypeError:
            # OTLP HTTP exporters before/after the SDK signature transition
            # expose ``shutdown(self)`` without the timeout keyword.
            self.delegate.shutdown()

    def force_flush(self, timeout_millis: int = 30_000) -> bool:
        try:
            flushed = self.delegate.force_flush(timeout_millis=timeout_millis)
        except Exception:
            flushed = False
        if not flushed:
            self.last_result = SpanExportResult.FAILURE
        return flushed


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
        if key in ("web_read_sources", "workspace_read_sources"):
            continue
        safe_key = _KEY_PATTERN.sub("_", str(key)).strip("_") or "attribute"
        attributes[f"bago.event.{safe_key}"] = _attribute_value(value)
    measured = (
        event.start_time_unix_nano is not None
        and event.attributes.get("timing_source") != "projection"
        and event.attributes.get("duration_measured") is not False
    )
    attributes["timing_source"] = "native" if measured else "projection"
    attributes["duration_measured"] = measured
    attributes["bago.event.timing_source"] = attributes["timing_source"]
    attributes["bago.event.duration_measured"] = measured
    return attributes


def _set_status(span: Span, status: str) -> None:
    normalized = status.upper()
    if normalized in {"SUCCESS", "SUCCEEDED", "PASS", "COMPLETED", "ALLOW"}:
        span.set_status(Status(StatusCode.OK))
    elif normalized in {
        "FAILED", "FAIL", "FAILURE", "ERROR", "CONSTRAINT_VIOLATION",
        "DENY", "DENIED", "CANCELLED", "INCOMPLETE",
    }:
        span.set_status(Status(StatusCode.ERROR, description=normalized))
    else:
        span.set_status(Status(StatusCode.UNSET, description=normalized))


def _identity(*parts: str, size: int) -> int:
    encoded = json.dumps(parts, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    return int.from_bytes(hashlib.sha256(encoded).digest()[:size], "big") or 1


class _EvidenceIds(IdGenerator):
    """Provider-local IDs; stable identity is not exactly-once delivery."""

    def __init__(self, local_trace: LocalTrace) -> None:
        self.trace_id = _identity("bago.local-trace.v1", local_trace.trace_id, size=16)
        self.span_id = 0

    def generate_trace_id(self) -> int:
        return self.trace_id

    def generate_span_id(self) -> int:
        return self.span_id


def _validated_events(local_trace: LocalTrace) -> tuple[TraceEvent, ...]:
    """Validate the entire graph before creating a provider or exporting anything."""

    events: dict[str, TraceEvent] = {}
    span_ids: set[int] = set()
    for event in local_trace.events:
        if event.event_id in events:
            raise ValueError("Duplicate event ID")
        if event.trace_id != local_trace.trace_id:
            raise ValueError("Event trace ID does not match LocalTrace")
        start, end = event.start_time_unix_nano, event.end_time_unix_nano
        if (start is None) != (end is None):
            raise ValueError("Incomplete event interval")
        if start is not None and (
            type(start) is not int or type(end) is not int or start < 0 or end < start
        ):
            raise ValueError("Invalid event interval")
        span_id = _identity("bago.local-event.v1", local_trace.trace_id, event.event_id, size=8)
        if span_id in span_ids:
            raise ValueError("Event span ID collision")
        span_ids.add(span_id)
        events[event.event_id] = event

    children: dict[str, list[str]] = {event_id: [] for event_id in events}
    ready: deque[str] = deque()
    for event in events.values():
        if event.parent_event_id is None:
            ready.append(event.event_id)
        elif event.parent_event_id not in events:
            raise ValueError("Missing event parent")
        else:
            children[event.parent_event_id].append(event.event_id)
    ordered: list[TraceEvent] = []
    while ready:
        event_id = ready.popleft()
        ordered.append(events[event_id])
        ready.extend(children[event_id])
    if len(ordered) != len(events):
        raise ValueError("Event graph contains a cycle")
    return tuple(ordered)


def _export_local_trace_unledgered(
    local_trace: LocalTrace,
    *,
    exporter: SpanExporter,
    endpoint: str = DEFAULT_OTLP_HTTP_ENDPOINT,
    service_name: str = DEFAULT_SERVICE_NAME,
) -> OTelExportReceipt:
    """Project validated evidence without inheriting an ambient trace.

    Stable IDs identify the same evidence on retries, not exactly-once storage.
    Missing measurements describe projection time only, never executed work.
    """

    if not service_name.strip():
        raise ValueError("service_name is required")
    normalized_endpoint = normalize_otlp_http_endpoint(endpoint)
    events = _validated_events(local_trace)
    attributes_by_id = {
        event.event_id: _span_attributes(local_trace, event) for event in events
    }
    ids = _EvidenceIds(local_trace)
    capturing = _CapturingExporter(exporter)
    provider = TracerProvider(
        resource=Resource.create(
            {
                "service.name": service_name,
                "service.version": "l15",
                "bago.observability.scope": "local",
            }
        ),
        id_generator=ids,
        shutdown_on_exit=False,
    )
    processor = SimpleSpanProcessor(capturing)
    provider.add_span_processor(processor)
    tracer = provider.get_tracer("bago.observability", "l15")
    spans_by_event_id: dict[str, Span] = {}
    error = ""

    try:
        for event in events:
            parent = spans_by_event_id.get(event.parent_event_id)
            context = Context() if parent is None else set_span_in_context(parent, Context())
            ids.span_id = _identity(
                "bago.local-event.v1", local_trace.trace_id, event.event_id, size=8
            )
            start_options: dict[str, Any] = {}
            if event.start_time_unix_nano is not None:
                start_options["start_time"] = event.start_time_unix_nano
            span = tracer.start_span(
                event.name, context=context,
                attributes=attributes_by_id[event.event_id], **start_options,
            )
            _set_status(span, event.status)
            span.end(end_time=event.end_time_unix_nano)
            spans_by_event_id[event.event_id] = span
        if not processor.force_flush() or not capturing.force_flush():
            error = "OpenTelemetry exporter did not flush"
        if capturing.last_result is SpanExportResult.FAILURE:
            error = "OpenTelemetry exporter returned FAILURE"
    except Exception:
        error = "OpenTelemetry projection failed"
    finally:
        try:
            provider.shutdown()
        except Exception:
            error = "OpenTelemetry exporter shutdown failed"

    exported = not error and len(spans_by_event_id) == len(events)
    return OTelExportReceipt(
        trace_id=local_trace.trace_id,
        endpoint=normalized_endpoint,
        service_name=service_name,
        span_count=len(local_trace.events),
        exported=exported,
        status="PASS" if exported else "FAILURE",
        error=error,
        jaeger_trace_id=(capturing.trace_ids[0] if exported and capturing.trace_ids else None),
    )


def _ledger_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _ledger_hash(value: Any) -> str:
    return hashlib.sha256(_ledger_json(value).encode("utf-8")).hexdigest()


def _ledger_connect(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path.resolve().as_uri() + "?mode=rw", uri=True, timeout=10.0)
    try:
        connection.execute("PRAGMA synchronous=FULL")
        if connection.execute("PRAGMA journal_mode=DELETE").fetchone() != ("delete",):
            raise ValueError("Unsupported ledger journal")
        if connection.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
            raise ValueError("Invalid ledger integrity")
        return connection
    except (sqlite3.Error, ValueError):
        connection.close()
        raise


def _ledger_read(connection: sqlite3.Connection, trace_id: str) -> dict[str, Any] | None:
    if connection.execute("SELECT version FROM ledger_format").fetchall() != [(1,)]:
        raise ValueError("Invalid ledger format")
    row = connection.execute(
        "SELECT record, checksum FROM claims WHERE trace_id = ?", (trace_id,)
    ).fetchone()
    if row is None:
        return None
    record = json.loads(row[0])
    if not isinstance(record, dict) or set(record) != {"binding", "state", "receipt"}:
        raise ValueError("Invalid ledger record")
    if _ledger_hash(record) != row[1]:
        raise ValueError("Invalid ledger checksum")
    if record["state"] not in {"STARTED", "SUCCESS"}:
        raise ValueError("Invalid ledger state")
    if record["state"] == "STARTED" and record["receipt"] is not None:
        raise ValueError("Invalid pending receipt")
    return record


def _ledger_claim(path: Path, trace_id: str, binding: str) -> dict[str, Any] | None:
    # Exclusive file creation distinguishes initialization from a damaged old DB.
    # SQLite FULL commits, rather than POSIX directory fsync, provide durability.
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        created = False
    else:
        os.close(descriptor)
        created = True
    connection = _ledger_connect(path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        if created:
            connection.execute("CREATE TABLE ledger_format (version INTEGER NOT NULL)")
            connection.execute("INSERT INTO ledger_format VALUES (1)")
            connection.execute(
                "CREATE TABLE claims (trace_id TEXT PRIMARY KEY NOT NULL, "
                "record TEXT NOT NULL, checksum TEXT NOT NULL)"
            )
        previous = _ledger_read(connection, trace_id)
        if previous is not None:
            connection.rollback()
            return previous
        record = {"binding": binding, "state": "STARTED", "receipt": None}
        connection.execute(
            "INSERT INTO claims VALUES (?, ?, ?)",
            (trace_id, _ledger_json(record), _ledger_hash(record)),
        )
        connection.commit()
        return None
    finally:
        connection.close()


def _ledger_finish(path: Path, trace_id: str, binding: str, receipt: OTelExportReceipt) -> None:
    connection = _ledger_connect(path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        previous = _ledger_read(connection, trace_id)
        if previous != {"binding": binding, "state": "STARTED", "receipt": None}:
            raise ValueError("Ledger claim changed")
        record = {"binding": binding, "state": "SUCCESS", "receipt": receipt.to_dict()}
        connection.execute(
            "UPDATE claims SET record = ?, checksum = ? WHERE trace_id = ?",
            (_ledger_json(record), _ledger_hash(record), trace_id),
        )
        connection.commit()
    finally:
        connection.close()
    # A failed readback is uncertainty, never a success-shaped fallback.
    connection = _ledger_connect(path)
    try:
        if _ledger_read(connection, trace_id) != record:
            raise ValueError("Ledger commit could not be verified")
    finally:
        connection.close()


def export_local_trace(
    local_trace: LocalTrace,
    *,
    exporter: SpanExporter,
    endpoint: str = DEFAULT_OTLP_HTTP_ENDPOINT,
    service_name: str = DEFAULT_SERVICE_NAME,
    ledger_dir: str | os.PathLike[str] | None = None,
) -> OTelExportReceipt:
    """Optionally fence export attempts using a host-owned durable SQLite ledger.

    STARTED is permanent unless a verified success is committed. No automatic
    retry follows uncertainty. This is not exactly-once network delivery, nor
    protection against a hostile writer replacing the entire ledger directory.
    """
    if ledger_dir is None:
        return _export_local_trace_unledgered(
            local_trace, exporter=exporter, endpoint=endpoint, service_name=service_name,
        )
    if not service_name.strip():
        raise ValueError("service_name is required")
    normalized_endpoint = normalize_otlp_http_endpoint(endpoint)
    events = _validated_events(local_trace)
    # Validate attribute conversion before claiming or creating any spans.
    for event in events:
        _span_attributes(local_trace, event)
    inconclusive = OTelExportReceipt(
        trace_id=local_trace.trace_id, endpoint=normalized_endpoint,
        service_name=service_name, span_count=len(events), exported=False,
        status="INCONCLUSIVE", error="Durable export unavailable or outcome uncertain",
    )
    try:
        binding = _ledger_hash({
            "version": 1, "local_trace": local_trace.to_dict(),
            "endpoint": normalized_endpoint, "service_name": service_name,
        })
        directory = Path(ledger_dir)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "otel-export-ledger.sqlite3"
        previous = _ledger_claim(path, local_trace.trace_id, binding)
        if previous is not None:
            if previous["binding"] != binding or previous["state"] != "SUCCESS":
                return inconclusive
            # Validate the stored receipt against this evidence and destination.
            expected = OTelExportReceipt(
                trace_id=local_trace.trace_id, endpoint=normalized_endpoint,
                service_name=service_name, span_count=len(events), exported=True,
                status="PASS", jaeger_trace_id=(
                    f"{_identity('bago.local-trace.v1', local_trace.trace_id, size=16):032x}"
                    if events else None
                ),
            )
            if previous["receipt"] != expected.to_dict():
                return inconclusive
            return expected
    except (OSError, sqlite3.Error, ValueError, TypeError, OverflowError):
        return inconclusive
    try:
        receipt = _export_local_trace_unledgered(
            local_trace, exporter=exporter, endpoint=normalized_endpoint,
            service_name=service_name,
        )
    except Exception:
        # The delegate/SDK is an external effect boundary; retain STARTED and
        # report uncertainty without disclosing arbitrary exception payloads.
        return inconclusive
    if not receipt.exported or receipt.status != "PASS":
        return inconclusive
    try:
        _ledger_finish(path, local_trace.trace_id, binding, receipt)
    except (OSError, sqlite3.Error, ValueError, TypeError, OverflowError):
        return inconclusive
    return receipt


def export_local_trace_to_otlp(
    local_trace: LocalTrace,
    *,
    endpoint: str = DEFAULT_OTLP_HTTP_ENDPOINT,
    service_name: str = DEFAULT_SERVICE_NAME,
    timeout: float = 10.0,
    ledger_dir: str | os.PathLike[str] | None = None,
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
        ledger_dir=ledger_dir,
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
