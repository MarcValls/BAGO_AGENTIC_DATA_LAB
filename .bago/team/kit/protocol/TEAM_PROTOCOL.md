# TEAM PROTOCOL v0.1.0

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

The mission is complete only when all terminal work items are DONE and the final verification handoff reports no P0/P1 failure. A partially working UI is not mission completion.
