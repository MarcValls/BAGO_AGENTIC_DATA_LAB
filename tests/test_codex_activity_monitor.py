"""Negative/positive checks for the optional Codex OTLP witness."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from opentelemetry.proto.collector.logs.v1.logs_service_pb2 import ExportLogsServiceRequest
from opentelemetry.proto.common.v1.common_pb2 import KeyValue
from observability.codex_activity_monitor import (
    Observation,
    diagnostic_report,
    load_observations,
    parse_otlp_logs,
    save_observation,
)


def _kv(key, val):
    item = KeyValue(key=key)
    if isinstance(val, bool):
        item.value.bool_value = val
    elif isinstance(val, int):
        item.value.int_value = val
    else:
        item.value.string_value = val
    return item


def _payload(*, service="codex_cli_rs", event="codex.tool_result", extra=None,
             event_in_body=False):
    req = ExportLogsServiceRequest()
    resource = req.resource_logs.add()
    resource.resource.attributes.append(_kv("service.name", service))
    record = resource.scope_logs.add().log_records.add()
    record.time_unix_nano = 1800000000000000000
    if event_in_body:
        record.body.string_value = event
    else:
        record.event_name = event
    details = {
        "conversation.id": "sensitive-session-id",
        "call_id": "sensitive-call-id",
        "tool_name": "functions.shell",
        "success": "false",
        "duration_ms": 35000,
        "output": "SECRET-output-do-not-store",
        "arguments": "SECRET-arguments-do-not-store",
        "prompt": "SECRET-prompt-do-not-store",
        "user.account_id": "SECRET-identity-do-not-store",
    }
    details.update(extra or {})
    for key, val in details.items():
        record.attributes.append(_kv(key, val))
    return req.SerializeToString()


def test_privacy_allowlist_does_not_persist_raw_payload(tmp_path):
    parsed, ignored = parse_otlp_logs(_payload())
    assert ignored == 0 and len(parsed) == 1
    event = parsed[0]
    assert event.event_name == "codex.tool_result"
    assert event.attributes["success"] is False
    assert event.attributes["duration_ms"] == 35000
    assert event.session_ref != "sensitive-session-id"
    assert event.attributes["call_ref"] != "sensitive-call-id"
    assert save_observation(tmp_path, event)
    content = (tmp_path / f"{event.event_id}.json").read_text()
    for secret in ("SECRET", "sensitive-session-id", "sensitive-call-id"):
        assert secret not in content


def test_replay_deduplicates_and_does_not_rewrite(tmp_path):
    event = parse_otlp_logs(_payload())[0][0]
    assert save_observation(tmp_path, event)
    first = (tmp_path / f"{event.event_id}.json").read_bytes()
    assert save_observation(tmp_path, event) is False
    assert (tmp_path / f"{event.event_id}.json").read_bytes() == first


def test_wrong_source_and_unknown_event_are_ignored():
    assert parse_otlp_logs(_payload(service="some-other-application"))[0] == []
    assert parse_otlp_logs(_payload(event="codex.unlisted_event"))[0] == []


def test_body_event_fallback_and_conservative_unknowns():
    parsed, ignored = parse_otlp_logs(_payload(event_in_body=True, extra={"success": "maybe"}))
    assert ignored == 0
    assert parsed[0].attributes["success"] is None


def test_deterministic_diagnosis_on_evidence(tmp_path):
    event = parse_otlp_logs(_payload())[0][0]
    save_observation(tmp_path, event)
    report = diagnostic_report(tmp_path)
    assert report["completeness"] == "PARTIAL"
    assert report["events"] == 1
    rules = {x["rule"] for x in report["findings"]}
    assert rules == {"SLOW_TOOL_REPORTED", "TOOL_FAILURE_OBSERVED"}
    assert report["sessions_observed"] == 1


def test_corrupted_saved_witness_is_visible_not_repaired(tmp_path):
    (tmp_path / ("0" * 32 + ".json")).write_text("garbled")
    report = diagnostic_report(tmp_path)
    assert report["unreadable_records"] == 1
    assert "WITNESS_INTEGRITY_UNREADABLE" in {x["rule"] for x in report["findings"]}
    assert len(load_observations(tmp_path)[0]) == 0


def test_limit_and_duplicate_metadata(tmp_path):
    from observability.codex_activity_monitor import MAX_REQUEST_BYTES
    import pytest
    with pytest.raises(ValueError):
        parse_otlp_logs(b"x" * (MAX_REQUEST_BYTES + 1))
    observation = Observation("0" * 32, "codex.api_request", "unknown", None, {})
    assert save_observation(tmp_path, observation)
    with pytest.raises(ValueError):
        save_observation(tmp_path, Observation("0" * 32, "codex.tool_result", "unknown", None, {}))


def test_no_data_not_misreported_as_inactivity(tmp_path):
    report = diagnostic_report(tmp_path)
    assert report["status"] == "NO_DATA"
    assert report["completeness"] == "PARTIAL"


def test_otlp_http_round_trip(tmp_path):
    import subprocess, socket, urllib.request, time
    import os
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    script = ROOT / "scripts" / "codex_activity.py"
    proc = subprocess.Popen([sys.executable, str(script), "serve",
                             "--port", str(port), "--data-dir", str(tmp_path)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    try:
        health_url = f"http://127.0.0.1:{port}/health"
        for _ in range(50):
            try:
                with urllib.request.urlopen(health_url, timeout=0.25) as reply:
                    assert json.load(reply)["status"] == "READY"
                break
            except OSError:
                time.sleep(0.025)
        else:
            raise AssertionError("No local receiver")
        request = urllib.request.Request(
            f"http://127.0.0.1:{port}/v1/logs", data=_payload(),
            headers={"Content-Type":"application/x-protobuf"}, method="POST")
        with urllib.request.urlopen(request, timeout=2) as reply:
            assert reply.status == 200
            assert reply.headers["Content-Type"] == "application/x-protobuf"
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/report", timeout=2) as reply:
            report = json.load(reply)
        assert report["events"] == 1
        assert report["completeness"] == "PARTIAL"
    finally:
        proc.terminate()
        proc.wait(timeout=5)
