# Goal — OpenMetadata #28860 local reproduction and governed adapter validation

**Status:** VERIFIED — PR #36 merged; no release
**Authorization:** Marc Valls authorized a disposable local OpenMetadata `1.12.10` run and a minimal adapter change if evidence warranted it.
**Track:** `real-world/openmetadata-28860-v1.1`, based on frozen `v1.0.0` commit `b584235ecfdbc2ecb1c3d601ce40fb4f973ff2e8`.

## Objective

Reproduce the core missing-dataset/no-lineage behavior described in issue #28860 against the version-matched local OpenLineage REST API, determine actual response and persisted state, and expose zero-edge 2xx responses through the existing BAGO authorization/receipt boundary.

## Authorized scope

- Read-only inspection of other repositories/directories and public issue/source/docs.
- Disposable local OpenMetadata `1.12.10` using isolated Compose project, ports, network, and data; preserve the existing Data Lab `1.12.6` stack.
- The smallest adapter, unit-test, and goal-evidence changes on a new post-v1.0.0 branch needed for a governed OpenLineage event and independent state verification.
- Local tests and removal of temporary runtime resources after the run.

## Not authorized / non-goals

- Any edit to frozen `v1.0.0` commit/tag/assets or its tracked source.
- OpenMetadata server changes or claims that an upstream fix was implemented.
- New architecture/subsystems, AWS/cloud, commercetools, or remote OpenMetadata calls.
- External OpenMetadata issue activity, tag, merge, or release without a separate decision. Marc Valls separately authorized local commits and push/opening a PR in this BAGO repository.
- Claiming exact reproduction of the issue's request: its body lacks a complete event/URL/FQN fixture, and the title route differs from the version-matched event route.

## Acceptance criteria and result

- Confirm issue state, version, and available request details — **PASS; exact event fixture unavailable**.
- Confirm the version-matched event endpoint and distinguish it from generic lineage — **PASS** (`POST /api/v1/openlineage/lineage`; generic `/api/v1/lineage` is not the OpenLineage event route).
- Run a disposable local `1.12.10` event case and verify HTTP response, entity state, and lineage state — **PASS for the core behavior**; HTTP 200 with zero edges, absent tables verified by 404; the exact public request is not claimed as reproduced.
- Validate a positive control with pre-existing tables and independently read back an OpenLineage edge — **PASS**.
- Add the minimal governed adapter operation; make zero-edge 2xx responses visible as `PARTIAL`; validate event shape, permit, and response count — **PASS**.
- Verify on Python 3.11 CI runtime and full suite — **PASS: 27 targeted, 162 full**. GitHub Actions for the latest PR commit: full-suite verify and README consistency checks **PASS**. Python 3.14 full suite: **162 passed**, 5 compatibility/deprecation warnings.
- Record evidence and cleanup, preserving v1.0.0 — **PASS**; evidence is under `.bago/goals/openmetadata-lineage-28860/evidence/`; isolated Compose resources were removed and follow-up entity reads returned 404.

## Final boundary

The test reproduced a server-side table auto-create failure (`updatedAt` null) in the controlled 1.12.10 scenario; this BAGO change only provides governed event submission and reports zero-edge outcomes. The adapter and tests were committed as `14ab65f97fa90bc7d12387748ac98ff821f12654`; generated README test metrics were refreshed in `85007a1da4871670e8aa06a661e3056652a776a0`. PR [#36](https://github.com/MarcValls/BAGO_AGENTIC_DATA_LAB/pull/36) is now reported as merged at `c2a7768e15da59e57aae132c0aac492c63de5a64`, attributed by GitHub to `MarcValls` at 2026-10-03 12:28:36Z. The assistant did not execute the merge; prior explicit authorization covered push and PR creation, not merge. The remote `v1.0.0` tag still peels to `b584235ecfdbc2ecb1c3d601ce40fb4f973ff2e8`. No release, server fix, or external issue activity is claimed.
