# W13 Receipt Run Binding Remediation

Date: 2026-10-08  
Finding: W11 P1, action receipt provenance does not independently prove run ownership.

## Change

The Decision Inspector integration now forwards receipt records to the action adapter only when each record has an explicit, non-empty `run_id` equal to the source `AgentRun.run_id`. This applies to `decision_receipts`, `mcp_receipts`, and `provider_receipt`. If the source run identity is absent, no receipt can be associated. The adapter and source receipt contents remain authoritative; the integration does not add or infer identities.

An excluded receipt cannot be displayed as matched. If the proposal reports successful execution without another accepted receipt, execution remains `unverified`.

## Adversarial coverage

- Foreign receipt with colliding `receipt_id` and `request_id`: excluded; link state is `missing`; receipt payload is absent; execution is `unverified`.
- Receipt with no explicit `run_id`, including the provider receipt slot: excluded with the same unverified result.

Focused integration checks are recorded in the W13 team handoff. This remediation does not change the shared action receipt contract or adapter.

## Boundary

This establishes a UI integration guard for the current source payload. It does not cryptographically attest receipt origins or validate backend receipt issuance. Independent adversarial re-verification is assigned to W14.
