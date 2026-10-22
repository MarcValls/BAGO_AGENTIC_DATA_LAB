from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from src.execution.identity import AuthenticationError, GexIdentityStore, IdentityProvisioningError


AGENT_A = "agent_0123456789abcdef"
AGENT_B = "agent_fedcba9876543210"


def _store(tmp_path):
    return GexIdentityStore(tmp_path / "identity.sqlite3")


def _provision(store, tmp_path, *, agents=(AGENT_A, AGENT_B)):
    return store.provision_principal(
        principal_id="principal_alice",
        workspace_root=tmp_path,
        allowed_agent_ids=list(agents),
    )


def _session(store, api_key, agent_id=AGENT_A, *, now=None):
    return store.create_session(api_key, requested_agent_id=agent_id, ttl_seconds=300, now=now)


def _resolve(store, session_token, agent_id=AGENT_A, existing=(AGENT_A, AGENT_B), *, now=None):
    return store.authenticate_session(
        session_token,
        requested_agent_id=agent_id,
        agent_exists=lambda candidate: candidate in existing,
        now=now,
    )


def test_identity_is_resolved_from_persisted_session_not_client_claims(tmp_path):
    store = _store(tmp_path)
    credential_id, api_key = _provision(store, tmp_path)
    session_id, session_token = _session(store, api_key)

    # The resolver has no principal/workspace arguments to trust from a request.
    resolved = _resolve(store, session_token)

    assert resolved.principal_id == "principal_alice"
    assert resolved.workspace_id.startswith("workspace_")
    assert resolved.agent_id == AGENT_A
    assert resolved.session_id == session_id
    assert resolved.credential_id == credential_id
    assert resolved.principal_id != "principal_attacker"
    assert resolved.workspace_id != "workspace_attacker"


def test_raw_api_and_session_tokens_are_not_stored(tmp_path):
    store = _store(tmp_path)
    _, api_key = _provision(store, tmp_path)
    _, session_token = _session(store, api_key)

    with sqlite3.connect(store.database_path) as connection:
        persisted = " ".join(str(value) for row in connection.execute(
            "SELECT token_sha256 FROM gex_api_credentials UNION ALL SELECT token_sha256 FROM gex_sessions"
        ) for value in row)
    assert api_key not in persisted
    assert session_token not in persisted


def test_session_survives_store_restart(tmp_path):
    store = _store(tmp_path)
    _, api_key = _provision(store, tmp_path)
    _, session_token = _session(store, api_key)

    reopened = GexIdentityStore(store.database_path)

    assert _resolve(reopened, session_token).principal_id == "principal_alice"


@pytest.mark.parametrize("bad_token", [None, "", "bago_gex_session_v1_not-a-valid-token", "not-a-token"])
def test_missing_and_malformed_sessions_fail_closed(tmp_path, bad_token):
    with pytest.raises(AuthenticationError):
        _resolve(_store(tmp_path), bad_token)


def test_unknown_and_revoked_api_credentials_cannot_mint_sessions(tmp_path):
    store = _store(tmp_path)
    _, api_key = _provision(store, tmp_path)

    with pytest.raises(AuthenticationError):
        store.create_session(api_key)
    with pytest.raises(AuthenticationError):
        store.create_session("bago_gex_key_v1_" + "a" * 43)


def test_session_expiration_is_fail_closed_at_expiry_boundary(tmp_path):
    store = _store(tmp_path)
    now = datetime(2026, 10, 18, 12, 0, tzinfo=timezone.utc)
    _, api_key = store.provision_principal(
        principal_id="principal_alice", workspace_root=tmp_path,
        allowed_agent_ids=[AGENT_A], now=now,
    )
    _, token = store.create_session(api_key, requested_agent_id=AGENT_A, ttl_seconds=60, now=now)

    assert _resolve(store, token, existing=(AGENT_A,), now=now + timedelta(seconds=59)).principal_id == "principal_alice"
    with pytest.raises(AuthenticationError, match="expired"):
        _resolve(store, token, existing=(AGENT_A,), now=now + timedelta(seconds=60))


def test_revoked_session_and_cross_principal_revocation_fail_closed(tmp_path):
    store = _store(tmp_path)
    _, api_key = _provision(store, tmp_path)
    session_id, token = _session(store, api_key)
    _, bob_key = store.provision_principal(
        principal_id="principal_bob", workspace_root=tmp_path, allowed_agent_ids=[AGENT_A]
    )
    _, bob_token = _session(store, bob_key)

    assert not store.revoke_session(
        session_id, requester_session_token=bob_token, requester_agent_id=AGENT_A,
        agent_exists=lambda candidate: candidate == AGENT_A,
    )
    assert store.revoke_session(
        session_id, requester_session_token=token, requester_agent_id=AGENT_A,
        agent_exists=lambda candidate: candidate == AGENT_A,
    )
    with pytest.raises(AuthenticationError, match="revoked"):
        _resolve(store, token)


def test_api_credential_revocation_revokes_its_existing_sessions(tmp_path):
    store = _store(tmp_path)
    credential_id, api_key = _provision(store, tmp_path)
    _, token = _session(store, api_key)

    assert store.revoke_api_credential(
        credential_id, requester_session_token=token, requester_agent_id=AGENT_A,
        agent_exists=lambda candidate: candidate in {AGENT_A, AGENT_B},
    )
    with pytest.raises(AuthenticationError, match="revoked"):
        _resolve(store, token)


def test_agent_scope_and_backend_agent_lookup_are_enforced(tmp_path):
    store = _store(tmp_path)
    _, api_key = _provision(store, tmp_path, agents=(AGENT_A,))
    _, token = _session(store, api_key)

    with pytest.raises(AuthenticationError, match="outside"):
        _resolve(store, token, AGENT_B)
    with pytest.raises(AuthenticationError, match="unavailable"):
        _resolve(store, token, existing=())


def test_principal_deactivation_revokes_identity_and_sessions(tmp_path):
    store = _store(tmp_path)
    _, api_key = _provision(store, tmp_path)
    _, token = _session(store, api_key)

    assert store.deactivate_principal("principal_alice")
    with pytest.raises(AuthenticationError, match="revoked"):
        _resolve(store, token)
    with pytest.raises(AuthenticationError):
        store.create_session(api_key)


def test_provisioning_rejects_client_controlled_or_malformed_identity(tmp_path):
    store = _store(tmp_path)
    with pytest.raises(IdentityProvisioningError):
        store.provision_principal(
            principal_id="alice",
            workspace_root=tmp_path,
            allowed_agent_ids=[AGENT_A],
        )
    with pytest.raises(IdentityProvisioningError):
        store.provision_principal(
            principal_id="principal_alice",
            workspace_root=tmp_path,
            allowed_agent_ids=["../outside"],
        )


@pytest.mark.parametrize("ttl", [0, -1, 13 * 60 * 60, True, 60.5])
def test_session_lifetime_outside_policy_is_rejected(tmp_path, ttl):
    store = _store(tmp_path)
    _, api_key = _provision(store, tmp_path)
    with pytest.raises(AuthenticationError, match="lifetime"):
        store.create_session(api_key, ttl_seconds=ttl)
