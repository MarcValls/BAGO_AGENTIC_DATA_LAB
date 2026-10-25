"""Opt-in native intervals; no exporter or historical trace mutation."""

from __future__ import annotations

import asyncio
import re
import threading
import time
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from typing import Any, Mapping
from uuid import uuid4

from .local_trace import LocalTrace, TraceEvent, TraceKind


# Tasks inherit immutable causal bindings, never a shared mutable stack.
_current: ContextVar[tuple[NativeTimingRecorder, str] | None] = ContextVar(
    "native_timing_parent", default=None
)
_LABEL = re.compile(r"[a-z][a-z0-9_.-]{0,79}\Z")
_COUNTERS = frozenset({"attempt", "item_count", "byte_count"})
_FLAGS = frozenset({"retry", "cache_hit", "denied"})
_OUTCOMES = frozenset({"SUCCEEDED", "FAILED", "DENIED", "CANCELLED"})


def _owner() -> tuple[int, object]:
    try:
        task = asyncio.current_task()
    except RuntimeError:  # No running event loop in synchronous callers/threads.
        task = None
    return threading.get_ident(), task


def _safe_attributes(attributes: Mapping[str, Any] | None) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in (attributes or {}).items():
        if key in _COUNTERS and type(value) is int and 0 <= value <= 2**63 - 1:
            result[key] = value
        elif key in _FLAGS and type(value) is bool:
            result[key] = value
    return result


def _union_ns(intervals: list[tuple[int, int]]) -> int:
    total = 0
    boundary: int | None = None
    for start, end in sorted(intervals):
        if boundary is None or start > boundary:
            total += end - start
            boundary = end
        elif end > boundary:
            total += end - boundary
            boundary = end
    return total


@dataclass
class _Interval:
    event_id: str
    sequence: int
    name: str
    kind: TraceKind
    parent_id: str | None
    start_unix_ns: int
    start_mono_ns: int
    attributes: dict[str, Any] = field(default_factory=dict)
    end_unix_ns: int | None = None
    end_mono_ns: int | None = None
    status: str = "INCOMPLETE"


class NativeTimingRecorder:
    """One recorder per turn, with explicit outcomes and native intervals.

    Call span.finish() only after observing an operation's result. Ordinary
    scope exit is not proof of success. Names must be static operation labels,
    never user input. No recording, transport or integration happens on import.
    """

    def __init__(self, run_id: str | None = None) -> None:
        if run_id is not None and (not isinstance(run_id, str) or not run_id.strip()):
            raise ValueError("run_id must be a nonempty string")
        self.run_id = run_id if run_id is not None else uuid4().hex
        self.trace_id = uuid4().hex
        self._lock = threading.RLock()
        self._intervals: dict[str, _Interval] = {}

    def span(
        self,
        name: str,
        kind: TraceKind = TraceKind.EXECUTION,
        *,
        attributes: Mapping[str, Any] | None = None,
    ) -> NativeSpan:
        """Create a single-use scope; timing starts only on entry."""
        if not isinstance(name, str) or not _LABEL.fullmatch(name):
            raise ValueError("span name must be a static lowercase operation label")
        return NativeSpan(self, name, TraceKind(kind), _safe_attributes(attributes))

    def to_local_trace(self) -> LocalTrace:
        """Snapshot without closing scopes or inventing endpoint timestamps.

        Durations/coverage use monotonic time. Raw Unix endpoints are retained;
        regressed wall clocks are flagged and omitted from TraceEvent's ordered
        timestamp pair. Gaps are uninstrumented time, not attributed work.
        Coverage is clipped to the parent, and late children are explicit.
        """
        with self._lock:
            events = []
            for interval in self._intervals.values():
                attributes = dict(interval.attributes)
                attributes.update({
                    "timing_source": "native",
                    "native_start_unix_ns": interval.start_unix_ns,
                    "native_start_monotonic_ns": interval.start_mono_ns,
                    "interval_complete": interval.end_mono_ns is not None,
                })
                start = end = None
                if interval.end_mono_ns is not None:
                    end_mono = interval.end_mono_ns
                    end_unix = interval.end_unix_ns
                    assert end_unix is not None
                    duration = end_mono - interval.start_mono_ns
                    attributes.update({
                        "duration_ns": duration,
                        "duration_ms": duration / 1_000_000,
                        "native_end_unix_ns": end_unix,
                        "native_end_monotonic_ns": end_mono,
                    })
                    if end_unix >= interval.start_unix_ns:
                        start, end = interval.start_unix_ns, end_unix
                    else:
                        attributes["wall_clock_regressed"] = True
                    children = [child for child in self._intervals.values()
                                if child.parent_id == interval.event_id]
                    complete = all(child.end_mono_ns is not None for child in children)
                    attributes["child_coverage_complete"] = complete
                    attributes["child_outside_interval"] = any(
                        child.start_mono_ns > end_mono
                        or (child.end_mono_ns is not None and child.end_mono_ns > end_mono)
                        for child in children
                    )
                    if complete:
                        windows = []
                        for child in children:
                            assert child.end_mono_ns is not None
                            a = max(interval.start_mono_ns, child.start_mono_ns)
                            b = min(end_mono, child.end_mono_ns)
                            if b > a:
                                windows.append((a, b))
                        covered = _union_ns(windows)
                        attributes["immediate_children_union_ns"] = covered
                        attributes["uninstrumented_ns"] = duration - covered
                events.append(TraceEvent(
                    event_id=interval.event_id,
                    trace_id=self.trace_id,
                    sequence=interval.sequence,
                    name=interval.name,
                    kind=interval.kind,
                    status=interval.status,
                    parent_event_id=interval.parent_id,
                    attributes=attributes,
                    start_time_unix_nano=start,
                    end_time_unix_nano=end,
                ))
            return LocalTrace(self.trace_id, self.run_id, tuple(events))


class NativeSpan:
    """Synchronous scope usable around awaited operations and in to_thread."""

    def __init__(
        self, recorder: NativeTimingRecorder, name: str,
        kind: TraceKind, attributes: dict[str, Any],
    ) -> None:
        self._recorder = recorder
        self._name = name
        self._kind = kind
        self._attributes = attributes
        self._token: Token | None = None
        self._interval: _Interval | None = None
        self._outcome: str | None = None
        self._owner: tuple[int, object] | None = None
        self._closed = False

    @property
    def event_id(self) -> str:
        if self._interval is None:
            raise RuntimeError("span has not started")
        return self._interval.event_id

    def __enter__(self) -> NativeSpan:
        recorder = self._recorder
        with recorder._lock:
            if self._interval is not None:
                raise RuntimeError("span scopes are single-use")
            parent = _current.get()
            interval = _Interval(
                event_id=uuid4().hex,
                sequence=len(recorder._intervals),
                name=self._name,
                kind=self._kind,
                parent_id=parent[1] if parent and parent[0] is recorder else None,
                start_unix_ns=time.time_ns(),
                start_mono_ns=time.monotonic_ns(),
                attributes=self._attributes,
            )
            recorder._intervals[interval.event_id] = interval
            self._interval = interval
            self._owner = _owner()
            self._token = _current.set((recorder, interval.event_id))
        return self

    def _require_active_context(self) -> None:
        if self._interval is None or self._closed:
            raise RuntimeError("span is not active")
        if self._owner != _owner() or _current.get() != (self._recorder, self.event_id):
            raise RuntimeError("span requires its original causal context and task")

    def finish(self, status: str = "SUCCEEDED") -> None:
        """Declare an observed result; exit still determines duration/errors."""
        if status not in _OUTCOMES:
            raise ValueError("unsupported explicit outcome")
        with self._recorder._lock:
            self._require_active_context()
            if self._outcome is not None:
                raise RuntimeError("span outcome already declared")
            self._outcome = status

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> bool:
        with self._recorder._lock:
            self._require_active_context()
            assert self._token is not None and self._interval is not None
            # Tokens also reject a copied Context in the same thread/task.
            _current.reset(self._token)
            interval = self._interval
            interval.end_mono_ns = time.monotonic_ns()
            interval.end_unix_ns = time.time_ns()
            if exc_type is not None:
                interval.status = (
                    "CANCELLED" if issubclass(exc_type, asyncio.CancelledError)
                    else "FAILED"
                )
            else:
                interval.status = self._outcome or "INCOMPLETE"
            self._closed = True
        return False
