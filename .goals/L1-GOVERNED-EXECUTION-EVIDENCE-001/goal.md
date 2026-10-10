# Goal — L1 Governed Execution: evidencia suficiente y ligada al código

**Goal ID:** `L1-GOVERNED-EXECUTION-EVIDENCE-001`
**Lifecycle:** `VALIDATED` (auditoría de evidencia local; la fase L1 continúa `PARTIAL`)
**Proyecto:** BAGO Agentic Data Lab
**Rama de referencia:** `codex/l1-governed-execution-evidence-20261010`
**Snapshot inicial:** `aebead4373025c07a4d2c63052890288133d6a4b`

**Candidato final ejecutado:** `defe7b80840082c0ad2749c2ea17af443b87a055`

## Objetivo

Determinar y demostrar, usando los siete casos de `tests/test_l1_governance.py`,
qué garantías de L1 (`LangGraph Governed Execution`) están realmente
implementadas y cuáles siguen siendo ejemplos o afirmaciones sin prueba. La
evidencia final debe estar ligada a un commit y a los archivos exactos; cada
test de referencia debe ejercitar comportamiento del sistema o quedar marcado
explícitamente como `PARTIAL`, `NOT_PROVEN` o `NOT_IMPLEMENTED`.

El objetivo no da por válida la fase L1 por el mero hecho de que sus tests pasen.
Solo se conservará `VALIDATED` para los criterios con pruebas ejecutables contra
el código del grafo y una revisión independiente sin hallazgos P0/P1.

## Tests de referencia

1. `test_langgraph_cannot_execute_directly`
2. `test_permit_reuse_denied`
3. `test_document_without_provenance_rejected`
4. `test_superseded_chunk_filtered_in_retrieval`
5. `test_mcp_tool_unregistered_denied`
6. `test_bedrock_provider_timeout_controlled_failure`
7. `test_governed_agent_graph_end_to_end`

El diagnóstico inicial está en `evidence/REFERENCE_TEST_AUDIT.md`; no eleva
ninguna afirmación de L1 a evidencia suficiente.

## Criterios de aceptación

- **A1 — Identidad:** registrar HEAD, rama, estado del worktree y SHA-256 de
  tests y código cubierto para el candidato final.
- **A2 — Trazabilidad:** mapear los siete casos a la afirmación, símbolo real
  probado, aserciones relevantes y resultado de suficiencia (`PASS`, `PARTIAL`,
  `NOT_PROVEN` o `NOT_IMPLEMENTED`).
- **A3 — Pruebas de comportamiento:** los casos que respalden garantías deben
  invocar el grafo o componentes de producción con entradas adversariales y
  verificar denegaciones, ausencia de efectos/recibos de éxito y errores
  observables. Las comprobaciones de fixtures locales no cuentan por sí solas.
- **A4 — Alcance honesto:** cuando L1 no implemente una capacidad (por ejemplo,
  registro real de herramientas, rechazo de documentos sin procedencia,
  anti-replay persistente o timeout de proveedor), dejarla explícitamente como
  `NOT_IMPLEMENTED`/`NOT_PROVEN`; no simularla para mejorar el resultado.
- **A5 — Ejecución reproducible:** guardar comandos y salidas de la suite L1 y
  regresión pertinente, enlazadas al mismo snapshot final. Fallos y warnings se
  conservan, no se ocultan.
- **A6 — Revisión:** revisión independiente del diff, de los tests y de la
  evidencia; cero P0/P1 sin resolver para cada afirmación que se marque
  `VALIDATED`.
- **A7 — Cierre:** actualizar el estado/evidencia de L1 solo con los criterios
  respaldados. Si faltan pruebas o implementación, cerrar el informe como
  `PARTIAL`, sin promover la afirmación histórica.
- **A8 — README generado:** cumplir la regla general de cierre del repo en
  `AGENTS.md`: ejecutar el generador completo, después la comprobación de
  sincronización, y adjuntar ambos resultados. Nunca editar `README.md` a mano.

## Plan

1. Congelar candidato y auditar los siete tests frente a
   `src/orchestration/state_graph.py`.
2. Diseñar pruebas de integración negativas para las garantías realmente
   implementadas; identificar capacidades que necesitan implementación aparte.
3. Añadir pruebas/evidencias con el cambio mínimo, sin conectar proveedores ni
   realizar efectos externos.
4. Ejecutar suite L1 y regresión afectada; registrar resultados y hashes.
5. Actualizar las fuentes canónicas según la evidencia final, ejecutar el
   generador del README y comprobar que el artefacto queda sincronizado.
6. Ejecutar revisión independiente y emitir el índice final de claims y
   evidencias.

## Restricciones

- No llamar AWS, Ollama Cloud ni servicios externos para probar L1.
- No presentar `execute_actions` simulado como ejecución material real.
- No convertir una aserción sobre datos de prueba en prueba de un control de
  producción.
- No cambiar contratos o fases posteriores L2-L15 como parte de este goal.
- No declarar el goal `VALIDATED` si A1-A8 no están respaldados por el
  candidato final.

## Evidencia inicial

- Referencia ejecutada en el snapshot inicial: **7 passed**, 5 warnings.
- La ejecución acredita que los siete tests corren en este checkout; no demuestra
  por sí sola las garantías de gobernanza descritas por sus nombres.
- El desglose inicial y los hashes están en
  `evidence/REFERENCE_TEST_AUDIT.md`.

## Cierre del objetivo — 2026-10-10

- Estado del goal: `VALIDATED` para la auditoría de evidencia local.
- Estado de L1: `PARTIAL (local evidence)`; no se eleva a VALIDATED.
- Candidato/commit: `defe7b80840082c0ad2749c2ea17af443b87a055` en la rama indicada.
- Suite L1: **8 passed**; regresión sandbox/retrieval/MCP/Bedrock: **40 passed**;
  suite completa: **203 passed**, con un aviso Pydantic V1/Python 3.14.
- La revisión independiente no encontró P0/P1 en los claims PASS con sus límites.
- README generado y `--check --skip-tests` verificado para 203 tests.
- Recibo, límites y hashes: `evidence/l1_governed_execution_20261010.md`;
  salidas: `evidence/l1-governed-execution-20261010/`.
