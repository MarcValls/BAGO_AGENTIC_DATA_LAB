# Capability Manager: contrato de MVP derivado de la espiral

## Identidad y evidencia de entrada

- Candidato: `C:\Users\AMTEC_Terminal_1º\AppData\Local\Temp\BAGO_AGENTIC_DATA_LAB_conversation_library`
- Rama/HEAD: `codex/conversation-library-v1` / `69b4f4b1ead2552b527e6e48868ab36cc2b38cbc`.
- El worktree ya estaba sucio antes de esta misión. Los auditores no editaron fuentes y sus reportes registran hashes de los archivos relevantes.
- Auditorías consumidas: [W01 arquitectura](W01_ARCHITECTURE.md), [W02 backend](W02_BACKEND.md), [W03 frontend](W03_FRONTEND.md). `teamctl verify` pasó antes de iniciar esta síntesis.
- Las definiciones locales bajo `agents/` indican `reference-only` y `activation: none`. En esta misión se activaron los tres perfiles de auditoría como agentes de análisis read-only por instrucción explícita del usuario; esto no cambia el estado del catálogo del producto.

## Hechos que gobiernan el diseño

1. El chat de control y el chat de agentes usan Ollama; la lectura de proyecto es acotada y read-only por turno. Crear un perfil de agente persiste configuración y no le concede ejecución.
2. `CapabilityRegistry` y `GovernedMCPAdapter` separan descubrimiento, registro y llamada, pero hoy son objetos en memoria usados por demo/tests; no están conectados al API ni al chat.
3. `ExecutionGateway`, `Permit`, `SandboxManager` y recibos son piezas reutilizables, pero no están conectados al Agent Runner. `/ws/agents/run` sigue rechazando con `execution_unavailable`; `/api/demo/run` ejecuta una demo distinta.
4. `AgentConfig.tools`, una lista de catálogo, un proveedor listo y un control visual no son autorización para producir efectos.
5. No hay identidad de usuario/actor en el API local. CORS y loopback limitan superficie, pero no identifican quién emitió una aprobación.

## Contrato del gestor

La app tendrá una única vista raíz **Capabilities**, propiedad del router de `App.tsx`, y el chat podrá abrirla por un destino enumerado. La vista mostrará un catálogo backend-owned y estados explícitos:

`DISCOVERED -> REGISTERED -> AVAILABLE -> ELIGIBLE -> AUTHORIZATION_REQUIRED/AUTHORIZED -> EXECUTED -> VERIFIED`

`DISABLED`, `UNAVAILABLE` y `UNKNOWN` deben poder mostrarse sin inferir transiciones. Las transiciones son independientes; ninguna equivale automáticamente a otra.

La fuente de la verdad será el backend. El catálogo persistente necesita identidad de workspace, ID estable de capacidad, proveedor/servidor, nombre, efecto, fingerprint de esquema/versión, estado, límites y marcas de tiempo. Se mantendrá un registro append-only de cambios y referencias a conversación/traza. Los secretos del proveedor se excluyen; siguen en el keyring del sistema operativo.

## Operaciones por chat y revisión

- `listar capacidades` y `estado de <capacidad>`: consultar una API de solo lectura y devolver los estados confirmados por servidor.
- `preparar propuesta para <capacidad>`: crear una propuesta tipada y persistida con ID, fingerprint exacto, efecto, alcance, actor/conversación, revisión esperada y caducidad. Si el nombre no coincide exactamente con una capacidad conocida, no seleccionar otra.
- La respuesta del modelo nunca ejecuta endpoints mutables. La propuesta se presenta en un panel con alcance y efecto legibles. Confirmar, rechazar o cancelar requiere controles explícitos de UI y endpoints dedicados; al volver del servidor se refresca el catálogo.
- Mientras no exista una identidad de actor y una política de autorización verificables, la propuesta puede persistirse y revisarse, pero **no puede convertir una capacidad de escritura/ejecución en autorizada**. Texto libre como “sí”, una respuesta del modelo o React state no constituye un permiso.

## Secuencia recomendada

### Fase 1: catálogo observable

- API read-only lista capacidades integradas y su disponibilidad real con fuente/fingerprint.
- Vista Capabilities y comandos de chat para listar, consultar estado y navegar.
- Marcar Agent Runner como no disponible. Capacidades presentes solo en demos o módulos sin conexión se muestran como no activadas.

### Fase 2: propuestas persistentes

- SQLite local del producto, separado de secretos y enlazado a identidad de workspace; revisión optimista y eventos append-only.
- Chat crea propuestas tipadas; controles UI revisan/cancelan/rechazan. No concede permisos de materialización.
- Cerrar antes el límite de identidad del actor para aprobar cambios que amplíen efectos.

### Fase 3: ejecución gobernada

- Conectar una capacidad concreta a `ExecutionRequest -> AuthorizationBoundary/Permit -> ExecutionGateway -> SandboxManager -> receipt`.
- Definir perfiles, alcance exacto del workspace, operaciones/ejecutables, red, vencimiento, revocación y consumo único persistente del permit.
- Vincular conversación, decisión, job, recibo, LocalTrace y proyección Jaeger. Ejecutar un piloto explícito antes de habilitar `Run`.

## Criterios de aceptación

- La vista y el chat muestran el mismo inventario backend-owned y estados tras recargar.
- Un nombre desconocido no crea una capacidad ejecutable.
- Crear o cancelar una propuesta no ejecuta procesos ni crea jobs.
- El modelo no puede llamar libremente a operaciones mutables ni concederse un permit.
- El Runner permanece deshabilitado mientras no exista una capacidad real conectada a la frontera de autorización y sandbox.
- Una futura ejecución solo se declara `EXECUTED` con efecto real y recibo; solo se declara `VERIFIED` con lectura posterior del efecto ligado al mismo request/permit.

## Decisión abierta antes de cambios mutables

El primer incremento de interfaz/API puede limitarse al catálogo read-only y propuestas. Para activar/desactivar concesiones desde la UI —especialmente escritura o ejecución— falta decidir cómo se demuestra la identidad del actor en esta app local sin login. No ampliar permisos hasta cerrar ese contrato.

## Límites

- Esta espiral es una auditoría y contrato de implementación; no implementó gestor, endpoints, persistencia ni ejecución.
- No se ejecutaron tests, build, browser, runtime ni llamadas a Ollama/Jaeger en esta misión.
- Los hallazgos aplican al snapshot sucio asociado al HEAD indicado; no afirman que el commit limpio por sí solo contenga esas fuentes.
