# Local Observability and Evals

L12 adds a zero-cost evidence layer after the existing governed agent and
sandbox boundaries. It does not authorize actions, replace receipts or claim
production telemetry.

```text
AgentRun
  ↓
LocalTraceBuilder
  ↓
workflow + retrieval + tool + permit + execution + sandbox + receipt events
  ↓
LocalTraceEvaluator
  ↓
EvaluationReport
```

## Implemented scope

- `src/observability/local_trace.py` normalizes the existing `AgentRun` trace,
  retrieval citations, proposals, permits, provider/MCP/ontology receipts and
  optional `SandboxExecutionResult` values.
- Events are ordered, linked by parent event IDs and carry evidence references.
- `src/evaluation/local_evals.py` checks workflow coverage, retrieval evidence,
  permit linkage, receipt linkage, absence of unauthorized effects and, when
  requested, sandbox receipt linkage.
- The evaluator is deterministic and scores evidence completeness. It does not
  judge the semantic quality of an LLM answer.
- `scripts/run_l12_observability_evidence.py` executes an injected provider
  fixture plus a typed local pytest request and writes the reproducible receipt
  to `evidence/l12_observability_evals.md`.

## Boundary

The trace is kept in memory and serialized locally as JSON. No OpenTelemetry
collector, external observability SaaS, AWS call or OpenMetadata remote call is
made. The provider is a Bedrock-shaped fixture and the sandbox is the existing
`LocalRestrictedBackend`; OS-level isolation remains outside the claim.

## Reproduce

```bash
python -m pytest tests/test_l12_observability.py -q
python scripts/run_l12_observability_evidence.py
```

`VERIFIED (local)` means that the local trace and evaluator passed against the
fixture and sandbox execution described above. It does not mean production
telemetry, LLM answer-quality benchmarking or a deployed collector.
