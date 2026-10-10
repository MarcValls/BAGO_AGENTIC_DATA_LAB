# Agent Evaluation Lab — candidate evidence

Date: 2026-10-10
Candidate: `codex/adl-agent-evaluation-lab-20261010`
Base: `1e4d9f930da1225ce61ce27def897f76d57a08fc`
HEAD at baseline: `1e4d9f930da1225ce61ce27def897f76d57a08fc` (the implementation is uncommitted in the candidate worktree)
Candidate source SHA-256: `8c751f67b4454e3654fba0dfdb31a732775b215454d987bd58d392ba3b15a87c`
Career target selected by user: AI platform and agent engineering.

## Implemented

- Versioned, workspace-isolated evaluation suites and immutable run records in SQLite.
- Explicit run API uses the configured Ollama model after preflight checks; model/agent identity and agent configuration fingerprint are recorded.
- Deterministic checks cover non-empty response, required/forbidden text, and saved LocalTrace. These checks do not establish correctness or general answer quality.
- New Agent Evaluation Lab navigation and chat intent; existing governance Evaluation view remains separate.
- Capability catalog includes bounded `agent.evaluate`; no tools, jobs, or workspace writes are enabled.
- Trace omits prompts and outputs; Jaeger link is conditional on confirmed OTLP export.
- Secret detection is heuristic. It detects known labeled/provider formats and high-entropy opaque values; arbitrary secrets in natural language may escape detection. Long hex values can be false positives. UI and docs instruct users not to put secrets in prompts or cases.

## Verification

| Check | Result | Evidence scope |
|---|---|---|
| Backend focused tests | PASS — 27 passed, 1 Python 3.14/Pydantic compatibility warning | Current candidate source; `test_agent_evaluation_lab`, `test_capability_manager`, `test_agent_chat_trace` |
| Frontend API tests | PASS — 5 passed | Fetch stubs; no browser/server UI integration |
| Frontend component render | PASS — 1 test | React SSR initial accessible loading state only |
| Production build | PASS | TypeScript project build + Vite production build |
| Frontend lint | NOT_RUN | `eslint` unavailable in frontend package |
| Independent review | PASS with residual P2 | W04 details; state UI render coverage remains partial |

## Live provider evidence

One real single-turn Ollama Cloud request was made with `gemma4:31b` and persisted agent `agent_d3e63db8b4704080b924a05fb1ab71fc` (`ADL Read Evidence Agent`, no tools). The case used inline synthetic text only. It returned the expected token and the deterministic suite result was `PASS`. Sanitized receipt: `evidence/live-ollama/receipt.json`; local trace: `evidence/live-ollama/traces/trace-c03d1ed69fe647a2.json`. The run database is outside the repository under the temporary directory.

The live inference preceded the final credential-redaction hardening. The hardened detector was verified afterward with focused unit tests; no second cloud request was made. The receipt proves the provider/evaluation path for this candidate's unchanged inference flow, not broad model quality. Trace state is `local_only`; Jaeger/OTLP export is `NOT_RUN`. Provider usage/cost was `not_reported`.

## Residual validation

W01 asked for rendered UI coverage of empty, error, edit/review, explicit run, result/trace and unavailable-model states. Current UI tests cover API behavior and initial SSR loading only, so that acceptance item remains `PARTIAL` and the overall candidate is not `VALIDATED`. No commit, push, merge or synchronization was performed.
