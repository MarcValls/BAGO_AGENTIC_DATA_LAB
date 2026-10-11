# W02 — Auditoría backend del gestor de capacidades

## Identidad y alcance

- Worktree inspeccionado: `C:\Users\AMTEC_Terminal_1º\AppData\Local\Temp\BAGO_AGENTIC_DATA_LAB_conversation_library`.
- HEAD solicitado y observado: `69b4f4b1ead2552b527e6e48868ab36cc2b38cbc`.
- El worktree ya tenía numerosos cambios modificados y no rastreados. Se preservaron; no se editaron fuentes ni se ejecutaron pruebas.
- Las rutas `.bago/context/PROJECT_CONTEXT.md`, `.bago/state/PROJECT_STATE.json`, `.bago/runtime/ACTIVE_HANDOFF.md` y `.codex/skills/bago-core/SKILL.md` no están presentes en este worktree. Se leyó el skill BAGO Core disponible en el perfil de usuario y las instrucciones locales `AGENTS.md`.
- Este informe describe el contenido de trabajo observado en las fuentes, no atribuye esos bytes al commit limpio: `src/api/server.py` y `src/providers/ollama.py` están modificados respecto a HEAD.

## Conclusión ejecutiva

**HECHO:** el backend ya conecta Ollama con el chat de control y con el chat de agentes; permite crear perfiles de agentes y ofrece lectura de archivos delimitada por petición. La creación guarda configuración, no concede herramientas ni inicia trabajos.

**HECHO:** `CapabilityRegistry`, `GovernedMCPAdapter`, `Permit`, `ExecutionGateway`, `SandboxManager` y los recibos tipados existen como código reutilizable. El registro MCP es memoria del objeto, se instancia en `scripts/run_mcp_demo.py` y en pruebas; la búsqueda en `src/` no encontró instancias del registry/adaptador/gateway/sandbox manager desde el API FastAPI. No hay endpoints de catálogo/capacidades, asignación, aprobación o revocación.

**HECHO:** `POST /ws/agents/run` falla cerrado con `execution_unavailable` y afirma que no se inicia ni registra trabajo. El gateway y el sandbox, por tanto, no están conectados a la ejecución del Agent Runner del producto.

**RECOMENDACIÓN:** para un MVP persistente, usar SQLite local de la app para el catálogo versionado y su historial de cambios, ligado a un ID/fingerprint del workspace; mantener las claves de proveedor en el almacén seguro del sistema operativo. No reutilizar `agents[].tools` como autoridad, ni considerar “registrado” equivalente a “autorizado” o “ejecutado”.

## Trazado por componente

| Componente | Conectado realmente | Persistencia / límite |
|---|---|---|
| Provider | `GET /api/providers/ollama/status`, `PUT /api/providers/ollama/config`, `GET /api/providers/ollama/models`, `POST /api/providers/ollama/verify` en `src/api/server.py:394-422`. `/api/chat/control` y `/api/agents/{agent_id}/chat` llaman al provider (`server.py:928-977`, `1055-1113`). | `src/providers/ollama.py:24,82-132` persiste modo/modelo en `.bago/providers/ollama.json`; API key via keyring del SO (`:62-79,98-144`). El secreto no se devuelve al API. Auth soportada: `api_key` o `local_cli`. No es un registro de capacidades.
| Agentes | `POST /api/agents/create`, `GET /api/agents/list`, `GET /api/agents/{id}` (`server.py:822-872`). El chat de control puede proponer JSON editable; el usuario lo guarda por la ruta Create agent (`server.py:929-953`). | `agents/created/<agent_id>.json`, escritura temporal y `os.replace` (`server.py:616-663`). `AgentConfig.tools` acepta solo una allowlist literal (`server.py:48-54,87-92`), `sandbox_profile` es un string opcional; estos campos se guardan, pero la ruta de chat no los ejecuta. Las configuraciones son perfiles, no permisos.
| Chat de control | `POST /api/chat/control` persiste turnos y maneja `help`, `list_agents`, `draft_agent`, `navigate` y chat con Ollama (`server.py:875-977`). Su prompt declara que no inicia jobs ni modifica archivos (`:957-964`). | Historial/cambios con revision CAS en SQLite, compartido con chats de agentes (`src/conversations/library.py:42-81,100-188`). No hay operación de capacidades en `ControlChatRequest` (`server.py:191-200`).
| Chat de agente y lectura | `POST /api/agents/{id}/chat` persiste el turno, llama Ollama y anota fuente/traza (`server.py:1055-1113`). Si `allow_workspace_read=true`, `_chat_with_workspace_read` solo ofrece `read_workspace_file` (`:674-743`). | Guardas en `src/agent_tools/workspace_read.py:14-18,37-63,65-160`: ruta relativa individual, sandbox read-only, 32 KiB/archivo, máximo 250 líneas por lectura, 4 llamadas y 3 rondas por turno, rutas de runtime/secretos bloqueadas y filtro de credenciales. No permite listar directorios, escribir ni ejecutar comandos.
| Conversaciones | APIs create/list/get/rename/archive/delete/restore en `server.py:763-819`. | SQLite bajo `%LOCALAPPDATA%\BAGO\AgenticDataLab\conversations\library.sqlite3` (`library.py:25-35`), `BEGIN IMMEDIATE`, control de revision y estados (`:150-188,190-234`). `PROJECT_ID` es actualmente la constante `bago-agentic-data-lab:default` (`:13-14`), por lo que aún no representa identidad única para varios workspaces.
| MCP | `CapabilityRegistry` separa descubrimiento y registro; exige `approved_by`, conserva fingerprint/clasificación y deniega invocación sin registro (`src/adapters/mcp_adapter.py:109-123,162-259`). `GovernedMCPAdapter` valida schema, forma solicitud, emite Permit y produce `MCPCallReceipt` (`:315-347,349-419,421-505`). Hay CLI demo de servidor stdio en `scripts/run_mcp_demo.py:27-77`. | Registry vive solo en memoria del adapter (`mcp_adapter.py:182-187`), sin serialización/API. `scripts/run_mcp_demo.py` registra bajo identidad fija `l5-demo-policy`; no representa configuración del producto. El subárbol no recibe gestión del chat. Los tests cubren contratos pero **no se ejecutaron**.
| Permisos, gateway y sandbox | `Permit` tipado contiene request, decisión, restricciones, vigencia y emisor (`src/orchestration/state_graph.py:43-76`). `ExecutionGateway.execute` obliga `SandboxRequest` y valida que coincida ID de request (`src/execution/gateway.py:12-41`). `SandboxManager.execute` deriva política desde el Permit, consume IDs una vez por instancia, crea/ejecuta/destruye sandbox y devuelve recibo incluso al denegar (`src/sandbox/manager.py:57-159,162-232,234-316`). | Son componentes instanciables por código; no hay integración FastAPI, endpoint de revisión humana, emisión persistente de permit ni almacenamiento durable de `SandboxReceipt`. El cache de replay `_used_permits` está en memoria de cada `SandboxManager` (`manager.py:165-186`), no es global/persistente.
| Jobs y recibos | `GET /api/jobs/list` y `GET /api/jobs/{job_id}` leen historial (`server.py:1118-1160`). `POST /api/demo/run` y `/ws/demo/run` ejecutan `demo.py`, crean job tipo `demo` y lo guardan (`server.py:449-522,530-612`). | `src/jobs/__init__.py:11,36-67` usa JSON por job bajo `jobs/history`. No es el camino de ejecución de perfiles de agentes: `/ws/agents/run` envía error y cierra con 1008 (`server.py:1229-1246`). Los recibos de la demo también pueden proceder de `demo_output/latest` (`server.py:300-369`); no deben confundirse con recibos generados por el Agent Runner.

## Frontera de autoridad observada

1. **Perfil creado:** configuración JSON con nombre/tipo/prompt/modelo y posiblemente etiquetas de tools. No prueba capacidad instalada o elegible.
2. **Tool de lectura conectado:** disponibilidad fija dentro del backend y opt-in por mensaje; no atraviesa un catálogo administrable.
3. **MCP descubierto/registrado:** contrato Python local en memoria/demo. `register(... approved_by=...)` acepta una cadena no vacía, pero el registro no crea un endpoint ni persistencia durable.
4. **Autorización/Permit:** el adapter tiene política (`READ` auto-allow por defecto; otros efectos requieren aprobación humana) y construye Permit por request. La clase `Permit` es un objeto de datos, no una firma criptográfica. `explicit_approval` es parámetro Python sin flujo de confirmación de usuario conectado al chat (`mcp_adapter.py:263-270,381-419`).
5. **Ejecución/recibo:** gateway/sandbox son código separado. El Agent Runner real está deshabilitado y no crea job/recibo.

Además, `state_graph.py:256-319` contiene una puerta de demo que emite permisos para ciertos efectos y `execute_actions` usa `random`/`actual_effect={'mock': ...}` (`:323-360`); es una simulación de grafo y no debe interpretarse como evidencia de ejecución gobernada del producto.

## Persistencia sugerida para el MVP

1. Crear un almacén SQLite de capacidades local al usuario (puede convivir como archivo separado bajo `%LOCALAPPDATA%\BAGO\AgenticDataLab\capabilities\` junto a la biblioteca de conversaciones). No guardar el catálogo en memoria ni dentro del prompt/modelo.
2. Usar `workspace_id` estable derivado/confirmado por el binding del proyecto; corregir la actual constante `PROJECT_ID` antes de afirmar aislamiento multi-workspace.
3. Tablas mínimas: `capabilities` (id, proveedor, nombre, effect, fingerprint/schema, estado disponible, versión, timestamps); `agent_capability_assignments` (agente/capacidad/alcance); `capability_events` append-only (actor, antes/después, motivo, conversación/trace, revisión); `action_proposals` y `authorizations` (request hash, scope, decisión, actor, expiry); `execution_receipts` (permit/request/capability/version y outcome).
4. Actualizar transacciones con revision optimista (`BEGIN IMMEDIATE`/revision) ya usado en conversaciones. Nunca almacenar API keys en estas tablas; seguir con keyring para secreto.
5. El chat puede listar capacidades y preparar propuestas estructuradas; acciones de conceder, revocar y autorizar deben mostrar exactamente el alcance y exigir confirmación humana inequívoca fuera del texto libre del modelo. Chat no puede autoemitirse un Permit.
6. Mantener estados no equivalentes: `DISCOVERED`, `REGISTERED`, `AVAILABLE`, `ELIGIBLE`, `AUTHORIZED`, `EXECUTED`, `VERIFIED`. Cambiar catálogo debe producir evento auditable; solo un camino de ejecución conectado puede producir job y recibo.

## Riesgos / límites

- La inspección fue estática y de solo lectura; no se comprobaron rutas HTTP activas, Ollama, la UI, almacenamiento real ni Jaeger en este work item.
- No se ejecutaron tests ni demo MCP por instrucción del encargo. `tests/test_mcp_governance.py:1-55` solo documenta sus pruebas; no es evidencia de que este runtime tenga un servidor MCP configurado.
- El API local no muestra una identidad de usuario/actor asociada a `approved_by`; CORS/local-loopback no equivale a autenticación. No implementar aprobación a partir de una frase del modelo.
- Persistencia de agentes/jobs y configuración del proveedor está en el checkout; la biblioteca de conversaciones va bajo LocalAppData. Esto da ubicaciones y ciclos de vida distintos.
- El código de `src/orchestration/state_graph.py` tiene una vía simulada y aleatoria, y los recibos de sandbox se devuelven como objetos; el API no los guarda ni los vincula con `/api/jobs`.
- Worktree sucio: las conclusiones están ligadas a este snapshot activo; no afirmar que sean el contenido limpio de HEAD.

## Huellas SHA-256 de fuentes clave del worktree

- `src/api/server.py`: `958A6C7A2A1BAF0A04B8AD3BC76F36B0F80BB52AD8AA5E4718E01C480EC30A7E`
- `src/providers/ollama.py`: `E52D71268F2E1072EB6B32AF75103A66956855A59001BD0B3FE0B88CA352D7C9`
- `src/agent_tools/workspace_read.py`: `B30EF09867E28471FF0315D65AFCBF746085304D5E47D9DA392B30D112F65DEB`
- `src/adapters/mcp_adapter.py`: `EF22A50A0E5B3464B47536F67F581880B124D71B8CD8B9B90F85234FC76DB5BE`
- `src/execution/gateway.py`: `543D840857931FF69B41530FD6B8FE8EA6276039E21661BC0BA197D080FE1E26`
- `src/sandbox/manager.py`: `07B24BF62CAB172B65C58652177076C3080BD4D333D31325F28AF747817173AE`
- `src/orchestration/state_graph.py`: `2F070F5FC7F6A85BF0250A82B7F4B1C49CC71D14900699885613DE8F6B69FC11`
- `src/conversations/library.py`: `8E89041D4EB3F2D98B31DB182DCE174A459DD257291CE267F32D0201B82DFDE9`
- `src/jobs/__init__.py`: `BD8D08D9F9DF67172FEFE5BDF19D4277A364D3543158E64842126A1370522C08`

Verification: `NOT_RUN` (read-only static audit; no test/demo/runtime command executed). The report itself and its SHA will be registered by the W02 handoff.
