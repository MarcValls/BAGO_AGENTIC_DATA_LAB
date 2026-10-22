# COMMUNICATION CONTRACT v0.1.0

The team uses two communication layers.

## Live layer

When native multi-agent collaboration is available, agents may exchange live messages for questions, blockers and discoveries. Live messages accelerate work but are not authoritative project state.

Any message that changes a contract, dependency, risk classification or consumer expectation must also be materialized.

## Durable layer

Use:

`python .bago/team/kit/scripts/teamctl.py note --from-agent <id> --to-agent <id-or-root> --kind INFO|BLOCKER|CONTRACT|RISK|QUESTION --text "..."`

This appends the note to `.bago/team/runtime/events.jsonl`.

Completion is communicated only through a validated handoff. A live message saying "done" never unlocks dependent work.

## Same-batch rule

Agents in one safe parallel batch may read shared frozen inputs, but they must not make each other depend on undocumented intermediate state. If one discovers a fact the other needs:

1. send a live message if available;
2. write a durable note;
3. if the fact changes a frozen contract, stop the affected work and escalate to the orchestrator instead of silently adapting.

## Root responsibility

The orchestrator is responsible for broadcasting changes that affect more than one active work item and for recomputing safe scheduling after every completed handoff or contract-impacting event.


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
