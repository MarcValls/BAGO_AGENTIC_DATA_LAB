"""Real local operations exercising the opt-in native timing foundation."""

import asyncio
import json
from pathlib import Path
import sys
import time

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from observability.local_trace import LocalTrace, TraceEvent, TraceKind
from observability.native_timing import NativeTimingRecorder


def _events(recorder):
    return {event.name: event for event in recorder.to_local_trace().events}


def _duration(event):
    return event.attributes["duration_ns"]


def test_real_wait_120ms_and_native_clocks():
    recorder = NativeTimingRecorder()
    before_unix, before_mono = time.time_ns(), time.monotonic_ns()
    with recorder.span("controlled.wait", TraceKind.WORKFLOW) as span:
        time.sleep(0.120)
        span.finish()
    after_mono, after_unix = time.monotonic_ns(), time.time_ns()
    trace = recorder.to_local_trace()
    assert isinstance(trace, LocalTrace)
    event, = trace.events
    assert isinstance(event, TraceEvent)
    assert event.kind is TraceKind.WORKFLOW
    assert event.status == "SUCCEEDED"
    assert 100 <= event.attributes["duration_ms"] <= 500
    assert before_unix <= event.start_time_unix_nano <= event.end_time_unix_nano <= after_unix
    a = event.attributes
    assert before_mono <= a["native_start_monotonic_ns"] <= a["native_end_monotonic_ns"] <= after_mono
    assert _duration(event) == a["native_end_monotonic_ns"] - a["native_start_monotonic_ns"]
    assert a["uninstrumented_ns"] == _duration(event)
    assert a["immediate_children_union_ns"] == 0
    assert recorder.to_local_trace().to_dict() == trace.to_dict()


def test_overlapping_children_union_not_sum_and_sequential_siblings():
    async def exercise():
        recorder = NativeTimingRecorder()
        ready = [asyncio.Event(), asyncio.Event()]
        release = asyncio.Event()

        async def child(index):
            with recorder.span("parallel." + str(index)) as span:
                ready[index].set()
                await release.wait()
                span.finish()

        with recorder.span("parallel.root") as root:
            tasks = [asyncio.create_task(child(i)) for i in range(2)]
            await asyncio.gather(*(item.wait() for item in ready))
            await asyncio.sleep(0.060)
            release.set()
            await asyncio.gather(*tasks)
            root.finish()
        with recorder.span("sequential.root") as root:
            for i in range(2):
                with recorder.span("sequential." + str(i)) as span:
                    await asyncio.sleep(0.030)
                    span.finish()
            root.finish()
        return recorder

    events = _events(asyncio.run(exercise()))
    parallel = events["parallel.root"]
    children = [events["parallel.0"], events["parallel.1"]]
    assert all(child.parent_event_id == parallel.event_id for child in children)
    starts = [child.attributes["native_start_monotonic_ns"] for child in children]
    ends = [child.attributes["native_end_monotonic_ns"] for child in children]
    assert max(starts) < min(ends)
    union = parallel.attributes["immediate_children_union_ns"]
    assert union == max(ends) - min(starts)
    assert union < sum(map(_duration, children))
    assert union >= max(map(_duration, children))
    sequential = events["sequential.root"]
    first, second = events["sequential.0"], events["sequential.1"]
    assert first.parent_event_id == second.parent_event_id == sequential.event_id
    assert first.attributes["native_end_monotonic_ns"] <= second.attributes["native_start_monotonic_ns"]
    assert sequential.attributes["immediate_children_union_ns"] == _duration(first) + _duration(second)
    for root in (parallel, sequential):
        assert root.parent_event_id is None
        assert root.attributes["child_coverage_complete"] is True
        assert root.attributes["child_outside_interval"] is False
        assert root.attributes["uninstrumented_ns"] == _duration(root) - root.attributes["immediate_children_union_ns"]


def test_only_immediate_children_count_toward_coverage():
    recorder = NativeTimingRecorder()
    with recorder.span("root") as root:
        with recorder.span("child") as child:
            with recorder.span("grandchild") as grandchild:
                time.sleep(0.005)
                grandchild.finish()
            child.finish()
        root.finish()
    events = _events(recorder)
    assert events["grandchild"].parent_event_id == events["child"].event_id
    assert events["root"].attributes["immediate_children_union_ns"] == _duration(events["child"])


def test_to_thread_inherits_parent_and_resets_worker_context():
    async def exercise():
        recorder = NativeTimingRecorder()

        def worker():
            with recorder.span("thread.child") as child:
                time.sleep(0.005)
                child.finish()
            with recorder.span("thread.sibling") as sibling:
                sibling.finish()

        with recorder.span("root") as root:
            await asyncio.to_thread(worker)
            with recorder.span("task.sibling") as sibling:
                sibling.finish()
            root.finish()
        await asyncio.to_thread(lambda: run_detached(recorder))
        return recorder

    def run_detached(recorder):
        with recorder.span("thread.detached") as span:
            span.finish()

    events = _events(asyncio.run(exercise()))
    for name in ("thread.child", "thread.sibling", "task.sibling"):
        assert events[name].parent_event_id == events["root"].event_id
    assert events["thread.detached"].parent_event_id is None


def test_two_concurrent_recorders_and_nested_context_reset():
    async def exercise():
        recorders = [NativeTimingRecorder(), NativeTimingRecorder()]
        ready = [asyncio.Event(), asyncio.Event()]

        async def chat(index):
            recorder = recorders[index]
            with recorder.span("chat.root") as root:
                ready[index].set()
                await ready[1 - index].wait()
                with recorder.span("chat.child") as child:
                    await asyncio.sleep(0.005)
                    child.finish()
                root.finish()
            with recorder.span("chat.detached") as detached:
                detached.finish()

        await asyncio.gather(chat(0), chat(1))
        outer, inner = NativeTimingRecorder(), NativeTimingRecorder()
        with outer.span("outer") as root:
            with inner.span("inner") as nested:
                nested.finish()
            with outer.span("restored") as child:
                child.finish()
            root.finish()
        return recorders, outer, inner

    recorders, outer, inner = asyncio.run(exercise())
    traces = [recorder.to_local_trace() for recorder in recorders]
    assert traces[0].trace_id != traces[1].trace_id
    assert traces[0].run_id != traces[1].run_id
    assert not ({e.event_id for e in traces[0].events} & {e.event_id for e in traces[1].events})
    for recorder, trace in zip(recorders, traces):
        events = _events(recorder)
        assert len(events) == 3
        assert all(event.trace_id == trace.trace_id for event in trace.events)
        assert events["chat.child"].parent_event_id == events["chat.root"].event_id
        assert events["chat.detached"].parent_event_id is None
    assert _events(inner)["inner"].parent_event_id is None
    assert _events(outer)["restored"].parent_event_id == _events(outer)["outer"].event_id


def test_error_overrides_success_and_sensitive_attributes_are_dropped():
    recorder = NativeTimingRecorder()
    canary = "CANARY-private-prompt-token-8741"
    attributes = {
        "prompt": canary, "text": canary, "secret": canary,
        "authorization": canary, canary: 1, "attempt": 2,
        "item_count": True, "byte_count": canary, "retry": False,
        "cache_hit": canary, "denied": True, "duration_ns": canary,
        "native_start_unix_ns": canary,
    }
    with pytest.raises(ValueError, match=canary):
        with recorder.span("failure", attributes=attributes) as span:
            span.finish()
            raise ValueError(canary)
    with recorder.span("after.failure") as span:
        span.finish("DENIED")
    trace = recorder.to_local_trace()
    events = _events(recorder)
    assert events["failure"].status == "FAILED"
    assert events["after.failure"].status == "DENIED"
    assert events["after.failure"].parent_event_id is None
    safe = events["failure"].attributes
    assert safe["attempt"] == 2 and safe["retry"] is False and safe["denied"] is True
    assert all(key not in safe for key in ("prompt", "text", "secret", "authorization", "item_count", "byte_count", "cache_hit"))
    assert canary not in trace.to_json()
    assert canary not in json.dumps(trace.to_dict())


def test_real_task_cancellation_and_incomplete_scopes():
    async def exercise():
        recorder = NativeTimingRecorder()
        started = asyncio.Event()
        never = asyncio.Event()

        async def operation():
            with recorder.span("cancelled") as span:
                span.finish()
                started.set()
                await never.wait()

        task = asyncio.create_task(operation())
        await started.wait()
        live, = recorder.to_local_trace().events
        assert live.status == "INCOMPLETE"
        assert live.start_time_unix_nano is None and live.end_time_unix_nano is None
        assert live.attributes["interval_complete"] is False
        assert "duration_ns" not in live.attributes
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        with recorder.span("unfinished"):
            await asyncio.sleep(0)
        with recorder.span("after.cancel") as span:
            span.finish()
        return recorder

    events = _events(asyncio.run(exercise()))
    assert events["cancelled"].status == "CANCELLED"
    assert events["cancelled"].attributes["interval_complete"] is True
    assert events["unfinished"].status == "INCOMPLETE"
    assert events["unfinished"].attributes["interval_complete"] is True
    assert events["after.cancel"].parent_event_id is None


def test_child_outliving_parent_does_not_invent_coverage():
    async def exercise():
        recorder = NativeTimingRecorder()
        started, release = asyncio.Event(), asyncio.Event()

        async def child():
            with recorder.span("late.child") as span:
                started.set()
                await release.wait()
                span.finish()

        with recorder.span("root") as root:
            task = asyncio.create_task(child())
            await started.wait()
            root.finish()
        interim = _events(recorder)["root"]
        assert interim.attributes["child_coverage_complete"] is False
        assert "uninstrumented_ns" not in interim.attributes
        release.set()
        await task
        return recorder

    events = _events(asyncio.run(exercise()))
    root, child = events["root"], events["late.child"]
    assert child.parent_event_id == root.event_id
    assert root.attributes["child_outside_interval"] is True
    clipped = root.attributes["native_end_monotonic_ns"] - child.attributes["native_start_monotonic_ns"]
    assert root.attributes["immediate_children_union_ns"] == clipped
    assert root.attributes["uninstrumented_ns"] >= 0


def test_scope_lifecycle_and_foreign_task_cannot_finish_parent():
    async def exercise():
        recorder = NativeTimingRecorder()
        scope = recorder.span("root")
        with pytest.raises(RuntimeError):
            scope.finish()
        with scope:
            async def foreign():
                with pytest.raises(RuntimeError, match="original causal context"):
                    scope.finish()
                with pytest.raises(RuntimeError, match="original causal context"):
                    scope.__exit__(None, None, None)
            await asyncio.create_task(foreign())
            with pytest.raises(ValueError):
                scope.finish("UNKNOWN")
            scope.finish()
            with pytest.raises(RuntimeError, match="already declared"):
                scope.finish()
        with pytest.raises(RuntimeError):
            scope.finish()
        with pytest.raises(RuntimeError, match="single-use"):
            scope.__enter__()
        return recorder

    event, = asyncio.run(exercise()).to_local_trace().events
    assert event.status == "SUCCEEDED"
