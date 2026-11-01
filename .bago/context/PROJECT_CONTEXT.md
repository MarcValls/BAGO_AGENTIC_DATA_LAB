# BAGO project context

The authoritative project context entrypoint is `.bago/INDEX.md`. It defines source precedence and the roles of canon, goals, team protocol, runtime evidence, local configuration, traces and generated context.

Root `AGENTS.md`, `.codex/`, `.agents/` and `.github/` remain tool-required entrypoints/adapters; they do not define a competing project canon.

## Current desktop-only decision

Read `.bago/canon/DESKTOP_FIRST.md`: BAGO is desktop first. Do not inspect or test mobile views, enable mobile emulation, or produce mobile manuals/demos until the user explicitly requests it. Current UI acceptance is desktop-only, including worktrees.

## Current chat-first and minimum-friction decision

Read `.bago/canon/INTERACTION_MINIMUM_FRICTION.md`: complete workflows inside the chat without forced window/view changes. Keep operation-specific permission/acceptance/actions in their own message; keep persistent conversation controls at the composer. Detect web links in the human message without another URL text box. This is a requirement to verify, not a claim of implemented coverage.
