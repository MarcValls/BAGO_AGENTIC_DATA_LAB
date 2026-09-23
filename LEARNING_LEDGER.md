# LEARNING LEDGER

## Propósito

Este documento registra **qué he aprendido realmente** en cada fase del laboratorio.

No es un diario. Es un **ledger de evidencia de aprendizaje**.

Cada entrada debe poder usarse para:
- Explicar el concepto en una entrevista técnica
- Demostrar que lo he implementado
- Mostrar qué errors evito ahora

---

## Formato de Entrada

`markdown
### [FECHA] — [CONCEPTO]

**Fase:** L0-L9

**Qué entendí:**
[Explicación clara del concepto, qué problema resuelve, cómo funciona]

**Qué implementé:**
[Archivos creados, funciones específicas, tests escritos]

**Evidence:**
[Links a commits, tests passing, demos, benchmarks]

**Failure modes que ahora evito:**
[Errores conceptuales comunes, qué hacía antes vs qué hago ahora]

**Interview explanation:**
[Cómo explicaría esto en 2 minutos en una entrevista técnica]

**Gaps restantes:**
[Qué no sé todavía sobre este tema, qué quiero explorar después]
`

---

## Entradas

### 2026-09-21 — LangGraph StateGraph con Gobernanza BAGO

**Fase:** L1

**Qué entendí:**

LangGraph es un framework de orchestration basado en grafos de estado. Permite definir flujos de razonamiento como secuencias de nodos que transforman un estado compartido.

**Conceptos clave aprendidos:**

1. **StateGraph**: Contenedor principal que define el schema de estado (TypedDict) y los nodos.
2. **Nodes**: Funciones puras que reciben state y retornan actualizaciones parciales.
3. **Edges**: Conexiones determinísticas entre nodos. El flujo es START → node1 → node2 → ... → END.
4. **compile()**: Convierte la definición declarativa en un ejecutable.

**Problema que resuelve:**
Orquestar flujos complejos de reasoning + retrieval + action de forma mantenible y testeable, en lugar de tener código espagueti con if/else anidados.

**Qué implementé:**

- src/orchestration/state_graph.py (450 líneas):
  - Domain model: ExecutionRequest, Permit, Receipt, EffectType, AuthorizationDecision
  - State schema: AgentState TypedDict con 12 campos
  - 6 nodes: classify_intent, etrieve_context, eason, uthorization_gate, xecute_actions, erify_and_respond
  - Graph construction con langgraph.graph.StateGraph

- 	ests/test_l1_governance.py (6 tests CRIT P0):
  - 	est_langgraph_cannot_execute_directly() → WRITE actions denegadas
  - 	est_permit_reuse_denied() → Replay attack prevention
  - 	est_document_without_provenance_rejected() → Metadata enforcement
  - 	est_superseded_chunk_filtered_in_retrieval() → Version filtering
  - 	est_mcp_tool_unregistered_denied() → Capability registry
  - 	est_bedrock_provider_timeout_controlled_failure() → Receipt on failure

**Evidence:**

- ✅ Commit 1f522d7 + c576404 + implementation commit
- ✅ 7 tests passing (pytest output)
- ✅ Grafo compilando y ejecutándose end-to-end

**Failure modes que ahora evito:**

❌ **ANTES:** Framework externo = autoridad implícita  
✅ **AHORA:** LangGraph ORQUESTA pero BAGO AUTORIZA

❌ **ANTES:** Ejecutar acciones directamente desde el grafo  
✅ **AHORA:** ExecutionRequest → AuthorizationBoundary → Permit → ExecutionGateway

❌ **ANTES:** Permisos reutilizables  
✅ **AHORA:** Single-use permits con tracking

❌ **ANTES:** Documentos sin metadata aceptados  
✅ **AHORA:** Provenance obligatoria o rechazo

❌ **ANTES:** Silent failures en timeouts  
✅ **AHORA:** Controlled failure + Receipt siempre

**Interview explanation:**

*"Implementé un sistema de agents gobernado donde LangGraph orquesta el flujo de razonamiento pero NO tiene autoridad para ejecutar efectos materiales directamente.*

*Cuando el grafo identifica que se necesita una acción (escribir archivo, llamar API externa), crea un ExecutionRequest que pasa por un authorization gate. Este gate valida:*
- *¿Es READ? Auto-allow con timeout*
- *¿Es WRITE/CREATE/DELETE? Requiere autorización humana explícita*
- *¿Es EXTERNAL_API? Allow con constraints estrictas de timeout y rate limit*

*Solo si hay un Permit válido y vigente, el execution gateway procede. Después de ejecutar, genera un Receipt con evidence refs, duration, cost, y error_message si falló.*

*Esto garantiza auditabilidad completa: cada efecto material tiene un paper trail desde la intención inicial hasta el receipt final."*

**Gaps restantes:**

- ❌ Conditional routing dinámico (solo edges fijos por ahora)
- ❌ Interrupt/resume para aprobaciones humanas
- ❌ Checkpointing para durable execution
- ❌ Subgraphs para modularidad
- ⚠️ Mock retrieval (RAG real en L4)
- ⚠️ Mock execution (adapters reales en L5-L6)

---

## Progreso por Fase

| Fase | Conceptos clave aprendidos | Evidence generada | Interview ready |
|------|---------------------------|-------------------|-----------------|
| L0 | Contract + Architecture + Market intel | 5 docs fundacionales | ✅ Sí |
| L1 | LangGraph StateGraph, Governance boundary, Permit pattern | state_graph.py + 7 tests passing | ✅ Sí |
| L2 | — | — | — |
| L3 | Entity schema, authority, validity, relations, lineage | schema.py + ontology.py + ontology_generator.py + 25 tests + graph/proposal evidence | ✅ Sí |
| L4 | Governed RAG, hybrid retrieval, metadata filters, evidence context | governed_rag.py + benchmark + 12 tests | ✅ Sí |
| L5 | MCP discovery, capability registry, effect classification, governed stdio calls | mcp_adapter.py + local server + 7 tests + execution receipt | ✅ Sí |
| L6 | AWS Bedrock Converse/Stream, provider boundary, retries, quotas, cost receipts | bedrock_provider_adapter.py + 10 tests + offline benchmark | ✅ Sí (offline scope) |
| L7 | Bedrock Knowledge Base, Retrieve/Generate, metadata filters, citations, managed-vs-local trade-offs | bedrock_kb_adapter.py + 10 tests + ETL/KB comparison | ✅ Sí (offline scope) |
| L8 | Metadata Catalog, lineage, ownership, quality | adapter + 12 tests + catalog evidence | ✅ Sí (offline scope) |
| L9 | End-to-end governed agent, tool proposals, provider boundary | agent + 7 tests + 3-scenario evidence | ✅ Sí (offline scope) |

---

**Última actualización:** 2026-09-22
**Próxima entrada:** Al cerrar una validación live explícitamente autorizada

---

### 2026-09-21 — ETL Pipeline Gobernado

**Fase:** L2

**Tests:** 4/4 CRIT P0 passing

**Evidence:** 65 chunks ingeridos, idempotencia verificada, receipts generados

---

### 2026-09-21 — Metadata & Ontology

**Fase:** L3

**Implementación:** `src/metadata/schema.py` define entidades, autoridad,
clasificación, procedencia, versionado y `ValidityStatus`; `src/metadata/ontology.py`
define relaciones, lineage e integridad del grafo; `src/metadata/ontology_generator.py`
separa metadata extraction, relation proposals y validation.

**Tests:** 45/45 passing en la suite combinada; la aceptación L3 quedó en
37/37 antes del agente; L3 aporta 12 tests de ontología,
4 tests de schema, 7 tests de generator y 2 checks de evidencia.

**Evidence:** `evidence/l3_ontology_graph.md`, generado de forma reproducible
por `scripts/generate_l3_ontology_evidence.py`; 0 errores de integridad.
`evidence/ontology_proposal.md` registra el resultado sobre la documentación
BAGO actual (16 entidades, 0 relaciones explícitas) y
`evidence/ontology_proposal_examples.md` demuestra 4 propuestas que pasan
reglas pero permanecen pendientes de aprobación humana/contractual.

---

### 2026-09-22 — Governed RAG

**Fase:** L4

**Implementación:** `src/retrieval/governed_rag.py` separa intent,
metadata/authority gate, BM25-like lexical retrieval, semantic hash baseline,
hybrid fusion, reranking y contexto con `EvidenceRef`.

**Tests:** 57/57 passing en la suite combinada; L4 aporta 9 tests de accuracy
y 3 tests del benchmark.

**Evidence:** `evidence/retrieval_benchmark_results.md` contiene 48 filas
reproducibles: tres modos, reranking on/off, top-k 10/25/50/100 y dos
políticas de metadata. El semantic baseline es offline y no representa una
evaluación de un modelo cloud.

---

### 2026-09-22 — Governed MCP

**Fase:** L5

**Implementación:** `src/adapters/mcp_adapter.py` separa discovery de
registration, clasifica efectos en BAGO, crea `ExecutionRequest` y exige
`Permit` antes de llamar al transporte MCP.

**Tests:** 64/64 passing en la suite combinada; L5 aporta 7 tests, incluida
una ronda real por stdio contra `scripts/local_mcp_server.py`.

**Evidence:** `evidence/mcp_governed_demo.md` demuestra un `READ` permitido y
un `WRITE` bloqueado antes del servidor. La evidencia visual está en
`evidence/mcp_governed_demo.mp4` con SHA-256 asociado; el transcript es
reproducible con `python scripts/run_mcp_demo.py`.

---

### 2026-09-22 — Governed AWS Bedrock Provider

**Fase:** L6

**Qué entendí:**

`Converse` ofrece una frontera unificada para modelos conversacionales y
`ConverseStream` devuelve eventos incrementales. La SDK es transporte, no
autoridad: BAGO debe decidir si el modelo, la operación y el presupuesto están
permitidos antes de crear la llamada externa.

**Qué implementé:**

- `src/adapters/bedrock_provider_adapter.py`:
  - `ExecutionRequest` con `EffectType.EXTERNAL_API` y modelo/operación ligados.
  - `Permit` obligatorio, expiración y allowlist opcional de modelos.
  - `Converse` y `ConverseStream` normalizados a `BedrockCallResult`.
  - retries acotados para timeout/throttle/network, sin retry de autorización o validación.
  - rate limit local, configuración de timeout del cliente y receipts con usage/cost.
- `tests/test_bedrock_integration.py`: 10 checks offline con cliente inyectado.
- `scripts/benchmark_bedrock_provider.py` y
  `evidence/bedrock_provider_benchmark.md`: dos fixtures de modelo, latencia local
  y coste calculado con rates explícitos.
- `docs/aws_bedrock_setup.md`: boto3 opcional, IAM mínimo, cuotas, costes y checklist live.

**Tests:** 74/74 passing en la suite combinada; L6 aporta 10 checks.

**Evidence:** el benchmark offline demuestra `ALLOW → called → SUCCESS` y
receipts ligados a modelo/request. No se ejecutó una cuenta AWS real: la
validación de credenciales, IAM, model access, latencia cloud y precio vigente
queda `NOT_RUN`.

**Failure modes que ahora evito:**

❌ LLM/provider llamado sin permiso explícito
✅ `ExecutionRequest → Permit → adapter`, y denegación antes del cliente

❌ Retry infinito o retry de `AccessDenied`
✅ Presupuesto de intentos y taxonomy que solo reintenta errores transitorios

❌ Coste inventado o no trazable
✅ Coste estimado solo desde `usage` y rates configurados, dentro del receipt

**Interview explanation:**

*"Encapsulé Bedrock detrás de un adapter gobernado. La aplicación construye
una request de `EXTERNAL_API`, el policy decide el modelo y límites, y un
permit ligado al request_id habilita `Converse` o `ConverseStream`. El adapter
normaliza respuestas, limita retries y quota, clasifica fallos y emite un
receipt con tokens, coste estimado, intentos y evidencia. Las pruebas usan un
cliente inyectado; la conectividad AWS se valida por separado."*

**Gaps restantes:**

- ⚠️ Live AWS validation: credenciales, IAM, model access y `ConverseStream` real.
- ⚠️ Prices and quotas must be refreshed from the target AWS account/region.
- ⚠️ Tool-use end-to-end with MCP remains a later integration milestone.

---

### 2026-09-22 — Governed Bedrock Knowledge Base

**Fase:** L7

**Qué entendí:**

Una Knowledge Base gestionada separa el ciclo de ingestión/vectorización del
query runtime. `Retrieve` devuelve referencias para que BAGO pueda ensamblar y
gobernar el contexto; `RetrieveAndGenerate` añade generación y citas, pero no
convierte al servicio AWS en autoridad. La decisión correcta para Devoteam es
comparar el control total del ETL propio con la comodidad gestionada, no
presentar uno como sustituto universal.

**Qué implementé:**

- `src/adapters/bedrock_kb_adapter.py`:
  - requests `EXTERNAL_API` para `Retrieve` y `RetrieveAndGenerate`;
  - allowlist de Knowledge Base, modelo ARN para generación y filtros metadata;
  - normalización de score, source URI, metadata, chunk IDs y citations;
  - retries acotados, rate limit local y `BedrockKBReceipt` auditable.
- `tests/test_bedrock_kb_adapter.py`: 10 checks offline con cliente inyectado.
- `scripts/compare_bago_etl_vs_bedrock_kb.py` y
  `evidence/bago_etl_vs_bedrock_kb_comparison.md`: misma query, tres referencias
  coincidentes, respuesta/citations fixture y comparación de fronteras.
- `docs/bedrock_knowledge_base.md`: lifecycle, IAM, filtros, costes y checklist live.

**Tests:** 84/84 passing en la suite combinada; L7 aporta 10 checks.

**Evidence:** la comparación demuestra `ExecutionRequest → Permit →
RetrieveAndGenerate → citations → receipt` y conserva la comparación con el
ETL/RAG local. El cliente Bedrock es un fixture; AWS real, ingestión, vector
store, IAM, relevancia cloud y costes vigentes quedan `NOT_RUN`.

**Failure modes que ahora evito:**

❌ Knowledge Base gestionada tratada como autoridad implícita
✅ BAGO controla KB allowlist, permit, metadata policy y receipt

❌ Respuesta generada sin trazabilidad de fuentes
✅ `BedrockKBHit` conserva source URI, metadata, score y citation estable

❌ Comparar latencia local con latencia cloud como si fueran equivalentes
✅ Evidencia separa fixture offline de validación AWS pendiente

**Interview explanation:**

*"Implementé un adapter para `bedrock-agent-runtime` que separa `Retrieve`
de `RetrieveAndGenerate`. Antes de consultar, BAGO valida la Knowledge Base,
el modelo y los límites mediante un Permit. Después normalizo referencias y
citas en un receipt. También comparé la misma query contra el ETL/RAG local:
el ETL conserva control y provenance; Bedrock reduce operación pero añade
dependencia, permisos y superficie de coste. La comparación pública usa un
fixture y deja la conexión AWS como validación separada."*

**Gaps restantes:**

- ⚠️ Crear/ingerir una Knowledge Base real y verificar su service role.
- ⚠️ Comparar relevancia, filtros y latencia sobre corpus Devoteam real.
- ⚠️ Actualizar IAM, vector store, quotas y precios con la cuenta/region objetivo.

---

### 2026-09-22 — Governed OpenMetadata Catalog

**Fase:** L8

**Qué entendí:**

Un catálogo no es sólo una tabla de búsqueda. Para que sea útil al agente debe
resolver discovery, lineage, ownership, versionado y calidad bajo una misma
frontera de autoridad. OpenMetadata ofrece APIs para esas capacidades, pero la
SDK o el servidor no deben saltarse `ExecutionRequest → Permit → receipt`.

**Qué implementé:**

- `src/adapters/openmetadata_adapter.py`:
  - `search` y `get_lineage` como lecturas gobernadas;
  - `add_lineage`, `assign_ownership`, `register_schema_version` y
    `create_quality_rule` como escrituras con scope explícito;
  - normalización de entidades, owners, tags, versión, autoridad y edges;
  - retries sólo para timeout/throttle/network, rate limit local y receipts;
  - cliente inyectable para pruebas y transporte HTTP stdlib preparado para un
    servidor real.
- `tests/test_openmetadata_adapter.py`: 12 checks P0 offline.
- `scripts/generate_l8_catalog_evidence.py` y
  `evidence/l8_openmetadata_catalog.md`: search, source → asset → chunk,
  ownership, schema version, quality rule y receipts.
- `docs/openmetadata_catalog.md`: contrato, endpoints, boundary y checklist live.

**Tests:** 96/96 esperados en la suite combinada; L8 aporta 12 checks.

**Evidence:** el fixture demuestra `ALLOW → transport → SUCCESS` para las seis
operaciones, dos entidades descubiertas, dos edges de lineage, ownership,
versionado `2.0`, una quality rule y receipts. No se ejecutó un servidor
OpenMetadata real.

**Failure modes que ahora evito:**

❌ Escribir lineage, ownership o reglas sin permiso ligado a la request
✅ Cada operación exige un Permit válido y deja un `MetadataCatalogReceipt`

❌ Reintentar un `401/403` como si fuera un fallo transitorio
✅ Taxonomía separa autorización, validación, not-found y errores retryables

❌ Confundir un fixture con un catálogo desplegado
✅ La evidencia identifica el cliente en memoria y mantiene Docker/live como
`NOT_RUN` hasta comprobarlo realmente

**Interview explanation:**

*"Construí un adapter de OpenMetadata que convierte discovery y cambios de
metadata en operaciones BAGO gobernadas. Las lecturas recuperan entidades y
lineage normalizados; las escrituras de ownership, versionado y calidad sólo
se envían con un Permit acotado. Cada llamada tiene receipt, rate limit y
taxonomy de errores. La validación offline está cerrada; Docker y el servidor
real quedan como una prueba de integración separada, no como una afirmación
implícita."*

**Gaps restantes:**

- ⚠️ Docker/OpenMetadata real: este entorno no tiene `docker` ni `docker compose`.
- ⚠️ Validar JWT/RBAC, ownership y lineage contra la versión/instancia objetivo.
- ⚠️ Mapear definitivamente `KnowledgeAsset`/`KnowledgeChunk` a las entidades
  OpenMetadata elegidas para el despliegue de producción.

---

### 2026-09-22 — End-to-End Governed Agent para commercetools

**Fase:** L9

**Qué entendí:**

Un agente de portfolio no debe ser sólo un prompt conectado a herramientas.
Debe conservar una cadena verificable desde la pregunta hasta el contexto
recuperado, la propuesta de herramienta, el permit, el efecto observado y la
respuesta final. El proveedor LLM y MCP son capacidades intercambiables; la
autoridad sigue en BAGO.

**Qué implementé:**

- `src/agent/governed_knowledge_agent.py`:
  - StateGraph con clasificación, retrieval, reasoning/proposal,
    authorization gate, execution y verification;
  - integración con `GovernedRAG`, `GovernedMCPAdapter` y
    `GovernedBedrockAdapter` opcional;
  - propuestas `CREATE`, `WRITE` y `EXTERNAL_API` que quedan pendientes de
    aprobación humana y no tienen transporte material;
  - receipts y citas reunidos en `AgentRun`.
- `tests/test_l9_end_to_end_agent.py`: 7 checks offline.
- `scripts/generate_l9_agent_evidence.py` y
  `evidence/l9_commercetools_agent.md`: tres escenarios reproducibles,
  MCP local stdio READ, Bedrock fixture y denegaciones pre-transporte.
- `docs/commercetools_capstone.md`: mapa de capacidades y límites de la
  candidatura commercetools.

**Evidence:**

`COMPLETED` para la pregunta técnica con citas, READ MCP y Bedrock fixture;
`PENDING_AUTHORIZATION` para crear un test y crear un issue externo. La suite
L9 pasa 7/7. No se ejecutó AWS, una API real de commercetools ni GitHub.

**Failure modes que ahora evito:**

❌ El LLM decide y ejecuta una escritura directamente
✅ El agente sólo propone; BAGO clasifica el efecto y exige aprobación humana

❌ MCP descubierto tratado como autoridad
✅ Discovery, registry, permit, transporte y receipt quedan separados

❌ Fixture presentado como integración de producción
✅ La evidencia identifica MCP local/Bedrock fixture y marca live como
`NOT_RUN`

**Interview explanation:**

*"Construí un agente end-to-end donde LangGraph orquesta, GovernedRAG aporta
contexto con citas y cada tool proposal se transforma en un ExecutionRequest.
Las lecturas MCP pueden ejecutarse con un permit acotado; CREATE, WRITE y
acciones externas se detienen antes del transporte hasta obtener aprobación.
Bedrock está detrás de otro adapter con allowlist de modelo y receipt de uso.
Así puedo enseñar el loop completo sin confundir un fixture offline con
producción."*

**Gaps restantes:**

- ⚠️ Validación live de AWS, commercetools y GitHub con identidades autorizadas.
- ⚠️ Video nuevo de las tres demos; el transcript Markdown es reproducible.
- ⚠️ Evaluación con corpus y tráfico de negocio real de commercetools.

---

### 2026-09-22 — L10 Governed Ontology Engine

**Fase:** L10
**Estado:** `VERIFIED` para el alcance local RDF/SPARQL + agente; AWS y
OpenMetadata live siguen `NOT_RUN`.

**Qué entendí:**

RAG recupera texto, pero el motor ontológico recupera la estructura que conecta
ese texto: qué entidad depende de otra, qué versión sustituye a cuál, qué
evidencia valida una afirmación y qué relación contradice el resultado. La
ontología no puede convertirse en autoridad por inferencia; debe devolver el
camino, la evidencia y un receipt para que BAGO y el LLM razonen con límites.

**Qué implementé:**

- `src/metadata/ontology_engine.py`: materialización RDF/Turtle desde el grafo
  L3, joins SPARQL locales, filtros `regex`/igualdad y `LIMIT`.
- Inferencia determinista de inversas, transitividad acotada y simetría de
  contradicciones.
- Restricciones de endpoints, evidencia y contradicciones explícitas.
- Integración opcional en `GovernedKnowledgeAgent`; una violación grave produce
  `CONSTRAINT_VIOLATION`, aunque el camino pueda seguir siendo inspeccionado.
- `tests/test_l10_ontology_engine.py`, script de evidencia y documentación.

**Evidence:**

`evidence/l10_ontology_engine.md` ejecuta el caso RAG → RDF/SPARQL → path +
evidence → fixture LLM con coste `0.0 USD`. El fixture contiene una relación
contradictoria a propósito: el receipt reporta `CONSTRAINT_VIOLATION` y no se
presenta como una respuesta limpia.

**Interview explanation:**

*"Construí una frontera ontológica local que convierte el KnowledgeGraph de
   BAGO en RDF, ejecuta un subconjunto controlado de SPARQL y materializa
   relaciones inversas/transitivas. El agente no recibe sólo chunks: recibe
   caminos y citas. Si el grafo contiene una contradicción, el resultado queda
   marcado como `CONSTRAINT_VIOLATION`; el LLM puede explicar la evidencia, pero
   no puede borrar la señal de gobernanza."*

**Gaps restantes:**

- ⚠️ Sustituir el store en memoria por un triplestore local reproducible sólo
  si aporta valor verificable; el contrato de evidencia ya está desacoplado.
- ⚠️ Validar L10 con un corpus mayor y relaciones extraídas desde documentos
  reales, manteniendo aprobación antes de promoción canónica.
- ⚠️ Después de L10: OpenMetadata local real y observabilidad/evals local;
  AWS live queda pospuesto hasta contar con créditos o una necesidad laboral.

---

### 2026-09-23 — L11 Governed Sandbox Layer

**Fase:** L11
**Estado:** `VERIFIED` para el backend local restringido y sus receipts; el
aislamiento OS de red sigue `NOT_RUN`.

**Qué entendí:**

Autorizar una acción y limitar técnicamente su ejecución son capas distintas.
El `Permit` decide autoridad, pero no debe convertirse automáticamente en
acceso al filesystem, shell, Git o red. El `ExecutionGateway` debe exigir una
request tipada y el `SandboxManager` debe derivar un perfil efectivo que sólo
pueda reducir la autoridad del permit.

**Qué implementé:**

- `src/sandbox/specification.py`: capabilities, perfiles, límites y política de
  red explícita.
- `src/sandbox/filesystem.py`: workspace boundary, resolución de symlinks,
  traversal denial y write allowlist.
- `src/sandbox/backend.py`: `LocalRestrictedBackend` con `shell=False`, pytest
  tipado, Git read-only, timeout, límites de salida y filtrado de entorno.
- `src/sandbox/manager.py`: validación de permit, derivación de perfil y
  receipt para éxitos, fallos, timeouts y denegaciones.
- `src/execution/gateway.py`: frontera única que no acepta efectos sin
  `SandboxRequest`.

**Evidence:**

`tests/test_sandbox.py` aporta 14 checks. `scripts/run_sandbox_local_validation.py`
ejecuta seis receipts en un workspace temporal: lectura, traversal denial,
write scope, pytest tipado con secreto filtrado y fail-closed de aislamiento
OS. El resultado queda en `evidence/sandbox_local_restricted.md`.

**Interview explanation:**

*"Separé autoridad de contención técnica: BAGO autoriza mediante un Permit,
ExecutionGateway obliga a una request tipada y SandboxManager materializa un
perfil que no puede aumentar capacidades. El backend local bloquea escapes de
ruta, shell arbitrario, Git de escritura, timeouts y credenciales heredadas;
cuando se pide aislamiento OS que no existe, falla cerrado y lo evidencia."*

**Gaps restantes:**

- ⚠️ `LocalRestrictedBackend` no es Windows Sandbox ni un contenedor: no se
  presenta como aislamiento fuerte de proceso o red.
- ⚠️ Falta conectar la observabilidad/evals local al trace completo y ejecutar
  una demo E2E pública reproducible.
- ⚠️ AWS live continúa pospuesto hasta créditos/free tier o una necesidad laboral.

