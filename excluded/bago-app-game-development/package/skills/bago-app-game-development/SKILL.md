---
name: bago-app-game-development
description: Plan, build, inspect, debug, and package applications or games in an existing or new project. Routes work by task and platform, checks available tools instead of assuming integrations, and ties completion claims to the actual build or runtime evidence.
metadata:
  version: "1.0.0"
  source: "BAGO App & Game Development package"
---

# BAGO App & Game Development

Use this skill when the user asks to create, improve, debug, review, or package an application or game. Follow the user's chosen platform, engine, stack, scope, and language. This skill does not choose a product or grant permission to publish, deploy, buy assets, install system software, or perform destructive changes.

## Route by task

- For a question, explanation, or small read-only lookup, answer directly and inspect only what is needed. Do not create a goal, delegate, or run a build merely because the topic is software.
- For an audit or bug diagnosis, trace the reported behavior through its real entry point and affected runtime. Report findings before proposing broad redesign.
- For implementation, inspect the active project and local instructions, identify the smallest complete change, and use its existing stack.
- For build, launch, deployment, store submission, or publishing, follow the user's requested target and available authorization. Treat execution success and observed target state as separate facts.

For a larger or riskier task, select only the relevant workflow below:

- Application work: [application workflow](references/application-workflow.md).
- Game work: [game workflow](references/game-workflow.md).
- Tool, engine, and integration selection: [tool routing](references/tool-routing.md).
- Cross-cutting quality and release evidence: [quality and verification](references/quality-and-verification.md).

## Establish the project and stack

Use repository-provided instructions and the user's stated target as authority. If the stack is unclear and matters, inspect the existing project before asking the user. The optional `tools/project_inventory.py` helper can identify common project markers without editing files; use it only when that inventory will reduce uncertainty.

Do not infer that an engine, SDK, plugin, MCP server, browser, simulator, or device is usable from a filename, manifest, past conversation, or documentation alone. Check the current tool/skill catalog and actual runtime. If a needed capability is absent, continue with useful source-level work and label the missing runtime check `NOT_RUN` or `UNKNOWN`.

When starting from an empty directory, preserve an explicit stack choice. If none exists and the choice materially changes the deliverable, compare a small number of suitable options against platform, deployment, performance, team, and maintenance needs; ask one concise question only if repository context cannot settle it.

## Build with a visible outcome

Translate the request into user-visible behavior and the smallest set of changes. For new projects, define the primary flow and one working vertical slice before expanding features. Keep game mechanics, application domain logic, presentation, persistence, and platform adapters separated only as much as the project warrants.

Use current project conventions. Prefer installed, relevant Codex skills and tools when available, but do not duplicate them inside this package or claim they were invoked unless they were. Read a reference only when its workflow applies.

## Verify the claim at the right boundary

Choose checks that demonstrate the requested outcome: focused tests, lint/type checks, a platform build, a launched app, or a playable game flow. Do not report source inspection as runtime proof, a successful build as gameplay validation, or a screenshot as evidence for unobserved states. Bind results to the candidate, artifact, platform, and runtime actually checked.

For the domain-specific checks, use [quality and verification](references/quality-and-verification.md). Report what changed, what ran, what was observed, and what remains unverified. Keep `PROPOSED`, `PREPARED`, `EXECUTED`, `VERIFIED`, and `VALIDATED` distinct.
