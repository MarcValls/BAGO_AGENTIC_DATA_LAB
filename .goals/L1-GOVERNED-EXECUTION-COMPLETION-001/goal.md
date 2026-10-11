# Goal — Completar L1: LangGraph Governed Execution

**Goal ID:** `L1-GOVERNED-EXECUTION-COMPLETION-001`
**Lifecycle:** `VALIDATED`
**Proyecto:** BAGO Agentic Data Lab
**Rama:** `codex/l1-governed-execution-completion-20261010`
**Base:** `48f67fdf00a97548f1f40b18f5c2dd23229a54c2`

## Objetivo

Completar la fase L1 implementando y demostrando un flujo end-to-end de
LangGraph gobernado: retrieval con procedencia, propuesta de acción,
confirmación explícita antes de ejecutar, operación local acotada por
`ExecutionGateway` y `SandboxManager`, y verificación mediante recibos. El
resultado debe poder ejecutarse sin servicios de pago y dejar evidencia
reproducible ligada al commit final.

El goal anterior `L1-GOVERNED-EXECUTION-EVIDENCE-001` auditó los tests y cerró
con L1 `PARTIAL`; este goal implementa los gaps de integración. No reabre ni
reescribe aquella auditoría. El `.codex-team/state.json` de la rama pertenece
a la misión ya cerrada Agent Chat Control Plane; se conserva intacto. Este goal
L1 es la misión explícitamente solicitada y su coordinación se materializa aquí.

## Decisiones de alcance de este goal

La auditoría independiente señaló que conectar L4 `GovernedRAG` y L11
`SandboxManager` al grafo amplía la definición histórica de L1. El usuario
seleccionó completar L1 hasta `VALIDATED` “hasta tener evidencias”; por ello,
este goal registra explícitamente esa ampliación para demostrar la cadena
end-to-end, reutilizando L4/L11 sin alterar sus contratos ni promover sus
estados. `ExecutionGateway → SandboxManager` coincide además con el límite de
ejecución material ya descrito por L1 y `LAB_CONTRACT.md`.

La aprobación se demuestra como pausa/resume explícita de LangGraph, vinculada
al hash de la petición y al workspace. Esta prueba local no certifica identidad
de usuario ni autorización autenticada de producción. La demo real queda
limitada al workspace temporal. El entregable “video/demo” del roadmap se
satisface con una demo reproducible, transcripción conservada y recibos
machine-readable; no se afirmará que hay vídeo si no se graba uno.

## Criterios de aceptación

- **A1 — Grafo conectado:** el StateGraph usa `GovernedRAG` y la ruta de
  autorización → `ExecutionGateway` → `SandboxManager`; los caminos productivos
  no sustituyen estas fronteras por fixtures o resultados simulados.
- **A2 - Pausa y confirmación:** LangGraph interrumpe antes de toda acción
  material. Solo reanuda por un canal de aprobación externo al estado editable
  por el agente, con confirmación ligada a un fingerprint canónico de la
  petición completa (parámetros, operación/capability, workspace y scope).
  Falta, expiración o mismatch deja la ejecución denegada. Este gate de
  demostración no prueba identidad/autenticación de usuario.
- **A3 - Efecto gobernado verificable:** una confirmación válida permite una
  operación de escritura local tipada dentro de un directorio temporal de
  prueba; el recibo identifica permiso, request, capability, efecto y resultado
  observado. Pruebas adversariales confirman que la política lógica del sandbox
  deniega escapes de path. No se afirma aislamiento de SO/red que
  `LocalRestrictedBackend` no proporciona.
- **A4 - Rechazo de replay y fallos:** el reuso del permiso es denegado por la
  ruta integrada dentro de la vida del manager. Un timeout/fallo del nodo de
  ejecución produce fallo controlado y recibo de fallo, sin presentar éxito.
  Anti-replay durable tras reinicio queda fuera y se identifica como límite.
- **A5 — Retrieval gobernado:** el grafo usa retrieval real con procedencia y
  filtros de vigencia; faltas de provenance y chunks `SUPERSEDED` no llegan a
  la respuesta como evidencia autorizada.
- **A6 — Casos de referencia:** los siete casos L1 conservan nombres o una
  equivalencia trazable y ejercitan los límites productivos correspondientes.
  MCP y Bedrock permanecen pruebas de sus adapters L5/L6; no se declaran
  integraciones del grafo L1 salvo que una prueba las demuestre.
- **A7 - Evidencia de producto:** existe una demo determinista end-to-end,
  transcripción reproducible, documentación de arquitectura/límites y registro
  de aprendizaje L1. La ejecución genera `LocalTrace` desde el resultado del
  propio StateGraph, enlazando propuesta, aprobación, acción y recibo sin
  sintetizar eventos materiales. Evidencia incluye caso permitido, denegado,
  replay y fallo, con recibos/traza y huellas ligadas al candidato; no se
  inventa evidencia de vídeo.
- **A8 — Validación:** suite enfocada, regresiones afectadas y suite completa
  pasan; README se genera y comprueba; revisión independiente confirma P0=0 y
  P1=0 para los claims L1 marcados `VALIDATED`.
- **A9 — Cierre canónico:** README, manifest, STATE, ROADMAP y matriz reflejan
  `VALIDATED` para L1 solo después de cumplir A1-A8. Si un criterio no se
  satisface, el estado queda `PARTIAL` y se registra el bloqueo/evidencia
  faltante.

## Límites

- Las pruebas y demo no llaman a Bedrock, Ollama Cloud, MCP remoto ni servicios
  de pago.
- Los efectos reales de demostración se limitan a un workspace temporal
  desechable, creado por el test/demo.
- El sandbox local aplica límites lógicos; no equivale a un contenedor ni a
  aislamiento de SO/red.
- No se afirma anti-replay durable entre reinicios/checkpoints si el almacén de
  permisos no lo implementa. No se introduce checkpointing durable como
  requisito implícito de esta fase.
- No se modifican contratos ni estados de L2-L15.
- La rama permanece aislada; no se mezcla en `main` sin petición explícita.

## Plan

1. Congelar contratos de grafo, approval/resume, request/permit y sandbox;
   revisar los límites reales de `GovernedRAG`, `ExecutionGateway` y
   `SandboxManager`.
2. Implementar integración fail-closed y pruebas de los casos permitidos,
   denegados, alterados, replay y fallo/timeout.
3. Probar una demo end-to-end determinista sobre directorio temporal y
   materializar recibos/evidencia.
4. Actualizar docs, learning ledger y fuentes de estado L1; conservar la
   etiqueta `PARTIAL` hasta superar todos los gates.
5. Ejecutar revisiones independientes, tests focalizados, regresiones, suite
   completa y cierre README; corregir hallazgos P0/P1.
6. Registrar hashes/commit final, actualizar el estado del goal y publicar la
   rama con su explicación en la descripción del PR cuando se abra.

## Ejecución y evidencia actual

- Código integrado fijado en `82db27fd4fc613d47f5037cb6fbce58261578373`.
- Demo ejecutada desde ese HEAD; resultados en
  `evidence/l1-governed-execution-completion-20261010/` con cinco casos:
  escritura permitida, aprobación alterada/denegada, replay, escape de
  workspace y timeout de proceso real.
- Suite focalizada después del cambio de timeout: `27 passed`.
- A1-A7: ejecutados/evidenciados en el candidato de código indicado.
- A8: `VALIDATED` - suite completa `210 passed`, suite enfocada `29 passed`,
  README generado y comprobado, `compileall` PASS y review independiente sin
  P0/P1 para los claims acotados.
- A9: `VALIDATED` - `STATE.md`, roadmap, manifest, matriz y README reflejan el
  estado L1 y sus límites.
- El fix de aprobación estricta está en
  `f19ab7f2e1cebf5118989735227911a712c8cc05`; la demo y su transcripción se
  regeneraron desde ese commit. El cierre documental añade esta evidencia sin
  modificar la implementación probada.
