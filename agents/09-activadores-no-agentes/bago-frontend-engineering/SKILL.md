---
name: bago-frontend-engineering
description: Apply BAGO frontend change discipline: trace state ownership, preserve backend authority, and verify React/Vite changes with scope-appropriate evidence.
compatibility: Pi 0.84.2+ and Codex environments with repository read, edit, and shell access.
metadata:
  targetHarness: pi
  source: BAGO_COPILOT_ENGINEERING_PACK_v1.1.0_FRONTEND_PREPARED
  adaptation: BAGO monorepo native; no Copilot runtime, hooks, or .gabo namespace
---

# BAGO Frontend Engineering

Use this skill for material work under `frontend/**`. It complements `bago-core`; it does not create a second continuity runtime or override repository canon.

## Operating contract

1. Resolve the live repository root, HEAD, worktree and pre-existing changes.
2. Trace the user-visible surface to its state owner before editing. If a symptom may be backend, API, or Electron-originated, trace that boundary first.
3. Classify each effect: `FIX`, `REFACTOR`, `ADD_SURFACE`, `VISUAL_CHANGE`, `STATE_CHANGE`, `API_CONTRACT_CHANGE`, `PERFORMANCE`, or `ACCESSIBILITY`.
4. Define the smallest scope, invariants, state ownership, expected fallback/loading/error behavior, and verification gates.
5. Preserve the canonical navigation and state systems; do not create parallel navigation, transport, or global-state paths for a local change.
6. Review the final diff for duplicate state, ad-hoc fetches, persisted credentials, hardcoded visual values, and missing blocked/error behavior.

## Ownership rules

- Backend owns sessions, effective provider/model, permissions, jobs, security decisions and evidence. The UI may display/cache them but is not authority.
- Shared UI state is only for cross-component presentation/navigation. Keep transient, local interaction state local.
- Persist only explicit presentation/workflow state. Credentials and tokens must not become persisted UI state.
- Navigation has one canonical destination model; aliases and persisted-state migrations must be explicit and tested.

## Evidence matrix

- TypeScript logic: targeted test + `typecheck`.
- Navigation/state: `typecheck` + interaction/state test; add full tests, build, and reload/persistence evidence when material.
- API contract: client/contract test + `typecheck`; add backend handler/contract evidence and build.
- New surface: typecheck + tests + build; inspect empty/loading/error/blocked states and accessibility.
- CSS/token-only: build + hardcode/token review; rendered visual inspection for material changes.
- Accessibility: semantic, keyboard and focus review; add rendered inspection.
- Performance/refactor: behavioral tests + typecheck + build; use an actual before/after measure when making a performance claim.

A build proves packaging, not interaction correctness. Unit tests do not prove backend integration. Screenshots do not establish system authority.

## Closure

Record `EXECUTED` after files change. Claim `VERIFIED` only when the selected checks ran against the final state. Claim `VALIDATED` only against explicit acceptance criteria. For important closure, request an independent frontend or final verification pass.
