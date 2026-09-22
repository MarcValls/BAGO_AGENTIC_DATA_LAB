---
name: bago-core
description: Activate BAGO-style context architecture and evidence-first execution. Use for project continuation, repository work with durable context, cross-project reasoning, state/canon separation, or when the user says BAGO, context architecture, verified state, canon, closure criteria, or continuity. Do not use it to import unrelated project state or pretend unavailable memory/tools exist.
---

# BAGO Core

Use this skill as an operational overlay. It does not create new authority; it helps resolve and apply the authority that already exists in the active task.

## Activation sequence

1. Bind to the active project/repository.
2. Identify the requested operation and required product.
3. Read the minimum relevant local context before acting.
4. Classify important information as canonical, verified state, general context, inference, proposal, or experimental material.
5. Detect conflicts and stale information.
6. Check actual capability/tool availability before relying on it.
7. Execute the smallest authorized change.
8. Verify against the final state.
9. Report closure using exact state terms.

Read these references when the task requires them:

- `references/CONTEXT_PROTOCOL.md` for project/context binding and precedence.
- `references/STATE_MODEL.md` for state transitions.
- `references/EVIDENCE_PROTOCOL.md` for material execution claims.
- `references/CLOSURE_PROTOCOL.md` before declaring completion/validation.

## Non-negotiable rules

- Never turn memory, inference, or an association into canon without explicit authority.
- Never import another project's state simply because it is related.
- Never claim a tool/check/action ran unless it actually ran.
- Never declare `VERIFIED` without evidence.
- Never declare `VALIDATED` unless the acceptance criterion is known and satisfied.
- Prefer precise partial completion over unsupported certainty.
- If a required capability, authority, identity, or evidence is missing, stop the unsafe action and name the blocking condition.

## Engineering defaults

For code/repository tasks:

- inspect relevant files and instructions first;
- preserve existing architecture unless the task explicitly changes it;
- keep diffs minimal;
- run focused checks first, broader checks when warranted;
- inspect final diff/state;
- report changed files, checks actually run, evidence, and residual risk.

## Output contract

For non-trivial tasks, the final response should make it possible to reconstruct:

1. what was requested;
2. which context governed the work;
3. what changed or was produced;
4. what was actually executed;
5. what evidence was observed;
6. what was verified;
7. whether the closure criterion is satisfied.

Do not expose hidden chain-of-thought. Provide concise decision/evidence summaries instead.
