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
from src.communications.service import digest, encoded

UTC = timezone.utc


@pytest.fixture
def auto_whatsapp(tmp_path, monkeypatch):
    """Real private persistence/profile identity; transport writes a canary, never sends."""
    from types import SimpleNamespace
    from src.whatsapp import WhatsAppSession
    from src.project_permissions import ProjectContext, ProjectPermissions
    root = tmp_path / "w"
    root.mkdir()
    (root / "out").mkdir()
    (root / "out/report.txt").write_text("private synthetic report", encoding="utf-8")
    current = [root]
    context = ProjectContext("project-auto", root, "opaque-project-binding", "Private test")
    permissions = ProjectPermissions(lambda: context)
    initial = permissions.snapshot()
    permissions.save(expected_project_id=initial["project_id"], expected_binding=initial["binding"],
        expected_revision=initial["revision"], read_directories=["out"], write_directories=[], confirmed=True)
    session = WhatsAppSession(tmp_path / "wa")
    monkeypatch.setattr("src.whatsapp.session.find_brave", lambda: None)
    monkeypatch.setattr(session, "status", lambda: {"state": "connected"})
    session.configure("Private fixture", True)
    attempts = tmp_path / "transport-attempts.jsonl"
    calls = []
    mode = ["sent"]
    def send(phone, text, attachments, operation_id):
        calls.append((phone, text, [p.read_bytes() for p in attachments], operation_id))
        with attempts.open("a", encoding="utf-8") as output:
            output.write(encoded({"operation_id": operation_id, "fixture_only": True}) + "\n")
        if mode[0] == "missing":
            return None
        return {"status": mode[0], "operation_id": operation_id, "observed_at": "2026-11-01T12:00:00+00:00"}
    monkeypatch.setattr(session, "send", send)
    allowed = [True]
    def authorize(source, payload, project):
        if not allowed[0]:
            return {"authorized": False}
        return {"authorized": True, "source_sha256": digest(encoded(source).encode("utf-8")),
            "payload_sha256": digest(encoded(payload).encode("utf-8"))}
    now = [datetime(2026, 11, 1, 12, tzinfo=UTC)]
    service = CommunicationService(tmp_path / "s", session, lambda: current[0], lambda: now[0],
        project_snapshot=permissions.snapshot, task_authorizer=authorize)
    contact = service.create_contact("Synthetic recipient", "+34600000001")
    return SimpleNamespace(service=service, session=session, contact=contact, calls=calls, attempts=attempts,
        root=root, current=current, now=now, allowed=allowed, mode=mode, permissions=permissions)


def auto_consent(env, enabled=True):
    status = env.service.whatsapp_authorization()
    return env.service.set_whatsapp_authorization(enabled=enabled,
        expected_project_id=status["project"]["project_id"], expected_binding=status["project"]["binding"],
        expected_session_identity=status["session_identity"], expected_authorization_revision=status["revision"])


def auto_request(env, key="task-1", **changes):
    status = env.service.whatsapp_authorization()
    source = {"mission_id": "private-human-task", "project_id": status["project"]["project_id"],
        "binding": status["project"]["binding"], "session_identity": status["session_identity"],
        "conversation_id": "private-conversation", "human_message_id": "human-message-1", "conversation_revision": 1,
        "human_message_sha256": digest(b"Send the synthetic report"), "send_intent_receipt_sha256": digest(b"controlled host intent")}
    data = {"request_id": key, "source": source, "contact_id": env.contact["id"], "text": "Synthetic requested result",
        "expected_authorization_revision": status["revision"]}
    data.update(changes)
    return data


def test_auto_fresh_only(auto_whatsapp):
    e = auto_whatsapp
    previous = e.service.create_draft(e.contact["id"], "Existing draft must stay a draft")
    assert not e.service.whatsapp_authorization()["enabled"]
    auto_consent(e)
    assert e.service.get_draft(previous["id"])["state"] == "draft"
    assert not e.attempts.exists()
    request = auto_request(e, attachments=["out/report.txt"])
    sent = e.service.create_requested_message(**request)
    assert sent["state"] == "sent" and sent["confirmed_at"] is None
    assert sent["authorization"]["kind"] == "channel_task"
    assert len(e.calls) == 1 and e.calls[0][2] == [b"private synthetic report"]
    assert e.service.create_requested_message(**request)["id"] == sent["id"]
    assert e.service.create_requested_message(**{**request, "request_id": "host-retry-alias"})["id"] == sent["id"]
    assert len(e.attempts.read_text().splitlines()) == 1
    with pytest.raises(CommunicationError, match="different"):
        e.service.create_requested_message(**{**request, "text": "Different payload"})
    assert len(e.calls) == 1


@pytest.mark.parametrize("change", ["no_grant", "no_host", "rejected_host", "source_extra", "source_project", "source_session", "source_revision", "attachment_scope"])
def test_auto_denied(auto_whatsapp, change):
    e = auto_whatsapp
    if change != "no_grant": auto_consent(e)
    request = auto_request(e)
    if change == "no_host": e.service.task_authorizer = None
    if change == "rejected_host": e.allowed[0] = False
    if change == "source_extra": request["source"]["model_granted"] = True
    if change == "source_project": request["source"]["project_id"] = "other"
    if change == "source_session": request["source"]["session_identity"] = "0" * 64
    if change == "source_revision": request["source"]["conversation_revision"] = True
    if change == "attachment_scope": request["attachments"] = ["outside.txt"]
    with pytest.raises(CommunicationError): e.service.create_requested_message(**request)
    assert e.service.drafts() == [] and not e.calls and not e.attempts.exists()


@pytest.mark.parametrize("change", ["revoke", "source", "session", "project", "contact"])
def test_auto_before_due(auto_whatsapp, change):
    e = auto_whatsapp
    auto_consent(e)
    request = auto_request(e, schedule={"kind": "once", "at": (e.now[0] + timedelta(hours=1)).isoformat()})
    pending = e.service.create_requested_message(**request)
    assert pending["state"] == "scheduled" and not e.attempts.exists()
    if change == "revoke": auto_consent(e, False)
    if change == "source": e.allowed[0] = False
    if change == "session":
        config = json.loads((e.session.root / "config.json").read_text())
        (e.session.root / "config.json").write_text(json.dumps({**config, "session_id": "0" * 32}))
    if change == "project":
        other = e.root.parent / "other"
        other.mkdir()
        e.current[0] = other
    if change == "contact":
        with e.service._db() as db:
            db.execute("UPDATE contacts SET data=? WHERE id=?", (encoded({**e.contact, "phone": "+34600000002"}), e.contact["id"]))
    e.now[0] += timedelta(hours=1)
    e.service.tick()
    assert e.service.get_draft(pending["id"])["state"] == "needs_review"
    assert not e.calls and not e.attempts.exists()


def test_auto_revoke_admission(auto_whatsapp, monkeypatch):
    e = auto_whatsapp
    auto_consent(e)
    def status_then_revoke():
        auto_consent(e, False)
        return {"state": "connected"}
    monkeypatch.setattr(e.session, "status", status_then_revoke)
    stopped = e.service.create_requested_message(**auto_request(e))
    assert stopped["state"] == "failed" and not e.calls and not e.attempts.exists()
    assert not e.service.runs()[0].get("transport_admitted_at")


def test_auto_revoke_old_profile(auto_whatsapp):
    e = auto_whatsapp
    auto_consent(e)
    config_path = e.session.root / "config.json"
    original = config_path.read_bytes()
    rotated = {**json.loads(original), "session_id": "0" * 32}
    config_path.write_text(json.dumps(rotated), encoding="utf-8")
    assert e.service.whatsapp_authorization()["enabled"] is False
    auto_consent(e, False)
    config_path.write_bytes(original)
    assert e.service.whatsapp_authorization()["enabled"] is False
    with pytest.raises(CommunicationError):
        e.service.create_requested_message(**auto_request(e))
    assert not e.calls and not e.attempts.exists()


def test_auto_stop_admission(auto_whatsapp):
    e = auto_whatsapp
    auto_consent(e)
    pending = e.service.create_requested_message(**auto_request(e,
        schedule={"kind": "once", "at": (e.now[0] + timedelta(hours=1)).isoformat()}))
    e.now[0] += timedelta(hours=1)
    checks = []
    def stop():
        checks.append(True)
        return len(checks) > 1
    e.service.tick(should_stop=stop)
    assert e.service.get_draft(pending["id"])["state"] == "failed"
    assert not e.calls and not e.attempts.exists()


def test_auto_missing_receipt(auto_whatsapp):
    e = auto_whatsapp
    auto_consent(e)
    e.mode[0] = "missing"
    request = auto_request(e)
    assert e.service.create_requested_message(**request)["state"] == "uncertain"
    assert e.service.create_requested_message(**request)["state"] == "uncertain"
    assert len(e.calls) == len(e.attempts.read_text().splitlines()) == 1


def test_auto_manual_edit_no_inherit(auto_whatsapp):
    e = auto_whatsapp
    auto_consent(e)
    pending = e.service.create_requested_message(**auto_request(e,
        schedule={"kind": "once", "at": (e.now[0] + timedelta(hours=1)).isoformat()}))
    edited = e.service.update_draft(pending["id"], pending["revision"], text="Only a new draft")
    assert edited["state"] == "draft" and not edited.get("authorization")
    e.now[0] += timedelta(hours=1)
    e.service.tick()
    assert not e.calls and not e.attempts.exists()


def test_auto_api_strict(auto_whatsapp):
    e = auto_whatsapp
    app = FastAPI(); app.include_router(create_communication_router(e.service))
    client = TestClient(app)
    current = client.get("/api/communications/whatsapp-authorization").json()
    body = {"enabled": True, "expected_project_id": current["project"]["project_id"], "expected_binding": current["project"]["binding"],
        "expected_session_identity": current["session_identity"], "expected_authorization_revision": current["revision"]}
    assert client.put("/api/communications/whatsapp-authorization", json={**body, "enabled": "true"}).status_code == 422
    assert client.put("/api/communications/whatsapp-authorization", json={**body, "send_old_drafts": True}).status_code == 422
    assert client.put("/api/communications/whatsapp-authorization", json={**body, "expected_binding": "wrong"}).status_code == 409
    grant = client.put("/api/communications/whatsapp-authorization", json=body).json()
    assert grant["enabled"] is True and grant["validity"] == "until_revoked"
    assert client.put("/api/communications/whatsapp-authorization", json=body).status_code == 409
    assert e.service.drafts() == [] and not e.attempts.exists()


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
