# Export, CI, and local capability verification

Date: 2026-10-17
Repository: `BAGO5_ADL`
Base and observed HEAD: `c7b8e2ded64d7f004e82a3a8bfd7891ce9b39490`
Candidate state: modified working tree; no commit, push, merge, or deployment.

## Changes verified

- Agent export returns JSON. The UI names the downloaded file `agents-export.json`; a rendered UI test exercises the button and captures the actual anchor filename.
- The duplicate `GET /api/agents/export` route registration was removed. The remaining route appears once before the parameterized `/api/agents/{agent_id}` route.
- GitHub Actions now sets up Node 22, runs `npm ci`, `npm test`, `npm run test:ui`, and `npm run build` from `frontend/`.
- The clean install initially exposed an incompatible lock entry (`@vitejs/plugin-react@4.7.0` with Vite 8). The React plugin is now on 6.1.2, which supports Vite 8; the lockfile was regenerated without peer-dependency bypass flags.

## Executed checks

| Command or route | Result | Scope |
|---|---|---|
| `npm ci` | PASS; 122 packages installed, audit reported 0 vulnerabilities | Clean lockfile install on local Node 24.15.0 |
| `python -m pytest tests/test_agent_export.py -q` | PASS; 1 passed | JSON content type, exported agent payload, single route registration |
| `npm test` | PASS; 2 passed | Frontend package/runtime tests |
| `npm run test:ui` | PASS; 17 passed | API client and rendered Evaluation Lab/Agent Runner states; export filename regression included |
| `npm run build` | PASS; 121 modules transformed | TypeScript project build and Vite production bundle |
| `python scripts/generate_dynamic_readme.py` | PASS; 250 tests passed | Full Python suite and generated README |
| `python scripts/generate_dynamic_readme.py --check --skip-tests` | PASS; README verified, 250 cases collected | Consistency only; tests NOT_RUN by this check |
| `python -m compileall -q src scripts demo.py` | PASS | Python source/script compilation |
| `python scripts/run_public_e2e_demo.py --check` | PASS | Local deterministic fixture, 7 evaluation checks, 15 trace events; AWS NOT_RUN |
| `python demo.py --no-bootstrap --artifacts-dir demo_output/ci` | PASS | Local fictional-client portfolio demo, fixture provider, 7 checks |
| L1 governed execution demonstration | PASS | Temporary-only; allowed, denied, path escape, timeout, and replay cases |
| L12 observability demonstration | PASS; score 1.0 | 7 checks and 13 local trace events |
| `python scripts/run_sandbox_local_validation.py` | PASS; 6 receipts | Local logical sandbox; evidence refreshed at `evidence/sandbox_local_restricted.md` |
| `python scripts/run_l14_vector_store_validation.py --check` | PASS | 3 rows, 2 eligible, 1 filtered, stable fingerprint after reload |
| `git diff --check` | PASS | No whitespace errors; Git reports existing LF/CRLF normalization warnings |

The UI test was first run before the filename fix and failed with expected `agents-export.zip` versus `agents-export.json`; it passed after the fix. `npm ci` was also run after correcting the incompatible plugin version and completed successfully.

## Explicit limits and NOT_RUN

- OpenMetadata live validation (L8) and Jaeger live validation (L15): NOT_RUN because `docker info` could not connect to the Docker Desktop Linux engine named pipe. Unit and local adapter tests remain included in the passing Python suite.
- AWS/Bedrock, Ollama live calls, remote OpenMetadata, and other cloud/provider calls: NOT_RUN under `.bago/canon/STATE.md` zero-cost rule.
- Hosted GitHub Actions: NOT_RUN; no push was requested. Local clean install, test, and build commands matching the added workflow all passed.
- Frontend lint: NOT_RUN because `frontend/node_modules/.bin/eslint` is absent and ESLint is not declared in the frontend manifest.
- The local runtime is Python 3.14.5 and Node 24.15.0; Python emitted the known Pydantic V1 compatibility warning. The CI workflow pins Node 22 and Python 3.11; those hosted runtimes were not executed here.

## Source fingerprints

SHA-256 at verification time:

```text
.github/workflows/ci.yml 2246fbbc56012c45b187a19542d0f7de02372eb89285e643f603d6f1b9c1adf5
frontend/package.json 14a20024290cb2b081e95845eb763d34aa6c1dba938304085270cef696999bac
frontend/package-lock.json 0cac97de9cb0b6c7c82859716424f25d20403d6866a4047437f64fb64a2e2c64
frontend/src/components/AgentRunner.tsx c1d0a6dfdfe649f1a56e9d4a5c369793504f8173624fa7b5822469c703244766
frontend/tests/ui/agent-evaluation-lab/rendered.test.mjs 1f89cac9a6c02cab195eb180d4e267070648ae59b71bab00a6c67b2c058295e3
src/api/server.py 1787d78c4fe49286b2958025cb6555d684208cded56676568cb315867919f524
tests/test_agent_export.py a98e2d2011d6412e00505d4516e5f0c4a671be35c43a19761e8abf57d4402877
README.md d3fe67c98594716bdcc3552565bff52b0c8118801646f9387acd292094e03953
```
