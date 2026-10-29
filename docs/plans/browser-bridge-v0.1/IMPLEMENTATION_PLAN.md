# BAGO5_ADL Browser Bridge v0.1 — Plan de implementación

## Actualización de coordinación — conformidad de dominio (2026-10-29)

**Lectura prioritaria antes de P1:** [DOMAIN_CONFORMANCE_INTEGRATION.md](./DOMAIN_CONFORMANCE_INTEGRATION.md).

La implementación sigue pendiente. Tras redactar este plan se incorporó a `main` un adaptador de conformidad de dominio de solo lectura (`src/contracts/domain_conformance.py`), el manifiesto `adl.domain_manifest.v1` y un contrato de 13 controles. **No crear un segundo sistema de conformidad**: las comprobaciones específicas de Browser Bridge deben mapearse por política host-owned a esos controles, mediante checks requeridos y handoff gestionados por `teamctl`. Esta comprobación es un gate de candidata, nunca un permiso ni una puerta de ejecución.

Se conservan dos autoridades distintas y necesarias para cada lectura: la concesión `activeTab` derivada de un gesto real del usuario en Chrome y la autorización gobernada ADL/GEX. No se hereda `activeTab` del chat, un binding guardado ni un test de conformidad.

Tras `DISPATCH_INTENT`, si falta recibo terminal persistido, el resultado es `UNKNOWN / RECONCILIATION_REQUIRED`, no SUCCESS, aunque el host haya contestado o un test de transporte pase. No crear otro ledger: GEX mantiene efectos y recibos durables; `teamctl` aporta evidencia de verificaciones de candidata, y el adaptador de conformidad solo las consulta.

**Divergencia conocida:** el plan inicial se elaboró sobre `main@ae8e53e14afa763f816eac9e11ddc0e8a24cdc56` y se inspeccionó el contrato de conformidad sobre `main@1ebf9b1b2c5cd75de8dd34dddb0cc581588327c4`. Releer main al reanudar y actualizar el inventario P0. Ningún cambio de diseño se considera implementado por esta adenda.

---

Fecha: 2026-10-29.
Estado del diseño: **PROPUESTO / REVIEW REQUIRED**.
Estado de implementación del puente: **NO IMPLEMENTADO POR ESTE CAMBIO**.
Estado de ejecución de pruebas: **NOT_RUN**.
Publicar este documento no acepta ni congela el diseño, no autoriza su implementación completa y no acredita funcionamiento.

## 1. Objetivo y primer resultado demostrable

Añadir una capacidad de navegador a ADL, no otro agente ni otro sistema de autorización. El primer resultado será leer, desde el chat general, texto visible de una pestaña que el usuario haya compartido explícitamente, devolverlo con procedencia y conservar evidencia de autorización, despacho, resultado y verificación.

Recorrido objetivo: **Chat/control manual → propuesta tipada → autorización ADL → permiso y consumo durable → adaptador de navegador → host Windows → extensión Chrome → lectura acotada → recibo → Inspect/verificación**.

El puente será independiente del ejecutable y de los registros de Codex. Chrome continuará siendo una aplicación externa: operar desde el chat no equivale a incrustar Chrome dentro de ADL.

La v0.1 no incluye navegación autónoma, clics, escritura en formularios, compras, publicaciones, descargas, carga de archivos, lectura de cookies, contraseñas, historial, DevTools/CDP ni ejecución de JavaScript arbitrario enviado por un modelo. Estas capacidades requieren contratos y aceptación posteriores.

## 2. Base inspeccionada y límites de esta revisión

Repositorio: `MarcValls/BAGO_AGENTIC_DATA_LAB`.
Rama de referencia: `main`.
SHA inspeccionado y releído antes de crear la rama documental: `ae8e53e14afa763f816eac9e11ddc0e8a24cdc56`.
Commit: merge de PR #99, `fix(chat): isolate resource dialogs from composer submission`, fechado `2026-10-29T00:57:26Z`.
Rama documental: `docs/browser-bridge-plan-20261029`.

La inspección fue remota y de solo lectura hasta crear esta rama y sus documentos. Se leyeron archivos o rangos relevantes; no se auditó todo el repositorio, no se ejecutó su código y no se inspeccionó el Windows instalado. La ausencia de una capacidad en los archivos examinados no prueba su ausencia en todo el repositorio.

### Reutilización fundamentada

- `src/execution/gateway.py`: contiene `ExecutionGateway.execute`, exige `SandboxRequest` y delega en `SandboxManager`. **Es una frontera local existente, no un adaptador genérico de navegador demostrado.**
- `src/execution/gex_control.py`, líneas 1–155 inspeccionadas: importa identidad, permisos y ledger; su registro, política y esquema están especializados en `fixture.read`. Sus restricciones incluyen `network=deny`. **No basta con añadir un nombre de herramienta para controlar Chrome.**
- `src/api/gex_routes.py`, líneas 1–165 inspeccionadas: rutas GEX con Bearer, comprobación de Origin y estado que declara `fixture.read`, `synthetic=True`, aprobación obligatoria y perfil `single-process-local`.
- `docs/governed-execution/GEX_V1_NORMATIVE_CONTRACT.md`: el documento mantiene estado candidato/PREPARED; exige autoridad backend, consumo durable y reconciliación. No promoverlo a FROZEN por este plan. Algunas descripciones históricas deben contrastarse con el código actual.
- `src/api/project_permissions_routes.py`, líneas 1–125 inspeccionadas: revisión, binding e identidad esperados; sus campos READ/WRITE corresponden a directorios. **Un permiso de archivos no concede permiso de navegador.**
- `src/api/connection_routes.py`: los tipos admitidos son `docker_mcp`, `mcp`, `http_api`. Evaluar reutilización de presentación/registro, pero no disfrazar Native Messaging como uno de esos transportes ni dar acceso mediante un `invoke` genérico.
- `docs/readme_frontend.md`, líneas 1–125 inspeccionadas: identifica `frontend/src/components/AgentChat.tsx`, `frontend/src/App.tsx` y las superficies Chat, Settings, Capabilities, Agent Runs e Inspect. Los componentes React no fueron auditados en esta revisión; la selección exacta de puntos de extensión queda en P0.
- `docker-compose.ui.yml`: publica la API en `127.0.0.1:8080:8080`. El host de Chrome debe ejecutarse en Windows; el backend ADL puede permanecer en Docker. El puerto real se configura, no se presupone en la implementación.
- `AGENTS.md` y `.bago/team/kit/protocol/TEAM_PROTOCOL.md`: exigen base fresca, ámbitos no solapados, handoffs y verificación real. `README.md` y `README_DETAILS.md` son generados y no deben editarse a mano.

**Brecha principal:** adaptar el recorrido durable de ejecución a una capacidad de navegador sin debilitar las garantías de `fixture.read` ni crear una segunda autoridad. Esta ampliación es un gate de integración, no una capacidad ya verificada.

## 3. Decisiones propuestas

### 3.1 Topología y dirección real de conexión

La extensión MV3 inicia `chrome.runtime.connectNative`. Chrome crea el proceso nativo y conecta sus streams. El host abre después una conexión autenticada hacia la instancia ADL configurada. ADL no invoca Native Messaging directamente ni puede asumir que el host o Chrome ya están arrancados. [C1]

Canal propuesto host–ADL: WebSocket autenticado, iniciado por el host, hacia una dirección loopback explícita. No descubrir puertos explorando procesos ni elegir «el primer ADL disponible». Emparejar `adl_instance_id`, endpoint y clave pública/identidad del servidor; verificar esa asociación en cada reconexión. Soportar backend Windows y backend Docker publicado en loopback.

La autenticación del canal no autoriza operaciones. Solo un comando derivado de una solicitud autorizada y consumida por ADL puede producir lectura. La UI, el modelo, una página y el host no pueden acuñar permisos.

El host será un adaptador pequeño; la lógica de política permanece en ADL. Propuesta inicial: Python para reutilizar contratos del backend y empaquetado Windows independiente. La elección concreta de empaquetador y versiones se valida en P0/P2, sin incorporar todas las dependencias de ADL al ejecutable.

### 3.2 Chrome y ADL mantienen permisos distintos

Permisos iniciales propuestos: `nativeMessaging`, `activeTab`, `scripting`; añadir `storage` solamente para el estado mínimo justificado. No solicitar `<all_urls>`, `cookies`, `debugger`, `history` ni permisos de archivos/incógnito en v0.1.

`activeTab` requiere una interacción reconocida por Chrome con la extensión. Una instrucción en el chat de ADL no concede ese permiso. El usuario comparte primero la pestaña mediante la extensión; después puede ordenar lecturas desde ADL mientras siga siendo válido el permiso y el ámbito interno. El cambio de origen revoca el permiso temporal de Chrome. [C2]

La concesión de Chrome tampoco equivale a autorización ADL. El ámbito ADL debe ligar proyecto/binding, agente o actor autenticado, instancia/perfil emparejado, pestaña, documento, origen y operación. Una política persistente de lectura, si se acepta, será explícita y específica de navegador; no se heredará de `read_directories` ni evitará una nueva concesión de Chrome cuando corresponda.

En v0.1 no se inventaría una identidad de agente para una acción manual: resolver el principal y el actor con un contrato aprobado; ampliar GEX de forma explícita si el modelo de identidad existente no lo admite.

### 3.3 Operaciones iniciales

`browser.shared_tabs.list`: metadatos mínimos de las pestañas ya compartidas y autorizadas para el proyecto. No inventario de todas las pestañas del usuario.

`browser.document.read`: texto visible acotado del documento principal autorizado, con título/origen, instante, identidad documental y digest de los bytes efectivamente entregados. No devolver DOM completo por defecto.

Handshake, diagnóstico y revocación pertenecen al control del puente. El diagnóstico no debe consultar documentos, revelar pestañas ni simular una lectura exitosa.

La extracción usa código fijo incluido en la extensión, ejecutado en contexto aislado; no acepta funciones, scripts ni selectores arbitrarios como forma de ampliar su poder. `scripting` permite dirigir la ejecución a pestañas/documentos y exige el permiso de host correspondiente. [C3]

### 3.4 Contratos, autenticación y revocación

Definir antes del código: `BrowserSessionV1`, `SharedTabBindingV1`, `BrowserCommandV1`, `BrowserReadResultV1`, códigos de error y mapping a solicitud/permiso/recibo GEX. No crear un segundo ledger autoritativo.

El comando enlaza versión, `command_id`, `request_id`, `request_digest`, referencia de permiso consumido, run, proyecto/binding, revisión de política, instancia emparejada, sesión, tab/document, origen, límites, nonce y expiración. Backend deriva identidades de estado autenticado; no las acepta como autoridad del modelo.

El backend persiste intención de despacho y consumo transaccional antes de entregar el comando. El sobre de despacho debe estar autenticado por la misma autoridad de ejecución y ligado a la solicitud exacta; no es otra decisión de política. Host/extensión validan la integridad y las restricciones que les corresponden. La separación de claves del canal y de autorización se define en P1.

Emparejamiento explícito, credenciales fuera del chat, DOM, URLs y logs, sesión expirable, claves almacenadas con protección adecuada al usuario Windows y rotación/revocación. Ni Origin ni escuchar en localhost bastan como autenticación. El argumento de origen del proceso y `allowed_origins` son controles de integración con Chrome, no prueba criptográfica contra un proceso local malicioso. [C1]

Revalidar política/binding y revocación antes del despacho; en la extensión, comprobar sesión, expiración y documento antes de leer. Cambio de proyecto A→B→A, navegación, cambio de perfil, permisos retirados o desconexión invalidan el contexto correspondiente. Una revocación bloquea nuevas operaciones; no puede deshacer una lectura ya realizada. Documentar el punto de corte y las carreras residuales.

Nunca reenviar automáticamente un comando ambiguo tras una reconexión. Si hubo `DISPATCH_INTENT` y falta recibo terminal, conservar `UNKNOWN / RECONCILIATION_REQUIRED` hasta resolverlo; «sin recibo» no demuestra «sin efecto». Un reintento de lectura será una nueva solicitud gobernada, no la repetición ciega del permiso anterior.

### 3.5 Frontera de confianza y privacidad

Una página es dato no confiable. Validar origen, identidad del emisor y correlación al recibir mensajes de content scripts; estos no invocan Native Messaging directamente. [C1]

El texto recuperado no puede cambiar permisos, pedir herramientas por sí mismo, sustituir instrucciones de sistema ni alterar proyecto/destino. Tratarlo como recurso citado con procedencia y clasificación de confianza.

Excluir contraseñas, campos de formulario, tokens evidentes y contenido oculto de la extracción inicial; imponer límites de bytes/nodos/tiempo. La redacción automática no garantiza detectar todos los secretos. Acceso, retención, borrado y envío de contenido a proveedores de modelos requieren política propia y destino visible. Guardar por defecto metadatos y hashes; el contenido retenido exige autorización y control de acceso.

Denegar `chrome://`, páginas de extensiones, `file://`, incógnito y marcos cruzados en v0.1. Un error de acceso de Chrome debe verse como tal, no como página vacía. No prometer control de pestañas restringidas. [C2]

No presentar el sandbox lógico de ADL como aislamiento del proceso Chrome. El navegador, la extensión, el host, el SO local y el emparejamiento son parte de la base de confianza; compromiso del mismo usuario/administrador Windows queda fuera de una garantía fuerte de este MVP.

## 4. Protocolo y operación Windows

Native Messaging usa JSON UTF-8 con prefijo de longitud de 32 bits en orden nativo. Separar framing binario de lógica; stdout solo transporta protocolo y los diagnósticos van a stderr. El límite Chrome documentado es 1 MB desde host y 64 MiB hacia host. [C1]

Límites iniciales propios propuestos: 256 KiB por frame, texto extraído de hasta 128 KiB, timeout de lectura de 5 segundos y una operación activa por sesión. Son parámetros de diseño, no límites impuestos por Chrome. Rechazar encabezados parciales, EOF inesperado, JSON duplicado/no válido, profundidad excesiva y tamaños declarados desmesurados antes de reservar memoria. La truncación de contenido debe quedar explícita.

Reconexión con backoff y límite; comprobar versiones incompatibles y host caído. Los service workers pueden terminar y perder variables globales; un puerto nativo afecta a su ciclo de vida, pero no elimina la necesidad de recuperación y pruebas de caída. [C4]

Identificadores propuestos: ejecutable `bago5-chrome-native-host.exe`; host `com.bago.adl.browser_bridge`. Registrar únicamente la clave HKCU propia y un manifiesto con ID exacto de la extensión, nunca el host de Codex ni comodines. [C1]

El instalador deriva rutas de su ubicación real, exige confirmación de cambios y registra archivos/clave que posee. En baterías de ZIP se parte de la carpeta actual, sin rutas del equipo del autor. Desinstalación restaura solo recursos propios comprobados; no borra perfiles Chrome. Publicar versión, hashes y estado real de firma del ejecutable. Un binario sin firma se etiqueta como tal.

## 5. Superficies de producto

**Settings:** sección de navegador en el sistema de configuración existente: instalar/comprobar host, emparejar, instancia y perfil, permisos, desconectar/revocar. Mostrar pasos de Chrome que requieran intervención real; no prometer instalación silenciosa.

**Chat general:** indicador contextual y tarjeta de pestaña compartida; solicitar lectura y mostrar destino, ámbito y recibo. El chat sigue siendo el orquestador. No crear un agente navegador obligatorio ni cambiar de conversación para usar la capacidad.

**Control manual:** usar el mismo servicio de propuesta/autorización que el chat. Ningún botón puede emitir comandos al host saltándose el backend gobernado.

**Capabilities / Agent Runs / Inspect:** proyectar disponibilidad, resultado y evidencia ya existentes. Enlazar conversación→run→request→permit→command→receipt→verification. No inventar una segunda pantalla principal ni otro almacén de evidencia.

Estados separados: `NOT_INSTALLED`, `UNPAIRED`, `DISCONNECTED`, `CONNECTED`, `AUTHORIZED`, `ERROR`. Conexión, autorización y prueba E2E son dimensiones distintas. `SUCCEEDED` no se convierte en `VERIFIED_SUCCESS` sin verificador independiente.

Conservar los comportamientos existentes de diálogo/composer corregidos por PR #99, permisos de proyecto, selección de agente/proveedor y navegación Chat/Inspect. La extensión Chrome y las pruebas de producto no se confunden con las pruebas visuales de la UI React.

## 6. Fases y gates de entrega

Todos los trabajos siguientes están **PROPUESTOS**, no READY/DONE. Las PR son unidades sugeridas, no PR ya creadas.

### P0 — Inventario y baseline

Releer `origin/main` y registrar SHA, estado de worktree, PR concurrentes y ámbitos ocupados. Buscar implementaciones previas de browser/Native Messaging antes de añadir archivos. Inspeccionar gateway, sandbox, ledger, identidad, permisos, conexiones, UI y suites afectadas. Ejecutar baseline según CI actual y guardar versiones/resultados; no trasladar números históricos de tests.

**Salida:** mapa de reutilización, mapa de confianza, ruta exacta de integración, matriz de conservación y alcance de implementación aceptado. **Gate:** ninguna dependencia crítica se declara verificada solo por existir código. Si el perfil GEX no permite extensión segura, bloquear integración y mantener únicamente harness de desarrollo.

### P1 — Contratos y vectores de conformidad

Preparar ADR, esquemas cerrados, mapping GEX, política de navegador, emparejamiento, límites, estados y estrategia de reconciliación. Evaluar ampliación versionada del registro/capacidades sin alterar las garantías de `fixture.read`. Documentar qué enforcement corresponde a ADL, host y extensión.

**Salida:** contratos revisados, vectores positivos/negativos y criterios de aceptación. **Gate:** aprobación explícita antes de congelar contratos consumidos por varias ramas. Los cambios posteriores requieren change request y nueva huella.

### P2 — Host y transporte aislados

Implementar framing, validación, handshake, cliente de transporte autenticado y empaquetado Windows. No habilitar navegación ni lectura de páginas como diagnóstico. Instalar/desinstalar en usuario de prueba y extensión de ID fijo de desarrollo.

**Ámbito propuesto:** `src/browser_bridge/` para código compartido/host, `scripts/browser_bridge/` para instalación y packaging, y pruebas específicas de host. Ajustar el árbol tras P0 para no duplicar módulos existentes.

**Gate:** protocolo host↔harness PASS, mensajes malformados rechazados, ningún comando genérico, stdout limpio y reversión de instalación demostrada.

### P3 — Extensión Chrome mínima

Implementar MV3, acción Compartir pestaña, service worker, comprobación de mensajes y extracción fija de texto principal. Probar identidad documental, pérdida de permiso, perfiles y reconexión. No introducir `eval`, código remoto ni permisos globales.

**Ámbito propuesto:** `extensions/bago-browser-bridge/` y pruebas de extensión. **Gate:** lectura contra fixture controlada y denegaciones PASS; ninguna autorización otorgada únicamente por mensajes de página.

P2 y P3 pueden avanzar en paralelo solo después de P1 y con ámbitos separados. Integrador único para contratos compartidos.

### P4 — Adaptador y autorización durable ADL

Registrar capacidades de lectura con versiones y esquemas; conectar propuestas del chat y control manual a la autoridad existente. Reutilizar identidad, claves, consumo y ledger donde los contratos lo permitan; hacer explícita cualquier ampliación. No convertir `fixture.read` en ejecutor abierto ni cambiar `network=deny` por una excepción global.

**Ámbito propuesto:** adaptador en `src/execution/adapters/`, API específica en `src/api/browser_bridge_routes.py` y cambios mínimos revisados en los puntos existentes. Los nombres son propuestas, no archivos ya creados.

**Gate:** dos solicitudes concurrentes no consumen el mismo permiso; manipulación, replay, expiración, cambio de proyecto/política y store caído deniegan antes del efecto. Caída tras despacho conserva incertidumbre. Las pruebas históricas del recorrido GEX no sufren regresión.

### P5 — Integración de UI y recorrido completo

Añadir sección Settings, contexto de pestaña en Chat y evidencia en superficies existentes. API/client contracts congelados antes de integrar. Evitar editar `App.tsx`, `AgentChat.tsx`, routers centrales o contratos compartidos simultáneamente con otros trabajos de Codex: reservarlos o serializar el cambio.

**Gate:** desde el chat y desde control manual se recorre la misma frontera de autorización. Proyecto A no recibe datos de B; no se muestran éxitos optimistas. La prueba Chat→Inspect abre exactamente la evidencia del run nuevo.

### P6 — Retest independiente Windows y publicación

Probar Chrome real en Windows, tanto con backend local como con backend Docker publicado en loopback. Registrar versiones de SO/Chrome/extensión/host/backend y SHA candidato, no solo capturas. El verificador no reutiliza el propio extractor como único oráculo.

**Gate:** evidencia E2E y adversarial, pruebas de regresión, instalación/reinstalación/desinstalación y fallos recuperables PASS. Cualquier P0/P1 de seguridad o evidencia bloquea promoción. Documentar NOT_RUN sin convertirlo en PASS.

Solo entonces considerar `BROWSER_BRIDGE_READ_V0_1` verificado dentro de ese entorno y alcance. No afirmar compatibilidad con Brave/Edge/macOS/Linux o producción sin sus retests.

## 7. Matriz mínima de pruebas

- **T01 Happy path:** fixture controlada con marcador conocido; autorización válida, lectura acotada, recibo y oráculo independiente coinciden.
- **T02 Sin permisos:** ausencia de activeTab, permiso ADL o emparejamiento produce denegación; no lectura encubierta durante health.
- **T03 Contexto:** A→B→A, pestaña reutilizada, documento cambiado, origen redirigido y otro perfil invalidan el binding.
- **T04 Revocación:** antes del despacho, durante el tránsito y tras lectura; resultados y punto de corte se registran sin prometer deshacer efectos.
- **T05 Integridad:** argumentos/IDs/límites manipulados, versión desconocida, permiso expirado y firma no válida se rechazan.
- **T06 Replay/concurrencia:** duplicado, reconexión y dos consumidores; consumo único durable, sin ejecución repetida silenciosa.
- **T07 Framing:** lectura fragmentada, UTF-8 multibyte, EOF, tamaños excesivos, claves JSON repetidas y contaminación stdout.
- **T08 Inyección:** instrucciones maliciosas dentro del texto y mensajes falsificados de página no crean acciones ni autoridad.
- **T09 Privacidad:** formularios/secretos de fixture no aparecen en resultado, logs ni trazas; no se inspeccionan otras pestañas.
- **T10 Fallos:** host/Chrome/backend caídos, timeout y ledger no disponible; no falso SUCCESS ni reintento de efecto ambiguo.
- **T11 Evidencia:** digest del extracto no se presenta como hash de toda la página; la cadena correlaciona IDs y distingue observado de verificado.
- **T12 UI y conservación:** diálogos no envían composer; permisos de archivos, proveedores, agentes, Chat/Inspect y recorrido GEX conservados.
- **T13 Instalación:** rutas con espacios/Unicode, dos instancias ADL, manifiesto incorrecto, permisos de registro y retirada solo de recursos propios.
- **T14 Datos y proveedor:** denegar envío del extracto a un modelo externo cuando la política de datos no lo permita.

Para cada vector guardar comando real, resultado, versión, entorno, archivos/hash de evidencia y responsable del verificador. Un nombre de test o una captura aislada no constituye PASS.

## 8. Rollout, rollback y continuidad

Nueva capacidad deshabilitada por defecto. Activación explícita por instancia/proyecto después de los gates; el flag no sustituye permisos. No migrar permisos de archivos hacia navegador automáticamente.

Rollback: impedir nuevos despachos, revocar sesión/emparejamiento, desconectar host/extensión y deshabilitar capacidades. Conservar recibos, denegaciones y operaciones ambiguas para reconciliar; no borrar evidencia ni afirmar que se revierten lecturas. Migraciones de estado versionadas y compatibles, sin sobrescribir bases del runtime activo.

Escrituras/navegación se planifican en otra revisión. Pulsar un botón puede producir un efecto externo aunque parezca navegación; se requiere clasificación y verificación de postcondición específica antes de habilitarlo.

## 9. Coordinación con Codex y cierre

Este cambio solo publica documentación. No toca `main`, código, dependencias, permisos instalados ni `.bago/team/runtime/`. No inicia, reinicia ni declara terminada la misión activa del usuario.

La implementación futura sigue `AGENTS.md` y el protocolo del equipo: worktree desde base remota recién obtenida, ámbitos no solapados, handoffs materiales y verificador independiente. No generar un `state.json` o recibo de equipo ficticio para este plan.

Antes de publicar una implementación, releer main y comparar la base; si avanzó, revalidar los archivos/contratos afectados y repetir pruebas. Antes de cierre ejecutar los comandos exigidos por el repositorio:

```text
python scripts/generate_dynamic_readme.py
python scripts/generate_dynamic_readme.py --check --skip-tests
```

Ambos están **NOT_RUN en esta entrega documental**. No se editaron README generados. Esta rama/PR debe permanecer propuesta y sin cierre de implementación hasta la revisión y los gates aplicables. La publicación verificable del documento no equivale a `teamctl verify`, pruebas de producto ni terminal gate.

## 10. Fuentes

Fuentes del repositorio consultadas en el SHA indicado; no equivalen a pruebas ejecutadas:

- [AGENTS.md](https://github.com/MarcValls/BAGO_AGENTIC_DATA_LAB/blob/ae8e53e14afa763f816eac9e11ddc0e8a24cdc56/AGENTS.md)
- [Arquitectura canónica](https://github.com/MarcValls/BAGO_AGENTIC_DATA_LAB/blob/ae8e53e14afa763f816eac9e11ddc0e8a24cdc56/.bago/canon/ARCHITECTURE.md)
- [Team protocol](https://github.com/MarcValls/BAGO_AGENTIC_DATA_LAB/blob/ae8e53e14afa763f816eac9e11ddc0e8a24cdc56/.bago/team/kit/protocol/TEAM_PROTOCOL.md)
- [Gateway](https://github.com/MarcValls/BAGO_AGENTIC_DATA_LAB/blob/ae8e53e14afa763f816eac9e11ddc0e8a24cdc56/src/execution/gateway.py)
- [GEX control](https://github.com/MarcValls/BAGO_AGENTIC_DATA_LAB/blob/ae8e53e14afa763f816eac9e11ddc0e8a24cdc56/src/execution/gex_control.py)
- [GEX routes](https://github.com/MarcValls/BAGO_AGENTIC_DATA_LAB/blob/ae8e53e14afa763f816eac9e11ddc0e8a24cdc56/src/api/gex_routes.py)
- [Contrato GEX candidato](https://github.com/MarcValls/BAGO_AGENTIC_DATA_LAB/blob/ae8e53e14afa763f816eac9e11ddc0e8a24cdc56/docs/governed-execution/GEX_V1_NORMATIVE_CONTRACT.md)
- [Permisos de proyecto](https://github.com/MarcValls/BAGO_AGENTIC_DATA_LAB/blob/ae8e53e14afa763f816eac9e11ddc0e8a24cdc56/src/api/project_permissions_routes.py)
- [Conexiones](https://github.com/MarcValls/BAGO_AGENTIC_DATA_LAB/blob/ae8e53e14afa763f816eac9e11ddc0e8a24cdc56/src/api/connection_routes.py)
- [Frontend documentado](https://github.com/MarcValls/BAGO_AGENTIC_DATA_LAB/blob/ae8e53e14afa763f816eac9e11ddc0e8a24cdc56/docs/readme_frontend.md)
- [Compose](https://github.com/MarcValls/BAGO_AGENTIC_DATA_LAB/blob/ae8e53e14afa763f816eac9e11ddc0e8a24cdc56/docker-compose.ui.yml)

Fuentes primarias Chrome consultadas el 2026-10-29:

- C1: [Native Messaging](https://developer.chrome.com/docs/extensions/develop/concepts/native-messaging)
- C2: [activeTab](https://developer.chrome.com/docs/extensions/develop/concepts/activeTab)
- C3: [Scripting API](https://developer.chrome.com/docs/extensions/reference/api/scripting)
- C4: [Service worker lifecycle](https://developer.chrome.com/docs/extensions/develop/concepts/service-workers/lifecycle)
