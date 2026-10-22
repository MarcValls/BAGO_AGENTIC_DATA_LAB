"""SQLite WAL ledger and atomic one-use PermitV1 dispatch reservation.

The ledger reserves authority only. It never invokes an executor or makes
``/ws/agents/run`` available. A committed dispatch intent with no terminal
receipt is uncertain and must be reconciled; it is never automatically retried.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterator, Mapping
from contextlib import contextmanager
from jsonschema import Draft202012Validator, FormatChecker

from src.execution.identity import AuthenticatedPrincipal
from src.execution.permit.permit_v1 import (
    PermitError,
    PermitKeyRegistry,
    PermitV1,
    PermitVerificationContext,
    verify_permit,
)


_EVENT_KINDS = {
    "STARTED", "EFFECT_OBSERVED", "FAILED",
    "PROPOSED", "POLICY_DECIDED", "APPROVAL_REQUESTED", "APPROVED", "REJECTED",
    "CANCELLED", "DENIED", "EXPIRED", "RECEIPT_PERSISTED", "CONTROL_FAILED",
    "PERMIT_ISSUED", "PERMIT_CONSUMED", "DISPATCH_INTENT", "REPLAY_DENIED",
    "REVOKED", "RECONCILIATION_REQUIRED", "TERMINAL_RECEIPT_PERSISTED",
    "VERIFICATION_RESULT_PERSISTED",
}


class LedgerError(RuntimeError):
    """A ledger operation failed closed or violated its durable contract."""


class StoreUnavailableError(LedgerError):
    """The durable store could not confirm a pre-effect transaction."""


class PermitReplayError(LedgerError):
    """The single-use permit has already been consumed or cannot be reused."""


@dataclass(frozen=True)
class LedgerEvent:
    contract_version: str
    event_id: str
    request_id: str
    run_id: str
    seq: int
    prev_hash: str | None
    event_digest: str
    kind: str
    timestamp: str
    payload_ref: str
    proposal_id: str
    proposal_digest: str
    request_digest: str | None
    attempt_id: str | None
    permit_id: str | None
    sandbox_receipt_id: str | None = None
    decision_id: str | None = None
    approval_id: str | None = None
    job_id: str | None = None
    boundary_receipt_id: str | None = None
    verification_result_id: str | None = None

    def to_dict(self) -> dict[str, object]:
        return dict(self.__dict__)


@dataclass(frozen=True)
class TerminalVerification:
    receipt_id: str
    verification_result_id: str
    request_id: str
    request_digest: str
    permit_id: str
    attempt_id: str
    receipt: dict[str, object]
    result_state: str
    executor_output_sha256: str | None
    observed_output_sha256: str | None
    verification_state: str


def _canonical(value: object) -> bytes:
    """JCS for this event's I-JSON subset (strings, nulls and safe integers)."""
    def enc(item: object) -> str:
        if item is None:
            return "null"
        if item is True:
            return "true"
        if item is False:
            return "false"
        if isinstance(item, int) and not isinstance(item, bool):
            if abs(item) > 9007199254740991:
                raise LedgerError("event integer is outside the I-JSON safe range")
            return str(item)
        if isinstance(item, str):
            return json.dumps(item, ensure_ascii=False, separators=(",", ":"))
        if isinstance(item, list):
            return "[" + ",".join(enc(v) for v in item) + "]"
        if isinstance(item, Mapping):
            keys = sorted(item, key=lambda key: key.encode("utf-16-be", errors="strict"))
            return "{" + ",".join(enc(k) + ":" + enc(item[k]) for k in keys) + "}"
        raise LedgerError(f"unsupported event value: {type(item).__name__}")
    try:
        return enc(value).encode("utf-8", errors="strict")
    except (UnicodeEncodeError, AttributeError) as exc:
        raise LedgerError("event contains invalid JCS data") from exc


def _stamp(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamps must include a timezone")
    return value.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _principal_session_active(principal: AuthenticatedPrincipal) -> bool:
    """Placeholder only when an integrator explicitly supplies a live resolver."""
    return False


class ExecutionLedger:
    """Single-host SQLite WAL ledger with a transactional PermitV1 CAS."""

    def __init__(self, database_path: Path | str, *, event_profile: str = "legacy"):
        if event_profile not in {"legacy", "runtime"}:
            raise LedgerError("unknown ledger event profile")
        self.event_profile = event_profile
        schema = json.loads(Path(__file__).with_name("gex_event_schema.json").read_text(encoding="utf-8"))
        self._event_validator = Draft202012Validator({"$ref": "#/$defs/LedgerEventV1", "$defs": schema["$defs"]}, format_checker=FormatChecker())
        self.database_path = Path(database_path).expanduser().resolve()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.database_path, timeout=10, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA synchronous=FULL")
        db.execute("PRAGMA busy_timeout=10000")
        return db

    def _initialize(self) -> None:
        try:
            with self._connect() as db:
                mode = db.execute("PRAGMA journal_mode=WAL").fetchone()[0]
                if str(mode).lower() != "wal":
                    raise StoreUnavailableError("SQLite WAL mode is unavailable")
                db.executescript("""
                    CREATE TABLE IF NOT EXISTS requests(
                        request_id TEXT PRIMARY KEY, run_id TEXT NOT NULL,
                        proposal_id TEXT NOT NULL, proposal_digest TEXT NOT NULL,
                        request_digest TEXT NOT NULL UNIQUE
                    );
                    CREATE TABLE IF NOT EXISTS permits(
                        permit_id TEXT PRIMARY KEY, request_id TEXT NOT NULL REFERENCES requests(request_id),
                        request_digest TEXT NOT NULL UNIQUE, state TEXT NOT NULL CHECK(state IN ('ISSUED','CONSUMED','REVOKED','EXPIRED')),
                        uses INTEGER NOT NULL CHECK(uses IN (0,1)), db_version INTEGER NOT NULL,
                        expires_at TEXT NOT NULL, consumed_at TEXT, attempt_id TEXT UNIQUE
                    );
                    CREATE TABLE IF NOT EXISTS attempts(
                        attempt_id TEXT PRIMARY KEY, request_id TEXT NOT NULL REFERENCES requests(request_id),
                        permit_id TEXT NOT NULL UNIQUE REFERENCES permits(permit_id), state TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS ledger_events(
                        event_id TEXT PRIMARY KEY, request_id TEXT NOT NULL REFERENCES requests(request_id),
                        run_id TEXT NOT NULL, seq INTEGER NOT NULL, prev_hash TEXT, event_digest TEXT NOT NULL,
                        kind TEXT NOT NULL, timestamp TEXT NOT NULL, payload_ref TEXT NOT NULL,
                        proposal_id TEXT NOT NULL, proposal_digest TEXT NOT NULL, request_digest TEXT,
                        attempt_id TEXT, permit_id TEXT, sandbox_receipt_id TEXT, decision_id TEXT,
                        approval_id TEXT, job_id TEXT, boundary_receipt_id TEXT, verification_result_id TEXT,
                        UNIQUE(request_id, seq)
                    );
                    CREATE TABLE IF NOT EXISTS permit_revocations(
                        permit_id TEXT PRIMARY KEY REFERENCES permits(permit_id), revoked_at TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS terminal_receipts(
                        receipt_id TEXT PRIMARY KEY, attempt_id TEXT NOT NULL UNIQUE REFERENCES attempts(attempt_id),
                        request_id TEXT NOT NULL REFERENCES requests(request_id), request_digest TEXT NOT NULL,
                        permit_id TEXT NOT NULL REFERENCES permits(permit_id), receipt_json TEXT NOT NULL,
                        receipt_sha256 TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS verification_results(
                        verification_result_id TEXT PRIMARY KEY,
                        receipt_id TEXT NOT NULL UNIQUE REFERENCES terminal_receipts(receipt_id),
                        attempt_id TEXT NOT NULL UNIQUE REFERENCES attempts(attempt_id),
                        request_id TEXT NOT NULL REFERENCES requests(request_id), request_digest TEXT NOT NULL,
                        permit_id TEXT NOT NULL REFERENCES permits(permit_id), result_json TEXT NOT NULL,
                        result_sha256 TEXT NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS ledger_events_request_seq ON ledger_events(request_id,seq);
                    CREATE TABLE IF NOT EXISTS control_records(
                        request_id TEXT PRIMARY KEY REFERENCES requests(request_id),
                        principal_id TEXT NOT NULL, workspace_id TEXT NOT NULL, agent_id TEXT NOT NULL,
                        record_json TEXT NOT NULL, record_sha256 TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS ingress_denials(
                        denial_id TEXT PRIMARY KEY, code TEXT NOT NULL, timestamp TEXT NOT NULL,
                        seq INTEGER NOT NULL UNIQUE, prev_hash TEXT, event_digest TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS gex_ingress_artifacts(
                        seq INTEGER PRIMARY KEY, denial_id TEXT NOT NULL UNIQUE,
                        receipt_json TEXT NOT NULL, receipt_sha256 TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS gex_runtime_verifications(
                        verification_id TEXT PRIMARY KEY, request_id TEXT NOT NULL REFERENCES requests(request_id),
                        attempt_id TEXT NOT NULL UNIQUE REFERENCES attempts(attempt_id),
                        result_json TEXT NOT NULL, result_sha256 TEXT NOT NULL
                    );
                """)
                # Additive migration for provisioned-but-unused early runtime
                # stores. Never replace authority keys/configuration or rows.
                columns = {row["name"] for row in db.execute("PRAGMA table_info(ingress_denials)")}
                added = False
                for name, declaration in (("seq", "INTEGER"), ("prev_hash", "TEXT"), ("event_digest", "TEXT")):
                    if name not in columns:
                        db.execute("ALTER TABLE ingress_denials ADD COLUMN " + name + " " + declaration)
                        added = True
                if added:
                    previous = None
                    for seq, row in enumerate(db.execute("SELECT rowid,* FROM ingress_denials ORDER BY rowid").fetchall()):
                        entry = {"denial_id": row["denial_id"], "code": row["code"], "timestamp": row["timestamp"],
                                 "seq": seq, "prev_hash": previous}
                        previous = hashlib.sha256(_canonical(entry)).hexdigest()
                        db.execute("UPDATE ingress_denials SET seq=?,prev_hash=?,event_digest=? WHERE rowid=?",
                                   (seq, entry["prev_hash"], previous, row["rowid"]))
            self._recover_uncertain_attempts()
        except (sqlite3.Error, OSError) as exc:
            raise StoreUnavailableError("durable ledger initialization failed") from exc

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        db = self._connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.execute("COMMIT")
        except Exception:
            try:
                db.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            raise
        finally:
            db.close()

    def _recover_uncertain_attempts(self) -> None:
        """After restart, conservatively reconcile every committed intent."""
        try:
            with self._transaction() as db:
                pending = db.execute("""SELECT a.attempt_id,a.request_id,a.permit_id,r.run_id,
                    r.proposal_id,r.proposal_digest,p.request_digest
                    FROM attempts a JOIN requests r USING(request_id) JOIN permits p USING(permit_id)
                    WHERE a.state='DISPATCH_INTENT'""").fetchall()
                for row in pending:
                    db.execute("UPDATE attempts SET state='RECONCILIATION_REQUIRED' WHERE attempt_id=? AND state='DISPATCH_INTENT'",
                               (row["attempt_id"],))
                    self._append_event(db, request_id=row["request_id"], run_id=row["run_id"],
                        proposal_id=row["proposal_id"], proposal_digest=row["proposal_digest"],
                        request_digest=row["request_digest"], permit_id=row["permit_id"],
                        attempt_id=row["attempt_id"], kind="RECONCILIATION_REQUIRED",
                        now=datetime.now(timezone.utc))
        except sqlite3.Error as exc:
            raise StoreUnavailableError("restart recovery could not persist reconciliation state") from exc

    def _append_event(self, db: sqlite3.Connection, *, request_id: str, run_id: str,
                      proposal_id: str, proposal_digest: str, request_digest: str,
                      permit_id: str, attempt_id: str | None, kind: str, now: datetime,
                      sandbox_receipt_id: str | None = None,
                      boundary_receipt_id: str | None = None,
                      verification_result_id: str | None = None,
                      artifact_sha256: str | None = None,
                      artifact_prefix: str = "ledger-artifact-sha256:") -> LedgerEvent:
        if kind not in _EVENT_KINDS:
            raise LedgerError("unsupported ledger event kind")
        if self.event_profile == "runtime":
            kind = {"TERMINAL_RECEIPT_PERSISTED": "RECEIPT_PERSISTED", "CONTROL_FAILED": "FAILED",
                    "VERIFICATION_RESULT_PERSISTED": "EFFECT_OBSERVED" if artifact_prefix == "ledger-artifact-sha256:" else "VERIFICATION_RESULT_PERSISTED"}.get(kind, kind)
        decision_id, approval_id = None, None
        if self.event_profile == "runtime":
            record = db.execute("SELECT record_json FROM control_records WHERE request_id=?", (request_id,)).fetchone()
            if record is not None:
                control = json.loads(record["record_json"])
                decision_id = (control.get("policy_decision") or {}).get("decision_id")
                approval_id = (control.get("approval") or {}).get("approval_id")
        last = db.execute("SELECT seq,event_digest FROM ledger_events WHERE request_id=? ORDER BY seq DESC LIMIT 1", (request_id,)).fetchone()
        seq = 0 if last is None else int(last["seq"]) + 1
        prev = None if last is None else str(last["event_digest"])
        event = {
            "contract_version": "gex-ledger-event/v1", "event_id": "gexevent_" + uuid.uuid4().hex,
            "request_id": request_id, "run_id": run_id, "seq": seq, "prev_hash": prev,
            "kind": kind, "timestamp": _stamp(now),
            "payload_ref": (artifact_prefix + artifact_sha256 if artifact_sha256
                            else "event-payload:embedded-minimal-v1"),
            "proposal_id": proposal_id, "proposal_digest": proposal_digest,
            "request_digest": request_digest, "attempt_id": attempt_id, "permit_id": permit_id,
            "sandbox_receipt_id": sandbox_receipt_id, "decision_id": decision_id, "approval_id": approval_id, "job_id": None,
            "boundary_receipt_id": boundary_receipt_id, "verification_result_id": verification_result_id,
        }
        event["event_digest"] = hashlib.sha256(_canonical(event)).hexdigest()
        if self.event_profile == "runtime":
            self._event_validator.validate(event)
        db.execute("""INSERT INTO ledger_events(event_id,request_id,run_id,seq,prev_hash,event_digest,kind,
            timestamp,payload_ref,proposal_id,proposal_digest,request_digest,attempt_id,permit_id,
            sandbox_receipt_id,decision_id,approval_id,job_id,boundary_receipt_id,verification_result_id)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (event["event_id"], request_id, run_id, seq, prev, event["event_digest"], kind,
             event["timestamp"], event["payload_ref"], proposal_id, proposal_digest, request_digest,
             attempt_id, permit_id, sandbox_receipt_id, decision_id, approval_id, None,
             boundary_receipt_id, verification_result_id))
        return LedgerEvent(**event)

    def register_permit(self, *, permit: PermitV1, keys: PermitKeyRegistry,
                        context: PermitVerificationContext, request_id: str, run_id: str,
                        proposal_id: str, proposal_digest: str,
                        now: datetime | None = None) -> None:
        """Verify signed claims then persist their opaque request/run binding."""
        instant = now or context.now
        try:
            verified = verify_permit(permit, keys=keys, context=context)
            claims = verified.to_dict()
            with self._transaction() as db:
                if db.execute("SELECT 1 FROM permit_revocations WHERE permit_id=?", (verified.permit_id,)).fetchone():
                    raise PermitError("permit revoked")
                existing = db.execute("SELECT * FROM requests WHERE request_id=?", (request_id,)).fetchone()
                binding = (request_id, run_id, proposal_id, proposal_digest, verified.request_digest)
                if existing is None:
                    db.execute("INSERT INTO requests VALUES(?,?,?,?,?)", binding)
                elif tuple(existing) != binding:
                    raise LedgerError("existing request bindings differ; registration denied")
                db.execute("INSERT INTO permits VALUES(?,?,?,?,?,?,?,?,?)", (
                    verified.permit_id, request_id, verified.request_digest, "ISSUED", 0, 0,
                    claims["expires_at"], None, None))
                self._append_event(db, request_id=request_id, run_id=run_id,
                    proposal_id=proposal_id, proposal_digest=proposal_digest,
                    request_digest=verified.request_digest, permit_id=verified.permit_id,
                    attempt_id=None, kind="PERMIT_ISSUED", now=instant)
        except PermitError as exc:
            raise LedgerError("PermitV1 verification failed; registration denied") from exc
        except (sqlite3.Error, OSError) as exc:
            raise StoreUnavailableError("permit registration was not durably committed") from exc

    def consume_for_dispatch(self, *, permit: PermitV1, keys: PermitKeyRegistry,
                             context: PermitVerificationContext, request_id: str,
                             attempt_id: str | None = None, now: datetime | None = None,
                             failpoint: Callable[[str], None] | None = None,
                             live_authority: Callable[[], None] | None = None) -> str:
        """Verify, CAS consume and persist both required events atomically.

        Returns the unique attempt id only after COMMIT. This method does not
        dispatch; the caller must treat the returned value as a reservation.
        """
        attempt = attempt_id or "gexattempt_" + uuid.uuid4().hex
        instant = now or context.now
        replay_error: str | None = None
        try:
            with self._transaction() as db:
                if live_authority is not None:
                    live_authority()
                    instant = datetime.now(timezone.utc)
                row = db.execute("""SELECT p.*,r.run_id,r.proposal_id,r.proposal_digest
                    FROM permits p JOIN requests r USING(request_id)
                    WHERE p.permit_id=? AND p.request_id=?""", (permit.permit_id, request_id)).fetchone()
                if row is None:
                    raise PermitReplayError("permit is not registered for this request")
                if row["state"] != "ISSUED" or row["uses"] != 0:
                    self._append_event(db, request_id=request_id, run_id=row["run_id"],
                        proposal_id=row["proposal_id"], proposal_digest=row["proposal_digest"],
                        request_digest=row["request_digest"], permit_id=permit.permit_id,
                        attempt_id=attempt, kind="REPLAY_DENIED", now=instant)
                    replay_error = "permit already consumed, revoked, or expired"
                if replay_error is None and failpoint:
                    failpoint("before_verification")
                live_context = PermitVerificationContext(
                    request_digest=context.request_digest, principal=context.principal, now=instant,
                    is_revoked=lambda permit_id: bool(db.execute(
                        "SELECT 1 FROM permit_revocations WHERE permit_id=?", (permit_id,)).fetchone()),
                    is_session_active=context.is_session_active,
                )
                if replay_error is None:
                    verified = verify_permit(permit, keys=keys, context=live_context)
                    if verified.request_digest != row["request_digest"]:
                        raise PermitReplayError("registered request binding mismatch")
                    if live_authority is not None:
                        live_authority()
                        instant = datetime.now(timezone.utc)
                        verified = verify_permit(permit, keys=keys, context=PermitVerificationContext(
                            request_digest=context.request_digest, principal=context.principal, now=instant,
                            is_revoked=live_context.is_revoked, is_session_active=context.is_session_active))
                    updated = db.execute("""UPDATE permits SET state='CONSUMED',uses=1,db_version=db_version+1,
                    consumed_at=?,attempt_id=? WHERE permit_id=? AND state='ISSUED' AND uses=0 AND db_version=0""",
                    (_stamp(instant), attempt, permit.permit_id))
                    if updated.rowcount != 1:
                        raise PermitReplayError("permit compare-and-swap lost")
                    db.execute("INSERT INTO attempts VALUES(?,?,?,?)", (attempt, request_id, permit.permit_id, "DISPATCH_INTENT"))
                    args = dict(request_id=request_id, run_id=row["run_id"], proposal_id=row["proposal_id"],
                        proposal_digest=row["proposal_digest"], request_digest=row["request_digest"],
                        permit_id=permit.permit_id, attempt_id=attempt, now=instant)
                    self._append_event(db, kind="PERMIT_CONSUMED", **args)
                    if failpoint:
                        failpoint("after_consumed_event")
                    self._append_event(db, kind="DISPATCH_INTENT", **args)
                    if failpoint:
                        failpoint("before_commit")
            if replay_error:
                raise PermitReplayError(replay_error)
            return attempt
        except PermitReplayError:
            raise
        except PermitError as exc:
            raise LedgerError("PermitV1 verification failed; dispatch denied") from exc
        except (sqlite3.Error, OSError) as exc:
            raise StoreUnavailableError("atomic permit reservation failed; dispatch denied") from exc
        except Exception as exc:
            if failpoint is not None:
                raise StoreUnavailableError("atomic reservation aborted by storage failure") from exc
            raise

    def revoke_permit(self, permit_id: str, *, now: datetime | None = None) -> None:
        instant = now or datetime.now(timezone.utc)
        try:
            with self._transaction() as db:
                row = db.execute("SELECT p.*,r.run_id,r.proposal_id,r.proposal_digest FROM permits p JOIN requests r USING(request_id) WHERE permit_id=?", (permit_id,)).fetchone()
                if row is None:
                    raise LedgerError("unknown permit")
                db.execute("INSERT OR IGNORE INTO permit_revocations VALUES(?,?)", (permit_id, _stamp(instant)))
                if row["state"] == "ISSUED":
                    db.execute("UPDATE permits SET state='REVOKED',db_version=db_version+1 WHERE permit_id=? AND state='ISSUED'", (permit_id,))
                self._append_event(db, request_id=row["request_id"], run_id=row["run_id"],
                    proposal_id=row["proposal_id"], proposal_digest=row["proposal_digest"],
                    request_digest=row["request_digest"], permit_id=permit_id, attempt_id=row["attempt_id"],
                    kind="REVOKED", now=instant)
        except sqlite3.Error as exc:
            raise StoreUnavailableError("permit revocation was not durably committed") from exc

    def require_reconciliation(self, attempt_id: str, *, now: datetime | None = None) -> None:
        instant = now or datetime.now(timezone.utc)
        try:
            with self._transaction() as db:
                row = db.execute("""SELECT a.attempt_id,a.request_id,a.permit_id,a.state,
                    r.run_id,r.proposal_id,r.proposal_digest,p.request_digest
                    FROM attempts a JOIN requests r USING(request_id) JOIN permits p USING(permit_id)
                    WHERE a.attempt_id=?""", (attempt_id,)).fetchone()
                if row is None:
                    raise LedgerError("unknown attempt")
                if row["state"] == "RECONCILIATION_REQUIRED":
                    return
                if row["state"] != "DISPATCH_INTENT":
                    raise LedgerError("terminal attempt state cannot be downgraded to reconciliation")
                db.execute("UPDATE attempts SET state='RECONCILIATION_REQUIRED' WHERE attempt_id=? AND state='DISPATCH_INTENT'", (attempt_id,))
                self._append_event(db, request_id=row["request_id"], run_id=row["run_id"],
                    proposal_id=row["proposal_id"], proposal_digest=row["proposal_digest"],
                    request_digest=row["request_digest"], permit_id=row["permit_id"], attempt_id=attempt_id,
                    kind="RECONCILIATION_REQUIRED", now=instant)
        except sqlite3.Error as exc:
            raise StoreUnavailableError("reconciliation state could not be persisted") from exc

    def record_attempt_started(self, attempt_id: str) -> None:
        """Runtime-only durable start marker after CAS, before gateway call."""
        try:
            with self._transaction() as db:
                row = db.execute("""SELECT a.*,r.run_id,r.proposal_id,r.proposal_digest,p.request_digest
                    FROM attempts a JOIN requests r USING(request_id) JOIN permits p USING(permit_id)
                    WHERE a.attempt_id=?""", (attempt_id,)).fetchone()
                if row is None or row["state"] != "DISPATCH_INTENT":
                    raise LedgerError("attempt is not authorized to start")
                self._append_event(db, request_id=row["request_id"], run_id=row["run_id"],
                    proposal_id=row["proposal_id"], proposal_digest=row["proposal_digest"],
                    request_digest=row["request_digest"], permit_id=row["permit_id"], attempt_id=attempt_id,
                    kind="STARTED", now=datetime.now(timezone.utc))
        except (sqlite3.Error, OSError) as exc:
            raise StoreUnavailableError("attempt start could not be persisted") from exc

    def record_control_replay(self, record: Mapping[str, object]) -> None:
        """Append evidence of a terminal API decision without rewriting it."""
        try:
            with self._transaction() as db:
                receipt = record.get("receipt") or {}
                self._append_event(db, request_id=record["request_id"], run_id=record["run_id"],
                    proposal_id=record["proposal_id"], proposal_digest=record["proposal"]["proposal_digest"],
                    request_digest=record["request_digest"], permit_id=(record.get("permit") or {}).get("permit_id"),
                    attempt_id=receipt.get("attempt_id"), kind="REPLAY_DENIED", now=datetime.now(timezone.utc))
        except (sqlite3.Error, OSError) as exc:
            raise StoreUnavailableError("replay denial was not durably committed") from exc

    def persist_terminal_verification(self, *, receipt_id: str,
                                      verification_result_id: str, attempt_id: str,
                                      request_id: str, request_digest: str, permit_id: str,
                                      receipt: Mapping[str, object], result_state: str,
                                      executor_output_sha256: str | None,
                                      observed_output_sha256: str | None,
                                      now: datetime | None = None) -> TerminalVerification:
        """Atomically persist the executor receipt and separate verifier result.

        Only a live DISPATCH_INTENT can be terminalized. Startup recovery changes
        unresolved attempts to RECONCILIATION_REQUIRED, which cannot be promoted.
        """
        instant = now or datetime.now(timezone.utc)
        if not all((receipt_id, verification_result_id, attempt_id, request_id, request_digest, permit_id)):
            raise LedgerError("terminal result bindings must be non-empty")
        try:
            receipt_data = dict(receipt)
            if (receipt_data.get("receipt_id") != receipt_id
                    or receipt_data.get("request_id") != request_id
                    or receipt_data.get("permit_id") != permit_id):
                raise LedgerError("executor receipt bindings do not match terminal result")
            if result_state not in {"EXECUTOR_SUCCESS", "EXECUTOR_FAILURE"}:
                raise LedgerError("uncertain executor outcomes cannot be terminalized")
            success = result_state == "EXECUTOR_SUCCESS"
            receipt_status = receipt_data.get("status")
            if receipt_status not in {"SUCCESS", "DENIED", "FAILURE", "TIMEOUT"}:
                raise LedgerError("executor receipt has an unknown terminal status")
            if success != (receipt_status == "SUCCESS"):
                raise LedgerError("executor result state disagrees with receipt status")
            hashes_valid = all(isinstance(value, str) and len(value) == 64
                               and all(c in "0123456789abcdef" for c in value)
                               for value in (executor_output_sha256, observed_output_sha256))
            matched = bool(success and hashes_valid
                           and executor_output_sha256 == observed_output_sha256)
            verification_state = "VERIFIED_SUCCESS" if matched else "VERIFICATION_FAILED"
            attempt_state = "VERIFIED_SUCCESS" if matched else "FAILED_CLOSED"
            verification = {
                "contract_version": "gex-verification-result/v1",
                "verification_result_id": verification_result_id,
                "receipt_id": receipt_id,
                "request_id": request_id,
                "request_digest": request_digest,
                "permit_id": permit_id,
                "attempt_id": attempt_id,
                "executor_output_sha256": executor_output_sha256,
                "observed_output_sha256": observed_output_sha256,
                "verification_state": verification_state,
            }
            receipt_json = _canonical(receipt_data).decode("utf-8")
            receipt_digest = hashlib.sha256(receipt_json.encode("utf-8")).hexdigest()
            result_json = _canonical(verification).decode("utf-8")
            result_digest = hashlib.sha256(result_json.encode("utf-8")).hexdigest()
            with self._transaction() as db:
                row = db.execute("""SELECT a.state,a.request_id,a.permit_id,r.run_id,
                    r.proposal_id,r.proposal_digest,p.request_digest
                    FROM attempts a JOIN requests r USING(request_id)
                    JOIN permits p USING(permit_id) WHERE a.attempt_id=?""", (attempt_id,)).fetchone()
                if row is None:
                    raise LedgerError("terminal result references an unknown attempt")
                if row["state"] != "DISPATCH_INTENT":
                    raise LedgerError("attempt is not live; replay or reconciliation cannot be promoted")
                if (row["request_id"] != request_id or row["permit_id"] != permit_id
                        or row["request_digest"] != request_digest):
                    raise LedgerError("terminal result does not match durable request/permit bindings")
                db.execute("INSERT INTO terminal_receipts VALUES(?,?,?,?,?,?,?)", (
                    receipt_id, attempt_id, request_id, request_digest, permit_id,
                    receipt_json, receipt_digest))
                self._append_event(db, request_id=request_id, run_id=row["run_id"],
                    proposal_id=row["proposal_id"], proposal_digest=row["proposal_digest"],
                    request_digest=request_digest, permit_id=permit_id, attempt_id=attempt_id,
                    kind="TERMINAL_RECEIPT_PERSISTED", now=instant,
                    sandbox_receipt_id=receipt_id, boundary_receipt_id=receipt_id,
                    artifact_sha256=receipt_digest)
                db.execute("INSERT INTO verification_results VALUES(?,?,?,?,?,?,?,?)", (
                    verification_result_id, receipt_id, attempt_id, request_id,
                    request_digest, permit_id, result_json, result_digest))
                self._append_event(db, request_id=request_id, run_id=row["run_id"],
                    proposal_id=row["proposal_id"], proposal_digest=row["proposal_digest"],
                    request_digest=request_digest, permit_id=permit_id, attempt_id=attempt_id,
                    kind="VERIFICATION_RESULT_PERSISTED", now=instant,
                    sandbox_receipt_id=receipt_id, boundary_receipt_id=receipt_id,
                    verification_result_id=verification_result_id,
                    artifact_sha256=result_digest)
                db.execute("UPDATE attempts SET state=? WHERE attempt_id=? AND state='DISPATCH_INTENT'",
                           (attempt_state, attempt_id))
            return TerminalVerification(receipt_id, verification_result_id, request_id,
                request_digest, permit_id, attempt_id, receipt_data, result_state,
                executor_output_sha256, observed_output_sha256, verification_state)
        except LedgerError:
            raise
        except (sqlite3.Error, OSError) as exc:
            raise StoreUnavailableError("terminal receipt and verification were not durably committed") from exc

    def terminal_verification(self, attempt_id: str) -> TerminalVerification | None:
        try:
            with self._connect() as db:
                row = db.execute("""SELECT tr.*,vr.verification_result_id,vr.result_json,
                    vr.result_sha256,vr.request_id AS vr_request_id,vr.request_digest AS vr_request_digest,
                    vr.permit_id AS vr_permit_id,vr.attempt_id AS vr_attempt_id,
                    a.state AS attempt_state
                    FROM terminal_receipts tr JOIN verification_results vr USING(attempt_id)
                    JOIN attempts a USING(attempt_id)
                    WHERE tr.attempt_id=?""", (attempt_id,)).fetchone()
            if row is None:
                return None
            receipt_json, result_json = str(row["receipt_json"]), str(row["result_json"])
            if (hashlib.sha256(receipt_json.encode("utf-8")).hexdigest() != row["receipt_sha256"]
                    or hashlib.sha256(result_json.encode("utf-8")).hexdigest() != row["result_sha256"]):
                raise LedgerError("durable terminal artifact digest mismatch")
            result = json.loads(result_json)
            receipt_data = json.loads(receipt_json)
            events = [e for e in self.events_for_request(str(row["request_id"]))
                      if e.attempt_id == attempt_id]
            receipt_event_index = next((i for i, e in enumerate(events)
                if e.kind == ("RECEIPT_PERSISTED" if self.event_profile == "runtime" else "TERMINAL_RECEIPT_PERSISTED") and e.sandbox_receipt_id == row["receipt_id"]
                and e.boundary_receipt_id == row["receipt_id"]
                and e.payload_ref == "ledger-artifact-sha256:" + str(row["receipt_sha256"])), None)
            result_event_index = next((i for i, e in enumerate(events)
                if e.kind == ("EFFECT_OBSERVED" if self.event_profile == "runtime" else "VERIFICATION_RESULT_PERSISTED") and e.sandbox_receipt_id == row["receipt_id"]
                and e.boundary_receipt_id == row["receipt_id"]
                and e.verification_result_id == row["verification_result_id"]
                and e.payload_ref == "ledger-artifact-sha256:" + str(row["result_sha256"])), None)
            expected_attempt_state = ("VERIFIED_SUCCESS" if result.get("verification_state") == "VERIFIED_SUCCESS"
                                      else "FAILED_CLOSED")
            executor_hash, observed_hash = (result.get("executor_output_sha256"),
                                            result.get("observed_output_sha256"))
            hashes_valid = all(isinstance(value, str) and len(value) == 64
                               and all(c in "0123456789abcdef" for c in value)
                               for value in (executor_hash, observed_hash))
            expected_verification_state = (
                "VERIFIED_SUCCESS" if receipt_data.get("status") == "SUCCESS"
                and hashes_valid and executor_hash == observed_hash else "VERIFICATION_FAILED")
            bindings_match = (
                receipt_data.get("receipt_id") == row["receipt_id"]
                and receipt_data.get("request_id") == row["request_id"]
                and receipt_data.get("permit_id") == row["permit_id"]
                and result.get("verification_result_id") == row["verification_result_id"]
                and result.get("receipt_id") == row["receipt_id"]
                and result.get("request_id") == row["request_id"]
                and result.get("request_digest") == row["request_digest"]
                and result.get("permit_id") == row["permit_id"]
                and result.get("attempt_id") == attempt_id
                and row["vr_request_id"] == row["request_id"]
                and row["vr_request_digest"] == row["request_digest"]
                and row["vr_permit_id"] == row["permit_id"]
                and row["vr_attempt_id"] == attempt_id
                and row["attempt_state"] == expected_attempt_state
                and result.get("verification_state") == expected_verification_state
                and self.verify_event_chain(str(row["request_id"]))
                and receipt_event_index is not None and result_event_index is not None
                and receipt_event_index < result_event_index
            )
            if not bindings_match:
                raise LedgerError("durable terminal artifact bindings or event chain mismatch")
            return TerminalVerification(row["receipt_id"], row["verification_result_id"],
                row["request_id"], row["request_digest"], row["permit_id"], attempt_id,
                receipt_data, "EXECUTOR_SUCCESS" if receipt_data.get("status") == "SUCCESS" else "EXECUTOR_FAILURE",
                result.get("executor_output_sha256"), result.get("observed_output_sha256"),
                result["verification_state"])
        except LedgerError:
            raise
        except (sqlite3.Error, OSError, ValueError, TypeError) as exc:
            raise StoreUnavailableError("durable terminal result could not be read") from exc

    def events_for_request(self, request_id: str) -> list[LedgerEvent]:
        with self._connect() as db:
            rows = db.execute("SELECT * FROM ledger_events WHERE request_id=? ORDER BY seq", (request_id,)).fetchall()
        values = [LedgerEvent(contract_version="gex-ledger-event/v1", **dict(row)) for row in rows]
        if self.event_profile == "runtime":
            for value in values:
                try:
                    self._event_validator.validate(value.to_dict())
                except Exception:
                    raise LedgerError("durable event violates runtime schema") from None
        return values

    def save_control(self, record: Mapping[str, object], *, principal_id: str,
                     workspace_id: str, agent_id: str, kind: str,
                     create: bool = False, now: datetime | None = None) -> None:
        """Commit a control snapshot and its content-addressed chain event together.

        No secrets are accepted here by the control plane. The immutable whole
        request/provenance binding cannot be replaced by a later decision.
        """
        data = dict(record)
        raw = _canonical(data).decode("utf-8")
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        request_id = str(data["request_id"])
        proposal = data["proposal"]
        try:
            with self._transaction() as db:
                old = db.execute("SELECT * FROM control_records WHERE request_id=?", (request_id,)).fetchone()
                if create:
                    if old is not None:
                        raise LedgerError("control request already exists")
                    db.execute("INSERT INTO requests VALUES(?,?,?,?,?)", (
                        request_id, data["run_id"], data["proposal_id"], proposal["proposal_digest"],
                        data["request_digest"] or hashlib.sha256(
                            b"ADL:GEX:UNREGISTERED:v1\n" + request_id.encode("utf-8")
                            + proposal["proposal_digest"].encode("ascii")).hexdigest()))
                    db.execute("INSERT INTO control_records VALUES(?,?,?,?,?,?)", (
                        request_id, principal_id, workspace_id, agent_id, raw, digest))
                else:
                    if old is None or (old["principal_id"], old["workspace_id"], old["agent_id"]) != (principal_id, workspace_id, agent_id):
                        raise LedgerError("control owner binding mismatch")
                    previous = json.loads(old["record_json"])
                    for key in ("request", "request_digest", "task", "provider", "proposal", "run_id", "proposal_id", "_provenance", "_proposal_envelope"):
                        if previous[key] != data[key]:
                            raise LedgerError("immutable control snapshot mutation denied")
                    db.execute("UPDATE control_records SET record_json=?,record_sha256=? WHERE request_id=?", (raw, digest, request_id))
                self._append_event(db, request_id=request_id, run_id=str(data["run_id"]),
                    proposal_id=str(data["proposal_id"]), proposal_digest=proposal["proposal_digest"],
                    request_digest=data["request_digest"], permit_id=(data.get("permit") or {}).get("permit_id"),
                    attempt_id=(data.get("receipt") or {}).get("attempt_id"), kind=kind,
                    now=now or datetime.now(timezone.utc), artifact_sha256=digest,
                    artifact_prefix="control-artifact-sha256:")
        except (sqlite3.Error, OSError) as exc:
            raise StoreUnavailableError("control record was not durably committed") from exc

    def read_control(self, request_id: str, *, principal_id: str,
                     workspace_id: str, agent_id: str) -> dict[str, object] | None:
        try:
            with self._connect() as db:
                row = db.execute("SELECT * FROM control_records WHERE request_id=? AND principal_id=? AND workspace_id=? AND agent_id=?",
                    (request_id, principal_id, workspace_id, agent_id)).fetchone()
            if row is None:
                return None
            raw = str(row["record_json"])
            if hashlib.sha256(raw.encode("utf-8")).hexdigest() != row["record_sha256"]:
                raise LedgerError("control artifact digest mismatch")
            data = json.loads(raw)
            events = self.events_for_request(request_id)
            anchors = [e for e in events if e.payload_ref.startswith("control-artifact-sha256:")]
            if (not self.verify_event_chain(request_id) or not anchors
                    or anchors[-1].payload_ref != "control-artifact-sha256:" + str(row["record_sha256"])
                    or data.get("request_id") != request_id):
                raise LedgerError("control event chain mismatch")
            return data
        except (sqlite3.Error, OSError) as exc:
            raise StoreUnavailableError("control record could not be read") from exc

    def record_ingress_denial(self, code: str) -> None:
        """Sanitized ingress audit: no guessed authenticated identity or body."""
        try:
            from src.execution.gex_control import validate
            with self._transaction() as db:
                last = db.execute("SELECT seq,event_digest FROM ingress_denials ORDER BY seq DESC LIMIT 1").fetchone()
                entry = {"denial_id": "gexingress_" + uuid.uuid4().hex, "code": code,
                         "timestamp": _stamp(datetime.now(timezone.utc)),
                         "seq": int(last["seq"]) + 1 if last else 0, "prev_hash": last["event_digest"] if last else None}
                entry["event_digest"] = hashlib.sha256(_canonical(entry)).hexdigest()
                db.execute("INSERT INTO ingress_denials VALUES(?,?,?,?,?,?)", tuple(entry.values()))
                previous = db.execute("SELECT seq,receipt_json FROM gex_ingress_artifacts ORDER BY seq DESC LIMIT 1").fetchone()
                prior = json.loads(previous["receipt_json"])["ingress_event_digest"] if previous else None
                receipt = {"contract_version": "gex-ingress-denial/v1",
                    "receipt_id": "gexingressreceipt_" + uuid.uuid4().hex,
                    "ingress_id": entry["denial_id"],
                    "raw_request_sha256": hashlib.sha256(b"ADL:GEX:REJECTED_INGRESS_MARKER:v1\n").hexdigest(),
                    "decision": "DENY", "reason_code": code, "received_at": entry["timestamp"],
                    "persisted_at": entry["timestamp"], "ledger_event_id": "gexingressevent_" + uuid.uuid4().hex,
                    "prev_ingress_hash": prior}
                receipt["ingress_event_digest"] = hashlib.sha256(b"ADL:GEX:INGRESS:v1\n" + _canonical(receipt)).hexdigest()
                validate("IngressDenialReceiptV1", receipt)
                raw = _canonical(receipt).decode("utf-8")
                db.execute("INSERT INTO gex_ingress_artifacts VALUES(?,?,?,?)", (
                    int(previous["seq"]) + 1 if previous else 0, entry["denial_id"], raw,
                    hashlib.sha256(raw.encode("utf-8")).hexdigest()))
        except (sqlite3.Error, OSError) as exc:
            raise StoreUnavailableError("ingress denial persistence unavailable") from exc

    def ingress_receipts(self) -> list[dict[str, object]]:
        """Verify the separate, typed ingress chain without guessed identities."""
        from src.execution.gex_control import validate
        try:
            with self._connect() as db:
                rows = db.execute("SELECT * FROM gex_ingress_artifacts ORDER BY seq").fetchall()
            previous, values = None, []
            for seq, row in enumerate(rows):
                raw = str(row["receipt_json"])
                receipt = json.loads(raw)
                validate("IngressDenialReceiptV1", receipt)
                unsigned = {key: value for key, value in receipt.items() if key != "ingress_event_digest"}
                expected = hashlib.sha256(b"ADL:GEX:INGRESS:v1\n" + _canonical(unsigned)).hexdigest()
                if (row["seq"] != seq or receipt["prev_ingress_hash"] != previous
                        or receipt["ingress_id"] != row["denial_id"] or receipt["ingress_event_digest"] != expected
                        or hashlib.sha256(raw.encode("utf-8")).hexdigest() != row["receipt_sha256"]):
                    raise LedgerError("ingress artifact chain mismatch")
                previous = expected
                values.append(receipt)
            return values
        except (sqlite3.Error, OSError) as exc:
            raise StoreUnavailableError("ingress artifacts could not be read") from exc

    def persist_runtime_verification(self, record: Mapping[str, object], result: Mapping[str, object]) -> None:
        """CR06: exact normative result and its event commit as one unit.

        The independent oracle's legacy result remains a separately identified
        internal artifact. This full result binds the already persisted ReceiptV1.
        """
        from src.execution.gex_control import validate, digest
        validate("VerificationResultV1", result)
        raw = _canonical(result).decode("utf-8")
        result_sha = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        try:
            with self._transaction() as db:
                stored = db.execute("SELECT record_json FROM control_records WHERE request_id=?", (record["request_id"],)).fetchone()
                if stored is None:
                    raise LedgerError("normative receipt must be persisted before verification")
                persisted = json.loads(stored["record_json"])
                receipt = persisted["receipt"]["gex_receipt"]
                if (receipt != record["receipt"]["gex_receipt"] or result["receipt_id"] != receipt["receipt_id"]
                        or result["receipt_digest"] != digest("RECEIPT", receipt)
                        or result["request_digest"] != receipt["request_digest"] or result["attempt_id"] != receipt["attempt_id"]):
                    raise LedgerError("normative verification does not match durable receipt")
                db.execute("INSERT INTO gex_runtime_verifications VALUES(?,?,?,?,?)", (
                    result["verification_id"], record["request_id"], result["attempt_id"], raw, result_sha))
                self._append_event(db, request_id=record["request_id"], run_id=record["run_id"],
                    proposal_id=record["proposal_id"], proposal_digest=record["proposal"]["proposal_digest"],
                    request_digest=record["request_digest"], permit_id=record["receipt"]["permit_id"],
                    attempt_id=result["attempt_id"], kind="VERIFICATION_RESULT_PERSISTED", now=datetime.now(timezone.utc),
                    sandbox_receipt_id=receipt["receipt_id"], boundary_receipt_id=receipt["receipt_id"],
                    verification_result_id=result["verification_id"], artifact_sha256=result_sha,
                    artifact_prefix="verification-artifact-sha256:")
        except (sqlite3.Error, OSError) as exc:
            raise StoreUnavailableError("normative verification was not durably committed") from exc

    def runtime_verification(self, verification_id: str) -> dict[str, object] | None:
        from src.execution.gex_control import validate
        try:
            with self._connect() as db:
                row = db.execute("SELECT * FROM gex_runtime_verifications WHERE verification_id=?", (verification_id,)).fetchone()
            if row is None:
                return None
            raw = str(row["result_json"])
            result = json.loads(raw)
            validate("VerificationResultV1", result)
            events = self.events_for_request(row["request_id"])
            if (hashlib.sha256(raw.encode("utf-8")).hexdigest() != row["result_sha256"]
                    or row["attempt_id"] != result["attempt_id"] or row["verification_id"] != result["verification_id"]
                    or not any(event.kind == "VERIFICATION_RESULT_PERSISTED" and event.verification_result_id == verification_id
                        and event.attempt_id == result["attempt_id"] and event.request_digest == result["request_digest"]
                        and event.boundary_receipt_id == result["receipt_id"]
                        and event.payload_ref == "verification-artifact-sha256:" + row["result_sha256"] for event in events)):
                raise LedgerError("normative verification artifact bindings mismatch")
            return result
        except (sqlite3.Error, OSError) as exc:
            raise StoreUnavailableError("normative verification could not be read") from exc

    def permit_state(self, permit_id: str) -> dict[str, object] | None:
        with self._connect() as db:
            row = db.execute("SELECT permit_id,request_digest,state,uses,db_version,consumed_at,attempt_id FROM permits WHERE permit_id=?", (permit_id,)).fetchone()
        return None if row is None else dict(row)

    def verify_event_chain(self, request_id: str) -> bool:
        events = self.events_for_request(request_id)
        prev = None
        for seq, event in enumerate(events):
            raw = event.to_dict()
            digest = raw.pop("event_digest")
            if event.seq != seq or event.prev_hash != prev:
                return False
            if hashlib.sha256(_canonical(raw)).hexdigest() != digest:
                return False
            prev = digest
        return bool(events)
