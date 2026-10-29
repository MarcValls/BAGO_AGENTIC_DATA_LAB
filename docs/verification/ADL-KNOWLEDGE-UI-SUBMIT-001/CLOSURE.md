# Local verification scope

Base fetched before worktree creation and again before publication: bf4ce08b730e4616f3a5caf9e3111b8d8ec1a3e6. The refreshed merge base matched. The earlier audit candidate 19f6a3716f91287c41ced38f4faf1ae7f12cd01d has the same complete Git tree as this base.

- Baseline: both new regressions failed before the patch; desktop submission reloaded the page.
- Fixed candidate: 15 focused frontend cases passed; frontend build passed.
- Desktop: real Codex/gpt-6-luna answer from the attached synthetic source; one knowledge request, zero chat requests, preserved draft, no nested forms, and Escape restored Resources focus at 1920x1080.
- Independent review: static diff review found no new P0/P1 behavior defect. It did not rerun suites or provider calls. Formatting/build-output observations were resolved before publication; native Escape/focus is supported by the separate desktop observation.
- Windows/Python3.14.5: `python scripts/generate_dynamic_readme.py` exited 0 and reported 1661 passing cases. README generation is executed, not inferred from collection.
- `python scripts/generate_dynamic_readme.py --check --skip-tests` exited 0, collecting 1664 cases without executing them in that consistency check.
- `git diff --check` passed. Unrelated generated build artifacts were restored; the generated README content remained canonical.

Platform limitation: Windows/Python3.11 full suite had 1657 passed, 4 failed, 3 skipped and 22 passing subtests. The four failures reproduce in unchanged backend/test sources (matching the base after CRLF normalization); they pass under Python3.14. No backend timing/status repair is included. README_FULL_RUN.json preserves the failing result; PLATFORM_DIFFERENTIAL.json preserves the inspected identities and clock implementations. A passing Python3.14 run must not be presented as a passing Windows/Python3.11 run.

This is a local, bounded repair verification. Consult the PR and its checks for remote synchronization/CI status. It is not production-wide authorization validation, a shared-index isolation proof, or a common execution gateway migration. Temporary QA ports 8085/5199 and the QA browser session were stopped; the existing user preview/backend were preserved during the check.

Evidence packaging: original console output and the Python3.11 failed-run record are JSON-escaped without discarding whitespace. The fixture ZIP preserves the exact source bytes/hash. Human-readable transcripts use LF, and the scoped Git attributes preserve content-addressed evidence bytes across checkouts. The index only verifies attached byte identities, not the truth of a behavioral claim.

## Follow-up: restore Node static rendering

The first published parent 89c6069 failed CI in the existing package-upgrade Node SSR test: the portal accessed document during renderToString(App). This was a regression introduced by the portal change. A typeof-document guard restores the existing non-browser render path while preserving the browser portal branch. The same test failed locally before the guard; the five focused test files now pass 17 cases, and the build passes. SSR_REVIEW.json is a fresh independent static review of the new source hash. SSR_BROWSER_CHECK.json records a separate browser open/close observation. The real-model response and 1661-case local full run above remain evidence for the initial parent, not a new execution on the guard bytes. Final full-suite generation and README consistency for the follow-up must be recorded from its hosted CI before closure. No local full-backend suite was repeated for this one-line frontend-only follow-up.
