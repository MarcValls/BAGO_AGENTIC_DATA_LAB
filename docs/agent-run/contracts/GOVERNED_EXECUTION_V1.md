# ADL Governed Execution — contrato normativo v1 (candidato)

**ID:** ADL-GEX-V1 · **Estado:** PREPARED / NOT_FROZEN / NO_GO
**Repositorio base inspeccionado:** MarcValls/BAGO_AGENTIC_DATA_LAB, main@79149cdbc4174103a351ba454c3e71a50034d056.
**Ámbito:** agent.run con efectos. Una sola inferencia sin herramientas pertenece a otro contrato y no activa este servicio.

Este documento es una propuesta normativa **subordinada** al canon de .bago/canon. Las contradicciones con el canon se elevan mediante una change request antes de FREEZE. No implica disponibilidad, implementación, auditoría aprobada ni identidad de producción. Las condiciones MUST son criterios de aceptación futuros; SHOULD exige excepción documentada.

## Objetivo y fronteras de confianza

El planificador LLM solo emite propuestas estructuradas. API/Auth y backend resuelven identidad, workspace y agente; Registry+Policy deciden elegibilidad; Approval Service obtiene decisión humana fuera del estado editable del agente; Permit Authority firma un permiso restringido; Worker verifica y reclama; ExecutionGateway+SandboxManager despachan únicamente operaciones locales tipadas; adaptadores registrados median operaciones externas; Evidence Ledger registra hechos; un evaluador ADL independiente verifica los hechos. Ni WebSocket, ni interfaz, ni LangGraph, ni MCP discovery, ni receipt del ejecutor conceden autoridad.

### GEX-01 — Identidad y workspace (P0)
MUST: autenticar principal humano/servicio con credenciales comprobadas por el backend; resolver agent_id, workspace_id, scope, ruta canónica y autorización de pertenencia sin aceptar esas identidades desde propuesta LLM o cabeceras sin autenticar. La validación Origin/CORS no es autenticación. MUST ligar session_auth_id, identity_provider, principal_id, tenant/workspace ACL revision y authz epoch. Sin identidad de confianza: DENIED, sin llamar a tool.

### GEX-02 — Sobre completo e inmutable (P0)
MUST: persistir antes de pedir aprobación un request envelope con schema_version, run_id, trace_id, request_id, nonce, issued_at/valid_until, los siete campos heredados de ExecutionRequest (request_id, tool_name, effect_type, parameters, proposed_by, context_revision, timestamp), principal y agent resueltos, workspace id/root/repo/branch/commit/context binding, tool id/version/schema_digest/registry_revision/adapter id, classification de efecto, límites y política id/revision/digest. MUST preservar exactamente los tipos de argumentos, sin coerción posterior ni campos implícitos. Solo el backend puede aportar identidad y root. Campos desconocidos, duplicados o ambiguos: DENIED. Cambio de cualquier campo normativo => nueva propuesta y huella.

### GEX-03 — Huella canónica íntegra (P0)
MUST: validar el esquema antes de canonicalizar; restringir a I-JSON válido (sin claves repetidas, NaN, Infinity, enteros fuera del rango interoperable o Unicode inválido), normalizar timestamps a UTC explícito y rechazar datos no canónicos según el perfil de serialización. Canonicalización RFC 8785 (JCS), bytes UTF-8; digest completo hex SHA-256 del prefijo ASCII "ADL-GEX-REQUEST-v1\n" seguido de bytes JCS de todo el sobre. MUST almacenar bytes/código de algoritmo o formato inequívocos para reproducir el digest entre lenguajes. SHA-256 prueba integridad comparativa, NO autenticidad. ExecutionRequest.to_hash() actual no cumple.

### GEX-04 — Registro de capacidades explícito (P0)
MUST: registro administrado por backend con tool_id, versión inmutable, JSON Schema de argumentos (additionalProperties:false), efecto, clasificación de riesgo, límites, workspace scopes, requisito de aislamiento, adaptador, salida de red y estado. Solo ACTIVE+HEALTHY+CONNECTED con versión/digest exactos es elegible; discovered, unknown, disabled o schema drift => DENIED. Un catálogo de marketing no constituye registro autorizado.

### GEX-05 — Política determinista (P0)
MUST: decisión explícita sobre principal, sesión, agente, workspace, ACL revision, tool/version, parámetros, efecto, permisos por recurso, contexto, restricciones, red e aislamiento. DENY por defecto; política y estado de capacidad se reevaluarán antes de dispatch. Auto-permit solo para capacidades con política específica y efectos seguros comprobados; no existe habilitación por defecto en v1. Un score de riesgo no concede permiso.

### GEX-06 — Revisión humana exacta (P0)
MUST: UI muestra operación, recurso, parámetros relevantes (redactados sin esconder el efecto), efecto esperado, destino, tool/version, workspace, alcance, límites, expiración y huella completa recuperados desde snapshot inmutable del backend. La identidad de quien aprueba debe estar autenticada y facultada para esa operación en el momento de aprobar. MUST persistir APPROVED o REJECTED, actor, tiempo, razón opcional y request_hash; aprobación de un texto genérico o de la salida del LLM no vale. Cualquier edición genera un nuevo request_id y exige nueva decisión.

### GEX-07 — Permiso verificable (P0)
MUST: Permit v1 (adaptar DTO existente) tendrá permit_id/jti aleatorio, request_hash SHA-256 completo, principal_id, agent_id, workspace_id, tool id/version, efecto, scope, límites, policy revision, authz epoch, issued_at, expires_at, audiencia worker y key_id. El servicio de autoridad firma la serialización canónica con Ed25519 usando biblioteca auditada y clave privada fuera del agente/worker. El worker verifica firma, key_id, audiencia, vigencia, revocación y correspondencia exacta. El campo heredado signed_by por sí solo no es firma. TTL predeterminado <=120 s, límite normativo <=300 s. Rotación/revocación de claves es obligatoria antes de producción.

### GEX-08 — Revocación, cambios y TOCTOU (P0)
MUST: revocación explícita y revisión durable de ACL/policy/tool/workspace en autorización y de nuevo antes del efecto. El worker no acepta concesiones de la cola, solo comprobaciones propias contra autoridad y DB. Si cambia principal, revocación, versiones, workspace binding o permisos entre approval y dispatch: DENIED o REAUTH_REQUIRED, nunca ampliar scope. La garantía exacta del intervalo entre check y efecto requiere backend apto para la operación; no declarar TOCTOU eliminado sin prueba.

### GEX-09 — Consumo durable de uso único (P0)
MUST: transición atomicamente transaccional de permiso ISSUED a CLAIMED y creación de attempt_id + claim evidence antes de efecto. Un único claim exitoso entre procesos/reinicios; UNIQUE permit_id y compare-and-swap por estado. Reintentar claim tras consumo genera REPLAY_DENIED + recibo de rechazo. SQLite WAL sirve para slice local **de proceso único o múltiples procesos coordinados en un mismo archivo local**, nunca multi-host por carpeta compartida. Uso único no es garantía general de exactly-once effect.

### GEX-10 — Intento y despacho (P0)
MUST: attempt_id, idempotency_key, dispatch_intent y lease persistidos antes del dispatch. Separar intento de acción de resultado; commit durable de intent antes de llamar a adaptador. Si falla el commit, el efecto no se inicia. Sólo la política puede permitir reintentos y únicamente cuando se pruebe seguridad de idempotencia del adaptador o que no hubo dispatch.

### GEX-11 — Máquina de estados durable (P0)
MUST: estados y transiciones definidas en tabla posterior, serializados por actualización condicional y con evento append-only transaccional. Ningún cambio a SUCCESS por mensaje WebSocket, timeout, cierre de proceso o aparición de receipt aislado. Idempotencia en transición repetida sin reapertura de permiso.

### GEX-12 — Resultado indeterminado (P0)
MUST: ante caída o timeout después de DISPATCH_INTENT_PERSISTED si no hay prueba verificable de no-efecto, transitar a RECONCILIATION_REQUIRED; bloquear nuevo intento mutante. Reconciliación ejecuta probes autorizados independientes, registra incertidumbre y decisión humana cuando no exista prueba concluyente. MUST diferenciar "receipt no registrado", "tool no ejecutada", "efecto posiblemente ocurrido". Prohibido "sin receipt = no ocurrió" como inferencia factual.

### GEX-13 — ExecutionGateway y sandbox local (P0)
MUST: toda operación local autorizada pasa por ExecutionGateway.execute con ExecutionRequest, Permit validado y SandboxRequest tipado; SandboxManager intersecta permiso, perfil y workspace sin ampliación. El gateway actual solo comprueba request_id y no reemplaza el gate completo. Ruta, alias, symlink/reparse point y archivo cambiado entre check/uso necesitan pruebas de seguridad de recurso. Nunca habilitar shell arbitraria ni ejecución de código no fiable bajo solo restricciones lógicas.

### GEX-14 — Aislamiento proporcional y fail closed (P0)
MUST: declarar backend, threat model y garantías efectivas. LocalRestrictedBackend ofrece restricciones de aplicación y NO equivale a confinamiento SO, egress, CPU/memoria ni resistencia a procesos no confiables. Capacidades que requieren esas garantías siguen UNAVAILABLE hasta usar contenedor/VM/OS boundary verificado y quotas reales. Las operaciones de primera fase se limitan a fixture de lectura preinscrita, sin secretos ni ejecución arbitraria; su autorización también es obligatoria.

### GEX-15 — MCP y red (P1)
MUST: descubierto ≠ registrado ≠ autorizado ≠ conectado. Validar versión, esquema, clasificación, destino, TLS/certificados, credenciales mínimas inyectadas por adaptador y egress proxy/allowlist aplicados fuera del modelo. DNS rebinding/redirecciones sin allowlist efectiva => DENIED. Registro del MCP adapter existente no significa /ws/agents/run conectado. Por defecto red y MCP remoto UNAVAILABLE.

### GEX-16 — Recibos y evidencia de cada transición (P0)
MUST: propuesta, decisión, aprobación o rechazo, claim, dispatch, fallo, replay, timeout, efecto reportado y reconciliación generan eventos durables ligados por run_id, request_id, permit_id cuando existe, attempt_id y trace_id. Receipt del ejecutor incluye version, inputs/outputs hashes, herramienta/adaptador, límite efectivo, estado, effect_claim, error y refs. Event chain append-only con hashes permite detectar modificaciones, no prueba invulnerabilidad sin anclaje externo. Información secreta se redacta y guarda por separado.

### GEX-17 — Verificación ADL independiente (P0)
MUST: separar ExecutorReceipt (afirmación del ejecutor) de VerificationResult (evaluación de ADL). Un verificador con identidad, contexto, versión y método propios contrasta evidencia observable, postcondición e invariantes de capacidades conservadas; un receipt sin verificación no promueve a VERIFIED_SUCCESS. Si la verificación no puede decidir, UNVERIFIED o RECONCILIATION_REQUIRED. UI/Decision Inspector solo proyecta hechos y no autoriza.

### GEX-18 — Concurrencia, recursos y fallos (P1)
MUST: límites por principal/workspace/agente/tool; timeouts por operación, límite de respuesta y tamaño de parámetros; almacenamiento durable + escritura transaccional para metadatos; artefactos grandes fuera de la DB con hash+retención+ACL. V1 es slice local; cola/workers horizontales quedan UNAVAILABLE hasta pruebas de leases, ordering, idempotencia y particiones de red.

### GEX-19 — Compatibilidad y preservación diferencial (P1)
MUST: congelar conjunto previo de capacidades/rutas/contratos visibles; comparar antes/después, incluidas denegaciones, estados, componentes UI y recibos. Una capacidad nueva no compensa quitar otra. No promover cambio solo por test de feature; ejecutar regresión API, Windows y prueba visual Playwright solo donde la superficie cambie. No modificar README excepto mediante scripts/generate_dynamic_readme.py y su --check --skip-tests.

### GEX-20 — Disponibilidad y gates de promoción (P0)
MUST: catalog agent.run, sandbox.execute y mcp.execute siguen UNAVAILABLE / FAIL_CLOSED hasta validación E2E del flujo real identidad→registro→aprobación→firma→claim→gateway→observación→receipt durable→verificación y vectores negativos/restart/concurrencia. Un prototipo de ledger o cambiar etiqueta no basta. El runner de inferencia sin herramientas puede tener estado separado, sin afirmar efecto.

### GEX-21 — API, privacidad y observabilidad (P1)
MUST: API/WebSocket no firma ni ejecuta, mensajes de progreso solo derivados de DB, replay del WebSocket no altera estado ni confiere permisos; acceso a consulta de recibos sujeto a ACL de workspace; resultado sensible no se filtra en logs/traces; identificadores permiten seguir Conclusion → Evidence → Authorization → Trace → Receipt manteniendo fuentes distintas.

### GEX-22 — Gestión de cambios y pruebas (P0)
MUST: vectores de conformidad versionados, con resultados esperados y referencias al código/commit exacto; pruebas reales sobre repositorio y workers distintos de mocks para reclamar integración. Verificador independiente sin reusar lógica que implementa el gate; P0/P1=0, README generator PASS, teamctl handoffs PASS y CRIT explícito antes de FROZEN. Contrato congelado cambia solo por change request aprobada con invalidación de consumidores.

## Máquina de estados de referencia (GEX-11)

| Estado actual | Evento | Estado siguiente | Condición |
|---|---|---|---|
| PROPOSED | policy_deny | DENIED | recibo duradero, 0 dispatch |
| PROPOSED | human_required | PENDING_APPROVAL | snapshot persistido |
| PROPOSED | policy_auto_allow | PERMIT_ISSUED | solo política explícita, no habilitado v1 |
| PENDING_APPROVAL | approve | PERMIT_ISSUED | misma huella, principal autenticado, permiso firmado |
| PENDING_APPROVAL | reject / expire | REJECTED / EXPIRED | recibo de rechazo |
| PERMIT_ISSUED | revoke / expire | REVOKED / EXPIRED | no efecto |
| PERMIT_ISSUED | atomic_claim | CLAIMED | único en DB; intento persistido |
| CLAIMED | persist_dispatch_intent | DISPATCH_INTENT_PERSISTED | commit previo a E/S |
| DISPATCH_INTENT_PERSISTED | dispatch | DISPATCHED | operador tipado validado |
| DISPATCH_INTENT_PERSISTED / DISPATCHED | result_unknown | RECONCILIATION_REQUIRED | bloquear retry |
| DISPATCHED | executor_result | EFFECT_REPORTED | solo afirmación del ejecutor |
| EFFECT_REPORTED | verification_started | VERIFICATION_PENDING | postcondición independiente |
| VERIFICATION_PENDING | evidence_pass | VERIFIED_SUCCESS | evidencia y receipts persistidos |
| VERIFICATION_PENDING | evidence_fail | VERIFIED_FAILURE | conservar efectos que sí ocurrieron |
| VERIFICATION_PENDING | undecidable | UNVERIFIED o RECONCILIATION_REQUIRED | no SUCCESS |
| RECONCILIATION_REQUIRED | reconciled_with_evidence | VERIFIED_SUCCESS / VERIFIED_FAILURE / VERIFIED_NO_EFFECT | evidencia independiente explícita |

DENIED, REJECTED, EXPIRED, REVOKED, VERIFIED_SUCCESS, VERIFIED_FAILURE y VERIFIED_NO_EFFECT son terminales para ese permiso; nuevos intentos requieren nuevas decisiones. RECONCILIATION_REQUIRED y UNVERIFIED no son éxito ni autorizarán reintentos automáticamente. Un DISPATCH intent ya confirmado impide presumir no-efecto sin investigación.

## Slice mínimo elegible, todavía sin integrar

Operación única: READ de un fixture inmutable y preinscrito de test, con ruta específica ligada a workspace autenticado, limitación de bytes y un adaptador tipado mediante ExecutionGateway/SandboxManager; prohibidas rutas arbitrarias, escritura, procesos y red. Primero demostrar denegación de herramientas desconocidas, mutación de argumentos, replay tras reinicio, expiración, revocación, conflicto de identidad, pérdida de DB y crash posdispatch. La implementación futura debe integrar comprobación real de identidad y postcondiciones independientes. El paquete previo F1 de ApprovalLedger solo es una propuesta de pre-ejecución; carece de firma verificable y no satisface GEX-07/GEX-16/GEX-17.

## Bloqueadores de FREEZE

**Conflicto de canon:** .bago/canon/ARCHITECTURE.md afirma «Sin receipt = no ocurrió» y ADR-003 «Lo que no tiene receipt no existe para propósitos de auditoría». Es una regla de reclamación probatoria, pero interpretada literalmente choca con GEX-12: un efecto puede ocurrir antes de perderse el receipt. La corrección exige distinguir «no acreditado» de «no ocurrido» mediante change request, **sin cambiar silenciosamente el canon**.

**Gates pendientes:** autenticación fuerte, firma+verificación de permisos, anti-replay duradero integrado, ledger de intentos/recibos, reconciliación y verificación independiente; coordinación teamctl, ejecutable Windows, retest y README generator. Este documento no afirma haberlos ejecutado.
