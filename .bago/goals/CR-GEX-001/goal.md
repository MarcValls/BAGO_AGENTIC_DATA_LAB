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
- docs/governed-execution/GEX_V1_STATE_MACHINE.json
- docs/governed-execution/CR_GEX_002_005_RESOLUTIONS.md
- docs/governed-execution/CRIT_ADL_GOVERNED_EXECUTION_001.md
- docs/governed-execution/verification/test_gex_contract_consistency.py
- .github/workflows/gex-contract-consistency.yml
- .github/workflows/gex-readme-evidence.yml
- docs/governed-execution/BASELINE_AND_GAPS.md
- .bago/goals/CR-GEX-001/goal.md

Do not modify: src/api/server.py, ExecutionGateway, SandboxManager, state_graph.py, MCP adapter, Decision Inspector, canon, README, or existing .bago/team/runtime mission.

## Baseline and authority

Read AGENTS.md, .bago/INDEX.md, .bago/canon/STATE.md, LAB_CONTRACT.md, ARCHITECTURE.md, ROADMAP.md, .bago/runtime/ACTIVE_HANDOFF.md, team protocol, default mission, shared mission state, governance-action-engineer and team-orchestrator skills. Shared .bago/team/runtime/state.json belongs to existing AGENT_CHAT_CONTROL_PLANE_V1 terminal DONE and must not be replaced to start unrelated work.

Source inspected via connected GitHub read API on main (not a local worktree). Older claims including L1 integrated local validation remain scoped to their historical commit, not automatically upgraded.

## Acceptance before freeze

- [x] Legacy boundaries mapped to exact source.
- [x] Normative security semantics specified, including irreversible changes and failure states.
- [x] 40 positive/negative SPEC_ONLY vectors materialized, with HMAC fixtures for approval/permit.
- [x] 11 structural wire schemas documented, without runtime authority.
- [ ] Independent contract retest validates cross-field completeness, RFC 8785 interoperability, identities/signatures, CAS races and transition completeness.
- [x] CR-GEX-002/003/004/005 architecture decided with explicit fail-closed profiles; execution controls remain unimplemented.
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

## Recorded CI / independent review chronology

- GEX structural test workflow run 38725338776 at commit 95abceac5041bc1e3547bd75cdafea12b7483942: 11 PASS, before subsequent schema amendments; superseded as final evidence.
- GitHub Copilot reviewer raised seven independent contract findings (six P1, one P2) on PR #59. See PR discussions; fixes were attempted in this branch but require **new independent retest** at exact final SHA.
- Additional isolated GEX test run on commit 2e44baa63976aec59fee380dd9777222838f73cc: PASS, but subsequent ingress-denial additions invalidate treating it as final validation.
- README generator workflow generated and checked README successfully on run 38725962692; full suite result is candidate-bound and later commits require fresh verification.
- Independent full-contract approval, teamctl handoff, runtime vertical slice, failure-injection tests and CRIT closure remain PENDING/NOT_RUN.

**Stop gate:** Do not FREEZE or enable tool execution on /ws/agents/run while an independent P1 remains unresolved or fail-closed production controls are absent.

- Isolated contract consistency GitHub Actions run 38726959879 for commit a841186918a810e2c85c240c3f752b6aaa02b903: PASS (spec tests). Independent reviewer clearance and runtime tests still required.
- New gate report: docs/governed-execution/CRIT_ADL_GOVERNED_EXECUTION_001.md, preliminary NO_GO; no runtime promotion.
