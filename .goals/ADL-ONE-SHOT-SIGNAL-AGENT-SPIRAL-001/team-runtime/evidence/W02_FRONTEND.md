# W02 — Auditoría de frontend: lifecycle, chat y revisión

## Alcance y vínculo al candidato

- Misión: `ADL_ONE_SHOT_SIGNAL_AGENT_SPIRAL_001`, trabajo `W02`, rol `frontend-auditor`.
- Candidato según `evidence/W01_SCOPE.md`: worktree aislado `BAGO_ADL_agent_evaluation_lab_20261010`, rama `codex/adl-agent-evaluation-lab-20261010`, HEAD base `1e4d9f930da1225ce61ce27def897f76d57a08fc`.
- La fuente tiene cambios previos sin commit. Este informe observa los ficheros actuales del worktree, cuyos SHA-256 figuran debajo; HEAD por sí solo no identifica su contenido modificado.
- Auditoría de lectura únicamente. No se editaron fuentes de producto.
- Archivos locales pedidos por el adaptador frontend que no están presentes en este candidato: `.github/copilot-instructions.md`, `.github/skills/bago-frontend-engineering/SKILL.md` y skills de rol bajo `plugins/bago-agent-decision-engineering-team/skills/` para `frontend-auditor`. Se usaron el protocolo de misión, el scope W01 y los perfiles `bago-frontend-auditor`, `bago-ui-architecture-auditor` y `bago-ui-state-tracer` disponibles en `agents/04-frontend-ui/`.

## Hechos observados

### Creación asistida desde chat

- `frontend/src/App.tsx:27-36,47-52,74-77,98-104`: Chat es la vista inicial; el shell también registra Builder, Runner, Capabilities y Evaluation Lab. El chat puede navegar por destinos enumerados mediante `onNavigate`.
- `frontend/src/components/AgentChat.tsx:5-15,25-27`: el tipo de configuración describe identidad, prompt, proveedor/modelo, herramientas y opciones RAG/sandbox; no declara `lifecycle`, `trigger`, `signal_source` ni programación.
- `frontend/src/components/AgentChat.tsx:353-396`: el envío de chat llama `/api/chat/control` o al chat del agente. Para `draft_agent`, valida una propuesta no creada, carga modelos del proveedor y deja el modelo seleccionado en el borrador.
- `frontend/src/components/AgentChat.tsx:416-445,497-498`: guardar un borrador requiere el botón `Create agent`, modelo confirmado y campos no vacíos; cancelar solo descarta el borrador. La respuesta del endpoint se incorpora al inventario. Es un flujo de definición persistida con confirmación humana.
- `frontend/src/components/AgentChat.tsx:491-503`: la vista informa nombre/modelo del agente, lista conversaciones activas/archivadas/eliminadas, presenta errores y espera del proveedor, muestra fuentes de lectura y trazas vinculadas a mensajes. El mensaje de pie limita la lectura a archivos del proyecto por mensaje y dice que el chat no puede escribir ni ejecutar jobs.

### Builder independiente y revisión

- `frontend/src/components/AgentBuilder.tsx:4-15,48-60,62-94`: el Builder usa otra configuración local y pasos `select`, `configure`, `preview`, `complete`; la configuración no incluye un modo de ciclo de vida o trigger.
- `frontend/src/components/AgentBuilder.tsx:96-128,240-303`: el botón de guardar llama `/api/agents/create`; la vista previa permite revisión antes de ese guardado. El código expuesto no implementa ejecución de un agente ni espera de señal.
- `docs/agent-chat-control/contracts/CONTROL_PLANE_V1.md:28-38,46-54`: el contrato de control describe operaciones de chat acotadas; un borrador de agente se crea solo tras confirmación explícita, la lectura de archivos es opt-in y el Runner heredado debe permanecer fail-closed si no existe ejecución gobernada.

### Estado y ejecución visibles hoy

- `frontend/src/components/AgentChat.tsx:22-24,143-171,467-485`: `active`, `archived` y `deleted` son estados de conversaciones/chats por propietario, no estados de vida del agente.
- `frontend/src/components/CapabilityManager.tsx:18-31,73-89,109-120`: la UI refleja propuestas de capacidades con `PENDING_REVIEW`, `CANCELLED` y `EXPIRED`, puede cancelar una propuesta y afirma que ello no da permiso ni ejecuta código. No es una máquina de estado de agentes.
- `frontend/src/components/AgentRunner.tsx:24-25,57-61,186-219`: la constante de ejecución está fija en `false`; Run aparece deshabilitado y la UI informa que no hay capacidad de ejecución gobernada registrada. La lista de agentes no demuestra que puedan correr o esperar eventos.
- `frontend/package.json:1-20`: existe `test:ui` para Evaluation Lab; el manifiesto no expone un script dedicado de pruebas para chat, Builder o estados de agente.
- Inventario de `frontend/tests/`: existen pruebas renderizadas/cliente de Evaluation Lab, contratos de Inspector y P1-02 del Runner. `rg` no encontró pruebas específicas de `AgentChat`, `AgentBuilder`, propuesta/confirmación de creación, cambios de propietario con esos flujos, ni triggers/señales.

### Evidencia de contenido (SHA-256 actual)

- `frontend/src/App.tsx` — `bfee97a6e9f224274078e26bf2d89adb878aac75b58478b63b472696ee0011d0`
- `frontend/src/components/AgentChat.tsx` — `127ae7323d14f63d3b821ff440a2b540bf3b17646f559fad3bd91ab1e8c7faf2`
- `frontend/src/components/AgentBuilder.tsx` — `ad47e405be94cd7e2fc0ce67924e8673cbc43fad658f4d9e153f898b7ead8d39`
- `frontend/src/components/AgentRunner.tsx` — `d6bcff256f3ed47c8c8eda0de657b0e2727d660ec452c389ffccc147565a7dab`
- `frontend/src/components/CapabilityManager.tsx` — `873fa62c92aca80db95392614fbc70caaea12c991166d6b6a60672c13fba8347`
- `frontend/tests/ui/agent-evaluation-lab/rendered.test.mjs` — `a69fc47d857784a80c47c6a3984f15e785fae6a801f4b3a2bdd8f5ccdd0da3dc`
- `frontend/tests/ui/agent-evaluation-lab/agent-evaluation-lab.test.mjs` — `ca209885434af62535e4654a6f2b913fe148e2ffde64449bcb6d74fb0c3b704b`
- `docs/agent-chat-control/contracts/CONTROL_PLANE_V1.md` — `98de492e09becfdff66da36922bf16e533a5fef6f7f5440452d1e207e52ead67`
- `.goals/ADL-CONVERSATION-LIBRARY-001/goal.md` — `49c59d2b6b54f3888c9c28fd3800b9ebecaf9074e8606444f33f3d3233fffc02`
- `.goals/ADL-CAPABILITY-MANAGER-001/team-runtime/evidence/W04_CAPABILITY_MANAGER_CONTRACT.md` — `b2ef1214d88f898da5fdc451e46e9e88552297a92df2d1054dcbb81f1c5bb652`

## Inferencias de diseño para esta espiral

- La frontera de creación asistida ya ofrece una costura natural para presentar tipo de ciclo, pero los estados de definición deben separarse de los estados de ejecución. `Not created`/`Create agent` describe revisión y persistencia; no debería transformarse en `running` al guardar.
- Una sola lista de agentes podría mostrar un resumen de ciclo/estado, siempre que el backend entregue un estado persistido y verificable. La UI no debe derivar `waiting` porque un agente existe, porque el usuario lo seleccionó o porque el proveedor está configurado.
- `active/archived/deleted` de chats y los estados de propuestas de capacidad no se deben reutilizar para agentes: pertenecen a otros dominios.
- `Waiting for Ollama` hoy es estado transitorio del envío de una conversación (`AgentChat.tsx:498-503`), no una espera de señal de negocio.

## Recomendación para el contrato W04 (propuesta, no implementación)

1. Separar `definition_status` de `run_status`. La revisión/creación podría seguir `draft -> review -> saved`; un cambio de configuración debe pasar por revisión/guardado explícito.
2. Presentar dos tipos en el editor/chat solo cuando se defina el contrato: **one-shot** con tarea acotada, propietario, alcance, vencimiento y confirmación de ejecución; **signal-waiting** con señal exacta y estado de registro claramente visible. No inventar señales disponibles antes de elegir una fuente real.
3. Mantener estados del runtime como telemetría backend-driven, no estado optimista de React. Una taxonomía candidata para discutir en W04: `waiting`, `paused`, `queued`, `running`, `succeeded`, `failed`, `cancelled`, `expired`; `signal_received`/`authorization_required` pueden ser transiciones/eventos separados. No fijar esta lista como contrato sin acuerdo backend.
4. Para el MVP UI, revisar fuente y autorización antes de ofrecer el modo de espera. Si no hay integración/permiso, mostrarlo como `not available` o `proposal`, nunca como `waiting`.
5. Añadir pruebas renderizadas/handler para: borrador editable y cancelar sin persistir; guardado confirmado; modelo no disponible; una sola ejecución explícita; evento de señal válido/duplicado; waiting/paused/error/cancelled/completed/expired; refresco/reapertura desde servidor y ausencia de efectos al solo navegar/revisar. La cobertura debe afirmar qué hace el navegador sin simular autoridad del servidor.
6. Separar permisos de configuración. Seleccionar herramientas, proveedor, modelo o señal no concede autorización de ejecución; conservar Runner deshabilitado hasta el camino gobernado y sus recibos estén conectados.

## Riesgos y decisiones aún abiertas

- El selector de señal y su payload dependen de una fuente/evento que W01 deja sin decidir. El frontend no puede cerrar esa decisión solo.
- Identidad del propietario/actor, quién puede crear/pausar/cancelar, duración máxima, repetición, deduplicación/idempotencia, reintentos, caducidad y auditoría deben definirse antes de representar “registrado” como vigilancia activa.
- El worktree está modificado previamente; hashes documentan el contenido leído. No se calculó un fingerprint total de todos los cambios del candidato en esta tarea.

## Verificación

- **PASS (alcance de auditoría):** inspección estática de rutas/componentes/pruebas indicados; cada afirmación del mapa se vincula a líneas actuales y hashes.
- **NOT_RUN:** pruebas frontend, lint, build, navegador, llamadas de API, señales, ejecución de agentes, Jaeger/LocalTrace y validación del comportamiento runtime. No forman parte de esta asignación de auditoría read-only.
- No se modificó producto ni se afirmó una capacidad de trigger activa.
