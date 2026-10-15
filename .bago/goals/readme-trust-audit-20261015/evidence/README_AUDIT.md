# README trust audit

## Candidate identity

- Repository: `BAGO_AGENTIC_DATA_LAB`
- Branch: `codex/readme-trust-audit-20261015`
- Base commit: `ff9292fe4340a2bdab9658a2e804579fa4ef8fb0` (freshly fetched
  `origin/main`)
- The candidate is a separate worktree; the original checkout and its local
  changes were preserved.
- Final relevant file hashes:
  - `README.md`: `67d56796b68a04897a54f1e02f02096e1e4e5c59ac31ec70a87e0ed0d4a13f35`
  - `scripts/generate_dynamic_readme.py`:
    `971a7f4a9ffa4246172a85c4e327f868f31a0f3020f151b7e10dad943e3cbf88`
  - `tests/test_dynamic_readme.py`:
    `c332aeaba0073993efd16637a19f20ab05b90d1851f560315927f62686ee6f55`
  - `.bago/canon/STATE.md`:
    `cd3ae49095ba470e1a63e8c89d9520e543160410539f95a926a23c5d049244a9`
  - `.bago/canon/JOB_SKILL_MATRIX.md`:
    `a9d5e59514fe86605fcd0bb48ae694fde0321538ff393e5aac82f037f2cfebae`

## Findings and corrections

1. `--skip-tests` used pytest collection as `passing_tests`, so it could render
   a green `248/248` badge without executing tests. Removed the test badge and
   pass-count row. Both skip-mode messages now say `suite NOT_RUN` and report
   collection only.
2. The phase and file inventories called AST counts of function definitions
   “tests” or “checks.” Replaced those claims in the README with a concise phase
   status table; no static function count is presented as an execution result.
3. Removed the stale `203 test cases` claim and distinguished the historical
   210-test L1 run from the latest recorded CI run.
4. Re-queried GitHub and found a later full CI run than the one in the old
   record. Bound the README to run `38665463586`, commit
   `ff9292fe4340a2bdab9658a2e804579fa4ef8fb0`, and 2026-10-15; its full-suite
   and README-check steps succeeded. The README states that it does not cover
   later changes.
5. Removed the AWS Free Tier live-check command from general reproduction
   steps because the current state declares no additional cloud calls under
   the zero-cost rule.
6. Reduced README from 642 to 158 lines. It now links to the detailed demo,
   evidence, tutorial and canonical project records instead of copying large
   source inventories and planning tables into the landing page.
7. Labeled job-fit percentages as planning estimates in the source links and
   stated that summary dates do not refresh the timestamps of external evidence.

## Verification

- `python scripts/generate_dynamic_readme.py` — exit 0; complete suite passed
  (`248 tests passed`) before README generation.
- `python scripts/generate_dynamic_readme.py --check --skip-tests` — exit 0;
  `README verificado; suite NOT_RUN (248 casos recogidos)`.
- `python -m py_compile scripts/generate_dynamic_readme.py tests/test_dynamic_readme.py`
  — exit 0.
- `git diff --check` — exit 0.
- Manual source audit — 35 Markdown links total; every repository-relative link
  resolves. All declared phase evidence files and all five tutorial artifacts
  exist. No missing manifest assets.
- GitHub REST API reads for latest CI run `38665463586` — `completed` /
  `success`, head `ff9292fe4340a2bdab9658a2e804579fa4ef8fb0`; job steps confirm
  `Run complete test suite` and `Check generated README` both succeeded.

## Scope and remaining limit

The full suite passed locally against this candidate worktree. The latest CI
record is for the base commit, not this audit branch. No commit or push was
made.
