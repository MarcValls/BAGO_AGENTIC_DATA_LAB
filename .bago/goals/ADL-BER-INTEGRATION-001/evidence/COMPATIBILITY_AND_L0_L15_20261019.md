# BER compatibility and L0-L15 verification

## Candidate identity

- ADL worktree: `codex/adl-ber-integration-20261019`, HEAD/base `585fe4635596b1bd253fb8ba6d5b736ebf133ee9` plus the current uncommitted goal candidate.
- BAGO BER source worktree: `codex/ber-embedded-runtime-20261019`, source commit `5fb6f2f0c57f29de1b42bbb2efb4a57c86aa032d`, dirty at archive build.
- ADL archive: `runtime/ber/bago-embedded-runtime-0.1.0.zip`, SHA-256 `da7960e83bd7dd8b16c7518e8019d52280b381bdf2f2fd4eb71cd74d38650f22`; `BER.lock.json` binds the same value.

## Compatibility route

`docs/ber/COMPATIBILITY_PARITY_MATRIX.md` maps the legacy `SandboxManager`
route and packaged BER route across read, create, modify, typed Git status,
and typed pytest execution. The parity tests create equivalent isolated
temporary workspaces and compare observable outcomes. Receipt IDs and
authorization owners remain intentionally distinct because ADL legacy owns
the old sandbox receipts and BAGO owns BER authorization and receipts.

| Action | Command | Result |
|---|---|---|
| Run legacy/BER side-by-side parity | `python -m pytest tests/runtime/ber/test_legacy_parity.py -q` in ADL worktree | `5 passed`; reads, creates, modifies, Git status, and pytest outcomes matched. |
| Run ADL BER runtime checks | `python -m pytest tests/runtime/ber -q` in ADL worktree | `13 passed`; includes parity, artifact lock, lifecycle, authorization, receipts, replay rejection, and tamper checks. One Python 3.14/Pydantic v1 warning. |
| Run BAGO source profile/gateway checks | `python -m pytest tests/test_execution_gateway_v2.py tests/test_execution_envelope.py tests/test_authorization_boundary.py tests/test_execution_operations.py tests/test_embedded_runtime.py tests/test_embedded_filesystem.py tests/test_embedded_process.py tests/test_embedded_authorization.py -q` in BAGO `backend` | `107 passed`; includes the Windows-scoped APPDATA pytest discovery fix and environment isolation regression. |

The compatibility adapter changes only Windows newline representation for
legacy text writes before BER prepare; it does not authorize, dispatch, or
issue receipts. `filesystem.delete` remains blocked and `process.terminate`
is not exposed.

## Protected regression

The protected behavior map is in `docs/ber/COMPATIBILITY_PARITY_MATRIX.md`.
It identifies focused canonical test files for L0-L15 and the non-level
capabilities Provider Registration/Ollama, Agent Chat, Conversation Library,
Decision Inspector, Agent Runner fail-closed behavior, and Docker packaging.

The required full-suite and README generation completed successfully:

- `python scripts/generate_dynamic_readme.py` -> PASS, README generated after **273 tests passed**.
- `python scripts/generate_dynamic_readme.py --check --skip-tests` -> PASS, README matches canonical sources; 273 tests collected and intentionally NOT_RUN by this check.
- `git diff --check` -> PASS; Git emitted only existing line-ending conversion warnings for tracked files.

This verifies the full suite and protected L0-L15 regression surface on this
ADL candidate. The matrix is a test-to-capability map; it does not imply that
every platform-level external condition, package image, or clean-machine
deployment has been verified.

## Separate open gates

- Clean-machine standalone package behavior: `NOT_RUN`. A fresh `docker info`
  probe in this continuation reached Docker Desktop's client but failed to
  connect to `dockerDesktopLinuxEngine` because its named pipe is absent
  (exit code 1). The package build and clean-machine run were therefore not
  attempted; this phase remains blocked.
- Agent Runner: remains fail-closed pending the standalone/package gate and
  remaining explicit acceptance checks.
- Publishing and deployment: `NOT_RUN` and not part of this goal.
