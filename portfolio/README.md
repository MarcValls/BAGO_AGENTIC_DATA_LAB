# BAGO Governed Knowledge Agent — Portfolio Demo

This is the product-facing projection of BAGO Agentic Data Lab. It does not add a
new agent architecture. It reuses the existing verified L0–L15 components and
packages one bounded scenario so a reviewer can execute the governed chain and
inspect its evidence.

For the dated delivery selection, current capability evidence and explicit
exclusions, start with the [Day 1 inventory](day1-inventory/README.md).
Historical live evidence is not a claim that those integrations were rerun in
the latest inventory.

## One command

From a fresh clone with Python 3.11+:

```bash
python demo.py
```

The launcher creates or reuses `.venv`, installs the pinned requirements when
needed, runs the existing Bruma Market governed E2E scenario, and materializes
a local evidence bundle under `demo_output/latest/`.

The demo runtime itself uses deterministic local fixtures and does not require
AWS credentials, a paid model, OpenMetadata, Docker or an external collector.
Installing Python dependencies can require package-index access on a fresh
machine.

## What the reviewer sees

```text
business question
  → GovernedRAG retrieval + citations
  → ontology reasoning over the verified policy/evidence relation
  → GovernedKnowledgeAgent
  → explicit authorization boundary
  → restricted sandbox execution
  → receipts
  → LocalTrace
  → deterministic evaluation
```

The default scenario is intentionally small: Bruma Market is fictional, the
policy data is committed as deterministic fixtures, and the LLM-shaped response
is injected locally. The point of the demo is not answer novelty; it is proving
that retrieval, reasoning, execution and evidence remain linked through the
governed path.

## Evidence bundle

A passing run writes:

```text
demo_output/latest/
├── summary.json
├── agent_run.json
├── receipts.json
├── trace.json
└── evaluation.json
```

- `summary.json` — concise status and gate results.
- `agent_run.json` — query, retrieval, proposals, citations and provider/ontology evidence.
- `receipts.json` — authorization, MCP/provider when present, ontology and sandbox receipts.
- `trace.json` — ordered local evidence graph for the run.
- `evaluation.json` — deterministic governance checks and final score.

The output directory is ignored by Git. Canonical repository evidence remains
under `evidence/`; the portfolio bundle is a per-run projection.

## Reused implementation

No new runtime subsystem is introduced here.

- L4 — `GovernedRAG`: governed retrieval and citations.
- L9 — `GovernedKnowledgeAgent`: end-to-end orchestration and proposals.
- L10 — `OntologyEngine`: RDF/Turtle materialization, bounded SPARQL, inference and receipts.
- L11 — `SandboxManager`: restricted local execution with typed receipts.
- L12 — `LocalTraceBuilder` + `LocalTraceEvaluator`: trace/evidence linkage and deterministic governance evaluation.
- L13 — existing public E2E scenario and CI contract.
- L15 — existing OpenTelemetry projection and local Jaeger validation, optional for the portfolio demo.

The implementation remains in the existing `src/` and `scripts/` modules.
This directory is documentation and packaging only.

## Optional: inspect the trace in Jaeger

The zero-cost portfolio command does not require Docker. To project the same
`LocalTrace` through the already implemented L15 path:

```bash
docker compose -p bago-otel -f infra/observability/docker-compose.yml up -d
python scripts/run_l15_otel_live_validation.py --check
docker compose -p bago-otel -f infra/observability/docker-compose.yml down
```

OpenTelemetry and Jaeger are projections of BAGO evidence; they do not grant
authorization or become execution authority.

## Scope

This demo proves the local governed chain represented by its artifacts and CI.
It does not claim production deployment, live Bedrock Knowledge Base,
`ConverseStream`, remote OpenMetadata or remote observability. Those surfaces
retain the status declared by the lab's canonical `STATE.md` and evidence.

For the engineering history and phase-by-phase validation, see the repository
root `README.md`, `ARCHITECTURE.md`, `STATE.md` and `evidence/`.
