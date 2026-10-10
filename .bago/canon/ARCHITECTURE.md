# BAGO AGENTIC DATA LAB — Arquitectura de Referencia

## Visión General

Sistema de ejecución gobernada para agentes de IA con trazabilidad completa, desde la ingestión de datos hasta la ejecución de acciones con autorización.

---

## Capas Arquitectónicas

`
┌─────────────────────────────────────────────────────────────┐
│                    ORCHESTRATION (LangGraph)                 │
│  StateGraph · nodes · edges · conditional routing · tools   │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                    REASONING LAYER                           │
│  Intent classification · Tool proposal · Plan generation    │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                 AUTHORIZATION BOUNDARY ← BAGO GOVERNANCE     │
│  ExecutionRequest · Permit · Validation · Action limits     │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                  EXECUTION GATEWAY                           │
│  EffectAdapter · Provider routing · Receipt generation      │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                  SANDBOX MANAGER                             │
│  Permit-derived profiles · path/process limits · evidence   │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│              EXTERNAL CAPABILITIES                           │
│  AWS Bedrock · MCP tools · APIs · Vector DBs · ETL          │
└─────────────────────────────────────────────────────────────┘
`

---

## Flujo de Datos Principal

### Pipeline de Ingestión (ETL)

`
SOURCE
  ↓
EXTRACT (web scraping, API calls, file upload)
  ↓
NORMALIZE (unified schema)
  ↓
VALIDATE (schema validation, deduplication)
  ↓
ENRICH (metadata extraction, entity recognition)
  ↓
CHUNK (semantic boundaries, content hashing)
  ↓
METADATA (provenance, version, authority)
  ↓
LOAD (vector store + relational metadata)
  ↓
VERIFY (receipt generation)
`

### Pipeline de Retrieval (RAG Gobernado)

`
QUERY
  ↓
INTENT (classification, entity extraction)
  ↓
METADATA FILTERS (authority, recency, domain)
  ↓
LEXICAL RETRIEVAL (BM25, keyword matching)
  ↓
SEMANTIC RETRIEVAL (embeddings, vector similarity)
  ↓
PERSISTENT LOCAL VECTOR BACKEND (SQLiteVectorStore, deterministic vectors)
  ↓
RERANKING (cross-encoder, relevance scoring)
  ↓
AUTHORITY FILTERING (BAGO governance rules)
  ↓
CONTEXT ASSEMBLY (prompt construction)
  ↓
GENERATION (LLM inference)
  ↓
EVIDENCE (claim → chunk → source → revision)
`

### Backend semántico persistente local (L14)

`
RETRIEVAL CHUNKS + METADATA
  ↓
SQLITE VECTOR INDEX (content, metadata, deterministic HashEmbedding)
  ↓
AUTHORITY / VALIDITY / PROVENANCE GATE
  ↓
VECTOR SCORES + STABLE FINGERPRINT
  ↓
GOVERNEDRAG CONTEXT + CITATIONS
`

### Pipeline de Reasoning Ontológico (L10)

`
RETRIEVED CHUNKS + CITATIONS
  ↓
RDF MATERIALIZATION (KnowledgeGraph → Turtle triples)
  ↓
SPARQL SELECT (bounded local query subset)
  ↓
INFERENCE (inverse · transitive · symmetric relations)
  ↓
CONSTRAINTS (endpoints · evidence · contradictions)
  ↓
PATH + EVIDENCE + ONTOLOGY RECEIPT
  ↓
LLM CONTEXT (reasoning only; no authority promotion)
`

### Pipeline de Ejecución Governada

`
TOOL_PROPOSAL (from LangGraph/reasoning)
  ↓
EXECUTION_REQUEST (structured effect description)
  ↓
AUTHORIZATION_BOUNDARY (validation, permits, action limits)
  ↓
PERMIT_ISSUED (signed authorization token)
  ↓
EXECUTION_GATEWAY (single material-effect boundary)
  ↓
SANDBOX_MANAGER (permit-derived technical limits)
  ↓
LOCAL_RESTRICTED_BACKEND (typed capability execution)
  ↓
EXTERNAL_EFFECT (API call, database write, file operation)
  ↓
RECEIPT (what happened, when, outcome, evidence)
  ↓
VERIFICATION (expected vs actual, assertions)
  ↓
OPENTELEMETRY PROJECTION (spans only; no authority)
  ↓
JAEGER LOCAL (OTLP/HTTP queryable backend)
`

---

## Componentes Críticos

### 1. ExecutionRequest

`python
class ExecutionRequest:
    request_id: str
    tool_name: str
    effect_type: EffectType  # READ, WRITE, CREATE, DELETE, EXTERNAL
    parameters: dict
    proposed_by: str  # agent/tool identifier
    context_revision: str
    timestamp: str
`

### 2. AuthorizationBoundary

`python
class AuthorizationBoundary:
    permit_id: str
    request_id: str
    decision: ALLOW | DENY | REQUIRE_HUMAN
    rationale: str
    constraints: list[Constraint]  # time limits, resource limits, scope limits
    issued_at: str
    expires_at: str
    signed_by: str  # authority identifier
`

### 3. Receipt

`python
class Receipt:
    receipt_id: str
    permit_id: str
    execution_outcome: SUCCESS | FAILURE | PARTIAL
    actual_effect: dict
    evidence_refs: list[str]
    duration_ms: int
    cost_usd: float
    error_message: str | None
`

---

## Adapters por Implementar

| Adapter | External Tech | Responsibility | Priority |
|---------|---------------|----------------|----------|
| BedrockProviderAdapter | AWS Bedrock | Converse API, tool use, streaming | L6 |
| BedrockKnowledgeBaseAdapter | AWS Bedrock Knowledge Bases | Retrieve/Generate, citations, metadata filters | L7 |
| MCPCapabilityAdapter | MCP Protocol | Tool discovery, schema validation | L5 |
| VectorStoreAdapter | FAISS/Pinecone | Distributed/hosted similarity search for a later live boundary | Future |
| SQLiteVectorStore | SQLite + deterministic HashEmbedding | Persistent local vectors, metadata gate, reload fingerprint and evidence citations | L14 |
| ETLSourceAdapter | Web/API/Files | Extraction, normalization | L2 |
| MetadataCatalogAdapter | OpenMetadata | Search, lineage, ownership, schema version, quality y receipts | L8 |
| GovernedKnowledgeAgent | LangGraph + RAG + MCP + Bedrock | End-to-end orchestration, proposals, permits, receipts y evidence | L9 |
| OntologyEngine | Local RDF/Turtle + bounded SPARQL | Relation paths, inference, constraints, contradiction receipts | L10 |
| SandboxManager | LocalRestrictedBackend | Workspace, process, credential and fail-closed execution limits | L11 |
| LocalTraceBuilder | Local JSON trace | Workflow, retrieval, permits, sandbox and receipt linkage | L12 |
| LocalTraceEvaluator | Deterministic local checks | Coverage, evidence linkage and unauthorized-effect checks | L12 |
| OTelTraceBridge | OpenTelemetry SDK + OTLP/HTTP | Project LocalTrace into parent-linked spans without authority | L15 |
| Jaeger local | Docker all-in-one `1.60.0` | Queryable local trace backend for live validation | L15 |
| Public E2E Demo | Committed fixtures + local boundaries | Clone-and-run composition with stable PASS gates | L13 |
| GitHub Actions CI | Python 3.11 + pinned requirements | Suite, README, E2E and compile verification | L13 |

---

## Invariantes de Seguridad

1. **Ningún framework externo ejecuta efectos materiales directamente**
   - LangGraph propone, BAGO autoriza, ExecutionGateway ejecuta

2. **Toda acción tiene receipt verificable**
   - Sin receipt = no ocurrió (para propósitos de auditoría)

3. **Metadata obliga**
   - Documento sin provenance = rechazado
   - Chunk de revisión superseded = filtrado en retrieval

4. **Autoridad explícita**
   - MCP tool discovered ≠ automatic authority
   - Requiere registro explícito + clasificación de efectos

5. **Timeouts y retries acotados**
   - Todo llamada externa tiene timeout máximo
   - Retry policy con backoff exponencial y límite superior

6. **La inferencia no concede autoridad**
   - Un triple inferido conserva la evidencia de sus premisas
   - La ontología devuelve paths y restricciones; no promueve automáticamente
     una propuesta a estado canónico

7. **La contradicción no se oculta**
   - Una relación `CONTRADICTS` produce `CONSTRAINT_VIOLATION`
   - El path y el receipt permanecen disponibles para revisión

8. **Una acción material no puede saltarse el sandbox**
   - `ExecutionGateway → SandboxManager` es la frontera única de ejecución local
   - Un agente o salida LLM no puede elegir un perfil más privilegiado

9. **El sandbox sólo reduce autoridad**
   - La especificación efectiva es la intersección de permit, perfil y request
   - Un fallo de aislamiento solicitado produce `DENIED`, nunca ejecución abierta

10. **La red fuerte no se simula**
    - El backend local sólo ofrece política lógica `network=deny`
    - El aislamiento OS requerido permanece explícitamente `NOT_RUN`

11. **La observabilidad no concede autoridad**
    - Un trace sólo normaliza eventos y receipts ya producidos
    - Un eval local puede fallar por evidencia incompleta, pero nunca autoriza
      ni promueve una acción

12. **OpenTelemetry sólo proyecta evidencia existente**
    - El `LocalTrace` sigue siendo la fuente de evidencia y la autoridad BAGO
    - Un fallo de exportación no se convierte en éxito ni habilita ejecución
    - Jaeger local no se presenta como collector remoto o producción

---

## Estrategia de Testing

### Tests Unitarios

- Cada adapter con mocks de dependencias externas
- Contracts validados con schemas explícitos
- Error handling probado (timeouts, rate limits, auth failures)

### Tests de Integración

- LangGraph complete flow (START → END)
- ETL pipeline end-to-end con datos de prueba
- RAG retrieval con queries conocidos
- Ontology Engine con RDF/Turtle, SPARQL, inference y constraint receipt
- Sandbox local con escapes de ruta, allowlists de proceso, timeout, entorno
  filtrado, Git read-only y receipts de denegación
- Trace local con workflow, retrieval, permits, sandbox, receipts y evals

### Tests de Gobernanza (CRÍTICOS)

`python
def test_langgraph_cannot_execute_directly():
    """LangGraph intenta ejecutar herramienta directamente → EXPECTED: DENY"""
    
def test_permit_reuse_denied():
    """Permit reutilizado → EXPECTED: DENY"""
    
def test_document_without_provenance_rejected():
    """Documento sin provenance → EXPECTED: REJECT"""
    
def test_superseded_chunk_filtered():
    """Chunk de revisión superseded utilizado como autoridad → EXPECTED: FILTERED"""
    
def test_mcp_tool_unregistered_denied():
    """MCP tool no registrado → EXPECTED: DENY"""
    
def test_bedrock_timeout_controlled_failure():
    """Bedrock provider timeout → EXPECTED: CONTROLLED_FAILURE + RECEIPT"""
`

---

## Decisiones Arquitectónicas Clave

### ADR-001: LangGraph como Orchestrator, no como Executor

**Decisión:** LangGraph orquesta el flujo de razonamiento, pero NO ejecuta efectos materiales directamente.

**Racional:** Separa reasoning de execution, permitiendo gobernanza explícita.

**Consecuencias:**
- ✅ Autorización centralizada
- ✅ Audit trail completo
- ❌ Overhead adicional por request/permit/receipt

### ADR-002: Metadata-first sobre Data

**Decisión:** Todo dato ingerido debe tener metadata completa antes de estar disponible para retrieval.

**Racional:** Permite filtering por autoridad, versión, lineage en queries.

**Consecuencias:**
- ✅ Retrieval más preciso
- ✅ Trazabilidad completa
- ❌ Latencia inicial mayor en ingestión

### ADR-003: Receipts como Fuente de Verdad

**Decisión:** Lo que no tiene receipt no existe para propósitos de auditoría.

**Racional:** Permite reconstrucción exacta de ejecuciones pasadas.

**Consecuencias:**
- ✅ Auditabilidad total
- ✅ Debugging simplificado
- ❌ Storage overhead

### ADR-004: Ontology Engine local antes que cloud live

**Decisión:** Priorizar un motor RDF/SPARQL local, reproducible y sin coste antes
de desplegar AWS live u otros servicios de pago.

**Racional:** Convierte retrieval en reasoning sobre relaciones y produce una
capacidad demostrable con evidencia pública sin introducir credenciales, gasto
ni dependencia operativa.

**Consecuencias:**

- ✅ Paths de dependencia, supersession, validación y contradicción con receipt
- ✅ El contrato puede adaptarse más tarde a un triplestore real
- ❌ El alcance actual no es un triplestore desplegado ni SPARQL completo

### ADR-005: Observabilidad local antes que collector externo

**Decisión:** Normalizar los eventos y receipts existentes en un trace local y
evaluarlos con reglas deterministas antes de introducir OpenTelemetry, un
collector o un servicio externo.

**Racional:** Mantiene el coste en cero, hace pública la cadena de evidencia y
evita confundir telemetría con autoridad o con una validación de calidad del
modelo.

**Consecuencias:**

- ✅ Trace reproducible y enlazado a receipts
- ✅ Evals de gobernanza ejecutables offline
- ❌ No es todavía observabilidad de producción ni evaluación semántica LLM

### ADR-006: Public E2E composition before cloud live

**Decisión:** Cerrar una ruta pública reproducible que componga las fronteras
locales ya verificadas antes de introducir una dependencia cloud adicional.

**Racional:** Una demo E2E sólo aporta evidencia profesional si atraviesa la
misma cadena de retrieval, reasoning, authorization, sandbox, receipt, trace y
eval que el diseño declara. La CI repite esa cadena en cada push y pull request.

**Consecuencias:**

- ✅ Clone-and-run sin credenciales, Docker ni coste
- ✅ La CI detecta deriva de tests, README, demo y compilación
- ❌ No convierte fixtures en AWS live, OpenMetadata remoto ni producción

### ADR-007: Persistent local vector backend before remote vector service

**Decisión:** Añadir un `SQLiteVectorStore` local y determinista detrás del
contrato semántico de `GovernedRAG` antes de adoptar un vector database remoto.

**Racional:** Cierra la capacidad de persistencia y reload con coste cero,
mantiene el filtro de autoridad/validity/provenance antes del ranking y produce
una evidencia pública reproducible sin credenciales ni servicio externo.

**Consecuencias:**

- ✅ El retrieval deja de depender únicamente de un backend semántico en memoria
- ✅ El fingerprint permite comprobar que el índice se conserva al recargarlo
- ✅ El backend puede sustituirse más tarde sin mover la frontera de gobernanza
- ❌ No ofrece distribución, ANN ni relevancia productiva; el vector DB remoto
  permanece como una validación separada

### ADR-008: Local OpenTelemetry projection before remote observability

**Decisión:** Proyectar el `LocalTrace` existente a spans OpenTelemetry y
validarlos en Jaeger local antes de introducir un collector remoto o SaaS.

**Racional:** Hace visible la cadena E2E real —workflow, retrieval, permits,
receipts, sandbox y eval— con coste cero, sin duplicar la autoridad ni ocultar
los límites del trace JSON ya verificado.

**Consecuencias:**

- ✅ Parent links y atributos de evidencia son consultables en un backend live
- ✅ Docker + Jaeger permiten reproducir la validación desde un clon
- ✅ El exporter falla cerrado en la evidencia cuando OTLP no responde
- ❌ No ofrece retención, HA, alertas, producción ni un collector remoto

---

## Roadmap de Implementación

`mermaid
gantt
    title Fases de Implementación
    dateFormat  YYYY-MM-DD
    section Baseline
    L0: Contract & Architecture  :done, des1, 2026-09-21, 1d
    section Core
    L1: LangGraph Execution      :active, des2, after des1, 7d
    L2: ETL Pipeline             :         des3, after des2, 7d
    L3: Metadata & Ontology      :         des4, after des3, 7d
    L4: Governed RAG             :         des5, after des4, 7d
    section Integration
    L5: MCP                      :         des6, after des5, 7d
    L6: AWS Bedrock              :         des7, after des6, 7d
    L7: Bedrock Knowledge Base   :         des8, after des7, 7d
    L8: Metadata Catalog         :         des9, after des8, 7d
    section Capstone
    L9: End-to-End Agent         :         des10, after des9, 14d
    L10: Ontology Engine          :done, des11, after des10, 1d
    L11: Governed Sandbox         :done, des12, after des11, 1d
    L12: Local Observability      :done, des13, after des12, 1d
    L13: Public E2E + CI           :done, des14, after des13, 1d
    L14: Local Vector Store        :done, des15, after des14, 1d
    L15: OTel + Jaeger Local Live  :done, des16, after des15, 1d
`

---

## Estado Actual

`yaml
FASE: L15 (OpenTelemetry + Jaeger Local Live)
COMPLETION: L15 OTLP/HTTP projection and Jaeger query validation VERIFIED
NEXT_MILESTONE: AWS live only with credits/free tier or a concrete job need
BLOCKERS: AWS/OpenMetadata live y vector DB remoto no autorizados o no configurados
`

**Última actualización:** 2026-09-23
