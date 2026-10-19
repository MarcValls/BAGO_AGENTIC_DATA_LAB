# ADL / BER integration — final verification snapshot

## Candidate

- ADL worktree: `codex/adl-ber-integration-20261019`, base `585fe4635596b1bd253fb8ba6d5b736ebf133ee9`; working tree remains uncommitted and isolated.
- BAGO source worktree: `codex/ber-embedded-runtime-20261019`, source commit `5fb6f2f0c57f29de1b42bbb2efb4a57c86aa032d`, runtime version `4.11.10`.
- BER artifact SHA-256 (current): `da7960e83bd7dd8b16c7518e8019d52280b381bdf2f2fd4eb71cd74d38650f22`.

## Executed and verified

| Claim | Command or source | Result and scope |
|---|---|---|
| Full ADL regression suite and generated README | `python scripts/generate_dynamic_readme.py` | PASS on 2026-10-19; README generated after **273 tests passed**, including five side-by-side legacy/BER parity cases. |
| Generated README matches canonical sources | `python scripts/generate_dynamic_readme.py --check --skip-tests` | PASS on 2026-10-19; 273 cases collected, tests intentionally `NOT_RUN` by this command. |
| BER client and ADL effect-evidence path | `python -m pytest tests/runtime/ber -q` | PASS; 13 focused tests covering explicit lifecycle, pinned artifact verification, filesystem, typed-process, legacy parity, CLI confirmation, BAGO receipt projection into LocalTrace, and bounded evaluation. |
| Decision Inspector behavior | `npm exec --prefix frontend vitest -- run frontend/tests/ui/decision-inspector` | PASS; 5 files, 30 tests. |
| Frontend build | `npm run build --prefix frontend` | PASS; TypeScript and Vite build, 127 modules transformed. |
| Inspector terminal mission | `.bago/team/runtime/handoffs/W01.json` through `W12.json`; `python .bago/team/kit/scripts/teamctl.py --root . verify` | Mission gate `DONE`; validator PASS with preserved AC01–AC10 orphan warnings. Independent W11 found P0=0 and P1 open=0. |
| BAGO BER profile and gateway tests | BAGO candidate evidence in `evidence/BER_ARTIFACT_AND_ADL_CLIENT_20261019.md` | 107 passed on the BAGO candidate; exact scope is listed in that evidence. |
| Extracted archive smoke | BAGO candidate evidence in `evidence/BER_ARTIFACT_AND_ADL_CLIENT_20261019.md` | PASS for health identity, approved write receipt, replay rejection and shutdown. |

## Remaining acceptance gates

- The interactive CLI now projects executed BER receipts into ADL LocalTrace and a bounded evaluation. That path is **not** wired into the ADL API, browser Inspector input, or Agent Runner.
- Side-by-side semantic parity for read/create/modify, typed Git status, and typed pytest plus the 273-test L0-L15 regression suite are verified on this candidate; scope and limits are recorded in `evidence/COMPATIBILITY_AND_L0_L15_20261019.md` and `docs/ber/COMPATIBILITY_PARITY_MATRIX.md`.
- Docker Linux engine was unavailable at baseline, so clean-machine ADL packaging/standalone validation remains blocked.
- Governed Agent Runner remains fail-closed until compatibility and standalone gates pass.
- `filesystem.delete` remains blocked pending a canonical verified BAGO adapter and world-state revalidation.
- Manual keyboard/screen-reader verification remains `NOT_RUN`; AC01–AC10 remain validator warnings.

## W17 terminal follow-up - supersedes the earlier remaining-gates snapshot

The following checks were rerun on the same final uncommitted candidate after Agent Runner implementation. Earlier statements above that Docker remained unavailable or Agent Runner remained unimplemented describe the preceding checkpoint and are superseded here.

| Claim | Command / evidence | Result |
|---|---|---|
| Complete repository suite and generated README | `python scripts/generate_dynamic_readme.py` | PASS; generated README after **299 tests passed**. |
| Generated README canonical check | `python scripts/generate_dynamic_readme.py --check --skip-tests` | PASS; 299 cases collected, test execution explicitly NOT_RUN by this command. |
| BER Agent Runner adversarial backend | W16 report, `python -m pytest tests/runtime/ber/test_agent_runner.py tests/runtime/ber/test_client.py tests/runtime/ber/test_observability.py tests/test_provider_cognition_repair.py -q` | PASS; 41 passed, existing Python 3.14/Pydantic v1 compatibility warning. |
| WebSocket integration and obsolete-test regression | W16 report, `python -m pytest tests/verification/agent-runner/test_websocket_integration.py tests/test_agent_execution_unavailable.py -q` | PASS; 6 passed using TestClient, fake provider/BER, and malformed-start guard. |
| Agent Runner UI and frontend | `node --test tests/ui/agent-runner/agent-runner.test.mjs`; `npm run test:ui --prefix frontend`; `npm run build --prefix frontend` | PASS; 9 runner tests, 17 UI tests, and TypeScript/Vite build (129 modules). |
| Standalone local image with pinned BER | `.bago/goals/ADL-BER-INTEGRATION-001/evidence/STANDALONE_PACKAGE_SMOKE_20261019.md` W17 section | PASS; local image rebuilt, API health `ok`, UI 200, archive/lock SHA match, approved synthetic write receipt and independent readback. Image ID `sha256:b40f0f38d1cc9cca60351f1ffee15a2c123e65efe1ab4244e23b4c861a8b1acf`. |
| Team handoffs and terminal gate | `.bago/team/runtime/handoffs/W13.json`, `W14.json`, `W15.json`, `W15R.json`, `W16.json`; W17 handoff | PASS; `teamctl verify` validates all current mission handoffs. Existing orphan warnings AC01-AC10 and W01-W12 remain preserved. |

**Residual limits:** live Ollama inference and live Agent Runner execution against BER remain `NOT_RUN`; W16 used deterministic provider/BER fakes. The container smoke exercised the packaged BER demo with an explicit synthetic filesystem write, not the live Agent Runner WebSocket. `filesystem.delete` remains blocked. No publish or deployment occurred. Manual keyboard/screen-reader review remains `NOT_RUN`.
