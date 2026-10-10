# Active handoff

Goal: `.bago/goals/context-unification/goal.md`

Status: `VALIDATED` on the current candidate tree.

Work is bound to branch `codex/bago-context-unification-20261011`, based directly on current `origin/main` `2af091bc8948398d4bc6b44d4cafa1693c86fcb6`. The pre-migration reference snapshot is `.bago/migrations/context-unification-20261011/REFERENCE_SNAPSHOT.md` (263 versioned files, 446 reference lines, 7 ignored generated-context fingerprints).

Verification: full suite `210 passed`; README regeneration and `--check --skip-tests` pass at 210; root and plugin `teamctl verify` pass; three migration JSON files parse; `git diff --check` passes. A fresh fetch confirmed `origin/main` remains `2af091bc8948398d4bc6b44d4cafa1693c86fcb6` and the candidate merge base equals it.

Integrity check: all 163 moved historical evidence, snapshot, runtime, handoff and checksum artifacts match the detached base snapshot byte-for-byte; 67 were restored after path rewriting was detected. Their embedded `.goals/...` paths remain historical provenance and are translated via `MIGRATION_MAP.md`.

The README's skills table explanation now states that the table is rendered from `.bago/canon/JOB_SKILL_MATRIX.md`; a regression assertion rejects the previous contradictory phrase. The branch freshness rule is documented in root `AGENTS.md`, `.bago/INDEX.md`, and the migration map.

Remaining release action: commit/push the validated candidate and set its branch description; do not merge automatically.
