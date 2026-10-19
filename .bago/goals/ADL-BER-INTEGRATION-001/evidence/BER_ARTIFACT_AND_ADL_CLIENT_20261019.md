# BER artifact and ADL client evidence

## Candidate binding

- ADL worktree: `codex/adl-ber-integration-20261019`, base `585fe4635596b1bd253fb8ba6d5b736ebf133ee9`.
- BAGO worktree: `codex/ber-embedded-runtime-20261019`, base/source commit `5fb6f2f0c57f29de1b42bbb2efb4a57c86aa032d`; `backend/release_version.txt` is `4.11.10`.
- Source BAGO checkout remains untouched; the BER source candidate is the isolated worktree.

## BAGO Embedded Runtime

The generated archive is `runtime/ber/bago-embedded-runtime-0.1.0.zip` and
`runtime/ber/BER.lock.json`. Its current SHA-256 is
`da7960e83bd7dd8b16c7518e8019d52280b381bdf2f2fd4eb71cd74d38650f22`. The
lock binds the selected source commit, source file hashes, effect profile and
protocol. `source_dirty_at_build` is `true`: the isolated source candidate
contains the BER implementation and related gateway/filesystem changes. This
is candidate provenance, not a claim that the original BAGO checkout was
clean or that the archive has a publisher signature.

| Claim | Action / evidence | Result and scope |
|---|---|---|
| BER profile, authorization, filesystem and typed-process tests pass | `python -m pytest tests/test_execution_gateway_v2.py tests/test_execution_envelope.py tests/test_authorization_boundary.py tests/test_execution_operations.py tests/test_embedded_runtime.py tests/test_embedded_filesystem.py tests/test_embedded_process.py tests/test_embedded_authorization.py -q` in BAGO candidate `backend` | `107 passed` on 2026-10-19; candidate source test scope only. |
| Source-derived archive and lock agree | `python scripts/build_embedded_runtime.py` in BAGO candidate `backend` | `PASS`; archive SHA above; source commit matches. |
| Extracted artifact runs without importing BAGO checkout | Manual JSONL smoke launched from a temporary directory with only extracted archive on `PYTHONPATH` | `PASS`: health SHA matched lock; explicit create returned a BAGO receipt; repeated execution returned `ber_challenge_replay`; shutdown clean. |
| ADL verifies and launches pinned BER without auto-start | `python -m pytest tests/runtime/ber -q` in ADL worktree | `13 passed` on 2026-10-19: inert construction, locked identity, create/modify/stale-write, typed process, receipt, replay denial, tamper rejection, and legacy parity. One Python 3.14/Pydantic v1 compatibility warning was emitted. |

The ADL adapter is `src/runtime/ber/client.py`. It verifies the pinned archive,
lock identity, embedded source hashes and safe archive paths before extraction.
Lifecycle is explicit. The child communicates through private stdio; ADL does
not expose BAGO Permit tokens. The existing `/ws/agents/run` route remains
fail-closed and is not connected to this client.

## Inspector mission progress

- W01–W06 handoffs and `teamctl verify` pass; W06 scope was corrected to add
  the repository's actual `frontend/`-prefixed paths while preserving the
  original mission globs.
- W07–W09 were assigned in the `teamctl pair` safe-parallel batch. W10 adds
  explicit write scope for existing frontend contract mirrors so integration
  can reconcile them against frozen source contracts.
- Orphan AC01–AC10 handoffs are pre-existing and preserved; `teamctl verify`
  reports them as warnings.

## Limits and next gates

- Side-by-side parity is recorded in `docs/ber/COMPATIBILITY_PARITY_MATRIX.md`; full L0-L15 regression is tracked in the goal verification evidence.
- Docker build and clean-machine ADL packaging are not verified because the
  Docker Desktop Linux engine was unavailable at baseline. Standalone gate
  remains blocked.
- BER is not yet integrated into Agent Runner; `filesystem.delete` remains
  blocked; provider registration and model authentication remain separate.
- Decision Inspector evidence/trace/action feature work and the mission W12
  terminal gate remain open.
