# Decision action contract v1

Status: **PREPARED** for W05; freeze only when the teamctl handoff validates.

## Authority and source mapping

`src/contracts/action/action.ts` defines a read-only inspection model.
`src/adapters/action/agentRun.ts` projects supplied ADL `AgentRun` proposal,
authorization-decision, permit, execution and receipt fields. It does not
authorize, execute, mint permits, verify receipt signatures or establish BER
authority. A projected receipt is explicitly labeled `source: adl-agent-run`.
The Inspector must keep that observation visually distinct from an
authoritative BAGO BER receipt. Proposal display data and browser interactions
never grant authority.

## Separate lifecycle states

- `proposalState: proposed` represents intent only.
- Capability is populated only from an explicitly supplied capability map;
  eligibility and availability likewise require separate supplied values.
  Missing values remain `unknown`.
- Authorization maps only explicit `ALLOW`, `DENY` and `REQUIRE_HUMAN` values
  to `authorized`, `rejected` and `requires_approval`. This is a recorded
  decision, not proof of a currently valid permit or permission to execute.
  Permit validity is independent and uses explicit issue/expiry timestamps plus
  caller-supplied `asOf`; explicit revocation is distinct from expiry. Missing
  authorization remains `unknown`.
- Execution uses the supplied `called` and outcome. `SUCCESS` without
  `called: true` is `unknown`; a called success without an identity-matched
  receipt is `unverified`. Failure and partial outcomes remain visible.
- Receipt correlation requires a unique supplied receipt ID, or a unique
  request-ID candidate if the proposal did not name a receipt. A match requires
  exact request identity; a supplied permit ID must also match exactly. When
  both sides supply an effect, it must match too. Duplicate or conflicting
  candidates are `mismatch`; a declared absent receipt is `missing`; no
  correlatable identity is `unknown`.

Risk is a transparent classification of effect type: `READ` is read-only,
`WRITE`/`CREATE`/`DELETE` are mutating, external effects are external, and
unknown types remain unknown. This is not a policy verdict or numeric score.
Approval is `required` only for an explicit `REQUIRE_HUMAN`; otherwise it stays
unknown. Actor and reasons appear only when supplied.

## Verification scope and limits

Contract tests cover proposal state, separate lifecycle values, expired and
revoked permits, denied actions, execution failure, absent receipts, duplicate
or mismatched receipt identities, missing request/permit binding, and success
that remains unverified without an exact linked receipt. These checks validate
structural mapping only. They do not verify signatures, evaluate eligibility,
query live capability availability, authorize actions or prove BER execution.

The existing `frontend/src/contracts/action/action.ts` is a separate legacy
copy outside W05's write scope. W05 freezes the source contract under
`src/contracts/action/`; frontend consumers must reconcile it in their
assigned integration scope before claiming consumption of this contract.
