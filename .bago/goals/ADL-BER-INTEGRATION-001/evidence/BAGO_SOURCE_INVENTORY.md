# BAGO source inventory for BER

## Candidate and authority

- Reference checkout: `C:\Users\AMTEC_Terminal_1º\BAGO`.
- Checkout branch and HEAD at inspection: `publish/worktree-groups-20261003-7f5d47a6`, `5fb6f2f0c57f29de1b42bbb2efb4a57c86aa032d`.
- `release_version.txt`: `4.11.10`.
- The Codex suite's BAGO 4.11.10 source-bundle guide also pins commit
  `5fb6f2f0c57f29de1b42bbb2efb4a57c86aa032d`.
- The repository tag `v4.11.10` resolves to `ad2a56336632ca8186ed19819dd108b479bfbc9d`, a different commit. This task binds to the suite source-bundle commit, not the similarly named tag.
- The reference worktree is dirty in `.bago/bin/bago.py` and backend context/docs/tests. `backend/.bago/core` has no working-tree changes. No files in the BAGO checkout were edited.
- Fetched `origin/main` at `f3804a7e9333607561d28fd5075569e725aa0bb0` before preparing the isolated candidate. The BER worktree is clean at the exact pinned source commit `5fb6f2f0c57f29de1b42bbb2efb4a57c86aa032d` on `codex/ber-embedded-runtime-20261019`; the original dirty checkout is untouched. The pinned commit is the version-bundle source and remains the implementation base.
- BAGO root has no `.bago/INDEX.md`; its `AGENTS.md` and version-pinned suite runtime guide are the available authority records. `releases/INDEX.md` is limited to releases.

## Search results

- No `backend/bago_core/embedded/` package or BER implementation exists at the pinned source tree (`git ls-tree` returned no entries; bounded search under `backend/.bago/core`, `backend/bago_core`, `backend/docs/contracts`, and `backend/tests` found no BER runtime).
- The current gateway uses flat absolute imports and imports dozens of BAGO Full adapters at module import time. `ExecutionGateway` accepts an injected `EffectAdapterRegistry`, but its default registry is built from the full adapter set.
- Current relevant core modules are `authorization_boundary.py`, `execution_request.py`, `execution_gateway.py`, `execution_claims.py`, `effect_registry.py`, `execution_adapter_contract.py`, `world_state_snapshot.py`, `execution_envelope.py`, and `runtime_observability.py`.
- The existing process adapter declares `process.execute`, `process.inspect`, and `process.terminate`; the BER profile must exclude termination and expose only reviewed typed operations.
- Existing filesystem adapters expose `filesystem.read` and `filesystem.write`. The write path currently uses `write_file_effect` and returns a receipt, but the inspected implementation does not expose the required BER preconditions `expected_exists` plus prior digest for modification. BER must bind those conditions and revalidate target state at dispatch.
- Gateway, authorization, claims, effect-registry, world-state, filesystem and process transitive dependency closure remains `PARTIAL`; a bounded import/dependency audit and contract review must finish before implementation.

## Consequences for the next phase

- Derive from the pinned source commit and record blob hashes; do not copy files manually into ADL.
- Keep the existing BAGO Full default gateway behavior. Add a separate explicit BER composition/profile and lazy or injected adapter loading only if dependency analysis and regression tests support it.
- Treat `filesystem.delete` as `BLOCKED`; no delete adapter is registered in the inspected gateway, and no delete capability will be added to BER.
- The isolated BAGO worktree is prepared. Continue to verify its exact commit and clean state before material edits.
- Do not claim BER exists, is runnable, or is verified until its source-derived artifact, manifest, protocol, lifecycle and negative security checks are implemented and pass.
