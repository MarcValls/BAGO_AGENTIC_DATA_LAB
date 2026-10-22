from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from src.execution.identity import AuthenticatedPrincipal
from src.execution.permit.permit_v1 import (
    AuthorizationClaims,
    PermitError,
    PermitKeyRegistry,
    PermitVerificationContext,
    _claims_for_signature,
    issue_permit,
    verify_permit,
)


NOW = datetime(2026, 10, 18, 12, 0, tzinfo=timezone.utc)
DIGEST = "a" * 64
CONSTRAINTS = {
    "sandbox_profile": "fixture-read-v1",
    "network": "deny",
    "timeout_ms": 1000,
    "max_output_bytes": 2048,
    "write_scope": "none",
    "egress_allowlist": [],
}


def identity() -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        principal_id="principal_alice",
        workspace_id="b" * 64,
        agent_id="agent_01234567",
        session_id="gexsess_test",
        credential_id="gexcred_test",
        issued_at="2026-10-18T11:00:00.000Z",
        expires_at="2026-10-18T13:00:00.000Z",
    )


def key_registry(key_id: str = "permit-key-2026-01") -> PermitKeyRegistry:
    private = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
    return PermitKeyRegistry(
        issuer="adl-test-authority",
        active_key_id=key_id,
        private_keys={key_id: private},
        public_keys={key_id: private.public_key()},
    )


def authorization(**overrides: object) -> AuthorizationClaims:
    values = {
        "request_digest": DIGEST,
        "agent_config_digest": "c" * 64,
        "capability_id": "fixture.read",
        "capability_version": "1.0.0",
        "registry_digest": "d" * 64,
        "effect_scope": "read:fixture:sample",
        "operation_digest": "e" * 64,
        "policy_revision": "policy-2026-10",
        "constraints_effective": CONSTRAINTS,
        "decision_id": "decision-123",
        "approval_id": "approval-456",
        "auto_rule_id": None,
    }
    values.update(overrides)
    return AuthorizationClaims(**values)


def issue(**kwargs):
    return issue_permit(
        principal=identity(), authorization=authorization(), keys=key_registry(), now=NOW, **kwargs
    )


def context(*, now: datetime = NOW, request_digest: str = DIGEST,
            principal: AuthenticatedPrincipal | None = None, is_revoked=lambda _: False,
            is_session_active=lambda _: True):
    return PermitVerificationContext(
        request_digest=request_digest, principal=principal or identity(), now=now,
        is_revoked=is_revoked, is_session_active=is_session_active
    )


def test_issue_and_verify_complete_ed25519_permit_v1_and_json_schema():
    permit = issue()
    assert permit.contract_version == "gex-permit/v1"
    assert permit.signature_algorithm == "Ed25519"
    assert permit.key_id == "permit-key-2026-01"
    assert len(permit.signature) == 86 and "=" not in permit.signature
    assert verify_permit(permit, keys=key_registry(), context=context()) == permit

    schema_path = Path("docs/governed-execution/GEX_V1_SCHEMA.json")
    from jsonschema import Draft202012Validator

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(permit.to_dict())


def test_signature_is_known_vector_over_all_permit_claims_including_key_id():
    """P2 coverage: deterministic Ed25519 known vector signs complete JCS claims."""
    permit = issue()
    claims = permit.to_dict()
    claims["permit_id"] = "gexpermit_known_vector_0001"
    claims["signature"] = ""
    signed = _claims_for_signature(claims)
    public = key_registry().verification_key("adl-test-authority", "permit-key-2026-01")
    signature = key_registry().signing_key().sign(signed)
    public.verify(signature, signed)
    assert signed.startswith(b"ADL:GEX:PERMIT:v1\n{")
    assert b'"key_id":"permit-key-2026-01"' in signed
    encoded = base64.urlsafe_b64encode(signature).decode("ascii").rstrip("=")
    assert hashlib.sha256(signed).hexdigest() == "a3bdc7d75e76e2e60383fe059e0304c9a1f6f08aaa90c633b83b5587c97b06f5"
    assert encoded == "_R2DUsPvJKmjYdzvvb2ieTb8yAq285PIFyag_kvo8QQE0-FrQRLzpnLX78_eJJBVcoVevsNa8Q1elycsEO1PDQ"


@pytest.mark.parametrize("change", [
    lambda p: p.__setitem__("effect_scope", "write:anything"),
    lambda p: p.__setitem__("key_id", "unknown-key"),
    lambda p: p.__setitem__("issuer", "attacker"),
    lambda p: p.__setitem__("constraints_effective", {**p["constraints_effective"], "network": "allowlist"}),
])
def test_any_signed_claim_tampering_is_rejected(change):
    permit = issue()
    altered = permit.to_dict()
    change(altered)
    with pytest.raises(PermitError):
        verify_permit(altered, keys=key_registry(), context=context())


def test_wrong_key_signature_expiry_not_before_revocation_and_request_mismatch_rejected():
    permit = issue()
    wrong_private = Ed25519PrivateKey.from_private_bytes(bytes(reversed(range(32))))
    wrong_keys = PermitKeyRegistry(
        issuer="adl-test-authority", active_key_id="permit-key-2026-01",
        private_keys={"permit-key-2026-01": wrong_private},
        public_keys={"permit-key-2026-01": wrong_private.public_key()},
    )
    with pytest.raises(PermitError, match="signature is invalid"):
        verify_permit(permit, keys=wrong_keys, context=context())
    with pytest.raises(PermitError, match="request digest"):
        verify_permit(permit, keys=key_registry(), context=context(request_digest="f" * 64))
    with pytest.raises(PermitError, match="expired"):
        verify_permit(permit, keys=key_registry(), context=context(now=NOW + timedelta(minutes=5)))
    with pytest.raises(PermitError, match="not yet valid"):
        verify_permit(permit, keys=key_registry(), context=context(now=NOW - timedelta(seconds=1)))
    with pytest.raises(PermitError, match="revoked"):
        verify_permit(permit, keys=key_registry(), context=context(is_revoked=lambda _: True))
    with pytest.raises(PermitError, match="lookup failed"):
        verify_permit(permit, keys=key_registry(), context=context(is_revoked=lambda _: (_ for _ in ()).throw(OSError())))


def test_identity_session_agent_or_workspace_mismatch_rejected():
    permit = issue()
    wrong_identity = AuthenticatedPrincipal(
        **{**identity().__dict__, "workspace_id": "f" * 64}
    )
    with pytest.raises(PermitError, match="binding mismatch"):
        verify_permit(permit, keys=key_registry(), context=context(principal=wrong_identity))
    with pytest.raises(PermitError, match="session is revoked"):
        verify_permit(permit, keys=key_registry(), context=context(is_session_active=lambda _: False))
    with pytest.raises(PermitError, match="session expired"):
        verify_permit(permit, keys=key_registry(), context=context(now=NOW + timedelta(hours=1)))


def test_authorization_source_requires_exactly_one_approval_or_auto_rule():
    with pytest.raises(PermitError, match="exactly one"):
        issue_permit(principal=identity(), authorization=authorization(approval_id=None), keys=key_registry(), now=NOW)
    with pytest.raises(PermitError, match="exactly one"):
        issue_permit(principal=identity(), authorization=authorization(auto_rule_id="auto-1"), keys=key_registry(), now=NOW)


def test_legacy_permit_cannot_be_promoted_and_signed_claims_are_immutable():
    legacy = {"permit_id": "old", "signed_by": "operator"}
    with pytest.raises(PermitError, match="complete canonical claim set"):
        verify_permit(legacy, keys=key_registry(), context=context())
    permit = issue()
    with pytest.raises(FrozenInstanceError):
        permit.effect_scope = "write"  # type: ignore[misc]
    detached = permit.to_dict()
    detached["constraints_effective"]["network"] = "allowlist"
    assert permit.constraints_effective["network"] == "deny"

