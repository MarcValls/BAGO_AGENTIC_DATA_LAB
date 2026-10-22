# W29 Final Independent Verification — 2026-10-18

## Candidate

- Work item: `W29`, role `verification-engineer`.
- Exact candidate HEAD: `83e69c155d0a661065f7e86f33a20a4f866eb982`.
- Branch: `codex/adl-gex-controls-20261018`.
- W28 implementation file `src/execution/ledger/sqlite_ledger.py` SHA-256: `5247c75a0cc4150ea4da86716bc376d0b06c2e3516822756d6f75dd46f489bb5`.
- W29 did not change W28 implementation code. The W28 negative-test evidence was independently reproduced against the exact candidate.

## Independent oracle and adversarial coverage

The verifier holds its own fixed fixture bytes and request canonicalization logic. It captures the raw gateway result and compares those bytes directly to the independently held vector. It does not use the executor's declared hash or success predicate as its oracle. The W18 test in the verification scope was updated to require the current durable terminal verification, observer hash, receipt/event links and result binding; the historical W18 report and handoff were left untouched.

Adversarial coverage includes successful terminal persistence and restart, replay after restart, independent raw fixture observation, wrong/missing/denied output, receipt and request/permit/attempt mismatches, missing or tampered durable receipt/result artifacts, tampered event chain, injected terminal storage failure and restart reconciliation, executor exception after effect, and status/result disagreement across `DENIED`, `FAILURE`, `TIMEOUT`, and `SUCCESS` receipt cases.

The formerly reported P1 was reproduced in the W27 test against its original candidate. On this exact W29 candidate, `persist_terminal_verification` rejects inconsistent status/result pairs before creating terminal rows/events or changing the attempt state. The independent regression confirms no verification can be read back and the durable attempt remains `DISPATCH_INTENT` for reconciliation.

## Verification results

- `python -m pytest -q -p no:cacheprovider tests/verification/governed-execution tests/governed_execution/integration tests/governed_execution/identity tests/governed_execution/permit tests/governed_execution/ledger docs/governed-execution/verification/test_gex_contract_consistency.py tests/test_agent_execution_unavailable.py` — **PASS**, 102 passed; one Python 3.14/Pydantic compatibility warning.
- `python -m py_compile tests/verification/governed-execution/test_w27_independent_terminal_verification.py tests/verification/governed-execution/test_independent_fixture_verification.py` — **PASS**.
- `git diff --check -- tests/verification/governed-execution docs/governed-execution/verification` — **PASS**. Git emitted a line-ending notice for the modified W27 Python test (LF will be converted to CRLF on a future Git touch); no whitespace errors were reported.
- `python .bago/team/kit/scripts/teamctl.py verify` — **PASS**, with pre-existing warnings for orphan handoffs `AC01.json` through `AC10.json`.
- `/ws/agents/run`, `agent.run`, `sandbox.execute`, `mcp.execute` live endpoints/runtime — **NOT_RUN**. The existing unavailable-route regression passed; these capabilities remain `UNAVAILABLE / FAIL_CLOSED`.

## Findings

- **P0: 0.** No unintended dispatch or dangerous authorization/control failure was observed in this bounded library slice.
- **P1: 0.** Receipt status/result disagreement is rejected before persistence and mutation. Missing, altered, uncertain, replayed, denied or mismatched outcomes do not become `VERIFIED_SUCCESS`.
- **P2: 1.** The observer and ledger remain same-host, in-process controls. No external trust anchor, administrator-resistant ledger, or production runtime isolation is established. This remains an explicit deployment limitation; the product routes stay unavailable.

## Verdict

**PASS for W29's bounded acceptance criteria; eligible for W12 review.** This is not a claim that production endpoints are available or validated. W12 must retain the P2 deployment limitation and NOT_RUN runtime state in its final evidence index.
