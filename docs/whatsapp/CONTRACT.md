# WhatsApp y Comunicaciones - contrato de implementación v1

## Autoridad y ámbito

Petición actual: sesión propia de BAGO por QR persistente; indicador de conexión
real; pantalla propia de comunicaciones, embebible en chat y editable por el
orquestador; envío inmediato, puntual y recurrente de mensajes/resultados.
Base remota obtenida con fetch: c5a78d33fbf5da608f550c4e8809eb6a8cb1be4c.
Trabajo aislado: codex/whatsapp-settings-20261022. Conservar main sucio y pruebas
externas existentes. El objetivo previo de seis casos sigue abierto.

No se autoriza con esta implementación enviar mensajes reales a nadie. La prueba
de conexión real requiere vinculación QR del usuario; la prueba de envío real
requiere destinatario y contenido concretos autorizados. No copiar cookies ni
tokens de otro perfil. No crear un nuevo coordinador de agentes.

## Producto y recorridos

1. Settings -> WhatsApp: guardar alias local, abrir WhatsApp en Brave visible con
   perfil exclusivo, vincular QR, comprobar conexión fresca, cerrar navegador
   conservando vinculación. Nunca inferir conexión del archivo de configuración.
2. Menú -> Comunicaciones: contactos propios de BAGO (nombre + número E.164),
   borradores, edición, adjuntos del workspace, revisión, envío/programación,
   historial y cancelación. Reutilizar un mismo componente en página y chat.
3. Chat: lenguaje natural -> propuesta estructurada de borrador/edición. El modelo
   no tiene herramientas de aprobación ni de envío. La tarjeta permite editar y
   confirmar la revisión del destinatario, texto, adjuntos y calendario exactos.
4. Scheduler persistente: puntual y recurrente diario/semanal, IANA timezone,
   días de semana ISO1..7, hora local. Revisión muestra siguiente fecha efectiva.
   Reinicios recuperan tareas, no hacen nuevos envíos de intentos inciertos.

## Interfaces congeladas entre trabajos

### Sesión y transporte (W02)

Paquete `src/whatsapp` exporta:

- `WhatsAppSession(state_dir: Path | None = None)`
- `.status() -> dict`: state, configured, label, checked_at, reason,
  browser_available, persistent_profile. Estados: not_configured, disconnected,
  linking, connected, unavailable, unknown. `connected` solo con sesión
  autenticada observada en DOM del WhatsApp Web de ESTE perfil y navegador
  accesible. No se leen/exportan conversaciones ajenas.
- `.configure(label: str, enabled: bool) -> dict`
- `.open() -> dict`: inicia/reutiliza SOLO perfil propio; abre web.whatsapp.com.
- `.close() -> dict`: cierra SOLO ese navegador; conserva perfil y vinculación.
- `.send(phone: str, text: str, attachments: list[Path], operation_id: str) -> dict`:
  consume un destino E.164 y contenido ya autorizado por W03. Selecciona el
  destinatario exacto; no basta buscar un nombre. Adjuntos son snapshots revisados.
  Retorna `status` (sent, failed, uncertain), `operation_id`, `message_id` opcional,
  `observed_at`, `reason`; `sent` requiere observación independiente de salida
  nueva atribuible al intento y acuse visible, no solamente click/teclas.
  No reintentar automáticamente una operación incierta.
- Fallos públicos: no incluir páginas, mensajes, cookies o credenciales en errores.
- API router `create_whatsapp_router(session=None)` en `src/api/whatsapp_routes.py`:
  GET `/api/whatsapp/session`; PUT misma ruta `{label,enabled}`;
  POST `/api/whatsapp/session/open` y `/close` con `{confirmed:true}`.
- State dir: BAGO_WHATSAPP_STATE_DIR o LOCALAPPDATA/BAGO/AgenticDataLab/whatsapp.
  CDP loopback propio, puerto distinto de9222, comprobar propiedad del perfil
  antes de controlar o cerrar navegador. No URL/comando arbitrarios del cliente.

### Comunicaciones (W03)

API base `/api/communications`, sin duplicar TaskStore de inferencia como scheduler
de efectos. Reutilizar sus patrones de SQLite, revisiones e historial.

- GET `/contacts` -> `{contacts:[{id,name,phone}]}`
- POST `/contacts` `{name,phone}` -> contacto; teléfono normalizado E.164.
- GET `/drafts` -> `{drafts:[Draft]}`
- POST `/drafts` `{contact_id,text,attachments,schedule,conversation_id?}` -> Draft
- PATCH `/drafts/{id}` mismos campos editables + `expected_revision` -> Draft
- GET `/drafts/{id}` -> Draft
- POST `/drafts/{id}/confirm` `{expected_revision,confirmed:true}` -> Draft
- POST `/drafts/{id}/cancel` `{expected_revision,confirmed:true}` -> Draft
- GET `/runs` -> `{runs:[Run]}`

Draft: id, revision (SHA256), contact_id, recipient `{id,name,phone}`, text,
attachments `[{path,name,sha256,size}]`, schedule, state, next_run_at (UTC|null),
created_at, updated_at, conversation_id|null, last_error|null.

Entrada attachments es lista de rutas relativas exactas del workspace. Snapshot
durable al preparar y revalidación antes de consumir. No traversal/reparse,
secretos ni sustitución de archivo tras aprobación. Indicar alcance y límites de
tamaño/tipo; aceptar PDF de resultados, texto/CSV/imagen dentro del límite.

Schedule: `{kind:'now'|'once'|'daily'|'weekly',timezone:'Europe/Madrid',
at:string|null,time:'HH:MM'|null,weekdays:number[]}`. `once.at` es ISO8601 con offset
explícito; daily/weekly.time es hora local. No aceptar horas inexistentes o
ambiguas por DST sin resolución explícita. No dar por UTC una hora local.
now/once/time/campos no aplicables se validan, no se ignoran silenciosamente.

Estados Draft: draft, scheduled, sending, sent, failed, uncertain, cancelled,
needs_review. Edición de confirmado/scheduled invalida autorización y vuelve a
draft; ninguna edición cambia un envío ya ejecutado. No aprobar desde LLM.
Confirmar now ejecuta vía transporte; confirmar otro calendario persiste y worker
ejecuta cuando corresponda. Cancelar evita nuevas ocurrencias y conserva recibos.

Run: id, draft_id, occurrence_at, started_at, finished_at|null, state, receipt|null,
error|null. Reclamo transaccional/único por draft+ocurrencia. Persistir sending
ANTES del efecto. Tras reinicio un sending sin recibo queda uncertain/needs_review
y no se reenvía. No prometer exactly-once externo. Sin sesión conectada, evidencia
inválida o dependencia ausente NO se registra sent. Si la hora se perdió fuera de
ventana acotada documentada, needs_review; no enviar muy tarde silenciosamente.
Recurrencia conserva contenido revisado; un archivo modificado exige nueva revisión.

Store: `CommunicationService(state_dir=None, session=None, workspace_root=None)`
con métodos contacts/create_contact/drafts/create_draft/update_draft/get_draft/
confirm/cancel/runs/tick/ recover. Router factory `create_communication_router(...)`.
Integración worker de lifespan arranca/parada efectiva en server existente; no
iniciar envíos durante import/tests. Overrides aislados por env
`BAGO_COMMUNICATIONS_STATE_DIR` y dependencia inyectable de reloj/transporte.

Chat devuelve `communication_draft: Draft` en su respuesta y guarda referencia ID
en conversación. Operaciones semánticas preparar/editar, nunca approve/send tool.
UI de W04 escucha ese campo. W03 amplía esquema y despacho de resolución existente
en src/api/server.py; su contrato TypeScript lo consume W04 sin inventar API.

### UI (W04)

- `WhatsAppSettings.tsx`: interfaz anterior en Settings -> WhatsApp; controles
  loading/error/unknown/fresco; poll limitado mientras visible; cancelar peticiones
  viejas, evitar estado conectado cacheado después de cerrar.
- `Communications.tsx`: `inline?: boolean`, `initialDraft?: Draft`,
  `conversationId?: string`; misma pantalla real y tarjeta del chat. Fuente de verdad
  servidor; estados y revisiones explícitos, conflictos409 recuperables sin perder
  texto del usuario; acción de confirmación visible separada de edición.
- App.tsx añade menú Comunicaciones y sección WhatsApp. AgentChat.tsx renderiza
  `communication_draft` retornado, conserva/recupera referencia de conversación y
  permite abrir pantalla completa. Evitar duplicar almacenamiento y lógica.
- Contrato no incluye componente simulado como conectado. Pruebas con fixtures
  deben identificarse; demo real usa el backend de esta candidata.

## Pruebas obligatorias y cierre

Sesión: no configurada, QR pendiente, navegador ausente/cerrado, sonda fallida,
perfil ajeno rechazado, persistencia tras reconstruir servicio, authed DOM real
solo con QR del usuario. Contrato de envío: destino correcto, adjunto inmutable,
acuse ausente -> uncertain; nunca ejecutar envío real en suite automática.
Comunicaciones: sin confirmar no efecto; editar revoca; datos inválidos; adjunto
ausente/alterado; replay confirmación; dos workers; crash antes/después del efecto;
once/daily/weekly, DST, hora pasada, cancelación, persistencia y recuperación.
UI: pantalla propia, misma tarjeta en chat, orquestador prepara/edita con ID y
revisión; mock no equivale a host. README desde generador y suite/regresiones al
cierre. No aplicar sobre main ni publicar hasta superar puertas pertinentes.

Capacidades que requieren contacto real autorizado quedan NOT_RUN hasta disponer
de ese dato; no enviar una prueba a un contacto elegido por el agente.
