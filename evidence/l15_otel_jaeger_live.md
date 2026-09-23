# L15 · OpenTelemetry + Jaeger local live validation

Generated at: `2026-09-23T21:53:33.450663+00:00`

This validation projects the existing BAGO `LocalTrace` into OpenTelemetry
spans and verifies that Jaeger receives and indexes the public E2E operations:

```text
public E2E LocalTrace
  → OTLP/HTTP exporter
  → Jaeger all-in-one local Docker service
  → Jaeger query API
  → observed operation evidence
```

## Result

- Status: `PASS`
- Service: `bago-agentic-data-lab`
- Spans projected: `15`
- Spans observed: `15`
- Trace found: `True`
- Operations: `agent.run, authorize, classify_intent, execute, ontology_engine, permit, reason_and_propose, receipt, retrieval, retrieve_context, sandbox_execution, tool_call, verify_and_respond`
- Cost: `0.0 USD`
- AWS live: `NOT_RUN`
- Remote collector: `NOT_RUN`

## Reproduce

```bash
docker compose -p bago-otel -f infra/observability/docker-compose.yml up -d
python scripts/run_l15_otel_live_validation.py --check
python scripts/run_l15_otel_live_validation.py --write-evidence
docker compose -p bago-otel -f infra/observability/docker-compose.yml down
```

## Boundary

The BAGO `LocalTrace` remains the source of evidence and authority. OpenTelemetry
is a projection/transport layer only; it cannot authorize or execute an action.
Jaeger is a local Docker backend, not production telemetry, AWS, SaaS
observability or an external collector validation.

## Stable summary

```json
{
  "aws_live": "NOT_RUN",
  "cost_usd": 0.0,
  "expected_operations": [
    "agent.run",
    "permit",
    "retrieval"
  ],
  "generated_at": "2026-09-23T21:53:33.450663+00:00",
  "jaeger_query": "http://localhost:16686",
  "local_trace_id": "trace-d16d70af70441af0",
  "matching_trace_ids": [
    "945ff487e7d467163ad88d8b03f7cf99"
  ],
  "observed_operations": [
    "agent.run",
    "authorize",
    "classify_intent",
    "execute",
    "ontology_engine",
    "permit",
    "reason_and_propose",
    "receipt",
    "retrieval",
    "retrieve_context",
    "sandbox_execution",
    "tool_call",
    "verify_and_respond"
  ],
  "otlp_endpoint": "http://localhost:4318/v1/traces",
  "public_e2e_status": "PASS",
  "remote_collector": "NOT_RUN",
  "scope": "local-opentelemetry-jaeger-public-e2e",
  "service_name": "bago-agentic-data-lab",
  "spans_observed": 15,
  "spans_projected": 15,
  "status": "PASS",
  "trace_found": true
}
```
