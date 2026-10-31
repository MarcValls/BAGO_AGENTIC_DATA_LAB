"""Read-only integrity checks for the independent nearest-goal review."""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
BASE = Path("docs/verification/nearest-goals-close-20261031")
REVIEW = BASE / "review"
errors: list[str] = []


def emit(payload: dict) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n"
    (ROOT / REVIEW / "review-check.json").write_text(serialized, encoding="utf-8")
    print(serialized, end="")


def read_json(relative: str) -> dict:
    path = ROOT / relative
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # report all integrity problems together
        errors.append(f"json:{relative}:{type(exc).__name__}")
        return {}


def digest(relative: str) -> str:
    path = ROOT / relative
    if not path.is_file():
        return "MISSING"
    return hashlib.sha256(path.read_bytes()).hexdigest()


actual_head = subprocess.run(
    ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, capture_output=True, check=False
)
if actual_head.returncode != 0 or actual_head.stdout.strip() != "b1b4d524a0e936300a71da36e0c0276e061fa34e":
    errors.append("candidate_head_mismatch")

matrix = read_json(str(REVIEW / "goal-matrix.json"))
result = read_json(str(REVIEW / "RESULT.json"))
summary = read_json(str(BASE / "regression" / "SUMMARY.json"))
regression = read_json(".bago/team/runtime/handoffs/REGRESSION.json")
state = read_json(".bago/team/runtime/state.json")
docs_result = read_json(str(BASE / "regression" / "documents-final.json"))
f02 = read_json("frontend/nearest-goals-check/footer-repair/layout-r2/F02-handoff.json")

if matrix.get("candidate_git_head") != actual_head.stdout.strip():
    errors.append("matrix_candidate_mismatch")
if result.get("candidate", {}).get("git_head") != actual_head.stdout.strip():
    errors.append("result_candidate_mismatch")
if result.get("goal_matrix", {}).get("sha256") != digest(str(REVIEW / "goal-matrix.json")):
    errors.append("result_matrix_hash_mismatch")
if summary.get("candidate_head") != actual_head.stdout.strip() or summary.get("status") != "PASS":
    errors.append("final_regression_summary_mismatch")
if state.get("mission", {}).get("mission_id") != "BAGO_NEAREST_OPEN_GOALS_CLOCK_REPAIR_20261031":
    errors.append("mission_identity_mismatch")
if state.get("work_status", {}).get("REVIEW", {}).get("agent") != "brave_e2e_r5":
    errors.append("review_claim_mismatch")
if state.get("work_status", {}).get("REVIEW", {}).get("status") not in {"CLAIMED", "DONE"}:
    errors.append("review_state_invalid")
if regression.get("payload_sha256") != result.get("regression_handoff", {}).get("payload_sha256"):
    errors.append("regression_payload_mismatch")
if state.get("work_status", {}).get("REGRESSION", {}).get("handoff", {}).get("sha256") != digest(".bago/team/runtime/handoffs/REGRESSION.json"):
    errors.append("regression_handoff_file_hash_mismatch")

regression_output_mismatches = []
for output in regression.get("outputs", []):
    if digest(output["path"]) != output["sha256"]:
        regression_output_mismatches.append(output["path"])
if len(regression.get("outputs", [])) != 138 or regression_output_mismatches:
    errors.append(f"regression_outputs:{len(regression.get('outputs', []))}:{len(regression_output_mismatches)}")

goals = matrix.get("goals", {})
eligible = sum(bool(goal.get("eligible_for_closure")) for goal in goals.values())
if len(goals) != 8 or eligible != 7:
    errors.append("goal_counts_mismatch")
if goals.get("square-color-ui-20261020", {}).get("eligible_for_closure") is not False:
    errors.append("square_color_must_remain_partial")
for goal_id, goal in goals.items():
    for evidence in goal.get("evidence", []):
        if digest(evidence["path"]) != evidence["sha256"]:
            errors.append(f"goal_evidence_hash:{goal_id}:{evidence['path']}")

if docs_result.get("status") != "PASS" or len(docs_result.get("checks", [])) != 10:
    errors.append("real_documents_check_mismatch")
if f02.get("status") != "DONE" or f02.get("payload_sha256") != "ffb9e9110647c8fff23caa2ef662f4269ef4eb40847aed25fdc180d59fbd8ada":
    errors.append("F02_handoff_mismatch")
if result.get("overall") != "GO_SCOPED_CLOSE" or result.get("global_product_closure") != "NOT_CLAIMED":
    errors.append("review_scope_mismatch")
if result.get("severity", {}).get("open_p0") != 0 or result.get("severity", {}).get("open_p1") != 0:
    errors.append("open_critical_findings")
for artifact in result.get("artifacts", []):
    if digest(artifact["path"]) != artifact["sha256"]:
        errors.append(f"result_artifact_hash:{artifact['path']}")

if errors:
    emit({"status": "FAIL", "errors": errors})
    raise SystemExit(1)

emit({
    "status": "PASS",
    "candidate_head": actual_head.stdout.strip(),
    "mission_id": state["mission"]["mission_id"],
    "review_claim": state["work_status"]["REVIEW"]["status"],
    "regression_outputs": len(regression["outputs"]),
    "regression_output_hash_mismatches": 0,
    "goal_count": len(goals),
    "eligible_for_scoped_closure": eligible,
    "partial": ["square-color-ui-20261020"],
    "goal_evidence_hash_mismatches": 0,
    "real_document_checks": len(docs_result["checks"]),
    "global_product_closure": "NOT_CLAIMED"
})
