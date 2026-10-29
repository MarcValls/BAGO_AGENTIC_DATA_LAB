"""SPEC_ONLY browser-bridge P1: schema, compatibility and reference vectors.

These tests NEVER exercise Chrome, install a host, authorize GEX or prove
the sufficiency of real-world browser grants. They only validate the proposed
contract package and the separation of verification from execution.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker, ValidationError


ROOT = Path(__file__).resolve().parents[3]
P1 = ROOT / "docs/plans/browser-bridge-v0.1"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


SCHEMA = load(P1 / "P1_BROWSER_SCHEMA.json")
VECTORS = load(P1 / "P1_VECTORS.json")
MAP = load(P1 / "P1_CONTROL_MAP.json")
GEX_SCHEMA = load(ROOT / "docs/governed-execution/GEX_V1_SCHEMA.json")
DOMAIN_SCHEMA = load(ROOT / "docs/domain-conformance/source/05_DOMAIN_MANIFEST.schema.json")
VALIDATOR = Draft202012Validator(SCHEMA, format_checker=FormatChecker())
H = "a" * 64
X = "abcdefghijklmnopabcdefghijklmnop"
STAMP = "2026-10-29T10:00:00Z"


def samples():
    profile = {
        "contract_version": "adl.browser.capability-profile.v1",
        "capability_id": "browser.document.read", "capability_version": "0.1.0",
        "effect": "READ", "executor_kind": "browser_native",
        "enablement": "DISABLED", "registration_authority": "ADL_GEX_BACKEND",
        "input_schema_digest": H, "registry_digest": H,
        "policy_revision": "browser-read-p1", "host_name": "com.bago.adl.browser_bridge",
        "extension_id": X, "grant_requirement": "CHROME_ACTIVE_TAB_USER_INVOCATION",
        "principal_origin": "BACKEND_AUTHENTICATED",
        "browser_content_trust": "UNTRUSTED_DATA",
        "network_scope": "HOST_LOOPBACK_TO_ADL_ONLY", "write_scope": "none",
        "max_output_bytes": 65536, "max_timeout_ms": 5000,
    }
    binding = {
        "contract_version": "adl.browser.shared-tab-binding.v1",
        "binding_id": H, "adl_instance_id": "adl-instance-1",
        "workspace_binding_fingerprint": H, "bridge_session_id": "bridge-1",
        "extension_id": X, "tab_id": 13, "document_epoch": "nav-1",
        "origin": "https://example.test", "invocation_event_ref": "user-click-1",
        "grant_claim": "CHROME_ACTIVE_TAB_USER_INVOCATION",
        "state": "SHARED", "expires_at": STAMP,
    }
    dispatch = {
        "contract_version": "adl.browser.dispatch.v1",
        "capability_id": "browser.document.read", "capability_version": "0.1.0",
        "request_id": "0ab73c0b-87a0-44aa-88f0-95cb488c0939",
        "request_digest": H, "attempt_id": "attempt-1", "permit_id": "permit-1",
        "dispatch_intent_event_id": "gex-ledger-event-1",
        "registry_digest": H, "policy_revision": "browser-read-p1",
        "adl_instance_id": "adl-instance-1", "workspace_binding_fingerprint": H,
        "bridge_session_id": "bridge-1", "binding_id": H, "document_epoch": "nav-1",
        "origin": "https://example.test", "initiator_kind": "HUMAN",
        "initiator_ref": "server-resolved-user-1", "session_key_id": "pair-1",
        "sequence": 1, "nonce": "nonce-1", "expires_at": STAMP,
        "limits": {"max_output_bytes": 65536, "timeout_ms": 5000},
        "message_auth_tag": H,
    }
    observation = {
        "contract_version": "adl.browser.read-observation.v1",
        "request_digest": H, "attempt_id": "attempt-1", "binding_id": H,
        "document_epoch": "nav-1", "status": "OBSERVED", "output_sha256": H,
        "output_bytes": 32, "truncated": False, "observed_at": STAMP,
        "error_code": None,
    }
    request_v2 = {
        "contract_version": "adl.browser.gex-request.v2",
        "request_id": "0ab73c0b-87a0-44aa-88f0-95cb488c0939",
        "run_id": "run-1", "proposal_id": "proposal-1",
        "principal": {"issuer": "adl-auth", "subject": "user-1",
                      "session_binding": H, "auth_strength": "verified"},
        "initiator": {"kind": "HUMAN", "actor_ref": "user-1"},
        "adl_instance_id": "adl-instance-1",
        "workspace_binding_fingerprint": H,
        "capability_id": "browser.document.read",
        "capability_version": "0.1.0",
        "registry_digest": H, "policy_revision": "browser-read-p1",
        "shared_tab_binding_id": H, "document_epoch": "nav-1",
        "origin": "https://example.test",
        "constraints": {"max_output_bytes": 65536, "timeout_ms": 5000},
        "created_at": STAMP, "expires_at": STAMP,
        "nonce": "nonce-1",
    }
    return profile, binding, dispatch, observation, request_v2


def test_schema_compiles_and_has_five_disjoint_contracts():
    Draft202012Validator.check_schema(SCHEMA)
    assert SCHEMA["$schema"].endswith("/2020-12/schema")
    for item in samples():
        assert VALIDATOR.is_valid(item), list(VALIDATOR.iter_errors(item))


@pytest.mark.parametrize("index", range(5))
def test_closed_messages_reject_unknown_fields(index):
    item = copy.deepcopy(samples()[index])
    item["can_execute_unrestricted"] = True
    with pytest.raises(ValidationError):
        VALIDATOR.validate(item)


@pytest.mark.parametrize("field,value", [
    ("effect", "WRITE"),
    ("executor_kind", "local"),
    ("registration_authority", "EXTENSION"),
    ("grant_requirement", "CHAT_REQUEST"),
    ("network_scope", "UNRESTRICTED"),
    ("write_scope", "any"),
    ("max_output_bytes", 65537),
    ("max_timeout_ms", 5001),
])
def test_profile_rejects_privilege_escalation(field, value):
    profile = copy.deepcopy(samples()[0])
    profile[field] = value
    with pytest.raises(ValidationError):
        VALIDATOR.validate(profile)


@pytest.mark.parametrize("field,value", [
    ("extension_id", "untrusted-extension"),
    ("origin", "chrome://settings"),
    ("origin", "https://user:token@example.test"),
    ("origin", "https://example.test/path?token=value"),
    ("origin", "https://example.test#fragment"),
    ("grant_claim", "LLM_INSTRUCTION"),
    ("tab_id", -1),
])
def test_binding_rejects_invalid_grant_shape(field, value):
    binding = copy.deepcopy(samples()[1])
    binding[field] = value
    with pytest.raises(ValidationError):
        VALIDATOR.validate(binding)


@pytest.mark.parametrize("field,value", [
    ("capability_id", "browser.form.submit"),
    ("initiator_kind", "SYSTEM"),
    ("limits", {"max_output_bytes": 131072, "timeout_ms": 5000}),
    ("message_auth_tag", "unchecked"),
    ("dispatch_intent_event_id", ""),
    ("origin", "https://example.test/private"),
])
def test_dispatch_rejects_bypass_shape(field, value):
    dispatch = copy.deepcopy(samples()[2])
    dispatch[field] = value
    with pytest.raises(ValidationError):
        VALIDATOR.validate(dispatch)


@pytest.mark.parametrize("mutator", [
    lambda x: x.update(status="OBSERVED", output_sha256=None),
    lambda x: x.update(status="DENIED", output_sha256=H),
    lambda x: x.update(status="ERROR", output_bytes=1, output_sha256=None),
    lambda x: x.update(status="SUCCESS"),
])
def test_observation_cannot_become_terminal_receipt(mutator):
    observation = copy.deepcopy(samples()[3])
    mutator(observation)
    with pytest.raises(ValidationError):
        VALIDATOR.validate(observation)


@pytest.mark.parametrize("initiator", [
    {"kind": "HUMAN", "actor_ref": "user-1"},
    {"kind": "AGENT", "actor_ref": "registered-agent-1",
     "agent_config_digest": H, "agent_revision": "v1"},
])
def test_versioned_gex_request_accepts_explicit_initiator(initiator):
    request = copy.deepcopy(samples()[4])
    request["initiator"] = initiator
    assert VALIDATOR.is_valid(request), list(VALIDATOR.iter_errors(request))


@pytest.mark.parametrize("initiator", [
    {"kind": "HUMAN", "actor_ref": "user-1", "agent_id": "fake"},
    {"kind": "AGENT", "actor_ref": "agent-1"},
    {"kind": "AGENT", "actor_ref": "agent-1", "agent_config_digest": "unchecked",
     "agent_revision": "v1"},
    {"kind": "SYSTEM", "actor_ref": "admin"},
])
def test_versioned_gex_request_rejects_fake_or_incomplete_initiators(initiator):
    request = copy.deepcopy(samples()[4])
    request["initiator"] = initiator
    with pytest.raises(ValidationError):
        VALIDATOR.validate(request)


def test_versioned_gex_request_cannot_be_bound_to_other_capabilities():
    request = copy.deepcopy(samples()[4])
    request["capability_id"] = "browser.tab.click"
    with pytest.raises(ValidationError):
        VALIDATOR.validate(request)


def reference_state(given: dict) -> dict:
    """Specification oracle ONLY, not a dispatch decision service."""
    prereqs = (
        given["chrome_user_invocation"]
        and given["chrome_grant_current"]
        and given["adl_permit_valid"]
        and given["pairing_valid"]
        and given["context_current"]
        and given["registration_enabled"]
        and given["command_auth_valid"]
        and not given["replay_detected"]
    )
    if not prereqs:
        return {"dispatch": "ZERO", "operation_state": "DENIED",
                "verification_state": "NOT_REQUESTED"}
    if not given["dispatch_intent_persisted"]:
        return {"dispatch": "ZERO", "operation_state": "BLOCKED",
                "verification_state": "NOT_REQUESTED"}
    if not given["terminal_receipt_persisted"]:
        return {"dispatch": "ONE", "operation_state": "RECONCILIATION_REQUIRED",
                "verification_state": "INCONCLUSIVE"}
    if not given["grant_current_at_effect"] or not given["effect_observed"]:
        return {"dispatch": "ONE", "operation_state": "FAILED",
                "verification_state": "VERIFIED_FAILURE"}
    return {"dispatch": "ONE", "operation_state": "SUCCEEDED",
            "verification_state": (
                "VERIFIED_SUCCESS" if given["independently_verified"] else "PENDING"
            )}


def test_all_spec_vectors_match_reference_state_without_claiming_execution():
    assert VECTORS["status"] == "SPEC_ONLY_NOT_EXECUTED"
    ids = [row["id"] for row in VECTORS["vectors"]]
    assert len(ids) == len(set(ids)) >= 20
    for row in VECTORS["vectors"]:
        assert row["classification"] == "SPEC_ONLY"
        assert row["expected"] == reference_state(row["given"]), row["id"]


def test_receipt_loss_is_unknown_even_when_host_acknowledges_and_conformant():
    for row in VECTORS["vectors"]:
        g = row["given"]
        if (g["dispatch_intent_persisted"] and g["terminal_receipt_persisted"] is False
                and row["expected"]["dispatch"] == "ONE"):
            assert row["expected"]["operation_state"] == "RECONCILIATION_REQUIRED"
            assert row["expected"]["verification_state"] == "INCONCLUSIVE"
    assert any(v["name"] == "missing_receipt_with_ack" for v in VECTORS["vectors"])


def test_conformance_and_chrome_grant_never_replace_adl_permission():
    for row in VECTORS["vectors"]:
        g = row["given"]
        if g["conformance_reported"] and not g["adl_permit_valid"]:
            assert row["expected"]["dispatch"] == "ZERO"
    assert not VECTORS["no_ledger_or_activation"] is False


def test_all_thirteen_controls_map_to_distinct_host_required_checks():
    canonical = set(DOMAIN_SCHEMA["$defs"]["control"]["properties"]["id"]["enum"])
    actual = MAP["controls"]
    assert len(actual) == 13
    assert {entry["control_id"] for entry in actual} == canonical
    check_ids = [entry["check_id"] for entry in actual]
    assert len(check_ids) == len(set(check_ids))
    ids = {v["id"] for v in VECTORS["vectors"]}
    for entry in actual:
        assert entry["check_id"].startswith("bb_")
        assert entry["assertion"]
        assert set(entry["vector_ids"]) <= ids
        assert entry["vector_ids"]
    assert MAP["status"] == "PROPOSED_HOST_POLICY_NOT_ACTIVE"
    assert MAP["policy_owner"] == "ADL_TRUSTED_HOST_NOT_DOMAIN_PACKET"


def test_gex_v1_must_remain_unchanged_until_explicit_versioned_extension():
    reg = GEX_SCHEMA["$defs"]["CapabilityRegistrationV1"]["properties"]
    req = GEX_SCHEMA["$defs"]["GEXRequestV1"]
    assert reg["executor_kind"]["enum"] == ["local", "mcp"]
    assert "agent" in req["required"]
    assert "browser_native" not in reg["executor_kind"]["enum"]
    assert "browser_native" in SCHEMA["$defs"]["CapabilityProfile"]["properties"]["executor_kind"]["const"]
