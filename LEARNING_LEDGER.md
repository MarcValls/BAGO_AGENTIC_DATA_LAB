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
| L3 | — | — | — |
| L4 | — | — | — |
| L5 | — | — | — |
| L6 | — | — | — |
| L7 | — | — | — |
| L8 | — | — | — |
| L9 | — | — | — |

---

**Última actualización:** 2026-09-21  
**Próxima entrada:** Al completar L2 (ETL Pipeline)

---

### 2026-09-21 — ETL Pipeline Gobernado

**Fase:** L2

**Tests:** 4/4 CRIT P0 passing

**Evidence:** 65 chunks ingeridos, idempotencia verificada, receipts generados

