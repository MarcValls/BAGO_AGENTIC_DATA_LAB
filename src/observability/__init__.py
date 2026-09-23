"""Zero-cost local observability contracts for governed BAGO runs."""

from .local_trace import LocalTrace, LocalTraceBuilder, TraceEvent, TraceKind
from .otel_bridge import (
    DEFAULT_OTLP_HTTP_ENDPOINT,
    DEFAULT_SERVICE_NAME,
    OTelExportReceipt,
    RecordingSpanExporter,
    export_local_trace,
    export_local_trace_to_otlp,
    normalize_otlp_http_endpoint,
)

__all__ = [
    "DEFAULT_OTLP_HTTP_ENDPOINT",
    "DEFAULT_SERVICE_NAME",
    "LocalTrace",
    "LocalTraceBuilder",
    "OTelExportReceipt",
    "RecordingSpanExporter",
    "TraceEvent",
    "TraceKind",
    "export_local_trace",
    "export_local_trace_to_otlp",
    "normalize_otlp_http_endpoint",
]
