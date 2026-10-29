"""Focused F-003 checks over ADL's real managed-execution evidence owner."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from src.contracts.domain_conformance import (
    DomainConformanceError,
    REQUIRED_DOMAIN_CONTROLS,
    verify_domain_conformance,
    verify_domain_manifest,
)


ROOT = Path(__file__).resolve().parents[3]
HARNESS_PATH = ROOT / "tests" / "test_teamctl_integrity.py"
_spec = importlib.util.spec_from_file_location("adl_teamctl_integrity_harness", HARNESS_PATH)
_harness_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_harness_module)


@pytest.fixture(scope="module")
def managed_work(tmp_path_factory):
    harness = _harness_module.Harness(ROOT, tmp_path_factory.mktemp("f003") / "artifacts")
    workspace = harness.setup("domain_conformance")
    execution = harness.run_check(workspace)
    handoff = harness.draft(workspace, execution)
    harness.handoff(workspace, handoff)
    state = harness.state(workspace)
    yield {
        "harness": harness,
        "workspace": workspace,
        "state": state,
        "candidate_id": state["candidate_id"],
    }


def evaluation(candidate_id, *, controls=None, result="CONFORMANT", conflicts=None):
    if controls is None:
        controls = [{"id": "scope", "result": "PASS", "evidence_refs": ["acceptance"]}]
    return {
        "domain_id": "fixture.domain",
        "candidate_id": candidate_id,
        "declared_result": result,
        "open_critical_conflicts": [] if conflicts is None else conflicts,
        "controls": controls,
    }


POLICY = {"scope": ["acceptance"]}
MANIFEST_POLICY = {control_id: ["acceptance"] for control_id in REQUIRED_DOMAIN_CONTROLS}


def verify(work, packet=None, policy=POLICY):
    return verify_domain_conformance(
        packet or evaluation(work["candidate_id"]),
        workspace_root=work["workspace"],
        work_id="P",
        required_checks_by_control=policy,
    )


def domain_manifest(candidate_id, *, controls=None, result="CONFORMANT", conflicts=None):
    if controls is None:
        controls = [
            {"id": control_id, "result": "PASS", "evidence_refs": ["acceptance"]}
            for control_id in REQUIRED_DOMAIN_CONTROLS
        ]
    return {
        "contract": "adl.domain_manifest.v1",
        "domain_id": "fixture.domain",
        "version": "1.0.0",
        "candidate_sha256": candidate_id,
        "supersedes": None,
        "scope": {"in_scope": ["synthetic fixture"], "out_of_scope": ["production activation"]},
        "sources": [],
        "operations": [],
        "capabilities": [],
        "interfaces": [],
        "relations": [],
        "conformance": {
            "result": result,
            "open_critical_conflicts": [] if conflicts is None else conflicts,
            "controls": controls,
        },
    }


def verify_manifest(work, packet=None):
    return verify_domain_manifest(
        packet or domain_manifest(work["candidate_id"]),
        workspace_root=work["workspace"],
        work_id="P",
        required_checks_by_control=MANIFEST_POLICY,
    )


def test_all_host_required_controls_with_managed_candidate_bound_receipt_conform(managed_work):
    result = verify(managed_work)
    assert result["status"] == "CONFORMANT"
    assert result["candidate_id"] == managed_work["candidate_id"]
    assert result["evidence_basis"] == "ADL_TEAMCTL_MANAGED_HANDOFF"
    assert result["controls"] == [{"id": "scope", "result": "PASS", "verified_checks": ["acceptance"]}]
    assert result["persisted"] is False
    assert result["authorization_granted"] is False
    assert result["activation_performed"] is False


def test_self_declared_conformant_with_empty_controls_is_rejected(managed_work):
    with pytest.raises(DomainConformanceError, match="mandatory controls missing"):
        verify(managed_work, evaluation(managed_work["candidate_id"], controls=[]))


@pytest.mark.parametrize("control_result", ["FAIL", "BLOCKED", "N/A", "NOT_RUN", "UNKNOWN"])
def test_non_pass_mandatory_control_never_conforms(managed_work, control_result):
    packet = evaluation(managed_work["candidate_id"], controls=[
        {"id": "scope", "result": control_result, "evidence_refs": ["acceptance"]}
    ])
    with pytest.raises(DomainConformanceError, match="did not PASS"):
        verify(managed_work, packet)


def test_missing_evidence_reference_is_rejected(managed_work):
    packet = evaluation(managed_work["candidate_id"], controls=[{"id": "scope", "result": "PASS"}])
    with pytest.raises(DomainConformanceError, match="evidence refs"):
        verify(managed_work, packet)


def test_untrusted_evidence_reference_cannot_replace_host_mapped_check(managed_work):
    packet = evaluation(managed_work["candidate_id"], controls=[
        {"id": "scope", "result": "PASS", "evidence_refs": ["producer-assertion"]}
    ])
    with pytest.raises(DomainConformanceError, match="do not match host policy"):
        verify(managed_work, packet)


def test_candidate_mismatch_is_rejected(managed_work):
    packet = evaluation("0" * 64)
    with pytest.raises(ValueError, match="candidate identity changed|evaluation candidate does not match"):
        verify(managed_work, packet)


def test_open_critical_conflict_blocks_claim(managed_work):
    packet = evaluation(managed_work["candidate_id"], conflicts=[{"id": "conflict-1"}])
    with pytest.raises(DomainConformanceError, match="conflicts"):
        verify(managed_work, packet)


def test_empty_host_policy_is_rejected(managed_work):
    with pytest.raises(DomainConformanceError, match="host policy must define"):
        verify(managed_work, policy={})


def test_host_policy_cannot_map_control_to_non_required_check(managed_work):
    packet = evaluation(managed_work["candidate_id"], controls=[
        {"id": "scope", "result": "PASS", "evidence_refs": ["invented"]}
    ])
    with pytest.raises(DomainConformanceError, match="not required by the mission"):
        verify(managed_work, packet, {"scope": ["invented"]})


def test_canonical_manifest_schema_is_valid_and_requires_controls_for_conformant():
    import jsonschema

    schema = json.loads((ROOT / "docs/domain-conformance/source/05_DOMAIN_MANIFEST.schema.json").read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    invalid = domain_manifest("a" * 64, controls=[])
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(schema).validate(invalid)


def test_canonical_manifest_with_all_managed_controls_conforms(managed_work):
    result = verify_manifest(managed_work)
    assert result["status"] == "CONFORMANT"
    assert result["contract"] == "adl.domain_manifest.v1"
    assert {item["id"] for item in result["controls"]} == set(REQUIRED_DOMAIN_CONTROLS)
    assert all(item["verified_checks"] == ["acceptance"] for item in result["controls"])
    assert result["activation_performed"] is False


def test_canonical_manifest_missing_mandatory_control_is_rejected(managed_work):
    controls = [
        {"id": control_id, "result": "PASS", "evidence_refs": ["acceptance"]}
        for control_id in REQUIRED_DOMAIN_CONTROLS[:-1]
    ]
    with pytest.raises(DomainConformanceError, match="schema validation failed"):
        verify_manifest(managed_work, domain_manifest(managed_work["candidate_id"], controls=controls))


def test_canonical_manifest_duplicate_control_is_rejected(managed_work):
    controls = [
        {"id": control_id, "result": "PASS", "evidence_refs": ["acceptance"]}
        for control_id in REQUIRED_DOMAIN_CONTROLS
    ]
    controls[-1] = dict(controls[0])
    with pytest.raises(DomainConformanceError, match="duplicated"):
        verify_manifest(managed_work, domain_manifest(managed_work["candidate_id"], controls=controls))


def test_canonical_manifest_non_pass_control_is_rejected(managed_work):
    controls = [
        {"id": control_id, "result": "PASS", "evidence_refs": ["acceptance"]}
        for control_id in REQUIRED_DOMAIN_CONTROLS
    ]
    controls[0]["result"] = "BLOCKED"
    with pytest.raises(DomainConformanceError, match="schema validation failed"):
        verify_manifest(managed_work, domain_manifest(managed_work["candidate_id"], controls=controls))


def test_canonical_manifest_cannot_claim_unbound_evidence(managed_work):
    controls = [
        {"id": control_id, "result": "PASS", "evidence_refs": ["acceptance"]}
        for control_id in REQUIRED_DOMAIN_CONTROLS
    ]
    controls[0]["evidence_refs"] = ["producer-only-claim"]
    with pytest.raises(DomainConformanceError, match="do not match host policy"):
        verify_manifest(managed_work, domain_manifest(managed_work["candidate_id"], controls=controls))


def test_canonical_manifest_candidate_mismatch_is_rejected(managed_work):
    with pytest.raises(DomainConformanceError, match="candidate does not match"):
        verify_manifest(managed_work, domain_manifest("0" * 64))


def test_canonical_manifest_open_critical_conflict_is_rejected(managed_work):
    with pytest.raises(DomainConformanceError, match="schema validation failed"):
        verify_manifest(managed_work, domain_manifest(managed_work["candidate_id"], conflicts=["critical-1"]))


def test_tampered_managed_receipt_blocks_conformance(managed_work):
    state = managed_work["state"]
    execution = next(iter(state["executions"].values()))
    receipt_path = managed_work["workspace"] / execution["path"]
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["returncode"] = 1
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    with pytest.raises(ValueError, match="managed execution receipt changed"):
        verify(managed_work)
