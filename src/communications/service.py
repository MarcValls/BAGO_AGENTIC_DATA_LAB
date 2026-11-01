"""Durable reviewed messages. External effects are at-most-attempted, never retried blindly.

Maximum lateness is five minutes. Recurrences reject ambiguous/nonexistent local
times rather than guessing DST. Attachments are limited to 10 MiB each, 5 files.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import stat
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from src.storage.portable import configured_path

UTC = timezone.utc


class CommunicationError(ValueError):
    def __init__(self, message, status=422):
        super().__init__(message)
        self.status = status


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def instant(value):
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if result.tzinfo is None:
            raise ValueError()
        return result.astimezone(UTC)
    except (ValueError, TypeError, AttributeError):
        raise CommunicationError("An ISO8601 instant with explicit offset is required.") from None


def schedule_value(value):
    if not isinstance(value, dict) or set(value) - {"kind", "timezone", "at", "time", "weekdays"}:
        raise CommunicationError("Invalid schedule fields.")
    s = {"kind": value.get("kind"), "timezone": value.get("timezone", "Europe/Madrid"),
         "at": value.get("at"), "time": value.get("time"), "weekdays": value.get("weekdays", [])}
    try:
        ZoneInfo(s["timezone"])
    except (ZoneInfoNotFoundError, TypeError, ValueError):
        raise CommunicationError("IANA timezone unavailable or invalid.") from None
    if s["kind"] not in {"now", "once", "daily", "weekly"}:
        raise CommunicationError("Unknown schedule kind.")
    if s["kind"] == "once":
        instant(s["at"])
    elif s["at"] is not None:
        raise CommunicationError("at applies only to once.")
    if s["kind"] in {"daily", "weekly"}:
        if not isinstance(s["time"], str) or not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", s["time"]):
            raise CommunicationError("Local HH:MM required.")
    elif s["time"] is not None:
        raise CommunicationError("time applies only to recurrence.")
    days = s["weekdays"]
    if not isinstance(days, list) or any(type(d) is not int or d not in range(1, 8) for d in days) or len(set(days)) != len(days):
        raise CommunicationError("Weekdays must be unique ISO 1..7.")
    if s["kind"] == "weekly" and not days:
        raise CommunicationError("Weekly schedule needs weekdays.")
    if s["kind"] != "weekly" and days:
        raise CommunicationError("weekdays applies only to weekly.")
    return s


def next_time(s, now):
    if s["kind"] == "now":
        return now
    if s["kind"] == "once":
        when = instant(s["at"])
        if when <= now:
            raise CommunicationError("Scheduled instant must be in the future.")
        return when
    zone = ZoneInfo(s["timezone"])
    hour, minute = map(int, s["time"].split(":"))
    local = now.astimezone(zone)
    for offset in range(9):
        day = local.date() + timedelta(days=offset)
        if s["kind"] == "weekly" and day.isoweekday() not in s["weekdays"]:
            continue
        naive = datetime.combine(day, datetime.min.time()).replace(hour=hour, minute=minute)
        candidates = {naive.replace(tzinfo=zone, fold=fold).astimezone(UTC) for fold in (0, 1)
                      if naive.replace(tzinfo=zone, fold=fold).astimezone(UTC).astimezone(zone).replace(tzinfo=None) == naive}
        if not candidates or len(candidates) != 1:
            if naive >= local.replace(tzinfo=None):
                raise CommunicationError("Ambiguous or nonexistent DST time; choose another local time.")
            continue
        candidate = candidates.pop()
        if candidate > now:
            return candidate
    raise CommunicationError("No next occurrence found.")


class CommunicationService:
    def __init__(self, state_dir=None, session=None, workspace_root=None, clock=None, contacts_store=None,
                 project_snapshot=None, task_authorizer=None):
        self.root = (Path(state_dir).expanduser().resolve() if state_dir else
                     configured_path("BAGO_COMMUNICATIONS_STATE_DIR", "communications"))
        self.contacts_store = contacts_store
        self.session = session
        self.workspace_root = workspace_root or Path.cwd()
        self.clock = clock or (lambda: datetime.now(UTC))
        self.project_snapshot = project_snapshot
        self.task_authorizer = task_authorizer
        # The existing worker binds its cooperative shutdown event here.
        # Immediate HTTP/chat dispatch must observe it too, not only scheduler ticks.
        self.stop_requested = lambda: False
        # Creation is explicit service construction, never module import.
        self.root.mkdir(parents=True, exist_ok=True)
        with self._db() as db:
            db.executescript("""CREATE TABLE IF NOT EXISTS contacts(id TEXT PRIMARY KEY,data TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS drafts(id TEXT PRIMARY KEY,data TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY,draft_id TEXT NOT NULL,occurrence TEXT NOT NULL,data TEXT NOT NULL,UNIQUE(draft_id,occurrence));
            CREATE TABLE IF NOT EXISTS whatsapp_authorizations(project_key TEXT PRIMARY KEY,data TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS requested_messages(request_id TEXT PRIMARY KEY,identity TEXT NOT NULL,draft_id TEXT NOT NULL);""")

    def _db(self):
        db = sqlite3.connect(self.root / "communications.sqlite3", timeout=15)
        db.row_factory = sqlite3.Row
        return db

    def _now(self):
        value = self.clock()
        if value.tzinfo is None:
            raise CommunicationError("Clock must be timezone aware.")
        return value.astimezone(UTC)

    def _save(self, db, d):
        d["updated_at"] = self._now().isoformat()
        db.execute("INSERT OR REPLACE INTO drafts VALUES (?,?)", (d["id"], encoded(d)))
        return d

    def _get(self, db, draft_id):
        row = db.execute("SELECT data FROM drafts WHERE id=?", (draft_id,)).fetchone()
        if row is None:
            raise CommunicationError("Draft not found.", 404)
        return json.loads(row[0])

    def contacts(self):
        if self.contacts_store is not None:
            with self._db() as db:
                legacy = [json.loads(r[0]) for r in db.execute("SELECT data FROM contacts ORDER BY rowid")]
            self.contacts_store.import_legacy(legacy)
            return self.contacts_store.list()
        with self._db() as db:
            return [json.loads(r[0]) for r in db.execute("SELECT data FROM contacts ORDER BY rowid")]

    def create_contact(self, name, phone):
        if self.contacts_store is not None:
            self.contacts()  # Reconcile before creation; never mint a second ID for legacy data.
            return self.contacts_store.add(name, phone)
        if not isinstance(name, str) or not name.strip() or len(name) > 120:
            raise CommunicationError("Contact name required (maximum 120 characters).")
        if not isinstance(phone, str):
            raise CommunicationError("E.164 phone required.")
        phone = re.sub(r"[ ()-]", "", phone)
        if not re.fullmatch(r"\+[1-9][0-9]{7,14}", phone):
            raise CommunicationError("E.164 phone required, including +country code.")
        c = {"id": "contact_" + uuid.uuid4().hex, "name": name.strip(), "phone": phone}
        with self._db() as db:
            db.execute("INSERT INTO contacts VALUES (?,?)", (c["id"], encoded(c)))
        return c

    def drafts(self):
        with self._db() as db:
            return [json.loads(r[0]) for r in db.execute("SELECT data FROM drafts ORDER BY rowid DESC")]

    def get_draft(self, draft_id):
        with self._db() as db:
            return self._get(db, draft_id)

    def _workspace(self):
        return Path(self.workspace_root() if callable(self.workspace_root) else self.workspace_root).resolve(strict=True)

    def _automatic_project(self):
        if self.project_snapshot is None:
            raise CommunicationError("Automatic WhatsApp requires a current registered project.", 409)
        try:
            snapshot = self.project_snapshot()
            if not isinstance(snapshot, dict) or any(not isinstance(snapshot.get(k), str) or not snapshot[k]
                    for k in ("project_id", "root", "binding")):
                raise ValueError()
            if Path(snapshot["root"]).resolve(strict=True) != self._workspace():
                raise ValueError()
        except Exception:
            raise CommunicationError("The current WhatsApp project binding is unavailable or changed.", 409) from None
        return dict(snapshot)

    def _channel_identity(self):
        try:
            value = self.session.authorization_identity()
        except Exception:
            value = None
        return value if isinstance(value, str) and re.fullmatch(r"[a-f0-9]{64}", value) else None

    @staticmethod
    def _project_key(project):
        return digest(encoded({k: project[k] for k in ("project_id", "root", "binding")}).encode("utf-8"))

    def _authorization_status(self, db, project):
        row = db.execute("SELECT data FROM whatsapp_authorizations WHERE project_key=?", (self._project_key(project),)).fetchone()
        grant = json.loads(row[0]) if row else {}
        identity = self._channel_identity()
        return {"available": True, "enabled": bool(grant.get("enabled") and identity and grant.get("session_identity") == identity),
            "revision": grant.get("revision", "none"), "grant_id": grant.get("grant_id"),
            "project": {k: project[k] for k in ("project_id", "root", "binding")},
            "session_identity": identity, "validity": "until_revoked",
            "granted_at": grant.get("granted_at"), "revoked_at": grant.get("revoked_at")}

    def whatsapp_authorization(self):
        project = self._automatic_project()
        with self._db() as db:
            return self._authorization_status(db, project)

    def set_whatsapp_authorization(self, *, enabled, expected_project_id, expected_binding,
                                  expected_session_identity, expected_authorization_revision):
        if type(enabled) is not bool:
            raise CommunicationError("Explicit WhatsApp channel consent is required.")
        project = self._automatic_project()
        if (project["project_id"] != expected_project_id or project["binding"] != expected_binding
                or not expected_session_identity or self._channel_identity() != expected_session_identity):
            raise CommunicationError("Project or WhatsApp session changed; reload its current authorization.", 409)
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            current = self._authorization_status(db, project)
            if current["revision"] != expected_authorization_revision:
                raise CommunicationError("WhatsApp authorization revision changed.", 409)
            if current["enabled"] == enabled:
                row = db.execute("SELECT data FROM whatsapp_authorizations WHERE project_key=?", (self._project_key(project),)).fetchone()
                persisted = json.loads(row[0]) if row else {}
                # An inactive mismatched profile is not already-revoked
                # consent. OFF must revoke the persisted grant as well, so
                # restoring the old profile cannot reactivate it later.
                if enabled or not persisted.get("enabled"):
                    return current
            grant = {"grant_id": "wa_grant_" + uuid.uuid4().hex if enabled else current["grant_id"],
                "project": current["project"], "session_identity": expected_session_identity,
                "enabled": enabled, "validity": "until_revoked",
                "granted_at": self._now().isoformat() if enabled else current["granted_at"],
                "revoked_at": None if enabled else self._now().isoformat()}
            grant["revision"] = digest(encoded(grant).encode("utf-8"))
            db.execute("INSERT OR REPLACE INTO whatsapp_authorizations VALUES (?,?)", (self._project_key(project), encoded(grant)))
            return self._authorization_status(db, project)

    def _require_task_grant(self, db, project, expected_revision, source):
        grant = self._authorization_status(db, project)
        if (not grant["enabled"] or grant["revision"] != expected_revision
                or source.get("project_id") != project["project_id"] or source.get("binding") != project["binding"]
                or source.get("session_identity") != grant["session_identity"]):
            raise CommunicationError("Automatic WhatsApp authorization was revoked or its project/session changed.", 403)
        return grant

    def _validate_task_source(self, source, payload, project):
        fields = {"mission_id", "project_id", "binding", "session_identity", "conversation_id", "human_message_id",
            "conversation_revision", "human_message_sha256", "send_intent_receipt_sha256"}
        if not isinstance(source, dict) or set(source) != fields:
            raise CommunicationError("An exact host-owned human task source is required.", 403)
        if (type(source["conversation_revision"]) is not int or source["conversation_revision"] < 0
                or any(not isinstance(source[k], str) or not source[k].strip() for k in fields - {"conversation_revision"})
                or any(not re.fullmatch(r"[a-f0-9]{64}", source[k]) for k in
                    ("session_identity", "human_message_sha256", "send_intent_receipt_sha256"))):
            raise CommunicationError("The host-owned human task identity is invalid.", 403)
        if self.task_authorizer is None:
            raise CommunicationError("A host source/intent validator is required for automatic WhatsApp.", 403)
        expected = {"authorized": True, "source_sha256": digest(encoded(source).encode("utf-8")),
            "payload_sha256": digest(encoded(payload).encode("utf-8"))}
        try:
            # Callbacks cannot change the payload being admitted by mutating it.
            proof = self.task_authorizer(json.loads(encoded(source)), json.loads(encoded(payload)), dict(project))
        except Exception:
            raise CommunicationError("The requested send was not authorized by its current human source.", 403) from None
        if not isinstance(proof, dict) or set(proof) != set(expected) or proof.get("authorized") is not True or proof != expected:
            raise CommunicationError("The human send-intent proof does not match this exact task.", 403)
        return expected

    def create_requested_message(self, *, request_id, source, contact_id, text, attachments=None, schedule=None,
                                 expected_authorization_revision):
        """Host-only fresh task admission. Ordinary drafts never become sends.

        Channel consent is not intent; a trusted host callback binds each new
        task to the actual owned human request before any automatic admission.
        """
        if self._stopping():
            raise CommunicationError("STOP before automatic WhatsApp task admission.", 409)
        if not isinstance(request_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,120}", request_id):
            raise CommunicationError("Stable task request_id is required.")
        if not isinstance(source, dict):
            raise CommunicationError("An exact host-owned human task source is required.", 403)
        project = self._automatic_project()
        payload = {"contact_id": contact_id, "text": text, "attachments": attachments or [],
            "schedule": schedule_value(schedule or {"kind": "now"}), "conversation_id": source.get("conversation_id")}
        identity = digest(encoded({"source": source, "payload": payload, "project_key": self._project_key(project),
            "grant_revision": expected_authorization_revision}).encode("utf-8"))
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            previous = db.execute("SELECT identity,draft_id FROM requested_messages WHERE request_id=?", (request_id,)).fetchone()
            if previous:
                if previous["identity"] != identity:
                    raise CommunicationError("This request_id is already bound to a different WhatsApp task.", 409)
                return self._get(db, previous["draft_id"])
            same_task = db.execute("SELECT draft_id FROM requested_messages WHERE identity=? LIMIT 1", (identity,)).fetchone()
            if same_task:
                # A retried host attempt with another transport request ID still
                # cannot duplicate the same exact human task/source and payload.
                db.execute("INSERT INTO requested_messages VALUES (?,?,?)", (request_id, identity, same_task["draft_id"]))
                return self._get(db, same_task["draft_id"])
            grant = self._require_task_grant(db, project, expected_authorization_revision, source)
            proof = self._validate_task_source(source, payload, project)
            self._check_automatic_attachment_scope(payload["attachments"], project)
            draft = {"id": "draft_" + uuid.uuid4().hex, "created_at": self._now().isoformat(),
                "conversation_id": source["conversation_id"], "version": 0, "workspace_root": str(self._workspace())}
            draft = self._prepare(draft, contact_id, text, payload["attachments"], payload["schedule"], db)
            draft.update(state="scheduled", task_request_id=request_id,
                authorization={"kind": "channel_task", "grant_id": grant["grant_id"], "grant_revision": grant["revision"],
                    "source": json.loads(encoded(source)), "payload": payload, "host_proof": proof})
            self._save(db, draft)
            db.execute("INSERT INTO requested_messages VALUES (?,?,?)", (request_id, identity, draft["id"]))
        if draft["schedule"]["kind"] == "now":
            self.tick(draft_id=draft["id"])
        return self.get_draft(draft["id"])

    @staticmethod
    def _check_automatic_attachment_scope(paths, project):
        if not isinstance(paths, list):
            raise CommunicationError("Attachment paths must be a list.")
        directories = project.get("read_directories") or []
        for path in paths:
            if not isinstance(path, str) or not any(directory == "." or path == directory or path.startswith(directory.rstrip("/") + "/") for directory in directories):
                raise CommunicationError("Automatic attachments require saved project READ scope.", 403)

    def _validate_automatic_dispatch(self, db, draft):
        authorization = draft.get("authorization") or {}
        if authorization.get("kind") != "channel_task":
            return
        project = self._automatic_project()
        if str(self._workspace()) != draft["workspace_root"]:
            raise CommunicationError("The automatic task workspace changed.", 403)
        source, payload = authorization["source"], authorization["payload"]
        if (draft["contact_id"] != payload["contact_id"] or draft["text"] != payload["text"]
                or draft["schedule"] != payload["schedule"] or [a["path"] for a in draft["attachments"]] != payload["attachments"]):
            raise CommunicationError("The automatic task contents changed after admission.", 409)
        recipient = next((c for c in self.contacts() if c["id"] == draft["contact_id"]), None)
        if recipient != draft["recipient"]:
            raise CommunicationError("The requested WhatsApp recipient changed after admission.", 409)
        self._require_task_grant(db, project, authorization["grant_revision"], source)
        self._validate_task_source(source, payload, project)
        self._check_automatic_attachment_scope(payload["attachments"], project)

    def _snapshot(self, paths, draft_id):
        if not isinstance(paths, list) or len(paths) > 5:
            raise CommunicationError("At most five attachments.")
        root = self._workspace()
        result = []
        for raw in paths:
            if not isinstance(raw, str) or "\\" in raw or ":" in raw or raw.startswith("/"):
                raise CommunicationError("Exact relative POSIX attachment path required.")
            parts = PurePosixPath(raw).parts
            if not parts or str(PurePosixPath(raw)) != raw or any(p.lower() in {"..", ".", ".git", ".env", ".ssh", ".codex"} or p.startswith(".env") or any(word in p.lower() for word in ("secret", "credential", "token", "password")) for p in parts):
                raise CommunicationError("Attachment path forbidden.")
            p = root
            for part in parts:
                p /= part
                try:
                    st = p.lstat()
                except OSError:
                    raise CommunicationError("Attachment does not exist.") from None
                if p.is_symlink() or getattr(st, "st_file_attributes", 0) & 1024:
                    raise CommunicationError("Reparse/symlink attachments forbidden.")
            if not p.resolve().is_relative_to(root) or not p.is_file() or p.suffix.lower() not in {".pdf", ".txt", ".csv", ".png", ".jpg", ".jpeg", ".webp"}:
                raise CommunicationError("Attachment type or scope forbidden.")
            if p.stat().st_size > 10 * 1024 * 1024:
                raise CommunicationError("Attachment exceeds 10 MiB.")
            data = p.read_bytes()
            sha = digest(data)
            target = self.root / "snapshots" / draft_id / (sha + p.suffix.lower())
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            result.append({"path": raw, "name": p.name, "sha256": sha, "size": len(data), "snapshot": str(target)})
        return result

    def _revision(self, d):
        return digest(encoded({k: d[k] for k in ("id", "contact_id", "recipient", "text", "attachments", "schedule", "workspace_root", "version")}).encode())

    def create_draft(self, contact_id, text, attachments=None, schedule=None, conversation_id=None):
        now = self._now().isoformat()
        d = {"id": "draft_" + uuid.uuid4().hex, "created_at": now, "conversation_id": conversation_id,
             "version": 0, "workspace_root": str(self._workspace())}
        return self._prepare(d, contact_id, text, attachments or [], schedule or {"kind": "now"})

    def _prepare(self, d, contact_id, text, attachments, schedule, db=None):
        recipient = next((c for c in self.contacts() if c["id"] == contact_id), None)
        if recipient is not None and not re.fullmatch(r"\+[1-9][0-9]{7,14}", recipient.get("phone", "")):
            raise CommunicationError("El contacto requiere un teléfono E.164 para WhatsApp.")
        if not recipient:
            raise CommunicationError("Choose an existing contact.")
        if not isinstance(text, str) or not text.strip() or len(text) > 10000:
            raise CommunicationError("Message required (maximum 10000 characters).")
        s = schedule_value(schedule)
        when = next_time(s, self._now())
        d.update(contact_id=contact_id, recipient=recipient, text=text, attachments=self._snapshot(attachments, d["id"]),
                 schedule=s, state="draft", next_run_at=when.isoformat(), last_error=None, version=d["version"] + 1,
                 confirmed_at=None, confirmed_revision=None)
        d.pop("authorization", None)
        d.pop("task_request_id", None)
        d["revision"] = self._revision(d)
        if db is not None:
            return self._save(db, d)
        with self._db() as db:
            return self._save(db, d)

    def update_draft(self, draft_id, expected_revision, **fields):
        if set(fields) - {"contact_id", "text", "attachments", "schedule", "conversation_id"}:
            raise CommunicationError("Unknown draft field.")
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            d = self._get(db, draft_id)
            if d["revision"] != expected_revision:
                raise CommunicationError("Draft revision changed.", 409)
            if d["state"] in {"sending", "sent", "uncertain", "cancelled"}:
                raise CommunicationError("This draft cannot be edited; create a new draft.", 409)
            if d["workspace_root"] != str(self._workspace()):
                raise CommunicationError("Switch to the draft workspace before editing.", 409)
            return self._prepare(d, fields.get("contact_id", d["contact_id"]), fields.get("text", d["text"]),
                fields.get("attachments", [a["path"] for a in d["attachments"]]), fields.get("schedule", d["schedule"]), db)

    def _validate_attachments(self, d):
        root = Path(d["workspace_root"])
        for a in d["attachments"]:
            p = root / a["path"]
            for candidate in (p, *p.parents):
                if candidate == root.parent:
                    break
                st = candidate.lstat()
                if candidate.is_symlink() or getattr(st, "st_file_attributes", 0) & 1024:
                    raise CommunicationError("Attachment became a reparse point.")
            snapshot = Path(a["snapshot"])
            for candidate in (snapshot, *snapshot.parents):
                if candidate == self.root.parent:
                    break
                st = candidate.lstat()
                if candidate.is_symlink() or getattr(st, "st_file_attributes", 0) & 1024:
                    raise CommunicationError("Snapshot became a reparse point.")
            if not snapshot.resolve().is_relative_to(self.root.resolve()) or digest(p.read_bytes()) != a["sha256"] or digest(snapshot.read_bytes()) != a["sha256"]:
                raise CommunicationError("Attachment changed; review a new revision.")

    def confirm(self, draft_id, expected_revision, confirmed=False):
        if confirmed is not True:
            raise CommunicationError("Explicit confirmation required.")
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            d = self._get(db, draft_id)
            if d["revision"] != expected_revision or d["state"] != "draft":
                raise CommunicationError("Review the current unconfirmed revision.", 409)
            try:
                self._validate_attachments(d)
            except OSError:
                raise CommunicationError("Attachment unavailable.") from None
            d["next_run_at"] = next_time(d["schedule"], self._now()).isoformat()
            d["state"] = "scheduled"
            d["confirmed_at"] = self._now().isoformat()
            d["confirmed_revision"] = d["revision"]
            d["authorization"] = {"kind": "manual_revision", "revision": d["revision"]}
            self._save(db, d)
        if d["schedule"]["kind"] == "now":
            self.tick(draft_id=draft_id)
        return self.get_draft(draft_id)

    def cancel(self, draft_id, expected_revision, confirmed=False):
        if confirmed is not True:
            raise CommunicationError("Explicit confirmation required.")
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            d = self._get(db, draft_id)
            if d["revision"] != expected_revision or d["state"] == "sending":
                raise CommunicationError("Revision changed or operation already in progress.", 409)
            if d["state"] == "sent":
                raise CommunicationError("An executed send cannot be cancelled.", 409)
            d.update(state="cancelled", next_run_at=None)
            return self._save(db, d)

    def runs(self):
        with self._db() as db:
            return [json.loads(r[0]) for r in db.execute("SELECT data FROM runs ORDER BY rowid DESC")]

    def recover(self):
        # Call only after obtaining exclusive server ownership, never each tick.
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            for row in db.execute("SELECT id,data FROM runs").fetchall():
                run = json.loads(row["data"])
                if run["state"] == "sending":
                    run.update(state="uncertain", error="Interrupted attempt; inspect delivery before any new send.", finished_at=self._now().isoformat())
                    db.execute("UPDATE runs SET data=? WHERE id=?", (encoded(run), run["id"]))
                    d = self._get(db, run["draft_id"])
                    d.update(state="uncertain", next_run_at=None, last_error=run["error"])
                    self._save(db, d)

    def _stopping(self, should_stop=None):
        try:
            return bool(self.stop_requested() or (should_stop and should_stop()))
        except Exception:
            return True

    def tick(self, draft_id=None, should_stop=None):
        # Transactional unique claim persists before any browser effect.
        for item in self.drafts():
            if self._stopping(should_stop):
                break
            if draft_id and item["id"] != draft_id:
                continue
            now = self._now()
            with self._db() as db:
                db.execute("BEGIN IMMEDIATE")
                d = self._get(db, item["id"])
                if d["state"] != "scheduled" or instant(d["next_run_at"]) > now:
                    continue
                if now - instant(d["next_run_at"]) > timedelta(minutes=5):
                    d.update(state="needs_review", last_error="Missed five-minute execution window.", next_run_at=None)
                    self._save(db, d)
                    continue
                run = {"id": "send_" + uuid.uuid4().hex, "draft_id": d["id"], "occurrence_at": d["next_run_at"],
                       "started_at": now.isoformat(), "finished_at": None, "state": "sending", "receipt": None, "error": None,
                       "revision": d["revision"], "confirmed_at": d.get("confirmed_at"),
                       "reviewed": {k: d[k] for k in ("recipient", "text", "attachments", "schedule")}}
                automatic = (d.get("authorization") or {}).get("kind") == "channel_task"
                if automatic:
                    try:
                        self._validate_automatic_dispatch(db, d)
                    except CommunicationError as error:
                        d.update(state="needs_review", next_run_at=None, last_error=str(error))
                        self._save(db, d)
                        continue
                    run["authorization"] = d["authorization"]
                elif d.get("confirmed_revision") != d["revision"]:
                    d.update(state="needs_review", next_run_at=None, last_error="Authorization revision does not match.")
                    self._save(db, d)
                    continue
                try:
                    db.execute("INSERT INTO runs VALUES (?,?,?,?)", (run["id"], d["id"], d["next_run_at"], encoded(run)))
                except sqlite3.IntegrityError:
                    continue
                d["state"] = "sending"
                self._save(db, d)
            try:
                self._validate_attachments(d)
                if self.session is None or self.session.status().get("state") != "connected":
                    raise CommunicationError("WhatsApp session is not connected.")
            except Exception:
                receipt = None
                state, error = "failed", "Session or reviewed attachment unavailable; no send attempted."
            else:
                try:
                    # This durable admission is the revocation/STOP boundary.
                    # A revoke committed first blocks dispatch; an already
                    # admitted transport is in flight and is never undone.
                    with self._db() as db:
                        db.execute("BEGIN IMMEDIATE")
                        if self._stopping(should_stop):
                            raise CommunicationError("STOP before transport admission.", 409)
                        self._validate_automatic_dispatch(db, d)
                        run["transport_admitted_at"] = self._now().isoformat()
                        db.execute("UPDATE runs SET data=? WHERE id=?", (encoded(run), run["id"]))
                except CommunicationError as rejected:
                    receipt = None
                    state, error = "failed", str(rejected)
                else:
                    try:
                        receipt = self.session.send(d["recipient"]["phone"], d["text"], [Path(a["snapshot"]) for a in d["attachments"]], run["id"])
                        if not isinstance(receipt, dict) or receipt.get("operation_id") != run["id"] or receipt.get("status") not in {"sent", "failed", "uncertain"} or not receipt.get("observed_at"):
                            receipt = None
                            state, error = "uncertain", "Transport receipt missing or mismatched."
                        else:
                            state, error = receipt["status"], None if receipt["status"] == "sent" else "Transport did not verify delivery."
                    except Exception:
                        receipt = None
                        state, error = "uncertain", "Transport interrupted; delivery requires review."
            with self._db() as db:
                db.execute("BEGIN IMMEDIATE")
                run.update(state=state, receipt=receipt, error=error, finished_at=self._now().isoformat())
                db.execute("UPDATE runs SET data=? WHERE id=?", (encoded(run), run["id"]))
                d.update(state=state, last_error=error, next_run_at=None)
                if state == "sent" and d["schedule"]["kind"] in {"daily", "weekly"}:
                    try:
                        d.update(state="scheduled", next_run_at=next_time(d["schedule"], self._now()).isoformat())
                    except CommunicationError:
                        d.update(state="needs_review", last_error="Next local occurrence needs DST review.")
                self._save(db, d)
