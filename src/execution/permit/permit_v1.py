"""Ed25519 issuance and validation for immutable GEX PermitV1 claims.

This module deliberately does not consume permits or authorize dispatch. A
durable store must separately check/revoke PermitUseStateV1 before execution.
"""

from __future__ import annotations

import base64
import hashlib
import json
import math
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from types import MappingProxyType
from typing import Callable, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from src.execution.identity import AuthenticatedPrincipal


_DOMAIN = b"ADL:GEX:PERMIT:v1\n"
_HEX256 = re.compile(r"^[0-9a-f]{64}$")
_B64URL_SIG = re.compile(r"^[A-Za-z0-9_-]{86}$")
_CLAIM_KEYS = frozenset({
    "contract_version", "permit_id", "request_digest", "principal_subject",
    "session_binding", "agent_id", "agent_config_digest",
    "workspace_binding_fingerprint", "capability_id", "capability_version",
    "registry_digest", "effect_scope", "operation_digest", "policy_revision",
    "constraints_effective", "issuer", "key_id", "signature",
    "signature_algorithm", "issued_at", "not_before", "expires_at",
    "max_uses", "authorization_source",
})


class PermitError(ValueError):
    """Permit input, authorization, or signature failed validation."""


def _canonical(value: object) -> bytes:
    """Serialize the PermitV1 I-JSON subset using RFC 8785 property ordering.

    Permit claims contain strings, booleans, nulls, arrays, objects and bounded
    integers only. Floating point values are rejected so Python's number
    formatting can never diverge from ECMAScript/JCS number serialization.
    Object names are ordered by UTF-16 code units as required by JCS.
    """

    def encode(item: object) -> str:
        if item is None:
            return "null"
        if item is True:
            return "true"
        if item is False:
            return "false"
        if isinstance(item, str):
            return json.dumps(item, ensure_ascii=False, separators=(",", ":"))
        if isinstance(item, int) and not isinstance(item, bool):
            if abs(item) > 9007199254740991:
                raise PermitError("integer is outside the I-JSON safe range")
            return str(item)
        if isinstance(item, float):
            if not math.isfinite(item):
                raise PermitError("non-finite numbers are not valid I-JSON")
            raise PermitError("floating point values are not allowed in PermitV1 claims")
        if isinstance(item, (list, tuple)):
            return "[" + ",".join(encode(child) for child in item) + "]"
        if isinstance(item, Mapping):
            if any(not isinstance(key, str) for key in item):
                raise PermitError("JCS object keys must be strings")
            keys = sorted(item, key=lambda key: key.encode("utf-16-be", errors="strict"))
            return "{" + ",".join(encode(key) + ":" + encode(item[key]) for key in keys) + "}"
        raise PermitError(f"unsupported JCS value type: {type(item).__name__}")

    try:
        return encode(value).encode("utf-8", errors="strict")
    except UnicodeEncodeError as exc:
        raise PermitError("claims contain invalid Unicode") from exc


def _freeze(value: object) -> object:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(child) for key, child in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(child) for child in value)
    return value


def _thaw(value: object) -> object:
    if isinstance(value, Mapping):
        return {key: _thaw(child) for key, child in value.items()}
    if isinstance(value, tuple):
        return [_thaw(child) for child in value]
    return value


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise PermitError("timestamps must include a timezone")
    return value.astimezone(timezone.utc)


def _stamp(value: datetime) -> str:
    return _utc(value).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _parse_stamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError) as exc:
        raise PermitError("invalid permit timestamp") from exc
    return _utc(parsed)


@dataclass(frozen=True)
class AuthorizationClaims:
    """Server-verified authorization inputs; never construct from agent payload."""

    request_digest: str
    agent_config_digest: str
    capability_id: str
    capability_version: str
    registry_digest: str
    effect_scope: str
    operation_digest: str
    policy_revision: str
    constraints_effective: Mapping[str, object]
    decision_id: str
    approval_id: str | None = None
    auto_rule_id: str | None = None


@dataclass(frozen=True)
class PermitV1:
    """Frozen claims object; mutable use/revocation state is intentionally absent."""

    contract_version: str
    permit_id: str
    request_digest: str
    principal_subject: str
    session_binding: str
    agent_id: str
    agent_config_digest: str
    workspace_binding_fingerprint: str
    capability_id: str
    capability_version: str
    registry_digest: str
    effect_scope: str
    operation_digest: str
    policy_revision: str
    constraints_effective: Mapping[str, object]
    issuer: str
    key_id: str
    signature: str
    signature_algorithm: str
    issued_at: str
    not_before: str
    expires_at: str
    max_uses: int
    authorization_source: Mapping[str, object]

    def to_dict(self) -> dict[str, object]:
        """Return a detached JSON-compatible snapshot of all signed claims."""
        return {key: _thaw(value) for key, value in self.__dict__.items()}


@dataclass(frozen=True)
class PermitVerificationContext:
    request_digest: str
    principal: AuthenticatedPrincipal
    now: datetime
    is_revoked: Callable[[str], bool]
    is_session_active: Callable[[AuthenticatedPrincipal], bool]


class PermitKeyRegistry:
    """Issuer/key-id scoped key selection with an explicit active signing key."""

    def __init__(self, *, issuer: str, active_key_id: str,
                 private_keys: Mapping[str, Ed25519PrivateKey],
                 public_keys: Mapping[str, Ed25519PublicKey]):
        if not issuer or not active_key_id:
            raise PermitError("issuer and active key id are required")
        if active_key_id not in private_keys or active_key_id not in public_keys:
            raise PermitError("active key id needs signing and verification keys")
        if any(not isinstance(key, Ed25519PrivateKey) for key in private_keys.values()):
            raise PermitError("all private signing keys must be Ed25519")
        if any(not isinstance(key, Ed25519PublicKey) for key in public_keys.values()):
            raise PermitError("all verification keys must be Ed25519")
        active_public = private_keys[active_key_id].public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        registered_public = public_keys[active_key_id].public_bytes(Encoding.Raw, PublicFormat.Raw)
        if active_public != registered_public:
            raise PermitError("active signing and verification keys do not match")
        self.issuer = issuer
        self.active_key_id = active_key_id
        self._private_keys = dict(private_keys)
        self._public_keys = dict(public_keys)

    def signing_key(self) -> Ed25519PrivateKey:
        try:
            return self._private_keys[self.active_key_id]
        except KeyError as exc:
            raise PermitError("active signing key is unavailable") from exc

    def verification_key(self, issuer: str, key_id: str) -> Ed25519PublicKey:
        if issuer != self.issuer:
            raise PermitError("permit issuer is not trusted")
        try:
            return self._public_keys[key_id]
        except KeyError as exc:
            raise PermitError("permit key id is unknown or retired") from exc


def _claims_for_signature(claims: Mapping[str, object]) -> bytes:
    if set(claims) != _CLAIM_KEYS:
        missing, extra = sorted(_CLAIM_KEYS - set(claims)), sorted(set(claims) - _CLAIM_KEYS)
        raise PermitError(f"PermitV1 claim set mismatch (missing={missing}, extra={extra})")
    if claims.get("contract_version") != "gex-permit/v1":
        raise PermitError("legacy or unsupported permit contract cannot be promoted to PermitV1")
    if claims.get("signature_algorithm") != "Ed25519":
        raise PermitError("production PermitV1 accepts Ed25519 only")
    unsigned = {key: value for key, value in claims.items() if key != "signature"}
    return _DOMAIN + _canonical(unsigned)


def _validate_claims(claims: Mapping[str, object]) -> None:
    if set(claims) != _CLAIM_KEYS:
        raise PermitError("PermitV1 does not match the complete canonical claim set")
    for key in ("request_digest", "session_binding", "agent_config_digest",
                "workspace_binding_fingerprint", "registry_digest", "operation_digest"):
        value = claims.get(key)
        if not isinstance(value, str) or not _HEX256.fullmatch(value):
            raise PermitError(f"invalid {key}")
    for key in ("permit_id", "principal_subject", "agent_id", "capability_id",
                "capability_version", "effect_scope", "policy_revision", "issuer", "key_id"):
        if not isinstance(claims.get(key), str) or not claims[key] or len(claims[key]) > 256:
            raise PermitError(f"invalid {key}")
    if claims.get("contract_version") != "gex-permit/v1":
        raise PermitError("legacy or unsupported permit contract cannot be promoted to PermitV1")
    if claims.get("signature_algorithm") != "Ed25519":
        raise PermitError("production PermitV1 accepts Ed25519 only")
    signature = claims.get("signature")
    if not isinstance(signature, str) or len(signature) > 256:
        raise PermitError("invalid signature member")
    if claims.get("max_uses") != 1 or isinstance(claims.get("max_uses"), bool):
        raise PermitError("PermitV1 max_uses must be exactly one")
    constraints = claims.get("constraints_effective")
    if not isinstance(constraints, Mapping):
        raise PermitError("constraints_effective must be an object")
    required_constraints = {"sandbox_profile", "network", "timeout_ms", "max_output_bytes",
                            "write_scope", "egress_allowlist"}
    if set(constraints) != required_constraints:
        raise PermitError("constraints_effective does not match the canonical Constraints schema")
    if (not isinstance(constraints["sandbox_profile"], str) or not constraints["sandbox_profile"]
            or len(constraints["sandbox_profile"]) > 256
            or constraints["network"] not in ("deny", "allowlist")
            or not isinstance(constraints["timeout_ms"], int) or isinstance(constraints["timeout_ms"], bool)
            or not 1 <= constraints["timeout_ms"] <= 3_600_000
            or not isinstance(constraints["max_output_bytes"], int) or isinstance(constraints["max_output_bytes"], bool)
            or constraints["max_output_bytes"] < 1
            or not isinstance(constraints["write_scope"], str) or not constraints["write_scope"]
            or len(constraints["write_scope"]) > 256
            or not isinstance(constraints["egress_allowlist"], (list, tuple))
            or any(not isinstance(host, str) or not host or len(host) > 256 for host in constraints["egress_allowlist"])
            or len(set(constraints["egress_allowlist"])) != len(constraints["egress_allowlist"])):
        raise PermitError("constraints_effective values do not match the canonical Constraints schema")
    source = claims.get("authorization_source")
    if not isinstance(source, Mapping) or set(source) != {"decision_id", "approval_id", "auto_rule_id"}:
        raise PermitError("authorization_source does not match schema")
    if not isinstance(source["decision_id"], str) or not source["decision_id"]:
        raise PermitError("authorization source needs a decision id")
    if (source["approval_id"] is None) == (source["auto_rule_id"] is None):
        raise PermitError("exactly one authenticated approval_id or explicit auto_rule_id is required")
    for key in ("approval_id", "auto_rule_id"):
        if source[key] is not None and (not isinstance(source[key], str) or not source[key]):
            raise PermitError(f"invalid authorization_source.{key}")
    issued, not_before, expires = (_parse_stamp(claims[key]) for key in ("issued_at", "not_before", "expires_at"))
    if not (issued <= not_before < expires):
        raise PermitError("permit time window is inconsistent")


def issue_permit(*, principal: AuthenticatedPrincipal, authorization: AuthorizationClaims,
                 keys: PermitKeyRegistry, ttl_seconds: int = 300,
                 now: datetime | None = None, not_before: datetime | None = None) -> PermitV1:
    """Sign a server-authorized PermitV1. This function does not infer approval."""
    if not isinstance(principal, AuthenticatedPrincipal):
        raise PermitError("authenticated principal resolution is required")
    if not isinstance(authorization, AuthorizationClaims):
        raise PermitError("server-verified authorization claims are required")
    if isinstance(ttl_seconds, bool) or not isinstance(ttl_seconds, int) or not 1 <= ttl_seconds <= 3600:
        raise PermitError("permit lifetime must be between 1 and 3600 seconds")
    issued = _utc(now or datetime.now(timezone.utc))
    begins = _utc(not_before or issued)
    expires = issued + timedelta(seconds=ttl_seconds)
    source = {"decision_id": authorization.decision_id,
              "approval_id": authorization.approval_id, "auto_rule_id": authorization.auto_rule_id}
    claims: dict[str, object] = {
        "contract_version": "gex-permit/v1",
        "permit_id": "gexpermit_" + uuid.uuid4().hex,
        "request_digest": authorization.request_digest,
        "principal_subject": principal.principal_id,
        "session_binding": hashlib.sha256(b"ADL:GEX:SESSION:v1\n" + principal.session_id.encode("utf-8")).hexdigest(),
        "agent_id": principal.agent_id,
        "agent_config_digest": authorization.agent_config_digest,
        "workspace_binding_fingerprint": principal.workspace_id,
        "capability_id": authorization.capability_id,
        "capability_version": authorization.capability_version,
        "registry_digest": authorization.registry_digest,
        "effect_scope": authorization.effect_scope,
        "operation_digest": authorization.operation_digest,
        "policy_revision": authorization.policy_revision,
        "constraints_effective": dict(authorization.constraints_effective),
        "issuer": keys.issuer,
        "key_id": keys.active_key_id,
        "signature": "",
        "signature_algorithm": "Ed25519",
        "issued_at": _stamp(issued),
        "not_before": _stamp(begins),
        "expires_at": _stamp(expires),
        "max_uses": 1,
        "authorization_source": source,
    }
    _validate_claims(claims)
    claims["signature"] = base64.urlsafe_b64encode(keys.signing_key().sign(_claims_for_signature(claims))).decode("ascii").rstrip("=")
    return PermitV1(**{key: _freeze(value) for key, value in claims.items()})


def verify_permit(permit: PermitV1 | Mapping[str, object], *, keys: PermitKeyRegistry,
                  context: PermitVerificationContext) -> PermitV1:
    """Verify full claims, signature, live identity, expiry, revocation and request binding."""
    if isinstance(permit, PermitV1):
        claims = permit.to_dict()
    elif isinstance(permit, Mapping):
        claims = dict(permit)
    else:
        raise PermitError("expected a PermitV1 value")
    _validate_claims(claims)
    signature = claims.get("signature")
    if not isinstance(signature, str) or not _B64URL_SIG.fullmatch(signature):
        raise PermitError("signature must be canonical unpadded Base64url Ed25519")
    try:
        raw_signature = base64.urlsafe_b64decode(signature + "==")
        if base64.urlsafe_b64encode(raw_signature).decode("ascii").rstrip("=") != signature:
            raise PermitError("non-canonical signature encoding")
        keys.verification_key(str(claims["issuer"]), str(claims["key_id"])).verify(
            raw_signature, _claims_for_signature(claims))
    except InvalidSignature as exc:
        raise PermitError("PermitV1 signature is invalid") from exc
    except (ValueError, TypeError) as exc:
        if isinstance(exc, PermitError):
            raise
        raise PermitError("PermitV1 signature is malformed") from exc

    if not isinstance(context, PermitVerificationContext):
        raise PermitError("live verification context is required")
    principal = context.principal
    if not isinstance(principal, AuthenticatedPrincipal):
        raise PermitError("authenticated principal resolution is required")
    if claims["request_digest"] != context.request_digest:
        raise PermitError("permit request digest does not match the execution request")
    expected_session = hashlib.sha256(b"ADL:GEX:SESSION:v1\n" + principal.session_id.encode("utf-8")).hexdigest()
    expected = {"principal_subject": principal.principal_id, "agent_id": principal.agent_id,
                "workspace_binding_fingerprint": principal.workspace_id,
                "session_binding": expected_session}
    if any(claims[key] != value for key, value in expected.items()):
        raise PermitError("permit identity, session, agent, or workspace binding mismatch")
    instant = _utc(context.now)
    if instant >= _parse_stamp(principal.expires_at):
        raise PermitError("authenticated session expired")
    if not callable(context.is_session_active):
        raise PermitError("live session status resolver is unavailable")
    try:
        session_active = context.is_session_active(principal)
    except Exception as exc:
        raise PermitError("session status lookup failed closed") from exc
    if session_active is not True:
        raise PermitError("authenticated session is revoked or inactive")
    if instant < _parse_stamp(str(claims["not_before"])):
        raise PermitError("permit is not yet valid")
    if instant >= _parse_stamp(str(claims["expires_at"])):
        raise PermitError("permit expired")
    if not callable(context.is_revoked):
        raise PermitError("permit revocation resolver is unavailable")
    try:
        revoked = context.is_revoked(str(claims["permit_id"]))
    except Exception as exc:
        raise PermitError("permit revocation lookup failed closed") from exc
    if revoked is not False:
        raise PermitError("permit is revoked or revocation status is unknown")
    return PermitV1(**{key: _freeze(value) for key, value in claims.items()})
