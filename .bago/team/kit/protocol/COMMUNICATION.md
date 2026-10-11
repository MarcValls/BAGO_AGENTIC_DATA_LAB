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
