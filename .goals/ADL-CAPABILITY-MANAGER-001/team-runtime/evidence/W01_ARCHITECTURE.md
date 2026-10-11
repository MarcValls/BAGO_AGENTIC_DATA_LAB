# W01 — Arquitectura y autoridad del gestor de capacidades

**Misión:** `ADL_CAPABILITY_MANAGER_SPIRAL_001`  
**Candidato:** `C:\Users\AMTEC_Terminal_1º\AppData\Local\Temp\BAGO_AGENTIC_DATA_LAB_conversation_library`  
**HEAD:** `69b4f4b1ead2552b527e6e48868ab36cc2b38cbc`  
**Estado:** inspección de solo lectura sobre worktree deliberadamente sucio. No se editó código, no se ejecutó producto ni se corrieron pruebas.

## Conclusión

El candidato tiene piezas reutilizables de inventario, lectura, política MCP, permisos, sandbox, gateway y recibos, pero **no aparece un gestor integrado que conecte esas piezas con la lista de agentes del chat y el Runner**. El catálogo `agents/` es expresamente de referencia. Los JSON en `agents/created/` son perfiles persistidos por la app; su presencia no los convierte en ejecutores ni les concede herramientas. La única capacidad de proyecto conectada al chat inspeccionada aquí es `read_workspace_file`, limitada y activada por mensaje. `/ws/agents/run` falla en cerrado. Esto encaja con el aviso actual del Runner.

La autoridad para activar/desactivar capacidades debe residir en un servicio backend persistente, con handlers conocidos por allowlist. La UI y el chat pueden consultar el estado y proponer cambios; el backend debe validar el cambio y exigir confirmación humana explícita. La activación no debe crear un permiso de ejecución. Cada efecto necesita una autorización/`Permit` vinculada a la solicitud y al workspace, una ejecución por el gateway/sandbox y un recibo correlacionado. El modelo no es la autoridad de ninguna de esas transiciones.

## Hechos del código observado

### 1. Catálogo de referencia y perfiles de agentes

- `agents/CATALOG_MANIFEST.json:1-5` declara `scope: reference-only`, `activation: none`; agrupa definiciones por responsabilidad. SHA-256: `071BA86556812A887D3FB2DF5A157497758B173C10C9FC0DE67F08E1699EDD61`.
- `agents/README.md:1-26` aclara que los archivos copiados preservan procedencia y no son carga automática; menciona aparte una definición operativa de `bago-sync-agent`.
- `src/api/server.py:43,616-663` carga y guarda perfiles bajo `agents/created/` mediante JSON local. `GET /api/agents/list` lee esos registros (`842-846`); `POST /api/agents/create` valida proveedor/configuración y persiste un perfil (`822-839`). Esto es inventario/configuración, no activación del handler.
- Muestra presente al inspeccionar: `agents/created/agent_d3e63db8b4704080b924a05fb1ab71fc.json`, con `tools: []`, `sandbox_profile: null`, proveedor `ollama-cloud` y `gemma4:31b`; SHA-256 `3C4D5A7F341DCF79A963E4B879E3CEE3F48F923FE0921AC8C37FEF651AF6F23A`. También está el perfil temporal `agent_c0ffee9876543210.json`, SHA-256 `D33E29B15B587D87DB73CC50FCAF1E06F1D04EA3F60E967AE66935EC256D047F`. Son registros observados, no prueba de que esos agentes estén activados.

### 2. Herramienta real disponible en el chat

- `src/agent_tools/workspace_read.py:14-35,37-63,65-115` define `read_workspace_file`; limita cada archivo a 32 KiB y 250 líneas, hasta cuatro llamadas por turno, exige ruta relativa y bloquea directorios/nombres sensibles. SHA-256 `B30EF09867E28471FF0315D65AFCBF746085304D5E47D9DA392B30D112F65DEB`.
- `src/api/server.py:674-740` ofrece esa herramienta solo si el usuario habilita lectura para ese mensaje; el bucle admite únicamente ese nombre de herramienta y devuelve rutas/líneas fuente. `frontend/src/components/AgentChat.tsx:398` refleja el permiso por mensaje y advierte que no escribe ni ejecuta trabajos. Hash del frontend `A983E89F288387807AE1B7C856806B4D5BB7829BB442376854A8D70E9ED2D720`; hash del servidor abajo.

### 3. Registro MCP no equivale al registro de agentes ni a la ejecución

- `src/adapters/mcp_adapter.py:109-159` modela metadatos descubiertos con fingerprint; `182-259` separa `_discovered` de `_registered`, y exige `approved_by` para registrar una capacidad descubierta. El registro vive en diccionarios de la instancia (no se observó persistencia en esta clase). SHA-256 `EF22A50A0E5B3464B47536F67F581880B124D71B8CD8B9B90F85234FC76DB5BE`.
- `GovernedMCPAdapter.authorize` (líneas `381-425`) requiere capacidad registrada, compara efecto y emite un `Permit`; `call` vuelve a comprobar la capacidad/permit y produce `MCPCallReceipt` (continuación en el mismo archivo). Este es un patrón de gobierno reutilizable, pero no se observó integrado en los endpoints de la app/chat ni conectado al catálogo `agents/created/`.
- `agents/08-runtime-supervision/infrastructure/agent_gateway.py` contiene otro gateway/registro de adaptadores en el árbol de agentes, pero el manifiesto califica ese árbol como referencia. Su presencia no demuestra que la aplicación API lo importe o lo use como fuente activa.

### 4. Autoridad material: WorkspaceBinding, Permit, gateway, sandbox, recibo

- `src/context/workspace_binding.py:117-180` define binding inmutable de identidad/alcance del workspace basado en raíz, repositorio, branch, commit y fingerprint. `docs/workspace_binding.md:22-30` dice explícitamente que el binding da contexto/evidencia, no permiso para efectos. SHA de módulo `F8AFCD50595735CE898FF82124132D38899D16624E44EC5C752D416091D01361`.
- `src/orchestration/state_graph.py:61-76` define `Permit` con decisión, constraints, emisor y vigencia. El mismo archivo tiene `execute_actions` en `323-357` con resultado comentado y construido como simulación (`mock`, aleatoriedad); no debe confundirse con el backend sandbox ejecutable.
- `src/execution/gateway.py:12-41` exige un `SandboxRequest` tipado, coteja `request_id` y delega al `SandboxManager`; SHA-256 `543D840857931FF69B41530FD6B8FE8EA6276039E21661BC0BA197D080FE1E26`.
- `src/sandbox/manager.py:83-159,162-190` falla sin Permit coincidente/ALLOW/vigente, reduce capacidades al perfil, valida raíz/alcance y consume el permit una sola vez; genera recibo con perfil/capacidad/operación/estado/evidencias (`272-316`). SHA-256 `07B24BF62CAB172B65C58652177076C3080BD4D333D31325F28AF747817173AE`.
- `docs/sandbox_manager.md:5-22,24-35,53-61` describe esta cadena y advierte que `LocalRestrictedBackend` es una política lógica, no un contenedor OS. Hash del documento `FFD3FC2F20648830E40CCEC8D85E92530CAC5CAE2BCCD1B76928446814EC1AC7`.
- `frontend/src/components/AgentRunner.tsx:24-25,57-61,186-219` fija `AGENT_EXECUTION_AVAILABLE = false`, muestra el estado no disponible y deshabilita Run; SHA-256 `D6BCFF256F3ED47C8B8EDA0DE657B0E2727D660EC452C389FFCCC147565A7DAB`.
- `src/api/server.py:1227-1245` devuelve `execution_unavailable`, afirma que no se inició/registró job y cierra WebSocket con 1008. SHA-256 del servidor `958A6C7A2A1BAF0A04B8AD3BC76F36B0F80BB52AD8AA5E4718E01C480EC30A7E`.
- Contrato `docs/agent-chat-control/contracts/CONTROL_PLANE_V1.md:32-54` diferencia chat, configuración, lectura de archivos y efectos; `38` requiere registro explícito, el camino de autoridad/permit y resultado trazable para cualquier futura capacidad ejecutable. SHA-256 `98DE492E09BECFDFF66DA36922BF16E533A5FEF6F7F5440452D1E207E52EAD67`.

## Modelo de autoridad recomendado para el gestor

Conservar dominios separados, aun si se presentan juntos en la UI:

1. **Catálogo de referencia:** definiciones/plantillas descriptivas de `agents/`; nunca “activos” por aparecer aquí.
2. **Perfil creado:** identidad, propósito, modelo y configuración persistida (`agents/created/`). Permite listar/editar perfil según su contrato, pero no invocar efectos.
3. **Capacidad registrada:** tipo/handler conocido por el backend, versión/fingerprint, efectos declarados, esquema, límites y procedencia. Descubrimiento externo (p. ej. MCP `tools/list`) queda como descriptor no confiable; registrar requiere revisión y clasificación.
4. **Disponible:** el handler puede resolver su dependencia real ahora (proveedor, conexión, binario). Es estado de salud/capacidad, no permiso.
5. **Elegible:** política determina que una capacidad puede usarse para este agente/workspace/solicitud. Debe calcularse server-side; que el chat la mencione no basta.
6. **Activada:** registro persistente reversible de que el handler está habilitado para ser considerado. No crea Permit ni equivale a autorización. Por defecto, desactivada.
7. **Autorizada para solicitud:** decisión explícita y contextual, con Permit de corta duración, alcance mínimo y vínculo a request/workspace. No heredar autorizaciones generales desde “activar”.
8. **Ejecutada/verificada:** sólo tras llamada real a gateway/sandbox y recibo; la verificación debe comprobar identidad/correlación del recibo. La ausencia de recibo no es éxito.

### Responsabilidades

- **Backend como autoridad:** repositorio persistente/versionado de definiciones y activaciones; servicio único de estado, validación, enable/disable/revoke y audit trail. Endpoints devuelven estado estructurado por separado (`registered`, `available`, `eligible`, `enabled`, `authorization`, `last_execution/receipt`), sin inferir estados faltantes.
- **Chat:** intents concretos para consultar, proponer activar/desactivar y abrir revisión. La respuesta del modelo nunca muta catálogo, activation, permisos ni runtime. Operación con efecto exige tarjeta de propuesta con alcance/diff y control explícito de confirmación; API repite validaciones y registra actor, revisión/fingerprint y motivo.
- **UI de capacidades:** vista compacta de listado, estado y detalle; filtros por “referencia”, “registrada”, “disponible” y “activada”; autorización/ejecución y recibos aparecen en solicitudes/ejecuciones vinculadas, no como un simple toggle global.
- **Ejecución:** solo handlers allowlisted; la llamada del agente va a un dispatcher que valida activación, elegibilidad, request, workspace binding, Permit y perfil. Gateway/sandbox aplica el límite y emite recibo correlacionado. Sin handler conectado, mantener Runner disabled y devolver error cerrado.
- **MCP:** mantener descubrimiento separado de registro. Registrar descriptor/versionado no autoriza llamada; cada llamada pasa política/permit y receipt. No usar el diccionario de una instancia como almacén persistente del gestor.

## Inferencias, límites y riesgos residuales

- **INFERENCIA:** el gestor descrito en la conversación no existe aún como producto integrado en este snapshot: búsqueda de referencias mostró componentes separados y el Runner/backend bloquean ejecución. No se ejecutaron pruebas ni se inspeccionó el proceso vivo.
- **INFERENCIA:** `agents/created/` es el inventario persistente de perfiles que usa esta app, pero la lectura de archivos no prueba qué registros están cargados en una instancia servidor viva.
- **RIESGO:** activar un handler por chat sin una frontera backend permitiría al modelo convertirse indirectamente en autoridad. Evitar que “enabled” se transforme en un Permit persistente.
- **RIESGO:** el backend de sandbox local aplica restricciones lógicas; `docs/sandbox_manager.md` advierte que no constituye aislamiento OS. Capacidades con procesos o red deben conservar este límite visible.
- **LÍMITE:** el reporte está ligado a HEAD más hashes individuales de fuentes que, según el status inicial, estaban modificadas/locales. No certifica una versión limpia/commit, runtime ni ejecución real. Fuentes examinadas tienen los hashes registrados arriba; otras partes del repo no fueron auditadas exhaustivamente.

## Recomendación de siguiente consumidor

W04 debe sintetizar este mapa con las auditorías de backend y frontend y cerrar un contrato MVP que cubra: catálogo/versionado, estado de activación persistido, endpoint de consulta/propuesta/confirmación/revocación, flujo equivalente desde UI/chat, matriz de estados explícitos, policy/Permit por solicitud, `ExecutionGateway` + sandbox, recibo/LocalTrace y criterios de seguridad/aceptación. Mantener la prueba de lectura actual como capacidad read-only independiente; no conectarla implícitamente a `Run`.

## Verificación

- **Inspección de fuentes:** `EXECUTED` (búsquedas de símbolos, lectura de secciones y hashes SHA-256 en el candidato declarado).
- **Tests/build/runtime:** `NOT_RUN` — W01 es una auditoría de arquitectura read-only; no se pidió ejecutar pruebas y no se corrieron.
- **Producto gestor:** no implementado ni validado por este W01.
