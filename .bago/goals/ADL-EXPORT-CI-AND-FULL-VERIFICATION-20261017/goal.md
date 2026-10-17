# Goal: Agent export contract and frontend CI coverage

## Objective
Make the agent export format truthful end to end, remove duplicate route registration, run frontend UI tests and production build in CI, and execute all feasible local repository checks.

## Acceptance criteria
1. `GET /api/agents/export` returns the existing JSON export contract, and the UI downloads it with a `.json` filename.
2. Only one export route is registered; API coverage verifies status, content type, and exported records.
3. CI installs the locked frontend dependencies and runs UI tests plus the production build.
4. Full Python suite, README generation/check, frontend checks, and applicable local CI validations are executed on the final snapshot.
5. No cloud/provider calls, commit, push, merge, or deployment.

## Capability demonstration routes
- Agent export: seed one temporary agent record, GET `/api/agents/export`, inspect JSON content and `application/json`, then verify UI filename is `agents-export.json`.
- Frontend CI: run `npm ci`, `npm run test:ui`, and `npm run build` in `frontend/`; the same commands are wired into GitHub Actions.
- Repository checks: run the documented full test suite and local demo/validation commands. Cloud-backed checks remain `NOT_RUN` under the zero-cost canon.

## Baseline
- Base commit: `c7b8e2ded64d7f004e82a3a8bfd7891ce9b39490` on `main`.
- Existing working tree already contained unrelated and Agent Evaluation Lab changes; they are preserved.
- `GET /api/agents/export` is currently declared twice at `src/api/server.py` lines 1626 and 2025; the first declaration precedes `/api/agents/{agent_id}` and currently wins routing.
- Frontend export names the response `agents-export.zip` although the API returns a JSON object.
- `.github/workflows/ci.yml` has no Node setup, npm install, frontend tests, or frontend build.
- No `project_baseline.py`, `run_checks.py`, or `verify_change.py` helper exists in this checkout; this record captures the baseline facts directly.

## Final status
`VERIFIED` for agent export and the local, zero-cost application/repository checks listed in `evidence/VERIFICATION_20261017.md`. Docker-backed live services and cloud/provider routes remain `NOT_RUN` for the recorded environment and project cost boundary; hosted GitHub Actions was not triggered.
