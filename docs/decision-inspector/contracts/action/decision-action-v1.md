# Decision action contract v1

Status: **PREPARED** for W05; freeze only when the teamctl handoff validates.

## Authority and source mapping

This is a read-only inspection projection. `AgentRun.to_dict()` is the source for run identity, proposal ID, request ID, tool, transport, effect type, arguments, rationale, authorization decision, permit ID, `called`, outcome, receipt ID and error message. `AgentToolProposal` retains those same proposal fields. `Permit` adds signed actor, rationale, issue/expiry times and constraints, but these are not included in the serialized `AgentToolProposal`; consumers may supply the matching permit record explicitly. The adapter does not look up or mint permits.

Receipts are correlated from the run's `decision_receipts`, `mcp_receipts` and optional `provider_receipt`. `MCPCallReceipt` and `BedrockCallReceipt` expose receipt/request/permit IDs, decision, execution outcome, actual effect and evidence refs. `SandboxReceipt` exposes receipt/request/permit IDs, capability, status and evidence refs. The UI model retains only supplied identifiers and fields; it does not become an authorization, execution or receipt authority.

## Separate lifecycle states

- **Capability** asks whether the named capability is available in a supplied capability inventory. A proposal's tool name proves only that it was requested; absent inventory yields `unknown`.
- **Eligibility** is a supplied policy assessment. No local eligibility verdict is invented from a proposal or its risk.
- **Authorization** maps explicit `ALLOW`, `DENY` and `REQUIRE_HUMAN` to authorized, rejected and requires-approval. Missing/other decisions remain `unknown`. Permit validity is a separate field and remains `unknown` unless a permit with both times and an explicit `asOf` is supplied. Expiry is not confused with the historical decision; revocation cannot be concluded unless a source provides it.
- **Availability** describes transport/capability availability only when explicitly supplied. A proposal or configured transport string does not prove a reachable service.
- **Execution** uses explicit `called` and outcome values. A success outcome without `called: true` is `unknown`; success without a matched receipt is `unverified`. Failure and partial outcomes remain visible. `called: false` with no outcome means `not_started`.
- **Receipt** is linked by the proposal receipt ID where present, otherwise by a unique matching request ID. Request/permit mismatch is explicit. A declared but absent receipt is `missing`; no receipt relation in the source is `unknown`. A receipt outcome does not silently overwrite proposal fields.

Risk is a transparent classification of effect type: `READ` is read-only, `WRITE`/`CREATE`/`DELETE` are mutating, and external effects are external. Unknown effect types stay unknown. This category is not a policy decision or numeric risk score. Approval is `required` only for an explicit `REQUIRE_HUMAN`; other cases remain unknown because `ALLOW` does not prove whether a human approved or whether policy required approval. Actor and reasons are shown only when supplied.

## Verification scope

The contract tests exercise unknown proposal fields, distinct lifecycle states, expired permits, denied actions, failed execution, absent/mismatched receipts, and success that remains unverified without a matched receipt. They validate structural mapping only; they do not authorize actions, check live capability availability, infer eligibility, or verify receipt signatures.
