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
| VectorStoreAdapter | FAISS/Pinecone | Embedding storage, similarity search | L4 |
| ETLSourceAdapter | Web/API/Files | Extraction, normalization | L2 |
| MetadataCatalogAdapter | OpenMetadata | Search, lineage, ownership, schema version, quality y receipts | L8 |
| GovernedKnowledgeAgent | LangGraph + RAG + MCP + Bedrock | End-to-end orchestration, proposals, permits, receipts y evidence | L9 |
| OntologyEngine | Local RDF/Turtle + bounded SPARQL | Relation paths, inference, constraints, contradiction receipts | L10 |
| SandboxManager | LocalRestrictedBackend | Workspace, process, credential and fail-closed execution limits | L11 |

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
`

---

## Estado Actual

`yaml
FASE: L10 (Governed Ontology Engine)
COMPLETION: L10 local scope VERIFIED
NEXT_MILESTONE: OpenMetadata local real + observability/evals local
BLOCKERS: AWS/OpenMetadata live no autorizados o no configurados
`

**Última actualización:** 2026-09-22
