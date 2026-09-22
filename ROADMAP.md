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
| L2 | 2026-09-21 20:54 | 1 semana | 16 min 39 s | -6 d 23 h 43 min 21 s |
| L3 | 2026-09-22 00:22 | 1 semana | 3 h 27 min 40 s | -6 d 20 h 32 min 20 s |
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
**Estado:** ✅ VERIFIED (adapter gobernado offline, 2026-09-22; AWS live `NOT_RUN`)

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
- [ ] Evidence: llamada AWS real `Converse`/`ConverseStream` (NOT_RUN: faltan credenciales y acceso de cuenta)

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

**Estado:** ✅ VERIFIED (adapter, gobernanza y evidencia offline, 2026-09-22;
OpenMetadata/Docker live `NOT_RUN`)

### Features a Integrar

- Catalog search
- Lineage visualization
- Ownership assignment
- Schema versioning
- Quality rules
- Discovery UI

### Entregables

- [x] src/adapters/openmetadata_adapter.py
- [x] tests/test_openmetadata_adapter.py (12 checks offline, cliente inyectado)
- [x] docs/openmetadata_catalog.md
- [x] scripts/generate_l8_catalog_evidence.py
- [x] evidence/l8_openmetadata_catalog.md (search, source → asset → chunk,
  ownership, schema version, quality rule y receipts)
- [ ] OpenMetadata local running (Docker) (`NOT_RUN`: docker no está instalado)
- [ ] Evidence: misma validación contra servidor OpenMetadata real (`NOT_RUN`)

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

## JOB SKILL MATRIX — Progreso por Fase

| Skill | L0 | L1 | L2 | L3 | L4 | L5 | L6 | L7 | L8 | L9 |
|-------|----|----|----|----|----|----|----|----|----|----|
| Python | ✅ | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 |
| REST APIs | ✅ | 🟡 | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 |
| LangGraph | ❌ | ✅ | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 |
| MCP | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | 🟢 | 🟢 | 🟢 | 🟢 |
| RAG | 🟡 | ❌ | ❌ | ❌ | ✅ | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 |
| ETL | ❌ | ❌ | ✅ | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 |
| Metadata/Ontology | ❌ | ❌ | ❌ | ✅ | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 |
| AWS Bedrock | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | 🟢 | 🟢 | 🟢 |
| Testing/Evals | 🟡 | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 |

✅ = Implemented & Tested  
🟢 = In use / Reinforced  
🟡 = Partial / Basic  
❌ = Not started

---

## Estado Operativo

`yaml
CURRENT_PHASE: L9
COMPLETION: L9 offline scope VERIFIED
NEXT_MILESTONE: Portfolio closure and explicitly authorized live validations
BLOCKERS: AWS, commercetools and GitHub live identities are not configured
P0_ISSUES: 0
P1_ISSUES: 0
TESTS_PASSING: 109/109 (L9 + workspace binding contract)
EVIDENCE_GENERATED: L9 offline agent evidence
LEARNING_ENTRIES: L0-L9
NEXT_ACTION: Review portfolio evidence; keep live integrations NOT_RUN
`

---

**Última actualización:** 2026-09-21  
**Próxima revisión:** Al completar cada fase
