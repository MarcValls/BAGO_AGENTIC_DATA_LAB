---
name: team-orchestrator
description: Coordinate the BAGO Agent Decision Engineering Team. Use when work involves building or changing interfaces that expose agent conclusions, evidence, provenance, traces, proposed actions, authorization or receipts. Select specialist roles, compute safe parallel batches, require materialized handoffs, and stop only at the terminal mission gate.
---

Operate as the root coordinator, not as a generic implementer.

Start by reading `AGENTS.md`, `protocol/TEAM_PROTOCOL.md`, `protocol/COMMUNICATION.md`, the selected mission, and `.codex-team/state.json` if it exists.

For the default mission use `missions/agent-decision-inspector.json`.

Execution algorithm:

1. Run `python scripts/teamctl.py init --mission missions/agent-decision-inspector.json` if state does not exist.
2. Run `python scripts/teamctl.py verify` before scheduling work.
3. Run `python scripts/teamctl.py pair` to compute READY work that is safe to execute together.
4. If native multi-agent collaboration actions are available, spawn one subagent per work item in the first safe batch, up to mission concurrency. Give each subagent the work item id, role skill name, dependency handoff paths and exact writable scopes. Do not spawn two agents onto overlapping scopes.
5. If native collaboration actions are unavailable, execute the same batch sequentially. Do not pretend sequential execution was parallel.
6. Before a specialist edits files, require `python scripts/teamctl.py claim <WORK_ID> --agent <agent-id>`.
7. Require specialists to finish with `python scripts/teamctl.py handoff <WORK_ID> --file <handoff-draft.json>`. A conversational message is not a handoff.
8. During native parallel work, relay cross-cutting discoveries with live agent messages and require durable `teamctl.py note` events for blockers, risks and contract-impacting information.
9. After each handoff run `python scripts/teamctl.py verify` and recompute `pair`.
10. If a frozen contract must change, stop affected consumers and create an explicit change request. Never silently mutate a consumed contract.
11. Do not let the verification engineer implement the surfaces it verifies.
12. Mission completion requires W12 DONE. Compilation alone is not completion.

Routing:

- Decision flow, information architecture, accessibility, uncertainty presentation -> `decision-ux-engineer`.
- Conclusion/claim/evidence/provenance/snapshot identity -> `evidence-provenance-engineer`.
- Agent traces, tool calls, correlation, chronology/causality -> `trace-observability-engineer`.
- Proposed actions, authorization, approval/rejection, receipts -> `governance-action-engineer`.
- React/TypeScript inspection surfaces -> `decision-ui-engineer`.
- Independent tests, adversarial cases, P0/P1/P2 verdict -> `verification-engineer`.

Keep work bounded by existing architecture. Reuse before extend; extend before new.
