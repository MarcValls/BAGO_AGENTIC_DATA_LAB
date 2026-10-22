# TEAM PROTOCOL v0.3.0 — ADL integrity

## Goal

Coordinate specialized Codex engineering agents without relying on conversational memory. Coordination is materialized in files and validated before each handoff.

## Shared state

All runtime coordination lives under `.bago/team/runtime/` in the target repository:

- `state.json`: mission, work item states, claims and terminal gate.
- `events.jsonl`: append-only coordination log.
- `handoffs/<WORK_ID>.json`: completion evidence for each work item.
- `change_requests/`: explicit requests to modify frozen contracts.

## Work item states

`PENDING -> READY -> CLAIMED -> DONE`

Exceptional states: `BLOCKED`, `INVALIDATED`, `FAILED`.

A work item becomes READY only when every dependency is DONE with a valid handoff.

## Auto-pairing

The orchestrator does not pair agents by persona preference. It pairs READY work items by:

1. Dependency closure.
2. Non-overlapping writable file scopes.
3. Compatible frozen contracts.
4. Independent verification boundaries.
5. Maximum configured concurrency.

`scripts/teamctl.py pair` computes conservative safe batches. If overlap cannot be ruled out, the items are serialized.

## Handoff contract

A DONE handoff must include:

- exact work item id and role;
- changed files;
- outputs/contracts produced;
- verification commands and PASS/FAIL results;
- evidence paths or machine-readable facts;
- residual risks;
- explicit next consumers;
- SHA-256 of the handoff payload.

Consumers must validate the handoff before acting on it.

## Frozen contract rule

A work item may declare outputs as frozen contracts. After a consumer starts, those contracts cannot be silently rewritten. A change requires a change request naming:

- contract id;
- old fingerprint;
- proposed new fingerprint;
- reason;
- impacted consumers;
- required invalidations.

## Parallelism rule

Two work items may execute concurrently only if:

- neither depends on the other;
- all dependencies are already DONE;
- their writable scopes do not overlap;
- neither changes a contract currently consumed by the other;
- verifier independence is preserved.

## Completion rule

Mission closure requires every work item to be DONE and all registered handoffs, dependencies and required execution checks to pass revalidation. ADMINISTRATIVE_DONE alone does not validate a product or satisfy its acceptance criteria.

Open P0/P1 findings in EVIDENCE or COVERAGE block closure for every operation. In AUDIT, documented PRODUCT findings may remain open: a completed audit reports product defects without claiming they are repaired. For REPAIR, VERIFICATION and PROMOTION, an open P0/P1 PRODUCT finding also blocks closure when affects_correction is true. Residual findings and NOT_RUN work must remain explicit; PROMOTION additionally requires its declared destination and applicable gates.


## ADL integrity contract v0.3

The canonical entry is `.bago/team/kit/scripts/teamctl.py`; the plugin is only a launcher.
Install `jsonschema==4.23.0` from kit/root requirements. New missions require operation,
output_scopes and required_checks. `identity` exposes the finite ADL implementation manifest;
`inspect` exposes mission/candidate/scope values for a submitted full-schema handoff.
Never invent these fields or automatically migrate/re-sign legacy evidence.
`status` and legacy `inspect` are read-only and label legacy data LEGACY_UNVERIFIED.
Current consumption/verification rejects legacy states without sufficient identity/receipts.

Use `run-check WORK --check-id ID --command-json '["executable","arg"]' --output relative/file
--allow-execute` for an explicitly authorized real child process. Use the returned verification
entry unchanged. The controller records argv, return code, candidate before/after, identity,
logs and output hashes. Typed command text and NOT_RUN cannot satisfy required_checks.
Paths must be relative canonical POSIX paths within root and declared work scopes: no absolute,
traversal, Windows ADS, symlinks/reparse points. Bad supplied hashes are rejected, never fixed.
ready/pair/claim, checkpoint/run-check, handoff and verify revalidate dependency files recursively
from persistent storage on every invocation, including after process restart. DONE and a monitor
projection are administrative history, not execution proof or host liveness.

Local integrity is not host authentication or a sandbox against an actor able to rewrite the
whole store. Hash checks have a time-of-check/time-of-use boundary. Pause persists before new
work; arbitrary children/descendants may not cooperate. No automatic rollback is asserted.
Preserve failed attempts; recover by restoring exact bytes or explicitly starting a new mission
for changed implementation/identity. Never rewrite old receipts to make a gate pass.
