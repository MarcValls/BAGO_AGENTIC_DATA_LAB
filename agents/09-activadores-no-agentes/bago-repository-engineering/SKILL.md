---
name: bago-repository-engineering
description: Govern material BAGO repository changes: resolve authority, preserve worktree boundaries, select evidence, and hand off cross-domain effects.
metadata:
  targetHarness: codex
  source: BAGO_COPILOT_ENGINEERING_PACK_v1.1.0_FRONTEND_PREPARED
  adaptation: Native Codex skill; uses .bago lifecycle and .codex agents, never .gabo or Copilot hooks.
---

# BAGO Repository Engineering

Use for material repository implementation, release-sensitive work, or cross-domain changes. Start with `bago-core` and the live repository state.

1. Resolve root, HEAD, worktree, pre-existing changes, user authority and applicable canon.
2. Classify the request as audit, trace, implementation, mechanical change, refactor, verification, or release work.
3. Define the smallest scope, invariant, recovery path, tests and required cross-domain handoffs before editing.
4. Preserve unrelated changes. Do not mutate canon, credentials, remotes, releases, or runtime copies without explicit authorization.
5. Bind verification to the final state with `python .bago/bin/bago.py verify -- <command>`.

Use the Codex roles under `.codex/agents`: explorers/mappers for discovery; auditors for read-only review; workers for approved changes; frontend engineer/verifier and UI tracer/auditor for frontend work; final verifier for independent closure.

Report facts, inference, proposed work, executed actions, evidence and `NOT_RUN` separately. `EXECUTED` means changed; `VERIFIED` requires passing final-state evidence; `VALIDATED` requires explicit acceptance criteria.
