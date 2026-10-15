"""Independent-of-runtime structural checks for the GEX contract candidate.

These tests validate specification consistency, not tool authorization or effects.
They are deliberately unable to declare governed execution AVAILABLE.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]
DOCS = ROOT / "docs" / "governed-execution"


def _read(name: str) -> dict:
    return json.loads((DOCS / name).read_text(encoding="utf-8"))


def test_gex_wire_schema_has_closed_required_objects() -> None:
    schema = _read("GEX_V1_SCHEMA.json")
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    definitions = schema["$defs"]
    assert len(schema["oneOf"]) == 10
    assert len({item["$ref"] for item in schema["oneOf"]}) == 10
    assert {"GEXRequestV1", "PermitV1", "PermitUseStateV1",
            "ToolProposalEnvelopeV1", "ProposalDenialReceiptV1",
            "ApprovalV1", "PolicyDecisionV1", "ReceiptV1",
            "LedgerEventV1", "CapabilityRegistrationV1"} <= set(definitions)
    for name, definition in definitions.items():
        assert definition["type"] == "object", name
        assert definition["additionalProperties"] is False, name
        assert set(definition["required"]) == set(definition["properties"]), name


def test_gex_schema_references_resolve() -> None:
    schema = _read("GEX_V1_SCHEMA.json")
    def walk(node: object) -> None:
        if isinstance(node, dict):
            if "$ref" in node:
                prefix = "#/$defs/"
                assert node["$ref"].startswith(prefix)
                assert node["$ref"][len(prefix):] in schema["$defs"]
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)
    walk(schema)


def test_gex_request_digest_covers_full_authority_context() -> None:
    fields = _read("GEX_V1_SCHEMA.json")["$defs"]["GEXRequestV1"]["properties"]
    assert set(fields) >= {
        "contract_version", "request_id", "run_id", "proposal_id", "principal",
        "agent", "workspace", "capability", "operation", "constraints", "policy",
        "context_revision", "proposed_at", "expires_at", "nonce",
    }
    definitions = _read("GEX_V1_SCHEMA.json")["$defs"]
    assert {"arguments", "target", "effect_scope"} <= set(definitions["Operation"]["properties"])
    assert {"issuer", "subject", "session_binding", "auth_strength"} <= set(definitions["Principal"]["properties"])
    assert {"binding_fingerprint", "repository_identity", "context_revision"} <= set(definitions["Workspace"]["properties"])
    assert {"id", "version", "registry_digest", "schema_digest", "effect"} <= set(definitions["Capability"]["properties"])
    normative = (DOCS / "GEX_V1_NORMATIVE_CONTRACT.md").read_text(encoding="utf-8")
    assert "RFC 8785" in normative and "SHA-256" in normative
    assert "to_hash" in normative and "prohibido" in normative.casefold()


def test_gex_signed_claims_and_durable_use_state_are_distinct() -> None:
    d = _read("GEX_V1_SCHEMA.json")["$defs"]
    assert "status" not in d["PermitV1"]["properties"]
    assert {"contract_version", "signature", "signature_algorithm", "key_id",
            "request_digest", "max_uses"} <= set(d["PermitV1"]["properties"])
    assert d["PermitV1"]["properties"]["max_uses"]["const"] == 1
    assert {"state", "uses", "db_version", "attempt_id"} <= set(d["PermitUseStateV1"]["properties"])
    assert "signature" not in d["PermitUseStateV1"]["properties"]
    assert {"signature", "signature_algorithm", "request_digest", "actor"} <= set(d["ApprovalV1"]["properties"])


def test_gex_approval_and_permit_signature_fixtures_verify() -> None:
    schema = _read("GEX_V1_SCHEMA.json")
    spec = _read("GEX_V1_CONFORMANCE_VECTORS.json")
    expected_domains = {
        "ApprovalV1": "ADL:GEX:APPROVAL:v1\n",
        "PermitV1": "ADL:GEX:PERMIT:v1\n",
    }
    expected_encodings = {
        "HMAC-SHA256": "^[0-9a-f]{64}$",
        "Ed25519": "^[A-Za-z0-9_-]{86}$",
    }
    for contract_type in expected_domains:
        branches = schema["$defs"][contract_type]["allOf"]
        encodings = {
            branch["if"]["properties"]["signature_algorithm"]["const"]:
            branch["then"]["properties"]["signature"]["pattern"]
            for branch in branches
        }
        assert encodings == expected_encodings
    assert {fixture["contract_type"] for fixture in spec["signature_verification_fixtures"]} == set(expected_domains)
    for fixture in spec["signature_verification_fixtures"]:
        contract_type = fixture["contract_type"]
        signed_object = fixture["signed_object"]
        assert fixture["domain_separator"] == expected_domains[contract_type]
        assert signed_object["signature_algorithm"] == "HMAC-SHA256"
        assert signed_object["signature"] == hmac.new(
            bytes.fromhex(fixture["key_hex"]),
            fixture["domain_separator"].encode()
            + json.dumps(
                {key: value for key, value in signed_object.items() if key != "signature"},
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode(),
            hashlib.sha256,
        ).hexdigest()
        assert set(signed_object) == set(
            schema["$defs"][contract_type]["required"]
        )
        if contract_type == "PermitV1":
            assert {"issuer", "key_id", "signature_algorithm"} <= set(signed_object)


def test_gex_predispatch_denial_does_not_fabricate_request() -> None:
    d = _read("GEX_V1_SCHEMA.json")["$defs"]
    assert "proposal_digest" in d["ProposalDenialReceiptV1"]["properties"]
    assert "request_digest" not in d["ProposalDenialReceiptV1"]["properties"]
    assert "raw_arguments_sha256" in d["ToolProposalEnvelopeV1"]["properties"]


def test_gex_state_machine_guards_are_explicit_and_closed() -> None:
    sm = _read("GEX_V1_STATE_MACHINE.json")
    assert sm["initial"] == "PROPOSED"
    states, terminal = set(sm["states"]), set(sm["terminal"])
    assert {"DENIED", "REJECTED", "RECONCILIATION_REQUIRED", "SUCCEEDED"} <= terminal
    arcs = {(t["from"], t["to"]) for t in sm["transitions"]}
    assert len(arcs) == len(sm["transitions"])
    for t in sm["transitions"]:
        assert t["from"] in states and t["to"] in states
        assert t["from"] not in terminal
        assert t["required_events"]
        assert t["guard"] != ""
    assert ("PROPOSED", "APPROVED") in arcs
    assert ("PROPOSED", "RUNNING") not in arcs
    assert ("AWAITING_APPROVAL", "RUNNING") not in arcs
    assert ("APPROVED", "SUCCEEDED") not in arcs
    assert ("RUNNING", "SUCCEEDED") in arcs
    assert ("RUNNING", "RECONCILIATION_REQUIRED") in arcs
    assert not any(t["to"] == "SUCCEEDED" and
                   "RECEIPT_PERSISTED" not in t["required_events"]
                   for t in sm["transitions"])


def test_gex_events_cover_state_machine() -> None:
    sm = _read("GEX_V1_STATE_MACHINE.json")
    schema = _read("GEX_V1_SCHEMA.json")
    allowed = set(schema["$defs"]["LedgerEventV1"]["properties"]["kind"]["enum"])
    assert all(set(t["required_events"]) <= allowed for t in sm["transitions"])
    ledger = schema["$defs"]["LedgerEventV1"]["properties"]
    assert {"request_digest", "proposal_digest", "prev_hash", "event_digest",
            "attempt_id", "permit_id"} <= set(ledger)


def test_gex_40_vectors_are_spec_only_and_have_unique_ids() -> None:
    spec = _read("GEX_V1_CONFORMANCE_VECTORS.json")
    cases = spec["vectors"]
    assert len(cases) == 40
    assert len({c["id"] for c in cases}) == len(cases)
    assert {f"GEX-{i:03}" for i in range(1, 41)} == {c["id"] for c in cases}
    assert spec["status"] == "SPEC_ONLY_NOT_EXECUTED"
    for case in cases:
        assert case["execution_status"] == "SPEC_ONLY"
        assert case["invariant"] and case["scenario"]
        assert case["expected"]["receipt"]
        assert isinstance(case["expected"]["max_effect_dispatches"], int)
    areas = {c["area"] for c in cases}
    assert {"identity", "registry", "canonical", "authorization", "approval",
            "permit", "consumption", "recovery", "receipt", "scope",
            "evidence", "positive"} <= areas


@pytest.mark.parametrize("name", ["GEX_V1_NORMATIVE_CONTRACT.md", "CR_GEX_002_005_RESOLUTIONS.md"])
def test_gex_unavailable_profiles_are_explicit(name: str) -> None:
    text = (DOCS / name).read_text(encoding="utf-8")
    assert "UNAVAILABLE" in text and "FAIL_CLOSED" in text


def test_gex_legacy_agent_run_remains_closed() -> None:
    server = (ROOT / "src" / "api" / "server.py").read_text(encoding="utf-8")
    ws = server.split('@app.websocket("/ws/agents/run")', 1)[1]
    agent_runner = ws.split("# ===== WebSocket: Agent Chat", 1)[0]
    assert "execution_unavailable" in agent_runner
    assert "1008" in agent_runner
    assert "gateway.execute" not in agent_runner

def test_gex_draft202012_schema_is_valid_and_rejects_incomplete_inputs() -> None:
    # This validates structure, not authorization, canonicalization or signatures.
    from jsonschema import Draft202012Validator, ValidationError

    schema = _read("GEX_V1_SCHEMA.json")
    Draft202012Validator.check_schema(schema)
    digest = "a" * 64
    request = {
        "contract_version": "gex-request/v1",
        "request_id": "123e4567-e89b-42d3-a456-426614174000",
        "run_id": "run-1",
        "proposal_id": "proposal-1",
        "principal": {"issuer": "host", "subject": "uid-1",
                      "session_binding": digest, "auth_strength": "verified"},
        "agent": {"agent_id": "agent-1", "config_digest": digest, "revision": "1"},
        "workspace": {"workspace_id": "workspace-1", "binding_fingerprint": digest,
                      "repository_identity": "example/repo", "branch": "main",
                      "commit_sha": "a" * 40, "context_revision": "1",
                      "root_identity": "backend-owned"},
        "capability": {"id": "filesystem.read", "version": "1",
                       "registry_digest": digest, "schema_digest": digest,
                       "executor_kind": "local", "effect": "READ"},
        "operation": {"arguments": {"path": "fixture.txt"},
                      "target": "workspace-relative", "effect_scope": "read-one-file"},
        "constraints": {"sandbox_profile": "read_only_agent", "network": "deny",
                        "timeout_ms": 2000, "max_output_bytes": 65536,
                        "write_scope": "none", "egress_allowlist": []},
        "policy": {"revision": "1", "policy_digest": digest},
        "context_revision": "1", "proposed_at": "2026-10-15T10:00:00Z",
        "expires_at": "2026-10-15T10:02:00Z", "nonce": "random-1"
    }
    Draft202012Validator(schema).validate(request)

    tampered = json.loads(json.dumps(request))
    tampered["principal"].pop("session_binding")
    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(tampered)
    unregistered_schema = json.loads(json.dumps(request))
    unregistered_schema["operation"]["unexpected"] = "ignored?"
    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(unregistered_schema)
    forged = json.loads(json.dumps(request))
    forged["principal"]["auth_strength"] = "unverified"
    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(forged)


def test_gex_schema_does_not_mistake_mutable_state_for_signature() -> None:
    from jsonschema import Draft202012Validator, ValidationError
    schema = _read("GEX_V1_SCHEMA.json")
    digest = "b" * 64
    approval = {
        "contract_version": "gex-approval/v1", "approval_id": "approval-1",
        "request_digest": digest, "actor": "person-1", "principal_subject": "person-1",
        "workspace_binding_fingerprint": digest, "operation_summary_digest": digest,
        "decision": "APPROVED", "issued_at": "2026-10-15T10:00:00Z",
        "expires_at": "2026-10-15T10:02:00Z", "auth_context_ref": "context-1",
        "evidence_ref": "evidence-1", "key_id": "kid1", "signature": "bytes-base64",
        "signature_algorithm": "HMAC-SHA256"
    }
    Draft202012Validator(schema).validate(approval)
    approval["signature_algorithm"] = "none"
    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(approval)
