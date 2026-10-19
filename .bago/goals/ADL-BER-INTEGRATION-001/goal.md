# ADL / BAGO Embedded Runtime integration

## Objective

Package a minimal, versioned BAGO Embedded Runtime (BER) with ADL so ADL can
perform human-authorized filesystem and typed-process effects without a
separate BAGO Full installation, while BAGO remains the authority for permits,
execution, effect adapters, and receipts. Preserve ADL's existing capabilities
and legacy execution path until parity and standalone gates pass.

## Acceptance gates

1. `CRIT-ADL-PRE-BER-BASELINE-001`: ADL baseline reconciled; tests and frontend
   pass; README is current; Docker passes or has an explicit non-blocking
   exception; Provider Registration and current execution capabilities are
   mapped.
2. `CRIT-BAGO-EMBEDDED-RUNTIME-001`: a minimal source-derived BER artifact has
   a manifest, identity, lifecycle, IPC protocol, and verified read/create/
   modify plus typed-process behavior; stale targets, workspace escapes, and
   Permit replay fail closed.
3. `CRIT-ADL-BER-COMPATIBILITY-001`: BER is integrated without deleting legacy;
   parity and L0-L15 regression pass.
4. `CRIT-ADL-BER-STANDALONE-001`: packaged ADL works on a clean environment
   without BAGO Full and produces receipts, LocalTrace, evaluation, and
   Decision Inspector evidence.
5. `CRIT-ADL-GOVERNED-AGENT-RUN-001`: Agent Runner uses BER only after the
   previous gates pass and reports terminal success only with linked evidence.

`filesystem.delete` is explicitly `BLOCKED` until BAGO has a canonical,
verified adapter and world-state revalidation for that effect.

## Candidate binding

- ADL starting revision: `585fe4635596b1bd253fb8ba6d5b736ebf133ee9`.
- Refreshed `origin/main`: same SHA.
- Implementation worktree: `.worktrees/adl-ber-integration-20261019`.
- BAGO reference checkout: `C:\Users\AMTEC_Terminal_1º\BAGO`, branch
  `publish/worktree-groups-20261003-7f5d47a6`, HEAD
  `5fb6f2f0c57f29de1b42bbb2efb4a57c86aa032d`, dirty; read-only at entry.
- BAGO `release_version.txt`: `4.11.10`.

## Baseline observations

- ADL was clean at entry and remains isolated from the BAGO dirty checkout.
- Reconciled baseline evidence: `evidence/BASELINE_20261019.md`.
- Full README generation/test after aligning the stale semantic-navigation
  expectation with the existing explicit confirmation flow: 260 passed.
- Frontend production build: PASS.
- README check with `--skip-tests`: PASS; 260 tests collected.
- Provider Registration is persisted and secret-safe, but registration does
  not grant live authentication or chat/agent execution. Current capability
  catalog reports `sandbox.execute` and `agent.run` as `UNAVAILABLE`; runner
  behavior remains fail-closed.
- Docker daemon is unavailable because `docker info` cannot connect to the
  Docker Desktop Linux engine. Explicit baseline exception: this does not
  block source-level BER work, but packaging and clean-machine standalone
  gates remain blocked until Docker/package evidence is available.

## Current state

- Phase A / `CRIT-ADL-PRE-BER-BASELINE-001`: `VALIDATED` with the Docker
  exception and limits recorded in baseline evidence.
- BAGO source inventory: `EXECUTED`, dependency closure still `PARTIAL`; see
  `evidence/BAGO_SOURCE_INVENTORY.md`. The ADL preservation map is in
  `evidence/PRESERVATION_MAP.md`.
- A clean BAGO worktree is prepared from the exact suite-pinned 4.11.10 source
  commit; the original dirty BAGO checkout remains untouched.
- BER artifact (`CRIT-BAGO-EMBEDDED-RUNTIME-001`): `VALIDATED` for the declared
  minimum profile using candidate-bound BAGO tests and an extracted-archive
  smoke. ADL now has an interactive CLI route that requires explicit typed
  confirmation for mutating/typed-execute effects and records the BAGO receipt
  into an ADL-owned LocalTrace and bounded effect evaluation.
- ADL integration (`CRIT-ADL-BER-COMPATIBILITY-001`): `IMPLEMENTED` for the
  explicit CLI demonstration route while retaining legacy execution. It is not
  connected to Agent Runner or the browser Inspector, and L0-L15 parity has not
  yet been established.
- Decision Inspector mission `AGENT_DECISION_INSPECTOR_V1`: W01-W12 `DONE`;
  `teamctl verify` passes with the preserved orphan handoff warnings AC01–AC10.
  W11 independently verified unsupported claims, stale evidence, authorization,
  receipts, trace correlations, and run identity binding with P0=0/P1 open=0.
  Manual keyboard and screen-reader review remains `NOT_RUN`.
- Clean-machine standalone/package and governed Agent Runner gates remain
  blocked/pending as stated below.
- No ADL Agent Runner execution is enabled. `filesystem.delete` remains
  `BLOCKED` pending a canonical BAGO adapter and verified world-state
  revalidation.

Inspector mission evidence: `docs/decision-inspector/FINAL_STATUS.md`,
`docs/decision-inspector/verification/W11_INDEPENDENT_VERIFICATION.md`, and
`.bago/team/runtime/handoffs/W12.json`. Its completion does not validate BER
standalone packaging, L0-L15 parity, or Agent Runner integration.

Do not copy BAGO code manually into ADL or remove existing execution owners.

## BER record inspection progress

A separate read-only **BER Effect Record** view now accepts successful JSON output
from `scripts/ber_effect_demo.py`, verifies the pinned BER identity and source-
supplied cross-links, and displays receipt, LocalTrace and evaluation metadata
without converting the record into an AgentRun or showing effect result content.
Candidate-bound focused tests and the frontend build pass; see
`evidence/BER_EFFECT_INSPECTOR_20261019.md`. This advances ADL integration but
does not close compatibility parity, L0-L15, clean standalone packaging, or
governed Agent Runner gates.

## Continuation W18 - live Agent Runner and final package refresh

Date: 2026-10-19. This section supersedes the earlier pending statements above
for standalone packaging and Agent Runner code/live-answer readiness; those
statements describe earlier checkpoints.

- The full protected L0-L15 and repository suite remains verified at 299
  passing tests; frontend build and README checks pass on the uncommitted
  candidate.
- The final local image was rebuilt after the provider-page frontend change.
  API health, UI HTTP 200, pinned BER archive/lock SHA, absence of `bago_core`,
  an approved synthetic write receipt and independent readback all passed.
- A real local Ollama `llama3.2:3b` task passed through the candidate
  Agent Runner and pinned BER startup, returning `task_result` with
  `effect_status=not_started`. The run used an isolated saved agent and
  temporary committed workspace. No cloud credential or project workspace
  was used.
- Governed Agent Runner code, UI, adversarial fake-provider/BER tests, and this
  live no-effect answer path are verified. A real-provider model-generated
  mutating proposal and approve/execute/receipt cycle remains `NOT_RUN`;
  W16 covers those branches with deterministic fakes.
- `filesystem.delete` remains `BLOCKED` until a canonical BAGO adapter and
  world-state revalidation are verified. No publication or deployment occurred.

Evidence: `evidence/LIVE_RUNNER_AND_FINAL_PACKAGE_20261019.md`.

## Acceptance closure

The five stated acceptance gates are `VALIDATED` for the candidate and exact
evidence referenced above: reconciled baseline; pinned source-derived BER with
read/create/modify and typed-process checks; legacy parity plus L0-L15 and full
regression; final standalone package without `bago_core`; and governed Agent
Runner implementation after those gates, with live local provider/BER answer
path and W16 adversarial effect-path checks. Legacy retirement remains
unstarted. The live model-generated mutating Runner path is an explicit
verification limit; `filesystem.delete` remains blocked as required. No
publishing or deployment took place.
