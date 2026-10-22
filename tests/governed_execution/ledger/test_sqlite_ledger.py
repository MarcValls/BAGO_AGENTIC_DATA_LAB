from __future__ import annotations

import multiprocessing
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from src.execution.identity import AuthenticatedPrincipal
from src.execution.ledger import ExecutionLedger, PermitReplayError, StoreUnavailableError
from src.execution.permit.permit_v1 import (
    AuthorizationClaims, PermitKeyRegistry, PermitVerificationContext, issue_permit,
)


NOW = datetime(2026, 10, 18, 12, 0, tzinfo=timezone.utc)
DIGEST = "a" * 64


def _keys():
    private = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
    return PermitKeyRegistry(issuer="adl-test", active_key_id="key-1",
        private_keys={"key-1": private}, public_keys={"key-1": private.public_key()})


def _principal():
    return AuthenticatedPrincipal("principal_alice", "b"*64, "agent_01234567", "session_1",
        "credential_1", "2026-10-18T11:00:00.000Z", "2026-10-18T13:00:00.000Z")


def _context(now=NOW, *, revoked=lambda _: False, active=lambda _: True):
    return PermitVerificationContext(DIGEST, _principal(), now, revoked, active)


def _permit(now=NOW, ttl=300):
    claims = AuthorizationClaims(DIGEST, "c"*64, "fixture.read", "1", "d"*64,
        "read:fixture", "e"*64, "policy-1", {"sandbox_profile":"fixture-read-v1",
        "network":"deny", "timeout_ms":1000, "max_output_bytes":2048,
        "write_scope":"none", "egress_allowlist":[]}, "decision-1", "approval-1", None)
    return issue_permit(principal=_principal(), authorization=claims, keys=_keys(), now=now, ttl_seconds=ttl)


def _register(path, permit=None):
    permit = permit or _permit()
    ledger = ExecutionLedger(path)
    ledger.register_permit(permit=permit, keys=_keys(), context=_context(), request_id="request-1",
        run_id="run-1", proposal_id="proposal-1", proposal_digest="f"*64)
    return ledger, permit


def _child_consume(path, permit_data, output):
    from src.execution.permit.permit_v1 import PermitV1
    permit = PermitV1(**permit_data)
    ledger = ExecutionLedger(path)
    try:
        result = ledger.consume_for_dispatch(permit=permit, keys=_keys(), context=_context(), request_id="request-1")
        output.put(("OK", result))
    except Exception as exc:
        output.put((type(exc).__name__, str(exc)))


def test_restart_replay_and_hash_linked_events(tmp_path):
    ledger, permit = _register(tmp_path / "ledger.sqlite3")
    attempt = ledger.consume_for_dispatch(permit=permit, keys=_keys(), context=_context(), request_id="request-1")
    restarted = ExecutionLedger(tmp_path / "ledger.sqlite3")
    assert restarted.permit_state(permit.permit_id)["state"] == "CONSUMED"
    with pytest.raises(PermitReplayError):
        restarted.consume_for_dispatch(permit=permit, keys=_keys(), context=_context(), request_id="request-1")
    events = restarted.events_for_request("request-1")
    assert [event.kind for event in events] == ["PERMIT_ISSUED", "PERMIT_CONSUMED", "DISPATCH_INTENT",
        "RECONCILIATION_REQUIRED", "REPLAY_DENIED"]
    assert events[2].attempt_id == attempt
    assert restarted.verify_event_chain("request-1")


def test_two_processes_can_reserve_only_once(tmp_path):
    path = tmp_path / "ledger.sqlite3"
    ledger, permit = _register(path)
    ctx = multiprocessing.get_context("spawn")
    output = ctx.Queue()
    args = (str(path), permit.to_dict(), output)
    children = [ctx.Process(target=_child_consume, args=args) for _ in range(2)]
    for child in children: child.start()
    for child in children: child.join(20)
    assert all(child.exitcode == 0 for child in children)
    results = [output.get(timeout=3)[0] for _ in children]
    assert results.count("OK") == 1
    assert sum(name in ("PermitReplayError", "LedgerError") for name in results) == 1
    assert ledger.permit_state(permit.permit_id)["uses"] == 1


def test_expired_or_revoked_permit_cannot_be_consumed(tmp_path):
    expired, permit = _register(tmp_path / "expired.sqlite3", _permit(now=NOW, ttl=60))
    with pytest.raises(Exception):
        expired.consume_for_dispatch(permit=permit, keys=_keys(),
            context=_context(now=NOW + timedelta(minutes=2)), request_id="request-1")
    revoked, permit2 = _register(tmp_path / "revoked.sqlite3")
    revoked.revoke_permit(permit2.permit_id, now=NOW)
    with pytest.raises(Exception):
        revoked.consume_for_dispatch(permit=permit2, keys=_keys(), context=_context(), request_id="request-1")
    assert revoked.permit_state(permit2.permit_id)["state"] == "REVOKED"


def test_storage_failure_rolls_back_permit_and_both_events(tmp_path):
    ledger, permit = _register(tmp_path / "ledger.sqlite3")
    def crash(point):
        if point == "after_consumed_event":
            raise sqlite3.OperationalError("injected disk failure")
    with pytest.raises(StoreUnavailableError):
        ledger.consume_for_dispatch(permit=permit, keys=_keys(), context=_context(),
            request_id="request-1", failpoint=crash)
    assert ledger.permit_state(permit.permit_id)["state"] == "ISSUED"
    assert [event.kind for event in ledger.events_for_request("request-1")] == ["PERMIT_ISSUED"]


def test_unknown_outcome_is_reconciliation_required_not_success(tmp_path):
    ledger, permit = _register(tmp_path / "ledger.sqlite3")
    attempt = ledger.consume_for_dispatch(permit=permit, keys=_keys(), context=_context(), request_id="request-1")
    restarted = ExecutionLedger(tmp_path / "ledger.sqlite3")
    restarted.require_reconciliation(attempt, now=NOW)
    assert [e.kind for e in restarted.events_for_request("request-1")][-1] == "RECONCILIATION_REQUIRED"
    assert restarted.verify_event_chain("request-1")
