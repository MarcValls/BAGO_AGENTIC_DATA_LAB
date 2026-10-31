#!/usr/bin/env python3
"""Independent final verifier for a three-cycle native cognitive audit."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

FILES = ("REQUIREMENTS.md", "mission_snapshot.json", "goal_status.json", "PROVENANCE.json", "pyproject.toml")
STAGES = ("OBSERVE", "DETECT", "PROPOSE", "SELECT", "ACT", "VALIDATE", "RECORD", "REFLECT", "EVOLVE", "REMEMBER", "DISTILL", "EMIT")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def canonical(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def check(work: Path):
    checks = []
    freeze = load(work / "evidence/INPUT_FREEZE.json")
    config = load(work / "CONFIG.json")
    candidate_hashes = {rel: sha(work / rel) for rel in freeze["candidate"]}
    freeze_ok = candidate_hashes == freeze["candidate"] and sha(work / "candidate/src/evaluate_mission.py") == freeze["oracle_sha256"] == config["evaluator_sha256"]
    checks.append({"id": "input_freeze", "status": "PASS" if freeze_ok else "FAIL",
                   "candidate": candidate_hashes, "evaluator_sha256": sha(work / "candidate/src/evaluate_mission.py"),
                   "frozen_evaluator_sha256": freeze.get("oracle_sha256"), "config_evaluator_sha256": config.get("evaluator_sha256")})

    processes, sessions, memories = set(), set(), []
    cycle_checks = []
    no_writes = True
    native_ok = True
    gateway_ok = True
    mailbox_ok = True
    immutable_ok = True
    truthful_fail = True
    cycles = []
    for n in range(1, 4):
        tag = f"{n:02}"
        result = load(work / f"evidence/cycle-{tag}-result.json")
        trace = load(work / f"evidence/cycle-{tag}-trace.json")
        observation = load(work / f"evidence/cycle-{tag}-observation.json")
        reflection_session = load(work / f"evidence/cycle-{tag}-reflect-session.json")
        propose_session = load(work / f"evidence/cycle-{tag}-propose-session.json")
        pid, sid = result.get("pid"), result.get("native_session_id")
        processes.add(pid)
        sessions.add(sid)
        memories.append(result.get("memory_entries"))
        cycle_product = result.get("product_status") == "FAIL" and observation.get("all_passed") is False
        truthful_fail = truthful_fail and cycle_product
        source_hashes = {name: sha(work / "project" / name) for name in FILES}
        immutable_ok = immutable_ok and source_hashes == freeze.get("project", {}) == result.get("source_sha256")

        entered = [e.get("stage") for e in trace if e.get("kind") == "STAGE_ENTER"]
        exited = [e.get("stage") for e in trace if e.get("kind") == "STAGE_EXIT"]
        native_ok = native_ok and entered == list(STAGES) and exited == list(STAGES) and result.get("stages") == list(STAGES)
        turns = [e for e in trace if e.get("kind") == "COGNITIVE_TURN"]
        by_stage = {e.get("stage"): e for e in turns}
        native_ok = native_ok and len(turns) == 2 and set(by_stage) == {"PROPOSE", "REFLECT"}
        for turn_name in ("PROPOSE", "REFLECT"):
            turn = by_stage.get(turn_name, {})
            exchange = turn.get("host_exchange", {})
            key = exchange.get("request_id")
            box = work / "mailbox"
            req_path, resp_path = box / f"{key}.request.json", box / f"{key}.response.json"
            try:
                req, resp = load(req_path), load(resp_path)
                req_hash = hashlib.sha256(canonical(req)).hexdigest()
                binding_ok = (req.get("id") == key and req_hash == exchange.get("request_sha256")
                              and resp.get("request_id") == key and resp.get("request_sha256") == req_hash
                              and resp.get("mode") == "live" and sha(resp_path) == exchange.get("response_sha256"))
            except Exception:
                binding_ok = False
            mailbox_ok = mailbox_ok and binding_ok and exchange.get("mode") == "live"
            context_ok = (turn.get("context_envelope_id") and turn.get("reflexive_question")
                          and turn.get("spbe_result", {}).get("kind") == "PROPOSAL_READY"
                          and turn.get("context_binding", {}).get("origin") == "cognitive-mission-adapter"
                          and turn.get("context_binding", {}).get("authority") == "data_only_no_permissions")
            native_ok = native_ok and bool(context_ok)
        refl = reflection_session.get("response", {})
        refl_honest = refl.get("observed_product") == "FAIL" and refl.get("proposed_changes") == []
        truthful_fail = truthful_fail and refl_honest
        cycle_checks.append({"cycle": n, "pid": pid, "session_id": sid, "memory_entries": result.get("memory_entries"),
                             "stage_order_valid": entered == list(STAGES) and exited == list(STAGES),
                             "mailbox_live_bindings_valid": mailbox_ok, "reflection_honest_fail": refl_honest,
                             "product_fail": cycle_product, "source_hashes_unchanged": source_hashes == freeze.get("project", {})})
        events = [e for e in trace if e.get("kind") == "GATEWAY_EXECUTION"]
        plan_steps = [e for e in trace if e.get("kind") == "PLAN_STEP"]
        if (any(e.get("effect_id") == "filesystem.write" for e in events)
                or any(e.get("action") == "write_file" for e in plan_steps)):
            no_writes = False
        process_events = [e for e in events if e.get("effect_id") == "process.execute"]
        consumed = False
        for event in process_events:
            auth = event.get("authorization", {})
            state = str(auth.get("state", auth.get("status", auth.get("permit_state", "")))).upper()
            consumed = consumed or bool(event.get("result", {}).get("ok") and event.get("result", {}).get("receipt_id")
                                       and (auth.get("consumed") is True or state in {"CONSUMED", "USED", "EXECUTED"}))
        gateway_ok = gateway_ok and bool(process_events) and consumed
        cycles.append({"result": result, "observation": observation, "trace": trace,
                       "proposal": propose_session, "reflection": reflection_session})

    distinct = len(processes) == 3 and None not in processes and len(sessions) == 1 and None not in sessions and "" not in sessions
    memory_ok = memories == [1, 2, 3]
    checks.extend([
        {"id": "three_processes_and_memory", "status": "PASS" if distinct and memory_ok else "FAIL",
         "pids": sorted(processes, key=str), "session_ids": sorted(sessions, key=str), "memory_entries": memories},
        {"id": "native_spiral_and_host_turns", "status": "PASS" if native_ok and mailbox_ok else "FAIL",
         "stages": list(STAGES), "cycles": cycle_checks},
        {"id": "context_reflexive_spbe", "status": "PASS" if native_ok else "FAIL"},
        {"id": "gateway_permissions_and_no_writes", "status": "PASS" if gateway_ok and no_writes else "FAIL",
         "process_permission_consumed": gateway_ok, "filesystem_write_seen": not no_writes},
        {"id": "original_product_fail_and_honest_reflection", "status": "PASS" if truthful_fail else "FAIL",
         "all_three_product_fail": truthful_fail},
        {"id": "project_inputs_immutable", "status": "PASS" if immutable_ok else "FAIL",
         "files": {name: sha(work / "project" / name) for name in FILES}},
    ])
    passed = all(c["status"] == "PASS" for c in checks)
    final = {"schema": "bago.cognitive.final-verification.v1", "status": "PASS" if passed else "FAIL",
             "coverage": "COMPLETE" if passed else "INCOMPLETE", "checks": checks,
             "product_conclusion": "Original mission remains NO_GO; this result verifies the cognitive audit integration only.",
             "original_mission_product": "FAIL/NO_GO", "cycle_count": len(cycles),
             "evaluator_sha256": sha(work / "candidate/src/evaluate_mission.py"),
             "input_freeze_sha256": sha(work / "evidence/INPUT_FREEZE.json")}
    result = {"schema": "bago.suite.check-result.v1", "status": final["status"], "coverage": final["coverage"],
              "findings": [final["product_conclusion"], "No ConfigManager fixture or product PASS is asserted."]}
    evidence = work / "evidence"
    evidence.mkdir(parents=True, exist_ok=True)
    (evidence / "FINAL_VERIFICATION.json").write_text(json.dumps(final, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    (evidence / "FINAL_CHECK_RESULT.json").write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return final, result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", type=Path, required=True)
    a = ap.parse_args()
    try:
        final, _ = check(a.work.resolve())
    except Exception as exc:
        work = a.work.resolve()
        evidence = work / "evidence"
        evidence.mkdir(parents=True, exist_ok=True)
        final = {"schema": "bago.cognitive.final-verification.v1", "status": "FAIL", "coverage": "INCOMPLETE",
                 "checks": [{"id": "verifier_execution", "status": "FAIL", "error": f"{type(exc).__name__}: {exc}"}],
                 "product_conclusion": "Original mission remains NO_GO; verifier did not establish integration validity."}
        result = {"schema": "bago.suite.check-result.v1", "status": "FAIL", "coverage": "INCOMPLETE",
                  "findings": [final["product_conclusion"], final["checks"][0]["error"]]}
        (evidence / "FINAL_VERIFICATION.json").write_text(json.dumps(final, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        (evidence / "FINAL_CHECK_RESULT.json").write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
