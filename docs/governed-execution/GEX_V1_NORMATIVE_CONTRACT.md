# CR-GEX-001 — Contrato normativo de ejecución gobernada v1 (candidato)

Estado: PREPARED / CONTRACT REVIEW REQUIRED. **No es un contrato FROZEN ni una capacidad disponible.**
Base inspeccionada: MarcValls/BAGO_AGENTIC_DATA_LAB, main, commit bdf2be825cfd16b3a9b9435efcb7c2384309cf25 (2026-10-15).
Alcance: identidad, solicitud, autorización, aprobación, permiso, consumo, evidencia y reconciliación. No habilita /ws/agents/run.

## 0. Autoridad y reutilización

Respeta .bago/canon/LAB_CONTRACT.md, .bago/canon/ARCHITECTURE.md y .bago/INDEX.md:
ExecutionRequest → AuthorizationBoundary → Permit → ExecutionGateway → SandboxManager → SandboxReceipt → LocalTrace.
El grafo y el LLM solo proponen; ni el grafo ni el WebSocket conceden autoridad. Mantener separados el runner de **una inferencia sin herramientas** y el servicio de **ejecución de efectos**. La interfaz de inspección proyecta la evidencia sin crearla ni convertirla en autorización.

Mapeo actual y diferencias:
- src/orchestration/state_graph.py: ExecutionRequest, Permit, EffectType y decisiones ALLOW/DENY/REQUIRE_HUMAN existentes. Su ExecutionRequest.to_hash() omite parámetros/contexto y trunca SHA-256; queda **prohibido usarlo para autorización GEX v1**. No se modifica el contrato histórico en esta fase.
- src/orchestration/governed_execution.py: usa una huella SHA-256 local más completa y human interrupt/resume, pero no vincula principal autenticado, agente persistido, versión del registro ni política, y la aprobación local no equivale a firma de producción.
- src/context/workspace_binding.py: reutilizar identidad de repositorio, rama, commit, contexto y fingerprint como atestación de ámbito; no es una credencial ni un permiso.
- src/execution/gateway.py: frontera de efectos locales tipados; src/sandbox/manager.py: política derivada del Permit, sandbox lógico y rechazo de replay **solo en memoria por instancia**.
- src/sandbox/receipt.py y src/observability/local_trace.py: recibos/observabilidad existentes; el ledger transaccional durable y su enlace de causalidad son requisitos nuevos.
- src/adapters/mcp_adapter.py: registro/denegación MCP previos al transporte. Su discovery no equivale a habilitación de la nueva ruta.
- src/api/server.py: /ws/agents/run sigue cerrando con execution_unavailable. Origin check es defensa del navegador, **no autenticación**.
- docs/decision-inspector/contracts/action/decision-action-v1.md: proyección solo lectura de propuesta/decisión/ejecución/recibo; no debe decidir ni fabricar estados.

## 1. Fronteras y actores

1. API/control plane autentica un Principal a partir de una credencial de sesión verificada (o contexto de host SO verificable), carga AgentRecord por ID y resuelve WorkspaceBinding desde estado del backend. Ignora principal_id, workspace_root y privilegios declarados por modelo, cliente o configuración editable del agente.
2. Planificador LLM emite únicamente ToolProposal sin credenciales. No recibe acceso directo a adaptadores, shell, tokens ni ejecutores.
3. Registro backend versionado y explícito asigna a cada capability_id (namespace/nombre), capability_version inmutable, schema_digest y esquema cerrado, effect_type, executor_type, perfil de aislamiento realmente soportado, límites de tiempo/salida/red, health y estado ENABLED/DISABLED/UNAVAILABLE. Discovery no registra ni habilita herramientas. Versión no identificada, estado distinto de ENABLED o falta de backend → DENY antes del efecto.
4. PolicyBoundary decide sobre (principal, agent_record, workspace_binding, capability_version, parámetros validados, efecto, policy_revision, límites). Default DENY. Una autorización de lectura estrecha puede ser automática solo con regla explícita; escrituras, operaciones externas y destructivas requieren aprobación humana según regla. Cambiar política/registro entre aprobación y despacho implica revalidar y denegar o reaprobar.
5. ApprovalService renderiza la operación concreta, rutas/destinos, versión, efecto y límites, incluyendo request_digest. El actor aprueba/rechaza por canal autenticado independiente de estado editable del agente. Una decisión no es un permiso sin emisión transaccional.
6. DurableExecutionStore controla permisos, intentos, trabajos y ledger; cola mueve solo referencias opacas y workers siempre releen del store. No se puede autorizar con payload editable de la cola.
7. LocalToolAdapter usa ExecutionGateway y SandboxManager. MCP remoto solo por adaptador registrado, credenciales de mínimo privilegio, política explícita de egress y cuotas. Sin enforcement de aislamiento de SO/red requerido, capability UNAVAILABLE/FAIL_CLOSED; no llamar sandbox lógico "OS-isolated".
8. EvidenceStore (transaccional + objetos referenciados) es fuente de hechos. LocalTrace/OTel/Jaeger solo proyecciones. UI/WebSocket no inventan ejecución completada.

## 1A. Propuesta anterior a registro (denegación verificable)

ToolProposalEnvelopeV1 lo crea el backend al recibir una propuesta del modelo, **incluso si la herramienta es desconocida**. Incluye request_id, run_id, proposal_id, agent_id cargado del servidor, principal_subject/backend-auth, workspace_binding_fingerprint, requested_tool (no confiable), raw_arguments_sha256 (bytes recibidos con límites de tamaño), received_at y proposal_digest. Este último se calcula con SHA-256 y separación de dominio ADL:GEX:PROPOSAL:v1 sobre el sobre sin el campo de digest, usando JCS. No existe permiso en esta fase.

Si falla registro, esquema, autenticación, ámbito o disponibilidad, se persiste ProposalDenialReceiptV1 con proposal_digest, request_id, decision/error_code, reason y refs del evento. NO inventar capability.version ni registry_digest para poder fabricar un GEXRequestV1; en particular, proposal_digest no se trata como request_digest. Si el ledger está caído, no ejecutar y no fingir que se persistió el rechazo.

## 2. Solicitud íntegra GEXRequestV1

GEXRequestV1 es un **sobre inmutable creado por el backend** que adapta sin borrar los campos del ExecutionRequest histórico; el wire-format aún no está conectado. Los campos vinculados a huella son obligatorios y no admiten null salvo donde el esquema expresamente lo permita:

~~~json
{
  "contract_version": "gex-request/v1",
  "request_id": "uuid-v4-backend",
  "run_id": "run-backend",
  "proposal_id": "proposal-backend",
  "principal": {"issuer": "auth-backend", "subject": "id-autenticado", "session_binding": "digest-sesion", "auth_strength": "verified"},
  "agent": {"agent_id": "id-servidor", "config_digest": "sha256", "revision": "rev"},
  "workspace": {"workspace_id": "id-servidor", "binding_fingerprint": "sha256", "repository_identity": "sin-credenciales", "branch": "branch", "commit_sha": "full-commit", "context_revision": "rev", "root_identity": "server-resolved"},
  "capability": {"id": "filesystem.read", "version": "1", "registry_digest": "sha256", "schema_digest": "sha256", "executor_kind": "local", "effect": "READ"},
  "operation": {"arguments": {"path": "README.md"}, "target": "workspace-relative", "effect_scope": "read-one-file"},
  "constraints": {"sandbox_profile": "read_only_agent", "network": "deny", "timeout_ms": 2000, "max_output_bytes": 65536, "write_scope": "none", "egress_allowlist": []},
  "policy": {"revision": "policy-rev", "policy_digest": "sha256"},
  "context_revision": "snapshot-rev",
  "proposed_at": "2026-10-15T00:00:00Z",
  "expires_at": "2026-10-15T00:02:00Z",
  "nonce": "unico-por-solicitud"
}
~~~

El ejemplo es ilustrativo, no un esquema operativo aprobado; toda cadena "sha256" es un marcador, no un digest válido.

Reglas:
- Todos los campos del sobre, incluyendo todos los argumentos normalizados, identidades backend, policy/registry revisions, destinos, límites, temporales y nonce, entran en la huella. Los adjuntos usan digest de bytes más longitud y content-type, nunca referencias mutables sin hash. Los secretos se identifican por referencia opaca versionada desde el backend, nunca en claro.
- Normalización semántica (rutas, hostname, Unicode, defaults de esquema, unidades) y validación de JSON Schema completo ocurren **antes** de formar el sobre. El objeto ejecutado es el objeto validado, no un segundo parseo de contenido libre. Sin parámetros desconocidos, floats no finitos, claves duplicadas ni estructuras ambiguas. Comprobar paths/symlinks nuevamente en la frontera de ejecución para evitar TOCTOU; cualquier cambio de destino efectivo fuera de alcance se deniega.
- Canonicalización según RFC 8785 (JCS sobre I-JSON), con versión y dominio fijo: request_digest = hex(SHA-256(UTF8("ADL:GEX:REQUEST:v1\n") || UTF8(JCS(GEXRequestV1)))). Nunca usar hashes truncados o serialización default=str para permisos.
- Serialización independiente del idioma/plataforma. Para soporte de números fuera del subconjunto interoperable de I-JSON utilizar strings decimales tipados; rechazar NaN/Infinity. Parser rechaza claves repetidas. Ordenar objetos según JCS, no según orden de llegada.
- request_digest es identificador de integridad, **no** firma ni autoridad.

## 3. Política, aprobación y permiso

PolicyDecisionV1 guarda decision_id, request_id, request_digest, policy_revision, actor/evaluador, result ALLOW/DENY/REQUIRE_HUMAN, reason_code, constraints_effective y timestamp; DENY y REQUIRE_HUMAN no producen permiso. Antes de aprobar, una pantalla muestra JSON semántico validado y un resumen operativo (herramienta, versión, efecto, recurso, destinatario externo, parámetros relevantes, workspace, límites y expiración). La vista debe poder inspeccionar todos los argumentos; los ocultados por secreto no pueden alterar el efecto visible.

ApprovalV1 registra approval_id, request_digest exacto, actor autenticado, principal y workspace de destino, operation_summary_digest, decision APPROVED/REJECTED, issued_at, expires_at, auth_context_ref, evidence_ref y signature/mensaje autenticado del backend. Rechazo se persiste y jamás acuña Permit. Una aprobación del mismo actor no sustituye controles de política. Debe existir separación de deberes cuando la regla lo exija.

PermitV1 se emite en backend desde decisión y aprobación verificadas (o ALLOW automático explícitamente permitido) con permit_id aleatorio no derivado solo del digest, request_digest, principal/session_binding, agent_id/config_digest, workspace.binding_fingerprint, capability id/version/registry_digest, effect_scope, operation_digest, policy revision, límites efectivos, issuer/key_id, issued_at/not_before/expires_at, max_uses=1 y firma/MAC verificable (algoritmo/key_id identificados, llave fuera del estado del agente). No aceptarlo desde un objeto que se limita a incluir signed_by. Revocar una sesión, cambiar policy/registry/binding o vencer ventana impide nuevas ejecuciones. La validación es en servidor/worker con comparación segura y reloj UTC con controles explícitos; evitar prometer tolerancia de reloj silenciosa.

**Inmutabilidad del permiso:** PermitV1 es el conjunto de claims firmado y **no** contiene su estado mutable. PermitUseStateV1 vive en DurableExecutionStore y conserva permit_id, request_digest, state ISSUED/CONSUMED/REVOKED/EXPIRED, uses 0/1, db_version de CAS y consumed_at/attempt_id opcionales. La firma valida los claims inmutables; el CAS valida el estado durable actual. Ningún worker debe reutilizar la copia de estado recibida desde una cola.

## 4. Consumo transaccional y estado

Perfil v1: SQLite local (WAL + synchronous=FULL + foreign_keys=ON + transacciones BEGIN IMMEDIATE); persistencia en disco local, no carpeta compartida ni HA. Tablas lógicas mínimas: requests(request_id UNIQUE, request_digest UNIQUE, snapshot), decisions(decision_id, request_id), approvals(approval_id, request_digest, actor), permits(permit_id UNIQUE, request_digest, status, expires_at, uses), jobs(job_id UNIQUE, request_id, permit_id), attempts(attempt_id UNIQUE, job_id, worker_id, lease_until, state), ledger_events(event_id UNIQUE, request_id, run_id, seq, prev_hash, event_digest, kind, timestamp, payload_ref), receipts(receipt_id UNIQUE, attempt_id, request_digest, observed_status, evidence_refs). Índices y FK obligatorios; los artefactos grandes almacenados por contenido y política de acceso.

Estados de trabajo: PROPOSED → DENIED | AWAITING_APPROVAL | APPROVED (esta última **solo** para política ALLOW explícita y capacidad autoautorizable); AWAITING_APPROVAL → REJECTED | EXPIRED | APPROVED; APPROVED → QUEUED | CANCELLED | EXPIRED; QUEUED → CLAIMED | EXPIRED | CANCELLED; CLAIMED → RUNNING | FAILED | RECONCILIATION_REQUIRED; RUNNING → SUCCEEDED | FAILED | RECONCILIATION_REQUIRED. La terminación SUCCESS es una transición transaccional junto con el recibo observado y persistido; una tarea consumida no puede reencolarse tras crash sin reconciliación. REJECTED, DENIED, EXPIRED y CANCELLED no producen efectos. Cualquier camino debe anexar eventos; rechazos, denegaciones, caducidad, replay y errores producen recibo/evento incluso sin efecto. El estado terminal no se infiere de que el LLM acabó una respuesta.

El worker, **antes de cualquier efecto**, abre transacción y realiza CAS/UPDATE condicional sobre Permit ISSUED, no revocado, vigente, exactamente ligado a solicitud/entorno/registro/política; también reserva attempt_id y anexa CONSUMED + DISPATCH_INTENT al ledger **en la misma transacción**. La confirmación durable precede al efecto; si falla la escritura durable no ejecuta. Los workers duplicados o tras reinicio reciben PERMIT_REPLAY (con evidencia). Si la operación no fue empezada, un operador puede evaluar crear una solicitud y permiso nuevos; nunca reutilizar el anterior.

Una cola no proporciona exactly-once execution. Permiso de un uso garantiza **una reserva de intento autorizada**, no efecto exactamente una vez. Ante interrupción después de DISPATCH_INTENT (incluida pérdida de conexión antes de recibo) marcar RECONCILIATION_REQUIRED de forma conservadora. Nunca reintentar automáticamente efectos no idempotentes; usar claves de idempotencia remotas cuando el proveedor las soporte y consultar su estado antes de reconciliar.

**Excepción inevitable: fallo del almacenamiento.** Si la transacción previa al efecto falla, la ejecución se bloquea y el control plane informa STORE_UNAVAILABLE_FAIL_CLOSED, sin fingir que existe un recibo persistido. La denegación solo puede incorporarse al ledger cuando el almacenamiento se recupere y su procedencia pueda verificarse; la telemetría volátil no se presenta como evidencia durable. Si el efecto pudo ocurrir y falla la persistencia posterior, se exige reconciliación externa y se impide anunciar SUCCESS.

No existe transición a SUCCEEDED sin (a) resultado observado por adaptador, (b) recibo durable enlazado a request_digest + attempt_id, (c) comprobación de alcance y (d) persistencia de la transición. Un recibo SUCCESS aislado no es prueba de cumplimiento de la política. Si no se puede escribir el recibo tras efecto potencial, reconciliar mediante un proceso autorizado, nunca éxito presunto.

## 5. Recibos, integridad y confidencialidad

El ledger emite eventos PROPOSED, POLICY_DECIDED, APPROVAL_REQUESTED, APPROVED/REJECTED, PERMIT_ISSUED, PERMIT_CONSUMED, DISPATCH_INTENT, STARTED, EFFECT_OBSERVED, FAILED/DENIED/TIMEOUT, REPLAY_DENIED, RECONCILIATION_REQUIRED y RECEIPT_PERSISTED. Cada evento enlaza run_id, request_id, digest, proposal_id y, si existen, decision_id, approval_id, permit_id, job_id, attempt_id y sandbox_receipt_id/mcp_receipt_id. Orden por seq asignada de forma transaccional dentro de una solicitud; event_digest = hex(SHA-256(UTF8(JCS(LedgerEventV1 sin el campo event_digest)))) con hexadecimal minúsculo; prev_hash forma parte de ese objeto y no se concatena de nuevo. Para seq=0, prev_hash es null; para cada evento siguiente, seq aumenta en uno y prev_hash es el event_digest del evento anterior de la misma solicitud. La cadena detecta modificaciones pero sin anclaje externo **no demuestra inmutabilidad ante un administrador**.

ReceiptV1 (tras validación completa de GEXRequestV1) requiere receipt_id, request_digest, attempt_id (o causa pre-despacho), tool/capability version, decision/approval refs, status (SUCCESS/FAILURE/DENIED/TIMEOUT/UNKNOWN), observed_effect, error taxonomy, execution-boundary identity, actual_limits, input/output digests, evidence_refs, persisted_at y origin event IDs. Para una denegación posterior a la construcción de GEXRequestV1 pero previa al despacho, permit_id/attempt_id son nulos y se usa decision_id. Para un rechazo previo a registro/esquema, usar ProposalDenialReceiptV1 con proposal_digest, sin afirmar que existe request_digest. El ledger protege datos sensibles; las trazas públicas contienen resúmenes redactados y hashes de artefactos guardados con ACL/retención. Los recibos se incorporan a LocalTrace mediante referencias, sin convertir Jaeger en fuente de autoridad.


**Decisiones CR-GEX-002/003/004/005 (perfil v1):** la interfaz del proveedor de identidad es obligatoria, pero permanece UNCONFIGURED/FAIL_CLOSED hasta un vínculo verificable de autenticación (Origin/localhost no es identidad); el ledger/permiso usa SQLite local con CAS transaccional; la primera capacidad elegible será una lectura tipada y acotada de fixture inmutable bajo workspace controlado por backend, sin subprocess/red; Decision Inspector solo proyecta el estado persistido. Detalle de decisiones y riesgos: `docs/governed-execution/CR_GEX_002_005_RESOLUTIONS.md`. La elección de estos contratos no demuestra su implementación.

**Verificación del emisor:** la firma de PermitV1 debe cubrir, con dominio `ADL:GEX:PERMIT:v1\n`, todos los claims excepto `signature` según JCS, incluida versión de contrato, algoritmo y key_id. El servicio de validación debe seleccionar una clave server-side del keyring por issuer/key_id, aplicar comprobación criptográfica en tiempo constante donde corresponda y rechazar algoritmos/keys no permitidos, firma alterada y cambios de scope. El estado mutable no forma parte del objeto firmado. ApprovalV1 tiene dominio de firma separado (`ADL:GEX:APPROVAL:v1\n`). Las claves no pertenecen al prompt, agente, WorkspaceBinding ni a los recibos.

## 6. Gates de capacidad y despliegue

- Antes de conectar /ws/agents/run: identidad autenticada y workspace resuelto por backend, registro tipado versionado, canonicalización validada por vectores, firma verificada, aprobación concreta, anti-replay durable, ledger de propuestas/denegaciones/fallos y recuperación; al menos un backend que imponga efectivamente los límites de la capacidad habilitada. Ninguna de estas garantías se hereda automáticamente de L1 local.
- Capability local de solo lectura podrá estudiarse como primer vertical slice SOLO si los controles reales son suficientes para ese efecto. Para código arbitrario, pruebas con procesos o red y efectos externos exigir aislamiento/egress según riesgo. Denegar shell arbitraria, capacidad desconocida, red sin allowlist, mutaciones sin permiso, secretos generales y scope widening.
- Control plane/WebSocket, workers, adaptadores y store son responsabilidades separadas; la primera implementación puede funcionar en un solo nodo **manteniendo interfaces separadas**, no confundiendo una DB local con HA o escala horizontal.
- Catálogo de ejecución gobernada: UNAVAILABLE / FAIL_CLOSED; /ws/agents/run: sin cambios. Runner de inferencia sin herramientas: contrato y disponibilidad independientes.
- No promover a FROZEN hasta consistencia con canon y contratos de inspección, prueba de vectores, revisión independiente P0=0/P1=0 y handoff verificado mediante teamctl. No promover a AVAILABLE hasta tests reales de identidad, permiso, sandbox, persistencia, errores, reinicio y reconciliación.

## 7. Compatibilidad, migración y decisiones abiertas

CR-GEX-001: mantener ExecutionRequest y Permit históricos para sus demos; no añadir alias engañosos ni considerar su to_hash/signed_by suficiente. Introducir adaptador validado a GEXRequestV1/PermitV1 cuando exista implementación y comprobar igualdad de request_id, tool, effect, parameters y scope. No permitir fallback permisivo si algún campo de seguridad no está disponible.

CR-GEX-002/003/004/005: decisiones de arquitectura acotadas registradas en `CR_GEX_002_005_RESOLUTIONS.md`; sus implementaciones de autenticación, claves, transacciones, aislamiento y proyección **no están demostradas**. Todo perfil sin controles verificados queda `UNAVAILABLE / FAIL_CLOSED`. Estas decisiones no autorizan rebajar el contrato.

Ver esquema estructural (no autorización operativa) en docs/governed-execution/GEX_V1_SCHEMA.json y vectores de conformidad en docs/governed-execution/GEX_V1_CONFORMANCE_VECTORS.json y evaluación de brechas en docs/governed-execution/BASELINE_AND_GAPS.md.
