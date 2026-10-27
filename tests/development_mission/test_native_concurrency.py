import asyncio
import hashlib
import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.api import server
from src.observability.local_trace import LocalTrace, TraceEvent, TraceKind


def frozen(index=1):
    trace_id = "trace-" + format(index, "032x")
    event = TraceEvent(
        event_id="event-" + format(index, "016x"), trace_id=trace_id,
        sequence=0, name="agent.chat", kind=TraceKind.WORKFLOW,
        status="SUCCEEDED", attributes={}, evidence_refs=(),
        start_time_unix_nano=1700000000000000001,
        end_time_unix_nano=1700000000000000101,
    )
    return LocalTrace(trace_id=trace_id, run_id="agent-chat-" + format(index, "032x"), events=(event,))


@pytest.fixture
def evidence(tmp_path, monkeypatch):
    root = tmp_path / "traces"
    monkeypatch.setattr(server, "AGENT_CHAT_TRACE_DIR", root)
    monkeypatch.setenv("BAGO_OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector.invalid/v1/traces")
    return root


def finalize(trace, conversation="conversation-1"):
    return server._finalize_native_agent_chat_trace(
        trace, agent_id="agent-1", conversation_id=conversation,
    )


def assert_digest(metadata):
    unsigned = dict(metadata)
    digest = unsigned.pop("metadata_sha256")
    canonical = json.dumps(unsigned, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    assert digest == hashlib.sha256(canonical).hexdigest()


def test_persistence_precedes_export_and_preserves_timestamps(evidence, monkeypatch):
    trace = frozen()
    before = trace.to_json()
    calls = []

    def export(value, **kwargs):
        data = (evidence / (value.trace_id + ".json")).read_bytes()
        assert data == (before + "\n").encode("utf-8")
        assert not (evidence / ("metadata-" + value.trace_id + ".v1.json")).exists()
        assert kwargs["ledger_dir"] == evidence / "export-ledger"
        assert kwargs["timeout"] == 2.0
        assert value is trace
        calls.append(value)
        return SimpleNamespace(exported=True)

    monkeypatch.setattr(server, "export_local_trace_to_otlp", export)
    result = finalize(trace)
    assert result["export_state"] == "exported"
    assert result["sidecar_state"] == "persisted"
    assert calls == [trace]
    assert trace.to_json() == before
    assert trace.events[0].start_time_unix_nano == 1700000000000000001
    assert trace.events[0].end_time_unix_nano == 1700000000000000101
    data = (evidence / (trace.trace_id + ".json")).read_bytes()
    assert result["trace_sha256"] == hashlib.sha256(data).hexdigest()
    assert json.loads((evidence / ("metadata-" + trace.trace_id + ".v1.json")).read_text()) == result
    assert_digest(result)


@pytest.mark.parametrize("field,value", [
    ("trace_id", "../escape"), ("run_id", "../escape"),
    ("agent_id", "../escape"), ("conversation_id", "../escape"),
])
def test_invalid_ids_have_no_effects(evidence, monkeypatch, field, value):
    def forbidden(*args, **kwargs):
        pytest.fail("export must not execute")

    monkeypatch.setattr(server, "export_local_trace_to_otlp", forbidden)
    trace = frozen()
    kwargs = {"agent_id": "agent-1", "conversation_id": "conversation-1"}
    if field in kwargs:
        kwargs[field] = value
    else:
        trace = replace(trace, **{field: value})
    with pytest.raises(ValueError):
        server._finalize_native_agent_chat_trace(trace, **kwargs)
    assert not evidence.exists()


def test_event_id_mismatch_rejected_before_effects(evidence):
    trace = frozen()
    trace = replace(trace, events=(replace(trace.events[0], trace_id=frozen(2).trace_id),))
    with pytest.raises(ValueError):
        finalize(trace)
    assert not evidence.exists()


def test_conflicting_bytes_preserved_without_export(evidence, monkeypatch):
    evidence.mkdir()
    trace = frozen()
    target = evidence / (trace.trace_id + ".json")
    target.write_bytes(b"previous evidence")

    def forbidden(*args, **kwargs):
        pytest.fail("conflicting evidence must not export")

    monkeypatch.setattr(server, "export_local_trace_to_otlp", forbidden)
    result = finalize(trace)
    assert result["local_state"] == "conflict"
    assert result["export_state"] == "not_attempted"
    assert "trace_sha256" not in result
    assert target.read_bytes() == b"previous evidence"


def _exercise_failed_chat_reference_boundary(monkeypatch, *, native):
    import asyncio
    from types import SimpleNamespace
    from src.api import server

    calls = []
    persisted = []
    reference = {
        "version": 1,
        "trace_id": "trace-" + "a" * 32,
        "execution_id": "agent-chat-" + "b" * 32,
        "trace_state": "pending_finalization",
    }
    original_reference = dict(reference)
    legacy_reference = {"trace_id": "trace-legacy", "trace_state": "local_only"}

    def record_legacy(**kwargs):
        calls.append(kwargs)
        return legacy_reference

    def append_message(*args, **kwargs):
        persisted.append((args, kwargs))
        return {"revision": 3}

    monkeypatch.setattr(server, "_record_agent_chat_trace", record_legacy)
    monkeypatch.setattr(server, "CONVERSATIONS", SimpleNamespace(append_message=append_message))
    monkeypatch.setattr(server, "_provider_http_error", lambda error: server.HTTPException(
        502, detail={"code": "provider_error"}, headers={"X-Provider-Failure": "1"}))
    sources = [{"path": "authorized.py", "start_line": 1, "end_line": 2}]
    read_events = [{"kind": "workspace_read", "decision": "ALLOW"}]
    proposal = {"proposal_id": "proposal-test"}
    delegation = {"proposal_id": "delegation-test"}
    options = {"native_trace_reference": reference} if native else {}
    result = asyncio.run(server._failed_chat_exception(
        RuntimeError("PRIVATE_PROVIDER_ERROR"), owner_id="agent-test", provider_id="provider-test",
        model_id="model-test", conversation_id="conversation-test", revision=2,
        started_at_ns=1, sources=sources, read_events=read_events,
        workspace_write_proposal=proposal, delegation_context=delegation, **options))

    assert result.status_code == 502
    assert result.headers == {"X-Provider-Failure": "1"}
    assert len(persisted) == 1
    args, kwargs = persisted[0]
    assert args[:4] == ("conversation-test", 2, "assistant", "")
    assert kwargs == {"status": "failed"}
    references = args[4]
    assert references["sources"] == sources
    assert references["read_events"] == read_events
    assert references["workspace_write_proposal"] == proposal
    assert references["delegation_parent"] == delegation
    assert references["execution_failure"] == {
        "state": "FAILED", "failure_code": "provider_error", "response_received": False}
    assert result.detail["revision"] == 3
    assert result.detail["evidence_persistence"]["conversation"] == "persisted"
    assert "PRIVATE_PROVIDER_ERROR" not in str(result.detail)
    if native:
        assert calls == []
        assert references["trace"] == original_reference
        assert references["trace"] is not reference
        assert reference == original_reference
        assert "trace_sha256" not in references["trace"]
        assert result.detail["evidence_persistence"]["trace"] == "pending_finalization"
    else:
        assert len(calls) == 1
        assert calls[0]["execution_status"] == "FAILED"
        assert calls[0]["sources"] == sources
        assert calls[0]["read_events"] == read_events
        assert references["trace"] == legacy_reference
        assert result.detail["evidence_persistence"]["trace"] == "persisted"


def test_native_failed_chat_reference_skips_legacy_trace(monkeypatch):
    _exercise_failed_chat_reference_boundary(monkeypatch, native=True)


def test_legacy_failed_chat_reference_remains_compatible(monkeypatch):
    _exercise_failed_chat_reference_boundary(monkeypatch, native=False)


def _readonly_native_fixture(tmp_path, monkeypatch):
    import hashlib
    import json
    from src.api import server as api

    monkeypatch.setattr(api, "AGENT_CHAT_TRACE_DIR", tmp_path)
    def forbidden(*args, **kwargs):
        raise AssertionError("read projection must not export or finalize")
    monkeypatch.setattr(api, "export_local_trace_to_otlp", forbidden)
    monkeypatch.setattr(api, "_finalize_native_agent_chat_trace", forbidden)
    reference = {"version": 1, "agent_id": "agent-one", "conversation_id": "conversation-one",
                 "trace_id": "trace-" + "a" * 32, "execution_id": "agent-chat-" + "b" * 32,
                 "trace_state": "pending_finalization"}
    data = json.dumps({"trace_id": reference["trace_id"], "run_id": reference["execution_id"],
                       "events": []}).encode("utf-8")
    trace_path = tmp_path / (reference["trace_id"] + ".json")
    sidecar_path = tmp_path / ("metadata-" + reference["trace_id"] + ".v1.json")
    trace_path.write_bytes(data)
    metadata = dict(reference, trace_state="local_only", local_state="persisted",
                    export_state="not_configured", sidecar_state="persisted",
                    trace_sha256=hashlib.sha256(data).hexdigest())
    def sign(value):
        unsigned = dict(value)
        unsigned.pop("metadata_sha256", None)
        canonical = json.dumps(unsigned, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
        unsigned["metadata_sha256"] = hashlib.sha256(canonical).hexdigest()
        sidecar_path.write_text(json.dumps(unsigned), encoding="utf-8")
        return unsigned
    metadata = sign(metadata)
    return api, reference, metadata, trace_path, sidecar_path, sign


def test_native_read_projection_is_detached_and_does_not_export(tmp_path, monkeypatch):
    import copy
    api, reference, metadata, trace_path, sidecar_path, _ = _readonly_native_fixture(tmp_path, monkeypatch)
    monkeypatch.setenv("BAGO_OTEL_EXPORTER_OTLP_ENDPOINT", "http://127.0.0.1:4318")
    conversation = {"owner_kind": "agent", "owner_id": "agent-one", "messages": [
        {"role": "assistant", "references": {"trace": reference, "sources": [{"id": "retained"}]}}]}
    original = copy.deepcopy(conversation)
    before = {path.name: path.read_bytes() for path in tmp_path.iterdir()}
    for _ in range(2):
        result = api._project_native_chat_references(conversation, conversation_id="conversation-one")
        assert result["messages"][0]["references"]["trace"] == metadata
        assert result["messages"][0]["references"]["sources"] == [{"id": "retained"}]
    assert conversation == original
    assert {path.name: path.read_bytes() for path in tmp_path.iterdir()} == before


def test_native_read_projection_rejects_invalid_evidence(tmp_path, monkeypatch):
    api, reference, metadata, trace_path, sidecar_path, sign = _readonly_native_fixture(tmp_path, monkeypatch)
    def resolve():
        return api._resolve_native_agent_chat_trace(reference, agent_id="agent-one", conversation_id="conversation-one")
    original_trace = trace_path.read_bytes()
    original_sidecar = sidecar_path.read_bytes()
    sidecar_path.write_bytes(b"not-json")
    assert resolve()["trace_state"] == "metadata_failed"
    sidecar_path.write_bytes(original_sidecar)
    changed = dict(metadata, agent_id="other-owner")
    sign(changed)
    assert resolve()["trace_state"] == "metadata_failed"
    sign(dict(metadata, version=2))
    assert resolve()["trace_state"] == "metadata_failed"
    sign(dict(metadata, local_state="failed"))
    assert resolve()["trace_state"] == "metadata_failed"
    sidecar_path.write_bytes(original_sidecar)
    trace_path.write_bytes(original_trace + b" ")
    assert resolve()["trace_state"] == "metadata_failed"
    trace_path.unlink()
    assert resolve()["trace_state"] == "metadata_failed"
    sidecar_path.unlink()
    assert resolve()["trace_state"] == "pending_finalization"
    unsafe = dict(reference, trace_id="../outside")
    assert api._resolve_native_agent_chat_trace(unsafe, agent_id="agent-one", conversation_id="conversation-one")["trace_state"] == "metadata_failed"


def test_native_read_projection_preserves_valid_jaeger_receipt(tmp_path, monkeypatch):
    api, reference, metadata, _, _, sign = _readonly_native_fixture(tmp_path, monkeypatch)
    receipt = sign(dict(metadata, export_state="exported", trace_state="exported",
                        jaeger_trace_id="c" * 32, jaeger_url="http://localhost:16686/trace/" + "c" * 32))
    resolved = api._resolve_native_agent_chat_trace(reference, agent_id="agent-one", conversation_id="conversation-one")
    assert resolved == receipt
    sign(dict(receipt, jaeger_url="http://user:secret@localhost/trace/" + "c" * 32))
    assert api._resolve_native_agent_chat_trace(reference, agent_id="agent-one", conversation_id="conversation-one")["trace_state"] == "metadata_failed"


def _native_lifecycle_fixture(tmp_path, monkeypatch):
    import copy
    import time
    from types import SimpleNamespace
    from src.api import server as api
    from src.observability import native_timing

    conversations = {}
    frozen = []
    effects = []
    provider_calls = []
    controls = {"deny": False, "append_fail": False, "provider_fail": False}

    class ProviderFailure(Exception):
        code = "provider_error"

    class Store:
        def get(self, conversation_id):
            return copy.deepcopy(conversations[conversation_id])

        def history(self, conversation_id):
            return [{"role": item["role"], "content": item["content"]}
                    for item in conversations[conversation_id]["messages"]]

        def append_message(self, conversation_id, revision, role, content, references=None, **kwargs):
            conversation = conversations[conversation_id]
            assert revision == conversation["revision"]
            if role == "assistant":
                assert native_timing._current.get() is not None
                if controls["append_fail"]:
                    raise OSError("PRIVATE_APPEND_FAILURE")
            conversation["revision"] += 1
            message = {"role": role, "content": content, "references": copy.deepcopy(references or {}),
                       "revision": conversation["revision"], **kwargs}
            conversation["messages"].append(message)
            effects.append((conversation_id, role, time.monotonic_ns()))
            return message

    def owned(conversation_id, kind, owner):
        conversation = conversations[conversation_id]
        assert conversation["owner_id"] == owner
        return copy.deepcopy(conversation)

    def authorize(*args, **kwargs):
        if controls["deny"]:
            raise api.HTTPException(422, detail={"code": "authorization_denied"})
        return []

    def provider(*args):
        binding = native_timing._current.get()
        assert binding is not None
        provider_calls.append(binding[0].trace_id)
        time.sleep(0.12)
        if controls["provider_fail"]:
            raise ProviderFailure("PRIVATE_PROVIDER_FAILURE")
        return "answer"

    original_finalize = api._finalize_native_agent_chat_trace
    def finalize(trace, **kwargs):
        assert all(event.attributes["interval_complete"] for event in trace.events)
        frozen.append(trace)
        effects.append((kwargs["conversation_id"], "finalize", time.monotonic_ns()))
        return original_finalize(trace, **kwargs)

    def forbidden(*args, **kwargs):
        raise AssertionError("legacy trace or unexpected export")

    monkeypatch.setattr(api, "AGENT_CHAT_TRACE_DIR", tmp_path)
    monkeypatch.delenv("BAGO_OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    monkeypatch.setattr(api, "CONVERSATIONS", Store())
    config = SimpleNamespace(provider_id="provider-test", model_id="model-test", system_prompt="system", tools=[])
    monkeypatch.setattr(api, "_load_model_enabled_agent", lambda owner: SimpleNamespace(id=owner, config=config))
    monkeypatch.setattr(api, "_owned_conversation", owned)
    monkeypatch.setattr(api, "current_workspace_root", lambda: tmp_path)
    monkeypatch.setattr(api, "_consume_workspace_read_authorization", authorize)
    monkeypatch.setattr(api, "_consume_workspace_scan_authorization", lambda *args, **kwargs: [])
    monkeypatch.setattr(api, "_consume_web_authorization", lambda *args, **kwargs: None)
    monkeypatch.setattr(api, "_workspace_read_instructions", lambda *args, **kwargs: "")
    monkeypatch.setattr(api, "baseline_chat_context", lambda: {"prompt_guidance": ""})
    monkeypatch.setattr(api, "_record_chat_cognition_trace", lambda **kwargs: {"state": "recorded"})
    monkeypatch.setattr(api, "_record_agent_chat_trace", forbidden)
    monkeypatch.setattr(api, "provider_runtime", SimpleNamespace(chat=provider, ProviderRuntimeError=ProviderFailure))
    monkeypatch.setattr(api, "_provider_http_error", lambda error: api.HTTPException(
        502, detail={"code": "provider_error"}, headers={"X-Provider-Failure": "1"}))
    monkeypatch.setattr(api, "_conversation_error", lambda error: api.HTTPException(409, detail={"code": "conversation_error"}))
    monkeypatch.setattr(api, "_finalize_native_agent_chat_trace", finalize)

    def request(suffix):
        owner, conversation_id = "agent-" + suffix, "conversation-" + suffix
        conversations[conversation_id] = {"id": conversation_id, "owner_kind": "agent", "owner_id": owner,
                                          "revision": 0, "messages": []}
        return owner, SimpleNamespace(conversation_id=conversation_id, revision=0, message="PRIVATE_MESSAGE",
            document_authorization_id=None, workspace_read_authorization_id=None,
            workspace_scan_authorization_id=None, web_read_authorization_id=None,
            allow_workspace_write_proposals=False, cognitive_mode="baseline"), SimpleNamespace(headers={})

    return SimpleNamespace(api=api, request=request, traces=frozen, effects=effects,
                           conversations=conversations, calls=provider_calls, controls=controls,
                           timing=native_timing, forbidden=forbidden)


def test_native_turn_provider_interval_and_persistence_order(tmp_path, monkeypatch):
    import asyncio
    fixture = _native_lifecycle_fixture(tmp_path, monkeypatch)
    owner, request, response = fixture.request("one")
    result = asyncio.run(fixture.api._execute_agent_chat_turn(owner, request, response))
    trace, = fixture.traces
    root = next(event for event in trace.events if event.name == "agent.chat")
    provider = next(event for event in trace.events if event.name == "provider.direct")
    assistant = next(event for event in trace.events if event.name == "conversation.assistant.persist")
    assert 100 <= provider.attributes["duration_ms"] <= 500
    assert root.status == assistant.status == "SUCCEEDED"
    assert root.attributes["native_end_monotonic_ns"] >= assistant.attributes["native_end_monotonic_ns"]
    assert root.attributes["native_end_monotonic_ns"] < fixture.effects[-1][2]
    assert all(event.parent_event_id == root.event_id for event in trace.events if event is not root)
    stored = fixture.conversations[request.conversation_id]["messages"][-1]["references"]["trace"]
    assert stored["trace_state"] == "pending_finalization" and "trace_sha256" not in stored
    assert result["trace"]["local_state"] == "persisted"
    assert result["conversation"]["messages"][-1]["references"]["trace"] == result["trace"]
    assert response.headers["X-Bago-Trace-Id"] == trace.trace_id
    assert "PRIVATE_MESSAGE" not in str(trace)
    monkeypatch.setattr(fixture.api, "_finalize_native_agent_chat_trace", fixture.forbidden)
    monkeypatch.setattr(fixture.api, "export_local_trace_to_otlp", fixture.forbidden)
    monkeypatch.setattr(fixture.api.provider_runtime, "chat", fixture.forbidden)
    reloaded = asyncio.run(fixture.api.get_conversation(request.conversation_id))
    assert reloaded["messages"][-1]["references"]["trace"] == result["trace"]
    assert stored["trace_state"] == "pending_finalization"


def test_native_turn_authorization_denied_before_provider(tmp_path, monkeypatch):
    import asyncio
    import pytest
    fixture = _native_lifecycle_fixture(tmp_path, monkeypatch)
    fixture.controls["deny"] = True
    args = fixture.request("denied")
    with pytest.raises(fixture.api.HTTPException) as caught:
        asyncio.run(fixture.api._execute_agent_chat_turn(*args))
    assert caught.value.status_code == 422
    assert fixture.calls == []
    assert fixture.conversations[args[1].conversation_id]["messages"] == []
    trace, = fixture.traces
    assert next(event for event in trace.events if event.name == "agent.chat").status == "DENIED"
    assert next(event for event in trace.events if event.name == "agent.authorization").status == "DENIED"


def test_native_turn_append_failure_is_not_success(tmp_path, monkeypatch):
    import asyncio
    import pytest
    fixture = _native_lifecycle_fixture(tmp_path, monkeypatch)
    fixture.controls["append_fail"] = True
    with pytest.raises(fixture.api.HTTPException) as caught:
        asyncio.run(fixture.api._execute_agent_chat_turn(*fixture.request("append")))
    assert caught.value.detail["code"] == "conversation_error"
    trace, = fixture.traces
    assert next(event for event in trace.events if event.name == "agent.chat").status == "FAILED"
    assert next(event for event in trace.events if event.name == "conversation.assistant.persist").status == "FAILED"
    assert "PRIVATE_APPEND_FAILURE" not in str(trace)


def test_native_turn_provider_failure_without_reads_persists_one_trace(tmp_path, monkeypatch):
    import asyncio
    import pytest
    fixture = _native_lifecycle_fixture(tmp_path, monkeypatch)
    fixture.controls["provider_fail"] = True
    owner, request, response = fixture.request("failure")
    with pytest.raises(fixture.api.HTTPException) as caught:
        asyncio.run(fixture.api._execute_agent_chat_turn(owner, request, response))
    assert caught.value.status_code == 502
    assert caught.value.headers["X-Provider-Failure"] == "1"
    assert len(fixture.traces) == 1
    trace = fixture.traces[0]
    assert next(event for event in trace.events if event.name == "agent.chat").status == "FAILED"
    message = fixture.conversations[request.conversation_id]["messages"][-1]
    assert message["role"] == "assistant" and message["content"] == "" and message["status"] == "failed"
    assert message["references"]["read_events"] == []
    assert message["references"]["trace"]["trace_id"] == trace.trace_id
    assert caught.value.detail["trace"]["trace_id"] == trace.trace_id
    assert "PRIVATE_PROVIDER_FAILURE" not in str(trace)
    assert len(list(tmp_path.glob("trace-*.json"))) == 1
    assert len(list(tmp_path.glob("metadata-*.v1.json"))) == 1


def test_native_turn_cancellation_resets_context_without_claiming_worker_stopped(tmp_path, monkeypatch):
    import asyncio
    import threading
    import pytest
    fixture = _native_lifecycle_fixture(tmp_path, monkeypatch)
    entered, release, ended = threading.Event(), threading.Event(), threading.Event()
    def provider(*args):
        entered.set()
        release.wait(3)
        ended.set()
        return "late answer"
    monkeypatch.setattr(fixture.api.provider_runtime, "chat", provider)
    async def exercise():
        task = asyncio.create_task(fixture.api._execute_agent_chat_turn(*fixture.request("cancel")))
        try:
            assert await asyncio.to_thread(entered.wait, 2)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            assert fixture.timing._current.get() is None
            assert not ended.is_set()
            trace, = fixture.traces
            assert next(event for event in trace.events if event.name == "agent.chat").status == "CANCELLED"
            assert next(event for event in trace.events if event.name == "provider.direct").status == "CANCELLED"
        finally:
            release.set()
            await asyncio.to_thread(ended.wait, 2)
    asyncio.run(exercise())
    assert len(fixture.conversations["conversation-cancel"]["messages"]) == 1


def test_native_inspection_selects_latest_without_hiding_old_corruption(tmp_path, monkeypatch):
    import asyncio
    import copy

    fixture = _native_lifecycle_fixture(tmp_path, monkeypatch)
    owner, request, response = fixture.request("inspection-history")
    first = asyncio.run(fixture.api._execute_agent_chat_turn(owner, request, response))
    request.revision = fixture.conversations[request.conversation_id]["revision"]
    latest = asyncio.run(fixture.api._execute_agent_chat_turn(owner, request, response))
    conversation = fixture.conversations[request.conversation_id]
    for index, message in enumerate(conversation["messages"]):
        message["id"] = "message-" + str(index)
    assert first["trace"]["trace_id"] != latest["trace"]["trace_id"]
    assert len(fixture.calls) == len(fixture.traces) == 2
    monkeypatch.setattr(fixture.api.provider_runtime, "chat", fixture.forbidden)
    monkeypatch.setattr(fixture.api, "_finalize_native_agent_chat_trace", fixture.forbidden)
    monkeypatch.setattr(fixture.api, "export_local_trace_to_otlp", fixture.forbidden)
    baseline = fixture.api.inspect_conversation(request.conversation_id)
    selected = baseline["selected"]
    assert selected["trace_id"] == latest["trace"]["trace_id"]
    assert selected["trace"] is not None
    assert selected["sha256"] == latest["trace"]["trace_sha256"]
    assert selected["integrity"] not in {"not_available", "legacy_unverified"}
    old_sidecar = tmp_path / ("metadata-" + first["trace"]["trace_id"] + ".v1.json")
    assert old_sidecar.is_file()
    old_sidecar.write_bytes(b"{}")
    original = copy.deepcopy(conversation)
    before = {path.name: path.read_bytes() for path in tmp_path.iterdir() if path.is_file()}
    reloaded = asyncio.run(fixture.api.get_conversation(request.conversation_id))
    assert reloaded["messages"][-1]["references"]["trace"] == latest["trace"]
    assert reloaded["messages"][1]["references"]["trace"]["trace_state"] == "metadata_failed"
    assert fixture.api.inspect_conversation(request.conversation_id) == baseline
    for selection in ({"trace_id": first["trace"]["trace_id"]},
                      {"execution_id": first["trace"]["execution_id"]}):
        with pytest.raises(fixture.api.HTTPException) as caught:
            fixture.api.inspect_conversation(request.conversation_id, **selection)
        assert caught.value.status_code == 409
        assert caught.value.detail == {"code": "native_trace_evidence_unavailable", "state": "failed"}
    assert conversation == original
    assert {path.name: path.read_bytes() for path in tmp_path.iterdir() if path.is_file()} == before
    assert len(fixture.calls) == len(fixture.traces) == 2


def test_native_inspection_rejects_tampered_metadata(tmp_path, monkeypatch):
    import pytest
    from types import SimpleNamespace
    api, reference, metadata, _, sidecar, _ = _readonly_native_fixture(tmp_path, monkeypatch)
    conversation = {"owner_kind": "agent", "owner_id": "agent-one", "messages": [
        {"role": "assistant", "references": {"trace": reference}}]}
    monkeypatch.setattr(api, "CONVERSATIONS", SimpleNamespace(get=lambda _: conversation))
    sidecar.write_bytes(b"{}")
    with pytest.raises(api.HTTPException) as caught:
        api.inspect_conversation("conversation-one", trace_id=reference["trace_id"])
    assert caught.value.status_code == 409
    assert caught.value.detail == {"code": "native_trace_evidence_unavailable", "state": "failed"}
    sidecar.unlink()
    with pytest.raises(api.HTTPException) as caught:
        api.inspect_conversation("conversation-one", trace_id=reference["trace_id"])
    assert caught.value.detail["state"] == "pending"


def test_native_metadata_historical_namespace_and_conflict(tmp_path, monkeypatch):
    api, reference, metadata, _, current, _ = _readonly_native_fixture(tmp_path, monkeypatch)
    historical = tmp_path / (reference["trace_id"] + ".metadata.v1.json")
    original = current.read_bytes()
    historical.write_bytes(original)
    current.unlink()
    resolve = lambda: api._resolve_native_agent_chat_trace(
        reference, agent_id="agent-one", conversation_id="conversation-one")
    assert resolve() == metadata
    current.write_bytes(original)
    assert resolve() == metadata
    historical.write_bytes(b"{}")
    assert resolve()["trace_state"] == "metadata_failed"
    assert historical.read_bytes() == b"{}"
    assert current.read_bytes() == original


def test_native_compatibility_projection_preserves_intervals_and_safe_metadata(tmp_path, monkeypatch):
    import asyncio
    import re
    fixture = _native_lifecycle_fixture(tmp_path, monkeypatch)
    owner, request, response = fixture.request("compatibility")
    result = asyncio.run(fixture.api._execute_agent_chat_turn(owner, request, response))
    trace, = fixture.traces
    assert re.fullmatch(r"trace-[0-9a-f]{16}", trace.trace_id)
    assert re.fullmatch(r"agent-chat-[0-9a-f]{32}", trace.run_id)
    root = next(event for event in trace.events if event.name == "agent.chat")
    assert root.attributes["agent_id"] == owner
    assert root.attributes["conversation_id"] == request.conversation_id
    assert root.attributes["model_id"] == "model-test"
    assert root.attributes["provider_id"] == "provider-test"
    state = {"root_attributes": {}, "observation": {"read_events": [
        {"decision": "ALLOW", "file_sha256": "a" * 64, "path": "PRIVATE_PATH", "content": "PRIVATE_CONTENT"},
        {"decision": "DENY", "reason_code": "PATH_NOT_AUTHORIZED"}]}}
    enriched = fixture.api._native_chat_compatibility_evidence(trace, state)
    reads = [event for event in enriched.events if event.name == "workspace.read"]
    assert [event.status for event in reads] == ["ALLOW", "DENY"]
    assert reads[0].attributes["file_sha256"] == "a" * 64
    assert all(event.parent_event_id == root.event_id for event in reads)
    assert all(event.attributes["timing_mode"] == "projection" for event in reads)
    assert all("duration_ms" not in event.attributes for event in reads)
    assert all(event.start_time_unix_nano is None and event.end_time_unix_nano is None for event in reads)
    assert "PRIVATE_PATH" not in str(enriched) and "PRIVATE_CONTENT" not in str(enriched)
    assert next(event for event in enriched.events if event.name == "agent.chat") == root
    assert result["trace"]["local_state"] == "persisted"
    assert len(list(tmp_path.glob("trace-*.json"))) == 1
    assert len(list(tmp_path.glob("metadata-*.v1.json"))) == 1


def test_native_turn_concurrent_recorders_do_not_mix(tmp_path, monkeypatch):
    import asyncio
    fixture = _native_lifecycle_fixture(tmp_path, monkeypatch)
    first, second = fixture.request("first"), fixture.request("second")
    async def exercise():
        results = await asyncio.gather(fixture.api._execute_agent_chat_turn(*first),
                                       fixture.api._execute_agent_chat_turn(*second))
        assert fixture.timing._current.get() is None
        return results
    results = asyncio.run(exercise())
    assert len(fixture.traces) == 2
    assert len({trace.trace_id for trace in fixture.traces}) == 2
    assert len({trace.run_id for trace in fixture.traces}) == 2
    assert set(fixture.calls) == {trace.trace_id for trace in fixture.traces}
    for args, result in zip((first, second), results):
        reference = fixture.conversations[args[1].conversation_id]["messages"][-1]["references"]["trace"]
        assert reference["agent_id"] == args[0]
        assert reference["conversation_id"] == args[1].conversation_id
        assert result["trace"]["trace_id"] == reference["trace_id"]
        trace = next(trace for trace in fixture.traces if trace.trace_id == reference["trace_id"])
        assert all(event.trace_id == trace.trace_id for event in trace.events)
        assert next(event for event in trace.events if event.name == "agent.chat").status == "SUCCEEDED"


def test_local_failure_does_not_export(evidence, monkeypatch):
    evidence.write_bytes(b"not a directory")

    def forbidden(*args, **kwargs):
        pytest.fail("unpersisted trace must not export")

    monkeypatch.setattr(server, "export_local_trace_to_otlp", forbidden)
    result = finalize(frozen())
    assert result["local_state"] == "failed"
    assert result["export_state"] == "not_attempted"
    assert result["sidecar_state"] == "not_attempted"


def test_export_exception_is_uncertain_and_redacted(evidence, monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("secret-provider-body")

    monkeypatch.setattr(server, "export_local_trace_to_otlp", fail)
    result = finalize(frozen())
    assert result["export_state"] == "uncertain"
    assert result["trace_state"] == "export_failed"
    assert result["local_state"] == result["sidecar_state"] == "persisted"
    assert "secret-provider-body" not in json.dumps(result)
    assert "secret-provider-body" not in next(evidence.glob("metadata-*.v1.json")).read_text()
    assert_digest(result)


def test_negative_receipt_is_not_success(evidence, monkeypatch):
    monkeypatch.setattr(server, "export_local_trace_to_otlp", lambda *a, **k: SimpleNamespace(exported=False))
    result = finalize(frozen())
    assert result["export_state"] == "not_confirmed"
    assert result["trace_state"] == "export_failed"


def test_sidecar_failure_preserves_export_result(evidence, monkeypatch):
    trace = frozen()
    evidence.mkdir()
    import os

    original_link = os.link

    def fail_sidecar(source, target, *args, **kwargs):
        if Path(target).name.startswith("metadata-") and Path(target).name.endswith(".v1.json"):
            raise OSError("secret-sidecar-error")
        return original_link(source, target, *args, **kwargs)

    monkeypatch.setattr(os, "link", fail_sidecar)
    monkeypatch.setattr(server, "export_local_trace_to_otlp", lambda *a, **k: SimpleNamespace(exported=True))
    result = finalize(trace)
    assert result["local_state"] == "persisted"
    assert result["export_state"] == "exported"
    assert result["sidecar_state"] == "failed"
    assert result["trace_state"] == "metadata_failed"
    assert "metadata_sha256" not in result
    assert (evidence / (trace.trace_id + ".json")).exists()


def test_reuse_identical_bytes_without_overwrite(evidence, monkeypatch):
    monkeypatch.delenv("BAGO_OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    trace = frozen()
    first = finalize(trace)
    target = evidence / (trace.trace_id + ".json")
    inode = target.stat().st_ino
    second = finalize(trace)
    assert second == first
    assert target.stat().st_ino == inode
    assert second["export_state"] == "not_configured"


def test_concurrent_ids_do_not_mix(evidence, monkeypatch):
    import threading

    barrier = threading.Barrier(2)

    def export(trace, **kwargs):
        barrier.wait(timeout=10)
        assert (evidence / (trace.trace_id + ".json")).read_bytes() == (trace.to_json() + "\n").encode("utf-8")
        return SimpleNamespace(exported=True)

    monkeypatch.setattr(server, "export_local_trace_to_otlp", export)

    async def run():
        return await asyncio.gather(
            asyncio.to_thread(finalize, frozen(1), "conversation-1"),
            asyncio.to_thread(finalize, frozen(2), "conversation-2"),
        )

    results = asyncio.run(run())
    assert len({item["trace_id"] for item in results}) == 2
    assert len({item["execution_id"] for item in results}) == 2
    for index, result in enumerate(results, 1):
        assert result["conversation_id"] == "conversation-" + str(index)
        assert result["trace_state"] == "exported"
        persisted = json.loads((evidence / ("metadata-" + result["trace_id"] + ".v1.json")).read_text())
        assert persisted == result
        assert_digest(result)
    assert not list(evidence.glob(".native-*"))


def test_local_only_cache_ignores_new_endpoint(evidence, monkeypatch):
    monkeypatch.delenv("BAGO_OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    trace = frozen()
    first = finalize(trace)
    before = {path.name: path.read_bytes() for path in evidence.iterdir()}
    monkeypatch.setenv("BAGO_OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector.invalid/v1/traces")

    def forbidden(*args, **kwargs):
        pytest.fail("historical local-only evidence must not export")

    monkeypatch.setattr(server, "export_local_trace_to_otlp", forbidden)
    assert finalize(trace) == first
    assert first["trace_state"] == "local_only"
    assert {path.name: path.read_bytes() for path in evidence.iterdir()} == before
    assert not (evidence / "export-ledger").exists()


def test_exported_cache_preserves_jaeger_receipt_without_redispatch(evidence, monkeypatch):
    jaeger_id = "e0838bb95431bc4aff9aa78fcc7c5012"
    calls = []

    def export(trace, **kwargs):
        calls.append(trace.trace_id)
        return SimpleNamespace(exported=True, jaeger_trace_id=jaeger_id)

    monkeypatch.setattr(server, "export_local_trace_to_otlp", export)
    monkeypatch.setenv("BAGO_JAEGER_UI_URL", "http://jaeger.invalid:16686/ui/")
    trace = frozen()
    first = finalize(trace)
    assert first["jaeger_trace_id"] == jaeger_id
    assert first["jaeger_url"] == "http://jaeger.invalid:16686/ui/trace/" + jaeger_id
    assert_digest(first)
    before = {path.name: path.read_bytes() for path in evidence.iterdir()}
    monkeypatch.setenv("BAGO_JAEGER_UI_URL", "http://changed.invalid")
    monkeypatch.setenv("BAGO_OTEL_EXPORTER_OTLP_ENDPOINT", "http://changed.invalid/v1/traces")
    assert finalize(trace) == first
    assert calls == [trace.trace_id]
    assert {path.name: path.read_bytes() for path in evidence.iterdir()} == before


def resign_metadata(metadata):
    metadata.pop("metadata_sha256", None)
    canonical = json.dumps(metadata, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    metadata["metadata_sha256"] = hashlib.sha256(canonical).hexdigest()
    return json.dumps(metadata, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii") + b"\n"


@pytest.mark.parametrize("damage", [
    "digest", "malformed", "schema", "version", "owner", "conversation",
    "trace_id", "execution_id", "trace_hash", "phase", "missing_trace",
    "changed_trace", "directory", "jaeger_id", "jaeger_url",
])
def test_invalid_sidecar_fails_closed_without_effects(evidence, monkeypatch, damage):
    monkeypatch.delenv("BAGO_OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    trace = frozen()
    first = finalize(trace)
    sidecar = evidence / ("metadata-" + trace.trace_id + ".v1.json")
    target = evidence / (trace.trace_id + ".json")
    stored = dict(first)
    if damage == "digest":
        stored["conversation_id"] = "tampered-secret"
        sidecar.write_text(json.dumps(stored), encoding="utf-8")
    elif damage == "malformed":
        sidecar.write_bytes(b"not-json-secret")
    elif damage == "missing_trace":
        target.unlink()
    elif damage == "changed_trace":
        target.write_bytes(b"different-secret-evidence")
    elif damage == "directory":
        sidecar.unlink()
        sidecar.mkdir()
    else:
        changes = {
            "schema": {"extra": "secret"}, "version": {"version": 2},
            "owner": {"agent_id": "another-agent"},
            "conversation": {"conversation_id": "another-conversation"},
            "trace_id": {"trace_id": frozen(2).trace_id},
            "execution_id": {"execution_id": frozen(2).run_id},
            "trace_hash": {"trace_sha256": "0" * 64},
            "phase": {"export_state": "exported", "trace_state": "local_only"},
            "jaeger_id": {"jaeger_trace_id": "0" * 32},
            "jaeger_url": {"jaeger_url": "javascript:secret"},
        }
        stored.update(changes[damage])
        sidecar.write_bytes(resign_metadata(stored))
    before = {path.name: path.read_bytes() if path.is_file() else None for path in evidence.iterdir()}

    def forbidden(*args, **kwargs):
        pytest.fail("invalid historical evidence must not reach export")

    monkeypatch.setattr(server, "export_local_trace_to_otlp", forbidden)
    monkeypatch.setenv("BAGO_OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector.invalid/v1/traces")
    result = finalize(trace)
    assert result["trace_state"] == "metadata_failed"
    assert result["export_state"] == "not_attempted"
    assert result["sidecar_state"] == "invalid"
    assert "metadata_sha256" not in result
    assert "secret" not in json.dumps(result)
    assert {path.name: path.read_bytes() if path.is_file() else None for path in evidence.iterdir()} == before
    assert not (evidence / "export-ledger").exists()


@pytest.mark.parametrize("field,value", [("agent_id", "agent-2"), ("conversation_id", "conversation-2")])
def test_cached_receipt_cannot_be_reused_by_other_owner(evidence, monkeypatch, field, value):
    monkeypatch.delenv("BAGO_OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    trace = frozen()
    finalize(trace)
    before = {path.name: path.read_bytes() for path in evidence.iterdir()}

    def forbidden(*args, **kwargs):
        pytest.fail("owner mismatch must not export")

    monkeypatch.setattr(server, "export_local_trace_to_otlp", forbidden)
    kwargs = {"agent_id": "agent-1", "conversation_id": "conversation-1"}
    kwargs[field] = value
    result = server._finalize_native_agent_chat_trace(trace, **kwargs)
    assert result["trace_state"] == "metadata_failed"
    assert result["export_state"] == "not_attempted"
    assert {path.name: path.read_bytes() for path in evidence.iterdir()} == before


@pytest.mark.parametrize("exported,jaeger_id,base,expected_id,expected_url", [
    (True, "e0838bb95431bc4aff9aa78fcc7c5012", "http://jaeger.invalid", True, True),
    (False, "e0838bb95431bc4aff9aa78fcc7c5012", "http://jaeger.invalid", False, False),
    (True, "0" * 32, "http://jaeger.invalid", False, False),
    (True, "invented/../secret", "http://jaeger.invalid", False, False),
    (True, "e0838bb95431bc4aff9aa78fcc7c5012", "javascript:secret", True, False),
    (True, "e0838bb95431bc4aff9aa78fcc7c5012", "http://user:secret@jaeger.invalid", True, False),
])
def test_only_valid_confirmed_jaeger_receipts_are_published(evidence, monkeypatch, exported, jaeger_id, base, expected_id, expected_url):
    monkeypatch.setenv("BAGO_JAEGER_UI_URL", base)
    monkeypatch.setattr(server, "export_local_trace_to_otlp", lambda *a, **k: SimpleNamespace(exported=exported, jaeger_trace_id=jaeger_id))
    result = finalize(frozen())
    assert ("jaeger_trace_id" in result) is expected_id
    assert ("jaeger_url" in result) is expected_url
    if expected_id:
        assert result["jaeger_trace_id"] == jaeger_id
    if expected_url:
        assert result["jaeger_url"] == base + "/trace/" + jaeger_id
    assert_digest(result)


def test_native_provider_roundtrips_are_worker_siblings(tmp_path, monkeypatch):
    import asyncio
    import threading
    import time
    from src.api import server as api
    from src.observability.native_timing import NativeTimingRecorder, _current

    recorder = NativeTimingRecorder()
    main_thread = threading.get_ident()
    observed = []
    messages = [{"role": "user", "content": "private"}]
    observation = {"sources": [], "read_events": []}
    monkeypatch.setattr(api, "MAX_TOOL_ROUNDS", 1)
    monkeypatch.setattr(api, "_web_instructions", lambda permit: "")

    def turn(provider, model, received, **kwargs):
        assert (provider, model) == ("provider-test", "model-test")
        assert received is messages
        assert kwargs == {"tools": []}
        assert threading.get_ident() != main_thread
        binding = _current.get()
        assert binding[0] is recorder
        start = time.monotonic_ns()
        time.sleep(0.12)
        observed.append((binding[1], start, time.monotonic_ns()))
        return {"tool_calls": [{"function": {"name": "unavailable", "arguments": {}}}]}

    def final(provider, model, received):
        assert received is messages
        assert threading.get_ident() != main_thread
        binding = _current.get()
        assert binding[0] is recorder
        start = time.monotonic_ns()
        time.sleep(0.12)
        observed.append((binding[1], start, time.monotonic_ns()))
        return " final answer "

    monkeypatch.setattr(api.provider_runtime, "chat_turn", turn)
    monkeypatch.setattr(api.provider_runtime, "chat", final)

    async def run():
        previous = _current.get()
        with recorder.span("agent.chat") as root:
            result = await api._chat_with_workspace_read(
                "model-test", messages, [], workspace_root=tmp_path,
                provider_id="provider-test", turn_observation=observation, recorder=recorder)
            assert _current.get() == (recorder, root.event_id)
            assert result == (" final answer ", [], [], None)
            assert result[1] is observation["sources"]
            assert result[2] is observation["read_events"]
            root.finish()
        assert _current.get() == previous

    asyncio.run(run())
    events = recorder.to_local_trace().events
    root = next(event for event in events if event.name == "agent.chat")
    children = [event for event in events if event is not root]
    assert [event.name for event in children] == ["provider.chat_turn.roundtrip", "provider.final.roundtrip"]
    assert [event.attributes["attempt"] for event in children] == [1, 2]
    for event, (event_id, start, end) in zip(children, observed):
        assert event.event_id == event_id
        assert event.parent_event_id == root.event_id
        assert event.status == "SUCCEEDED"
        assert event.attributes["timing_source"] == "native"
        assert event.attributes["interval_complete"] is True
        assert event.attributes["native_start_monotonic_ns"] <= start < end <= event.attributes["native_end_monotonic_ns"]
        assert event.attributes["duration_ns"] >= 120_000_000


def test_native_provider_worker_exception_is_failed(tmp_path, monkeypatch):
    import asyncio
    import time
    import pytest
    from src.api import server as api
    from src.observability.native_timing import NativeTimingRecorder, _current

    recorder = NativeTimingRecorder()
    failure = RuntimeError("provider failure")
    monkeypatch.setattr(api, "_web_instructions", lambda permit: "")

    def provider(*args, **kwargs):
        assert _current.get()[0] is recorder
        time.sleep(0.12)
        raise failure

    monkeypatch.setattr(api.provider_runtime, "chat_turn", provider)

    async def run():
        previous = _current.get()
        with recorder.span("agent.chat") as root:
            with pytest.raises(RuntimeError) as caught:
                await api._chat_with_workspace_read("model", [], [], workspace_root=tmp_path, recorder=recorder)
            assert caught.value is failure
            assert _current.get() == (recorder, root.event_id)
            root.finish(status="FAILED")
        assert _current.get() == previous

    asyncio.run(run())
    event = next(event for event in recorder.to_local_trace().events if event.name == "provider.chat_turn.roundtrip")
    assert event.status == "FAILED"
    assert event.attributes["interval_complete"] is True
    assert event.attributes["duration_ns"] >= 120_000_000


def test_native_provider_none_preserves_legacy_calls(tmp_path, monkeypatch):
    import asyncio
    import copy
    from src.api import server as api
    from src.observability.native_timing import _current

    calls = []
    monkeypatch.setattr(api, "MAX_TOOL_ROUNDS", 1)
    monkeypatch.setattr(api, "_web_instructions", lambda permit: "instructions")

    def turn(*args, **kwargs):
        assert _current.get() is None
        calls.append((copy.deepcopy(args), copy.deepcopy(kwargs)))
        return {"tool_calls": [{"function": {"name": "unavailable", "arguments": {}}}]}

    def final(*args, **kwargs):
        assert _current.get() is None
        calls.append((copy.deepcopy(args), copy.deepcopy(kwargs)))
        return " unchanged "

    def forbidden(*args, **kwargs):
        raise AssertionError("native wrapper must not run without recorder")

    monkeypatch.setattr(api.provider_runtime, "chat_turn", turn)
    monkeypatch.setattr(api.provider_runtime, "chat", final)
    monkeypatch.setattr(api, "_native_provider_roundtrip", forbidden)

    async def run():
        snapshots = []
        for options in ({}, {"recorder": None}):
            messages = [{"role": "user", "content": "original"}]
            observation = {"sources": [], "read_events": []}
            result = await api._chat_with_workspace_read(
                "model", messages, [], workspace_root=tmp_path, turn_observation=observation, **options)
            assert result == (" unchanged ", [], [], None)
            assert result[1] is observation["sources"]
            assert result[2] is observation["read_events"]
            snapshots.append((result, messages))
        assert snapshots[0] == snapshots[1]

    asyncio.run(run())
    assert len(calls) == 4
    assert calls[:2] == calls[2:]
    assert calls[0][1] == {"tools": []}
    assert calls[1][1] == {}


def test_native_provider_concurrent_loops_do_not_mix(tmp_path, monkeypatch):
    import asyncio
    import threading
    import time
    from src.api import server as api
    from src.observability.native_timing import NativeTimingRecorder, _current

    barrier = threading.Barrier(2, timeout=5)
    recorders = {model: NativeTimingRecorder(run_id=model) for model in ("model-one", "model-two")}
    bindings = {}
    monkeypatch.setattr(api, "_web_instructions", lambda permit: "")

    def provider(provider_id, model, messages, **kwargs):
        binding = _current.get()
        assert binding[0] is recorders[model]
        barrier.wait()
        time.sleep(0.12)
        assert _current.get() == binding
        bindings[model] = binding[1]
        return {"content": model}

    monkeypatch.setattr(api.provider_runtime, "chat_turn", provider)

    async def one(model, recorder):
        previous = _current.get()
        with recorder.span("agent.chat") as root:
            result = await api._chat_with_workspace_read(model, [], [], workspace_root=tmp_path, recorder=recorder)
            assert result == (model, [], [], None)
            assert _current.get() == (recorder, root.event_id)
            root.finish()
        assert _current.get() == previous

    async def run():
        await asyncio.gather(*(one(model, recorder) for model, recorder in recorders.items()))
        assert _current.get() is None

    asyncio.run(run())
    all_ids = set()
    for model, recorder in recorders.items():
        events = recorder.to_local_trace().events
        assert len(events) == 2
        root, child = events
        assert child.event_id == bindings[model]
        assert child.parent_event_id == root.event_id
        assert child.status == "SUCCEEDED"
        assert child.attributes["duration_ns"] >= 120_000_000
        ids = {event.event_id for event in events}
        assert not all_ids.intersection(ids)
        all_ids.update(ids)


def test_native_provider_cancel_does_not_claim_worker_stopped(tmp_path, monkeypatch):
    import asyncio
    import threading
    import pytest
    from src.api import server as api
    from src.observability.native_timing import NativeTimingRecorder

    recorder = NativeTimingRecorder()
    started = threading.Event()
    release = threading.Event()
    finished = threading.Event()
    monkeypatch.setattr(api, "_web_instructions", lambda permit: "")

    def provider(*args, **kwargs):
        started.set()
        try:
            assert release.wait(5)
            return {"content": "late answer"}
        finally:
            finished.set()

    monkeypatch.setattr(api.provider_runtime, "chat_turn", provider)

    async def run():
        try:
            with recorder.span("agent.chat") as root:
                task = asyncio.create_task(api._chat_with_workspace_read(
                    "model", [], [], workspace_root=tmp_path, recorder=recorder))
                for _ in range(500):
                    if started.is_set():
                        break
                    await asyncio.sleep(0.01)
                assert started.is_set()
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task
                assert not finished.is_set()
                root.finish(status="CANCELLED")
            frozen = recorder.to_local_trace()
            child = next(event for event in frozen.events if event.name == "provider.chat_turn.roundtrip")
            assert child.status == "INCOMPLETE"
            assert child.attributes["interval_complete"] is False
            parent = next(event for event in frozen.events if event.name == "agent.chat")
            assert parent.attributes["child_coverage_complete"] is False
        finally:
            release.set()
        return frozen

    frozen = asyncio.run(run())
    assert finished.is_set()
    child = next(event for event in recorder.to_local_trace().events if event.name == "provider.chat_turn.roundtrip")
    assert child.status == "SUCCEEDED"
    assert child.attributes["interval_complete"] is True
    parent = next(event for event in recorder.to_local_trace().events if event.name == "agent.chat")
    assert parent.attributes["child_outside_interval"] is True
    assert next(event for event in frozen.events if event.name == "provider.chat_turn.roundtrip").status == "INCOMPLETE"
