# W11 Independent Verification

## Scope and identity

- Work item: `W11`, independent verification only.
- Candidate: ADL worktree `codex/adl-ber-integration-20261019`, based on W10 snapshot HEAD `585fe4635596b1bd253fb8ba6d5b736ebf133ee9`; verification used the current W11 follow-up worktree state.
- No product source or tests were edited during W11. Temporary adversarial Vitest cases were created under `tests/verification/decision-inspector/`, executed, and removed.
- Current integration source SHA-256: `773F5843CB8C1C66DD502C0B64287CCD854CA101EE2997A9B96F414274E1033D`.
- Current integration test SHA-256: `8B87CCBB1C2EEFE0FA2655B8C004C7C1DB06FC55CAC0219AFFFD2CC7ED3676A3`.
- W02-W10 handoffs and the actual Decision Inspector frontend were reviewed.

## Verification results

| Case | Result | Evidence |
|---|---|---|
| Unsupported claim | PASS | `frontend/tests/ui/decision-inspector/evidence/evidence-explorer.test.tsx`: unsupported, missing, contradictory, and context-only cases render explicitly; claims are not derived from answer text. |
| Stale evidence | PASS | Same test file: expected revision `rev-3` against supplied `rev-2` renders `Freshness: Stale`, retains the reference, and shows the stale warning. |
| Unauthorized proposed action | PASS | `frontend/tests/ui/decision-inspector/actions/action-review.test.tsx`: denied authorization is shown as rejected, execution is not implied, and approve/reject controls are absent. |
| Missing/mismatched receipt | PASS | Same action tests: missing or wrong request/permit receipts remain missing/mismatched; source-reported success without an exact matching receipt remains unverified. Integration filters receipts by exact run ID. |
| Trace ID and explicit correlations | PASS | `frontend/tests/ui/decision-inspector/trace/trace.test.tsx`: supplied tool-call, proposal, request, claim, action, execution, execution-request, permit and receipt IDs remain distinct; navigation uses supplied claim/action IDs. Adapter reports event/envelope `trace_id` mismatch. |
| Frontend contract mirrors | PASS | Integration test byte-compares the five frontend evidence/trace/action contract and adapter mirrors with canonical files. |
| Focused Inspector UI suite | PASS | `npm exec --prefix frontend vitest -- run frontend/tests/ui/decision-inspector`: 5 files, 30 tests passed, 0 failed. |
| Frontend production build | PASS | `npm run build --prefix frontend`: TypeScript and Vite production build passed; 127 modules transformed. |
| Cross-run trace (run-A + run-B) | PASS | Model timeline is absent; `traceBindingIssue` contains expected `run-A` and actual `run-B`; rendered Inspector announces mismatch and hidden correlations; no foreign action ID is exposed. Regression tests are in `frontend/tests/ui/decision-inspector/integration/integration.test.tsx`. |
| Missing selected run ID + supplied trace | PASS | Model timeline is absent and issue kind is `run_id_missing`; rendered Inspector says the trace cannot be bound and hides correlations. Selecting Trace shows the `Unverified` state and binding explanation. This is covered by the committed integration regression plus an independent interactive adversarial rerun. |
| Manual keyboard/screen reader review | NOT_RUN | Automated tests cover native navigation, focusable buttons, and interactive navigation. No manual assistive-technology review was performed. |

## Finding history and resolution

### W11-P1-001 — cross-run trace accepted when both run identities exist — RESOLVED

The initial review found that a `run-A` conclusion could be combined with a `run-B` trace without warning. The follow-up compares the AgentRun ID to the trace envelope, suppresses the foreign timeline and correlations, and visibly reports the mismatch. The independent adversarial rerun confirmed these outcomes.

### W11-P1-002 — trace accepted when selected AgentRun has no run identity — RESOLVED

A subsequent adversarial case found that a valid trace remained visible when `agent_run.run_id` was absent. The follow-up now emits `traceBindingIssue.kind = run_id_missing`, returns no timeline, hides all foreign correlations, and presents the trace as unverified. The independent interactive rerun confirmed each behavior, including the Trace view state.

A first temporary UI harness attempt used singular queries where the page intentionally rendered more than one matching status message; the assertions were corrected to query all matching messages and the rerun passed. This was a harness selector issue, not a product failure.

## Verdict

- P0: 0 found.
- P1: 0 open; P1-001 and P1-002 are resolved for their adversarial cases.
- P2: none assigned.
- Terminal eligibility from W11: **YES**, subject to W12's remaining mission checks.
- Manual keyboard/screen-reader review remains `NOT_RUN` and is retained as a limitation.
- `python .bago/team/kit/scripts/teamctl.py verify`: PASS with preserved orphan handoff warnings `AC01.json` through `AC10.json`; W11 did not remove or alter them.
