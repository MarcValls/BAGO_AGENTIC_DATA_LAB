# Goal: README trust audit

Status: `VALIDATED`

## Objective

Make the generated README distinguish current repository facts, static
inventories, and dated execution evidence without implying that collected tests
passed.

## Candidate

- Repository: `BAGO_AGENTIC_DATA_LAB`
- Branch: `codex/readme-trust-audit-20261015`
- Base: freshly fetched `origin/main` at
  `ff9292fe4340a2bdab9658a2e804579fa4ef8fb0`
- Isolated worktree:
  `C:\Users\AMTEC_Terminal_1º\BAGO_AGENTIC_DATA_LAB_readme_audit_20261015`

## Acceptance criteria

- `--skip-tests` and `--check --skip-tests` report `NOT_RUN` and never create
  a passing badge or passing count.
- Test source inventories are labelled as static counts, not executed checks.
- The latest recorded CI result is linked to its exact run and commit and states
  that it does not cover later changes.
- Stale hard-coded test totals are removed from the README source.
- Local README links and declared artifacts resolve in this candidate.
- Generated README consistency and applicable repository checks pass, or their
  exact unrun/failed status is recorded.

## Evidence

See `evidence/README_AUDIT.md` after final review.
