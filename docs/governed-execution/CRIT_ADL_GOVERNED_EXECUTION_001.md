# CRIT-ADL-GOVERNED-EXECUTION-001 — Preliminary gate (NOT a passing retest)

**Candidate base:** main `bdf2be825cfd16b3a9b9435efcb7c2384309cf25`.
**Scope:** CR-GEX-001 and bounded decisions CR-GEX-002/003/004/005.
**Status:** CONTRACT PREPARED / CRIT NO_GO FOR RUNTIME / DESIGN FREEZE PENDING.
**Separation:** legacy local LangGraph L1 tests and demo are not evidence of governed `/ws/agents/run`.

## Claim → command/evidence → conclusion

| Claim | Concrete check or evidence | Conclusion |
|---|---|---|
| Request identity, arguments, policy, version and workspace are represented | GEX_V1_SCHEMA.json + normative contract; isolated Draft 2020-12 tests | Contract shape VERIFIED for tested examples; no runtime binding |
| Permit claims immutable; use-state separate | PermitV1 vs PermitUseStateV1 structural test | Shape VERIFIED, durable signing and CAS NOT_RUN |
| Pre-auth denials do not fabricate a principal or request | IngressDenialReceiptV1, GEX-004, independent schema tests | Spec consistency checked; production ingress persistence NOT_RUN |
| Unregistered proposal cannot execute | ToolProposalEnvelopeV1 + ProposalDenialReceiptV1 | Contract only; transport path NOT_RUN |
| Human approval binds exact full request | RFC 8785 digest + ApprovalV1 schema and HMAC fixtures | Fixed sample checks only; external authenticator NOT_RUN |
| Durable replay safety across processes/restarts | SQLite CAS architecture in CR_GEX_002_005_RESOLUTIONS.md | NOT_IMPLEMENTED / NO_GO |
| Real gateway/sandbox/receipt path | Existing legacy ExecutionGateway/SandboxManager and sandbox receipts inspected | Reusable in future; new GEX vertical slice NOT_RUN |
| No silent success after unknown effect | GEX_V1_STATE_MACHINE.json transitions and negative vectors | Normative; fault injection NOT_RUN |
| Agent run remains closed | Static route check in GEX spec suite | PASS static; no new runtime execution connected |
| Contract consistency test suite | GitHub Actions isolated `GEX contract candidate consistency` run **38726786310**, commit `14ec5234f3a78e951ac5cc226441b585c4b686ba`: **16 passed** | PASS as specification tests only |
| Independent review | GitHub Copilot PR #59 review submitted seven findings (six P1 and one P2); corrections have been made but no final clean independent retest yet | OPEN / DO NOT FREEZE |

## Actual outstanding implementation severity

- **P0:** No authenticated backend principal/workspace resolver is wired to `/ws/agents/run`.
- **P0:** No cryptographically verified GEX PermitV1 + matching authenticated approval/explicit auto-policy and durable CAS is wired to an effect.
- **P1:** No transactional persisted ledger receipt/recovery chain has been verified under crash/replay/concurrency.
- **P1:** No first read-only fixture capability traverses registry → policy → SQLite permit use → ExecutionGateway → SandboxManager → persisted observed receipt end-to-end.
- **P1:** No independent Windows threat/isolation assessment; code/process/network effects must stay unavailable.
- **P1:** The repository-required `teamctl` GEX-specific mission handoff and independent terminal gate have not run.

Counts here are **blocking criteria for runtime availability**, not claims of regressions to the historical local demos. The earlier independent review findings were contractual inconsistencies; their remediation is still subject to re-review.

## Preservation and security boundary

Existing runtime modules and `/ws/agents/run` are untouched. No model-controlled tool may execute via this work. The current PR remains draft pending independent reviewer clearance, generator/check verification, and a GEX-specific materialized handoff.

## Next admissible action

1. Request independent re-review of latest contract/schema/vectors/state-machine plus exact SHA; close every reviewer P0/P1 with evidence.
2. Run `python .bago/team/kit/scripts/teamctl.py verify`, then goal-specific protocol-compliant handoff and final gate (do not reset the existing mission).
3. Run `python scripts/generate_dynamic_readme.py` and `python scripts/generate_dynamic_readme.py --check --skip-tests` at the exact candidate, with full suite and `git diff --check`; retain receipts.
4. Only after frozen contract, implement READ-only trusted fixture vertical slice with real signed authenticated identity, local SQLite CAS, fault-injection and persistent receipt tests.
5. Keep `/ws/agents/run` returning `execution_unavailable` until actual API → worker/adapter execution is demonstrated.

**CRIT verdict: NO_GO for enabled governed tool execution.**
