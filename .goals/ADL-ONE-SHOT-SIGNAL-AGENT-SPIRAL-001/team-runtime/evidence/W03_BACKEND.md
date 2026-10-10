# W03 — Auditoría backend: agentes de un solo uso y espera de señal

## Identidad y alcance de evidencia

- Misión: `ADL_ONE_SHOT_SIGNAL_AGENT_SPIRAL_001`, work item `W03`, rol `backend-auditor`.
- Candidato: rama `codex/adl-agent-evaluation-lab-20261010`, HEAD `1e4d9f930da1225ce61ce27def897f76d57a08fc`.
- El snapshot inicial de W01 registró 79 entradas previas en el worktree y sus fingerprints. Este audit no cambia fuentes de producto. Las referencias siguientes corresponden al estado de trabajo observado, que incluye cambios preexistentes respecto al HEAD.
- Alcance de lectura: API, capacidad, persistencia, ejecución, sandbox, jobs, conversaciones, orquestación, observabilidad y tests existentes.
- Método: inspección estática de fuentes y tests ya presentes. **NOT_RUN:** pytest, lint, build, API/runtime, Ollama, señal/webhook/polling, LocalTrace/Jaeger. Este item autorizó auditoría de solo lectura, no ejecutar flujos.

## Resultado ejecutivo

1. **Creación y persistencia de perfil — IMPLEMENTED.** `POST /api/agents/create` valida la configuración/proveedor/modelo y guarda un JSON del agente mediante archivo temporal + `os.replace` (`src/api/server.py:1123-1140`, `895-909`). Es una definición persistida; no crea una suscripción a eventos, un trabajo, permiso o ejecución.
2. **Chat real y biblioteca — IMPLEMENTED como conversación/model inference.** `POST /api/agents/{agent_id}/chat` carga un agente existente, valida la propiedad de conversación y revisión, persiste el turno, llama Ollama y enlaza referencias/traza (`src/api/server.py:1356-1414`). El prompt del chat niega app-control, escritura y ejecución (`1375`). No se debe confundir una conversación con un job de agente.
3. **Agente de un solo uso — PROPOSED, aún no modelado.** No hay en `AgentConfig` un campo de lifecycle, límite de ejecución/uso, expiry, estado consumido, ni consumo atómico de la definición; los campos son nombre, descripción, tipo, prompt, provider/model, tools, retrieval y sandbox profile (`src/api/server.py:102-122`; creación en `189-219`). El flujo de guardado persiste el perfil sin lifecycle (`895-909`). El chat permite turnos sucesivos con conversación (`1356-1414`).
4. **Agente en espera de señal — PROPOSED; fuente/runtime no conectados.** La búsqueda de backend actual no identificó endpoint ni módulo de ingreso de trigger, webhook, evento o polling que active agentes. El registro de agente no declara origen/tipo de señal (`src/api/server.py:102-122`, `895-909`); la API de chat solo se inicia ante petición explícita (`1356-1388`). `src/orchestration/state_graph.py` no es evidencia de watcher: es un grafo de demo con decisiones/efectos simulados (ver abajo).
5. **Ejecución gobernada — componentes IMPLEMENTED como módulos, pero DISCONNECTED de la app.** El catálogo describe `sandbox.execute` como `UNAVAILABLE / MODULE_PRESENT_NOT_CONNECTED` y `agent.run` como `UNAVAILABLE / FAIL_CLOSED`, sin invocación ni jobs (`src/capabilities/manager.py:61-119`). `/ws/agents/run` devuelve `execution_unavailable` y afirma explícitamente que ningún job se inició/registró (`src/api/server.py:1530-1547`). Test existente expresa esa respuesta (`tests/test_agent_execution_unavailable.py:6-17`); no lo ejecuté.
6. **Autorización de actores — no conectada como identidad autenticada del producto.** `ExecutionRequest` guarda `proposed_by` (identificador de herramienta/agente), no actor humano autenticado; `Permit` tiene `signed_by`, expiración y restricciones (`src/orchestration/state_graph.py:44-76`). El endpoint de propuesta no registra actor; la ruta limita crear propuesta a operación explícita y aclara que no genera permiso/job/ejecución (`src/api/server.py:1032-1050`). WebSocket valida `Origin` contra allowlist local y no identifica actor (`371-378`). Esto es un límite observado del API local, no una afirmación sobre seguridad externa a este candidato.

## Mapa de seams actuales

### Configuración y almacenamiento

- Los agentes viven en `agents/created/<id>.json`; `_write_agent` usa archivo temporal exclusivo, flush/fsync y reemplazo atómico (`src/api/server.py:895-909`; ruta declarada en `70`). **No** hay tabla de jobs/lifecycle asociada al registro del agente.
- Las conversaciones se guardan en SQLite con `project_id`, `owner_kind`, `owner_id`, `status`, `revision`; los mensajes tienen secuencia y referencias (`src/conversations/library.py:14`, `54-78`, `100-111`, `150-187`). Esto da un seam útil para asociar un run/evento a una conversación, pero no es almacenamiento del ciclo de vida de una automatización.
- Capability proposals tienen SQLite persistente por workspace, fingerprint de capacidad, status `PENDING_REVIEW/CANCELLED/EXPIRED`, revisión, timestamps y eventos `PROPOSED/CANCELLED/EXPIRED` (`src/capabilities/manager.py:138-180`). Se crean con UUID, transacción `BEGIN IMMEDIATE`, vencen a siete días y cancelan con revisión condicional (`222-280`). Esto modela propuestas revisables, **no** definiciones de agentes, permisos activos, suscripciones o ejecución. UUID evita colisión de ID, pero no constituye deduplicación idempotente de una señal/reintento.

### Disparo, actor y transición a ejecución

- No existe una tabla `agent_runs`/`subscriptions`/`triggers` ni estado persistente `WAITING`, `TRIGGERED`, `RUNNING`, `CANCELLED`, `EXPIRED` para estos objetivos en los módulos auditados. **Conclusión de inspección estática**, no prueba de ausencia fuera del alcance revisado.
- La API de propuestas es una frontera útil de revisión: el modelo no es encaminado a ese endpoint y la creación no concede autoridad (`src/api/server.py:1032-1050`). Cancelar proposal requiere ID de forma y revisión; la respuesta declara que no creó ejecución (`1053-1061`). No existe endpoint de cancelar job/ejecución de agente en el mapa de rutas.
- `ExecutionRequest` enlaza request id, tool, efecto, parámetros, proponente, revisión de contexto y timestamp (`src/orchestration/state_graph.py:44-57`). `Permit.is_valid` comprueba ventana temporal (`61-76`). El `ExecutionGateway` exige `SandboxRequest` tipado y correspondencia de `request_id`, y deriva a sandbox (`src/execution/gateway.py:12-41`). El gateway no es llamado por `/ws/agents/run`, lo que coincide con el catálogo fail-closed.
- `SandboxPolicy.derive` comprueba presencia/decisión/vigencia de permit, coincidencia request, perfil, raíz workspace, capability, write scope, timeout y red (`src/sandbox/manager.py:83-159`). `SandboxManager` consume permits una sola vez mediante set+lock **en memoria de esa instancia** (`162-187`); esto previene replay en esa instancia/proceso, pero no da consumo persistente/idempotencia frente a reinicio o varias instancias.
- El state graph legacy no se debe tratar como autoridad de producto: para lecturas y APIs produce permits en memoria (incluye reglas demo y constraints) (`src/orchestration/state_graph.py:256-320`); luego crea recibos con `mock` effect, evidencia fija y aleatoriedad (`323-362`). Clasificación: **FIXTURE/DEMO**, no ejecución gobernada conectada.

### Jobs, cancelación, recibos y observabilidad

- `jobs/__init__.py` persiste archivos JSON en `jobs/history` (`11-12`, `36-50`) y expone listado/lectura (`55-72`), pero las rutas que crean jobs observadas son `/api/demo/run` y `/ws/demo/run`, ambas ejecutan `demo.py` (`src/api/server.py:526-599`, `607-690`). Los jobs creados llevan `agent_id=None`, `job_type="demo"`; son **jobs de demo**, no trabajos de los perfiles.
- `/ws/demo/run` crea un job antes de recibir el mensaje y, al desconectarse, captura `WebSocketDisconnect` sin cancelar explícitamente el subprocess ni finalizar el job (`src/api/server.py:607-678`). No generalizar esta mecánica a un runner de agentes; señala que el MVP nuevo deberá diseñar desconexión/cancelación del proceso y cierre del estado por separado.
- `SandboxReceipt` captura request/permit/sandbox/capability/status, modo filesystem/red, duración, exit code, timeout, hashes de salida/errores y evidence refs (`src/sandbox/receipt.py:36-83`). `SandboxManager` construye recibos también para denegaciones (`src/sandbox/manager.py:234-260`, `272-316`). En estas fuentes los recibos son valores retornados; no aparece un repositorio durable de recibos ligado a un job/lifecycle.
- El chat persiste LocalTrace bajo `.bago/traces/agent-chat` y exporta OTLP si está configurado (`src/api/server.py:1281-1353`); el trace contiene agente/provider/model y rangos de lectura, y responde con estado/traza (`1356-1414`). Es evidencia de chat/model inference, no de proceso ejecutado. No ejecuté export ni consulté Jaeger en W03.

## Implicaciones para el contrato W04

- Mantener claramente tres recursos separados: `AgentDefinition` (perfil), `AgentActivation` o `AgentRun` (una ejecución/concesión), y `TriggerSubscription` (espera a señal). No convertir un perfil persistido o `conversation_id` en autoridad para ejecución.
- One-shot requiere definición de alcance/tarea, vencimiento, estado terminal, máximo de activaciones (uno), dedupe key/request fingerprint, claim transaccional para impedir dos consumidores simultáneos, política de retry y resultado verificable. El “una sola vez” debe ser una propiedad durable y testeada; `SandboxManager._used_permits` en memoria no satisface esto.
- Signal-waiting requiere elegir fuente/evento concreta antes de crear watcher: autenticación/verificación de emisor, validación de esquema y workspace/agent destinatario, persistencia de cursor o dedupe key, protección contra replay, expiración y pausa/cancelación. Ningún tipo de señal queda seleccionado por esta auditoría.
- Para ambos: guardar actor/autor de creación y la base de autoridad por separado de `proposed_by` y del `signed_by` genérico; la app local actualmente no muestra una identidad de actor autenticada en estos handlers.
- Al activar una señal, crear un run durable y correlacionar `agent_id`, activation/subscription, signal ID, actor/policy decision, permit, job, sandbox receipt, conversation (si corresponde), LocalTrace y proyección OTLP/Jaeger. Export de trace no debe servir como permiso.
- Mantener Run fail-closed hasta que una capacidad elegible y un permit emitido por una autoridad conectada lleguen al gateway/sandbox y el receipt/job queden recuperables después de reinicio.

## Clasificación de evidencia

| Afirmación | Estado | Base |
|---|---|---|
| Crear y persistir perfiles de agentes | IMPLEMENTED | `src/api/server.py:895-909`, `1123-1140` |
| Chat persistido con inference y LocalTrace | IMPLEMENTED para chat | `src/api/server.py:1356-1414`, `1281-1353` |
| Persistencia de propuestas cancelables/expirables | IMPLEMENTED, solo propuestas | `src/capabilities/manager.py:138-180`, `184-280` |
| Gateway y sandbox tipados | IMPLEMENTED como módulos; DISCONNECTED del Runner | `src/execution/gateway.py:12-41`, catálogo `src/capabilities/manager.py:99-119` |
| `/ws/agents/run` ejecuta agentes | UNAVAILABLE / FAIL_CLOSED | `src/api/server.py:1530-1547`; test presente no ejecutado |
| Lifecycle de one-shot | PROPOSED | no hay modelo/run record ni límite durable de activación en configuración/handlers citados |
| Trigger/evento para agente waiting | PROPOSED; ingreso no conectado | sin endpoint/watcher localizado en alcance de auditoría; chat es request/response |
| Recibos `mock` del StateGraph | FIXTURE/DEMO | `src/orchestration/state_graph.py:323-362` |
| Cancelación/idempotencia durable de ejecución | NOT IMPLEMENTED en seams revisados | solo revisión optimista de conversaciones/propuestas; permits consumidos en set volátil |
| Runtime, integración de señal, Jaeger o pruebas W03 | NOT_RUN | auditoría estática read-only |

## Next consumer

W04 puede sintetizar el contrato de estados y preparar un siguiente packet **de diseño** antes de implementar. Open choices que siguen `PROPOSED`: señal/source y esquema; si one-shot es perfil temporal o activación/run separado; identidad/autorización de actor local; caducidad y cancelación; retry/DLQ; semántica de exactly-once vs at-least-once + idempotencia; retención de jobs/receipts y alcance workspace. No habilitar ejecución ni anunciar monitorización a partir de este audit.
