# W04 - Contrato de ciclo de vida para agentes one-shot y signal-waiting

## Identidad y alcance

- Misión: `ADL_ONE_SHOT_SIGNAL_SPIRAL_001`, work item W04.
- Candidato inspeccionado: worktree `BAGO_ADL_agent_evaluation_lab_20261010`, rama `codex/adl-agent-evaluation-lab-20261010`, HEAD base `1e4d9f930da1225ce61ce27def897f76d57a08fc`.
- Fuentes de síntesis: `W01_SCOPE.md`, `W02_FRONTEND.md` y `W03_BACKEND.md`. El candidato ya tenía cambios sin commit al iniciar; los informes citan rutas/líneas y, donde corresponde, hash del contenido observado.
- Tipo de trabajo: síntesis de auditorías estáticas. No se editaron fuentes de producto ni se ejecutó un agente de aplicación.

## Estado comprobado

- **IMPLEMENTED:** chat inicial, propuesta/creación explícita y persistencia de definiciones de agentes; conversaciones persistentes; propuestas de capacidades revisables; LocalTrace de la conversación.
- **DISCONNECTED / FAIL_CLOSED:** `ExecutionGateway` y `SandboxManager` existen como módulos, pero no están conectados al Runner; `/ws/agents/run` responde no disponible. No hay ejecución gobernada disponible por el mero hecho de guardar un agente.
- **FIXTURE/DEMO:** los receipts del StateGraph legacy y los jobs demo no acreditan ejecuciones reales de agentes.
- **PROPOSED:** ciclo de vida one-shot, entrada/espera de señales, suscripciones durables, estados de run, cancelación de run y deduplicación durable de activaciones.
- **NOT_RUN:** tests, lint, build, navegador, runtime de API, llamada a Ollama, señales, LocalTrace/Jaeger. Las auditorías son read-only y estáticas.

## Contrato de dominio recomendado

Mantener tres recursos distintos:

1. **AgentDefinition:** perfil revisable y persistido (nombre, prompt, proveedor/modelo, herramientas y alcance). Guardarlo no crea ejecución ni escucha.
2. **AgentActivation / AgentRun:** una activación concreta con actor, petición, política/permiso, estado, expiración e identificadores de job/receipt. El run es la unidad que puede ejecutar efectos y debe permanecer fail-closed hasta conectar autorización, sandbox y gateway.
3. **TriggerSubscription:** configuración durable de una señal, su emisor/fuente, esquema, clave de deduplicación, estado y caducidad. Crear una suscripción no equivale a recibir una señal ni autoriza sus efectos.

### One-shot

Estados candidatos de definición/activación: `draft -> review -> saved -> queued -> running -> succeeded | failed | cancelled | expired`. `saved` significa configuración guardada; nunca significa `queued` o `running`. El claim de ejecución debe ser transaccional y de una sola activación durable. Una repetición de transporte puede devolver el resultado asociado a la misma clave idempotente, pero no crear otro run ni otro efecto.

### Signal-waiting

Estados candidatos de suscripción: `draft -> review -> registered -> waiting -> paused | cancelled | expired`; al recibir señal válida, registrar primero un evento durable y pasar a `queued` solo después de deduplicar y decidir autorización. El run sigue luego sus propios estados. `signal_received` y `authorization_required` son eventos/transiciones, no permisos. La UI solo muestra `registered/waiting` a partir de estado persistido leído del backend; nunca por estado optimista del navegador.

Estos nombres son una propuesta de contrato para la siguiente iteración, no estados ya implementados.

## Invariantes de seguridad y evidencia

- Guardar, editar, revisar o navegar nunca ejecuta trabajo ni registra una suscripción.
- Un actor autenticado y un propietario de workspace deben vincular creación, pausa, reanudación y cancelación. La API inspeccionada no ofrece identidad humana autenticada suficiente; esta decisión precede a acciones con efectos.
- El permiso es distinto de la selección de provider/model, herramientas, trigger o perfil sandbox. Solo una autoridad conectada emite el permit; el endpoint actual de ejecución continúa cerrado.
- Al menos una caducidad explícita y una cancelación durable cubren tanto las definiciones temporales como las suscripciones y runs.
- La entrega de señal se trata como at-least-once salvo que una fuente garantice lo contrario. Aplicar deduplicación persistida por `(subscription_id, source_event_id)` y transacción que cree como máximo un run por evento aceptado. No afirmar exactly-once para efectos externos sin idempotencia del destino.
- Reintentos limitados y observables; distinguir errores recuperables, terminales y cancelación. Política de backoff/DLQ queda abierta hasta seleccionar una fuente de señal y requisitos de operación.
- Persistir relaciones `definition -> subscription/event -> activation/run -> permit -> job -> sandbox receipt -> LocalTrace/OTLP`. Jaeger es proyección de trazas, no autoridad ni prueba suficiente por sí sola de un efecto.
- Los receipts deben poder recuperarse después de reinicio y correlacionarse con el run; los sets de permits en memoria y receipts de demo no satisfacen el contrato.

## Adaptación frontend

- Extender el flujo existente de chat/Builder con una selección explícita de modo solo cuando el backend soporte el contrato. Preservar la revisión/confirmación antes de guardar.
- Presentar definición y actividad en paneles separados. Mostrar origen de señal, alcance, actor, expiración, estado persistido, última entrega/evento y estado/run vinculado.
- No reutilizar `active/archived/deleted` de conversaciones ni `PENDING_REVIEW/CANCELLED/EXPIRED` de propuestas como estado de agente.
- Deshabilitar “Activar/Registrar” con explicación hasta disponer de fuente de señal, identidad/permiso y runner conectado. Run mantiene estado no disponible hoy.
- Las pruebas renderizadas deben verificar que guardar no ejecuta; estados backend-driven al reabrir/refrescar; duplicados; modelo/fuente no disponible; pausa, reanudación, cancelación, expiración y errores.

## Próxima espiral recomendada

**W05 - Decisión de fuente de señal y autoridad, sin habilitar ejecución.** Antes de implementar un watcher, definir con el usuario un primer evento concreto que exista en este proyecto, quién lo puede emitir y verificar, propietario/actor, schema, caducidad, retry y cancelación. El frontend puede preparar el formulario únicamente después de que el backend confirme que esa integración existe. Si no hay una fuente real elegida, seguir con contratos y fixture explícitamente rotulada; no presentar fixture como trigger operativo.

**W06 - Persistencia y API de lifecycle en modo no ejecutable.** Una vez cerradas las decisiones anteriores, implementar definición/versionado, suscripción/run records, endpoints de review/status/pause/cancel, idempotencia durable y pruebas de reinicio/concurrencia. No conectar efectos todavía.

**W07 - Ejecución gobernada end-to-end.** Solo tras definir actor autenticado, autoridad que emite/consume permits y conectar el gateway/sandbox/receipt durable: un caso sintético acotado, autorización explícita, una activación, cancelación/timeout y LocalTrace correlacionado. Comparar UI y Jaeger como evidencia complementaria. Este gate es posterior y no se declara iniciado.

## Decisiones que siguen abiertas

| Decisión | Estado | Motivo |
|---|---|---|
| Primera fuente/evento de señal | PROPOSED | Auditoría no localizó ingreso conectado; no elegir un webhook, cron o señal de chat por inferencia. |
| Identidad y autoridad de actor | PROPOSED | Los handlers inspeccionados no autentican a la persona que autoriza efectos. |
| One-shot como plantilla temporal o run separado | PROPOSED | Recomendación técnica: run separado para conservar perfil y atribución, requiere aceptación de producto. |
| Semántica de reintentos/DLQ y retención | PROPOSED | Depende de la fuente/evento y operación esperada. |
| Límites de duración, concurrencia y coste | PROPOSED | Definir por workspace antes de registrar activaciones reales. |

## Criterio de cierre de esta vuelta

La vuelta de descubrimiento está lista para revisión: las auditorías frontend/backend están enlazadas a fuentes, el contrato conserva el límite fail-closed, y la siguiente decisión está explícita. No constituye implementación ni validación runtime.

## Verificación

- `teamctl handoff` individual W02 y W03: PASS, según sus handoffs.
- `teamctl verify` sobre el runtime aislado: PASS tras los handoffs W02/W03.
- Tests/build/lint/API/Ollama/signals/Jaeger: **NOT_RUN** por alcance read-only.
