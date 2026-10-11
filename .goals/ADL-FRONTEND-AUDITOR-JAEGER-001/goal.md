# Goal: Real Frontend Auditor and Jaeger proof

## Objective
Demonstrate that the ADL app's Frontend Auditor, using configured Ollama Cloud through the real agent-chat path, reads current project source files, assesses the historical P1-02 finding against current code with exact citations, and produces a LocalTrace that is exported and independently retrievable in Jaeger. Close the Evaluation Lab's remaining UI verification gaps where practical.

## Why this is the opposite proof
A synthetic echo confirms only connectivity. A real audit must show server-recorded workspace-read sources, model identity, a finding tied to current source lines, and a queryable Jaeger projection for the same chat trace. P1-02 must be reevaluated against the candidate; the 2026-10-09 report is historical evidence and may be stale.

## Acceptance criteria
1. Use the actual ADL `/api/agents/create` and `/api/agents/{id}/chat` paths in an isolated TestClient environment; no fixtures for the provider response.
2. Use the configured `gemma4:31b` provider. The persisted agent is an isolated instance derived from ADL's existing Frontend Auditor definition.
3. Request-scoped read access is enabled for exactly the current `frontend/src/components/AgentRunner.tsx` and `src/api/server.py` source. The API response and trace must contain those exact workspace-relative source receipts.
4. The model response makes a FACT claim about P1-02 and cites current line ranges; an independent deterministic code test confirms the corresponding UI and server behavior.
5. Save a redacted receipt and actual audit report; do not store secrets or claim universal secret detection. Temporary conversations/agent records stay outside tracked project source.
6. Project the resulting LocalTrace via OTLP to the already-running local Jaeger. Query Jaeger's trace API and confirm the returned trace ID, service, model and source attributes match the local receipt. Capture the trace graph/details in a screenshot.
7. Add and run rendered UI tests for the Evaluation Lab's remaining loading/empty/error/review/run/results/unavailable-model states, or record any specific state that cannot be covered and why. Preserve a separate live-provider result from all fixture tests.
8. No production job, workspace write, source modification by the auditor, commit, push, merge or sync occurs during the demonstration.

## Security and evidence boundary
The read tool is a bounded, request-scoped capability; it cannot write, execute commands, or list directories. Provider secrets remain in the OS keyring. The Evaluation Lab secret filter remains heuristic and must not be represented as universal detection. Jaeger is an observability projection; LocalTrace and the agent-chat source receipts are the local evidence.

## Candidate
- Branch: `codex/adl-agent-evaluation-lab-20261010`
- Worktree: `C:\Users\AMTEC_Terminal_1º\AppData\Local\Temp\BAGO_ADL_agent_evaluation_lab_20261010`
- Current HEAD/base: `1e4d9f930da1225ce61ce27def897f76d57a08fc`
- Historical source report: `.bago/CRIT-BAGO-ADL-FRONTEND-20261009-01.md`, SHA-256: `eb331e30bc5f9e720cf2c714e8e02766f8488980c72413ff8b3f9f8ab1ba48bf`

## Final status
`EXECUTED` / `VALIDATION PARTIAL`.

The actual app agent-chat endpoint returned a live Ollama response after two bounded source reads; LocalTrace was saved and projected, Jaeger returned the same trace, and a Jaeger UI screenshot was captured. P1-02 is supported as fixed in this candidate by source review, 14 UI tests, and a deterministic WebSocket test. Evaluation Lab UI tests and build pass. Full validation remains partial because `npm run lint` cannot launch (`eslint` is absent from frontend dependencies), a repeated live call from the isolated CLI context could not access the Windows credential store, and exact-file allowlisting is not enforced by the read capability. See `evidence/FINAL_PROOF.md`.
