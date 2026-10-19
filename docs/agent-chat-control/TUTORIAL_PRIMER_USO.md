# Videotutorial de primer uso

El [vídeo actual narrado en español](assets/ADL_videotutorial_ui_actual_2026-10-19.mp4) dura 68,04 segundos. Se grabó el 2026-10-19 sobre la UI actual servida en `127.0.0.1:5173`, con Playwright, narración local, subtítulos incrustados y [SRT independiente](assets/ADL_videotutorial_ui_actual_2026-10-19.es.srt). La navegación y los componentes visibles son los del frontend vigente en este checkout.

Las respuestas de API del recorrido son sintéticas e interceptadas dentro de un contexto aislado de Playwright. El historial mostrado es de demostración; no se consultaron conversaciones reales, no se guardó un agente y no se ejecutó ningún trabajo.

SHA-256 del MP4 actual: `61cf2b1c85a71e0079342a887cf3201a4c9be8b5a492bb7504bd99f1878104a9`. La captura se reproduce con [`record_current_ui_tutorial.py`](../../scripts/record_current_ui_tutorial.py); sus nueve segmentos de narración local están bajo `assets/narration/ui-actual-2026-10-19/`.

El [Manual visual de BAGO](MANUAL_PARA_DUMMIES_CAPTURAS.md) contiene capturas de un recorrido anterior. No se regeneró en esta tarea y no es evidencia de la UI que aparece en el vídeo actual.

## Evidencia histórica: interfaz del 2026-10-10

El vídeo anterior se conserva como evidencia de una sesión real de la UI antigua: [MP4 histórico](assets/historical/ADL_videotutorial_primer_usuario_2026-10-10.mp4), [SRT histórico](assets/historical/ADL_videotutorial_primer_usuario_2026-10-10.es.srt) y [LocalTrace asociada](assets/trace-c7ec5fcc40284a42.json).

### Recorrido de la grabación histórica

1. Bienvenida del chat y consulta del inventario de agentes.
2. Pantalla completa de ajustes del proveedor Ollama Cloud. El estado muestra API key y `gemma4:31b`; el recuadro de credenciales queda cubierto por una máscara. No se muestra el valor de la clave.
3. El agente persistido **Frontend Auditor**, fijado a `kimi-k2.6`, lee el archivo benigno [`sample-note.txt`](../../output/tutorial/sample-note.txt). La respuesta y el recibo aparecen en el chat.
4. El asistente propone un borrador de agente usando el modelo global; la persona cancela la propuesta. No se crea un segundo agente.
5. Navegación a Agent Builder.

### Alcance de esa grabación histórica

La [LocalTrace](assets/trace-c7ec5fcc40284a42.json) registra `agent.chat`, `provider_id=ollama-cloud`, `model_id=kimi-k2.6`, `outcome=response_received`, una lectura de `output/tutorial/sample-note.txt:1-8` y estado `COMPLETED`. Es evidencia local de esa lectura y respuesta. El asistente global aparece configurado con `gemma4:31b`; no debe confundirse con el modelo fijado al agente lector.

La grabación demuestra una lectura acotada del archivo de ejemplo y una respuesta real del proveedor. No demuestra que Frontend Auditor auditara el código fuente del proyecto, que modificara archivos o que ejecutara un job. La propuesta cancelada tampoco crea un nuevo agente.

La captura histórica se hizo sobre la UI local de `127.0.0.1:8081`. El vídeo se produjo el 2026-10-10 y refleja ese estado antiguo de la aplicación. SHA-256 MP4: `77FE889B7CB7793ABF4F11118C01F9861789E6F94589A11D8E0BDA851151DDB4`; SHA-256 SRT: `4256621AC527878A7A7E0AB0C04EC2085126FB3F778A3B5B2966E850DA1B8B96`.

## Qué aparece dentro del chat

No hace falta recordar una frase ni usar un comando exacto. Describe con tus palabras lo que quieres consultar o preparar. Si la respuesta es un resultado acotado o un formulario revisable, BAGO lo presenta en el mensaje del asistente.

Ya se pueden materializar dentro del chat:

- El historial real de jobs como tabla con filtros.
- El inventario de agentes.
- El borrador editable de un agente y su vista previa; guardar sigue requiriendo que pulses **Save Agent**.
- El catálogo de capacidades y una propuesta de capacidad para revisar.
- Lecturas autorizadas de archivos con sus rutas y recibos de evidencia.
- El texto de respuesta de un agente con los datos de traza disponibles.

También encajan bien como siguientes respuestas en chat: el detalle breve de un job, un resumen de evaluación o ejecución, una traza corta con enlaces a evidencia y el estado de solo lectura del proveedor/modelo. Esos formatos requieren su propio mapeo antes de considerarlos disponibles.

No encaja bien dentro de un mensaje una tarea que necesita una superficie de edición extensa o trabajo sostenido: introducir o cambiar credenciales, ajustar en detalle el comportamiento cognitivo, configurar experimentos de evaluación, inspeccionar trazas largas o revisar decisiones y autorizaciones con mucho detalle. Para eso se usan las vistas completas, como Provider & models, Cognition & context, Agent Evaluation Lab, Trace, Decision Inspector o Authorization.

Si pides un contenido que puede aparecer aquí, se queda aquí. Si pides ir a una pantalla completa que no puede materializarse en el chat, BAGO mostrará una pregunta con el destino y esperará a que elijas **Sí, cambiar de pantalla** o **Seguir en el chat**. No cambiará de pantalla por iniciativa propia ni por una interpretación ambigua.

Por ejemplo, “enséñame los jobs recientes” muestra la tabla dentro del chat; “abre la pantalla Job History” pregunta antes de cambiar de vista. “Diseñemos un agente para soporte” muestra el formulario aquí; “abre Agent Builder” pregunta antes de cambiar.

Las acciones con efectos —guardar un agente o una propuesta, conceder capacidades, ejecutar un agente/job, modificar archivos, instalar o publicar— necesitan un control explícito y la autorización correspondiente. Mostrar una propuesta o un resumen no ejecuta esas acciones.

### Capturas paso a paso

Estas imágenes pertenecen al manual visual anterior y muestran flujos de demostración. No se actualizaron junto con el vídeo actual; no representan una ejecución real ni un agente guardado.

1. El chat listo para recibir una petición.

   ![Chat inicial de BAGO](assets/manual/01-chat-inicial.png)

2. Al pedir los jobs, la tabla aparece dentro de la conversación.

   ![Historial de jobs dentro del chat](assets/manual/02-historial-jobs-en-chat.png)

3. Al describir un agente, el formulario aparece en el mismo chat. Revisa sus campos y usa **Preview** antes de guardarlo.

   ![Borrador editable de agente dentro del chat](assets/manual/03-borrador-agente-en-chat.png)

4. Si pides abrir Agent Builder, BAGO pregunta antes de salir del chat. El cambio solo ocurre al elegir **Sí, cambiar de pantalla**.

   ![Confirmación antes de cambiar de pantalla](assets/manual/04-confirmar-cambio-de-pantalla.png)

Para conversar con un agente ya creado, selecciónalo en la lista.

La navegación y las funciones de la aplicación se procesan desde **App assistant**; al seleccionar un agente, el mensaje se envía a ese agente.

## Lectura de archivos y propuestas

La lectura de archivos está desactivada inicialmente. Al activarla, indica rutas relativas exactas, una por línea; la autorización se limita a ese turno y permite lectura, no escritura ni ejecución de trabajos. La aplicación conserva el resultado de lectura y sus recibos de integridad.

Una propuesta de capacidad se guarda para revisión; no concede permisos ni inicia trabajos. Crear un perfil de agente tampoco concede permisos de herramientas o de control de la aplicación. Los modelos disponibles en el borrador proceden del proveedor configurado.

El panel de Cognition & context distingue el modo Baseline del modo experimental BAGO5. El panel BAGO5 expone señales acotadas de atención usadas como guía del prompt; no representa razonamiento interno oculto del modelo.

## Workspace

La pestaña **Workspace** muestra la carpeta de proyecto vinculada a la aplicación y permite guardar rutas para el contexto y la memoria: contexto del proyecto, estado, continuidad, conversaciones y trazas. Cada ruta se guarda en este navegador y se comprueba si existe. La memoria de chat corresponde al historial de conversaciones. Elegir una ruta no carga su contenido; para que el asistente lea un archivo, autoriza su ruta exacta desde el chat.

El chat sigue siendo la puerta para pedir cualquier vista o función. Si pides abrir **Workspace**, BAGO pregunta antes de cambiar de pantalla.

## Buscar código duplicado

Describe al orquestador que quieres localizar código repetido. El formulario aparece dentro del chat y propone la raíz del proyecto abierto (`.`). Si lo prefieres, escribe una carpeta relativa concreta. Marca la autorización para permitir una sola lectura de esa carpeta en esa conversación y pulsa **Scan duplicates**. El análisis es local: no modifica ni ejecuta código, y no envía el contenido fuente a un modelo.

El análisis recorre como máximo 300 archivos, 10 MiB y 150.000 líneas en total; cada archivo está limitado a 256 KiB y 20.000 líneas. El informe incluye hasta 200 pares de coincidencias. Cuando se alcanza un límite, reduce la carpeta y vuelve a analizar para acotar el resultado. Busca bloques exactos en Python, JavaScript/JSX, TypeScript/TSX, Java, Go, Rust, C#, C/C++, PHP, Ruby, Swift y Kotlin; además, compara la estructura de funciones Python. Se omiten carpetas ocultas, generadas o sensibles y enlaces simbólicos.

Cada análisis guarda un recibo en la conversación, un manifiesto con la huella SHA-256 de los archivos revisados y una traza local. La autorización es de un solo uso y queda ligada a la carpeta, conversación y revisión autorizadas. Estos datos permiten identificar el alcance y resultado del análisis; no contienen el código fuente.
