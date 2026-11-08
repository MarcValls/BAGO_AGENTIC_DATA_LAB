"""Read-only, privacy-bounded Codex OTLP-log observer for ADL.

Original Codex telemetry is *observational input*, not execution authority.
The saved event records are a partial, sanitized local witness; Jaeger is a
projection, not the source of truth. The observer never runs a monitored tool.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections import Counter
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Iterable

from opentelemetry.proto.collector.logs.v1.logs_service_pb2 import (
    ExportLogsServiceRequest,
    ExportLogsServiceResponse,
)

MAX_REQUEST_BYTES = 2 * 1024 * 1024
MAX_LOG_RECORDS = 2000
EVENT_TYPES = frozenset({
    "codex.conversation_starts", "codex.tool_result", "codex.tool_decision",
    "codex.api_request", "codex.turn_cost", "codex.sse_event",
    "codex.skill_invocation",
})
_SAFE_LABEL = re.compile(r"^[A-Za-z0-9_.:/+-]{1,120}$")
_HASH_ID = re.compile(r"^[0-9a-f]{32}$")


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:32]


def _scalar(value: Any) -> str | int | float | bool | None:
    field = value.WhichOneof("value")
    if field in ("string_value", "int_value", "double_value", "bool_value"):
        return getattr(value, field)
    return None


def _attrs(fields: Iterable[Any]) -> dict[str, Any]:
    return {item.key: _scalar(item.value) for item in fields if item.key}


def _label(value: Any) -> str | None:
    if isinstance(value, str) and _SAFE_LABEL.fullmatch(value):
        return value
    return None


def _bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.lower() in ("true", "false"):
        return value.lower() == "true"
    return None


def _duration(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        if isinstance(value, float) and not value.is_integer():
            return None
        parsed = int(value)
    except (ValueError, TypeError, OverflowError):
        return None
    return parsed if 0 <= parsed <= 86_400_000 else None


def _event_name(log: Any, fields: dict[str, Any]) -> str | None:
    choices = [getattr(log, "event_name", ""), fields.get("event.name"),
               fields.get("otel.name"), fields.get("name"), _scalar(log.body)]
    return next((item for item in choices if item in EVENT_TYPES), None)


@dataclass(frozen=True)
class Observation:
    event_id: str
    event_name: str
    session_ref: str
    timestamp_unix_nano: int | None
    attributes: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "source": "codex.otlp.logs",
            "coverage": "PARTIAL",
            "event_id": self.event_id,
            "event_name": self.event_name,
            "session_ref": self.session_ref,
            "timestamp_unix_nano": self.timestamp_unix_nano,
            "attributes": self.attributes,
        }


def parse_otlp_logs(raw: bytes) -> tuple[list[Observation], int]:
    """Decode only allowlisted metadata; never retain prompts, arguments or output."""
    if len(raw) > MAX_REQUEST_BYTES:
        raise ValueError("OTLP request too large")
    request = ExportLogsServiceRequest()
    try:
        request.ParseFromString(raw)
    except Exception as exc:
        raise ValueError("Invalid OTLP protobuf") from exc
    records = sum(len(group.log_records) for resource in request.resource_logs
                  for group in resource.scope_logs)
    if records > MAX_LOG_RECORDS:
        raise ValueError("Too many OTLP log records")
    accepted: list[Observation] = []
    for resource in request.resource_logs:
        resource_attrs = _attrs(resource.resource.attributes)
        service = resource_attrs.get("service.name")
        if not isinstance(service, str) or not service.lower().startswith("codex"):
            continue
        for group in resource.scope_logs:
            for log in group.log_records:
                fields = _attrs(log.attributes)
                event_name = _event_name(log, fields)
                if event_name is None:
                    continue
                session = fields.get("conversation.id") or fields.get("session.id")
                if not isinstance(session, str) or not session:
                    # No fabricated session identity: keep an explicitly unknown bucket.
                    session_ref = "unknown"
                else:
                    session_ref = _hash("session:" + session)
                attrs: dict[str, Any] = {}
                for from_key, to_key in (("tool_name", "tool_name"),
                                         ("tool.name", "tool_name"),
                                         ("model", "model"),
                                         ("skill.name", "skill_name")):
                    if to_key not in attrs:
                        clean = _label(fields.get(from_key))
                        if clean:
                            attrs[to_key] = clean
                if event_name == "codex.tool_result":
                    attrs["success"] = _bool(fields.get("success"))
                if event_name == "codex.tool_decision":
                    decision = fields.get("decision")
                    if decision in ("approved", "approved_for_session", "denied", "abort"):
                        attrs["decision"] = decision
                if event_name in ("codex.tool_result", "codex.api_request", "codex.sse_event"):
                    attrs["duration_ms"] = _duration(fields.get("duration_ms"))
                call_id = fields.get("call_id")
                if isinstance(call_id, str) and call_id:
                    attrs["call_ref"] = _hash("call:" + call_id)
                # Use native event timestamp only. Never pretend collector time is execution time.
                timestamp = int(log.time_unix_nano or log.observed_time_unix_nano) or None
                event_id = _hash(service + ":" + log.SerializeToString(deterministic=True).hex())
                accepted.append(Observation(event_id, event_name, session_ref,
                                            timestamp, attrs))
    return accepted, records - len(accepted)


def save_observation(root: Path, event: Observation) -> bool:
    """O_EXCL avoids overwriting or silently repairing an existing witness."""
    root.mkdir(parents=True, exist_ok=True)
    if not _HASH_ID.fullmatch(event.event_id):
        raise ValueError("Invalid event ID")
    target = root / (event.event_id + ".json")
    record = event.to_dict()
    record["witness_sha256"] = hashlib.sha256(json.dumps(
        record, ensure_ascii=True, sort_keys=True, separators=(",", ":"),
        allow_nan=False).encode("utf-8")).hexdigest()
    payload = json.dumps(record, ensure_ascii=True, sort_keys=True,
                         separators=(",", ":"), allow_nan=False).encode("utf-8") + b"\n"
    try:
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        if target.read_bytes() != payload:
            raise ValueError("Existing witness differs from new observation")
        return False
    with os.fdopen(fd, "wb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    return True


def load_observations(root: Path) -> tuple[list[dict[str, Any]], int]:
    if not root.is_dir():
        return [], 0
    records: list[dict[str, Any]] = []
    invalid = 0
    for entry in sorted(root.glob("*.json")):
        try:
            value = json.loads(entry.read_text(encoding="utf-8"))
            if (value.get("schema_version") != 1
                    or value.get("source") != "codex.otlp.logs"
                    or value.get("event_id") != entry.stem
                    or not _HASH_ID.fullmatch(entry.stem)
                    or value.get("event_name") not in EVENT_TYPES
                    or not isinstance(value.get("attributes"), dict)
                    or not isinstance(value.get("session_ref"), str)):
                raise ValueError("Invalid witness")
            checksum = value.pop("witness_sha256", None)
            expected = hashlib.sha256(json.dumps(
                value, ensure_ascii=True, sort_keys=True, separators=(",", ":"),
                allow_nan=False).encode("utf-8")).hexdigest()
            if checksum != expected:
                raise ValueError("Invalid witness")
            records.append(value)
        except (OSError, ValueError, TypeError, AttributeError):
            invalid += 1
    return records, invalid


def diagnostic_report(root: Path, *, slow_ms: int = 30_000) -> dict[str, Any]:
    events, invalid = load_observations(root)
    counts = Counter(e["event_name"] for e in events)
    findings: list[dict[str, Any]] = []
    for event in events:
        attrs = event["attributes"]
        if event["event_name"] == "codex.tool_result":
            if attrs.get("success") is False:
                findings.append({"rule": "TOOL_FAILURE_OBSERVED", "severity": "P1",
                                 "event_id": event["event_id"]})
            if isinstance(attrs.get("duration_ms"), int) and attrs["duration_ms"] >= slow_ms:
                findings.append({"rule": "SLOW_TOOL_REPORTED", "severity": "P2",
                                 "event_id": event["event_id"], "duration_ms": attrs["duration_ms"]})
        if event["event_name"] == "codex.tool_decision" and attrs.get("decision") in ("denied", "abort"):
            findings.append({"rule": "TOOL_DECISION_NOT_APPROVED", "severity": "INFO",
                             "event_id": event["event_id"]})
    if invalid:
        findings.append({"rule": "WITNESS_INTEGRITY_UNREADABLE", "severity": "P1",
                         "invalid_files": invalid})
    return {
        "status": "OBSERVED_PARTIAL" if events else "NO_DATA",
        "source": "codex.otlp.logs",
        "completeness": "PARTIAL",
        "events": len(events), "unreadable_records": invalid,
        "sessions_observed": len(set(e["session_ref"] for e in events)),
        "by_type": dict(sorted(counts.items())), "findings": findings,
        "limits": "Not a complete Codex execution record; no PID/causal inference/permission claims.",
    }


def project_to_jaeger(root: Path, *, endpoint: str = "http://127.0.0.1:4318/v1/traces",
                      max_events: int = 500) -> dict[str, Any]:
    """On-demand snapshot projection via ADL's existing LocalTrace bridge.

    Stable snapshot identity avoids saying this snapshot is an ongoing live trace.
    Parent links are intentionally absent without proven causal correlation.
    """
    from .local_trace import LocalTrace, TraceEvent, TraceKind
    from .otel_bridge import export_local_trace_to_otlp

    events, invalid = load_observations(root)
    if invalid or not events:
        return {"status": "INCONCLUSIVE", "reason": "Missing or invalid local witnesses"}
    if not 1 <= max_events <= 1000:
        raise ValueError("max_events must be in range 1..1000")
    events.sort(key=lambda e: (e["timestamp_unix_nano"] or 0, e["event_id"]))
    total_events = len(events)
    events = events[-max_events:]  # Explicitly bounded *latest* snapshot, never full-history claim.
    fingerprint = _hash("".join(e["event_id"] for e in events))
    trace_id = "trace-codex-activity-" + fingerprint
    trace_events = []
    for sequence, event in enumerate(events):
        attrs = event["attributes"]
        if attrs.get("success") is False:
            status = "FAILURE"
        elif attrs.get("decision") in ("denied", "abort"):
            status = "DENIED"
        else:
            status = "OBSERVED"
        ts = event["timestamp_unix_nano"]
        trace_events.append(TraceEvent(
            event_id="event-" + event["event_id"], trace_id=trace_id,
            sequence=sequence, name=event["event_name"],
            kind=TraceKind.TOOL if event["event_name"].startswith("codex.tool_") else TraceKind.WORKFLOW,
            status=status,
            attributes={**attrs, "session_ref": event["session_ref"],
                        "timing_source": "projection", "duration_measured": False},
            evidence_refs=("codex-activity://" + event["event_id"],),
            start_time_unix_nano=ts, end_time_unix_nano=ts,
        ))
    trace = LocalTrace(trace_id=trace_id, run_id="codex-activity-snapshot-" + fingerprint,
                       events=tuple(trace_events))
    try:
        result = export_local_trace_to_otlp(trace, endpoint=endpoint,
                                             service_name="adl-codex-activity")
        receipt = result.to_dict()
        receipt["observed_total"] = total_events
        receipt["projected_count"] = len(events)
        receipt["excluded_older"] = total_events - len(events)
        receipt["coverage"] = "PARTIAL"
        return receipt
    except Exception:
        return {"status": "INCONCLUSIVE", "reason": "Projection unavailable"}


def serve(root: Path, *, port: int = 4319) -> None:
    """Loopback-only OTLP protobuf logs listener. No execution or upstream proxy."""
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args: Any) -> None:
            return  # Do not leak raw telemetry in HTTP access logs.

        def do_GET(self) -> None:
            if self.path == "/health":
                self._reply_json(200, {"status": "READY", "capture": "PARTIAL"})
            elif self.path == "/report":
                self._reply_json(200, diagnostic_report(root))
            else:
                self.send_error(404)

        def _reply_json(self, status: int, obj: dict[str, Any]) -> None:
            body = json.dumps(obj, sort_keys=True).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self) -> None:
            if self.path != "/v1/logs":
                self.send_error(404)
                return
            if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/x-protobuf":
                self.send_error(415)
                return
            try:
                size = int(self.headers.get("Content-Length", ""))
            except ValueError:
                self.send_error(411)
                return
            if not 0 < size <= MAX_REQUEST_BYTES:
                self.send_error(413)
                return
            try:
                observations, _ignored = parse_otlp_logs(self.rfile.read(size))
                for event in observations:
                    save_observation(root, event)
            except (ValueError, OSError):
                self.send_error(400)
                return
            body = ExportLogsServiceResponse().SerializeToString()
            self.send_response(200)
            self.send_header("Content-Type", "application/x-protobuf")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = HTTPServer(("127.0.0.1", port), Handler)
    try:
        server.serve_forever(poll_interval=0.5)
    finally:
        server.server_close()
