# PROMPT 6 — BAGO_AGENTIC_DATA_LAB_DEMO_RELEASE_CHECK

- **SHA candidato:** `9a315c8abf9bf0c5a9414e7e1954f50945a8fc62`
- **Versión:** `1.0.0` (`VERSION`)
- **Tests:** PASS — `151 passed, 5 warnings`.
- **CI:** workflow syntax/config reviewed; `python demo.py` step present and compiles. Remote GitHub Actions execution for this candidate: NOT_OBSERVED. Docker service steps run in CI but were not rerun locally because host Docker daemon is unavailable.
- **Clean clone:** PASS — cloned commit `aeddfe0` on Windows, created Python 3.11 venv, installed requirements, ran only documented `python demo.py`; created all five outputs and IDs aligned. Later changes since that clean clone affect walkthrough/release docs only; runtime/code/requirements are unchanged.
- **Demo:** PASS — canonical fixture command outputs PASS, 2 retrieval hits, 15 trace events, evaluation 1.0; no network or credentials.
- **Receipts:** PASS — provider fixture receipt, ontology receipt and sandbox receipt present; provider and sandbox permit/receipt IDs serialized.
- **Trace:** PASS — 15 events; run ID matches agent and receipts; trace ID matches evaluation.
- **Evaluation:** PASS — 7/7 structural checks, score 1.0; not an answer-quality metric.
- **README:** PASS — generated section, `README --check` passes, command/artifacts/limits linked to detailed docs.
- **Artifacts:** PASS — canonical five JSON files in `evidence/one_command_demo/`; same run/trace IDs.
- **Configuration:** Python 3.11+; only pinned requirements; no environment variables/secrets needed. Isolated Python 3.11 venv `pip check` passed. Global developer Python 3.14 environment has unrelated litellm/click mismatch and compatibility warnings; not present in clean venv.
- **License:** MIT present.
- **Local paths/secrets scan:** no user home path, AWS key marker, TODO/FIXME in release/demo docs or canonical artifacts.
- **Working tree:** only `.bago/goals/` internal untracked goal state; release candidate files are committed.
- **Release notes:** `RELEASE_NOTES_DEMO_V1.md`.

## Blockers/priorities

- **P0:** 0.
- **P1:** 0 observed.
- **P2:** remote CI run not yet observed; five legacy/environment warnings; generated run IDs/hashes vary across executions (documented); `demo_output/` is ignored runtime output, canonical artifacts are separately versioned under `evidence/one_command_demo/`.

## Verdict

`FREEZE_V1` candidate is locally ready, subject to PROMPT 7 independent critical pass. Remote CI is configured but must not be represented as passed until a run is observed.

**Progress:** `███████████████████░ 98 %`