# Goal — One-Command Governed Knowledge Agent Demo v1

**Lifecycle:** PREPARED
**Scope:** close and publish a reproducible one-command demo using existing repository components only. No new architecture or external integrations.

## Ordered workflow

1. Audit current state and record blockers without implementation.
2. Apply only audit-supported minimal fixes.
3. Verify from a clean clone using repository documentation.
4. Update portfolio README/docs with verified behavior only.
5. Run and preserve one canonical demo execution and requested artifacts.
6. Independently check release candidate.
7. Independent critical pass; require P0=0 and P1=0.
8. Freeze v1.0 with version, SHA, notes, outputs, and commands.

## Acceptance criteria

- A1: P1 audit records reproducible blockers, priorities, unchanged components, file scope, minimal sequence, and objective DONE criteria.
- A2: public `python demo.py` command works from repository root with documented installation and no credentials, network, Docker, or paid service.
- A3: one successful run writes `summary.json`, `agent_run.json`, `receipts.json`, `trace.json`, and `evaluation.json` under a documented deterministic output directory.
- A4: all artifacts correspond to the same run; references, trace IDs, receipt IDs and evaluation are consistent.
- A5: existing tests remain passing; new tests cover demo artifact contract and error handling where needed; CI invokes the canonical demo.
- A6: a clean clone can follow public docs on Python 3.11+ (including Windows commands) and reproduce the artifacts without implicit setup.
- A7: README explains problem, verified architecture/flow, command, example, artifacts, governance, stack, tests/CI, limitations, reproduction, and demo observations within recruiter-readable scope.
- A8: canonical demo has input/output, all five artifacts, and 30s/90s/5min explanations.
- A9: release candidate and independent critical audit find zero reproducible P0/P1 blockers.
- A10: v1.0 release notes and verification record bind the frozen artifacts to a Git commit/tag SHA; no in-place changes after freeze.

## Constraints

- Reuse existing public E2E implementation, serializers, trace and evaluator.
- Do not add architecture, subsystems, UI, integrations, or claims.
- Do not reopen VERIFIED features absent regression.
- Keep receipts/evidence scoped to the local deterministic fixture; no new cloud calls.
- Distinguish staged/local release state from pushed/merged state in final reporting.
