# Goal: Agent Evaluation Lab for ADL

## Objective
Add a reviewable, repeatable evaluation capability that helps an AI platform/agent engineer test an existing ADL agent against explicit cases, run it through the configured real provider, inspect deterministic grading, and correlate each run to its model and trace.

## Market rationale
Current ADL already has governance/evidence checks and local traces, but those do not evaluate answer quality or catch behavioral regressions across prompt/model changes. Prioritize evaluation and traceability because current agent-engineering reports show broad observability adoption and a remaining gap in offline evaluation practices; the project job matrix also marks evaluation/model comparison as an open capability.

## MVP acceptance criteria
1. An engineer can define a small versioned evaluation suite with explicit input and deterministic assertions, and choose an existing agent/model.
2. A run invokes the real configured provider, records the effective agent/model identity, per-case result, elapsed time, and trace identity. No fixture may be presented as a live model result.
3. The suite and run history persist locally with optimistic conflict or immutable run records; no credentials are serialized.
4. The UI lets the user create/edit a suite, run it, and inspect passed/failed assertions and linked trace metadata with low cognitive load.
5. Failure, provider unavailability, missing model, and missing trace are shown as such; execution remains read-only and cannot change workspace files or create jobs.
6. Focused backend/frontend verification passes against the resulting candidate; one genuine Ollama-backed run is performed only if provider connectivity and the configured model are available, otherwise that portion is `NOT_RUN` with the exact reason.
7. Documentation and evidence state precisely which checks used a fixture and which used the real model.

## Scope boundaries
- No LLM-as-judge claims in this MVP. Grading uses explicitly authored deterministic assertions (for example required/forbidden phrases) and labels their limits.
- No automatic production deployment, job dispatch, workspace writes, new provider, or cloud charge beyond the already configured provider.
- No merge, push, or commit unless separately requested.

## Candidate
- Base: `codex/conversation-library-v1` at `1e4d9f930da1225ce61ce27def897f76d57a08fc`.
- Worktree: `C:\Users\AMTEC_Terminal_1º\AppData\Local\Temp\BAGO_ADL_agent_evaluation_lab_20261010`.
- Branch: `codex/adl-agent-evaluation-lab-20261010`.

## Status
`EXECUTED` — candidate implementation, focused checks, and one live Ollama smoke evaluation exist in the isolated worktree. Validation remains partial because full rendered-state UI coverage is incomplete; Jaeger export and frontend lint are NOT_RUN.
