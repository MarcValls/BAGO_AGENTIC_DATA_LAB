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


_WORK_HISTORY_FIELDS = {
    "key", "kind", "id", "status", "agent_id", "agent_name",
    "parent_conversation_id", "conversation_id", "message_id", "trace_id",
    "receipt_id", "receipt_sha256", "created_at", "started_at", "completed_at",
    "activity_at", "duration_ms", "cost_usd", "tools_executed", "target_written",
    "tool_receipt_count", "related_key",
}
_WORK_HISTORY_RESPONSE_FIELDS = {
    "schema", "items", "total", "limit", "offset", "has_more", "next_offset", "sources",
}
_WORK_HISTORY_PRIVATE = "PRIVATE_WORK_HISTORY_BODY_SENTINEL"


def _work_history_no_effect(*args, **kwargs):
    raise AssertionError("work history invoked an execution or mutation API")


def _work_history_bytes(root):
    return {str(path.relative_to(root)): path.read_bytes()
            for path in root.rglob("*") if path.is_file()}


def _work_history_fixture(tmp_path):
    from src.agent_tasks import TaskStore
    from src.conversations import ConversationStore
    from src.evaluation.agent_lab import EvaluationStore
    from src.services.agent_delegation import AgentDelegations

    task_path = tmp_path / "tasks.sqlite3"
    conversation_path = tmp_path / "conversations.sqlite3"
    evaluation_path = tmp_path / "evaluations.sqlite3"
    private = _WORK_HISTORY_PRIVATE
    with sqlite3.connect(task_path) as connection:
        connection.execute("CREATE TABLE task_runs (run_id TEXT, agent_id TEXT, snapshot TEXT, created_at TEXT, completed_at TEXT, status TEXT, answer TEXT, error TEXT)")
        connection.execute("INSERT INTO task_runs VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                           ("task-failed", "deleted-agent", private, "2026-01-01T08:00:00+00:00",
                            "2026-01-01T09:00:00+00:00", "FAILED", private, private))
    with sqlite3.connect(conversation_path) as connection:
        connection.executescript("""
            CREATE TABLE conversations (id TEXT, project_id TEXT, owner_kind TEXT,
                owner_id TEXT, title TEXT, status TEXT, created_at TEXT, updated_at TEXT, revision INTEGER);
            CREATE TABLE messages (id TEXT, conversation_id TEXT, sequence INTEGER,
                role TEXT, content TEXT, created_at TEXT, status TEXT, references_json TEXT);
        """)
        for identity, owner, status in (
            ("child-conversation", "agent", "archived"),
            ("empty-conversation", "agent", "active"),
            ("deleted-conversation", "agent", "deleted"),
            ("general-conversation", "app", "active"),
        ):
            connection.execute("INSERT INTO conversations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                               (identity, "bago-agentic-data-lab:default", owner, "fixture-agent",
                                private, status, "2026-01-01T00:00:00+00:00",
                                "2026-01-01T00:00:00+00:00", 0))
        references = json.dumps({"trace": {"trace_id": "trace-fixture"},
                                 "delegation_parent": {"proposal_id": "delegation_" + "a" * 32},
                                 "private": private})
        for identity, conversation, role, refs in (
            ("turn-matched", "child-conversation", "assistant", references),
            ("turn-no-trace", "child-conversation", "assistant", "{}"),
            ("turn-user", "child-conversation", "user", references),
            ("turn-deleted", "deleted-conversation", "assistant", references),
            ("turn-general", "general-conversation", "assistant", references),
        ):
            connection.execute("INSERT INTO messages VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                               (identity, conversation, 1, role, private,
                                "2026-01-01T11:00:00+00:00", "completed", refs))
    with sqlite3.connect(evaluation_path) as connection:
        connection.executescript("""
            CREATE TABLE runs (id TEXT, suite_id TEXT, suite_version TEXT, suite_name TEXT,
                agent_id TEXT, agent_name TEXT, agent_config_fingerprint TEXT, provider_id TEXT,
                model_id TEXT, status TEXT, total_cases INTEGER, passed_cases INTEGER,
                failed_cases INTEGER, error_cases INTEGER, duration_ms REAL, started_at TEXT,
                completed_at TEXT, payload_json TEXT);
            CREATE TABLE active_suite_runs (suite_id TEXT, run_id TEXT, started_at TEXT);
        """)
        connection.execute("INSERT INTO runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                           ("evaluation-completed", "suite-fixture", "1", private,
                            "fixture-agent", "Historical fixture agent", private, private, private,
                            "COMPLETED", 1, 1, 0, 0, 0, "2026-01-01T10:00:00+00:00",
                            "2026-01-01T10:30:00+00:00", private))
        connection.executemany("INSERT INTO active_suite_runs VALUES (?, ?, ?)", [
            ("suite-fixture", "evaluation-completed", "2026-01-01T10:00:00+00:00"),
            ("suite-pending", "evaluation-running", "2026-01-01T12:00:00+00:00"),
        ])
    jobs_directory = tmp_path / "jobs"
    jobs_directory.mkdir()
    (jobs_directory / "legacy-failed.json").write_text(json.dumps({
        "job_id": "legacy-failed", "agent_id": "fixture-agent", "status": "FAILED",
        "created_at": "2026-01-01T07:00:00", "completed_at": "2026-01-01T08:00:00",
        "duration_ms": 0, "cost_usd": 0, "stdout": private, "stderr": private,
        "metrics": {"private": private},
    }), encoding="utf-8")
    conversations = ConversationStore(conversation_path)
    delegations = AgentDelegations(
        directory=tmp_path / "delegations", workspace=tmp_path,
        conversations=conversations, load_agent=_work_history_no_effect,
        resolve_model=_work_history_no_effect, execute_turn=_work_history_no_effect,
        authorize_tools=_work_history_no_effect, record_trace=_work_history_no_effect,
        trace_root=tmp_path / "traces",
    )
    (tmp_path / "delegations" / "records").mkdir(parents=True, exist_ok=True)
    fixture = {
        "jobs_directory": jobs_directory, "task_store": TaskStore(task_path),
        "conversations": conversations,
        "evaluations": EvaluationStore(tmp_path, database_path=evaluation_path),
        "delegations": delegations,
    }
    _work_history_save_delegation(fixture, "a", "PASSED", "child-conversation", "trace-fixture")
    _work_history_save_delegation(fixture, "b", "FAILED", "failed-child", "failed-trace")
    return fixture


def _work_history_save_delegation(fixture, digit, state, conversation, trace):
    from src.services.agent_delegation import digest

    binding = {
        "proposal_id": "delegation_" + digit * 32,
        "parent_conversation_id": "parent-conversation", "agent_id": "fixture-agent",
        "agent_name": "Historical fixture agent", "expires_at": 1900000000,
        "workspace": str(fixture["jobs_directory"].parent),
        "task": _WORK_HISTORY_PRIVATE, "human_scope": _WORK_HISTORY_PRIVATE,
    }
    record = {
        "binding": binding, "proposal_sha256": digest(binding), "state": state,
        "started_at": None if state == "PROPOSED" else 1767261600,
        "finished_at": None if state == "PROPOSED" else 1767265200,
        "child_conversation_id": conversation, "child_trace_id": trace,
        "receipt_id": None if state == "PROPOSED" else "receipt-" + digit,
        "receipt_sha256": None if state == "PROPOSED" else digit * 64,
        "tools_executed": None if state == "PROPOSED" else False,
        "target_written": None if state == "PROPOSED" else False,
    }
    fixture["delegations"]._save(record, new=True)
    return binding["proposal_id"]


def _work_history_forbid_mutation(monkeypatch, fixture):
    store = fixture["delegations"]
    for name in ("get", "public", "_parent", "execute", "save", "_save"):
        if hasattr(store, name):
            monkeypatch.setattr(store, name, _work_history_no_effect)
    for name in ("_connect", "_db"):
        for key in ("task_store", "conversations", "evaluations"):
            if hasattr(fixture[key], name):
                monkeypatch.setattr(fixture[key], name, _work_history_no_effect)


def _work_history_authorizer(monkeypatch):
    original_connect = sqlite3.connect
    reads = []
    sensitive = {"snapshot", "answer", "error", "content", "title", "payload_json",
                 "provider_id", "model_id", "agent_config_fingerprint"}

    def connect(*args, **kwargs):
        connection = original_connect(*args, **kwargs)

        def authorize(action, first, second, database, trigger):
            if action == sqlite3.SQLITE_READ:
                reads.append((first, second))
                if second in sensitive:
                    return sqlite3.SQLITE_DENY
            if action in (sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_DELETE,
                          sqlite3.SQLITE_CREATE_TABLE, sqlite3.SQLITE_DROP_TABLE,
                          sqlite3.SQLITE_ALTER_TABLE):
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK

        connection.set_authorizer(authorize)
        return connection

    monkeypatch.setattr(sqlite3, "connect", connect)
    return reads


def test_work_history_real_five_sources_readonly_and_allowlisted(tmp_path, monkeypatch):
    from src.work_history import work_history

    fixture = _work_history_fixture(tmp_path)
    _work_history_forbid_mutation(monkeypatch, fixture)
    before = _work_history_bytes(tmp_path)
    reads = _work_history_authorizer(monkeypatch)
    result = work_history(**fixture)
    assert set(result) == _WORK_HISTORY_RESPONSE_FIELDS
    assert result["schema"] == "work-history.v1"
    assert result["total"] == 7
    assert result["has_more"] is False
    assert result["next_offset"] is None
    assert len(result["sources"]) == 5
    assert {source["kind"] for source in result["sources"]} == {
        "legacy_job", "task_run", "delegation", "agent_turn", "evaluation"}
    for source in result["sources"]:
        assert set(source) == {"kind", "state", "error_code", "truncated"}
        assert source["state"] == "available"
        assert source["error_code"] is None
        assert source["truncated"] is False
    rows = {item["key"]: item for item in result["items"]}
    assert len(rows) == 7
    for item in rows.values():
        assert set(item) == _WORK_HISTORY_FIELDS
        assert item["key"] == item["kind"] + ":" + item["id"]
    assert rows["legacy_job:legacy-failed"]["status"] == "FAILED"
    assert rows["legacy_job:legacy-failed"]["cost_usd"] == 0
    assert rows["legacy_job:legacy-failed"]["duration_ms"] == 0
    task = rows["task_run:task-failed"]
    assert task["agent_id"] == "deleted-agent"
    assert task["status"] == "FAILED"
    for field in ("agent_name", "trace_id", "receipt_id", "tools_executed", "target_written", "cost_usd"):
        assert task[field] is None
    passed_key = "delegation:delegation_" + "a" * 32
    passed = rows[passed_key]
    assert passed["status"] == "PASSED"
    assert passed["tools_executed"] is False
    assert passed["target_written"] is False
    assert passed["agent_name"] == "Historical fixture agent"
    assert passed["started_at"] == "2026-01-01T10:00:00+00:00"
    assert passed["completed_at"] == "2026-01-01T11:00:00+00:00"
    assert rows["delegation:delegation_" + "b" * 32]["status"] == "FAILED"
    turn = rows["agent_turn:turn-matched"]
    assert turn["related_key"] == passed_key
    assert passed["related_key"] == turn["key"]
    assert turn["started_at"] is None
    assert turn["duration_ms"] is None
    assert turn["completed_at"] == "2026-01-01T11:00:00+00:00"
    assert rows["evaluation:evaluation-running"]["status"] == "RUNNING"
    assert rows["evaluation:evaluation-running"]["trace_id"] is None
    assert rows["evaluation:evaluation-completed"]["duration_ms"] == 0
    encoded = json.dumps(result)
    assert _WORK_HISTORY_PRIVATE not in encoded
    assert str(tmp_path) not in encoded
    for field in ("snapshot", "rendered_prompt", "answer", "content", "payload_json", "task",
                  "provider_id", "model_id", "path", "grants", "stdout"):
        assert '"' + field + '"' not in encoded
    assert {table for table, column in reads} >= {"task_runs", "messages", "runs", "active_suite_runs"}
    assert _work_history_bytes(tmp_path) == before


def test_work_history_absent_sources_do_not_create_storage(tmp_path):
    from src.agent_tasks import TaskStore
    from src.conversations import ConversationStore
    from src.evaluation.agent_lab import EvaluationStore
    from src.services.agent_delegation import AgentDelegations
    from src.work_history import work_history

    absent = tmp_path / "absent"
    conversations = ConversationStore(absent / "conversations.sqlite3")
    delegations = AgentDelegations(
        directory=absent / "delegations", workspace=tmp_path, conversations=conversations,
        load_agent=_work_history_no_effect, resolve_model=_work_history_no_effect,
        execute_turn=_work_history_no_effect, authorize_tools=_work_history_no_effect,
        record_trace=_work_history_no_effect, trace_root=absent / "traces")
    before = sorted(str(path.relative_to(tmp_path)) for path in tmp_path.rglob("*"))
    result = work_history(
        jobs_directory=absent / "jobs", task_store=TaskStore(absent / "tasks.sqlite3"),
        conversations=conversations,
        evaluations=EvaluationStore(tmp_path, database_path=absent / "evaluations.sqlite3"),
        delegations=delegations)
    assert result["items"] == []
    assert result["total"] == 0
    assert len(result["sources"]) == 5
    assert all(source["state"] == "absent" for source in result["sources"])
    assert sorted(str(path.relative_to(tmp_path)) for path in tmp_path.rglob("*")) == before
    assert not absent.exists()


@pytest.mark.parametrize("storage", ["corrupt", "missing-table"])
def test_work_history_sqlite_errors_are_not_empty_success(tmp_path, storage):
    from src.agent_tasks import TaskStore
    from src.conversations import ConversationStore
    from src.evaluation.agent_lab import EvaluationStore

    path = tmp_path / "broken.sqlite3"
    if storage == "corrupt":
        path.write_bytes(b"synthetic invalid sqlite database")
    else:
        with sqlite3.connect(path) as connection:
            connection.execute("CREATE TABLE unrelated (id TEXT)")
    before = path.read_bytes()
    stores = (TaskStore(path), ConversationStore(path), EvaluationStore(tmp_path, database_path=path))
    for store in stores:
        result = store.work_history_metadata()
        assert result["state"] == "unavailable"
        assert result["items"] == []
        assert isinstance(result["error_code"], str) and result["error_code"]
        assert str(path) not in result["error_code"]
    assert path.read_bytes() == before


def test_work_history_corrupt_records_preserve_valid_attempts(tmp_path, monkeypatch):
    from src.work_history import work_history

    fixture = _work_history_fixture(tmp_path)
    (fixture["jobs_directory"] / "broken.json").write_text("{invalid", encoding="utf-8")
    record_path = tmp_path / "delegations" / "records" / ("delegation_" + "b" * 32 + ".json")
    record = json.loads(record_path.read_text(encoding="utf-8"))
    record["state"] = "PASSED"
    record_path.write_text(json.dumps(record), encoding="utf-8")
    _work_history_forbid_mutation(monkeypatch, fixture)
    before = _work_history_bytes(tmp_path)
    result = work_history(**fixture)
    sources = {source["kind"]: source for source in result["sources"]}
    for kind in ("legacy_job", "delegation"):
        assert sources[kind]["state"] == "partial"
        assert sources[kind]["error_code"]
    keys = {item["key"] for item in result["items"]}
    assert "legacy_job:legacy-failed" in keys
    assert "delegation:delegation_" + "a" * 32 in keys
    assert "delegation:delegation_" + "b" * 32 not in keys
    assert _work_history_bytes(tmp_path) == before


@pytest.mark.parametrize("link_kind", ["symlink", "hardlink"])
def test_work_history_rejects_unsafe_files(tmp_path, link_kind):
    import os
    from src.work_history import legacy_metadata

    jobs = tmp_path / "jobs"
    jobs.mkdir()
    original = tmp_path / "unsafe.json"
    original.write_text(json.dumps({"job_id": "unsafe", "status": "FAILED"}), encoding="utf-8")
    (jobs / "good.json").write_text(json.dumps({"job_id": "good", "status": "FAILED"}), encoding="utf-8")
    try:
        if link_kind == "symlink":
            (jobs / "unsafe.json").symlink_to(original)
        else:
            os.link(original, jobs / "unsafe.json")
    except (OSError, NotImplementedError) as error:
        pytest.skip("platform cannot create the unsafe-link fixture: " + str(error))
    before = _work_history_bytes(tmp_path)
    result = legacy_metadata(jobs)
    assert result["state"] == "partial"
    assert result["error_code"]
    assert [item["id"] for item in result["items"]] == ["good"]
    assert _work_history_bytes(tmp_path) == before


def test_work_history_real_times_order_unknowns_and_pagination(tmp_path):
    from src.work_history import work_history

    fixture = _work_history_fixture(tmp_path)
    with sqlite3.connect(fixture["task_store"].database_path) as connection:
        connection.execute("DELETE FROM task_runs")
        connection.executemany("INSERT INTO task_runs VALUES (?, ?, ?, ?, ?, ?, ?, ?)", [
            ("task-a", "deleted-agent", "private", "2026-01-01T10:00:00-05:00", "2026-01-01T11:00:00+00:00", "FAILED", "private", "private"),
            ("task-b", "deleted-agent", "private", "2026-01-01T16:00:00+01:00", None, "FAILED", "private", "private"),
            ("task-invalid", "deleted-agent", "private", "not-a-timestamp", "2026-01-01T09:00:00", "FAILED", "private", "private"),
        ])
    _work_history_save_delegation(fixture, "c", "PROPOSED", None, None)
    all_rows = work_history(**fixture, limit=200)
    task_rows = work_history(**fixture, kind="task_run", limit=200)
    assert task_rows["total"] == 3
    assert [row["id"] for row in task_rows["items"]] == ["task-a", "task-b", "task-invalid"]
    first, second, invalid = task_rows["items"]
    assert first["created_at"] == "2026-01-01T15:00:00+00:00"
    assert first["activity_at"] == second["activity_at"] == "2026-01-01T15:00:00+00:00"
    assert invalid["created_at"] is None
    assert invalid["completed_at"] is None
    assert invalid["activity_at"] is None
    for row in task_rows["items"]:
        for name in ("cost_usd", "duration_ms", "tools_executed", "target_written"):
            assert row[name] is None
    proposed = next(row for row in all_rows["items"] if row["id"] == "delegation_" + "c" * 32)
    for name in ("created_at", "started_at", "completed_at", "activity_at"):
        assert proposed[name] is None
    legacy = next(row for row in all_rows["items"] if row["kind"] == "legacy_job")
    assert legacy["created_at"] == "2026-01-01T07:00:00+00:00"
    assert legacy["cost_usd"] == legacy["duration_ms"] == 0
    first_page = work_history(**fixture, limit=2, offset=0)
    second_page = work_history(**fixture, limit=2, offset=2)
    assert first_page["items"] == all_rows["items"][:2]
    assert second_page["items"] == all_rows["items"][2:4]
    assert first_page["total"] == second_page["total"] == all_rows["total"]
    assert first_page["has_more"] is True and first_page["next_offset"] == 2
    assert second_page["has_more"] is True and second_page["next_offset"] == 4
    final = work_history(**fixture, limit=2, offset=all_rows["total"])
    assert final["items"] == []
    assert final["has_more"] is False and final["next_offset"] is None


@pytest.mark.parametrize("value,epoch", [
    (None, False), (True, True), (float("nan"), True), (float("inf"), True),
    (10 ** 100, True), ("bad", False), ("2026-01-01T00:00:00", False),
])
def test_work_history_invalid_time_is_unknown_not_exception(value, epoch):
    from src.work_history import _time

    assert _time(value, epoch=epoch) is None


@pytest.mark.parametrize("kwargs", [
    {"limit": True}, {"limit": 0}, {"limit": 201}, {"limit": 1.5},
    {"offset": True}, {"offset": -1}, {"offset": 10001}, {"kind": "unknown"},
])
def test_work_history_rejects_invalid_pagination(tmp_path, kwargs):
    from src.work_history import work_history

    fixture = _work_history_fixture(tmp_path)
    before = _work_history_bytes(tmp_path)
    with pytest.raises(ValueError):
        work_history(**fixture, **kwargs)
    assert _work_history_bytes(tmp_path) == before


@pytest.mark.parametrize("mismatch", ["agent", "conversation", "trace", "proposal", "ambiguous"])
def test_work_history_requires_exact_unambiguous_delegation_relationship(tmp_path, mismatch):
    from src.work_history import work_history

    fixture = _work_history_fixture(tmp_path)
    path = fixture["conversations"].database_path
    with sqlite3.connect(path) as connection:
        if mismatch == "agent":
            connection.execute("UPDATE conversations SET owner_id = 'other-agent' WHERE id = 'child-conversation'")
        elif mismatch == "conversation":
            connection.execute("UPDATE conversations SET id = 'other-child' WHERE id = 'child-conversation'")
            connection.execute("UPDATE messages SET conversation_id = 'other-child' WHERE conversation_id = 'child-conversation'")
        elif mismatch in ("trace", "proposal"):
            refs = {"trace": {"trace_id": "other-trace" if mismatch == "trace" else "trace-fixture"},
                    "delegation_parent": {"proposal_id": "delegation_" + ("d" if mismatch == "proposal" else "a") * 32}}
            connection.execute("UPDATE messages SET references_json = ? WHERE id = 'turn-matched'", (json.dumps(refs),))
        else:
            connection.execute("INSERT INTO messages SELECT 'turn-duplicate', conversation_id, 2, role, content, created_at, status, references_json FROM messages WHERE id = 'turn-matched'")
    result = work_history(**fixture)
    turns = [row for row in result["items"] if row["kind"] == "agent_turn"]
    assert len(turns) == (2 if mismatch == "ambiguous" else 1)
    assert all(row["related_key"] is None for row in turns)
    delegation = next(row for row in result["items"] if row["id"] == "delegation_" + "a" * 32)
    assert delegation["related_key"] is None
    assert len([row for row in result["items"] if row["kind"] == "delegation"]) == 2


def test_work_history_explicit_truncation_and_mismatched_filename(tmp_path):
    from src.work_history import legacy_metadata

    jobs = tmp_path / "jobs"
    jobs.mkdir()
    for identity in ("a", "b", "c"):
        (jobs / (identity + ".json")).write_text(json.dumps({"job_id": identity, "status": "FAILED"}), encoding="utf-8")
    before = _work_history_bytes(tmp_path)
    bounded = legacy_metadata(jobs, limit=2)
    assert len(bounded["items"]) == 2
    assert bounded["truncated"] is True
    assert _work_history_bytes(tmp_path) == before
    (jobs / "wrong.json").write_text(json.dumps({"job_id": "different", "status": "FAILED"}), encoding="utf-8")
    result = legacy_metadata(jobs)
    assert result["state"] == "partial"
    assert result["error_code"]
    assert {row["id"] for row in result["items"]} == {"a", "b", "c"}


def test_work_history_endpoint_uses_runtime_bindings_and_validates_queries(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from src.api import server
    import src.jobs as jobs_repository
    from src.work_history import work_history

    fixture = _work_history_fixture(tmp_path)
    agents = tmp_path / "agents"
    monkeypatch.setattr(server, "AGENTS_DIR", agents)
    monkeypatch.setattr(jobs_repository, "JOBS_DIR", fixture["jobs_directory"])
    monkeypatch.setattr(server, "CONVERSATIONS", fixture["conversations"])
    monkeypatch.setattr(server, "EVALUATIONS", fixture["evaluations"])
    monkeypatch.setattr(server, "_agent_delegations", lambda: fixture["delegations"])
    monkeypatch.setenv("BAGO_TASK_HISTORY_PATH", str(fixture["task_store"].database_path))
    monkeypatch.setattr(server.provider_runtime, "chat", _work_history_no_effect)
    _work_history_forbid_mutation(monkeypatch, fixture)
    before = _work_history_bytes(tmp_path)
    expected = work_history(**fixture)
    # Deliberately avoid lifespan: this GET must not depend on startup jobs or host storage.
    client = TestClient(server.app)
    try:
        response = client.get("/api/work-history")
        assert response.status_code == 200
        assert response.json() == expected
        page = client.get("/api/work-history", params={"kind": "task_run", "limit": 2, "offset": 0})
        assert page.status_code == 200
        assert page.json() == work_history(**fixture, kind="task_run", limit=2, offset=0)
        for query in ("limit=0", "limit=201", "offset=-1", "offset=10001", "kind=unknown", "limit=true"):
            assert client.get("/api/work-history?" + query).status_code == 422
    finally:
        client.close()
    assert _work_history_bytes(tmp_path) == before
    assert not agents.exists()


