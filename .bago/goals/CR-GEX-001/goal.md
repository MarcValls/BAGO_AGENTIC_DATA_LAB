# CR-GEX-001 — Contract first: Governed Tool Execution

Goal ID: CR-GEX-001
Date: 2026-10-15
Repository: MarcValls/BAGO_AGENTIC_DATA_LAB
Pinned base: main @ bdf2be825cfd16b3a9b9435efcb7c2384309cf25
Candidate branch: codex/cr-gex-001-contract-v1-20261015
Status: PREPARED / OPEN / NO_GO_FOR_AGENT_RUN_TOOLS
Owner: contract-design candidate; independent verifier not assigned.

## Objective

Cerrar el contrato normativo de identidad, solicitud inmutable, digest, registro versionado, política, aprobación autenticada, Permit verificable, consumo transaccional, evidencia y reconciliación **antes** de conectar efectos a /ws/agents/run. Preservar contratos legacy y route fail-closed.

## Exact scope

Added:
- docs/governed-execution/GEX_V1_NORMATIVE_CONTRACT.md
- docs/governed-execution/GEX_V1_CONFORMANCE_VECTORS.json
- docs/governed-execution/GEX_V1_SCHEMA.json
- docs/governed-execution/BASELINE_AND_GAPS.md
- .bago/goals/CR-GEX-001/goal.md

Do not modify: src/api/server.py, ExecutionGateway, SandboxManager, state_graph.py, MCP adapter, Decision Inspector, canon, README, or existing .bago/team/runtime mission.

## Baseline and authority

Read AGENTS.md, .bago/INDEX.md, .bago/canon/STATE.md, LAB_CONTRACT.md, ARCHITECTURE.md, ROADMAP.md, .bago/runtime/ACTIVE_HANDOFF.md, team protocol, default mission, shared mission state, governance-action-engineer and team-orchestrator skills. Shared .bago/team/runtime/state.json belongs to existing AGENT_CHAT_CONTROL_PLANE_V1 terminal DONE and must not be replaced to start unrelated work.

Source inspected via connected GitHub read API on main (not a local worktree). Older claims including L1 integrated local validation remain scoped to their historical commit, not automatically upgraded.

## Acceptance before freeze

- [x] Legacy boundaries mapped to exact source.
- [x] Normative security semantics specified, including irreversible changes and failure states.
- [x] 40 positive/negative SPEC_ONLY vectors materialized.
- [x] 10 structural wire schemas documented, without runtime authority.
- [ ] Independent contract retest validates cross-field completeness, RFC 8785 interoperability, identities/signatures, CAS races and transition completeness.
- [ ] CR-GEX-002/003/004/005 dependencies resolved or explicitly closed with fail-closed profiles.
- [ ] teamctl verify and mission-specific validated handoff.
- [ ] README generator and check, repository test suite, diff check under pinned worktree, Windows E2E (as applicable).

## Acceptance before available

- [ ] Principal backend authentication real, not Origin-only.
- [ ] Registry versioned + policy and approval authenticated.
- [ ] Verified PermitV1, durable atomic one-use CAS and replay evidence across restart/parallel workers.
- [ ] Real supported typed sandbox operation and receipts persisted for success, denial, failure and uncertain outcome.
- [ ] Independent tests exercise entire API → authorization → gateway → receipt path, including failure injection.
- [ ] /ws/agents/run can report job states truthfully. Until then returns execution_unavailable.

## Evidence and current limits

Static code evidence: docs/governed-execution/BASELINE_AND_GAPS.md.
Contract: docs/governed-execution/GEX_V1_NORMATIVE_CONTRACT.md.
Spec oracle: docs/governed-execution/GEX_V1_CONFORMANCE_VECTORS.json.
Structural schema: docs/governed-execution/GEX_V1_SCHEMA.json.
No full local checkout or ability to run teamctl/test/README generator from GitHub connector: NOT_RUN. Do not claim FROZEN, VERIFIED, VALIDATED or new tool execution AVAILABLE.

## Next consumer

Independent governance/action verifier: resolve CR-GEX-002/003/004/005, check the normative contract against 40 vectors and existing frozen action-inspector projections, produce findings P0/P1/P2 and a materialized team handoff with exact commit and command receipts. Only then decide FREEZE v1, before implementing the minimal vertical slice.
