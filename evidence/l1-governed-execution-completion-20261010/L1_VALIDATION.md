# L1 LangGraph Governed Execution - validation record

**Phase status:** `VALIDATED` within the local scope below
**Implementation commit:** `f19ab7f2e1cebf5118989735227911a712c8cc05`
**Branch:** `codex/l1-governed-execution-completion-20261010`
**Date:** 2026-10-10

## Verified claims

The integrated graph connects governed retrieval, an explicit LangGraph
interrupt/resume gate, a complete request fingerprint, `ExecutionGateway`, a
typed sandbox operation, and receipts. The graph-result `LocalTrace` records
retrieval citations, proposal, approval result, and actual sandbox receipts.

The reproducible demo ran from the implementation commit above. Its transcript
and JSON receipt bundle cover:

1. `SUCCESS`: a workspace file was absent before approval and had the expected
   SHA-256 after a matching approval.
2. `DENIED`: a mismatched fingerprint produced `PERMIT_REQUIRED`; no file was
   created.
3. `PERMIT_REPLAY`: reusing the same permit with the same manager was denied.
4. `PATH_ESCAPE`: an approved path escaping the workspace produced a denial
   receipt; no outside file was created.
5. `TIMEOUT`: a real typed pytest subprocess exceeded its two-second cap and
   returned a `TIMEOUT` receipt. This runner is disabled unless its capability
   is explicitly enabled at graph construction.

`resume_approval` accepts only the actual boolean `True`; the strings `"false"`
and integer `1` fail closed. The final independent review found no P0/P1 for
these bounded claims.

## Validation checks

| Check | Result | Evidence |
|---|---|---|
| Full test suite | `210 passed` | `python scripts/generate_dynamic_readme.py` completed and reported 210 tests; this workflow runs `pytest tests -q` before rendering README |
| Focused L1, integration and sandbox tests | `29 passed` | `.goals/L1-GOVERNED-EXECUTION-COMPLETION-001/evidence/FOCUSED_TESTS.txt` |
| Generated README consistency | `PASS`, 210 tests | `.goals/L1-GOVERNED-EXECUTION-COMPLETION-001/evidence/README_CHECK.txt` |
| Python compile check | `PASS` | `.goals/L1-GOVERNED-EXECUTION-COMPLETION-001/evidence/COMPILEALL.txt` |
| Independent review | `P0=0, P1=0` in declared scope | review of implementation commit `f19ab7f2`; details recorded in goal status |

There is one known warning: Pydantic V1 compatibility support warns on Python
3.14. No test failure was associated with it. The repository BAGO verification
entrypoint was `NOT_RUN` because `.bago/bin/bago.py` is absent in this checkout.

## Limits of this validation

This does not prove authenticated reviewer identity, durable checkpoint or
anti-replay storage across restarts, OS/network isolation, remote MCP or
Bedrock execution, a Jaeger projection for this graph, or a screen-recorded
video. `LocalRestrictedBackend` supplies logical workspace controls. The
replay guarantee is per `SandboxManager` lifetime. The pytest action is an
opt-in local capability and is not an OS sandbox.

Reproduce with `python scripts/run_l1_governed_execution_demo.py`. The demo
receipt bundle and exact run transcript are in this directory.
