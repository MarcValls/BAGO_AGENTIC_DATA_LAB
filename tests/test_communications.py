"""Synthetic transport tests: these never connect to WhatsApp or real contacts."""
import asyncio
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from src.api.communication_routes import create_communication_router
from src.communications import CommunicationService, CommunicationError
from src.communications.service import next_time, schedule_value
from src.communications.worker import CommunicationWorker

UTC = timezone.utc


class Transport:
    def __init__(self):
        self.calls = []
        self.connected = True
        self.mode = "sent"

    def status(self):
        return {"state": "connected" if self.connected else "disconnected"}

    def send(self, phone, text, attachments, operation_id):
        self.calls.append((phone, text, [p.read_bytes() for p in attachments], operation_id))
        if self.mode == "crash":
            raise KeyboardInterrupt()
        if self.mode == "exception":
            raise RuntimeError("private transport internals")
        return {"status": self.mode, "operation_id": operation_id, "observed_at": "2026-10-22T12:00:00+00:00"}


@pytest.fixture
def setup(tmp_path):
    root = tmp_path / "workspace"
    root.mkdir()
    (root / "result.pdf").write_bytes(b"%PDF synthetic fixture")
    now = [datetime(2026, 10, 22, 12, tzinfo=UTC)]
    transport = Transport()
    service = CommunicationService(tmp_path / "state", transport, root, lambda: now[0])
    contact = service.create_contact("Synthetic client", "+34 600-000-001")
    return service, contact, transport, now, root


def draft(setup, **kw):
    service, contact, *_ = setup
    return service.create_draft(contact["id"], "Synthetic reviewed result", **kw)


def test_prepare_no_effect_confirm_exact_revision_replay(setup):
    service, contact, transport, *_ = setup
    d = draft(setup, attachments=["result.pdf"])
    service.tick()
    assert transport.calls == []
    with pytest.raises(CommunicationError):
        service.confirm(d["id"], d["revision"], False)
    with pytest.raises(CommunicationError):
        service.confirm(d["id"], "stale", True)
    result = service.confirm(d["id"], d["revision"], True)
    assert result["state"] == "sent"
    assert transport.calls[0][:3] == (contact["phone"], d["text"], [b"%PDF synthetic fixture"])
    with pytest.raises(CommunicationError):
        service.confirm(d["id"], d["revision"], True)
    with pytest.raises(CommunicationError):
        service.update_draft(d["id"], d["revision"], text="changed")
    assert len(transport.calls) == 1
    assert service.runs()[0]["receipt"]["operation_id"] == transport.calls[0][3]


@pytest.mark.parametrize("phone", ["600000001", "+012345678", "+1", "javascript:123", ""])
def test_bad_contacts(setup, phone):
    with pytest.raises(CommunicationError):
        setup[0].create_contact("Name", phone)


@pytest.mark.parametrize("path", ["missing.pdf", "../result.pdf", "C:/result.pdf", ".env", "secret.txt", "result.pdf/../result.pdf", "result.pdf:ads", "./result.pdf"])
def test_bad_attachment(setup, path):
    with pytest.raises(CommunicationError):
        draft(setup, attachments=[path])
    assert not setup[2].calls


@pytest.mark.parametrize("change", ["modify", "delete", "snapshot"])
def test_attachment_revalidation_before_confirm(setup, change):
    from pathlib import Path
    service, _, transport, _, root = setup
    d = draft(setup, attachments=["result.pdf"])
    if change == "modify":
        (root / "result.pdf").write_bytes(b"changed")
    elif change == "delete":
        (root / "result.pdf").unlink()
    else:
        Path(d["attachments"][0]["snapshot"]).write_bytes(b"changed snapshot")
    with pytest.raises(CommunicationError):
        service.confirm(d["id"], d["revision"], True)
    assert not transport.calls


def once(setup):
    return {"kind": "once", "at": (setup[3][0] + timedelta(minutes=1)).isoformat(), "timezone": "Europe/Madrid"}


def test_edit_revokes_scheduled_and_stale_confirmation(setup):
    service, _, transport, now, _ = setup
    d = draft(setup, schedule=once(setup))
    service.confirm(d["id"], d["revision"], True)
    edited = service.update_draft(d["id"], d["revision"], text="New content")
    assert edited["state"] == "draft" and edited["revision"] != d["revision"]
    now[0] += timedelta(minutes=1)
    service.tick()
    assert not transport.calls
    with pytest.raises(CommunicationError):
        service.confirm(d["id"], d["revision"], True)


def test_once_persistence_two_workers_unique_claim(setup):
    service, _, transport, now, root = setup
    d = draft(setup, schedule=once(setup))
    service.confirm(d["id"], d["revision"], True)
    second = CommunicationService(service.root, transport, root, lambda: now[0])
    now[0] += timedelta(minutes=1)
    with ThreadPoolExecutor(2) as pool:
        list(pool.map(lambda s: s.tick(), [service, second]))
    assert len(transport.calls) == len(service.runs()) == 1
    assert second.get_draft(d["id"])["state"] == "sent"


@pytest.mark.parametrize("mode,expected", [("uncertain", "uncertain"), ("exception", "uncertain"), ("nonsense", "uncertain"), ("failed", "failed")])
def test_transport_failures_never_retry(setup, mode, expected):
    service, _, transport, *_ = setup
    transport.mode = mode
    d = draft(setup)
    assert service.confirm(d["id"], d["revision"], True)["state"] == expected
    service.tick()
    service.recover()
    service.tick()
    assert len(transport.calls) == 1
    assert "private transport" not in json.dumps(service.runs())


def test_crash_after_claim_or_effect_is_uncertain_no_retry(setup):
    service, _, transport, now, root = setup
    transport.mode = "crash"
    d = draft(setup)
    with pytest.raises(KeyboardInterrupt):
        service.confirm(d["id"], d["revision"], True)
    assert service.runs()[0]["state"] == "sending"
    reopened = CommunicationService(service.root, transport, root, lambda: now[0])
    reopened.recover()
    reopened.tick()
    assert reopened.get_draft(d["id"])["state"] == "uncertain"
    assert len(transport.calls) == 1


def test_disconnected_not_sent(setup):
    service, _, transport, *_ = setup
    transport.connected = False
    d = draft(setup)
    assert service.confirm(d["id"], d["revision"], True)["state"] == "failed"
    assert not transport.calls


def test_crash_before_transport_keeps_claim_uncertain(setup, monkeypatch):
    service, _, transport, *_ = setup
    d = draft(setup, schedule=once(setup))
    service.confirm(d["id"], d["revision"], True)
    setup[3][0] += timedelta(minutes=1)
    def crash(_):
        raise KeyboardInterrupt()
    monkeypatch.setattr(service, "_validate_attachments", crash)
    with pytest.raises(KeyboardInterrupt):
        service.tick()
    service.recover()
    assert service.get_draft(d["id"])["state"] == "uncertain"
    assert not transport.calls


def test_missing_or_other_operation_receipt_never_sent(setup, monkeypatch):
    service, _, transport, *_ = setup
    monkeypatch.setattr(transport, "send", lambda *a: {"status": "sent", "operation_id": "another", "observed_at": "2026-10-22T12:00:00Z"})
    d = draft(setup)
    assert service.confirm(d["id"], d["revision"], True)["state"] == "uncertain"


def test_persistence_failure_prevents_external_effect(setup):
    service, _, transport, *_ = setup
    d = draft(setup)
    with service._db() as db:
        db.execute("CREATE TRIGGER deny_run BEFORE INSERT ON runs BEGIN SELECT RAISE(ABORT,'disk unavailable fixture'); END")
    result = service.confirm(d["id"], d["revision"], True)
    assert result["state"] != "sent"
    assert transport.calls == [] and service.runs() == []


def test_modified_after_scheduling_blocks_consumption(setup):
    service, _, transport, now, root = setup
    d = draft(setup, attachments=["result.pdf"], schedule=once(setup))
    service.confirm(d["id"], d["revision"], True)
    (root / "result.pdf").write_bytes(b"late modification")
    now[0] += timedelta(minutes=1)
    service.tick()
    assert service.get_draft(d["id"])["state"] == "failed"
    assert not transport.calls


def test_cancel_and_missed_window(setup):
    service, _, transport, now, _ = setup
    a = draft(setup, schedule=once(setup))
    b = draft(setup, schedule=once(setup))
    for d in (a, b):
        service.confirm(d["id"], d["revision"], True)
    service.cancel(a["id"], a["revision"], True)
    now[0] += timedelta(hours=2)
    service.tick()
    assert service.get_draft(a["id"])["state"] == "cancelled"
    assert service.get_draft(b["id"])["state"] == "needs_review"
    assert not transport.calls


@pytest.mark.parametrize("kind,days", [("daily", []), ("weekly", [5])])
def test_recurring_persists_next_occurrence(setup, kind, days):
    service, _, transport, now, _ = setup
    d = draft(setup, schedule={"kind": kind, "timezone": "Europe/Madrid", "time": "15:00", "weekdays": days})
    service.confirm(d["id"], d["revision"], True)
    first = service.get_draft(d["id"])["next_run_at"]
    now[0] = datetime.fromisoformat(first)
    service.tick()
    updated = service.get_draft(d["id"])
    assert updated["state"] == "scheduled" and updated["next_run_at"] > first
    assert len(transport.calls) == 1


@pytest.mark.parametrize("day", [datetime(2026, 3, 29, 0, tzinfo=UTC), datetime(2026, 10, 25, 0, tzinfo=UTC)])
def test_dst_gap_fold_rejected(day):
    with pytest.raises(CommunicationError, match="DST"):
        next_time(schedule_value({"kind": "daily", "time": "02:30", "timezone": "Europe/Madrid"}), day)


@pytest.mark.parametrize("schedule", [
    {"kind": "once", "at": "2026-01-01T12:00:00"},
    {"kind": "now", "time": "12:00"}, {"kind": "daily", "time": "25:00"},
    {"kind": "weekly", "time": "12:00", "weekdays": [0]},
    {"kind": "daily", "time": "12:00", "weekdays": [1]},
    {"kind": "weekly", "time": "12:00", "weekdays": []},
    {"kind": "now", "timezone": "Wrong/Zone"}, {"kind": "now", "extra": 1}])
def test_invalid_schedule(setup, schedule):
    with pytest.raises(CommunicationError):
        draft(setup, schedule=schedule)


def test_past_once_rejected(setup):
    with pytest.raises(CommunicationError):
        draft(setup, schedule={"kind": "once", "at": "2026-01-01T12:00:00Z"})


def test_http_review_and_conflict(setup):
    service, contact, transport, *_ = setup
    app = FastAPI()
    app.include_router(create_communication_router(service))
    client = TestClient(app)
    d = client.post("/api/communications/drafts", json={"contact_id": contact["id"], "text": "Reviewed"}).json()
    assert client.post(f"/api/communications/drafts/{d['id']}/confirm", json={"expected_revision": "wrong", "confirmed": True}).status_code == 409
    assert not transport.calls
    assert client.post(f"/api/communications/drafts/{d['id']}/confirm", json={"expected_revision": d["revision"], "confirmed": "true"}).status_code == 422
    assert client.post(f"/api/communications/drafts/{d['id']}/confirm", json={"expected_revision": d["revision"], "confirmed": True}).json()["state"] == "sent"


def test_worker_exclusive_and_stop_no_new_effect(setup):
    async def run():
        a, b = CommunicationWorker(setup[0]), CommunicationWorker(setup[0])
        assert await a.start()
        assert not await b.start()
        await a.stop()
        assert a.task.done()
        assert await b.start()
        await b.stop()
    asyncio.run(run())
