# W01 — Mapa backend para Agent Evaluation Lab

## Identidad y alcance

- Candidato: `codex/adl-agent-evaluation-lab-20261010`.
- HEAD inspeccionado: `1e4d9f930da1225ce61ce27def897f76d57a08fc`.
- Misión: `ADL_AGENT_EVALUATION_LAB_SPIRAL_001`, work item W01, rol `evidence-provenance-engineer`.
- Alcance: lectura estática de API de chat, adaptador Ollama, biblioteca de conversaciones, LocalTrace/OTel, evaluaciones actuales y pruebas/documentos backend relacionados.
- No se leyó configuración local ni almacenes de credenciales. No se inspeccionaron claves, conversaciones reales, agentes creados ni trazas runtime.
- No se editó producto ni se ejecutaron tests, llamadas a Ollama, jobs ni benchmarks. Tests y ejecución real: `NOT_RUN` por el alcance asignado.

## Hallazgos confirmados en el código

### Chat de agente y proveedor real

- `POST /api/agents/{agent_id}/chat` vuelve a cargar el agente del servidor, exige conversación propiedad de ese agente y revisión actual, compone el prompt con el historial persistido y llama `ollama.chat` o el ciclo acotado de lectura opcional. La respuesta incluye `source: "ollama"`; errores del proveedor se devuelven como error y no como respuesta de fixture. (`src/api/server.py:1148-1206`.)
- El agente usa su `model_id` guardado. Si un registro heredado no lo tiene, el servidor resuelve el modelo seleccionado para esa petición sin reescribir el agente. (`src/api/server.py:1173-1174`, también transporte WebSocket en `src/api/server.py:1344-1405`.)
- El adaptador valida el identificador y hace `POST /chat` al endpoint correspondiente a `api_key` o `local_cli`; requiere contenido o llamadas de herramienta, y marca el modelo como llamada correcta solo después de una respuesta válida. La verificación de proveedor/modelo es no generativa y devuelve `generation_performed: false`. (`src/providers/ollama.py:98-148`, `150-259`, `261-294`.)
- La clave de API se guarda mediante el backend de credenciales del sistema operativo; la configuración JSON conserva modo y modelo, no la clave. El adaptador rechaza modo contenedor cuando el almacén del host no es accesible. (`src/providers/ollama.py:48-80`, `98-133`.)
- `POST /api/chat/control` también usa el modelo seleccionado de Ollama para el asistente de app y para generar borradores; el borrador permanece sin guardar como agente hasta confirmación. Esta ruta no produce una traza `agent.chat` actualmente. (`src/api/server.py:968-1070`.)

### Persistencia local

- Conversaciones y mensajes se guardan en SQLite fuera del repo, bajo `%LOCALAPPDATA%/BAGO/AgenticDataLab/conversations/library.sqlite3` por defecto (o `BAGO_CONVERSATION_DB_PATH`). El esquema separa proyecto, propietario/tipo, estado y revisión; los mensajes guardan cuerpo y `references_json`. (`src/conversations/library.py:25-38`, `46-82`.)
- Las escrituras de mensaje usan `BEGIN IMMEDIATE` y `expected_revision`, y fallan ante revisión obsoleta. Se pueden recuperar historial y referencias; `references.trace` puede enlazar el trace id y `references.sources` las lecturas autorizadas. (`src/conversations/library.py:134-188`, `236-241`.)
- Los cuerpos completos de los mensajes sí persisten en esa biblioteca. Por lo tanto, almacenar casos/salidas de evaluación ahí tendría implicaciones de retención y sensibilidad distintas a las trazas actuales; las claves de proveedor no deben copiarse a casos, prompts serializados, historial ni resultados.

### Trazas actuales de chat

- Tras una respuesta exitosa, `_record_agent_chat_trace` genera `trace_id`, `event_id` y `run_id`; crea un único evento `agent.chat` con estado `COMPLETED`, `agent_id`, `provider_id`, `model_id`, duración, `cost_status: not_reported` y referencias de archivos leídos. La traza tiene `evidence_refs` al agente, no al mensaje, conversación, suite ni caso. (`src/api/server.py:1073-1110`.)
- El JSON LocalTrace se intenta guardar en `.bago/traces/agent-chat/<trace_id>.json`; luego se proyecta por OTLP si `BAGO_OTEL_EXPORTER_OTLP_ENDPOINT` está configurado. En ese caso se devuelve Jaeger trace id/URL si la exportación lo informa. La respuesta HTTP incluye el trace id/estado y enlaza `references.trace` en el mensaje de asistente. (`src/api/server.py:1109-1147`, `1182-1206`.)
- La traza del chat omite deliberadamente el texto de usuario y respuesta, lo que reduce contenido sensible en telemetría, pero significa que una evaluación no puede reconstruir respuesta ni prompt desde LocalTrace. La prueba de fuente verifica la ausencia de esas cadenas en el JSON de traza. (`tests/test_agent_chat_trace.py:33-53`.)
- Se crea traza después del éxito de Ollama. Una excepción de proveedor sale antes de la llamada a `_record_agent_chat_trace`, así que no hay traza terminal de fallo del proveedor en este recorrido. El mensaje del usuario ya se había persistido antes de la llamada; fallo puede dejar turno sin mensaje de asistente. (`src/api/server.py:1157-1191`.)
- El evento actual no incluye `conversation_id`, `message_id`, `suite_id`, `case_id`, `run_id` de evaluación, hash del prompt/entrada, versión/configuración del agente, tokens ni latencia separada de proveedor. La duración observada cubre el intervalo alrededor de `ollama.chat`, pero no discrimina fases. El coste se declara `not_reported`; `LocalTrace.cost_usd` y `EvaluationReport.cost_usd` tienen default 0.0, que no debe interpretarse como coste medido. (`src/api/server.py:1085-1110`; `src/observability/local_trace.py:108-147`; `src/evaluation/local_evals.py:35-64`.)

### Evaluación existente — límite de lo que demuestra

- `src/evaluation/local_evals.py` implementa `LocalTraceEvaluator`: comprueba raíz y etapas de un flujo gobernado, citas de retrieval, linkage de permisos/recibos, efectos no autorizados y opcionalmente recibo de sandbox. Produce `EvaluationReport` determinista enlazado a trace id. No compara texto de respuesta con expected output, no evalúa calidad de chat ni lanza llamadas Ollama. (`src/evaluation/local_evals.py:66-220`.)
- `/api/evaluation` expone la sección `evaluation` del bundle demo precargado; no es una API para crear suite, seleccionar agente, ejecutar casos o persistir resultados de evaluaciones de chat. (`src/api/server.py:342-413`.)
- Las pruebas de observabilidad construyen runs con `FixtureBedrockClient` y llaman a `LocalTraceEvaluator`; son pruebas locales de reglas de trazabilidad/gobernanza, no evidencia de inferencia real de Ollama. (`tests/test_l12_observability.py:34-60`, `130-205`.) La prueba de chat que fija modelo y enlaza trace reemplaza `server.ollama.chat` con lambda y respuesta constante, por tanto tampoco valida la conectividad del proveedor real. (`tests/test_agent_chat_trace.py:11-53`.)

## Mapa de identidad reusable para evals

| Identidad/dato | Ya existe | Límite actual |
|---|---|---|
| `agent_id` | Sí, agente recargado server-side y evento | No hay snapshot/hash/version de configuración del agente por caso |
| proveedor y modelo efectivos | Sí, config Ollama y atributos de evento de éxito | No queda unido a suite/case; evitar leer credenciales |
| conversación/mensajes | Sí, ids, secuencia, contenido y revisión en SQLite | El mensaje persistido no porta identidad de evaluación ni prompt hash |
| `trace_id` y `run_id` | Sí, traza de éxito local y correlación opcional Jaeger | No incluye conversación/caso; los fallos no tienen este registro |
| reglas evaluadas | Sí, checks de gobernanza sobre LocalTrace | No existen assertions de respuesta para chat ni suite/resultados persistentes/API |
| duración/coste/tokens | Duración total y `cost_status=not_reported`; coste default 0.0 | Sin tokens, desglose de latencia ni coste medido |

## Límites recomendados para el diseño

1. Mantener evaluación como lectura/consulta sin autoridad de escritura ni dispatch de jobs. Los inputs esperados/assertions son datos de prueba, nunca instrucciones de herramienta.
2. Fijar agent id, snapshot/hash de configuración y modelo efectivo al inicio del run desde el servidor; registrar suite/version, case id, run id y trace id con un enlace explícito por caso. No depender de inferir estas relaciones por timestamp.
3. Reutilizar Ollama server-side y respuestas auténticas; separar fixture runs y live runs en el esquema/UX/evidencia. No rotular fixtures como generación real. Hacer visible fallo/ausencia de proveedor/modelo/trace como resultado incompleto o fallido.
4. Reutilizar LocalTrace/OTLP, pero enriquecer correlación con ids no sensibles. No guardar prompt/respuesta completa en spans por defecto; almacenar casos/resultados mediante política de retención explícita y sin secretos.
5. Añadir estado/coste/token metadata solo como desconocido/no reportado hasta que proveedor entregue métricas reales. `0.0` no equivale a gasto cero.
6. Las assertions iniciales pueden ser deterministas (contains / excludes / regex acotada / formato), deben indicar que evalúan criterios declarados y no verdad semántica. Un judge LLM no forma parte de este backend existente.
7. Usar la prueba fixture para contrato/error/persistencia y una llamada Ollama independiente para evidencia live solo con modelo y conexión configurados; este trabajo no realizó esa llamada.

## Evidencia y verificación

- Fuente: lectura de los archivos y líneas citados arriba en HEAD `1e4d9f930da1225ce61ce27def897f76d57a08fc`.
- Tests existentes inspeccionados como código; no ejecutados (`NOT_RUN`).
- Ollama/Jaeger configuraciones locales y credenciales: no consultadas; conectividad y modelo disponible: `NOT_RUN`.
- Código de producto: sin cambios en este work item.
