# W04 Independent Verification — Agent Evaluation Lab

**Date:** 2026-10-10 (Europe/Madrid)  
**Reviewer:** `bago-verifier`  
**Scope:** Read-only review against `implementation-runtime/evidence/W01_API_CONTRACT.md`; no product edits and no live provider request.

## Candidate identity and baseline

- Worktree: `C:\Users\AMTEC_Terminal_1º\AppData\Local\Temp\BAGO_ADL_agent_evaluation_lab_20261010`
- Branch: `codex/adl-agent-evaluation-lab-20261010`
- Git HEAD/baseline: `1e4d9f930da1225ce61ce27def897f76d57a08fc` (unchanged; product changes remain uncommitted/dirty).
- Post-hardening source fingerprint supplied by the root reviewer: SHA-256 `8c751f67b4454e3654fba0dfdb31a732775b215454d987bd58d392ba3b15a87c` over 13 product/test/doc files. I inspected the current detector, its focused test, UI warning, docs, frozen-contract clarification, and SSR test; I did not independently reconstruct this aggregate fingerprint.
- Current file SHA-256 values observed in this review: `src/evaluation/agent_lab.py` `E34AF10046FD5DFF748CBED1763677902B211CDAD842985DF923BF50EA68BC94`; `src/api/server.py` `16FBAC9E16DB9878B30CEDDD633DE0C6CE68AD9F729A2DD5E6D4F61F7C91DD74`; `frontend/src/components/AgentEvaluationLab.tsx` `5B2AFA980F753F1B065079A97163F4E1EA5A9EE54D4C3FA03D37BB664FDF3344`; `tests/test_agent_evaluation_lab.py` `D3217C9ADF897AE5294C06BF1D13E5C5F9AF42BDA2EAC19A5CB9DF68A4E56626`; SSR test `D0923A342195C7D3FC9C923D7FD3565E1A77653F6CB476D80BCCDDC5717EE82A`.

## Independent findings

### P0 — none observed

The reviewed evaluation endpoint calls only the configured Ollama chat adapter after suite-revision, persisted-agent, provider-status, model-catalog and active-run checks. The case path sends a system/user message pair, creates no job, and uses no agent tools or workspace-write operation. The UI makes the provider request only after explicit Run and requires a catalog-listed model.

### P1 privacy finding — MITIGATED WITH AN EXPLICIT HEURISTIC LIMIT

CR-002 narrows the contract to pattern-based detection and expressly says arbitrary secrets in natural language cannot be identified reliably. The final detector adds labeled credentials, common token patterns and a high-entropy opaque-string heuristic; the focused test rejects and redacts an unlabeled high-entropy token. The UI and docs now warn users not to put secrets in prompts or evaluation cases. This addresses the earlier overbroad privacy claim; it is not universal secret detection.

Residual behavior is explicit: long hexadecimal values can be false positives (the detector matches hex strings of 32 or more characters), and unrecognized secrets can evade the heuristic. Do not describe this as guaranteed redaction.

References: `src/evaluation/agent_lab.py`; `tests/test_agent_evaluation_lab.py::test_unlabeled_high_entropy_secrets_are_rejected_and_redacted`; `frontend/src/components/AgentEvaluationLab.tsx`; `docs/agent_evaluation_lab.md`; CR-002 in `W01_API_CONTRACT.md`.

### P2 UI verification finding — OPEN / PARTIALLY MITIGATED

The added React SSR test renders the actual `AgentEvaluationLab` component and asserts its accessible initial loading state (`role="status"`, “Loading evaluation workspace”). This is stronger than the earlier API-client-only tests and verifies that one component branch renders before effects fetch data.

It does not cover the rest of W01's required UI test surface: empty data, service/request errors, editing and review, explicit Run interaction, result/trace rendering, or inaccessible model state. `agent-evaluation-lab.test.mjs` still tests the fetch client using stubs; it does not mount the component. Trace-unavailable behavior is handled in code (`trace_local_failed` is returned and the deterministic `trace_local_saved` check fails), but there is no focused test for the failure-to-save branch in the current backend test file. Therefore W01 frontend test acceptance remains partial and this P2 stays open.

### Other contract checks — source-supported, not rerun here

- **Provider failure / no fixture fallback:** provider and catalog preflights precede `ollama.chat`; tests stub the provider and assert preflight failures cannot invoke chat. A completed test-path provider failure is recorded as `ERROR` with a safe code.
- **Stale revision / malformed suite:** revision mismatch returns 409 before agent/provider preflight; malformed case constraints are rejected by validation tests.
- **Trace and privacy boundaries:** LocalTrace attributes omit prompts/outputs and mark cost `not_reported`; response preview is bounded and filtered; Jaeger metadata is emitted only after a successful export receipt and trace ID.
- **Fixture versus live:** deterministic tests use stubs and are not live-model evidence. No production endpoint fixture fallback is present in the reviewed run path.

## Live evidence receipt considered

I reviewed `.goals/ADL-AGENT-EVALUATION-LAB-001/evidence/live-ollama/receipt.json` and its LocalTrace `traces/trace-c03d1ed69fe647a2.json`. The receipt reports one real Ollama Cloud request via the Evaluation Lab API using `gemma4:31b`, persisted agent `agent_d3e63db8b4704080b924a05fb1ab71fc`, a single synthetic case, PASS, run ID `evalrun_167d1a0a434a400989aceaed64f24630`, a response hash, and LocalTrace ID `trace-c03d1ed69fe647a2`. The matching trace records run/suite/case/agent/model/provider identity, `outcome=PASS`, `cost_status=not_reported`, and no prompt/output fields.

This is credible evidence of a real app/provider path in the base candidate's unchanged inference flow, but the receipt itself omits the actual response preview and has `trace_state=local_only`; it does not provide independently inspectable response text or Jaeger evidence. The receipt predates the final detector-only hardening, so it is not a live retest of the final aggregate source fingerprint. I made no new provider request.

## Test and check evidence boundaries

**Checks I ran during this independent review:** read-only source/contract/test/receipt inspection; `git rev-parse HEAD`; `git branch --show-current`; `git status --short`; per-file `Get-FileHash`; `rg` source searches; `git diff --check` (which only checks tracked diffs and does not cover untracked files). I did not run Python tests, Ruff, `py_compile`, frontend tests, a build, a browser test, a runtime/API request, a provider request, or Jaeger export/readback.

**Final test evidence reported by the root reviewer, not independently rerun by me:**

- `python -m pytest tests/test_agent_evaluation_lab.py tests/test_capability_manager.py tests/test_agent_chat_trace.py -q` — reported 27 passed; one Python 3.14/Pydantic-v1 compatibility warning.
- `ruff check src/evaluation/agent_lab.py src/capabilities/manager.py tests/test_agent_evaluation_lab.py tests/test_capability_manager.py` — reported PASS.
- `ruff check --ignore F811 src/api/server.py` — reported PASS with three pre-existing F811 findings excluded.
- `python -m py_compile ...` on scoped backend/test files — reported PASS.
- `git diff --check` — reported PASS.
- Frontend `node --test tests/ui/agent-evaluation-lab/agent-evaluation-lab.test.mjs` — reported 5 passed.
- Production `npm run build` — reported PASS.
- Compiled React SSR initial-loading test using `tsc` and a temporary CSS hook, then Node test runner — reported 1 passed.
- Frontend lint — reported NOT_RUN because ESLint is unavailable.

These results are recorded as external execution evidence from the root reviewer. This review does not claim to have executed them. Live Ollama was run before the latest detector hardening; Jaeger/OTLP was NOT_RUN.

## Verdict

No P0 was observed. The privacy P1 is mitigated by CR-002's explicit heuristic boundary and matching UX/documentation; avoid claiming universal secret detection. The UI-test P2 is only partially mitigated by the initial-loading SSR test and remains open against W01. Overall candidate is **not independently VALIDATED** while that UI acceptance item remains partial. No commit, push, merge, publication, product edit, or live provider action was performed by this reviewer.
