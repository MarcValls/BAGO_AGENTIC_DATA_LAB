# Por qué siguen siendo seis y cómo ampliarlas — PROPOSED

## Reproducción ejecutada, sólo lectura

GET `http://127.0.0.1:8093/api/capabilities` produjo200 y exactamente6entradas. Recibo con fechas/ID de workspace opaco/IDs/estados/fingerprints en CAPABILITIES_LIVE.json. No se consultaron contactos, credenciales, configuración privada ni contenido de workspace; no modelos, pruebas o invokes. No producto, runtime, README, candidataRC10 o publicación cambiados. Goal Inspector sigue PAUSED.

| ID actual | status | integration | source_available |
|---|---|---|---|
| workspace.read_text | AVAILABLE | CONNECTED | false |
| workspace.scan_duplicates | AVAILABLE | CONNECTED | false |
| agent.evaluate | AVAILABLE | CONNECTED | false |
| mcp.execute | UNAVAILABLE | MODULE_PRESENT_NOT_CONNECTED | false |
| sandbox.execute | UNAVAILABLE | MODULE_PRESENT_NOT_CONNECTED | false |
| agent.run | UNAVAILABLE | FAIL_CLOSED | false |

Son seis porque `src/capabilities/manager.py:64-145` construye una lista fija de seis specifications; el frontend sólo la representa. La UI de propuesta guarda solicitudes PENDING_REVIEW sobre IDs ya existentes; NO registra un ejecutor ni instala una capacidad. CapabilityStore.create_proposal rechaza IDs fuera de ese catálogo. Añadir conexiones o herramientas al perfil no amplía esa lista automáticamente.

`source_available` tampoco es una prueba de disponibilidad de ejecución: `_source_fingerprint(root,path)` resuelve cada fuente bajo el workspace de usuario seleccionado, no bajo la identidad del paquete que ejecuta el backend. El endpoint pasa `current_workspace_root()`. Un proyecto legítimo sin `src/api/server.py` devuelve false aunque el backend esté funcionando. PACKAGE_SOURCE_COMPARISON.json muestra las fuentes presentes/hash en L, separado expresamente de una atestación del paquete live. No se afirma haber leído el workspace privado ni identificado su contenido. Corregir el origen de fingerprint NO autoriza invocación ni convierte los3UNAVAILABLE enAVAILABLE.

## Tres inventarios hoy desconectados

1. Catálogo público6IDs anterior, estático.
2. Opciones configurables5IDs en AgentBuilder y allowlist backend de perfil (abajo), también estáticas.
3. Funciones que realmente se entregan al modelo por turno, determinadas en server._chat_with_workspace_read por grants/flags y contexto.

No hay un registro único llamado TOOL_CATALOG en estas fuentes activas. TOOL_CATALOG_MAP.json conserva los nombres/IDs exactos y límites.

### Catálogo configurable del perfil, exacto

`frontend/src/components/AgentBuilder.tsx:33-39` TOOL_OPTIONS y `src/api/server.py:170-176` AGENT_TOOL_ALLOWLIST:

- bedrock.converse
- mcp.execute
- ontology.query
- retrieval.search
- sandbox.run

AgentConfig valida/persiste config.tools contra esa allowlist. Eso acredita configuración, NO que cada ID tenga un dispatcher accesible en el chat o el Runner actual. `sandbox.execute` del catálogo y `sandbox.run` del perfil no son IDs idénticos ni se deben tratar como alias de autoridad sin contrato. Bedrock es un adaptador/proveedor; ontology/retrieval tienen módulos y puntos de entrada independientes, no un puente genérico de estas cinco cadenas al chat.

### Herramientas reales del chat

| Nombre de función | Consumidor/gate actual | Ausencia en catálogo6 |
|---|---|---|
| read_workspace_file | Orquestador/agente, sólo paths autorizados del turno y contexto exacto | Se describe bajo workspace.read_text; ID distinto |
| scan_code_duplicates | Orquestador/agente, sólo directorios autorizados | Se describe bajo workspace.scan_duplicates; ID distinto |
| public_web_read | Orquestador/agente, autorización por orígenes y lector público limitado | Falta entrada propia |
| propose_workspace_write | Chat de agente, opt-in por turno y raíz SDK-owned exacta; sólo prepara revisión, NO aplica archivo | Falta entrada propia |
| resolve_control_request | Orquestador allow_navigation; decide propuesta/navegación y tipos admitidos | Falta entrada propia, no es permiso de ejecución genérico |

El bucle `_chat_with_workspace_read` monta estas funciones por `authorized_paths`, `authorized_directories`, `web_reader`, `write_workspace` y `allow_navigation`; no intersecta allí con `config.tools`. Por tanto, elegir una casilla de perfil no es hoy el control de asignación efectivo para lectura/web/propuesta de escritura. La autorización por turno sí se valida backend. No atribuir disponibilidad por proveedor/modelo sin observar su tool-calling real.

## Entradas independientes que no son automáticamente agent-tools

- `/api/knowledge/ingest-and-answer`: RAG explícito de aplicación; `/api/ontology/query` y propuestas/aprobación de ontología: funciones de servicio. No equivale a registrar retrieval.search/ontology.query como ejecutores del chat.
- `/api/evaluations/suites/{suite_id}/run`: evaluación explícita, preflight/revisión/proveedor, sin tools. Es la entrada descrita por agent.evaluate, no una herramienta entregada al modelo.
- `/api/agents/{agent_id}/task-runs`: tarea guardada, confirmación+revisión y elegibilidad de modelo; prompt/servicio sólo respuesta de modelo, sin ejecución de herramientas. No equiparar a agent.run genérico.
- `/api/workspaces/v1/**`: SDK de archivos/Git/workspaces con confirmaciones e identidades. Chat `workspace_action` genera propuesta UI; no ejecuta SDK automáticamente. `propose_workspace_write` sólo prepara un archivo; apply_write exige confirmación/revisión/hash/contexto independientes.
- `/api/contacts/v1/**`: Contacts SDK/local y Google según configuración; no una herramienta de agente ni permiso para importar/enviar por figurar en el menú.
- `/api/communications/drafts`, `/{id}/confirm`, `/runs`: borrador/revisión/envío y programación. `resolve_control_request:communication_draft` YA puede crear/actualizar borrador persistido con revisión/contacto/conversación; esto es efecto de borrador real, NO envío autorizado. La confirmación/envío es otro control humano del servicio. No describir todas las propuestas del orquestador como carentes de persistencia.
- `/api/whatsapp/session`: configuración/open/close de sesión; conectada no significa enviar autorizado. Comunicaciones depende de ella y de confirmación vigente; no exponer como agente-invocable por defecto.
- `/api/connections/{id}/discover` y `/{id}/invoke`: integración externa manual con confirmación, revisión de conexión, herramienta/fingerprint/esquema y efecto declarado; no bridge genérico de agentes MCP. No se ha llamado aquí.
- `/api/gex/**`: fixture.read separada/autenticada con su protocolo; no habilita agent.run.
- Módulo BER AgentRunner tiene sandbox.run y efectos tipados acotados, binding y revisión; en server actual se importa pero no se encontró instanciación/ruta productiva nueva. `/ws/agents/run` responde execution_unavailable. Existencia de clase/adaptador ≠ conexión invocable. App runner actual presenta AgentTasks y demostraciónGEX, no presume ejecución genérica.

## Vocabulario propuesto, independiente por dimensión

- **Registrada**: descriptor versionado, schema/efecto/consumidores y ejecutor identificado. No un permiso.
- **Configurada**: requisitos de proveedor/conexión/perfil guardados para una revisión concreta. No prueba de conexión ni ejecución.
- **Conectada**: ruta/dispatcher/adaptador realmente enlazado para ese consumidor; separar salud actual y compatibilidad de herramientas. El CONNECTED estático actual no es una sonda live.
- **Autorizada**: permiso válido para ESTA operación/efecto/ámbito/actor/conversación/revisión. No booleano global permanente por capacidad.
- **Verificada**: recibo de ejecución/comprobación concreta con identidad de paquete/descriptor/perfil/configuración/modelo/ámbito y resultado/fecha. No extender un éxito a todos los consumidores ni a otras revisiones. Fallo, desconocido y NOT_RUN deben conservarse.

## Plan finito, después de publicar el estado verificado

### C01 — inventario único e identidad de fuentes

Registrar descriptores de las capacidades YA cableadas desde una fuente canónica consumida por API, UI y opciones de perfil. Separar `package_identity/source_identity` de `workspace_scope`; conservar IDs/aliases versionados, efecto real (READ, DRAFT_WRITE, PROPOSE_WRITE, MODEL_INFERENCE, HUMAN_CONFIRMED_ACTION), consumidores permitidos y reason codes. PublicWeb/propuestaescritura/controles de propuesta y servicios UI deben ser distinguibles, no declararse todos agent-invocable. Fingerprints desde paquete/manifest que ejecuta el servicio; disponibilidad de fuentes desconocida si no se distribuyen, sin confundir con ausencia de ejecutor. Sin nuevas operaciones.

Aceptación: catálogo y opciones de consumidor derivan del registro; workspace sin árbol fuente no oculta identidad instalada; paquete modificado/fuente faltante se detectan; cada descriptor apunta a un callable/ruta real o queda unavailable con razón. Mantener3UNAVAILABLE si no hay conexión real.

### C02 — asignación efectiva por perfil y contexto

Contrato versionado de asignación que el backend resuelva como intersección de capacidad registrada+conectada, perfil, compatibilidad proveedor/modelo y autorización específica del turno. Constructor sólo ofrece IDs relevantes; persistir revisión y rechazar toolcalls no asignadas/desconocidas incluso si el modelo las inventa. Congelar antes la migración de perfiles actuales y permisos por turno: no habilitar ni deshabilitar silenciosamente comportamiento anterior. UI debe distinguir permitido/configurado de concedido para esta operación.

Aceptación: positivo de una función ya implementada asignada y con grant; negativas sin asignación, grant ausente, owner/conv/revisión/raíz ajenos o stale y cambio de config en vuelo; cero efecto al negar. Recibo correlacionado y persistido. Sin escoger nuevos servicios peligrosos para demostrarlo.

### C03 — orquestador: borradores/propuestas frente a invocación

Catalogar exactamente resolve_control_request y sus salidas: draft_agent sin guardar perfil, communication_draft persistido sin envío, workspace_action sin ejecutar SDK, navegación con confirmación, lecturas con grant. Mostrar efectos exactos y estado. Para añadir otra capacidad necesaria, exigir descriptor+implementación+validadores+recibo reales antes de ofrecerla; un botón o tarjeta no es implementación. Primera ronda no convierte confirm/send de Comunicaciones, cambios SDK o sesiónWhatsApp en acciones autónomas.

Aceptación: flujo positivo al borrador existente, identidad/revisión/contexto correctos y no envío; rechazo de contacto/adjunto/revisión ajenos; navegación/propuesta no produce escritura de archivo ni autorización; registros de decisión distintos de recibos de efecto.

### C04 — conexiones, sandbox y runners externos

Trabajo separado y más amplio: elegir UNA integración/efecto limitado. Conexión y herramientas descubiertas congelan esquema/fingerprint/efecto/revisión; asignación explícita+revisión humana+grant acotado+timeout/cancel y recibo antes de conectar al modelo. Sandbox/BER requiere entrada de producto real, perfil/firma/versiones y operación tipada admitida, sin fallback shell o legado. GEX y tareas-modelo permanecen perfiles distintos. No declarar mcp.execute/sandbox.execute/agent.run AVAILABLE por instalar módulo ni por una prueba de fixture.

Aceptación: positivo del único efecto admitido sobre datos sintéticos, negativas de argumentos/efecto/schema/revisión/contexto y aprobación ausente, timeout/cancel sin dobleejecución, recibo y recuperación tras reinicio. Observación independiente del paquete exacto. No se ejecuta en esta auditoría.

## Límites de esta entrega

Único runtime consultado: GET capabilities de8093, sin endpoints que puedan expirar/modificar propuestas ni información privada. Mapa de rutas y fuenteL no prueba salud de cada servicio ni equivalencia byteaByte del backend live al árbolL; hashes de componentes se entregan separados. Todo control nuevo C01–C04 sigue PROPOSED, sin cambios al producto/README/runtime ni conflicto con publicaciónRC10. Próximo paso recomendado tras publicación: congelar sólo contratoC01 y una misión de inventario/identidad, no desbloquear todas las capacidades juntas.
