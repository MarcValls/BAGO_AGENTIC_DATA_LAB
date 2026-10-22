# Capturas actuales y demostración desde Chat — 22 de octubre de 2026

Estas imágenes se tomaron durante la sesión de trabajo del **2026-10-22**, mediante
`brave_screenshot`, en una misma pestaña de **Brave visible**, abierta en
`http://127.0.0.1:8080/`. Se mostraron al usuario al tomarlas. Son PNG originales,
sin recorte, retoque, montaje ni sustitución de respuestas. No se reutilizan las
capturas del tutorial del 19 de octubre.

## Recorrido observado

1. Abrir la aplicación local ya en ejecución y observar su interfaz.
2. Abrir Conversations and agents y pulsar New: conversación nueva.
3. Pedir en lenguaje natural un agente nuevo: **BAGO Demo Chat 20261022**.
4. Revisar el formulario que aparece dentro del chat: tarea documental acotada,
   tipo `tool`, modelo `codex / gpt-6-luna`, sin herramientas de ejecución.
5. Preview y Save Agent. El primer guardado rechazó una diferencia entre el modelo
   del agente y el registro del proveedor. Settings permitió guardar y comprobar
   GPT-6-Luna; el segundo guardado creó el agente.
6. Preparar una carpeta nueva con [DEMO.md](../../verification/readme-corporate-20261022/demo/DEMO.md),
   dos pedidos ficticios y una regla de retrasos. Seleccionarla mediante Workspace.
7. Elegir el agente nuevo en la biblioteca: conversación del agente nueva.
8. Activar Allow project file reads, introducir **DEMO.md** como única ruta
   autorizada y enviar la petición. El texto de autorización por sí solo no
   sustituye el control de rutas del formulario.
9. Observar dos respuestas y las citas: DEMO-001, 30 horas, devolución de 6 €;
   DEMO-002, 12 horas, sin devolución. La lectura figura como ALLOW, líneas 1–16.
10. Abrir Inspect y Trace: aparece una **traza diferente del caso Bruma**. Esta
    limitación queda registrada; su evaluación no valida el chat nuevo.

## Qué muestra cada imagen

| Archivo | Observación actual | Alcance |
|---|---|---|
| [chat.png](chat.png) | Respuesta del agente nuevo, citas y lectura ALLOW | Inferencia y lectura real del fixture sintético; no ejecución de pagos |
| [chat-created.png](chat-created.png) | Confirmación Agent Created dentro del chat | Creación del perfil después de la revisión y el guardado |
| [workspace.png](workspace.png) | Carpeta nueva seleccionada | No tiene archivos de canon ni memoria general conectada |
| [agent-builder.png](agent-builder.png) | Formulario independiente abierto durante la navegación | Captura actual de interfaz vacía; no prueba creación ni proveedor disponible |
| [inspect.png](inspect.png) | Panel Trace abierto hoy | Muestra `trace-5b385699ffda0529`, del fixture Bruma; **no es la traza de este chat** |

La fecha de captura no cambia la procedencia de los datos que una pantalla muestra.
Los hashes y dimensiones originales figuran en [SHA256SUMS.json](SHA256SUMS.json).

## Evidencia y contraste independiente

- [Resultado y hallazgos](../../verification/readme-corporate-20261022/demo/RESULT.json).
- [Perfil nuevo persistido](../../verification/readme-corporate-20261022/demo/agent-created.json).
- [Traza de lectura](../../verification/readme-corporate-20261022/demo/trace-496fac766f384348.json).
- [Contexto cognitivo baseline](../../verification/readme-corporate-20261022/demo/cognition.json).

Identidades: agente `agent_fe4947cc99074167ae5935d421dfc7b2`, conversación
`conv_3a8cd957b69a4ddd9026ef065405ace1`, traza `trace-496fac766f384348`.
El archivo original tiene SHA-256
`7fdbb3379f3abc59ef1d3c9fa5c9ffb4c7c2abc5de93a9c038e3ca8c25716677`.
El hash visible en Project files read,
`06b52e0bbf4c33e4d6cf5db09da1ff86a2e9dd38f1020b094563687b7b05338a`,
corresponde al **fragmento numerado** leído. Ambos se recalcularon desde el archivo;
las citas de política y datos se contrastaron con las líneas 7, 8, 12 y 13.

## Entorno y límites

Windows; servidor existente iniciado con `.venv/Scripts/python.exe -m src.api.server`,
PID observado 88708, loopback 8080. Fuentes del checkout principal
`2d521170fdf651da482b5bf9d5b229a41412a8d2`; frontend servido desde `frontend/dist`.
Los hashes de servidor, índice y JavaScript servido se conservan en RESULT.json.
El checkout tenía cambios locales previos preservados. La captura verifica el
runtime descrito, no una instalación nueva del worktree de documentación.

El proveedor Codex respondió con GPT-6-Luna. La traza declara `cost_status=not_reported`:
el valor numérico 0 no acredita uso gratuito. Modo cognitivo **baseline**; no se
demuestran aprendizaje continuo, pagos, sandbox ni ejecución genérica del Agent Runner.
La selección de carpeta y el registro del modelo requirieron controles de interfaz.
La creación, revisión y confirmación del perfil sí sucedieron dentro del chat.

La conexión automática **chat actual → Inspect** queda **FAIL en esta observación**.
Para cerrarla: abrir desde esa conversación su traza real y comprobar que el panel
presenta el mismo identificador, agente, fuente y lectura. La evidencia local del
chat existe y se conserva aunque ese enlace visual esté pendiente.
