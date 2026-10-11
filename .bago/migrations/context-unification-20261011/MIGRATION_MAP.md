# Path mapping and migration boundary

Baseline snapshot: `REFERENCE_SNAPSHOT.md`, captured from `origin/main` at `2af091bc8948398d4bc6b44d4cafa1693c86fcb6` before migration.

| Before | After | Treatment |
|---|---|---|
| `.goals/<id>/` | `.bago/goals/<id>/` | Migrated, including goals added on current `main`. Goal evidence/runtime content retained. |
| `.codex-team-kit/` | `.bago/team/kit/` | Migrated; canonical executable path and instructions updated. |
| `.codex-team/` | `.bago/team/runtime/` | Migrated; API and team monitor use the new location. |
| Root canonical Markdown documents | `.bago/canon/` | Migrated; ETL, ontology, README generation and documentation paths updated. |
| `.gabo/context/` | remains externally generated | Seven ignored files were fingerprinted. The BAGO installation owns this writer; `.bago/context/GENERATED_CONTEXT.md` documents it as a disposable retrieval cache. |
| root `AGENTS.md`, `.codex/`, `.agents/`, `.github/` | remain tool entrypoints/adapters | Direct project context to `.bago/`; retain conventional tool locations. |

Historical evidence, source snapshots, runtime events/states, drafts, handoffs and checksum manifests were checked against the captured base: all 163 matching artifacts are byte-identical; 67 moved artifacts were restored after an initial path-rewrite pass touched their payloads. Embedded legacy paths in these retained records are provenance; map `.goals/<id>/...` to `.bago/goals/<id>/...` when locating the artifact, but do not edit the recorded payload. Current instructions, goals and status metadata use the new location. The plugin's teamctl entrypoint delegates to `.bago/team/kit/scripts/teamctl.py` so the controller implementation has one source.

## Base-branch freshness control

The repeated stale-base failure is addressed in root `AGENTS.md` and `.bago/INDEX.md`: fetch and record the remote base SHA immediately before worktree creation, branch from that fetched ref, then fetch and confirm the candidate contains the refreshed tip before publishing. This candidate was created from `origin/main` at `2af091bc8948398d4bc6b44d4cafa1693c86fcb6`; a later `git fetch origin main` returned the same SHA, and `git merge-base HEAD origin/main` matched it.

The local base was deliberately not used. The previous branch based on the older project branch remains a separate recoverable backup and is not part of this candidate.
