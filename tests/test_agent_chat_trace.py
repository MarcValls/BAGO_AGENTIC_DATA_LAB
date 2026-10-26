import asyncio
import hashlib
import json
import pytest
from pathlib import Path

from fastapi import Response

from src.api import server
from src.conversations import ConversationStore


def test_agent_chat_pins_profile_model_and_returns_trace_headers(monkeypatch, tmp_path: Path):
    class Agent:
        id = "agent-demo"

        class Config:
            system_prompt = "Review only supplied findings."
            model_id = "kimi-k2.6"
            provider_id = "ollama-cloud"

        config = Config()

    calls = []
    monkeypatch.setattr(server, "_load_agent", lambda _agent_id: Agent())
    store = ConversationStore(tmp_path / "conversations.sqlite3")
    conversation = store.create("agent", "agent-demo")
    monkeypatch.setattr(server, "CONVERSATIONS", store)
    monkeypatch.setattr(server.ollama, "chat", lambda model, messages: calls.append((model, messages)) or "Finding reviewed.")
    monkeypatch.setattr(server, "AGENT_CHAT_TRACE_DIR", tmp_path)
    monkeypatch.setattr(server, "export_local_trace_to_otlp", lambda *args, **kwargs: None)
    monkeypatch.setenv("BAGO_OTEL_EXPORTER_OTLP_ENDPOINT", "")

    response = Response()
    result = asyncio.run(server.chat_with_agent(
        "agent-demo",
        server.AgentChatRequest(message="P1-02 run token demo-20261009", conversation_id=conversation["id"], revision=0),
        response,
    ))

    assert calls[0][0] == "kimi-k2.6"
    assert result["agent_id"] == "agent-demo"
    assert result["assistant_message"] == "Finding reviewed."
    assert result["conversation"]["messages"][1]["content"] == "Finding reviewed."
    assert result["conversation"]["messages"][1]["references"]["trace"]["trace_id"] == response.headers["X-Bago-Trace-Id"]
    assert response.headers["X-Bago-Trace-State"] == "local_only"
    assert response.headers["X-Bago-Trace-Id"].startswith("trace-")
    files = list(tmp_path.glob("trace-*.json"))
    assert len(files) == 1
    trace = json.loads(files[0].read_text(encoding="utf-8"))
    serialized = json.dumps(trace)
    assert response.headers["X-Bago-Trace-Id"] == trace["trace_id"]
    assert trace["events"][0]["attributes"]["model_id"] == "kimi-k2.6"
    assert "P1-02 run token" not in serialized
    assert "Finding reviewed." not in serialized


def test_real_agent_tool_loop_traces_allowed_and_denied_exact_file_reads(monkeypatch, tmp_path: Path):
    (tmp_path / "evidence.txt").write_text("Finding P1-02 is reproducible.\nSecond line.\n", encoding="utf-8")
    (tmp_path / "outside.txt").write_text("unapproved secret evidence", encoding="utf-8")

    class Agent:
        id = "agent-auditor"

        class Config:
            system_prompt = "Audit only files returned by the read tool."
            model_id = "kimi-k2.6"
            provider_id = "ollama-cloud"

        config = Config()

    store = ConversationStore(tmp_path / "conversations.sqlite3")
    conversation = store.create("agent", "agent-auditor")
    monkeypatch.setattr(server, "CONVERSATIONS", store)
    monkeypatch.setattr(server, "_load_agent", lambda _agent_id: Agent())
    monkeypatch.setattr(server, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(server, "current_workspace_root", lambda: tmp_path.resolve())
    monkeypatch.setattr(server, "AGENT_CHAT_TRACE_DIR", tmp_path / "traces")
    monkeypatch.setattr(server, "export_local_trace_to_otlp", lambda *args, **kwargs: None)
    monkeypatch.setenv("BAGO_OTEL_EXPORTER_OTLP_ENDPOINT", "")
    grant = server.WORKSPACE_READ_AUTHORIZATIONS.issue(
        tmp_path, owner_kind="agent", owner_id="agent-auditor", conversation_id=conversation["id"],
        revision=0, paths=["evidence.txt"],
    )
    provider_calls = []
    turns = iter([
        {"tool_calls": [
            {"function": {"name": "read_workspace_file", "arguments": {"path": "evidence.txt", "start_line": 1, "end_line": 1}}},
            {"function": {"name": "read_workspace_file", "arguments": {"path": "outside.txt"}}},
        ]},
        {"content": "The authorized evidence supports the finding; the other path was denied."},
    ])

    def chat_turn(model, messages, **kwargs):
        provider_calls.append((model, messages, kwargs))
        return next(turns)

    monkeypatch.setattr(server.ollama, "chat_turn", chat_turn)
    response = Response()
    result = asyncio.run(server.chat_with_agent("agent-auditor", server.AgentChatRequest(
        message="Inspect evidence and try the unapproved control file.", conversation_id=conversation["id"], revision=0,
        workspace_read_authorization_id=grant["authorization_id"],
    ), response))

    assert result["assistant_message"].startswith("The authorized evidence")
    assert result["sources"][0]["content_sha256"] == hashlib.sha256("1: Finding P1-02 is reproducible.".encode()).hexdigest()
    assert [item["decision"] for item in result["read_events"]] == ["ALLOW", "DENY"]
    assert result["read_events"][1]["reason_code"] == "PATH_NOT_AUTHORIZED"
    second_model_messages = provider_calls[1][1]
    assert any("Finding P1-02 is reproducible." in str(item.get("content")) for item in second_model_messages)
    assert "unapproved secret evidence" not in str(second_model_messages)
    trace = json.loads(next((tmp_path / "traces").glob("trace-*.json")).read_text(encoding="utf-8"))
    assert trace["events"][0]["attributes"]["model_id"] == "kimi-k2.6"
    reads = [event for event in trace["events"] if event["name"] == "workspace.read"]
    assert [event["status"] for event in reads] == ["ALLOW", "DENY"]
    assert all(event["parent_event_id"] == trace["events"][0]["event_id"] for event in reads)
    assert reads[0]["attributes"]["file_sha256"] == hashlib.sha256((tmp_path / "evidence.txt").read_bytes()).hexdigest()


def _a4_receipt_trace():
    from src.observability.native_timing import NativeTimingRecorder

    recorder = NativeTimingRecorder(run_id="agent-chat-" + "a" * 32)
    recorder.trace_id = "trace-" + "a" * 16
    with recorder.span("agent.chat") as root:
        with recorder.span("workspace.read") as measured:
            measured.finish(status="SUCCEEDED")
        root.finish(status="SUCCEEDED")
    return recorder.to_local_trace(), measured.event_id


def test_a4_individual_receipt_identity_and_no_global_gate():
    trace, event_id = _a4_receipt_trace()
    measured = {"decision": "ALLOW", "file_sha256": "b" * 64}
    equal_but_distinct = dict(measured)
    observation = {"read_events": [measured, equal_but_distinct, measured],
                   "_native_receipt_invocations": [(measured, event_id)]}
    result = server._native_chat_compatibility_evidence(
        trace, {"root_attributes": {}, "observation": observation})
    native = next(event for event in result.events if event.event_id == event_id)
    original = next(event for event in trace.events if event.event_id == event_id)
    assert native.status == measured["decision"]
    assert native.attributes["native_outcome"] == original.status
    assert native.start_time_unix_nano == original.start_time_unix_nano
    assert native.end_time_unix_nano == original.end_time_unix_nano
    assert native.attributes["file_sha256"] == "b" * 64
    projections = [event for event in result.events if event.attributes.get("timing_mode") == "projection"]
    assert len(projections) == 1
    assert projections[0].start_time_unix_nano is None
    assert projections[0].end_time_unix_nano is None
    assert "depth" not in projections[0].attributes
    assert "file_sha256" not in original.attributes


def test_a4_rejects_ambiguous_missing_and_incomplete_native_bindings():
    from dataclasses import replace

    trace, event_id = _a4_receipt_trace()
    receipt = {"decision": "DENY"}
    native = next(event for event in trace.events if event.event_id == event_id)
    incomplete = replace(native, attributes=dict(native.attributes, interval_complete=False))
    cases = [
        (trace, [(receipt, "event-missing")]),
        (trace, [(receipt, event_id), (receipt, event_id)]),
        (trace, [(receipt, event_id), (dict(receipt), event_id)]),
        (replace(trace, events=trace.events + (native,)), [(receipt, event_id)]),
        (replace(trace, events=tuple(incomplete if event is native else event for event in trace.events)),
         [(receipt, event_id)]),
    ]
    for frozen, bindings in cases:
        result = server._native_chat_compatibility_evidence(frozen, {
            "root_attributes": {}, "observation": {
                "read_events": [receipt], "_native_receipt_invocations": bindings}})
        projected = [event for event in result.events if event.attributes.get("timing_mode") == "projection"]
        assert len(projected) == 1
        assert projected[0].status == "DENY"
        assert projected[0].start_time_unix_nano is None
        assert projected[0].end_time_unix_nano is None


def test_a4_individual_compatibility_projections_redact_raw_data():
    trace, _ = _a4_receipt_trace()
    receipts = [
        {"kind": "public_web_read", "decision": "ALLOW"},
        {"kind": "workspace_write_proposal", "decision": "FAIL"},
        {"kind": "document_tool", "tool_name": "document_extract", "decision": "DENY"},
    ]
    for receipt in receipts:
        receipt.update(path="RAW_PRIVATE_PATH", arguments="RAW_ARGUMENTS", payload="RAW_PAYLOAD",
                       error="RAW_ERROR", authorization_id="RAW_AUTHORIZATION", provider_id="RAW_PROVIDER",
                       document="RAW_DOCUMENT", tool_call_id="RAW_TOOL_CALL")
    result = server._native_chat_compatibility_evidence(trace, {
        "root_attributes": {}, "observation": {"read_events": receipts + receipts}})
    projections = [event for event in result.events if event.attributes.get("timing_mode") == "projection"]
    assert [event.name for event in projections] == ["web.read", "workspace.propose_write", "document_extract"]
    assert [event.status for event in projections] == ["ALLOW", "FAIL", "DENY"]
    assert len({event.event_id for event in projections}) == 3
    assert "RAW_" not in result.to_json()
    assert all(event.start_time_unix_nano is None and event.end_time_unix_nano is None for event in projections)


def test_a4_receipt_worker_binds_actual_object_after_closed_handler(tmp_path):
    from src.observability.native_timing import NativeTimingRecorder

    (tmp_path / "evidence.txt").write_text("native evidence", encoding="utf-8")
    recorder = NativeTimingRecorder(run_id="agent-chat-" + "b" * 32)
    recorder.trace_id = "trace-" + "b" * 16
    observation = {"read_events": []}
    with recorder.span("agent.chat") as root:
        result, receipt = server._native_receipt_call(
            recorder, observation, "workspace.read", server.read_workspace_file,
            tmp_path, {"path": "evidence.txt"}, ["evidence.txt"])
        observation["read_events"].append(receipt)
        root.finish(status="SUCCEEDED")
    frozen = recorder.to_local_trace()
    bound, event_id = observation["_native_receipt_invocations"][0]
    assert bound is receipt
    event = next(event for event in frozen.events if event.event_id == event_id)
    assert event.attributes["interval_complete"] is True
    assert event.start_time_unix_nano is not None
    assert event.end_time_unix_nano >= event.start_time_unix_nano
    assert result is not None
    projected = server._native_chat_compatibility_evidence(frozen, {
        "root_attributes": {}, "observation": observation})
    assert len(projected.events) == len(frozen.events)


def _a4_failed_message(store):
    conversation = store.create("agent", "agent-a4")
    reference = {"version": 1, "agent_id": "agent-a4", "conversation_id": conversation["id"],
                 "trace_id": "trace-" + "c" * 16, "execution_id": "agent-chat-" + "c" * 32,
                 "trace_state": "pending_finalization"}
    references = {"trace": reference, "sources": [{"unchanged": True}],
                  "execution_failure": {"state": "FAILED", "response_received": False}}
    message = store.append_message(conversation["id"], 0, "assistant", "", references, status="failed")
    target = server._native_failed_chat_target("agent-a4", conversation["id"], message, references, reference)
    metadata = dict(reference, trace_state="local_only", local_state="persisted",
                    export_state="not_configured", sidecar_state="persisted")
    return conversation, target, metadata


def test_a4_failed_writeback_changes_only_existing_references(monkeypatch, tmp_path):
    import pytest

    store = ConversationStore(tmp_path / "failed.sqlite3")
    monkeypatch.setattr(server, "CONVERSATIONS", store)
    conversation, target, metadata = _a4_failed_message(store)
    with store._connect() as connection:
        before_conversation = dict(connection.execute("SELECT * FROM conversations WHERE id = ?", (conversation["id"],)).fetchone())
        before_messages = [dict(row) for row in connection.execute("SELECT * FROM messages")]
    server._native_failed_chat_writeback(target, metadata)
    with store._connect() as connection:
        after_conversation = dict(connection.execute("SELECT * FROM conversations WHERE id = ?", (conversation["id"],)).fetchone())
        after_messages = [dict(row) for row in connection.execute("SELECT * FROM messages")]
    assert after_conversation == before_conversation
    assert len(after_messages) == len(before_messages) == 1
    before = before_messages[0]
    after = after_messages[0]
    before_refs = json.loads(before.pop("references_json"))
    after_refs = json.loads(after.pop("references_json"))
    assert after == before
    assert after_refs.pop("trace") == metadata
    before_refs.pop("trace")
    assert after_refs == before_refs
    with pytest.raises(server.ConversationConflict):
        server._native_failed_chat_writeback(target, metadata)


def test_a4_failed_writeback_rejects_every_cas_guard(monkeypatch, tmp_path):
    import pytest

    store = ConversationStore(tmp_path / "cas.sqlite3")
    monkeypatch.setattr(server, "CONVERSATIONS", store)
    mutations = [
        ("UPDATE conversations SET revision = revision + 1 WHERE id = ?", "conversation"),
        ("UPDATE conversations SET status = 'deleted' WHERE id = ?", "conversation"),
        ("UPDATE conversations SET owner_id = 'another-agent' WHERE id = ?", "conversation"),
        ("UPDATE messages SET sequence = sequence + 1 WHERE id = ?", "message"),
        ("UPDATE messages SET status = 'complete' WHERE id = ?", "message"),
        ("UPDATE messages SET role = 'user' WHERE id = ?", "message"),
        ("UPDATE messages SET content = 'not empty' WHERE id = ?", "message"),
        ("UPDATE messages SET references_json = '{}' WHERE id = ?", "message"),
    ]
    for sql, identity in mutations:
        conversation, target, metadata = _a4_failed_message(store)
        with store._connect() as connection:
            connection.execute(sql, (conversation["id"] if identity == "conversation" else target["message_id"],))
            before = [dict(row) for row in connection.execute("SELECT * FROM messages ORDER BY id")]
        with pytest.raises(server.ConversationConflict):
            server._native_failed_chat_writeback(target, metadata)
        with store._connect() as connection:
            assert [dict(row) for row in connection.execute("SELECT * FROM messages ORDER BY id")] == before
    _, target, metadata = _a4_failed_message(store)
    for key in ("trace_id", "execution_id", "agent_id", "conversation_id"):
        with pytest.raises(ValueError):
            server._native_failed_chat_writeback(target, dict(metadata, **{key: "wrong-identity"}))
    for key in ("message_id", "conversation_id"):
        with pytest.raises(server.ConversationConflict, match=".*"):
            server._native_failed_chat_writeback(dict(target, **{key: "missing-identity"}), metadata)


@pytest.mark.parametrize(("receipt", "expected_status"), [
    ({"decision": "ALLOW"}, "SUCCEEDED"),
    ({"decision": "DENY"}, "DENIED"),
    ({"decision": "FAIL"}, "FAILED"),
    ({}, "FAILED"),
    ({"decision": "UNKNOWN"}, "FAILED"),
    (None, "FAILED"),
    ("invalid", "FAILED"),
])
def test_a4_receipt_call_fails_closed_for_unknown_or_missing_decisions(receipt, expected_status):
    from src.observability.native_timing import NativeTimingRecorder
    import pytest

    recorder = NativeTimingRecorder(run_id="agent-chat-" + "d" * 32)

    def handler(*args, **kwargs):
        return {"ok": True}, receipt

    server._native_receipt_call(recorder, None, "workspace.read", handler)
    event = recorder.to_local_trace().events[0]
    assert event.status == expected_status

