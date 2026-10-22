from __future__ import annotations

from datetime import datetime, timezone
from dataclasses import replace
import sqlite3

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from src.execution.adapters.fixture_read import FIXTURE_ID, FIXTURE_SHA256, FixtureReadRequest
from src.execution.gex_service import GexExecutionService
from src.execution.identity import GexIdentityStore
from src.execution.ledger import ExecutionLedger, LedgerError, StoreUnavailableError
from src.execution.permit import AuthorizationClaims, PermitKeyRegistry, PermitVerificationContext, issue_permit

NOW = datetime.now(timezone.utc)
AGENT = "agent_01234567"


def _key_registry():
    private = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
    return PermitKeyRegistry(issuer="gex-integration-test", active_key_id="key-1",
                             private_keys={"key-1": private}, public_keys={"key-1": private.public_key()})


def _fixture(tmp_path):
    root = tmp_path / "workspace"
    root.mkdir()
    identity = GexIdentityStore(tmp_path / "identity.sqlite3")
    _, api_key = identity.provision_principal(principal_id="principal_fixture", workspace_root=root,
                                               allowed_agent_ids=[AGENT], now=NOW)
    _, session = identity.create_session(api_key, requested_agent_id=AGENT, now=NOW)
    principal = identity.authenticate_session(session, requested_agent_id=AGENT,
                                               agent_exists=lambda value: value == AGENT, now=NOW)
    request = FixtureReadRequest("request-fixture-1", FIXTURE_ID)
    digest = GexExecutionService.request_digest(request)
    keys = _key_registry()
    permit_principal = GexExecutionService.permit_principal(principal)
    authorization = AuthorizationClaims(
        request_digest=digest, agent_config_digest="c" * 64, capability_id="fixture.read",
        capability_version="1.0.0", registry_digest="d" * 64, effect_scope="read:fixture:sample",
        operation_digest=request.operation_digest, policy_revision="policy-fixture-v1",
        constraints_effective={"sandbox_profile": "read_only_agent", "network": "deny",
                               "write_scope": "none",
                               "timeout_ms": 1000, "max_output_bytes": 2048, "egress_allowlist": []},
        decision_id="decision-fixture-1", approval_id="approval-fixture-1", auto_rule_id=None)
    permit = issue_permit(principal=permit_principal, authorization=authorization, keys=keys, now=NOW)
    context = PermitVerificationContext(digest, permit_principal, NOW, lambda _: False, lambda _: True)
    ledger = ExecutionLedger(tmp_path / "ledger.sqlite3")
    ledger.register_permit(permit=permit, keys=keys, context=context, request_id=request.request_id,
                           run_id="run-fixture-1", proposal_id="proposal-fixture-1", proposal_digest="f" * 64)
    service = GexExecutionService(identity_store=identity, ledger=ledger, keys=keys, workspace_root=root,
                                  agent_exists=lambda value: value == AGENT)
    return service, identity, ledger, keys, permit, session, request


def test_fixture_read_requires_authenticated_session_and_signed_permit(tmp_path):
    service, _, ledger, _, permit, session, request = _fixture(tmp_path)
    receipt = service.execute_fixture_read(session_token=session, request=request, permit=permit, now=NOW)
    assert receipt.result_state == "VERIFIED_SUCCESS"
    assert receipt.verification_state == "VERIFIED_SUCCESS"
    assert receipt.observed_sha256 == FIXTURE_SHA256
    assert receipt.fixture_sha256 == FIXTURE_SHA256
    assert receipt.sandbox_receipt["request_id"] == request.request_id
    assert receipt.sandbox_receipt["permit_id"] == permit.permit_id
    assert receipt.attempt_id
    assert ledger.permit_state(permit.permit_id)["state"] == "CONSUMED"
    attempt_events = [e for e in ledger.events_for_request(request.request_id) if e.attempt_id]
    assert [e.kind for e in attempt_events] == [
        "PERMIT_CONSUMED", "DISPATCH_INTENT", "TERMINAL_RECEIPT_PERSISTED",
        "VERIFICATION_RESULT_PERSISTED"]
    durable = ledger.terminal_verification(receipt.attempt_id)
    assert durable is not None and durable.verification_state == "VERIFIED_SUCCESS"
    assert durable.receipt["receipt_id"] == receipt.sandbox_receipt["receipt_id"]
    assert ledger.verify_event_chain(request.request_id)


def test_terminal_receipt_and_verification_survive_restart_and_replay_is_denied(tmp_path):
    service, _, ledger, _, permit, session, request = _fixture(tmp_path)
    receipt = service.execute_fixture_read(session_token=session, request=request, permit=permit, now=NOW)
    restarted = ExecutionLedger(ledger.database_path)
    recovered = restarted.terminal_verification(receipt.attempt_id)
    assert recovered is not None and recovered.verification_state == "VERIFIED_SUCCESS"
    with pytest.raises(Exception):
        service.execute_fixture_read(session_token=session, request=request, permit=permit, now=NOW)
    assert restarted.terminal_verification(receipt.attempt_id).verification_state == "VERIFIED_SUCCESS"


def test_altered_executor_output_fails_independent_observation(tmp_path):
    service, _, ledger, _, permit, session, request = _fixture(tmp_path)
    delegate = service.gateway

    class AlteredOutputGateway:
        def execute(self, **kwargs):
            result = delegate.execute(**kwargs)
            return replace(result, value="tampered executor output")

    service.gateway = AlteredOutputGateway()
    receipt = service.execute_fixture_read(session_token=session, request=request, permit=permit, now=NOW)
    assert receipt.verification_state == "VERIFICATION_FAILED"
    durable = ledger.terminal_verification(receipt.attempt_id)
    assert durable is not None and durable.verification_state == "VERIFICATION_FAILED"
    assert ledger.verify_event_chain(request.request_id)


def test_storage_error_rolls_back_terminal_artifacts_and_restart_marks_uncertain(tmp_path):
    service, _, ledger, _, permit, session, request = _fixture(tmp_path)
    with sqlite3.connect(ledger.database_path) as db:
        db.execute("CREATE TRIGGER fail_verification BEFORE INSERT ON verification_results "
                   "BEGIN SELECT RAISE(ABORT, 'injected storage failure'); END")
    with pytest.raises(StoreUnavailableError):
        service.execute_fixture_read(session_token=session, request=request, permit=permit, now=NOW)
    assert ledger.terminal_verification(ledger.events_for_request(request.request_id)[-1].attempt_id) is None
    assert [e.kind for e in ledger.events_for_request(request.request_id)][-2:] == [
        "PERMIT_CONSUMED", "DISPATCH_INTENT"]
    with sqlite3.connect(ledger.database_path) as db:
        db.execute("DROP TRIGGER fail_verification")
    restarted = ExecutionLedger(ledger.database_path)
    assert restarted.events_for_request(request.request_id)[-1].kind == "RECONCILIATION_REQUIRED"
    assert ledger.verify_event_chain(request.request_id)


def test_uncertain_executor_exception_never_creates_terminal_success(tmp_path):
    service, _, ledger, _, permit, session, request = _fixture(tmp_path)
    delegate = service.gateway

    class UncertainGateway:
        def execute(self, **kwargs):
            delegate.execute(**kwargs)
            raise RuntimeError("result channel lost after effect")

    service.gateway = UncertainGateway()
    with pytest.raises(RuntimeError, match="result channel lost"):
        service.execute_fixture_read(session_token=session, request=request, permit=permit, now=NOW)
    attempt_id = ledger.events_for_request(request.request_id)[-1].attempt_id
    assert attempt_id and ledger.terminal_verification(attempt_id) is None
    assert ledger.events_for_request(request.request_id)[-1].kind == "RECONCILIATION_REQUIRED"


def test_altered_durable_receipt_is_detected(tmp_path):
    service, _, ledger, _, permit, session, request = _fixture(tmp_path)
    receipt = service.execute_fixture_read(session_token=session, request=request, permit=permit, now=NOW)
    altered = {**receipt.sandbox_receipt, "request_id": "forged-request"}
    import json
    with sqlite3.connect(ledger.database_path) as db:
        db.execute("UPDATE terminal_receipts SET receipt_json=? WHERE receipt_id=?",
                   (json.dumps(altered, sort_keys=True, separators=(",", ":")),
                    receipt.sandbox_receipt["receipt_id"]))
    with pytest.raises(LedgerError, match="digest mismatch"):
        ledger.terminal_verification(receipt.attempt_id)


def test_missing_durable_verification_artifact_never_returns_verified_result(tmp_path):
    service, _, ledger, _, permit, session, request = _fixture(tmp_path)
    receipt = service.execute_fixture_read(session_token=session, request=request, permit=permit, now=NOW)
    with sqlite3.connect(ledger.database_path) as db:
        db.execute("DELETE FROM verification_results WHERE attempt_id=?", (receipt.attempt_id,))
    assert ledger.terminal_verification(receipt.attempt_id) is None


@pytest.mark.parametrize("binding", ["request_id", "request_digest", "permit_id", "attempt_id"])
def test_terminal_persistence_rejects_binding_mismatch(tmp_path, binding):
    service, identity, ledger, keys, permit, session, request = _fixture(tmp_path)
    principal = identity.authenticate_session(session, requested_agent_id=AGENT,
        agent_exists=lambda value: value == AGENT, now=NOW)
    signed_principal = service.permit_principal(principal)
    digest = service.request_digest(request)
    context = service._verification_context(signed_principal, session, digest, NOW)
    attempt = ledger.consume_for_dispatch(permit=permit, keys=keys, context=context,
        request_id=request.request_id, now=NOW)
    sandbox_receipt = {"receipt_id": "gexreceipt-binding-test", "request_id": request.request_id,
                       "permit_id": permit.permit_id, "status": "SUCCESS"}
    args = {"receipt_id": "gexreceipt-binding-test", "verification_result_id": "gexverify-binding-test",
            "attempt_id": attempt, "request_id": request.request_id, "request_digest": digest,
            "permit_id": permit.permit_id, "receipt": sandbox_receipt,
            "result_state": "EXECUTOR_SUCCESS", "executor_output_sha256": FIXTURE_SHA256,
            "observed_output_sha256": FIXTURE_SHA256, "now": NOW}
    if binding == "request_id":
        args["request_id"] = "other-request"
    elif binding == "request_digest":
        args["request_digest"] = "0" * 64
    elif binding == "permit_id":
        args["permit_id"] = "other-permit"
    else:
        args["attempt_id"] = "other-attempt"
    with pytest.raises(LedgerError):
        ledger.persist_terminal_verification(**args)
    assert ledger.terminal_verification(attempt) is None
    assert [e.kind for e in ledger.events_for_request(request.request_id)][-2:] == [
        "PERMIT_CONSUMED", "DISPATCH_INTENT"]


@pytest.mark.parametrize(("receipt_status", "result_state"), [
    ("DENIED", "EXECUTOR_SUCCESS"), ("FAILURE", "EXECUTOR_SUCCESS"),
    ("SUCCESS", "EXECUTOR_FAILURE"),
])
def test_terminal_persistence_rejects_receipt_result_status_disagreement(
        tmp_path, receipt_status, result_state):
    service, identity, ledger, keys, permit, session, request = _fixture(tmp_path)
    principal = identity.authenticate_session(session, requested_agent_id=AGENT,
        agent_exists=lambda value: value == AGENT, now=NOW)
    signed_principal = service.permit_principal(principal)
    digest = service.request_digest(request)
    context = service._verification_context(signed_principal, session, digest, NOW)
    attempt = ledger.consume_for_dispatch(permit=permit, keys=keys, context=context,
        request_id=request.request_id, now=NOW)
    sandbox_receipt = {"receipt_id": "gexreceipt-status-test", "request_id": request.request_id,
                       "permit_id": permit.permit_id, "status": receipt_status}
    with pytest.raises(LedgerError, match="disagrees"):
        ledger.persist_terminal_verification(receipt_id="gexreceipt-status-test",
            verification_result_id="gexverify-status-test", attempt_id=attempt,
            request_id=request.request_id, request_digest=digest, permit_id=permit.permit_id,
            receipt=sandbox_receipt, result_state=result_state,
            executor_output_sha256=FIXTURE_SHA256, observed_output_sha256=FIXTURE_SHA256, now=NOW)
    assert ledger.terminal_verification(attempt) is None
    with sqlite3.connect(ledger.database_path) as db:
        assert db.execute("SELECT state FROM attempts WHERE attempt_id=?", (attempt,)).fetchone()[0] == "DISPATCH_INTENT"
        assert db.execute("SELECT count(*) FROM terminal_receipts WHERE attempt_id=?", (attempt,)).fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM verification_results WHERE attempt_id=?", (attempt,)).fetchone()[0] == 0
    assert [e.kind for e in ledger.events_for_request(request.request_id)][-2:] == [
        "PERMIT_CONSUMED", "DISPATCH_INTENT"]


def test_unknown_fixture_and_wrong_request_digest_fail_before_consumption(tmp_path):
    service, _, ledger, _, permit, session, request = _fixture(tmp_path)
    with pytest.raises(ValueError, match="registered synthetic fixture"):
        FixtureReadRequest("request-fixture-1", "customer-data.csv")
    mismatched = FixtureReadRequest("other-request", FIXTURE_ID)
    with pytest.raises(ValueError, match="not bound"):
        service.execute_fixture_read(session_token=session, request=mismatched, permit=permit, now=NOW)
    assert ledger.permit_state(permit.permit_id)["state"] == "ISSUED"


def test_revoked_session_fails_before_ledger_reservation(tmp_path):
    service, identity, ledger, _, permit, session, request = _fixture(tmp_path)
    principal = identity.authenticate_session(session, requested_agent_id=AGENT,
                                               agent_exists=lambda value: True, now=NOW)
    # Trusted operator action models revocation; execute must resolve the token again.
    assert identity.deactivate_principal(principal.principal_id, now=NOW)
    with pytest.raises(Exception):
        service.execute_fixture_read(session_token=session, request=request, permit=permit, now=NOW)
    assert ledger.permit_state(permit.permit_id)["state"] == "ISSUED"


def test_adapter_workspace_must_match_authenticated_workspace(tmp_path):
    service, identity, ledger, keys, permit, session, request = _fixture(tmp_path)
    other_root = tmp_path / "other-workspace"
    other_root.mkdir()
    wrong_workspace_service = GexExecutionService(
        identity_store=identity, ledger=ledger, keys=keys, workspace_root=other_root,
        agent_exists=lambda value: value == AGENT)
    with pytest.raises(ValueError, match="differs from the authenticated workspace"):
        wrong_workspace_service.execute_fixture_read(session_token=session, request=request,
                                                       permit=permit, now=NOW)
    assert ledger.permit_state(permit.permit_id)["state"] == "ISSUED"
