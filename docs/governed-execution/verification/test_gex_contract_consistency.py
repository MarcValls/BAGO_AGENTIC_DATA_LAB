"""Independent-of-runtime structural checks for the GEX contract candidate.

These tests validate specification consistency, not tool authorization or effects.
They are deliberately unable to declare governed execution AVAILABLE.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import struct
import subprocess
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
    assert len(schema["oneOf"]) == 12
    assert len({item["$ref"] for item in schema["oneOf"]}) == 12
    assert {"GEXRequestV1", "PermitV1", "PermitUseStateV1",
            "ToolProposalEnvelopeV1", "ProposalDenialReceiptV1", "IngressDenialReceiptV1",
            "ApprovalV1", "PolicyDecisionV1", "ReceiptV1",
            "LedgerEventV1", "CapabilityRegistrationV1", "VerificationResultV1"} <= set(definitions)
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
            "request_digest", "max_uses", "authorization_source"} <= set(d["PermitV1"]["properties"])
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
    for contract_type in expected_domains:
        assert schema["$defs"][contract_type]["properties"]["signature_algorithm"] == {"const": "Ed25519"}
    assert {fixture["contract_type"] for fixture in spec["signature_verification_fixtures"]} == set(expected_domains)
    for fixture in spec["signature_verification_fixtures"]:
        contract_type = fixture["contract_type"]
        signed_object = fixture["signed_object"]
        assert fixture["profile"] == "TEST_ONLY_HMAC"
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


def test_gex_jcs_golden_vectors_match_rfc8785_reference_bytes_and_digests() -> None:
    spec = _read("GEX_V1_CONFORMANCE_VECTORS.json")
    appendix_b = next(item for item in spec["jcs_golden_vectors"] if item["id"] == "JCS-RFC8785-APPENDIX-B-NUMBERS")
    assert len(appendix_b["numbers"]) == 24
    reference = DOCS / "verification" / "jcs_reference.mjs"
    generated = json.loads(subprocess.check_output(
        ["node", str(reference), str(DOCS / "GEX_V1_CONFORMANCE_VECTORS.json")],
        cwd=ROOT, text=True, encoding="utf-8"
    ))
    by_id = {item["id"]: item["canonical_text"] for item in generated}
    for vector in spec["jcs_golden_vectors"]:
        if "input" in vector:
            text = by_id[vector["id"]]
            encoded = text.encode("utf-8")
            assert text == vector["canonical_text"]
            assert encoded.hex() == vector["canonical_utf8_hex"]
            assert hashlib.sha256(encoded).hexdigest() == vector["sha256"]
            if vector["id"] == "JCS-RFC8785-UTF16-PROPERTY-ORDER":
                assert list(json.loads(text).values()) == vector["expected_value_order"]
        for number in vector.get("numbers", []):
            assert struct.pack(">d", number["value"]).hex() == number["ieee754_hex"]
            text = by_id[f"{vector['id']}:{number['ieee754_hex']}"]
            encoded = text.encode("utf-8")
            assert text == number["canonical"]
            assert encoded.hex() == number["canonical_utf8_hex"]
            assert hashlib.sha256(encoded).hexdigest() == number["sha256"]
    invalid_input_check = (
        "import('./docs/governed-execution/verification/jcs_reference.mjs').then(({canonicalize})=>{"
        "for(const x of [NaN,Infinity,'\\ud800']){let failed=false;try{canonicalize(x)}catch{failed=true}"
        "if(!failed)process.exitCode=1}});"
    )
    subprocess.run(["node", "--input-type=module", "-e", invalid_input_check], cwd=ROOT, check=True)


def test_gex_verification_is_a_separate_receipt_bound_result() -> None:
    from jsonschema import Draft202012Validator, ValidationError
    schema = _read("GEX_V1_SCHEMA.json")
    result = schema["$defs"]["VerificationResultV1"]
    assert {"receipt_id", "receipt_digest", "request_digest", "attempt_id",
            "verifier_id", "verifier_version", "outcome", "postcondition_digest"} <= set(result["required"])
    assert result["properties"]["outcome"]["enum"] == ["VERIFIED_SUCCESS", "VERIFIED_FAILURE", "INCONCLUSIVE"]
    machine = _read("GEX_V1_STATE_MACHINE.json")
    assert "SUCCEEDED" in machine["terminal"]
    assert "VERIFIED_SUCCESS" not in machine["states"]
    assert "VERIFIED_SUCCESS" in machine["verification_states"]
    assert {"NOT_REQUESTED", "PENDING", "VERIFIED_SUCCESS", "VERIFIED_FAILURE", "INCONCLUSIVE"} == set(machine["verification_states"])
    kinds = set(schema["$defs"]["LedgerEventV1"]["properties"]["kind"]["enum"])
    assert "VERIFICATION_RESULT_PERSISTED" in kinds
    assert "verification_result_id" in schema["$defs"]["LedgerEventV1"]["required"]
    vectors = {item["id"]: item for item in _read("GEX_V1_CONFORMANCE_VECTORS.json")["vectors"]}
    assert vectors["GEX-036"]["expected"]["execution_state"] == "SUCCEEDED"
    assert vectors["GEX-036"]["expected"]["verification_state"] == "PENDING"
    assert vectors["GEX-039"]["expected"]["state"] == "RECONCILIATION_REQUIRED"
    assert "MISSING_NOT_EVIDENCE_OF_NO_EFFECT" == vectors["GEX-039"]["expected"]["receipt"]
    valid_result = {
        "contract_version": "gex-verification-result/v1", "verification_id": "verification-1",
        "receipt_id": "receipt-1", "receipt_digest": "a" * 64, "request_digest": "b" * 64,
        "attempt_id": "attempt-1", "verifier_id": "independent-verifier-1",
        "verifier_version": "1", "outcome": "VERIFIED_SUCCESS", "postcondition_digest": "c" * 64,
        "evidence_refs": ["fixture-observation-1"], "reason_code": "POSTCONDITION_MATCHED",
        "verified_at": "2026-10-18T00:00:00Z"
    }
    Draft202012Validator(schema).validate(valid_result)
    invalid_result = dict(valid_result, attempt_id="")
    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(invalid_result)
    for invalid_success in (
        dict(valid_result, postcondition_digest=None),
        dict(valid_result, evidence_refs=[]),
    ):
        with pytest.raises(ValidationError):
            Draft202012Validator(schema).validate(invalid_success)

    event_schema = schema["$defs"]["LedgerEventV1"]
    valid_event = {
        "contract_version": "gex-ledger-event/v1", "event_id": "event-1",
        "request_id": "request-1", "run_id": "run-1", "seq": 1,
        "prev_hash": "d" * 64, "event_digest": "e" * 64,
        "kind": "VERIFICATION_RESULT_PERSISTED", "timestamp": "2026-10-18T00:00:00Z",
        "payload_ref": "verification/verification-1", "proposal_id": "proposal-1",
        "proposal_digest": "f" * 64, "request_digest": "b" * 64,
        "attempt_id": "attempt-1", "permit_id": "permit-1", "sandbox_receipt_id": None,
        "decision_id": "decision-1", "approval_id": None, "job_id": "job-1",
        "boundary_receipt_id": "receipt-1", "verification_result_id": "verification-1",
    }
    Draft202012Validator(event_schema).validate(valid_event)
    for invalid_event in (
        dict(valid_event, verification_result_id=None),
        dict(valid_event, request_digest=None),
        dict(valid_event, attempt_id=None),
        dict(valid_event, boundary_receipt_id=None),
    ):
        with pytest.raises(ValidationError):
            Draft202012Validator(event_schema).validate(invalid_event)


def test_gex_crypto_negative_vectors_are_fail_closed_and_test_hmac_is_not_production() -> None:
    spec = _read("GEX_V1_CONFORMANCE_VECTORS.json")
    assert {item["id"] for item in spec["verification_vectors"]} >= {
        "GEX-VFY-001", "GEX-VFY-002", "GEX-VFY-003", "GEX-VFY-004",
        "GEX-VFY-005", "GEX-VFY-006", "GEX-VFY-007", "GEX-VFY-008",
        "GEX-VFY-009", "GEX-VFY-010", "GEX-VFY-011"
    }
    assert all(item["expected"] in {"DENY", "INCONCLUSIVE", "SCHEMA_REJECT"} for item in spec["verification_vectors"])
    permit = _read("GEX_V1_SCHEMA.json")["$defs"]["PermitV1"]["properties"]["signature_algorithm"]
    assert permit == {"const": "Ed25519"}
    assert all(fixture["profile"] == "TEST_ONLY_HMAC" for fixture in spec["signature_verification_fixtures"])
    fixture = spec["ed25519_test_fixture"]
    assert fixture["profile"].startswith("TEST_ONLY_")
    assert "private" not in fixture
    script = (
        "const c=require('node:crypto');"
        "const [pubHex,msgHex,sigText]=process.argv.slice(1);"
        "const key=c.createPublicKey({key:Buffer.from(pubHex,'hex'),format:'der',type:'spki'});"
        "const ok=c.verify(null,Buffer.from(msgHex,'hex'),key,Buffer.from(sigText,'base64url'));"
        "process.stdout.write(ok?'true':'false');"
    )
    def verify(public_key: str, message: str, signature: str) -> str:
        return subprocess.check_output(
            ["node", "-e", script, public_key, message, signature],
            cwd=ROOT, text=True, encoding="utf-8"
        )
    assert verify(fixture["public_key_spki_der_hex"], fixture["message_hex"], fixture["signature_base64url"]) == "true"
    assert verify(fixture["wrong_public_key_spki_der_hex"], fixture["message_hex"], fixture["signature_base64url"]) == "false"
    tampered = fixture["message_hex"][:-2] + ("00" if fixture["message_hex"][-2:] != "00" else "01")
    assert verify(fixture["public_key_spki_der_hex"], tampered, fixture["signature_base64url"]) == "false"


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
    assert sm["receipt_absence_semantics"].startswith("Without a persisted terminal receipt")
    assert sm["verification_transitions"]


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
        "decision_id": "decision-1",
        "request_digest": digest, "actor": "person-1", "principal_subject": "person-1",
        "workspace_binding_fingerprint": digest, "operation_summary_digest": digest,
        "decision": "APPROVED", "issued_at": "2026-10-15T10:00:00Z",
        "expires_at": "2026-10-15T10:02:00Z", "auth_context_ref": "context-1",
        "evidence_ref": "evidence-1", "key_id": "kid1", "signature": "A" * 86,
        "signature_algorithm": "Ed25519"
    }
    Draft202012Validator(schema).validate(approval)
    approval["signature_algorithm"] = "HMAC-SHA256"
    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(approval)

def test_gex_ingress_denial_has_no_fictitious_principal() -> None:
    definitions = _read("GEX_V1_SCHEMA.json")["$defs"]
    ingress = definitions["IngressDenialReceiptV1"]["properties"]
    assert {"ingress_id", "raw_request_sha256", "prev_ingress_hash",
            "ingress_event_digest", "reason_code"} <= set(ingress)
    assert not {"request_id", "proposal_digest", "principal_subject",
                "workspace_binding_fingerprint"} & set(ingress)


def test_gex_preconsumption_rechecks_and_approver_separation() -> None:
    states = _read("GEX_V1_STATE_MACHINE.json")["transitions"]
    arcs = {(edge["from"], edge["to"]) for edge in states}
    assert {("QUEUED", "DENIED"), ("CLAIMED", "DENIED"),
            ("CLAIMED", "EXPIRED"), ("CLAIMED", "RECONCILIATION_REQUIRED")} <= arcs
    vectors = {v["id"]: v for v in _read("GEX_V1_CONFORMANCE_VECTORS.json")["vectors"]}
    assert "not necessarily requesting principal" in vectors["GEX-019"]["invariant"]
    assert vectors["GEX-004"]["expected"]["receipt"] == "INGRESS_DENIAL_RECEIPT"


def test_gex_v1_vectors_never_dispatch_or_succeed_for_mutating_effects() -> None:
    spec = _read("GEX_V1_CONFORMANCE_VECTORS.json")
    mutating = re.compile(r"\b(?:write\w*|create\w*|delete\w*|mutat\w*)\b", re.IGNORECASE)
    for case in spec["vectors"]:
        expected = case["expected"]
        searchable = " ".join(str(case.get(key, "")) for key in ("effect", "invariant", "scenario"))
        if not mutating.search(searchable):
            continue
        assert expected["max_effect_dispatches"] == 0, case["id"]
        assert expected.get("availability", "UNAVAILABLE") == "UNAVAILABLE", case["id"]
        assert expected["decision"] not in {"ALLOW", "EXECUTE", "EXECUTOR_SUCCESS_UNVERIFIED"}, case["id"]
        assert expected["receipt"] != "SUCCESS", case["id"]
        assert expected["state"] != "SUCCEEDED", case["id"]
    vectors = {case["id"]: case for case in spec["vectors"]}
    for vector_id in ("GEX-029", "GEX-037"):
        expected = vectors[vector_id]["expected"]
        assert vectors[vector_id]["effect"] in {"CREATE", "WRITE"}
        assert expected["availability"] == "UNAVAILABLE"
        assert expected["decision"] == "DENY"
        assert expected["max_effect_dispatches"] == 0
