"""Read-only domain conformance adapter over ADL's managed evidence gate.

The canonical ADL manifest contract and its test were reconstructed from the
user-provided requirements on 2026-10-29. The trusted host supplies the
required-control/check mapping; a domain packet cannot choose mandatory
controls or authorize its own activation.
"""
from __future__ import annotations

import hashlib
import importlib.util
import re
from pathlib import Path
from typing import Any, Mapping, Sequence


class DomainConformanceError(ValueError):
    """A domain conformance claim is incomplete, unbound, or unverified."""


_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z")


def _teamctl():
    """Load the canonical repository controller, never workspace code."""
    path = Path(__file__).resolve().parents[2] / ".bago/team/kit/scripts/teamctl.py"
    spec = importlib.util.spec_from_file_location("adl_domain_conformance_teamctl", path)
    if spec is None or spec.loader is None:
        raise DomainConformanceError("canonical ADL teamctl is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


REQUIRED_DOMAIN_CONTROLS = (
    "AUTH-001", "SCOPE-001", "SOURCE-001", "STATE-001", "OPER-001",
    "CAP-001", "EVID-001", "MEM-001", "ROUTE-001", "REL-001",
    "VER-001", "SEM-001", "KERNEL-001",
)


def _ids(values: Any, label: str) -> list[str]:
    if not isinstance(values, (list, tuple)) or not values:
        raise DomainConformanceError(f"{label} must be a non-empty list")
    result = list(values)
    if any(not isinstance(value, str) or not _IDENTIFIER.fullmatch(value) for value in result):
        raise DomainConformanceError(f"{label} contains an invalid identifier")
    if len(set(result)) != len(result):
        raise DomainConformanceError(f"{label} contains duplicate identifiers")
    return result


def verify_domain_conformance(
    evaluation: Mapping[str, Any],
    *,
    workspace_root: str | Path,
    work_id: str,
    required_checks_by_control: Mapping[str, Sequence[str]],
) -> dict[str, Any]:
    """Verify normalized domain control claims against a persisted ADL handoff.

    ``required_checks_by_control`` is host-owned policy. Every listed check must
    also be required by the selected ADL work item, and canonical teamctl must
    revalidate the persisted handoff, managed receipts, outputs and logs.

    This function is read-only: it does not execute checks, mutate the mission,
    authorize an action, persist a result, or activate a domain.
    """
    if not isinstance(evaluation, Mapping):
        raise DomainConformanceError("evaluation must be an object")
    domain_id = evaluation.get("domain_id")
    if not isinstance(domain_id, str) or not _IDENTIFIER.fullmatch(domain_id):
        raise DomainConformanceError("domain_id is required")
    if evaluation.get("declared_result") != "CONFORMANT":
        raise DomainConformanceError("domain did not declare CONFORMANT")
    evaluated_candidate_id = evaluation.get("candidate_id")
    if not isinstance(evaluated_candidate_id, str) or not re.fullmatch(r"[a-f0-9]{64}", evaluated_candidate_id):
        raise DomainConformanceError("candidate_id must be a lowercase SHA-256")
    conflicts = evaluation.get("open_critical_conflicts")
    if not isinstance(conflicts, list) or conflicts:
        raise DomainConformanceError("open critical conflicts must be explicitly empty")

    if not isinstance(required_checks_by_control, Mapping) or not required_checks_by_control:
        raise DomainConformanceError("host policy must define required controls")
    required_controls: dict[str, list[str]] = {}
    for control_id, check_ids in required_checks_by_control.items():
        if not isinstance(control_id, str) or not _IDENTIFIER.fullmatch(control_id):
            raise DomainConformanceError("host policy contains an invalid control id")
        required_controls[control_id] = _ids(check_ids, f"required checks for {control_id}")

    claims = evaluation.get("controls")
    if not isinstance(claims, list):
        raise DomainConformanceError("controls must be a list")
    claims_by_id: dict[str, Mapping[str, Any]] = {}
    for claim in claims:
        if not isinstance(claim, Mapping):
            raise DomainConformanceError("control claim must be an object")
        control_id = claim.get("id")
        if not isinstance(control_id, str) or control_id in claims_by_id:
            raise DomainConformanceError("control id is invalid or duplicated")
        if control_id not in required_controls:
            raise DomainConformanceError(f"control is not in host policy: {control_id}")
        claims_by_id[control_id] = claim
    if set(claims_by_id) != set(required_controls):
        missing = sorted(set(required_controls) - set(claims_by_id))
        raise DomainConformanceError("mandatory controls missing: " + ", ".join(missing))

    team = _teamctl()
    root = team.root_path(workspace_root)
    state = team.load_state(root)
    team._verify(root, state)
    if work_id not in team.work_map(state):
        raise DomainConformanceError("work_id is not registered in the managed mission")
    if state["work_status"][work_id]["status"] != "DONE":
        raise DomainConformanceError("managed work item is not DONE")
    if state["candidate_id"] != evaluated_candidate_id:
        raise DomainConformanceError("evaluation candidate does not match the managed candidate")

    work = team.work_map(state)[work_id]
    mission_checks = set(work.get("required_checks", []))
    mapped_checks = {check_id for values in required_controls.values() for check_id in values}
    if not mapped_checks.issubset(mission_checks):
        raise DomainConformanceError("host policy maps a control to a check not required by the mission")

    handoff = team.validate_handoff(root, state, work_id)
    verified_checks = {
        item["id"] for item in handoff["verification"]
        if item.get("result") == "PASS"
    }
    report_controls = []
    for control_id, check_ids in required_controls.items():
        claim = claims_by_id[control_id]
        if claim.get("result") != "PASS":
            raise DomainConformanceError(f"mandatory control did not PASS: {control_id}")
        evidence_refs = _ids(claim.get("evidence_refs"), f"evidence refs for {control_id}")
        if set(evidence_refs) != set(check_ids):
            raise DomainConformanceError(f"evidence refs do not match host policy: {control_id}")
        missing = set(check_ids) - verified_checks
        if missing:
            raise DomainConformanceError(
                f"required evidence check did not PASS for {control_id}: " + ", ".join(sorted(missing))
            )
        report_controls.append({"id": control_id, "result": "PASS", "verified_checks": sorted(check_ids)})

    handoff_ref = state["work_status"][work_id]["handoff"]
    return {
        "status": "CONFORMANT",
        "contract": "adl.domain-conformance.normalized.v0",
        "domain_id": domain_id,
        "candidate_id": state["candidate_id"],
        "mission_id": state["mission"]["mission_id"],
        "work_id": work_id,
        "handoff_sha256": handoff_ref["sha256"],
        "evidence_basis": "ADL_TEAMCTL_MANAGED_HANDOFF",
        "conclusion_scope": "registered check execution, receipt integrity, and candidate binding; check semantic adequacy remains host-owned",
        "adapter_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "controls": report_controls,
        "persisted": False,
        "authorization_granted": False,
        "activation_performed": False,
    }


def verify_domain_manifest(
    manifest: Mapping[str, Any],
    *,
    workspace_root: str | Path,
    work_id: str,
    required_checks_by_control: Mapping[str, Sequence[str]],
) -> dict[str, Any]:
    """Validate the canonical manifest and verify all 13 mandatory controls.

    Schema validation is structural only. Exact control coverage and evidence
    binding are enforced here and by :func:`verify_domain_conformance`.
    """
    if not isinstance(manifest, Mapping):
        raise DomainConformanceError("manifest must be an object")
    schema_path = Path(__file__).resolve().parents[2] / "docs/domain-conformance/source/05_DOMAIN_MANIFEST.schema.json"
    try:
        import json
        import jsonschema

        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.Draft202012Validator(schema).validate(dict(manifest))
    except FileNotFoundError as exc:
        raise DomainConformanceError("canonical domain manifest schema is unavailable") from exc
    except Exception as exc:
        raise DomainConformanceError(f"manifest schema validation failed: {exc}") from exc

    conformance = manifest["conformance"]
    controls = conformance["controls"]
    control_ids = [control["id"] for control in controls]
    if len(control_ids) != len(set(control_ids)):
        raise DomainConformanceError("mandatory control id is duplicated")
    if set(control_ids) != set(REQUIRED_DOMAIN_CONTROLS):
        missing = sorted(set(REQUIRED_DOMAIN_CONTROLS) - set(control_ids))
        extra = sorted(set(control_ids) - set(REQUIRED_DOMAIN_CONTROLS))
        details = []
        if missing:
            details.append("missing: " + ", ".join(missing))
        if extra:
            details.append("unknown: " + ", ".join(extra))
        raise DomainConformanceError("manifest mandatory controls do not match v1.0 (" + "; ".join(details) + ")")

    normalized = {
        "domain_id": manifest["domain_id"],
        "candidate_id": manifest["candidate_sha256"],
        "declared_result": conformance["result"],
        "open_critical_conflicts": conformance["open_critical_conflicts"],
        "controls": [
            {"id": item["id"], "result": item["result"], "evidence_refs": item["evidence_refs"]}
            for item in controls
        ],
    }
    result = verify_domain_conformance(
        normalized,
        workspace_root=workspace_root,
        work_id=work_id,
        required_checks_by_control=required_checks_by_control,
    )
    result["contract"] = "adl.domain_manifest.v1"
    result["manifest_schema"] = "docs/domain-conformance/source/05_DOMAIN_MANIFEST.schema.json"
    return result


__all__ = ["DomainConformanceError", "REQUIRED_DOMAIN_CONTROLS", "verify_domain_conformance", "verify_domain_manifest"]
