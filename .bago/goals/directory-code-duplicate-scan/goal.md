# Goal: governed directory duplicate-code scan in ADL

## Objective

Replace the Control station's demo orchestration panel with a real local code-inspection tool. Let users run an exact project-relative source-directory scan for duplicate code, receive deterministic findings with file and line references, and review persisted scan evidence. Keep the same bounded scanner available as a tool to the app assistant and selected ADL agents.

## Acceptance criteria

- Directory access requires explicit per-turn authorization bound to owner, conversation and revision; the scan is read-only and cannot execute code.
- The scanner rejects path escape, skips blocked/sensitive/generated directories and symlinks, and enforces explicit file/byte/finding limits.
- The analyzer detects normalized repeated source blocks across supported source files and structurally matching Python function bodies; its report states the method, limitations, file/line pairs, and a hash-bound manifest.
- Both the app assistant and a selected agent can invoke the analyzer through the existing bounded tool loop.
- The control station exposes a direct opt-in and exact-directory field and shows scan counts and manifest SHA-256 evidence.
- The Control view contains no demo-run controls or demo-orchestration messaging; it scans directly and persists its report, receipt and local trace.
- The capability catalog truthfully lists the connected capability and its limits; existing general Agent Runner remains fail-closed.
- Focused checks, full suite, README regeneration and README check pass; final diff and branch state are inspected.

## Status

`VALIDATED` on the local candidate and active port 8081 runtime.

## Candidate

- Branch: `codex/adl-directory-duplicate-scan-20261013`
- Base: freshly fetched `origin/main` at `ac8bdf1b19f587a5ae553f13e846c7d41e1e507b`
- Candidate HEAD at start: `ac8bdf1b19f587a5ae553f13e846c7d41e1e507b`

## Verification

See `evidence/VERIFICATION.md` for focused/full checks, README generation, live API and served-bundle evidence, and the rendered UI interaction. The working branch remains uncommitted and unpublished.

## Scope note

This replaces the Control view with a real bounded local scanner and exposes the same scanner to agents through chat. It does not enable arbitrary agent jobs, shell execution, code modification, continuous monitoring, or semantic equivalence claims for non-Python languages. Existing demo APIs and test fixtures remain outside the Control view.
