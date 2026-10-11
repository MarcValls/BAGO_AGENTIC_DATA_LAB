# Videotutorial de inicio de BAGO Agentic Data Lab

**Archivo:** `ADL_videotutorial_primer_usuario.mp4` (95,76 s, H.264/AAC, 1600×900). Incluye narración en español y subtítulos incrustados. El archivo `.es.srt` permite activar o editar los subtítulos por separado.

## Recorrido

1. Bienvenida al chat y consulta del inventario de agentes.
2. Ajustes del proveedor, método API key, selección de modelo y estado de conexión.
3. Lectura de un archivo de ejemplo por el agente persistido **Frontend Auditor**, con presentación del recibo de lectura.
4. Propuesta de un nuevo agente por chat, revisión del borrador y cancelación explícita.
5. Entrada al Agent Builder.

## Privacidad de credenciales

Se conserva la pantalla completa de configuración del proveedor. El área de la credencial está cubierta durante toda su aparición con la etiqueta **CREDENCIAL CENSURADA**. No se incluye ni se muestra el valor de la API key.

## Evidencia de la interacción

La lectura del archivo benigno `sample-note.txt` produjo una traza local `trace-c7ec5fcc40284a42`, evento `agent.chat`, estado `COMPLETED`, proveedor `ollama-cloud`, modelo `kimi-k2.6`, una lectura (`output/tutorial/sample-note.txt:1-8`) y resultado `response_received`. La traza acredita esa lectura y respuesta reales en el flujo local.

El asistente global de la aplicación aparece configurado con `gemma4:31b` en la pantalla de proveedor. Es distinto del modelo fijado en el agente Frontend Auditor (`kimi-k2.6`), cuyo uso registra la traza anterior.

La propuesta “Resumidor de Informes” se cancela. El recorrido no crea un agente nuevo ni cambia archivos del producto. La lista de agentes persistidos se puede contrastar en la interfaz al reproducir el vídeo.

## Reproducción

Abrir el MP4 con cualquier reproductor compatible. El SRT tiene la misma base de nombre y codificación UTF-8. La grabación refleja el estado de la interfaz local en la fecha de captura; puede variar si cambia la configuración o la aplicación.
