#!/usr/bin/env python3
"""Read-only, six-criterion acceptance observer for the frozen BAGO5 audit."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

FILES = ("REQUIREMENTS.md", "mission_snapshot.json", "goal_status.json", "PROVENANCE.json", "pyproject.toml")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def git_show(repo: Path, ref: str, rel: str) -> bytes:
    p = subprocess.run(["git", "-C", str(repo), "show", f"{ref}:{rel}"], capture_output=True, check=False)
    if p.returncode:
        raise RuntimeError(f"git_show_failed:{ref}:{rel}:{p.stderr.decode('utf-8', 'replace')[:500]}")
    return p.stdout


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", type=Path, required=True)
    ap.add_argument("--suite", type=Path, required=True)
    a = ap.parse_args()
    project, suite = a.project.resolve(), a.suite.resolve()
    observations = []
    project_files = {}
    try:
        for name in FILES:
            p = project / name
            project_files[name] = sha(p) if p.is_file() and not p.is_symlink() else None

        prov = load(project / "PROVENANCE.json")
        repo = Path(prov["repository"]).resolve()
        goal_src = repo / prov["sources"]["goal_status.json"]["path"]
        goal_copy = project / "goal_status.json"
        snapshot_prov = prov["sources"]["mission_snapshot.json"]
        snapshot_copy = project / "mission_snapshot.json"
        source_ok = (goal_src.is_file() and sha(goal_src) == sha(goal_copy)
                     and sha(goal_src) == prov["sources"]["goal_status.json"]["sha256"]
                     and hashlib.sha256(git_show(repo, snapshot_prov["git_ref"], snapshot_prov["path"])).hexdigest()
                     == snapshot_prov["sha256"]
                     and sha(snapshot_copy) == snapshot_prov["sha256"])
        observations.append({"id": "source_provenance", "status": "PASS" if source_ok else "FAIL",
                             "evidence": {"goal_status_source": str(goal_src), "goal_status_sha256": sha(goal_copy),
                                          "snapshot_git_ref": snapshot_prov["git_ref"],
                                          "snapshot_git_path": snapshot_prov["path"],
                                          "snapshot_sha256": sha(snapshot_copy)}})

        snap = load(snapshot_copy)
        base = Path(prov["repository"]).resolve()
        runtime_id, cleanup_id = snap["brave_runtime"]["runtime_execution_id"], snap["brave_runtime"]["cleanup_execution_id"]
        runtime_receipt = base / ".bago/team/runtime/executions" / runtime_id / "receipt.json"
        cleanup_receipt = base / ".bago/team/runtime/executions" / cleanup_id / "receipt.json"
        runtime_sha = sha(runtime_receipt) if runtime_receipt.is_file() else None
        cleanup_sha = sha(cleanup_receipt) if cleanup_receipt.is_file() else None
        rrec, crec = load(runtime_receipt), load(cleanup_receipt)
        expected_ids = (runtime_id == rrec.get("execution_id") and cleanup_id == crec.get("execution_id")
                        and rrec.get("work_id") == crec.get("work_id") == "BRAVE_E2E_R5")
        expected_hashes = (runtime_sha == snap["brave_runtime"]["runtime_receipt_sha256"]
                           and cleanup_sha == snap["brave_runtime"]["cleanup_receipt_sha256"])
        output_hashes = []
        for receipt in (rrec, crec):
            for output in receipt.get("outputs", []):
                output_path = base / output["path"]
                observed = sha(output_path) if output_path.is_file() else None
                output_hashes.append({"path": output["path"], "expected": output.get("sha256"), "actual": observed,
                                      "matches": observed == output.get("sha256")})
        brave_ok = (expected_ids and expected_hashes and rrec.get("result") == crec.get("result") == "PASS"
                    and bool(output_hashes) and all(item["matches"] for item in output_hashes))
        observations.append({"id": "brave_receipts", "status": "PASS" if brave_ok else "FAIL",
                             "evidence": {"runtime_receipt": str(runtime_receipt), "runtime_sha256": runtime_sha,
                                          "runtime_id_matches": runtime_id, "cleanup_receipt": str(cleanup_receipt),
                                          "cleanup_sha256": cleanup_sha, "cleanup_id_matches": cleanup_id,
                                          "work_id": rrec.get("work_id"), "outputs": output_hashes,
                                          "both_results_pass": rrec.get("result") == crec.get("result") == "PASS"}})

        relay = base / ".bago/goals/operational-continuity-governance-20261031/evidence/relay-20261031/r2"
        relay_result = load(relay / "verify-host-result.json")
        relay_receipt_rel = relay_result["run"]["receipt"]
        relay_receipt = relay / "state" / relay_receipt_rel
        relay_sha = sha(relay_receipt)
        relay_receipt_data = load(relay_receipt)
        relay_check = load(relay / "workspace/verification-result.json")
        relay_close = load(relay / "close-result.json")
        relay_ok = (relay_result["run"]["status"] == "PASS" and relay_result["consume"]["evidence_status"] == "VALID"
                    and relay_result["finish"]["work_state"] == "DONE" and relay_check.get("status") == "PASS"
                    and relay_receipt_data.get("execution", {}).get("run_id") == relay_result["run"]["run_id"]
                    and relay_close.get("task_status") == "CLOSED" and relay_close.get("evidence_status") == "VALID"
                    and relay_close.get("outcomes") == {"verify": "PASS", "work": "PASS"})
        observations.append({"id": "relay_r2", "status": "PASS" if relay_ok else "FAIL",
                             "evidence": {"run_id": relay_result["run"]["run_id"], "receipt": str(relay_receipt),
                                          "receipt_sha256": relay_sha, "consume": relay_result["consume"],
                                          "finish": relay_result["finish"], "check_result": relay_check,
                                          "close_result": relay_close}})

        goal = load(project / "goal_status.json")
        local = base / ".bago/team/runtime/handoffs/LOCAL_POLICY.json"
        handoff = load(local)
        rel_outputs = [o for o in handoff.get("outputs", []) if o.get("path", "").replace("\\", "/").endswith("/status.json") or o.get("path", "").replace("\\", "/") == ".bago/goals/operational-continuity-governance-20261031/status.json"]
        status_path = base / ".bago/goals/operational-continuity-governance-20261031/status.json"
        actual_status_sha = sha(status_path)
        expected_status_sha = rel_outputs[0].get("sha256") if len(rel_outputs) == 1 else None
        policy_actual = snap.get("teamctl", {}).get("local_policy_status_actual_sha256")
        policy_expected = snap.get("teamctl", {}).get("local_policy_status_expected_sha256")
        policy_ok = (len(rel_outputs) == 1 and expected_status_sha == policy_expected
                     and actual_status_sha == policy_actual and actual_status_sha == expected_status_sha)
        observations.append({"id": "local_policy_integrity", "status": "PASS" if policy_ok else "FAIL",
                             "evidence": {"handoff": str(local), "status_path": str(status_path),
                                          "handoff_expected_sha256": expected_status_sha,
                                          "snapshot_expected_sha256": policy_expected,
                                          "actual_sha256": actual_status_sha,
                                          "known_mismatch_preserved": actual_status_sha != expected_status_sha}})

        latest_criteria = snap.get("acceptance_criteria", {})
        states = {f"T{i}": latest_criteria.get(f"T{i}") for i in range(1, 13)}
        legacy_criteria = goal.get("acceptance_criteria", [])
        legacy_states = {f"T{int(str(c.get('id', '')).removeprefix('AC-'))}": c.get("state")
                         for c in legacy_criteria if str(c.get("id", "")).startswith("AC-")
                         and str(c.get("id", ""))[3:].isdigit()}
        criteria_ok = len(latest_criteria) == 12 and all(states[f"T{i}"] == "MET" for i in range(1, 13))
        observations.append({"id": "T1_T12", "status": "PASS" if criteria_ok else "FAIL",
                             "evidence": {"states": states, "legacy_local_states": legacy_states,
                                          "all_twelve_met": criteria_ok}})

        teamctl = repo / ".bago/team/kit/scripts/teamctl.py"
        cmd = [__import__("sys").executable, "-B", str(teamctl), "verify"]
        proc = subprocess.run(cmd, cwd=repo, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        stdout = proc.stdout.strip()
        try:
            teamctl_json = json.loads(stdout)
        except Exception:
            teamctl_json = None
        teamctl_ok = proc.returncode == 0 and isinstance(teamctl_json, dict) and teamctl_json.get("status") == "PASS"
        observations.append({"id": "teamctl_verify", "status": "PASS" if teamctl_ok else "FAIL",
                             "evidence": {"argv": cmd, "cwd": str(repo), "returncode": proc.returncode,
                                          "stdout": stdout[:12000], "stderr": proc.stderr[-3000:],
                                          "parsed_status": teamctl_json.get("status") if teamctl_json else None}})
        evaluator_error = False
    except Exception as exc:
        evaluator_error = True
        observations.append({"id": "evaluator_execution", "status": "FAIL",
                             "evidence": {"error": f"{type(exc).__name__}: {exc}"}})
    passed = sum(t["status"] == "PASS" for t in observations)
    result = {"schema": "bago.cognitive.acceptance.v1", "evaluator_error": evaluator_error,
              "tests": observations, "passed": passed, "total": 6,
              "all_passed": (not evaluator_error and len(observations) == 6 and passed == 6),
              "project_files": project_files,
              "product_conclusion": "Original mission remains NO_GO unless every acceptance check passes."}
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
