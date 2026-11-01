# Flujos pendientes después del recorrido

Este documento se limita al [vídeo real](BAGO5_usuario_real.mp4) y su [cronología](TIMELINE.md) ([CSV](TIMELINE.csv), [JSON](TIMELINE.json), [SRT](SUBTITULOS.srt)). No es un inventario completo del producto ni declara publicación o cierre global.

## Trabajo que sigue abierto

| Flujo | Lo observado | Qué falta para comprobar el resultado solicitado |
|---|---|---|
| **F01 — arranque en chat** | FAIL. Recargar abrió Proyecto e Historial sobre el chat; se cerraron manualmente. | Arrancar y recargar la aplicación mostrando el chat con ese panel cerrado. Verificar la interfaz y la persistencia del comportamiento. |
| **F03 — presupuesto y redacción para cliente** | FAIL. La petición acabó en Comunicaciones y exigió un contacto; no calculó ni redactó. No se envió nada. | Resolver esa intención compuesta sin desviar el cálculo a un envío. La reformulación F04 dio 199,80 €, pero no sustituye la prueba original. |
| **F10–F12 — analizar el CSV desde el chat** | BLOCKED/BLOCKED/FAIL. Se pidió archivo autorizado; Consultar archivo rechazó CSV; guardar READ no produjo la lectura ni el análisis solicitados. | Observar una lectura real y autorizada del CSV, una respuesta ligada a esos datos y cálculos contrastados. Mostrar el diagnóstico preciso si una vía no admite el formato. La vista Tabla no demuestra este flujo. |
| **F13 — crear y probar la utilidad Python** | BLOCKED. No se crearon `calcular_pedidos.py` ni sus pruebas. La vía Tareas observada genera texto y no ejecuta herramientas, comandos ni escrituras live. | Una ruta real y gobernada que permita revisar y aplicar código, ejecutarlo y contrastar sus resultados. No atribuir la carencia a un permiso que el usuario hubiera denegado. |
| **F14/R26 — tres casos exactos del encargo** | El plan textual fue real; el propio autor indicó que no tenía el encargo guardado y propuso ejemplos provisionales. La revisión textual volvió a señalar esa ausencia. | Identificar y proporcionar el encargo, contrastar sus tres casos exactos e implementarlos y ejecutarlos cuando exista una ruta autorizada para ello. Una propuesta de tres ejemplos no satisface este requisito. |
| **F16 — multitarea y paralelo** | BLOCKED. No se despacharon los dos encargos independientes. | Dos tareas reales con identidades y alcances definidos, evidencia de concurrencia y dos resultados contrastados. No bastan dos perfiles guardados o una respuesta que describa un plan paralelo. |
| **F18 — menú con barra contraída** | FAIL. Pulsar Agentes expandió la barra. | Navegar con el desplegable conservando el modo contraído y comprobarlo visualmente. |

## Resultados ya comprobados, con alcance limitado

| Parte del recorrido | Resultado acreditado | Lo que no acredita |
|---|---|---|
| F05–F09 | Selección del directorio de pruebas; creación y sobrescritura del CSV; movimiento/renombrado; papelera y restauración con bytes verificados. | Escritura autónoma desde Tareas, gestión de código fuente completa o acceso sin permisos. |
| R19–R21 | CSV en Tabla y Texto; celdas complejas literales; aviso de CSV inválido y recuperación sin cambiar bytes ni fecha. | Lectura y análisis del mismo CSV por el chat ni ejecución de fórmulas. |
| F14 | Respuesta real del modelo guardada: un plan distinto de la solicitud. | Creación de archivos, pruebas ejecutadas o cumplimiento de los tres casos exactos. |
| R25 | Edición manual; ejecución bloqueada con borrador; cancelar conserva cambios locales y descarte confirmado restaura la tarea guardada. | Que ese ensayo haya guardado o ejecutado una modificación nueva. |
| R26 | Otro perfil emitió una revisión real, persistida y vinculada a la respuesta original. Se comprobó que el original no cambió. | Independencia de modelo: autor y revisor usaron Codex `gpt-6.1-sol`. Es una opinión textual, no aceptación, verificación de ejecución ni aprobación automática. |
| R27 | Copiar como borrador no ejecutó ni creó otra identidad de tarea; exigió guardar antes de ejecutar y permitió recuperar el original mediante descarte confirmado. | Ejecución de herramientas o un runtime paralelo. |
| F17 | Inspector mostró registros y un evento completado ligado a la conversación. | Que la tarea de negocio, la utilidad Python o una evaluación hayan pasado. |

La [verificación LIVE](LIVE_ACTIONS_VERIFICATION.json) contiene 18 comprobaciones del recorrido de edición/copia/revisión. Sus resultados no se extrapolan a toda la aplicación.

## Presentación del historial: conservar la secuencia

F15 fue FAIL: inicialmente se mostró la solicitud bajo «Respuesta recibida» sin una distinción clara. La comprobación posterior [F22-check.json](F22-check.json) registra respuesta antes de solicitud, etiquetas y copia como borrador correctas. F22 pertenece al tramo fuera de captura A; por tanto no se cambia el resultado histórico F15 ni se atribuye su evidencia a un vídeo inexistente. La edición, revisión y copia posteriores sí tienen recaptura R25–R27.

## Límites de la evidencia audiovisual

- El vídeo dura **38:01**, es **silencioso** y contiene texto explicativo quemado. No hay narración ni audio generado.
- Muestra el área capturada de Brave; no todo el escritorio ni una aceptación de la aplicación desktop completa.
- El segmento A terminó tras `Not attached to an active page`. F19–F23 quedaron documentados fuera de esa captura y los ensayos necesarios se repitieron con nuevos IDs en B. El montaje no representa continuidad sin cortes. Véase [CAPTURE_GAP_VERIFIED.json](CAPTURE_GAP_VERIFIED.json).
- La configuración comprobó acceso a Luna; la traza de las ejecuciones reales posteriores identifica Sol. No se atribuyen a Luna esas respuestas.
- El recorrido utilizó cambios de runtime locales documentados. No acredita una única versión congelada durante todo el vídeo ni una publicación en GitHub.
- No se ejecutaron herramientas desde TaskRunner/Tareas, no se materializó la utilidad de código, no se ejecutaron sus tres casos exactos y no se demostró runtime paralelo.

La [verificación del vídeo](VIDEO_VERIFICATION.json) y [R26-context-raw.json](R26-context-raw.json) permiten contrastar el material audiovisual y la revisión real, respectivamente. Los nuevos flujos deberán añadir sus propias acciones, resultados y evidencias, conservando estos fallos y bloqueos históricos.
