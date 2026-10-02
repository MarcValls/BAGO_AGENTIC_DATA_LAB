# Portfolio Demo v1 — CV & LinkedIn copy

**Tag:** `portfolio-demo-v1` (annotated, pushed to `origin`)
**Repo:** https://github.com/MarcValls/BAGO_AGENTIC_DATA_LAB
**Tag URL:** https://github.com/MarcValls/BAGO_AGENTIC_DATA_LAB/releases/tag/portfolio-demo-v1
**Snapshot date:** 2026-10-02
**Status:** L0–L15 VERIFIED (local) · 146/146 tests · 0.0 USD cost · no credentials required

---

## One-line pitch (LinkedIn headline option)

**AI Engineer · governed agents, retrieval and AWS Bedrock · L0–L15 portfolio shipped**

## Short bio (LinkedIn About snippet, ~300 words)

I design and ship **governed** AI systems: agents that propose, but
never execute without an explicit authorization boundary. My portfolio
repo, **BAGO Agentic Data Lab** (`portfolio-demo-v1`), is a complete
L0–L15 reference implementation that proves the recipe works locally,
deterministically, and at zero cost before any cloud call is made.

What is in the snapshot:

- **L1–L4** — LangGraph StateGraph with a typed `AuthorizationBoundary`,
  `Permit` (single-use) and `Receipt` pattern; ETL pipeline with
  provenance; ontology graph; **Governed RAG** with citations and
  metadata gates.
- **L5–L8** — **Governed MCP adapter** (discovery ≠ authority;
  pre-transport WRITE denial proven), **AWS Bedrock `Converse`** via a
  governed adapter with receipts (one live call, model-scoped permits,
  cost estimate), Bedrock KB adapter with offline citations, and a
  **real local OpenMetadata 1.12.6** integration (search, lineage,
  ownership, schema versioning, quality rules).
- **L9–L13** — End-to-end governed agent composing RAG + ontology +
  Bedrock + MCP, **public zero-cost E2E demo** that a reviewer can
  clone and run.
- **L14–L15** — Persistent **SQLite vector store** consumed by
  GovernedRAG, and **OpenTelemetry → local Jaeger** projecting 15 spans
  of the public E2E over OTLP/HTTP and queried through Jaeger's UI.

Hard limits I respect: AWS ConverseStream, Bedrock Knowledge Base live,
remote OpenMetadata and commercetools live are documented as
**NOT_RUN**, and zero-dollar billing for the Bedrock call is
**NOT_PROVEN**. The repo's STATE.md is the source of truth.

Looking to apply this rigor to Tuio (Forward Deployed AI Engineer),
Orbitant (AI Engineer) and Devoteam (GCP AI Engineer / Gemini).

## 5 portfolio highlights (LinkedIn "Featured" copy)

1. **Governed agent architecture** — LangGraph proposes, BAGO
   authorizes, Sandbox executes, LocalTrace audits. Receipts for every
   effect. See `evidence/public_e2e_demo.md` (PASS, eval score 1.00).
2. **Local Bedrock Converse, model-scoped permits** — One live AWS
   Bedrock `Converse` call (`amazon.nova-lite-v1:0`) with bounded
   retries, error taxonomy, local quota and a typed receipt. See
   `evidence/l6_aws_live.md` + `evidence/l6_aws_free_tier.md`.
3. **MCP with real authority boundary** — Discovery ≠ registration ≠
   authorization ≠ execution. A WRITE call is denied before it
   reaches the MCP server. See `evidence/mcp_governed_demo.md` and
   the companion `evidence/mcp_governed_demo.mp4`.
4. **Local OpenMetadata 1.12.6, real Docker** — Search, lineage,
   ownership, schema versioning and quality-rule definitions
   executed against an authenticated local OpenMetadata with
   receipts. See `evidence/l8_openmetadata_live.md`.
5. **OpenTelemetry → Jaeger local live** — 15 spans of the public E2E
   projected over OTLP/HTTP and observed in Jaeger. The trace ID is
   linked back to the BAGO LocalTrace via `bago.trace_id` tag. See
   `evidence/l15_otel_jaeger_live.md`.

## CV bullets (Spanish)

- **AI Engineer (portFOLIO)**: diseñé e implementé BAGO Agentic Data
  Lab (L0–L15, 146/146 tests), un laboratorio reproducible de agentes
  gobernados con LangGraph, RAG, MCP, Bedrock, OpenMetadata,
  vector store local y trazas OpenTelemetry/Jaeger. Snapshot
  público: tag `portfolio-demo-v1`.
- **Arquitectura de autorización**: separación explícita
  *reasoning ↔ execution* con `Permit` de un solo uso, `Receipt`
  auditable y `LocalTrace` ligado a OpenTelemetry. Patrón verificado
  con tests P0 (L1) y extendido a MCP, Bedrock, OpenMetadata, sandbox
  tipado (L11), vector store persistente (L14) y Jaeger local (L15).
- **AWS Bedrock (live, acotado)**: adapter gobernado para
  `Converse` con retries, error taxonomy, quotas locales y
  receipt firmado; un call real verificado (`amazon.nova-lite-v1:0`,
  41 tokens) más una verificación read-only de cuenta AWS `FREE`.
  Límites documentados: `ConverseStream`, Knowledge Base live,
  IAM least-privilege y cargo cero posterior siguen siendo
  `NOT_RUN` / `NOT_PROVEN`.
- **MCP y APIs gobernadas**: adapter con discovery, effect
  classification explícito y denegación pre-transport; demo real
  sobre stdio local con vídeo de evidencia + SHA-256.
- **OpenMetadata 1.12.6 (local live)**: integración con Docker
  local, JWT, lineage, ownership, schema versioning, quality
  rules y receipts; remota sigue siendo `NOT_RUN`.
- **Pipeline de datos y ontología**: ETL con provenance
  determinista, ontology engine local con RDF/Turtle, SPARQL
  acotado, inference, contradiction constraints y gate de
  authority/validity/provenance. Vector store SQLite persistente
  consumido por `GovernedRAG`.
- **Calidad reproducible**: 146/146 tests, public E2E demo
  (`scripts/run_public_e2e_demo.py --check`) PASS, GitHub Actions
  ejecuta tests + demo + vector validation + Jaeger validation +
  compile checks; cero credenciales y 0.0 USD para reproducir.
- **Honestidad técnica**: STATE.md distingue `VERIFIED`, `NOT_RUN`
  y `NOT_PROVEN`; el repo no afirma capacidades remotas no
  demostradas. Tag freeze `portfolio-demo-v1` anota este contrato.

## CV bullets (English)

- Designed and shipped BAGO Agentic Data Lab (L0–L15, 146/146 tests)
  as a reproducible governed-agent reference implementation: LangGraph,
  RAG, MCP, AWS Bedrock, OpenMetadata, persistent local vector store
  and OpenTelemetry/Jaeger traces. Public snapshot at tag
  `portfolio-demo-v1`.
- Enforced an explicit authorization boundary: reasoning proposes,
  permits (single-use) authorize, sandbox executes, local traces
  audit. Verified with P0 tests (L1) and extended to MCP, Bedrock,
  OpenMetadata, a typed sandbox (L11), a persistent vector store
  (L14) and a local Jaeger backend (L15).
- AWS Bedrock (live, bounded): governed `Converse` adapter with
  retries, error taxonomy, local quota and typed receipt. One real
  call verified (`amazon.nova-lite-v1:0`, 41 tokens) plus a
  read-only AWS `FREE` plan check. Documented limits:
  `ConverseStream`, Knowledge Base live, IAM least-privilege and
  zero-dollar post-call billing remain `NOT_RUN` / `NOT_PROVEN`.
- MCP and governed APIs: adapter with discovery, explicit effect
  classification and pre-transport denial; demo over MCP stdio with
  companion evidence video + SHA-256.
- OpenMetadata 1.12.6 (local live): Docker-deployed, JWT-authenticated
  integration with lineage, ownership, schema versioning, quality
  rules and receipts; remote OpenMetadata remains `NOT_RUN`.
- Data pipeline and ontology: deterministic ETL with provenance,
  local ontology engine (RDF/Turtle, bounded SPARQL, inference,
  contradiction constraints) and an authority/validity/provenance
  gate. A persistent SQLite vector store is consumed by
  `GovernedRAG`.
- Reproducible quality: 146/146 tests, public E2E demo PASS,
  GitHub Actions running tests + demo + vector + Jaeger validation +
  compile checks; zero credentials, 0.0 USD to reproduce.
- Technical honesty: STATE.md distinguishes `VERIFIED`, `NOT_RUN`
  and `NOT_PROVEN`; the repo never claims remote capabilities it
  has not demonstrated. The freeze tag `portfolio-demo-v1`
  codifies this contract.

## Skill ↔ evidence map (extract for JOB_SKILL_MATRIX)

| Skill | Evidence |
|---|---|
| Python (Senior) | `src/**/*.py`, `scripts/**/*.py`, deterministic fixtures |
| LangGraph | L1: `src/orchestration/state_graph.py` + `tests/test_l1_governance.py` (7/7 P0) |
| MCP | L5: `src/adapters/mcp_adapter.py` + `evidence/mcp_governed_demo.mp4` |
| AWS Bedrock | L6: `src/adapters/bedrock_provider_adapter.py` + `evidence/l6_aws_live.md` (1 live call) |
| Bedrock Knowledge Base | L7: `src/adapters/bedrock_kb_adapter.py` + `evidence/bedrock_provider_benchmark.md` + `evidence/bago_etl_vs_bedrock_kb_comparison.md` |
| OpenMetadata | L8: `src/adapters/openmetadata_adapter.py` + `evidence/l8_openmetadata_live.md` (Docker local, JWT) |
| Governed RAG | L4 + L14: `src/retrieval/governed_rag.py` + `src/retrieval/sqlite_vector_store.py` |
| Ontology / SPARQL | L3 + L10: `src/metadata/ontology.py` + `src/metadata/ontology_engine.py` |
| ETL | L2: `src/etl/pipeline.py` |
| Sandbox | L11: `src/sandbox/backend.py` + 14 tests |
| Observability | L12 + L15: `src/observability/local_trace.py` + `src/observability/otel_bridge.py` + `evidence/l15_otel_jaeger_live.md` |
| Public demo | L13: `scripts/run_public_e2e_demo.py` + `evidence/public_e2e_demo.md` |
| CI/CD | `.github/workflows/*.yml` (tests + demo + vector + Jaeger + compile) |
| Evaluation | 146/146 tests + `LocalTraceEvaluator` + Jaeger span count |

## LinkedIn "Project" card copy (≤ 3000 chars)

**BAGO Agentic Data Lab — Portfolio Demo v1**
`github.com/MarcValls/BAGO_AGENTIC_DATA_LAB/tree/portfolio-demo-v1`

A governed-agent reference implementation from L0 to L15: 146/146
tests, 0.0 USD cost, no credentials required to reproduce.

What the snapshot proves (locally verified):

- LangGraph StateGraph with an explicit authorization boundary
  (`Permit` single-use, `Receipt` auditable, `LocalTrace` linked).
- Governed MCP adapter: discovery ≠ authority; a WRITE call is
  denied before transport.
- AWS Bedrock `Converse` through a governed adapter with model-scoped
  permits; one live call verified + a read-only AWS `FREE` plan check.
- OpenMetadata 1.12.6 against a local Docker deployment with JWT,
  lineage, ownership, schema versioning and quality rules.
- Local ontology engine (RDF/Turtle + bounded SPARQL + inference +
  contradiction constraints) feeding a Governed RAG backed by a
  persistent SQLite vector store.
- OpenTelemetry → local Jaeger: 15 spans of the public E2E projected
  over OTLP/HTTP and observed in the Jaeger UI.

Hard limits respected: `ConverseStream`, Bedrock Knowledge Base live,
remote OpenMetadata, commercetools live and zero-dollar post-call
billing remain `NOT_RUN` / `NOT_PROVEN`. `STATE.md` is the source of
truth.

Companion demo video: `evidence/portfolio_demo_v1.mp4` (76.5s,
1920×1080, H.264 baseline, SHA-256 verified).

Reproduce:

```bash
python -m pip install -r requirements.txt
python scripts/run_public_e2e_demo.py --check
python scripts/render_portfolio_demo_video.py --check --write-evidence
# Optional Jaeger live:
docker compose -p bago-otel -f infra/observability/docker-compose.yml up -d
python scripts/run_l15_otel_live_validation.py --check
```

## LinkedIn post draft (optional)

> New release: BAGO Agentic Data Lab **Portfolio Demo v1**.
>
> 146/146 tests, 0.0 USD to reproduce, L0–L15 covered:
> LangGraph governed execution · MCP boundary · Bedrock Converse live
> (bounded) · local OpenMetadata 1.12.6 · ontology engine ·
> persistent vector store · OpenTelemetry → Jaeger live.
>
> The whole snapshot is reproducible from a public clone without
> credentials. Cloud claims that I have not demonstrated are
> documented as `NOT_RUN` — STATE.md is the source of truth.
>
> Repo: github.com/MarcValls/BAGO_AGENTIC_DATA_LAB
> Tag: `portfolio-demo-v1`
> Demo video: `evidence/portfolio_demo_v1.mp4`
>
> #AIEngineering #LangGraph #Bedrock #OpenMetadata #OpenTelemetry

## Wave alignment

| Wave | Company | Role | Why this snapshot helps |
|---|---|---|---|
| 1 | Orbitant | AI Engineer | Public repo + 146 tests + governed RAG + cloud adapters |
| 2 | Tuio | Forward Deployed AI Engineer | Bedrock live + RAG + sandbox + observability |
| 3 | Devoteam | GCP AI Engineer (Gemini) | Architecture transfers to Vertex AI; local live OpenMetadata pattern reusable |
| 4 | commercetools | AI Engineer | MCP boundary + governed agent (stretch goal) |

## Sources

- `STATE.md` — canonical state
- `LAB_CONTRACT.md` — laboratory contract
- `ARCHITECTURE.md` — architecture and limits
- `JOB_SKILL_MATRIX.md` — skill ↔ vacancy map
- `LEARNING_LEDGER.md` — phase-by-phase learning
- `evidence/` — receipts, traces and snapshots
- Tag: `portfolio-demo-v1`
- Video: `evidence/portfolio_demo_v1.mp4` (76.5s, SHA-256 in
  `evidence/portfolio_demo_v1.mp4.sha256`)