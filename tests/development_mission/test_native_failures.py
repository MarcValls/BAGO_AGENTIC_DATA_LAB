"""Real exporter effects and durable, fail-closed export fencing."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import importlib
import json
import sqlite3
import threading
import time

import pytest
from opentelemetry.sdk.trace.export import SpanExportResult

from observability import otel_bridge as bridge
from observability.local_trace import LocalTrace, TraceEvent, TraceKind
from observability.native_timing import NativeTimingRecorder


def evidence():
    return LocalTrace(
        trace_id="durable-trace", run_id="durable-run",
        events=(
            TraceEvent(
                event_id="root", trace_id="durable-trace", sequence=0,
                name="execution", kind=TraceKind.EXECUTION, status="SUCCEEDED",
                start_time_unix_nano=1_700_000_000_000_000_000,
                end_time_unix_nano=1_700_000_000_120_000_000,
            ),
            TraceEvent(
                event_id="child", trace_id="durable-trace", sequence=1,
                name="tool", kind=TraceKind.TOOL, status="SUCCEEDED",
                parent_event_id="root",
                start_time_unix_nano=1_700_000_000_010_000_000,
                end_time_unix_nano=1_700_000_000_020_000_000,
            ),
        ),
    )


def dispatch(trace, exporter, directory, **kwargs):
    return bridge.export_local_trace(trace, exporter=exporter, ledger_dir=directory, **kwargs)


def assert_uncertain(receipt):
    assert receipt.status == "INCONCLUSIVE"
    assert receipt.exported is False
    assert receipt.jaeger_trace_id is None
    assert "TOP_SECRET" not in json.dumps(receipt.to_dict())


def test_success_recreated_state_has_verifiable_receipt_without_redispatch(tmp_path):
    trace = evidence()
    first_exporter = bridge.RecordingSpanExporter()
    first = dispatch(trace, first_exporter, tmp_path)
    assert first.exported and first.status == "PASS"
    assert len(first_exporter.spans) == 2
    with sqlite3.connect(tmp_path / "otel-export-ledger.sqlite3") as connection:
        raw, checksum = connection.execute("SELECT record, checksum FROM claims").fetchone()
    record = json.loads(raw)
    assert checksum == bridge._ledger_hash(record)
    assert record["state"] == "SUCCESS"
    assert record["receipt"] == first.to_dict()
    # Reload removes any possibility that a module-local cache supplies fencing.
    importlib.reload(bridge)
    later_exporter = bridge.RecordingSpanExporter()
    later = dispatch(trace, later_exporter, tmp_path)
    assert later.to_dict() == first.to_dict()
    assert later_exporter.spans == []


@pytest.mark.parametrize("change", ["evidence", "endpoint", "service"])
def test_identity_is_bound_to_evidence_and_destination(tmp_path, change):
    trace = evidence()
    assert dispatch(trace, bridge.RecordingSpanExporter(), tmp_path).exported
    kwargs = {}
    if change == "evidence":
        trace = replace(trace, run_id="different-run")
    elif change == "endpoint":
        kwargs["endpoint"] = "http://different.invalid:4318"
    else:
        kwargs["service_name"] = "different-service"
    exporter = bridge.RecordingSpanExporter()
    assert_uncertain(dispatch(trace, exporter, tmp_path, **kwargs))
    assert exporter.spans == []


def test_concurrent_calls_dispatch_only_one_attempt(tmp_path):
    entered, release = threading.Event(), threading.Event()

    class BlockingExporter(bridge.RecordingSpanExporter):
        def export(self, spans):
            entered.set()
            assert release.wait(5)
            return super().export(spans)

    owner = BlockingExporter()
    observer = bridge.RecordingSpanExporter()
    with ThreadPoolExecutor(max_workers=2) as pool:
        pending = pool.submit(dispatch, evidence(), owner, tmp_path)
        assert entered.wait(5)
        try:
            second = pool.submit(dispatch, evidence(), observer, tmp_path).result(timeout=5)
            assert_uncertain(second)
            assert observer.spans == []
        finally:
            release.set()
        assert pending.result(timeout=5).exported
    assert len(owner.spans) == 2


@pytest.mark.parametrize("failure", ["partial", "lost_ack", "flush"])
def test_uncertain_attempt_never_redispatches(tmp_path, failure):
    class UncertainExporter(bridge.RecordingSpanExporter):
        def export(self, spans):
            result = super().export(spans)
            if failure == "lost_ack":
                raise RuntimeError("TOP_SECRET acknowledgement payload")
            if failure == "partial" and len(self.spans) == 1:
                return SpanExportResult.FAILURE
            return result

        def force_flush(self, timeout_millis=30000):
            return failure != "flush"

    exporter = UncertainExporter()
    assert_uncertain(dispatch(evidence(), exporter, tmp_path))
    assert exporter.spans
    # The intent is committed even when no acknowledgement can be trusted.
    with sqlite3.connect(tmp_path / "otel-export-ledger.sqlite3") as connection:
        record = json.loads(connection.execute("SELECT record FROM claims").fetchone()[0])
    assert record["state"] == "STARTED"
    assert record["receipt"] is None
    fresh = bridge.RecordingSpanExporter()
    assert_uncertain(dispatch(evidence(), fresh, tmp_path))
    assert fresh.spans == []


@pytest.mark.parametrize("damage", ["checksum", "receipt", "format", "corrupt"])
def test_tamper_or_corruption_never_dispatches(tmp_path, damage):
    assert dispatch(evidence(), bridge.RecordingSpanExporter(), tmp_path).exported
    path = tmp_path / "otel-export-ledger.sqlite3"
    if damage == "corrupt":
        path.write_bytes(b"invalid sqlite TOP_SECRET")
    else:
        with sqlite3.connect(path) as connection:
            if damage == "format":
                connection.execute("DROP TABLE ledger_format")
            elif damage == "checksum":
                connection.execute("UPDATE claims SET checksum = 'invalid'")
            else:
                record = json.loads(connection.execute("SELECT record FROM claims").fetchone()[0])
                record["receipt"]["exported"] = False
                connection.execute("UPDATE claims SET record = ?", (json.dumps(record),))
    exporter = bridge.RecordingSpanExporter()
    assert_uncertain(dispatch(evidence(), exporter, tmp_path))
    assert exporter.spans == []


def test_prevalidation_precedes_ledger_and_effects(tmp_path):
    trace = evidence()
    invalid = replace(trace, events=(replace(trace.events[0], parent_event_id="missing"),))
    exporter = bridge.RecordingSpanExporter()
    with pytest.raises(ValueError):
        dispatch(invalid, exporter, tmp_path / "not-created")
    assert not (tmp_path / "not-created").exists()
    assert exporter.spans == []


def test_persistence_failure_before_claim_has_no_export(tmp_path, monkeypatch):
    def unavailable(path):
        raise sqlite3.OperationalError("TOP_SECRET storage failure")

    with monkeypatch.context() as patch:
        patch.setattr(bridge, "_ledger_connect", unavailable)
        exporter = bridge.RecordingSpanExporter()
        assert_uncertain(dispatch(evidence(), exporter, tmp_path))
        assert exporter.spans == []
    # The exclusive initialization fence remains, so failure cannot authorize a retry.
    retry = bridge.RecordingSpanExporter()
    assert_uncertain(dispatch(evidence(), retry, tmp_path))
    assert retry.spans == []


def test_success_commit_failure_is_uncertain_and_fenced(tmp_path, monkeypatch):
    def cannot_commit(*args):
        raise sqlite3.OperationalError("TOP_SECRET commit failed")

    with monkeypatch.context() as patch:
        patch.setattr(bridge, "_ledger_finish", cannot_commit)
        exporter = bridge.RecordingSpanExporter()
        assert_uncertain(dispatch(evidence(), exporter, tmp_path))
        assert len(exporter.spans) == 2
    retry = bridge.RecordingSpanExporter()
    assert_uncertain(dispatch(evidence(), retry, tmp_path))
    assert retry.spans == []


def test_native_recorder_real_wait_reaches_exporter_unchanged(tmp_path):
    recorder = NativeTimingRecorder(run_id="native-run")
    with recorder.span("execution", kind=TraceKind.EXECUTION) as native_span:
        time.sleep(0.120)
        native_span.finish()
    trace = recorder.to_local_trace()
    assert len(trace.events) == 1
    event = trace.events[0]
    local_duration = event.end_time_unix_nano - event.start_time_unix_nano
    assert 100_000_000 <= local_duration <= 500_000_000
    exporter = bridge.RecordingSpanExporter()
    receipt = dispatch(trace, exporter, tmp_path)
    assert receipt.exported
    assert len(exporter.spans) == 1
    span = exporter.spans[0]
    assert span.start_time == event.start_time_unix_nano
    assert span.end_time == event.end_time_unix_nano
    assert 100_000_000 <= span.end_time - span.start_time <= 500_000_000
    assert span.attributes["duration_measured"] is True
    assert span.attributes["timing_source"] == "native"


@pytest.mark.parametrize(("decision", "status"), [
    ("ALLOW", "SUCCEEDED"), ("DENY", "DENIED"), ("FAIL", "FAILED"),
])
def test_document_handler_keeps_native_tool_interval_and_receipt(decision, status):
    from src.api import server
    from src.observability.native_timing import NativeTimingRecorder as Recorder

    recorder = Recorder(run_id="document-handler-kind")
    observation = {}
    receipt = {"kind": "document_extract", "decision": decision}
    result = {"ok": decision == "ALLOW"}
    calls = []

    def handler():
        calls.append(True)
        return result, receipt

    with recorder.span("agent.chat") as root:
        returned = server._native_receipt_call(
            recorder, observation, "document_extract", handler)
        root.finish()
    trace = recorder.to_local_trace()
    event = next(event for event in trace.events if event.name == "document_extract")
    parent = next(event for event in trace.events if event.name == "agent.chat")
    assert calls == [True]
    assert returned[0] is result and returned[1] is receipt
    assert event.kind == server.TraceKind.TOOL
    assert event.status == status
    assert event.parent_event_id == parent.event_id
    assert event.attributes["interval_complete"] is True
    assert event.attributes["timing_source"] == "native"
    assert event.end_time_unix_nano >= event.start_time_unix_nano
    bound, event_id = observation["_native_receipt_invocations"][0]
    assert bound is receipt and event_id == event.event_id


@pytest.mark.parametrize("measured", [False, True])
@pytest.mark.parametrize(("snapshot_id", "manifest", "valid_id", "valid_hash"), [
    ("0123456789abcdef0123456789abcdef", "a" * 64, True, True),
    ("https://private.invalid/path", "a" * 64, False, True),
    ("../private", "a" * 64, False, True),
    ("snapshot\nsecret", "a" * 64, False, True),
    ("x" * 129, "a" * 64, False, True),
    ("a" * 31, "a" * 64, False, True),
    ("a" * 33, "a" * 64, False, True),
    ("A" * 32, "a" * 64, False, True),
    ("g" * 32, "a" * 64, False, True),
    ("a" * 31 + "_", "a" * 64, False, True),
    ("a" * 32 + "\n", "a" * 64, False, True),
    (None, "a" * 64, False, True),
    (32, "a" * 64, False, True),
    ({"private": True}, ["private"], False, False),
    ("0123456789abcdef0123456789abcdef", "A" * 64, True, False),
    ("0123456789abcdef0123456789abcdef", "b" * 63, True, False),
])
def test_web_snapshot_evidence_is_safe_and_preserves_native_identity(
        measured, snapshot_id, manifest, valid_id, valid_hash):
    from src.api import server
    from src.observability.native_timing import NativeTimingRecorder as Recorder

    recorder = Recorder(run_id="snapshot-correlation")
    receipt = {"kind": "public_web_read", "decision": "ALLOW",
               "snapshot_id": snapshot_id, "snapshot_manifest_sha256": manifest,
               "url": "https://TOP_SECRET.invalid", "path": "TOP_SECRET",
               "content": "TOP_SECRET", "arguments": {"secret": "TOP_SECRET"},
               "authorization_id": "TOP_SECRET", "provider_id": "TOP_SECRET",
               "error": "TOP_SECRET"}
    observation = {"read_events": [receipt, receipt]}
    with recorder.span("agent.chat") as root:
        if measured:
            server._native_receipt_call(
                recorder, observation, "web.read", lambda: ({"ok": True}, receipt))
        root.finish()
    original = recorder.to_local_trace()
    before = [dict(event.attributes) for event in original.events]
    enriched = server._native_chat_compatibility_evidence(
        original, {"root_attributes": {}, "observation": observation})
    events = [event for event in enriched.events if event.name == "web.read"]
    assert len(events) == 1
    event = events[0]
    assert ("snapshot_id" in event.attributes) is valid_id
    assert ("snapshot_manifest_sha256" in event.attributes) is valid_hash
    assert event.evidence_refs == (("web-snapshot://" + snapshot_id,) if valid_id else ())
    assert [dict(item.attributes) for item in original.events] == before
    assert all(item.evidence_refs == () for item in original.events)
    if measured:
        native = next(item for item in original.events if item.name == "web.read")
        assert event.event_id == native.event_id
        assert event.parent_event_id == native.parent_event_id
        assert event.attributes["interval_complete"] is True
    if valid_id:
        assert event.attributes["snapshot_id"] == snapshot_id
    if valid_hash:
        assert event.attributes["snapshot_manifest_sha256"] == manifest
    assert not ({"url", "path", "content", "arguments", "authorization_id",
                 "provider_id", "error"} & set(event.attributes))
    assert "TOP_SECRET" not in json.dumps(dict(event.attributes))
    assert len({item.event_id for item in enriched.events}) == len(enriched.events)
    assert [dict(item.attributes) for item in original.events] == before
    if measured:
        native = next(item for item in original.events if item.name == "web.read")
        assert event.event_id == native.event_id
        assert event.parent_event_id == native.parent_event_id
        assert event.start_time_unix_nano == native.start_time_unix_nano
        assert event.end_time_unix_nano == native.end_time_unix_nano
        assert event.attributes["interval_complete"] is True
        assert event.attributes["native_outcome"] == "SUCCEEDED"
        assert event.attributes["timing_source"] == "native"
    else:
        assert event.attributes["timing_mode"] == "projection"


@pytest.mark.parametrize("source_mode", ["absent", "empty", "mixed"])
def test_native_source_compatibility_is_local_and_preserves_original(source_mode):
    from copy import deepcopy
    from src.api import server
    from src.observability.native_timing import NativeTimingRecorder as Recorder
    from src.observability.otel_bridge import _span_attributes

    recorder = Recorder(run_id="local-source-compatibility")
    with recorder.span("agent.chat") as interval:
        interval.finish()
    original = recorder.to_local_trace()
    root = next(event for event in original.events if event.name == "agent.chat")
    before = deepcopy(dict(root.attributes))
    observation = {"read_events": [
        {"kind": "directory_code_scan", "decision": "ALLOW"},
        {"kind": "directory_code_scan", "decision": "DENY"},
        {"kind": "directory_code_scan", "decision": "FAIL"},
        {"kind": "public_web_read", "decision": "DENY"},
        {"kind": "public_web_read", "decision": "FAIL"},
    ]}
    if source_mode != "absent":
        observation["sources"] = []
    if source_mode == "mixed":
        observation["sources"] = [
            {"source_type": "public_web", "path": "https://URL_SENTINEL.invalid/?token=PRIVATE"},
            {"source_type": "workspace", "path": "PATH_SENTINEL", "start_line": 2, "end_line": 7},
            {"path": "SECOND_PATH_SENTINEL", "start_line": 9, "end_line": 11},
        ]
    observation_before = deepcopy(observation)
    enriched = server._native_chat_compatibility_evidence(
        original, {"root_attributes": {}, "observation": observation})
    enriched_root = next(event for event in enriched.events if event.event_id == root.event_id)
    assert dict(root.attributes) == before
    assert observation == observation_before
    assert enriched_root.parent_event_id == root.parent_event_id
    assert enriched_root.start_time_unix_nano == root.start_time_unix_nano
    assert enriched_root.end_time_unix_nano == root.end_time_unix_nano
    assert enriched_root.evidence_refs == root.evidence_refs
    if source_mode == "absent":
        assert enriched_root == root
        return
    expected_workspace = ["PATH_SENTINEL:2-7", "SECOND_PATH_SENTINEL:9-11"] if source_mode == "mixed" else []
    expected_web = ["https://URL_SENTINEL.invalid/?token=PRIVATE"] if source_mode == "mixed" else []
    assert enriched_root.attributes["workspace_read_sources"] == expected_workspace
    assert enriched_root.attributes["web_read_sources"] == expected_web
    assert enriched_root.attributes["workspace_read_count"] == len(expected_workspace)
    assert enriched_root.attributes["web_read_count"] == len(expected_web)
    assert enriched_root.attributes["workspace_scan_count"] == 1
    local_before_export = deepcopy(dict(enriched_root.attributes))
    exported = _span_attributes(enriched, enriched_root)
    assert "bago.event.workspace_read_sources" not in exported
    assert "bago.event.web_read_sources" not in exported
    assert exported["bago.event.workspace_read_count"] == len(expected_workspace)
    assert exported["bago.event.web_read_count"] == len(expected_web)
    assert exported["bago.event.workspace_scan_count"] == 1
    assert "URL_SENTINEL" not in repr(exported)
    assert "PATH_SENTINEL" not in repr(exported)
    assert "PRIVATE" not in repr(exported)
    assert dict(enriched_root.attributes) == local_before_export
    assert dict(root.attributes) == before


def test_equal_web_receipt_does_not_borrow_native_interval():
    from src.api import server
    from src.observability.native_timing import NativeTimingRecorder as Recorder

    recorder = Recorder(run_id="snapshot-exact-identity")
    measured = {"kind": "public_web_read", "decision": "ALLOW",
                "snapshot_id": "0123456789abcdef0123456789abcdef", "snapshot_manifest_sha256": "c" * 64}
    other = dict(measured)
    observation = {"read_events": [other]}
    with recorder.span("agent.chat") as root:
        server._native_receipt_call(
            recorder, observation, "web.read", lambda: ({"ok": True}, measured))
        root.finish()
    original = recorder.to_local_trace()
    enriched = server._native_chat_compatibility_evidence(
        original, {"root_attributes": {}, "observation": observation})
    events = [event for event in enriched.events if event.name == "web.read"]
    assert len(events) == 2
    native = next(event for event in original.events if event.name == "web.read")
    assert next(event for event in events if event.event_id == native.event_id) == native
    projected = next(event for event in events if event.event_id != native.event_id)
    assert projected.attributes["timing_mode"] == "projection"
    assert projected.attributes["snapshot_id"] == "0123456789abcdef0123456789abcdef"
    assert projected.evidence_refs == ("web-snapshot://0123456789abcdef0123456789abcdef",)
    assert native.evidence_refs == ()
    assert next(event for event in original.events if event.event_id == native.event_id) == native


@pytest.mark.parametrize("conflict", [False, True])
def test_failed_chat_final_reference_contract_uses_real_sqlite_writeback(
        tmp_path, monkeypatch, conflict):
    from types import SimpleNamespace
    from fastapi import HTTPException, Response
    from src.api import server

    database = tmp_path / "final-reference.sqlite3"

    def connect():
        return sqlite3.connect(database)

    with connect() as connection:
        connection.execute("CREATE TABLE conversations (id TEXT PRIMARY KEY, revision INTEGER, status TEXT, owner_kind TEXT, owner_id TEXT)")
        connection.execute("CREATE TABLE messages (id TEXT PRIMARY KEY, conversation_id TEXT, sequence INTEGER, role TEXT, status TEXT, content TEXT, references_json TEXT)")
        connection.execute("INSERT INTO conversations VALUES ('conversation-final', 1, 'active', 'agent', 'agent-final')")
    monkeypatch.setattr(server, "CONVERSATIONS", SimpleNamespace(_connect=connect))
    captured = {}

    async def execute(agent_id, request, response, *, recorder, native_reference, native_state, **kwargs):
        reference = dict(native_reference)
        references_json = json.dumps({"trace": reference}, ensure_ascii=False)
        target = {"reference": reference, "references_json": references_json,
                  "owner_id": agent_id, "conversation_id": request.conversation_id,
                  "message_id": "failed-final", "sequence": 1, "revision": 1,
                  "conversation_status": "active"}
        with connect() as connection:
            connection.execute("INSERT INTO messages VALUES (?, ?, 1, 'assistant', 'failed', '', ?)",
                               (target["message_id"], request.conversation_id, references_json))
            if conflict:
                connection.execute("UPDATE conversations SET revision = 2")
        native_state["failed_message"] = target
        captured["target"] = target
        raise HTTPException(status_code=502, detail={
            "reason_code": "HANDLER_FAILED",
            "evidence_persistence": {"conversation": "persisted", "trace": "persisted"}})

    def finalize(trace, *, agent_id, conversation_id):
        metadata = dict(captured["target"]["reference"], trace_state="local",
                        local_state="persisted", export_state="not_attempted",
                        sidecar_state="not_attempted")
        captured["metadata"] = metadata
        return metadata

    monkeypatch.setattr(server, "_execute_native_agent_chat_turn", execute)
    monkeypatch.setattr(server, "_finalize_native_agent_chat_trace", finalize)
    request = SimpleNamespace(conversation_id="conversation-final")
    with pytest.raises(HTTPException) as raised:
        asyncio.run(server._execute_agent_chat_turn("agent-final", request, Response()))
    detail = raised.value.detail
    assert detail["reason_code"] == "HANDLER_FAILED"
    assert detail["trace"] == captured["metadata"]
    with connect() as connection:
        references = json.loads(connection.execute(
            "SELECT references_json FROM messages WHERE id = 'failed-final'").fetchone()[0])
    if conflict:
        assert detail["evidence_persistence"] == {
            "conversation": "persisted", "trace": "persisted", "trace_reference": "failed"}
        assert references["trace"]["trace_state"] == "pending_finalization"
    else:
        assert detail["evidence_persistence"] == {"conversation": "persisted", "trace": "persisted"}
        assert references["trace"] == detail["trace"]
        assert references["trace"]["trace_state"] != "pending_finalization"
        with pytest.raises(server.ConversationConflict):
            server._native_failed_chat_writeback(captured["target"], captured["metadata"])
        with connect() as connection:
            repeated = json.loads(connection.execute(
                "SELECT references_json FROM messages WHERE id = 'failed-final'").fetchone()[0])
        assert repeated == references


def test_native_private_source_lists_are_local_only_in_real_export(tmp_path):
    from dataclasses import asdict
    from src.api import server
    from src.observability import otel_bridge as bridge
    from src.observability.native_timing import NativeTimingRecorder

    recorder = NativeTimingRecorder(run_id="private-source-export")
    with recorder.span("agent.chat") as root:
        with recorder.span("web.read") as child:
            child.finish()
        root.finish()
    trace = server._native_chat_compatibility_evidence(
        recorder.to_local_trace(), {
            "root_attributes": {
                "web_read_sources": ["https://PRIVATE_WEB_SENTINEL.invalid/?token=PRIVATE_TOKEN_SENTINEL"],
                "workspace_read_sources": ["C:\\PRIVATE_PATH_SENTINEL\\source.py:2-4"],
                "web_read_count": 1, "workspace_read_count": 1,
                "workspace_scan_count": 0,
            },
            "observation": {},
        })
    before = asdict(trace)
    exporter = bridge.RecordingSpanExporter()
    receipt = bridge.export_local_trace(
        trace, exporter=exporter, ledger_dir=tmp_path / "export-ledger")
    assert receipt.exported
    assert len(exporter.spans) == len(trace.events) == 2
    spans = {span.attributes["bago.event_id"]: span for span in exporter.spans}
    local_root = next(event for event in trace.events if event.name == "agent.chat")
    exported_root = spans[local_root.event_id]
    assert exported_root.attributes["bago.event.web_read_count"] == 1
    assert exported_root.attributes["bago.event.workspace_read_count"] == 1
    assert exported_root.attributes["bago.event.workspace_scan_count"] == 0
    for event in trace.events:
        span = spans[event.event_id]
        assert span.start_time == event.start_time_unix_nano
        assert span.end_time == event.end_time_unix_nano
        assert span.start_time is not None
        assert span.end_time >= span.start_time
        assert span.attributes["timing_source"] == "native"
        assert span.attributes["duration_measured"] is True
        assert "bago.event.web_read_sources" not in span.attributes
        assert "bago.event.workspace_read_sources" not in span.attributes
        exported = repr(dict(span.attributes))
        for sentinel in ("PRIVATE_WEB_SENTINEL", "PRIVATE_TOKEN_SENTINEL", "PRIVATE_PATH_SENTINEL"):
            assert sentinel not in exported
        if event.parent_event_id is not None:
            assert span.parent is not None
            assert span.parent.span_id == spans[event.parent_event_id].context.span_id
        else:
            assert span.parent is None
    assert any(event.parent_event_id == local_root.event_id for event in trace.events)
    assert asdict(trace) == before
    assert local_root.attributes["web_read_sources"][0].startswith("https://PRIVATE_WEB_SENTINEL")
    assert "PRIVATE_PATH_SENTINEL" in local_root.attributes["workspace_read_sources"][0]


def test_real_agent_provider_failure_finalizes_and_preserves_foreign_conversation(monkeypatch, tmp_path):
    import asyncio
    import json
    import sqlite3
    from types import SimpleNamespace
    from fastapi import HTTPException, Response
    from src.api import server
    from src.conversations import ConversationStore

    database = tmp_path / "provider-failure.sqlite3"
    store = ConversationStore(database)
    conversation = store.create("agent", "provider-failure-agent")
    foreign = store.create("agent", "foreign-agent")
    trace_dir = tmp_path / "traces"
    monkeypatch.setattr(server, "CONVERSATIONS", store)
    monkeypatch.setattr(server, "current_workspace_root", lambda: tmp_path)
    monkeypatch.setattr(server, "AGENT_CHAT_TRACE_DIR", trace_dir)
    monkeypatch.setenv("BAGO_OTEL_EXPORTER_OTLP_ENDPOINT", "")
    monkeypatch.setattr(server, "_record_chat_cognition_trace", lambda **kwargs: {"state": "fixture"})
    record = SimpleNamespace(id="provider-failure-agent", config=SimpleNamespace(
        provider_id="ollama-cloud", model_id="fixture-model",
        system_prompt="Use only approved evidence."))
    monkeypatch.setattr(server, "_load_model_enabled_agent", lambda agent_id: record)
    calls = []

    def fail_provider(*args, **kwargs):
        calls.append(True)
        raise server.ollama.ProviderError("PROVIDER_UNAVAILABLE", "Synthetic provider failure")

    monkeypatch.setattr(server.provider_runtime, "chat", fail_provider)

    def stored_rows(table, conversation_id):
        with sqlite3.connect(database) as connection:
            connection.row_factory = sqlite3.Row
            column = "id" if table == "conversations" else "conversation_id"
            return [dict(row) for row in connection.execute(
                f"SELECT * FROM {table} WHERE {column} = ? ORDER BY rowid", (conversation_id,))]

    foreign_before = (stored_rows("conversations", foreign["id"]),
                      stored_rows("messages", foreign["id"]))
    request = server.AgentChatRequest(
        message="Respond without using tools.", conversation_id=conversation["id"], revision=0)
    with pytest.raises(HTTPException) as raised:
        asyncio.run(server.chat_with_agent(record.id, request, Response()))
    assert calls == [True]
    assert raised.value.status_code == 503
    detail = raised.value.detail
    assert detail["evidence_persistence"] == {"conversation": "persisted", "trace": "persisted"}
    reference = detail["trace"]
    assert reference["trace_state"] == "local_only"
    assert reference["local_state"] == "persisted"
    messages = stored_rows("messages", conversation["id"])
    assistant_messages = [message for message in messages if message["role"] == "assistant"]
    assert len(assistant_messages) == 1
    assert assistant_messages[0]["status"] == "failed"
    assert json.loads(assistant_messages[0]["references_json"])["trace"] == reference
    saved_trace = json.loads(
        (trace_dir / (reference["trace_id"] + ".json")).read_text(encoding="utf-8"))
    assert saved_trace["trace_id"] == reference["trace_id"]
    saved_metadata = json.loads(
        (trace_dir / ("metadata-" + reference["trace_id"] + ".v1.json")).read_text(
            encoding="utf-8"))
    assert saved_metadata == reference
    roots = [event for event in saved_trace["events"] if event["name"] == "agent.chat"]
    assert len(roots) == 1
    assert roots[0]["attributes"]["outcome"] == "provider_failed"
    assert roots[0]["status"] == "FAILED"
    assert roots[0]["start_time_unix_nano"] is not None
    assert roots[0]["end_time_unix_nano"] >= roots[0]["start_time_unix_nano"]
    assert (stored_rows("conversations", foreign["id"]),
            stored_rows("messages", foreign["id"])) == foreign_before
