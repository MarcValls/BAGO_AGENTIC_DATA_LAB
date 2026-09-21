# BAGO AGENTIC DATA LAB — Roadmap Ejecutable

## Timeline Objetivo

**Inicio:** 2026-09-21  
**L0-L4 (MVP empleable):** 5 semanas → 2026-10-26  
**L0-L7 (Portfolio completo):** 8 semanas → 2026-11-16  
**L0-L9 (Capstone):** 10 semanas → 2026-12-01

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

- [ ] src/adapters/mcp_adapter.py
- [ ] MCP server local de ejemplo
- [ ] 	ests/test_mcp_governance.py
- [ ] Evidence: video mostrando MCP tool call gobernado

---

## L6 · AWS BEDROCK

**Duración:** 1 semana  
**Fecha objetivo:** 2026-11-02  
**🎯 CANDIDATURA Tuio (~96% fit)**

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

- [ ] src/adapters/bedrock_provider_adapter.py
- [ ] 	ests/test_bedrock_integration.py
- [ ] docs/aws_bedrock_setup.md (IAM, quotas, costes)
- [ ] Evidence: benchmarks de latency/cost por modelo

---

## L7 · BEDROCK KNOWLEDGE BASE

**Duración:** 1 semana  
**Fecha objetivo:** 2026-11-09  
**🎯 CANDIDATURA Devoteam (~93% fit)**

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

- [ ] src/adapters/bedrock_kb_adapter.py
- [ ] vidence/bago_etl_vs_bedrock_kb_comparison.md
- [ ] Evidence: misma query respondida por ambos sistemas

---

## L8 · METADATA CATALOG (OpenMetadata)

**Duración:** 1 semana  
**Fecha objetivo:** 2026-11-16

### Features a Integrar

- Catalog search
- Lineage visualization
- Ownership assignment
- Schema versioning
- Quality rules
- Discovery UI

### Entregables

- [ ] src/adapters/openmetadata_adapter.py
- [ ] OpenMetadata local running (Docker)
- [ ] Evidence: lineage completo de un documento desde source hasta chunk

---

## L9 · END-TO-END GOVERNED AGENT

**Duración:** 2 semanas  
**Fecha objetivo:** 2026-12-01  
**🎯 PORTFOLIO COMPLETO PARA TODAS LAS CANDIDATURAS**

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

- [ ] src/agent/governed_knowledge_agent.py
- [ ] 	ests/test_end_to_end_agent.py
- [ ] README.md final con demos grabadas
- [ ] Portfolio público completo en GitHub

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
CURRENT_PHASE: L0
COMPLETION: 20%
NEXT_MILESTONE: Completar documentos fundacionales
BLOCKERS: Ninguno
P0_ISSUES: 0
P1_ISSUES: 0
TESTS_PASSING: 0/0
EVIDENCE_GENERATED: 0
LEARNING_ENTRIES: 0
NEXT_ACTION: Crear LEARNING_LEDGER.md y JOB_SKILL_MATRIX.md
`

---

**Última actualización:** 2026-09-21  
**Próxima revisión:** Al completar cada fase
