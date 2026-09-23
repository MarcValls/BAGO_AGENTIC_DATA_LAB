# L13 · Public E2E Demo — reproducible local evidence

Generated at: `2026-09-23T03:20:50.871073+00:00`

This is the public clone-and-run path for the BAGO Agentic Data Lab. It uses
only committed code and deterministic local fixtures:

```text
Governed RAG
  → Ontology Engine (RDF/Turtle + bounded SPARQL + inference)
  → injected Bedrock-shaped LLM context
  → LocalRestrictedBackend with typed pytest
  → LocalTraceBuilder
  → LocalTraceEvaluator
```

## Boundary

- Cost: `0.0 USD`
- Credentials: none
- Network: not required by the demo
- AWS live: `NOT_RUN`
- OpenMetadata live: `NOT_RUN`
- LLM transport: injected fixture; no AWS request is made
- Sandbox: `LocalRestrictedBackend`, workspace write scope, network deny
- CI: GitHub Actions runs the same tests, README check, demo check and compile check

## Result

- Overall status: `PASS`
- Agent status: `COMPLETED`
- Ontology outcome: `SUCCESS`
- Ontology paths: `4`
- Inferred triples: `2`
- Contradictions: `0`
- Sandbox status: `SUCCESS`
- Sandbox exit code: `0`
- Trace events: `15`
- Evaluation: `PASS` (`1.00`)

| Check | Status | Detail |
|---|---|---|
| `trace_root` | PASS | agent.run root is present |
| `workflow_coverage` | PASS | all governed workflow stages are present |
| `retrieval_evidence` | PASS | retrieval hits are linked to citations |
| `permit_linkage` | PASS | tool requests retain authorization linkage |
| `receipt_linkage` | PASS | executions and receipts are linked to evidence |
| `no_unauthorized_effect` | PASS | denied or pending tools have no material call |
| `sandbox_receipt` | PASS | sandbox execution is linked to a receipt |

## Reproduce from a public clone

```bash
python -m pip install -r requirements.txt
python scripts/run_public_e2e_demo.py --check
python -m pytest tests -q
python scripts/generate_dynamic_readme.py --check --skip-tests
```

The generated evidence is intentionally scoped to this local fixture. It does
not promote AWS, remote OpenMetadata, commercetools or production observability
claims to `VALIDATED`.

## Stable summary

```json
{
  "agent_status": "COMPLETED",
  "aws_live": "NOT_RUN",
  "context_revision": "public-e2e-v1",
  "cost_usd": 0.0,
  "evaluation_checks": [
    {
      "name": "trace_root",
      "passed": true
    },
    {
      "name": "workflow_coverage",
      "passed": true
    },
    {
      "name": "retrieval_evidence",
      "passed": true
    },
    {
      "name": "permit_linkage",
      "passed": true
    },
    {
      "name": "receipt_linkage",
      "passed": true
    },
    {
      "name": "no_unauthorized_effect",
      "passed": true
    },
    {
      "name": "sandbox_receipt",
      "passed": true
    }
  ],
  "evaluation_score": 1.0,
  "evaluation_status": "PASS",
  "fixture_calls": 1,
  "model": "fixture.public-e2e",
  "ontology_contradictions": 0,
  "ontology_evidence_refs": [
    "fixtures/public-policy-receipt.md#revision=1.0.0",
    "fixtures/public-policy-v1.md#revision=1.0.0",
    "fixtures/public-policy-v2.md#revision=2.0.0"
  ],
  "ontology_inferred_triples": 2,
  "ontology_outcome": "SUCCESS",
  "ontology_paths": 4,
  "openmetadata_live": "NOT_RUN",
  "query": "¿Qué sustituye a la política anterior y qué evidencia la valida?",
  "retrieval_hits": 2,
  "sandbox_evidence_refs": [
    "sandbox://sbxreceipt-f8856b48f91542ec"
  ],
  "sandbox_exit_code": 0,
  "sandbox_profile": "test_runner",
  "sandbox_status": "SUCCESS",
  "scope": "public-zero-cost-local-e2e",
  "status": "PASS",
  "trace_event_names": [
    "agent.run",
    "classify_intent",
    "retrieve_context",
    "ontology_engine",
    "reason_and_propose",
    "authorize",
    "execute",
    "verify_and_respond",
    "retrieval",
    "tool_call",
    "permit",
    "receipt",
    "receipt",
    "sandbox_execution",
    "receipt"
  ],
  "trace_events": 15
}
```
