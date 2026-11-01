"""Real HTTP/SQLite/Ed25519/CAS/gateway tests with SIMULATED provider callback.

No cloud claim: provider callbacks deliberately control adverse proposals.
"""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import subprocess

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from src.api.gex_routes import create_gex_router
from src.execution import gex_control as gc
from src.execution.adapters.fixture_read import FIXTURE_BYTES, FIXTURE_ID, FIXTURE_SHA256
from src.execution.ledger.sqlite_ledger import StoreUnavailableError
from src.execution.permit.permit_v1 import _canonical

AGENT = "agent_12345678"
OTHER_AGENT = "agent_87654321"
PROPOSAL = {"tool_calls": [{"function": {"name": "fixture.read", "arguments": {"fixture_id": FIXTURE_ID}}}]}


@pytest.fixture
def env(tmp_path, monkeypatch):
    work, state = tmp_path / "workspace", tmp_path / "state"
    work.mkdir()
    (work / "seed.txt").write_text("seed\n")
    for args in (["init"], ["add", "."], ["-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-m", "seed"]):
        subprocess.run(["git", "-C", str(work), *args], check=True, capture_output=True)
    agent = {"id": AGENT, "created_at": "2026-10-20T00:00:00Z", "config": {
        "system_prompt": "Propose the requested synthetic read.", "provider_id": "test-provider", "model_id": "test-model", "tools": []}}
    calls = []
    def load(agent_id):
        if agent_id not in {AGENT, OTHER_AGENT}:
            raise KeyError("unknown saved agent")
        return {**deepcopy(agent), "id": agent_id}
    current = {"turn": deepcopy(PROPOSAL)}
    def chat(model, messages, **kwargs):
        calls.append({"model": model, "messages": deepcopy(messages), "kwargs": deepcopy(kwargs)})
        if isinstance(current["turn"], Exception):
            raise current["turn"]
        return deepcopy(current["turn"])
    def resolver(provider):
        assert provider == "test-provider"
        return lambda: {"state": "ready"}, chat
    monkeypatch.delenv("BAGO_GEX_IDENTITY_DB_PATH", raising=False)
    monkeypatch.setenv("BAGO_GEX_STATE_DIR", str(state))
    monkeypatch.setenv("BAGO_GEX_WORKSPACE_ROOT", str(work))
    provisioned = gc.provision(state_dir=state, workspace=work, principal_id="principal_demo", agent_id=AGENT, load_agent=load)
    @contextmanager
    def client():
        app = FastAPI()
        router = create_gex_router(load_agent=load, provider_resolver=resolver)
        app.include_router(router)
        with TestClient(app) as http:
            yield http, router
    return {"work": work, "state": state, "agent": agent, "load": load, "resolver": resolver,
        "calls": calls, "current": current, "key": provisioned["api_key"], "client": client}


def session(http, env, key=None, agent=AGENT):
    response = http.post("/api/gex/sessions", headers={"Authorization": "Bearer " + (key or env["key"])}, json={"agent_id": agent})
    assert response.status_code == 201, response.text
    value = response.json()
    return {"Authorization": "Bearer " + value["session_token"], "X-GEX-Agent-ID": agent}, value


def propose(http, headers):
    response = http.post("/api/gex/requests", headers=headers, json={"task": "Read the registered synthetic customer summary."})
    assert response.status_code == 201, response.text
    return response.json()


def decide(http, headers, view, decision="APPROVED"):
    return http.post("/api/gex/requests/" + view["request_id"] + "/decision", headers=headers,
        json={"request_digest": view["request_digest"], "decision": decision, "reason": "Explicit operator fixture decision."})


def spy_dispatch(router):
    service = router.gex_holder["control"].service
    original = service.gateway.execute
    calls = []
    def execute(**kwargs):
        calls.append(kwargs["request"].request_id)
        return original(**kwargs)
    service.gateway.execute = execute
    return calls


def test_full_http_chain_restart_and_replay(env):
    with env["client"]() as (http, router):
        assert http.get("/api/gex/status").json()["state"] == "READY"
        headers, issued = session(http, env)
        view = propose(http, headers)
        assert view["state"] == "AWAITING_APPROVAL" and view["policy_decision"]["result"] == "REQUIRE_HUMAN"
        assert gc.whole_request_digest(view["request"]) == view["request_digest"]
        assert view["request"]["agent"]["config_digest"] == gc.digest("AGENT", env["agent"])
        dispatch = spy_dispatch(router)
        response = decide(http, headers, view)
        assert response.status_code == 200, response.text
        done = response.json()
        assert done["state"] == "SUCCEEDED", done
        assert all(done["integrity"].values()), done
        assert done["receipt"]["output"].encode() == FIXTURE_BYTES
        assert done["receipt"]["executor_output_sha256"] == done["receipt"]["observed_sha256"] == FIXTURE_SHA256
        kinds = [event["kind"] for event in done["events"]]
        for kind in ["PROPOSED", "POLICY_DECIDED", "APPROVAL_REQUESTED", "APPROVED", "PERMIT_ISSUED", "PERMIT_CONSUMED", "DISPATCH_INTENT", "VERIFICATION_RESULT_PERSISTED", "RECEIPT_PERSISTED"]:
            assert kind in kinds
        assert len(dispatch) == 1
        replay = decide(http, headers, view)
        assert replay.status_code == 409
        assert replay.json()["detail"]["view"]["state"] == "SUCCEEDED"
        assert replay.json()["detail"]["view"]["integrity"]["receipt_verified"] is True
        assert replay.json()["detail"]["view"]["events"][-1]["kind"] == "REPLAY_DENIED"
        assert len(dispatch) == 1
        payload = json.dumps(env["calls"])
        assert env["key"] not in payload and issued["session_token"] not in payload
        # SQLite/config/key content never contains a raw issued credential/token.
        for file in env["state"].glob("*.sqlite3*"):
            assert env["key"].encode() not in file.read_bytes()
            assert issued["session_token"].encode() not in file.read_bytes()
        key_before = (env["state"] / "signing-key.pem").read_bytes()
    with env["client"]() as (http, router):
        headers, _ = session(http, env)
        recovered = http.get("/api/gex/requests/" + view["request_id"], headers=headers)
        assert recovered.status_code == 200, recovered.text
        assert recovered.json()["state"] == "SUCCEEDED"
        assert recovered.json()["integrity"]["receipt_verified"] is True
        assert (env["state"] / "signing-key.pem").read_bytes() == key_before
        assert decide(http, headers, view).status_code == 409
        assert len(env["calls"]) == 1


@pytest.mark.parametrize("decision", ["REJECTED", "CANCELLED"])
def test_terminal_operator_denial_never_dispatches(env, decision):
    with env["client"]() as (http, router):
        headers, _ = session(http, env)
        view = propose(http, headers)
        dispatch = spy_dispatch(router)
        response = decide(http, headers, view, decision)
        assert response.status_code == 200, response.text
        denied = response.json()
        assert denied["state"] == decision and denied["receipt"]["status"] == "DENIED"
        assert denied["permit"] is None and denied["receipt"]["attempt_id"] is None
        assert decide(http, headers, view).status_code == 409 and not dispatch


@pytest.mark.parametrize("turn", [
    {"content": "I read it successfully"},
    {"content": "```json\n{}\n```"},
    {"tool_calls": [PROPOSAL["tool_calls"][0], PROPOSAL["tool_calls"][0]]},
    {"tool_calls": [{"function": {"name": "filesystem.write", "arguments": {"path": "secret"}}}]},
    {"tool_calls": [{"function": {"name": "fixture.read", "arguments": '{"fixture_id":"a","fixture_id":"b"}'}}]},
    {"tool_calls": [{"function": {"name": "fixture.read", "arguments": {"fixture_id": FIXTURE_ID, "extra": 1}}}]},
    {"tool_calls": PROPOSAL["tool_calls"], "content": '{"tool_name":"other","arguments":{}}'},
    {"content": '{"tool_name":"fixture.read","arguments":{"fixture_id":"other"}}'},
    {"content": "x" * 17000}, {"content": "NaN"},
])
def test_invalid_model_proposals_are_durable_pre_registration_denials(env, turn):
    env["current"]["turn"] = turn
    with env["client"]() as (http, router):
        headers, _ = session(http, env)
        dispatch = spy_dispatch(router)
        view = propose(http, headers)
        assert view["state"] == "DENIED" and view["request"] is None and view["request_digest"] is None
        assert view["receipt"] is None and view["permit"] is None and not dispatch
        gc.validate("ToolProposalEnvelopeV1", view["proposal_envelope"])
        gc.validate("ProposalDenialReceiptV1", view["proposal_denial"])
        assert view["proposal_denial"]["proposal_digest"] == view["proposal_envelope"]["proposal_digest"] == view["proposal"]["proposal_digest"]
        assert http.get("/api/gex/requests/" + view["request_id"], headers=headers).json()["state"] == "DENIED"
        repeated = propose(http, headers)
        assert repeated["state"] == "DENIED" and repeated["request_id"] != view["request_id"]


def test_textual_actual_callback_proposal_supported(env):
    env["current"]["turn"] = {"content": json.dumps({"tool_name": "fixture.read", "arguments": {"fixture_id": FIXTURE_ID}})}
    with env["client"]() as (http, _):
        headers, _ = session(http, env)
        assert decide(http, headers, propose(http, headers)).json()["state"] == "SUCCEEDED"


def test_provider_failure_persists_sanitized_record(env):
    env["current"]["turn"] = RuntimeError("provider secret arbitrary private raw response")
    with env["client"]() as (http, router):
        headers, _ = session(http, env)
        dispatch = spy_dispatch(router)
        response = http.post("/api/gex/requests", headers=headers, json={"task": "read fixture"})
        assert response.status_code == 502 and response.json()["detail"]["persisted"] is True
        assert "private raw" not in response.text and not dispatch


def test_auth_origin_closed_json_and_revocation(env):
    with env["client"]() as (http, router):
        for headers in ({}, {"Authorization": "Bearer forged"}):
            response = http.post("/api/gex/requests", headers=headers, json={"task": "read"})
            assert response.status_code == 401 and response.headers["cache-control"] == "no-store"
        denied = http.post("/api/gex/sessions", headers={"Authorization": "Bearer " + env["key"], "Origin": "https://evil.example"}, json={"agent_id": AGENT})
        assert denied.status_code == 403
        headers, issued = session(http, env)
        assert http.post("/api/gex/sessions", headers=headers, json={"agent_id": AGENT}).status_code == 401
        for body in ('{"task":"read","task":"write"}', '{"task":"read","principal_id":"x"}', '{"task":NaN}', '{"task":1.5}'):
            assert http.post("/api/gex/requests", headers={**headers, "Content-Type": "application/json"}, content=body).status_code == 422
        assert http.post("/api/gex/requests", headers=headers, json={"task": "x" * 4001}).status_code == 422
        view = propose(http, headers)
        dispatch = spy_dispatch(router)
        assert http.delete("/api/gex/sessions/current", headers=headers).status_code == 200
        assert http.get("/api/gex/requests/" + view["request_id"], headers=headers).status_code == 401
        assert decide(http, headers, view).status_code == 401 and not dispatch
        headers, _ = session(http, env)
        # New session can retrieve owner's pending snapshot, cannot approve it.
        assert http.get("/api/gex/requests/" + view["request_id"], headers=headers).status_code == 200
        assert decide(http, headers, view).status_code == 409 and not dispatch


def test_foreign_owner_and_agent_cannot_read(env):
    with env["client"]() as (http, router):
        headers, _ = session(http, env)
        view = propose(http, headers)
        control = router.gex_holder["control"]
        _, key = control.identity.provision_principal(principal_id="principal_other", workspace_root=env["work"], allowed_agent_ids=[AGENT, OTHER_AGENT])
        foreign, _ = session(http, env, key=key)
        assert http.get("/api/gex/requests/" + view["request_id"], headers=foreign).status_code == 404
        other, _ = session(http, env, key=key, agent=OTHER_AGENT)
        assert http.get("/api/gex/requests/" + view["request_id"], headers=other).status_code == 404
        assert http.get("/api/gex/requests/" + view["request_id"], headers={**headers, "X-GEX-Agent-ID": OTHER_AGENT}).status_code in {401, 403}


@pytest.mark.parametrize("change", ["agent", "workspace", "index", "policy", "registry"])
def test_fresh_authority_changes_deny_before_dispatch(env, monkeypatch, change):
    with env["client"]() as (http, router):
        headers, _ = session(http, env)
        view = propose(http, headers)
        dispatch = spy_dispatch(router)
        if change == "agent":
            env["agent"]["config"]["system_prompt"] = "Changed bytes same saved id"
        elif change == "workspace":
            (env["work"] / "seed.txt").write_text("different bytes same HEAD")
        elif change == "index":
            (env["work"] / "new.txt").write_text("new")
            subprocess.run(["git", "-C", str(env["work"]), "add", "."], check=True, capture_output=True)
        elif change == "policy":
            original = gc.policy_snapshot()
            monkeypatch.setattr(gc, "policy_snapshot", lambda: {**original, "policy_digest": "f" * 64})
        else:
            original = gc.registry_snapshot()
            monkeypatch.setattr(gc, "registry_snapshot", lambda: {**original, "registry_digest": "f" * 64})
        response = decide(http, headers, view)
        assert response.status_code == 409 and response.json()["detail"]["code"] == ("RUNTIME_CODE_CHANGED" if change == "registry" else "STALE_AUTHORITY"), response.text
        assert not dispatch


def test_concurrent_approve_has_one_actual_dispatch(env):
    with env["client"]() as (http, router):
        headers, _ = session(http, env)
        view = propose(http, headers)
        dispatch = spy_dispatch(router)
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(lambda _: decide(http, headers, view), range(2)))
        assert sorted(result.status_code for result in responses) == [200, 409]
        assert len(dispatch) == 1


def test_before_cas_authority_mutation_is_detected(env, monkeypatch):
    with env["client"]() as (http, router):
        headers, _ = session(http, env)
        view = propose(http, headers)
        dispatch = spy_dispatch(router)
        ledger = router.gex_holder["control"].ledger
        original = ledger.consume_for_dispatch
        def consume(**kwargs):
            env["agent"]["config"]["model_id"] = "changed-model"
            return original(**kwargs)
        monkeypatch.setattr(ledger, "consume_for_dispatch", consume)
        response = decide(http, headers, view)
        assert response.status_code == 409, response.text
        assert not dispatch
        with ledger._connect() as db:
            assert db.execute("SELECT count(*) FROM attempts").fetchone()[0] == 0


def test_storage_failure_before_effect_and_after_effect_restart(env, monkeypatch):
    with env["client"]() as (http, router):
        headers, _ = session(http, env)
        view = propose(http, headers)
        dispatch = spy_dispatch(router)
        control = router.gex_holder["control"]
        original = control.ledger.save_control
        monkeypatch.setattr(control.ledger, "save_control", lambda *a, **k: (_ for _ in ()).throw(StoreUnavailableError("injected")))
        response = decide(http, headers, view)
        assert response.status_code == 503 and response.json()["detail"]["persisted"] is False and not dispatch
        monkeypatch.setattr(control.ledger, "save_control", original)
        monkeypatch.setattr(control.ledger, "persist_terminal_verification", lambda **k: (_ for _ in ()).throw(StoreUnavailableError("after effect")))
        response = decide(http, headers, view)
        assert response.status_code == 503 and response.json()["detail"]["persisted"] is False
        assert len(dispatch) == 1
    with env["client"]() as (http, router):
        headers, _ = session(http, env)
        recovered = http.get("/api/gex/requests/" + view["request_id"], headers=headers).json()
        assert recovered["state"] == "RECONCILIATION_REQUIRED" and not recovered["integrity"]["receipt_verified"]
        assert decide(http, headers, view).status_code == 409
        with router.gex_holder["control"].ledger._connect() as db:
            assert db.execute("SELECT state FROM attempts").fetchone()[0] == "RECONCILIATION_REQUIRED"


def test_observer_mismatch_and_corrupted_receipt_never_success(env, monkeypatch):
    import src.execution.gex_service as service
    with env["client"]() as (http, router):
        headers, _ = session(http, env)
        view = propose(http, headers)
        monkeypatch.setattr(service, "observe_fixture_output", lambda _: b"wrong oracle bytes")
        done = decide(http, headers, view).json()
        assert done["state"] == "FAILED" and not done["integrity"]["receipt_verified"]
        assert done["receipt"]["status"] == "SUCCESS"  # Executor success is orthogonal to independent failure.
        ledger = router.gex_holder["control"].ledger
        with ledger._transaction() as db:
            db.execute("UPDATE terminal_receipts SET receipt_json='{}'")
        response = http.get("/api/gex/requests/" + view["request_id"], headers=headers)
        assert response.status_code != 200 or response.json()["integrity"]["receipt_verified"] is False


def test_owner_lock_configuration_and_no_per_request_initialization(env, monkeypatch):
    with env["client"]() as (http, router):
        assert http.get("/api/gex/status").json()["state"] == "READY"
        original = router.gex_holder["control"].ledger
        with env["client"]() as (other, _):
            status = other.get("/api/gex/status").json()
            assert status["state"] == "UNAVAILABLE" and status["reason_code"] == "OWNER_CONTENTION"
        for _ in range(3):
            assert http.get("/api/gex/status").json()["state"] == "READY"
            assert router.gex_holder["control"].ledger is original
    monkeypatch.delenv("BAGO_GEX_WORKSPACE_ROOT")
    with env["client"]() as (http, _):
        status = http.get("/api/gex/status")
        assert status.json()["state"] == "UNCONFIGURED" and str(env["state"]) not in status.text


@pytest.mark.parametrize("path", [
    ("principal", "subject"), ("agent", "config_digest"), ("workspace", "binding_fingerprint"),
    ("capability", "registry_digest"), ("policy", "policy_digest"), ("operation", "target"),
    ("constraints", "network"), ("expires_at",), ("nonce",),
])
def test_whole_request_digest_changes_every_authority_member(env, path):
    with env["client"]() as (http, _):
        headers, _ = session(http, env)
        view = propose(http, headers)
        changed = deepcopy(view["request"])
        target = changed
        for key in path[:-1]:
            target = target[key]
        key = path[-1]
        if key.endswith("digest") or key == "binding_fingerprint":
            target[key] = "f" * 64
        elif key == "network":
            target[key] = "allowlist"
        elif key == "expires_at":
            target[key] = gc._stamp(gc._parse_stamp(target[key]) - timedelta(seconds=1))
        else:
            target[key] += "-changed"
        assert gc.whole_request_digest(changed) != view["request_digest"]


def test_jcs_unicode_unsupported_data_and_duplicates():
    # UTF-16 ordering puts supplementary-plane key before U+E000.
    assert _canonical({"\ue000": "b", "\U00010000": "a"}).decode() == '{"\U00010000":"a","\ue000":"b"}'
    for raw in ('{"x":1,"x":2}', '{"x":1.5}', '{"x":NaN}', '{"x":9007199254740992}', '{"x":"\\ud800"}'):
        with pytest.raises(Exception):
            gc.strict_json(raw)


def test_digest_mismatch_signed_approval_and_permit_tampering(env, monkeypatch):
    with env["client"]() as (http, router):
        headers, _ = session(http, env)
        view = propose(http, headers)
        dispatch = spy_dispatch(router)
        changed = {**view, "request_digest": "f" * 64}
        assert decide(http, headers, changed).status_code == 409 and not dispatch
        control = router.gex_holder["control"]
        original = control._signed_approval
        def forged(*args):
            approval = original(*args)
            approval["actor"] = "principal_forged"
            return approval
        monkeypatch.setattr(control, "_signed_approval", forged)
        response = decide(http, headers, view)
        assert response.status_code != 200 and not dispatch


def test_no_global_provider_fallback(env):
    env["agent"]["config"]["provider_id"] = None
    with env["client"]() as (http, _):
        headers, _ = session(http, env)
        response = http.post("/api/gex/requests", headers=headers, json={"task": "read"})
        assert response.status_code == 409 and response.json()["detail"]["code"] == "AGENT_PROVIDER_UNCONFIGURED"
        assert not env["calls"]


def test_code_change_blocks_new_proposal_until_process_restart(env, monkeypatch):
    with env["client"]() as (http, router):
        headers, _ = session(http, env)
        original = gc.registry_snapshot()
        monkeypatch.setattr(gc, "registry_snapshot", lambda: {**original, "registry_digest": "f" * 64})
        response = http.post("/api/gex/requests", headers=headers, json={"task": "read fixture"})
        assert response.status_code == 503 and not env["calls"]
        assert http.get("/api/gex/status").json()["state"] == "UNAVAILABLE"


@pytest.mark.parametrize("mutation", ["missing", "limits", "effect", "decision", "output", "origin"])
def test_normative_receipt_semantic_tampering_never_verified(env, mutation, monkeypatch):
    # This test measures receipt semantics, not wall-clock synchronization.
    # A clock step backwards between permit issuance and dispatch correctly
    # fails closed; exercise that separately from these tampering cases.
    from src.execution import gex_service
    from src.execution.identity import session as identity_session
    from src.execution.ledger import sqlite_ledger
    from src.execution.permit import permit_v1

    stable_now = datetime.now(timezone.utc)

    class StableDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return stable_now.astimezone(tz) if tz is not None else stable_now.replace(tzinfo=None)

    for module in (gc, gex_service, identity_session, sqlite_ledger, permit_v1):
        monkeypatch.setattr(module, "datetime", StableDateTime)

    with env["client"]() as (http, router):
        headers, _ = session(http, env)
        view = propose(http, headers)
        done = decide(http, headers, view)
        assert done.status_code == 200 and done.json()["state"] == "SUCCEEDED", done.text
        control = router.gex_holder["control"]
        principal = control.authenticate(headers["Authorization"][7:], AGENT)
        record = control._read(view["request_id"], principal)
        full = record["receipt"]["gex_receipt"]
        gc.validate("ReceiptV1", full)
        assert full["actual_limits"] == gc.CONSTRAINTS
        if mutation == "missing":
            record["receipt"].pop("gex_receipt")
        elif mutation == "limits":
            full["actual_limits"]["max_output_bytes"] = 1000000
        elif mutation == "effect":
            full["observed_effect"]["effect"] = "WRITE"
        elif mutation == "decision":
            full["decision_id"] = "forged"
        elif mutation == "output":
            full["output_sha256"] = "f" * 64
        else:
            full["origin_event_ids"] = []
        # Even an internally committed, correctly hashed control snapshot must
        # not promote semantically invalid receipt content to verified output.
        control._save(record, principal, "RECEIPT_PERSISTED")
        recovered = http.get("/api/gex/requests/" + view["request_id"], headers=headers)
        assert recovered.status_code == 200, recovered.text
        assert recovered.json()["state"] == "RECONCILIATION_REQUIRED"
        assert recovered.json()["integrity"]["receipt_verified"] is False


def test_effective_output_limit_reaches_real_backend(env, monkeypatch):
    from src.execution.adapters.fixture_read import FixtureSandboxBackend
    actual = []
    original = FixtureSandboxBackend.execute
    def execute(self, sandbox, request):
        actual.append(sandbox.specification)
        return original(self, sandbox, request)
    monkeypatch.setattr(FixtureSandboxBackend, "execute", execute)
    with env["client"]() as (http, _):
        headers, _ = session(http, env)
        done = decide(http, headers, propose(http, headers))
        assert done.status_code == 200 and done.json()["state"] == "SUCCEEDED", done.text
        assert len(actual) == 1 and actual[0].max_output_bytes == 65536
        assert actual[0].timeout_seconds == 1 and not actual[0].allowed_executables
        assert not actual[0].writable_roots and not actual[0].allowed_network_hosts


def test_too_small_signed_output_limit_is_denied_by_actual_backend(env, monkeypatch):
    from src.execution.adapters.fixture_read import FixtureReadPolicy
    from src.sandbox.filesystem import FilesystemOperation, FilesystemRequest
    from src.sandbox.manager import SandboxManager, SandboxRequest
    from src.execution.adapters.fixture_read import FixtureSandboxBackend, FixtureReadRequest, sandbox_operation
    from src.orchestration.state_graph import Permit, AuthorizationDecision
    now = datetime.now(timezone.utc)
    permit = Permit(permit_id="limit-test", request_id="limit-test", decision=AuthorizationDecision.ALLOW,
        rationale="bounded output negative", constraints=["sandbox_profile=read_only_agent", "workspace_root=" + str(env["work"]),
            "network=deny", "capability=filesystem_read", "timeout_seconds=1", "max_output_bytes=1"],
        issued_at=now.isoformat(), expires_at=(now + timedelta(seconds=60)).isoformat(), signed_by="test")
    manager = SandboxManager(backend=FixtureSandboxBackend(), policy=FixtureReadPolicy())
    result = manager.execute(permit=permit, request=SandboxRequest(request_id="limit-test", workspace_root=env["work"],
        operation=sandbox_operation(FixtureReadRequest("limit-test", FIXTURE_ID))))
    assert result.receipt.status.value == "DENIED" and result.value is None
    assert result.receipt.error_code == "OUTPUT_LIMIT"


@pytest.mark.parametrize("mutation", ["missing", "digest", "oracle", "evidence", "id"])
def test_normative_verification_mutation_not_promoted(env, mutation):
    with env["client"]() as (http, router):
        headers, _ = session(http, env)
        initial = propose(http, headers)
        done = decide(http, headers, initial)
        assert done.status_code == 200 and done.json()["integrity"]["receipt_verified"], done.text
        control = router.gex_holder["control"]
        principal = control.authenticate(headers["Authorization"][7:], AGENT)
        record = control._read(initial["request_id"], principal)
        result = record["receipt"]["gex_verification"]
        gc.validate("VerificationResultV1", result)
        assert result["receipt_digest"] == gc.digest("RECEIPT", record["receipt"]["gex_receipt"])
        events = control.ledger.events_for_request(initial["request_id"])
        for event in events:
            control.ledger._event_validator.validate(event.to_dict())
        assert any(event.kind == "VERIFICATION_RESULT_PERSISTED" and event.verification_result_id == result["verification_id"]
                   and event.payload_ref.startswith("verification-artifact-sha256:") for event in events)
        if mutation == "missing":
            record["receipt"].pop("gex_verification")
        elif mutation == "digest":
            result["receipt_digest"] = "f" * 64
        elif mutation == "oracle":
            result["postcondition_digest"] = "f" * 64
        elif mutation == "evidence":
            result["evidence_refs"] = []
        else:
            result["verification_id"] = "forged"
        control._save(record, principal, "RECEIPT_PERSISTED")
        response = http.get("/api/gex/requests/" + initial["request_id"], headers=headers)
        assert response.status_code == 200 and response.json()["state"] == "RECONCILIATION_REQUIRED", response.text
        assert response.json()["integrity"]["receipt_verified"] is False


def test_normative_verification_storage_failure_cannot_publish_success(env, monkeypatch):
    with env["client"]() as (http, router):
        headers, _ = session(http, env)
        initial = propose(http, headers)
        dispatch = spy_dispatch(router)
        control = router.gex_holder["control"]
        monkeypatch.setattr(control.ledger, "persist_runtime_verification", lambda *a: (_ for _ in ()).throw(StoreUnavailableError("injected")))
        response = decide(http, headers, initial)
        assert response.status_code == 503 and not response.json()["detail"]["persisted"] and len(dispatch) == 1
        readback = http.get("/api/gex/requests/" + initial["request_id"], headers=headers)
        assert readback.status_code == 200 and readback.json()["state"] == "RECONCILIATION_REQUIRED"
        assert readback.json()["integrity"]["receipt_verified"] is False
        assert decide(http, headers, initial).status_code == 409 and len(dispatch) == 1


@pytest.mark.parametrize("mutation", ["unsigned", "signature", "actor", "summary", "expiry"])
def test_approval_mutation_never_dispatches(env, monkeypatch, mutation):
    with env["client"]() as (http, router):
        headers, _ = session(http, env)
        view = propose(http, headers)
        dispatch = spy_dispatch(router)
        control = router.gex_holder["control"]
        original = control._signed_approval
        def approval(*args):
            result = original(*args)
            if mutation == "unsigned":
                result.pop("signature")
            elif mutation == "signature":
                result["signature"] = "A" * 86
            elif mutation == "actor":
                result["principal_subject"] = "principal_forged"
            elif mutation == "summary":
                result["operation_summary_digest"] = "f" * 64
            else:
                result["expires_at"] = "2000-01-01T00:00:00Z"
            return result
        monkeypatch.setattr(control, "_signed_approval", approval)
        assert decide(http, headers, view).status_code != 200 and not dispatch


@pytest.mark.parametrize("mutation", ["signature", "constraints", "request_digest", "workspace"])
def test_permit_mutation_never_dispatches(env, monkeypatch, mutation):
    from dataclasses import replace
    with env["client"]() as (http, router):
        headers, _ = session(http, env)
        view = propose(http, headers)
        dispatch = spy_dispatch(router)
        original = gc.issue_permit
        def issue(**kwargs):
            permit = original(**kwargs)
            if mutation == "signature":
                return replace(permit, signature="A" * 86)
            if mutation == "constraints":
                return replace(permit, constraints_effective={**gc.CONSTRAINTS, "network": "allowlist"})
            if mutation == "request_digest":
                return replace(permit, request_digest="f" * 64)
            return replace(permit, workspace_binding_fingerprint="f" * 64)
        monkeypatch.setattr(gc, "issue_permit", issue)
        assert decide(http, headers, view).status_code != 200 and not dispatch


def test_expired_session_and_expired_request_deny(env):
    with env["client"]() as (http, router):
        headers, issued = session(http, env)
        view = propose(http, headers)
        dispatch = spy_dispatch(router)
        control = router.gex_holder["control"]
        with control.identity._connection() as db:
            db.execute("UPDATE gex_sessions SET expires_at='2000-01-01T00:00:00Z' WHERE session_id=?", (issued["session_id"],))
        assert decide(http, headers, view).status_code == 401 and not dispatch


def test_credential_cannot_leak_through_task_or_reason(env):
    with env["client"]() as (http, router):
        headers, issued = session(http, env)
        response = http.post("/api/gex/requests", headers=headers, json={"task": "please use " + env["key"]})
        assert response.status_code == 422 and not env["calls"]
        view = propose(http, headers)
        response = http.post("/api/gex/requests/" + view["request_id"] + "/decision", headers=headers,
            json={"request_digest": view["request_digest"], "decision": "APPROVED", "reason": issued["session_token"]})
        assert response.status_code == 422
        assert env["key"] not in response.text and issued["session_token"] not in response.text


def test_missing_key_no_auto_provision_and_external_state_required(env):
    original = (env["state"] / "signing-key.pem").read_bytes()
    (env["state"] / "signing-key.pem").unlink()
    with env["client"]() as (http, _):
        assert http.get("/api/gex/status").json()["state"] == "UNCONFIGURED"
        assert not (env["state"] / "signing-key.pem").exists()
    with pytest.raises(gc.ControlError):
        gc.configured_paths(env["work"] / "state", env["work"])
    assert len(original) > 0


def test_control_corruption_rejected_and_chain_sanitized(env):
    with env["client"]() as (http, router):
        headers, _ = session(http, env)
        view = propose(http, headers)
        ledger = router.gex_holder["control"].ledger
        http.post("/api/gex/requests", headers={"Authorization": "Bearer forged"}, json={"task": "body must not be recorded"})
        with ledger._connect() as db:
            ingress = db.execute("SELECT * FROM ingress_denials ORDER BY seq").fetchall()
        normative = ledger.ingress_receipts()
        assert normative
        for receipt in normative:
            gc.validate("IngressDenialReceiptV1", receipt)
            assert receipt["raw_request_sha256"] == hashlib.sha256(b"ADL:GEX:REJECTED_INGRESS_MARKER:v1\n").hexdigest()
            assert "principal" not in receipt and "request_id" not in receipt
        assert ingress and all("body must" not in str(dict(row)) for row in ingress)
        previous = None
        for seq, row in enumerate(ingress):
            event = dict(row)
            expected = event.pop("event_digest")
            assert event["seq"] == seq and event["prev_hash"] == previous
            assert hashlib.sha256(_canonical(event)).hexdigest() == expected
            previous = expected
        with ledger._transaction() as db:
            db.execute("UPDATE control_records SET record_json='{}' WHERE request_id=?", (view["request_id"],))
        assert http.get("/api/gex/requests/" + view["request_id"], headers=headers).status_code == 409


def test_provisioning_refuses_conflict_preserves_key(env):
    before = (env["state"] / "signing-key.pem").read_bytes()
    with pytest.raises(gc.ControlError, match="PROVISIONING_CONFLICT"):
        gc.provision(state_dir=env["state"], workspace=env["work"], principal_id="principal_new", agent_id=AGENT, load_agent=env["load"])
    assert (env["state"] / "signing-key.pem").read_bytes() == before
