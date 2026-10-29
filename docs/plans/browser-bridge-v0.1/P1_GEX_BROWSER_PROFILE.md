# P1 — Browser Bridge: contratos de autorización, capacidades y conformidad

**Estado:** P1_CONTRACT_CANDIDATE · MATERIALIZADO PARA REVISIÓN · NO FROZEN  
**Fecha:** 2026-10-29  
**Base revisada:** main @ 1ebf9b1b2c5cd75de8dd34dddb0cc581588327c4  
**Plan receptor:** PR #100, rama docs/browser-bridge-plan-20261029  
**Alcance:** especificación tipada, modelo de estados y pruebas de contrato, no implementación de Chrome ni activación del ejecutor.

## 1. Dictamen de compatibilidad

Se inspeccionaron los contratos reales antes de proponer una extensión:

- docs/governed-execution/GEX_V1_SCHEMA.json: CapabilityRegistrationV1 y Capability admiten únicamente executor_kind local o mcp; GEXRequestV1 requiere agent.
- src/execution/gex_control.py: plano de control durable especializado en fixture.read, con política de aprobación y network=deny.
- docs/governed-execution/GEX_V1_NORMATIVE_CONTRACT.md: estado PREPARED / CONTRACT REVIEW REQUIRED, sin garantía de que sea un runtime general; los efectos requieren consumo/dispatch durable y reconciliación.
- src/contracts/domain_conformance.py: adaptador read-only; sus resultados explícitos authorization_granted=false, activation_performed=false, persisted=false.
- docs/domain-conformance/source/03_DOMAIN_CONFORMANCE_TEST_v1.0.md y 05_DOMAIN_MANIFEST.schema.json: 13 controles obligatorios de conformidad, candidate-bound y vinculados a handoffs de teamctl.
- .bago/team/kit/protocol/TEAM_PROTOCOL.md: cambios sobre contratos compartidos requieren revisión, handoffs y gate terminal; no inferir DONE por documentos.

**Decisión P1-D01:** NO añadir browser_native a la enumeración de GEX v1 ni reinterpretar local/mcp como control de Chrome. NO fabricar un agent_id para acciones manuales. La implementación necesitará una extensión versionada del registro y solicitud (perfil de GEX v2 o subtipo explícito revisado), con iniciador autenticado HUMAN o AGENT, y un único ledger GEX existente. Si tal extensión no pasa revisión, P4 queda BLOQUEADO, no se ejecuta por una vía lateral.

El contrato nuevo adl.browser.capability-profile.v1 describe esa extensión futura sin mutar ni habilitar GEX hoy. Su executor_kind browser_native es un **tipo pendiente de soporte**, nunca una herramienta reconocida automáticamente por el runtime actual.

## 2. Propiedad de cada decisión

| Objeto | Dueño de autoridad | Qué puede hacer |
| --- | --- | --- |
| chrome.activeTab | Chrome, tras gesto real del usuario | Conceder acceso temporal a la pestaña invocada, según reglas del navegador. |
| SharedTabBinding | Servicio ADL + validación del estado efectivo por la extensión | Asociar pestaña/origen/documento con instancia/proyecto/sesión. No crea un permiso de Chrome. |
| GEXRequest / Policy / Permit | Identidad y autorización GEX del backend | Resolver principal, iniciador, contexto, registro/política y límites; autorizar una operación concreta. |
| Registro de capacidad | Backend GEX, versión y huella fijadas | Habilitar únicamente browser.document.read cuando haya integración y gates. No aceptar autodescubrimiento del host. |
| DISPATCH_INTENT + consumo | Ledger durable GEX existente | Reservar intento único antes de enviar el comando, sin crear otro registro autoritativo. |
| Host y extensión | Transporte y comprobación local | Validar autenticidad del mensaje, Chrome/grant, sesión, tab, documento y límites; jamás emitir permits. |
| Observation | Adaptador de lectura | Informar OBSERVED/DENIED/ERROR y hash del extracto; no equivale a recibo terminal. |
| ReceiptV1 + VerificationResultV1 | GEX y verificador independiente | Registrar efecto observado/durable y postcondición. Una respuesta del host no es VERIFIED_SUCCESS. |
| Conformidad de dominio | Adaptador read-only y checks host-owned de teamctl | Evaluar la candidata; no conceder autoridad runtime ni activar la capacidad. |

### P1-D02 — Dos concesiones independientes

Debe darse una interacción reconocida por Chrome con la extensión, como pulsar su acción. La extensión usará activeTab, no host_permissions globales. El chat, el backend, un registro recordado, un invocation_event_ref o un test no pueden **crear** ese grant. Al ejecutar la lectura debe comprobarse de nuevo su vigencia, pestaña/documento y origen. Si el navegador niega el acceso, el host devuelve una denegación factual.

ADL requiere además una decisión de autorización actual y un permit consumido, ligado a principal, workspace_binding_fingerprint, registro, política, instancia, binding, documento, límites y request_digest. Permisos READ/WRITE de directorios no autorizan una pestaña. La revocación corta nuevas operaciones, no deshace una lectura ya hecha.

### P1-D03 — Contrato de versión y registro

Capacidad inicial exclusiva: browser.document.read v0.1.0; effect READ; executor_kind browser_native; estado inicial DISABLED; backend como único registro de autoridad. Descubrir la extensión no habilita la capacidad.

Se proponen como límites de producto max_output_bytes <= 65 536, timeout_ms <= 5 000, write_scope none y egress de host únicamente a la instancia de ADL emparejada por loopback. La política de red de Chrome **no** queda aislada por ese límite. No reutilizar el perfil read_only_agent de fixture ni degradar su network=deny. Sin aislamiento fuerte demostrado, declarar el límite OS NOT_VERIFIED.

El registro futuro debe versionar también input_schema_digest, registry_digest, policy_revision, host_name, extension_id, constraints y compatibilidad de versiones. Si un digest cambia tras aprobar, DENY y emitir una nueva solicitud, no actualizar el permiso en marcha.

### P1-D04 — Tipos de mensajes cerrados

El archivo P1_BROWSER_SCHEMA.json usa JSON Schema 2020-12 y additionalProperties=false. Sus cinco tipos son:

1. CapabilityProfile: definición descriptiva del registro futuro, sin efecto de habilitación.
2. BrowserGexRequest: **perfil de solicitud versionado v2**, con principal autenticado y un initiator discriminado HUMAN o AGENT; HUMAN no lleva campos de agente, AGENT debe enlazar agent_config_digest y revisión. No sustituye ni altera GEXRequestV1; requerirá un adaptador GEX autorizado en P4.
3. SharedTabBinding: tab_id, extension_id, origin, document_epoch, sesión, proyecto e invocation_event_ref. Este último es una referencia de auditoría, **no una prueba de concesión activeTab**.
4. Dispatch: request_digest, attempt_id, permit_id, dispatch_intent_event_id, registry/policy, binding, document_epoch, límites, nonce, sesión/sequence y message_auth_tag.
5. Observation: OBSERVED/DENIED/ERROR, digest y longitud de lo realmente extraído, fecha y truncation. Nunca contiene SUCCESS o VERIFIED_SUCCESS.

El esquema valida forma, no autenticidad, tiempo efectivo, identidad real del usuario, activeTab ni relación criptográfica con el ledger. La validación semántica y criptográfica pertenece a las autoridades señaladas.

La entrada BrowserGexRequestV2 es un contrato propuesto **backend-generated**. Principal y binding deben derivarse de la sesión autenticada, no del JSON remitido por el modelo. Si el workspace carece de binding válido para GEX, la operación se deniega; no se fabrica una identidad Git ni se usa el permiso de carpetas como sustituto.

## 3. Flujo contractual para P4 (todavía NO IMPLEMENTADO)

1. Usuario comparte la pestaña con gesto de Chrome. Extensión constata el permiso real y comunica binding mínimo por el host; ADL enlaza el binding al proyecto e instancia verificados.
2. Chat general o interfaz manual solicita browser.document.read. El backend resuelve HUMAN/AGENT sin inventar agente para HUMAN, revalida identidad, política, digest, binding y registro versionado.
3. GEX decide según política y aprobación exigida; emite permit de un uso. Sin autorización explícita = DENY. Conformidad de dominio NO es uno de los requisitos que sustituyen el permit.
4. En **la transacción durable del ledger GEX existente**, reservar attempt_id, consumir permit (CAS) y persistir DISPATCH_INTENT. Si falla, fail closed antes del efecto.
5. El servidor envía un comando de lectura tipado por el canal emparejado. El host valida MAC y secuencia, sesión/digest/binding/límites y vigencia. La extensión revalida el grant efectivo de Chrome, origen, pestaña y documento antes de extraer.
6. El host remite Observation con output_sha256 de los bytes efectivamente observados. El backend convierte el resultado a ReceiptV1 únicamente con validación y persistencia durable; nunca recibe un receipt terminal "hecho" por un mensaje de una página.
7. Si GEX recibe y persiste ReceiptV1 correctamente, podrá asignar SUCCEEDED observado; la verificación independiente posterior emite VerificationResultV1 ligado al mismo request_digest, attempt_id, receipt_id y receipt_digest.
8. Si tras DISPATCH_INTENT falta recibo terminal persistido: **UNKNOWN / RECONCILIATION_REQUIRED** (estado de operación), verificación INCONCLUSIVE, sin retry ciego. Un host ACK, timeout, respuesta LLM o reporte CONFORMANT jamás convierte el intento en SUCCEEDED.

La entrega de un receipt terminal de error se distingue de ausencia de receipt: con error factual y recibo durable el estado puede ser FAILED. Una pérdida después de despacho no permite deducir que no ocurrió lectura.

## 4. Canal host-ADL y confianza

El host en Windows se inicia desde la extensión mediante Native Messaging y conecta a ADL por canal autenticado. NO supone que ADL pueda lanzar directamente Native Messaging ni que localhost autentique.

Para el prototipo se exige sesión emparejada, desafío/respuesta con secreto de 256 bits protegido para el usuario Windows, autenticación de mensajes HMAC-SHA256 sobre bytes canónicos del comando (excluido message_auth_tag), identidad de sesión, sequence monotónico y nonce. Usar comparación constante, expiración, rotación al reconectar y claves diferentes para canal y permisos GEX. La elección de canonización exacta, key derivation, persistencia de sesión y tratamiento de reconexiones se someterá a vectores criptográficos revisados antes de activar P2; **el esquema por sí solo no implementa estos controles**.

La extensión no expone al contenido web el canal Native Messaging, tokens o claves. Ningún mensaje de página decide un permiso. El contenido leído es dato no confiable y solo se incorpora al contexto como fuente con procedencia y restricciones.

No existe garantía contra un usuario/administrador Windows malicioso con acceso al perfil; la pareja Chrome/host/OS pertenece a la frontera de confianza local. No afirmar aislamiento OS sin pruebas.

## 5. Conformidad: 13 controles existentes, cero controles nuevos

P1_CONTROL_MAP.json relaciona cada control canónico con un check específico propuesto y los vectores BB-P1 correspondientes. La política real required_checks_by_control es **propiedad del host confiable**, no del paquete de dominio evaluado. Los nombres de checks aún NO están registrados en una misión de teamctl, por lo que no se declaran PASS.

La conformidad es un **gate de entrega de candidata**, no un paso runtime por cada lectura, ni un ledger. F-003 verifica integridad de handoffs/recibos de check; la suficiencia semántica de las aserciones requiere una revisión separada. Una candidata puede ser CONFORMANT para una revisión documental y seguir sin capacidad Browser Bridge habilitada.

## 6. Vectores, criterios de cierre y límites

P1_VECTORS.json contiene 24 escenarios SPEC_ONLY. tests/contracts/browser_bridge/test_p1_browser_contracts.py comprueba estructura, negativos, correspondencia 13↔checks, compatibilidad v1 y transiciones esperadas con un **oráculo de referencia**, no un runtime.

Para promover P1 a contrato ACCEPTED/FROZEN se requiere:

- aprobación explícita de la extensión versionada de registro GEX y del iniciador HUMAN, sin modificar GEX v1 retrospectivamente;
- revisión de la frontera de confianza, autenticación MAC y reconexión por un responsable independiente;
- ejecución real de la suite P1 en un checkout del SHA candidato, con comandos/recibos, y conservación del test actual de fixture.read;
- comprobación de que el mapping host-owned es obligatorio, exhaustivo y no autopropuesto;
- revisión de PR y handoff materializado según TEAM_PROTOCOL, con divergencias de main resueltas;
- suite completa y generación/check de README exigidos por AGENTS.md antes de declarar cierre de repositorio.

Un test de referencia PASS solo valida la consistencia de expectativas. No atribuir ese PASS a Chrome real, GEX P4 ni a verificación independiente.

**Bloqueos P4:** el registro GEX v1 no admite browser_native; GEXRequestV1 requiere agent; no hay adapter Chrome ni comprobación real de activeTab; no se han probado recibos reales del puente. No arrancar P4 sustituyendo esa brecha por una función de utilidad, un permiso alternativo o una segunda base de datos.

## 7. Fuentes de referencia

- GEX normativo: docs/governed-execution/GEX_V1_NORMATIVE_CONTRACT.md.
- Conformidad: docs/domain-conformance/ADL_ADAPTER_v0.1.md y docs/domain-conformance/source/03_DOMAIN_CONFORMANCE_TEST_v1.0.md.
- Arquitectura P0 y mapeo previo: PR #100, docs/plans/browser-bridge-v0.1/.
- Chrome: https://developer.chrome.com/docs/extensions/develop/concepts/activeTab y https://developer.chrome.com/docs/extensions/develop/concepts/native-messaging.

**Resultado esperado de este PR P1:** contrato candidato materializado y revisable. Ningún ejecutable Chrome, nueva autorización runtime ni resultado VERIFIED para el producto.
