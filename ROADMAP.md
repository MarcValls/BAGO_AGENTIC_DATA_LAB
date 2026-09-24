# BAGO AGENTIC DATA LAB — Roadmap Ejecutable

## Timeline Objetivo

**Inicio:** 2026-09-21  
**L0-L4 (MVP empleable):** 5 semanas → 2026-10-26  
**L0-L7 (Portfolio completo):** 8 semanas → 2026-11-16  
**L0-L9 (Capstone):** 10 semanas → 2026-12-01

## Tiempo real registrado por fase

La columna **Tiempo observado** mide el intervalo entre el commit de cierre de la
fase anterior y el commit de cierre de la fase indicada. Es una métrica
reproducible basada en Git, no una estimación de horas efectivamente trabajadas:
puede incluir pausas, revisión y documentación.

| Fase | Cierre registrado | Tiempo planificado | Tiempo observado | Desviación |
|------|-------------------|--------------------|------------------|------------|
| L0 | 2026-09-21 20:35 | 1 día | 11 s | -23 h 59 min 49 s |
| L1 | 2026-09-21 20:37 | 1 semana | 2 min 20 s | -6 d 23 h 57 min 40 s |
| L2 | 2026-09-21 21:04 | 1 semana | 26 min 28 s | -6 d 23 h 33 min 32 s |
| L3 | 2026-09-22 00:22 | 1 semana | 3 h 17 min 51 s | -6 d 20 h 42 min 09 s |
| L4 | 2026-09-22 01:15 | 1 semana | 53 min 22 s | -6 d 23 h 6 min 38 s |
| L5 | 2026-09-22 01:31 | 1 semana | 15 min 40 s | -6 d 23 h 44 min 20 s |
| L6 | 2026-09-22 02:00 | 1 semana | 29 min 12 s | -6 d 23 h 30 min 48 s |
| L7 | 2026-09-22 02:26 | 1 semana | 25 min 40 s | -6 d 23 h 34 min 20 s |
| L8 | 2026-09-22 02:52 | 1 semana | 26 min 38 s | -6 d 23 h 33 min 22 s |
| L9 | 2026-09-22 03:30 | 2 semanas | 37 min 39 s | -13 d 23 h 22 min 21 s |

**Lectura rápida:** el cierre L0→L9 quedó registrado en **6 h 55 min 1 s**,
frente a las **10 semanas** planificadas. La cifra refleja tiempo transcurrido
entre cierres Git; no debe interpretarse como dedicación neta.

---

## L0 · BASELINE & LAB CONTRACT

**Duración:** 1 día  
**Estado:** EN PROGRESO

### Entregables

- [x] LAB_CONTRACT.md
- [x] ARCHITECTURE.md
- [ ] ROADMAP.md (este documento)
- [ ] LEARNING_LEDGER.md
- [ ] JOB_SKILL_MATRIX.md
- [ ] Repositorio GitHub público inicializado

### Criterios de Aceptación

- [ ] Todos los documentos existen con contenido mínimo viable
- [ ] Repositorio creado en GitHub
- [ ] README.md con propósito y estado del proyecto
- [ ] Licencia definida (MIT recomendada)

### Próximos Pasos

1. Completar este ROADMAP.md
2. Crear LEARNING_LEDGER.md vacío
3. Crear JOB_SKILL_MATRIX.md con las 4 vacantes objetivo
4. Inicializar repo Git y push a GitHub

---

## L1 · LANGGRAPH GOVERNED EXECUTION

**Duración:** 1 semana  
**Fecha objetivo:** 2026-09-28

### Conceptos a Aprender

- StateGraph y state management
- Nodes y edges
- Conditional routing
- Command pattern
- Interrupt/resume
- Checkpointing (durable execution)
- Subgraphs
- Tool calls

### Implementación Mínima

Grafo funcional:
`
START → classify_intent → retrieve_context → reason → propose_action → authorization_gate → execute → verify → END
`

### Restricción Arquitectónica

**LangGraph NO ejecuta directamente efectos materiales gobernados.**

Toda acción material debe convertirse en:
`
ExecutionRequest → AuthorizationBoundary → Permit → ExecutionGateway
`

### Entregables

- [ ] src/orchestration/state_graph.py (implementación completa)
- [ ] 	ests/test_langgraph_governance.py (todos los tests de gobernanza)
- [ ] docs/langgraph_architecture.md (diagramas + decisiones)
- [ ] Evidence: video/demo del grafo ejecutando end-to-end

### Tests Críticos (CRIT)

- [ ] LangGraph intenta ejecutar herramienta directamente → DENY
- [ ] Permit reutilizado → DENY
- [ ] Timeout en node → CONTROLLED_FAILURE + RECEIPT

### Criterios de Validación

- [ ] P0 = 0, P1 = 0
- [ ] Todos los tests pasando
- [ ] Demo grabada funcionando
- [ ] LEARNING_LEDGER.md actualizado con conceptos de LangGraph

---

## L2 · ETL / DATA PIPELINE

**Duración:** 1 semana  
**Fecha objetivo:** 2026-10-05

### Corpus de Ingesta

Documentación pública de BAGO:
- AGENTS.md
- CANON_BAGO_1.0-RC6.md
- Docs de backend/
- Docs de frontend/

### Pipeline a Implementar

`
SOURCE (URLs/files)
  ↓
EXTRACT (HTTP GET, parse HTML/Markdown)
  ↓
NORMALIZE (unified Markdown schema)
  ↓
VALIDATE (schema check, deduplication por content hash)
  ↓
ENRICH (entity extraction, keyword extraction)
  ↓
CHUNK (semantic boundaries, ~500 tokens c/u)
  ↓
METADATA (provenance, version, authority, timestamp)
  ↓
LOAD (FAISS vector store + SQLite metadata)
  ↓
VERIFY (receipt: X chunks ingestados, Y errores)
`

### Features Requeridas

- [ ] Content hashing para idempotencia
- [ ] Versionado de documentos
- [ ] Lineage tracking
- [ ] Error handling con retries
- [ ] Dead-letter queue para fallos persistentes
- [ ] Receipts de ingestión

### Entregables

- [ ] src/etl/pipeline.py
- [ ] src/etl/sources/bago_docs.py
- [ ] 	ests/test_etl_pipeline.py
- [ ] Evidence: logs de ingesta de X documentos, Y chunks

---

## L3 · METADATA & ONTOLOGY

**Duración:** 1 semana  
**Fecha objetivo:** 2026-10-12
**Estado:** ✅ COMPLETE (2026-09-21)

### Entidades a Modelar

`python
class KnowledgeAsset:
    id: str
    title: str
    asset_type: DOCUMENT | CHUNK | CODE | TEST | EVIDENCE
    version: str
    authority: str
    created_at: str
    superseded_by: str | None

class KnowledgeChunk:
    id: str
    asset_id: str
    content_hash: str
    text: str
    start_offset: int
    end_offset: int
    embeddings: dict[str, list[float]]  # multiple embedding models

class Source:
    id: str
    url: str | None
    file_path: str | None
    source_type: WEB | FILE | API | MANUAL
    ingested_at: str

class Revision:
    id: str
    asset_id: str
    revision_number: int
    change_summary: str
    superseded_at: str | None

class Relation:
    subject_id: str
    predicate: DERIVED_FROM | SUPERSEDES | REFERENCES | IMPLEMENTS | VALIDATES | CONTRADICTS | GENERATED_BY | AUTHORIZES | GENERATES | SERVES | REQUIRES | BELONGS_TO
    object_id: str
    confidence: float
`

### Entregables

- [x] src/metadata/schema.py (definición de entidades)
- [x] src/metadata/ontology.py (relaciones y reglas)
- [x] src/metadata/ontology_generator.py (propuestas L1 → L2 → L3 gobernadas)
- [x] tests/test_metadata_schema.py
- [x] tests/test_ontology_generator.py
- [x] Evidence: ontología visualizada (grafo de relaciones)

---

## L4 · GOVERNED RAG

**Duración:** 1 semana  
**Fecha objetivo:** 2026-10-19
**Estado:** ✅ COMPLETE (2026-09-22)

### Pipeline de Retrieval

`
QUERY
  ↓
INTENT (classification: retrieval vs reasoning vs action)
  ↓
METADATA FILTERS (authority >= X, date >= Y, domain in Z)
  ↓
LEXICAL RETRIEVAL (BM25, top-k=50)
  ↓
SEMANTIC RETRIEVAL (embeddings, top-k=50)
  ↓
RERANKING (deterministic baseline, top-k=10)
  ↓
AUTHORITY FILTERING (BAGO governance rules)
  ↓
CONTEXT ASSEMBLY (prompt construction con citations)
  ↓
GENERATION (future provider boundary; not executed by L4)
  ↓
EVIDENCE (claim → chunk → source → revision mapping)
`

### Comparativas a Realizar

- [x] Lexical BM25-like vs semantic hash vs hybrid retrieval
- [x] Top-k variations (10, 25, 50, 100)
- [x] Con reranking vs sin reranking
- [x] Con metadata filters vs sin filters

### Entregables

- [x] src/retrieval/governed_rag.py
- [x] tests/test_retrieval_accuracy.py
- [x] evidence/retrieval_benchmark_results.md
- [x] Evidence: benchmark comparativo con métricas

---

## L5 · MCP (Model Context Protocol)

**Duración:** 1 semana  
**Fecha objetivo:** 2026-10-26  
**🎯 CANDIDATURA Orbitant (~91% fit)**
**Estado:** ✅ VERIFIED (local governed scope, 2026-09-22; video generated)

### Conceptos a Aprender

- MCP servers architecture
- Tools discovery y schemas
- Resources y prompts
- Transport mechanisms
- Capability discovery
- Trust boundaries

### Restricción de Seguridad

**MCP tool discovered ≠ automatic authority**

Debe cumplirse:
`
MCP tool
  → capability descriptor
  → effect classification
  → ExecutionRequest
  → authorization
  → execution
`

### Entregables

- [x] src/adapters/mcp_adapter.py
- [x] MCP server local de ejemplo (scripts/local_mcp_server.py)
- [x] tests/test_mcp_governance.py
- [x] Evidence: ejecución local stdio con receipt gobernado
- [x] Evidence: video mostrando MCP tool call gobernado (evidence/mcp_governed_demo.mp4)

### Demo reproducible

python scripts/run_mcp_demo.py descubre dos tools, registra sus efectos en
BAGO, permite el READ y bloquea el WRITE antes de enviarlo al servidor.

---

## L6 · AWS BEDROCK

**Duración:** 1 semana  
**Fecha objetivo:** 2026-11-02  
**🎯 CANDIDATURA Tuio (~96% fit)**
**Estado:** ✅ VERIFIED (adapter offline + una llamada AWS `Converse` real +
cuenta Free activa observada en API de solo lectura, 2026-09-24;
streaming/Knowledge Base siguen `NOT_RUN` y el cargo cero sigue `NOT_PROVEN`)

### Conceptos a Aprender

- boto3 SDK
- bedrock-runtime client
- Converse API
- IAM roles y policies
- Model identifiers
- Streaming responses
- Tool use con Bedrock
- Timeouts y retries
- Rate limits y quotas
- Error taxonomy
- Cost observability

### Entregables

- [x] src/adapters/bedrock_provider_adapter.py
- [x] tests/test_bedrock_integration.py (10 checks offline, cliente inyectado)
- [x] docs/aws_bedrock_setup.md (IAM, quotas, costes)
- [x] Evidence: benchmark offline de latency/cost por modelo
- [x] Evidence: una llamada AWS real `Converse` con receipt gobernado
- [x] Evidence: estado de cuenta `FREE/ACTIVE`, créditos restantes y Free Tier API
- [ ] Evidence: llamada AWS real `ConverseStream` (separada; `NOT_RUN`)
- [ ] Evidence: registro posterior confirma cargo cero (`NOT_PROVEN`; no se llamó Cost Explorer)

---

## L7 · BEDROCK KNOWLEDGE BASE

**Duración:** 1 semana  
**Fecha objetivo:** 2026-11-09  
**🎯 CANDIDATURA Devoteam (~93% fit)**
**Estado:** ✅ VERIFIED (adapter y comparación offline, 2026-09-22; AWS live `NOT_RUN`)

### Comparativa Explícita

| Dimensión | BAGO ETL Propio | Bedrock KB |
|-----------|-----------------|------------|
| Control | Total | Limitado |
| Customización | Alta | Baja |
| Coste | Variable (infra) | Pay-per-use |
| Vendor lock-in | Bajo | Alto |
| Security surface | Nuestra responsabilidad | Shared responsibility |
| Observability | Completa | Limitada |

### Entregables

- [x] src/adapters/bedrock_kb_adapter.py
- [x] tests/test_bedrock_kb_adapter.py (10 checks offline, cliente inyectado)
- [x] docs/bedrock_knowledge_base.md (Retrieve, citations, ingestion, IAM)
- [x] scripts/compare_bago_etl_vs_bedrock_kb.py
- [x] evidence/bago_etl_vs_bedrock_kb_comparison.md
- [x] Evidence: misma query recuperada/generada por ambos fixtures
- [ ] Evidence: misma query contra Knowledge Base AWS real (NOT_RUN: faltan cuenta, IAM y credenciales)

---

## L8 · METADATA CATALOG (OpenMetadata)

**Duración:** 1 semana  
**Fecha objetivo:** 2026-11-16

**Estado:** ✅ VERIFIED (adapter, gobernanza y evidencia offline + live local,
2026-09-23; OpenMetadata remoto/AWS `NOT_RUN`)

### Features a Integrar

- Catalog search
- Lineage visualization
- Ownership assignment
- Schema versioning
- Quality rules
- Discovery UI

### Entregables

- [x] src/adapters/openmetadata_adapter.py
- [x] tests/test_openmetadata_adapter.py (13 checks offline, cliente inyectado)
- [x] docs/openmetadata_catalog.md
- [x] scripts/generate_l8_catalog_evidence.py
- [x] evidence/l8_openmetadata_catalog.md (search, source → asset → chunk,
  ownership, schema version, quality rule y receipts)
- [x] `infra/openmetadata/docker-compose.yml` (OpenMetadata 1.12.6 local)
- [x] `scripts/run_l8_openmetadata_live_validation.py` (fixture temporal,
  JWT, HTTP real, cleanup gobernado)
- [x] `evidence/l8_openmetadata_live.md` (health, search, lineage,
  ownership, schema, quality y denegación pre-transporte)
- [x] OpenMetadata local running (Docker; migraciones código 0, healthcheck 200)
- [ ] OpenMetadata remoto/AWS (`NOT_RUN`: fuera de la regla de coste 0)

---

## L9 · END-TO-END GOVERNED AGENT

**Duración:** 2 semanas  
**Fecha objetivo:** 2026-12-01  
**🎯 PORTFOLIO COMPLETO PARA TODAS LAS CANDIDATURAS**
**Estado:** ✅ VERIFIED (flujo offline, MCP local y Bedrock fixture, 2026-09-22;
commercetools/AWS live `NOT_RUN`)

### Integración Final

Un agente capaz de:

1. **Investigar**: Recibir pregunta compleja
2. **Recuperar**: RAG gobernado sobre documentación BAGO + fuentes externas
3. **Razonar**: LangGraph orchestration con múltiples pasos
4. **Proponer herramientas**: MCP tools + Bedrock tool use
5. **Ejecutar gobernado**: AuthorizationBoundary + ExecutionGateway
6. **Trazabilidad completa**: Receipts + evidence links

### Escenarios de Demo

1. **Query técnica**: "¿Cómo funciona session_manager en BAGO?"
   - Recupera docs oficiales
   - Responde con citations
   - Ofrece abrir archivos relevantes (gobernado)

2. **Query de implementación**: "Crea un test para workspace_binding"
   - Recupera código existente
   - Genera test scaffold
   - Propone ejecutar test (gobernado)
   - Muestra resultado

3. **Query de arquitectura**: "¿BAGO cumple el canon RC6?"
   - Recupera canon + código actual
   - Compara punto por punto
   - Genera reporte de gaps
   - Crea issues en GitHub (gobernado)

### Entregables

- [x] src/agent/governed_knowledge_agent.py
- [x] tests/test_l9_end_to_end_agent.py (7 checks offline)
- [x] src/context/workspace_binding.py (identity, scope, fingerprint)
- [x] tests/test_workspace_binding.py (6 CRIT P0 contract checks)
- [x] docs/commercetools_capstone.md
- [x] scripts/generate_l9_agent_evidence.py
- [x] evidence/l9_commercetools_agent.md (3 escenarios reproducibles)
- [ ] Video nuevo de las 3 demos (`NOT_RUN`; la evidencia textual/transcript es reproducible)
- [ ] Validación contra APIs reales AWS/commercetools (`NOT_RUN`); GitHub issue #14 creado y verificado bajo autorización humana

---

## L10 · GOVERNED ONTOLOGY ENGINE

**Prioridad:** coste `0` + evidencia pública + skill repetida en ofertas + mejora real de BAGO
**Estado:** ✅ VERIFIED (motor local RDF/SPARQL y recorrido RAG → grafo → LLM fixture, 2026-09-22)

L10 convierte el retrieval de texto en retrieval de relaciones sin elevar la
ontología a autoridad implícita:

```text
RAG chunks + citations
  ↓
RDF materialization
  ↓
SPARQL SELECT + inverse/transitive/symmetric inference
  ↓
constraints: endpoints, evidence, contradictions
  ↓
path + evidence + receipt
  ↓
optional LLM reasoning
```

### Entregables

- [x] `src/metadata/ontology_engine.py`
- [x] RDF/Turtle materialization from the existing L3 graph
- [x] bounded local SPARQL `SELECT` subset with joins, filters and limits
- [x] deterministic inference for supersession, validation, dependency and contradiction paths
- [x] constraint result `CONSTRAINT_VIOLATION` instead of silently returning green
- [x] `GovernedKnowledgeAgent` context integration and ontology receipt
- [x] `tests/test_l10_ontology_engine.py` (4 checks)
- [x] `scripts/generate_l10_ontology_evidence.py`
- [x] `evidence/l10_ontology_engine.md`
- [x] `docs/ontology_engine.md`

### Explicit boundary

The verified scope is a local in-memory graph and a documented SPARQL subset.
The separate OpenMetadata validation is now verified against a real local
Docker deployment; it does not claim a deployed triplestore, AWS live access,
OpenMetadata remote, or a complete W3C SPARQL implementation.

### Orden posterior de trabajo sin coste

1. Demo end-to-end pública reproducible y CI automática.
2. AWS live sólo con créditos/free tier o una necesidad laboral concreta.

---

## L11 · GOVERNED SANDBOX LAYER

**Prioridad:** coste `0` + evidencia pública + secure execution + mejora real de
BAGO
**Estado:** ✅ VERIFIED (backend local restringido, 2026-09-23)

L11 convierte la frontera conceptual `ExecutionGateway` en una frontera
material local:

```text
ExecutionRequest + Permit
  ↓
ExecutionGateway
  ↓
SandboxManager deriva el perfil efectivo
  ↓
LocalRestrictedBackend
  ↓
capability tipada + receipt
```

### Entregables

- [x] `src/sandbox/specification.py` con perfiles y capabilities
- [x] `src/sandbox/filesystem.py` con workspace boundary y path traversal denial
- [x] `src/sandbox/backend.py` con proceso tipado, Git read-only, timeout y entorno filtrado
- [x] `src/sandbox/manager.py` con derivación desde `Permit` y receipts
- [x] `src/execution/gateway.py` como frontera única que exige `SandboxRequest`
- [x] `tests/test_sandbox.py` (14 checks)
- [x] `scripts/run_sandbox_local_validation.py`
- [x] `evidence/sandbox_local_restricted.md`
- [x] `docs/sandbox_manager.md`

### Explicit boundary

La evidencia cubre filesystem, capacidades, requests tipadas, pytest local,
Git allowlisted, timeout, filtrado de entorno y fail-closed. El backend no es
un contenedor ni implementa aislamiento OS de red; `network=allowlist` y
`os_network_isolation=required` producen `DENIED` porque el aislamiento fuerte
queda fuera de este bloque.

### Orden posterior de trabajo sin coste

1. Demo end-to-end pública reproducible y CI automática.
2. Backend OS-level sólo si existe una necesidad verificable y sin presentar
   el backend local como aislamiento fuerte.

---

## L12 · LOCAL OBSERVABILITY AND EVALS

**Prioridad:** coste `0` + evidencia pública + observabilidad/evals repetibles
**Estado:** ✅ VERIFIED (trace local, sandbox receipt y eval determinista,
2026-09-23)

L12 conecta la evidencia que ya producían las fases anteriores sin añadir una
segunda autoridad:

```text
AgentRun
  ↓
LocalTraceBuilder
  ↓
workflow → retrieval → tool → permit → execution → sandbox → receipt
  ↓
LocalTraceEvaluator
  ↓
EvaluationReport
```

### Entregables

- [x] `src/observability/local_trace.py`
- [x] `src/evaluation/local_evals.py`
- [x] `tests/test_l12_observability.py` (5 checks)
- [x] `scripts/run_l12_observability_evidence.py`
- [x] `evidence/l12_observability_evals.md`
- [x] `docs/observability_evals.md`

### Explicit boundary

La evidencia es local, serializable y determinista. Usa un cliente
Bedrock-shaped inyectado y el `LocalRestrictedBackend`; no contacta AWS,
OpenMetadata remoto ni un collector. El evaluador comprueba gobernanza y
completitud de evidencia, no calidad semántica de una respuesta LLM ni
observabilidad productiva.

---

## JOB SKILL MATRIX — Progreso por Fase

| Skill | L0 | L1 | L2 | L3 | L4 | L5 | L6 | L7 | L8 | L9 | L10 |
|-------|----|----|----|----|----|----|----|----|----|----|-----|
| Python | ✅ | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 |
| REST APIs | ✅ | 🟡 | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 |
| LangGraph | ❌ | ✅ | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 |
| MCP | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 |
| RAG | 🟡 | ❌ | ❌ | ❌ | ✅ | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 |
| ETL | ❌ | ❌ | ✅ | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 |
| Metadata/Ontology | ❌ | ❌ | ❌ | ✅ | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | ✅ |
| RDF/SPARQL/Reasoning | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| AWS Bedrock | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | 🟢 | 🟢 | 🟢 | 🟢 |
| Testing/Evals | 🟡 | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 |

✅ = Implemented & Tested  
🟢 = In use / Reinforced  
🟡 = Partial / Basic  
❌ = Not started

---

## Estado Operativo

`yaml
CURRENT_PHASE: L15
COMPLETION: L15 OpenTelemetry projection to local Jaeger and query validation VERIFIED
NEXT_MILESTONE: preserve zero-cost boundary; optionally confirm a later billing record, then validate ConverseStream
BLOCKERS: zero-dollar billing, least-privilege and remaining remote live identities are not closed
P0_ISSUES: 0
P1_ISSUES: 0
TESTS_PASSING: 146/146 (L8 + L9 + L10 + L11 + L12 + L13 + L14 + L15 + README generator contract + workspace binding contract)
EVIDENCE_GENERATED: L6 live Converse + L6 Free Tier account plan + L8 local live + L10 ontology + L11 sandbox + L12 trace/eval + L13 public E2E + L14 vector + L15 OTLP/Jaeger receipts plus prior L9 evidence
LEARNING_ENTRIES: L0-L15
NEXT_ACTION: retain the read-only Free Plan evidence; do not call Cost Explorer under the zero-cost rule; keep streaming, Knowledge Base and remote integrations separately scoped
`

---

**Última actualización:** 2026-09-24
**Próxima revisión:** Al completar cada fase

---

## L13 · PUBLIC E2E DEMO AND CI

**Prioridad:** coste `0` + evidencia pública + ejecución repetible
**Estado:** ✅ VERIFIED para la ruta local y sus gates de CI

### Criterio de cierre

La demo debe poder ejecutarse desde un clon público con `requirements.txt`, sin
credenciales ni servicios externos, y debe recorrer:

```text
RAG → Ontology Engine → injected LLM context
  → typed pytest sandbox → receipt → LocalTrace → deterministic eval
```

### Entregables

- [x] `scripts/run_public_e2e_demo.py --check`
- [x] `tests/test_public_e2e_demo.py` (3 checks)
- [x] `requirements.txt` con versiones fijadas
- [x] `.github/workflows/ci.yml` con suite, README, demo y compile gates
- [x] `docs/public_e2e_demo.md`
- [x] `evidence/public_e2e_demo.md`

### Límite explícito

La CI demuestra la integridad del checkout y de la ruta local. No equivale a
AWS live, OpenMetadata remoto, commercetools live ni observabilidad productiva;
esas integraciones siguen `NOT_RUN`.

---

## L14 · GOVERNED LOCAL VECTOR STORE

**Prioridad:** coste `0` + evidencia pública + vector retrieval persistente
**Estado:** ✅ VERIFIED para SQLite local, metadata gate y reload de GovernedRAG

### Criterio de cierre

El laboratorio debe persistir vectores deterministas junto a la metadata del
chunk, aplicar autoridad/validity/provenance antes del ranking y permitir que
`GovernedRAG` recargue el backend sin perder su fingerprint.

```text
RetrievalChunk + metadata
  → SQLiteVectorStore
  → metadata/authority/validity gate
  → deterministic vector scores
  → GovernedRAG citations
```

### Entregables

- [x] `src/retrieval/sqlite_vector_store.py`
- [x] `src/retrieval/governed_rag.py` con backend semántico persistente opcional
- [x] `tests/test_sqlite_vector_store.py` (4 checks)
- [x] `scripts/run_l14_vector_store_validation.py --check`
- [x] `docs/local_vector_store.md`
- [x] `evidence/l14_vector_store.md`
- [x] `.github/workflows/ci.yml` con validación del vector store local

### Límite explícito

El backend usa SQLite y `HashEmbedding` determinista, sin red ni coste. No es
un vector database distribuido, un servicio de embeddings alojado, un benchmark
ANN ni una afirmación de relevancia productiva. Vector DB remoto y AWS siguen
`NOT_RUN`.

---

## L15 · OPENTELEMETRY + JAEGER LOCAL LIVE

**Prioridad:** coste `0` + evidencia pública + observabilidad live local
**Estado:** ✅ VERIFIED para OTLP/HTTP, Jaeger Docker y query de spans BAGO

### Criterio de cierre

La cadena pública E2E debe poder exportar el `LocalTrace` existente a un
backend de observabilidad local y recuperar el resultado desde una API real,
manteniendo BAGO como autoridad única:

```text
LocalTrace
  → OpenTelemetry parented spans
  → OTLP/HTTP
  → Jaeger all-in-one local
  → query API
  → evidence
```

### Entregables

- [x] `src/observability/otel_bridge.py`
- [x] `tests/test_l15_otel_bridge.py` (3 checks)
- [x] `infra/observability/docker-compose.yml` con Jaeger `1.60.0`
- [x] `scripts/run_l15_otel_live_validation.py --check`
- [x] `docs/otel_jaeger.md`
- [x] `evidence/l15_otel_jaeger_live.md`
- [x] `.github/workflows/ci.yml` con startup, validación y cleanup de Jaeger

### Límite explícito

Jaeger es local y efímero; OpenTelemetry proyecta evidencia ya creada y no
concede permisos ni ejecuta acciones. No es producción, alta disponibilidad,
retención durable, AWS, SaaS ni collector remoto. Esas superficies siguen
`NOT_RUN`.
