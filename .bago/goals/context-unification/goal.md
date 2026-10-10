# Context unification migration goal

## Objective

Unify BAGO-managed project context in `.bago/` on current `origin/main`, migrate canonical documents, goals, team protocol and runtime, and leave conventional tool entrypoints as explicit adapters. Preserve historical evidence and document the generated context cache still written by the external BAGO scanner.

## Acceptance criteria

- A pre-migration snapshot is bound to current `origin/main` and records tracked-file hashes, path-reference lines and ignored generated-context hashes.
- Canonical docs, all goals, team kit and team runtime live under `.bago/`.
- Root `AGENTS.md` directs agents to `.bago/INDEX.md`; the index defines authority and reading order.
- Runtime code, tests, README generation and coordination use migrated paths.
- Historical runtime receipts remain byte-identical.
- The candidate is created from a freshly fetched remote base, and the remote tip is rechecked before publication.
- Generated README tables describe their source and rendered location consistently; tests guard the wording.
- The full test suite and README consistency check pass against the final candidate.

## Status

`EXECUTED`; verification pending.
