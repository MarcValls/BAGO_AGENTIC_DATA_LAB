---
name: bago-modularity
description: Detect monolithic BAGO modules, identify safe centralization opportunities, and guard new implementations against mixed responsibilities before code is written.
metadata:
  targetHarness: codex
  group: monolith-scanner, modularity-architect, centralization-auditor, modularity-guardian
---

# BAGO Modularity

Use for a modularity audit, a proposed large feature, duplicated behavior, or a module that is difficult to test/change. Start with `bago-core` and preserve unrelated work.

## Group routing

- `bago_monolith_scanner`: inventory candidates and evidence. Run `scripts/scan_monolith_candidates.py` first; line count is only a triage signal.
- `bago_centralization_auditor`: find duplicated behavior and propose one owner only when semantic variation is not intentional.
- `bago_modularity_architect`: design an incremental extraction with contracts, dependency direction and regression gates.
- `bago_modularity_guardian`: before material implementation, return `PROCEED`, `ARCHITECTURE_GUIDED`, or `HANDOFF_REQUIRED`. In `ARCHITECTURE_GUIDED`, coordinate a minimal boundary with the architect and continue implementation from that structure; it is not a stop state.

## Invariants

- A module may be large; modularize only with evidence of mixed responsibilities, unstable boundaries, duplicated behavior, or inadequate testability.
- Do not replace a monolith with indirection. Every extracted module needs a clear owner, public contract and consumer.
- Backend authority, canonical navigation, API transport and persisted state retain their existing owners unless the task explicitly changes them.
- Centralize behavior, not merely matching text. Keep intentional domain variation local.

## Closure

For an approved extraction: trace imports/contracts before and after, add or adjust focused tests, run the relevant repository gates, then request an independent verifier. Record `NOT_RUN` for runtime/visual checks that were not performed.
