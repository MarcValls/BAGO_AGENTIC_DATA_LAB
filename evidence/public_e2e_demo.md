# L13 · Bruma Market demo — reproducible local evidence

Generated at: `2026-10-02T16:30:24.709126+00:00`

This is a realistic but entirely fictional client scenario. Bruma Market is an
online retailer whose governed policy refunds the express shipping fee when an
order arrives more than 24 hours late. A QA receipt validates the current rule.
The demo uses deterministic local fixtures; it does not contain real customer
data or contact a live service.

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

- Fictional client: `Bruma Market (cliente ficticio)`
- Scenario: `Pedidos exprés con más de 24 horas de retraso`
- Question: `¿Qué política aplica a los pedidos exprés que llegan con más de 24 horas de retraso y qué evidencia valida la regla?`
- Answer: `Para pedidos exprés con más de 24 horas de retraso, la política vigente devuelve el coste del envío; el acta de QA valida la regla.

Evidence:
- fixtures/bruma-delivery-policy-qa.md#revision=1.0.0
- fixtures/bruma-delivery-policy-v2.md#revision=2.0.0`
- Overall status: `PASS`
- Agent status: `COMPLETED`
- Ontology outcome: `SUCCESS`
- Ontology paths: `2`
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
bash scripts/install_demo.sh
source .venv/bin/activate
python scripts/bago.py demo
python -m pytest tests -q
python scripts/generate_dynamic_readme.py --check --skip-tests
```

The installer creates a local `.venv` and installs the pinned requirements.
`python scripts/bago.py demo` prints a short business-facing result; add
`--json` for the machine-readable summary or `--write-evidence` to refresh this
file.

The generated evidence is intentionally scoped to this local fixture. It does
not promote AWS, remote OpenMetadata, commercetools or production observability
claims to `VALIDATED`.

## Stable summary

```json
{
  "agent_status": "COMPLETED",
  "aws_live": "NOT_RUN",
  "case": "Pedidos exprés con más de 24 horas de retraso",
  "client": "Bruma Market (cliente ficticio)",
  "context_revision": "bruma-market-delivery-v1",
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
    "fixtures/bruma-delivery-policy-qa.md#revision=1.0.0",
    "fixtures/bruma-delivery-policy-v2.md#revision=2.0.0"
  ],
  "ontology_inferred_triples": 2,
  "ontology_outcome": "SUCCESS",
  "ontology_paths": 2,
  "openmetadata_live": "NOT_RUN",
  "query": "¿Qué política aplica a los pedidos exprés que llegan con más de 24 horas de retraso y qué evidencia valida la regla?",
  "retrieval_hits": 2,
  "sandbox_evidence_refs": [
    "sandbox://sbxreceipt-aef2d979aa774814"
  ],
  "sandbox_exit_code": 0,
  "sandbox_profile": "test_runner",
  "sandbox_status": "SUCCESS",
  "scope": "fictional-client-zero-cost-local-e2e",
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
