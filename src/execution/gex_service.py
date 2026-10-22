"""Fail-closed orchestration for the single synthetic GEX fixture read."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Callable
import uuid

from src.execution.adapters.fixture_read import (
    FIXTURE_ID, FixtureReadRequest, FixtureSandboxBackend, FixtureReadPolicy, sandbox_operation,
)
from src.execution.adapters.fixture_observer import observe_fixture_output
from src.execution.identity import AuthenticatedPrincipal, GexIdentityStore
from src.execution.ledger import ExecutionLedger
from src.execution.permit import PermitKeyRegistry, PermitV1, PermitVerificationContext
from src.execution.permit.permit_v1 import verify_permit
from src.capabilities.manager import workspace_identity
from src.execution.gateway import ExecutionGateway
from src.orchestration.state_graph import AuthorizationDecision, EffectType, ExecutionRequest, Permit
from src.sandbox.manager import SandboxManager, SandboxRequest
from src.sandbox.specification import SandboxProfile


@dataclass(frozen=True)
class FixtureExecutionReceipt:
    request_id: str
    request_digest: str
    permit_id: str
    attempt_id: str
    sandbox_receipt: dict[str, object]
    fixture_sha256: str
    result_state: str
    verification_result_id: str
    verification_state: str
    observed_sha256: str | None
    output: str | None = None


class GexExecutionService:
    """Authenticated, signed, single-use execution of one immutable fixture.

    Public fixture routes supply validated whole-envelope authority. The
    explicit legacy library seam is retained for compatibility tests only;
    neither seam enables generic agent/tool execution.
    """

    def __init__(self, *, identity_store: GexIdentityStore, ledger: ExecutionLedger,
                 keys: PermitKeyRegistry, workspace_root: Path | str,
                 agent_exists: Callable[[str], bool], gateway: ExecutionGateway | None = None):
        self.identity_store = identity_store
        self.ledger = ledger
        self.keys = keys
        self.workspace_root = Path(workspace_root).expanduser().resolve()
        if not self.workspace_root.is_dir():
            raise ValueError("backend fixture workspace must be an existing directory")
        self.agent_exists = agent_exists
        manager = SandboxManager(backend=FixtureSandboxBackend(), policy=FixtureReadPolicy())
        self.gateway = gateway or ExecutionGateway(sandbox_manager=manager)

    @staticmethod
    def request_digest(request: FixtureReadRequest) -> str:
        body = {"contract_version": "gex-fixture-request/v1", "fixture_id": request.fixture_id,
                "operation": "READ", "request_id": request.request_id}
        canonical = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

    @staticmethod
    def permit_principal(principal: AuthenticatedPrincipal) -> AuthenticatedPrincipal:
        """Adapt W14's opaque workspace key to W15's fixed-width fingerprint.

        The transformed value is derived only from the server-resolved scope;
        callers must use this helper when creating AuthorizationClaims/PermitV1.
        """
        return replace(principal, workspace_id=hashlib.sha256(
            ("ADL:GEX:WORKSPACE:v1\n" + principal.workspace_id).encode("utf-8")).hexdigest())

    def execute_fixture_read(self, *, session_token: str, request: FixtureReadRequest,
                             permit: PermitV1, now: datetime | None = None,
                             authority=None) -> FixtureExecutionReceipt:
        if not isinstance(request, FixtureReadRequest) or request.fixture_id != FIXTURE_ID:
            raise ValueError("only a typed read of the registered fixture is supported")
        instant = now or datetime.now(timezone.utc)
        resolved_principal = self.identity_store.authenticate_session(
            session_token, requested_agent_id=self._permit_agent(permit),
            agent_exists=self.agent_exists, now=instant)
        if workspace_identity(self.workspace_root)[0] != resolved_principal.workspace_id:
            raise ValueError("fixture adapter workspace differs from the authenticated workspace")
        if authority is None:
            # Explicit legacy library seam, never called by the public router.
            principal = self.permit_principal(resolved_principal)
            request_digest = self.request_digest(request)
        else:
            from src.execution.gex_control import ValidatedExecutionAuthority, whole_request_digest
            if not isinstance(authority, ValidatedExecutionAuthority) or authority.principal != resolved_principal:
                raise ValueError("validated whole-request authority required")
            envelope = authority.validate_live()
            request_digest = whole_request_digest(envelope)
            if envelope != authority.request or envelope["request_id"] != request.request_id:
                raise ValueError("immutable whole-request binding mismatch")
            if envelope["operation"]["arguments"] != {"fixture_id": request.fixture_id}:
                raise ValueError("typed operation differs from immutable request")
            principal = replace(resolved_principal, workspace_id=envelope["workspace"]["binding_fingerprint"])
            expected = {"agent_config_digest": envelope["agent"]["config_digest"],
                        "registry_digest": envelope["capability"]["registry_digest"],
                        "capability_version": envelope["capability"]["version"],
                        "policy_revision": envelope["policy"]["revision"],
                        "constraints_effective": envelope["constraints"]}
            claims = permit.to_dict()
            if any(claims[key] != value for key, value in expected.items()):
                raise ValueError("permit differs from whole-request authority")
        if permit.request_digest != request_digest:
            raise ValueError("signed permit is not bound to this exact fixture request")
        if permit.capability_id != "fixture.read" or permit.effect_scope != "read:fixture:sample":
            raise ValueError("signed permit does not authorize the registered fixture read")
        if permit.operation_digest != request.operation_digest:
            raise ValueError("signed permit operation digest does not match the fixture operation")
        context = self._verification_context(principal, session_token, request_digest, instant,
                                             workspace_fingerprint=principal.workspace_id if authority else None)
        verified = verify_permit(permit, keys=self.keys, context=context)
        if verified.constraints_effective.get("sandbox_profile") != SandboxProfile.READ_ONLY_AGENT.value:
            raise ValueError("signed permit must select the read-only sandbox profile")
        if verified.constraints_effective.get("network") != "deny":
            raise ValueError("signed permit must deny network access")

        # The permit must have been registered durably by the trusted control plane.
        def immediately_before_cas():
            if authority is not None:
                fresh = authority.validate_live()
                if fresh != authority.request or whole_request_digest(fresh) != request_digest:
                    raise ValueError("whole authority changed before dispatch")
        attempt_id = self.ledger.consume_for_dispatch(
            permit=verified, keys=self.keys, context=context, request_id=request.request_id, now=instant,
            live_authority=immediately_before_cas if authority else None)
        legacy_request = ExecutionRequest(
            request_id=request.request_id, tool_name="fixture.read", effect_type=EffectType.READ,
            parameters={"fixture_id": FIXTURE_ID}, proposed_by=principal.agent_id,
            context_revision=authority.request["context_revision"] if authority else "gex-fixture-v1", timestamp=instant.isoformat())
        legacy_permit = Permit(
            permit_id=verified.permit_id, request_id=request.request_id,
            decision=AuthorizationDecision.ALLOW, rationale="verified PermitV1 bridge",
            constraints=[f"sandbox_profile={SandboxProfile.READ_ONLY_AGENT.value}",
                         f"workspace_root={self.workspace_root}", "network=deny",
                         "capability=filesystem_read", "timeout_seconds=1", "write_scope=none",
                         "max_output_bytes=" + str(verified.constraints_effective["max_output_bytes"])],
            issued_at=verified.issued_at, expires_at=verified.expires_at, signed_by=verified.issuer)
        sandbox_request = SandboxRequest(
            request_id=request.request_id, workspace_root=self.workspace_root,
            operation=sandbox_operation(request), requested_profile=SandboxProfile.READ_ONLY_AGENT)
        try:
            if authority is not None:
                # A committed reservation is not permission to dispatch stale
                # authority after scheduling/lock delay. Never replay it.
                immediately_before_cas()
                verify_permit(verified, keys=self.keys, context=self._verification_context(
                    principal, session_token, request_digest, datetime.now(timezone.utc),
                    workspace_fingerprint=principal.workspace_id))
                self.ledger.record_attempt_started(attempt_id)
                immediately_before_cas()
            result = self.gateway.execute(request=legacy_request, permit=legacy_permit,
                                          sandbox_request=sandbox_request)
        except Exception:
            # The effect may have happened before an exception. Never turn that
            # uncertain state into success, including after a process restart.
            self.ledger.require_reconciliation(attempt_id, now=instant)
            raise
        output_bytes = result.value.encode("utf-8") if isinstance(result.value, str) else None
        if output_bytes is not None and len(output_bytes) > verified.constraints_effective["max_output_bytes"]:
            self.ledger.require_reconciliation(attempt_id, now=instant)
            raise ValueError("fixture executor output exceeds signed byte limit")
        executor_hash = hashlib.sha256(output_bytes).hexdigest() if output_bytes is not None else None
        try:
            observed_bytes = observe_fixture_output(request.fixture_id)
            observed_hash = hashlib.sha256(observed_bytes).hexdigest()
        except Exception:
            observed_hash = None
        sandbox_receipt = result.receipt.to_dict()
        sandbox_receipt["gex_effective_constraints"] = verified.to_dict()["constraints_effective"]
        terminal = self.ledger.persist_terminal_verification(
            receipt_id=result.receipt.receipt_id,
            verification_result_id="gexverify_" + uuid.uuid4().hex,
            attempt_id=attempt_id, request_id=request.request_id,
            request_digest=request_digest, permit_id=verified.permit_id,
            receipt=sandbox_receipt,
            result_state="EXECUTOR_SUCCESS" if result.receipt.status.value == "SUCCESS" else "EXECUTOR_FAILURE",
            executor_output_sha256=executor_hash, observed_output_sha256=observed_hash,
            now=instant)
        return FixtureExecutionReceipt(
            request_id=request.request_id, request_digest=request_digest,
            permit_id=verified.permit_id, attempt_id=attempt_id,
            sandbox_receipt=sandbox_receipt,
            fixture_sha256=executor_hash or "",
            result_state=terminal.verification_state,
            verification_result_id=terminal.verification_result_id,
            verification_state=terminal.verification_state,
            observed_sha256=observed_hash,
            output=result.value if isinstance(result.value, str) else None)

    @staticmethod
    def _permit_agent(permit: PermitV1) -> str:
        if not isinstance(permit, PermitV1):
            raise ValueError("a signed PermitV1 is required")
        return permit.agent_id

    def _verification_context(self, principal: AuthenticatedPrincipal, session_token: str,
                              request_digest: str, now: datetime,
                              workspace_fingerprint: str | None = None) -> PermitVerificationContext:
        def active(candidate: AuthenticatedPrincipal) -> bool:
            try:
                live = self.identity_store.authenticate_session(
                    session_token, requested_agent_id=candidate.agent_id,
                    agent_exists=self.agent_exists,
                    now=datetime.now(timezone.utc) if workspace_fingerprint else now)
                if workspace_fingerprint is not None:
                    if workspace_identity(self.workspace_root)[0] != live.workspace_id:
                        return False
                    return replace(live, workspace_id=workspace_fingerprint) == candidate
                return self.permit_principal(live) == candidate
            except Exception:
                return False
        return PermitVerificationContext(request_digest=request_digest, principal=principal, now=now,
                                         is_revoked=lambda _: False, is_session_active=active)
