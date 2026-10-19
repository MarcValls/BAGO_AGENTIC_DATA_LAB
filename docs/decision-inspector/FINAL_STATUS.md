# Decision Inspector v1 — terminal status

## Verdict

Mission `AGENT_DECISION_INSPECTOR_V1` is **DONE** for the declared, read-only
inspection scope. Its W01–W11 dependency handoffs validate, and independent
verification reports **P0=0, P1 open=0**. The Inspector binds a supplied trace
to the selected AgentRun identity; a foreign trace is hidden with a mismatch
notice, and traces are unverified and hidden when the selected run has no
`run_id`.

This closes the Inspector mission only. It does not close the wider ADL/BER goal or connect BER to Agent Runner.

## Evidence index

| Claim | Evidence | Result and scope |
|---|---|---|
| W01–W11 work products and dependencies are materialized | `.bago/team/runtime/handoffs/W01.json` through `W11.json`; `python .bago/team/kit/scripts/teamctl.py --root . verify` | PASS. The validator retains warnings for orphan handoffs AC01–AC10. |
| Inspector contracts and UI integrate evidence, traces, actions, authorization, and receipts | W02–W10 handoffs; `frontend/src/features/decision-inspector/integration/DecisionInspector.tsx` | PASS for the declared source-backed, read-only integration. |
| Foreign and unbound traces cannot contribute timeline correlations | `docs/decision-inspector/verification/W11_INDEPENDENT_VERIFICATION.md`; integration regressions in `frontend/tests/ui/decision-inspector/integration/integration.test.tsx` | Independent adversarial reruns pass for run-A/run-B mismatch and missing AgentRun `run_id`. |
| Focused UI regressions pass | `npm exec --prefix frontend vitest -- run frontend/tests/ui/decision-inspector` | 5 files, 30 tests passed. |
| Production frontend builds | `npm run build --prefix frontend` | TypeScript and Vite build pass; 127 modules transformed. |
| ADL BER client focused regressions pass | `python -m pytest tests/runtime/ber -q` | 4 passed; explicit start/close, artifact verification, typed-process and filesystem behaviors in this test scope. |

## Limitations

- Manual keyboard-only and screen-reader review: `NOT_RUN`.
- The Inspector reads existing ADL AgentRun artifacts. No live BER execution result is connected to ADL API, LocalTrace, evaluation, or the Inspector.
- L0–L15 compatibility/parity and clean-machine standalone packaging remain unverified. Docker Linux engine was unavailable at baseline.
- Agent Runner remains fail-closed; `filesystem.delete` remains blocked.
- Orphan handoff warnings AC01–AC10 are preserved and visible.

## Reproduction

From the ADL worktree root:

```powershell
python .bago/team/kit/scripts/teamctl.py --root . verify
npm exec --prefix frontend vitest -- run frontend/tests/ui/decision-inspector
npm run build --prefix frontend
```

The independent adversarial commands and candidate details are recorded in the W11 verification report and handoff.
