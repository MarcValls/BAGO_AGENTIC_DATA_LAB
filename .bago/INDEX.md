# BAGO context entrypoint

This repository's project context is centralized under `.bago/`. Read this file first, then follow the authority order below. Root `AGENTS.md` is the Codex entrypoint and directs the agent here.

## Authority and reading order

1. Current user instruction and platform constraints.
2. `.bago/canon/` — project canon: state, lab contract, architecture, roadmap, learning ledger and skill matrix.
3. `.bago/goals/<id>/` — goal objective, status and goal-bound evidence. A goal does not override project canon.
4. `.bago/team/kit/` — coordination protocol, mission templates, schemas and canonical `teamctl.py`.
5. `.bago/team/runtime/` — current team mission state, events, handoffs and change requests. This is execution evidence, not canon. Nested per-goal runtime snapshots remain inside their goal and may preserve historical paths.
6. `.bago/context/` — context index and migration/reference records. Generated indexes are aids, not authority.
7. `.bago/runtime/` — active operational handoff and continuation notes.
8. `.bago/providers/` and `.bago/traces/` — provider configuration and execution/observability evidence; do not treat either as project canon. Local traces are the execution evidence source; Jaeger/OpenTelemetry are projections.

## What stays outside `.bago`

Codex/GitHub integration entrypoints such as root `AGENTS.md`, `.codex/`, `.agents/` and `.github/` remain at conventional paths. They are tool configuration or adapters; project context and decisions live in `.bago/`.

The installed BAGO scanner currently emits ignored retrieval data to `.gabo/context/`. Its writer belongs to the external BAGO installation, so `.bago/context/GENERATED_CONTEXT.md` documents that bridge. Treat its caches as disposable retrieval aids, not canon or execution proof.

## Task start

For non-trivial work, identify goal/repository, read relevant canon and active handoff, inspect exact branch/HEAD/worktree, then record the goal and evidence in `.bago/`. Before creating a worktree, fetch the intended remote base (normally `origin/main`), record its exact SHA and branch from that fetched ref. Never assume a local base branch is current. Before publishing, fetch again and ensure the candidate contains the refreshed remote tip; if the base advanced, rebase/recreate and rerun affected checks. Use lifecycle labels precisely: `PROPOSED`, `PREPARED`, `EXECUTED`, `VERIFIED`, `VALIDATED`.
