# L15 · Jaeger capture attempt during portfolio-demo-v1 freeze

Generated at: `2026-10-02T22:14:00Z`
Tag: `portfolio-demo-v1`

## Attempt summary

| Step | Result | Detail |
|---|---|---|
| `docker info` | FAIL | `failed to connect to the docker API at npipe:////./pipe/docker_engine` |
| `Get-Service com.docker.service` | REPORTED Running | Service control manager reports Running, no `dockerd`/`Docker Desktop` processes are actually alive |
| `docker context use default` | OK | Switched to `npipe:////./pipe/docker_engine`; same failure |
| `docker compose -p bago-otel -f infra/observability/docker-compose.yml up -d` | FAIL | Docker daemon unreachable |

## Root cause

The Windows service `com.docker.service` is in `Running` state per
PowerShell, but no `dockerd` / `com.docker.backend` / `Docker Desktop`
process is actually alive, so the named pipe is not exposed. This is
a host-side Docker Desktop limitation, not a BAGO fault.

## Fallback applied (per goal D2)

Per `goal.md` D2, the freeze falls back to the in-tree, inmutable L15
evidence file:

- `evidence/l15_otel_jaeger_live.md` — already VERIFIED with
  `spans_projected=15`, `spans_observed=15`, `trace_found=true`,
  `local_trace_id=trace-d16d70af70441af0`,
  `matching_trace_ids=["945ff487e7d467163ad88d8b03f7cf99"]`,
  `service_name=bago-agentic-data-lab`,
  `jaeger_query=http://localhost:16686`,
  `otlp_endpoint=http://localhost:4318/v1/traces`,
  `cost_usd=0.0`, `aws_live=NOT_RUN`,
  `remote_collector=NOT_RUN`.
- 13 operations observed: `agent.run`, `authorize`,
  `classify_intent`, `execute`, `ontology_engine`, `permit`,
  `reason_and_propose`, `receipt`, `retrieval`,
  `retrieve_context`, `sandbox_execution`, `tool_call`,
  `verify_and_respond`.

## CV/LinkedIn implication

The portfolio demo v1 video (`evidence/portfolio_demo_v1.mp4`)
references the L15 evidence that is already on disk. A reviewer who
clones the repo and runs `docker compose -f infra/observability/docker-compose.yml up -d`
plus `python scripts/run_l15_otel_live_validation.py --check` can
reproduce the live trace and view it in Jaeger at
`http://localhost:16686`. The freeze snapshot itself does not
require Docker to be available right now.

## Closure

- D1: NOT_RUN (Docker daemon not available during freeze)
- D2: PASS (in-tree L15 evidence retained as the canonical source)