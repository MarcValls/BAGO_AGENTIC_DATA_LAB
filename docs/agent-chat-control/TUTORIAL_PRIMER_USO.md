# Videotutorial de primer uso

El [vídeo narrado en español](assets/ADL_videotutorial_primer_usuario.mp4) dura 95,76 segundos. Incluye subtítulos incrustados y un archivo [SRT independiente](assets/ADL_videotutorial_primer_usuario.es.srt).

## Recorrido

1. Bienvenida del chat y consulta del inventario de agentes.
2. Pantalla completa de ajustes del proveedor Ollama Cloud. El estado muestra API key y `gemma4:31b`; el recuadro de credenciales queda cubierto por una máscara. No se muestra el valor de la clave.
3. El agente persistido **Frontend Auditor**, fijado a `kimi-k2.6`, lee el archivo benigno [`sample-note.txt`](../../output/tutorial/sample-note.txt). La respuesta y el recibo aparecen en el chat.
4. El asistente propone un borrador de agente usando el modelo global; la persona cancela la propuesta. No se crea un segundo agente.
5. Navegación a Agent Builder.

## Evidencia y alcance

La [LocalTrace](assets/trace-c7ec5fcc40284a42.json) registra `agent.chat`, `provider_id=ollama-cloud`, `model_id=kimi-k2.6`, `outcome=response_received`, una lectura de `output/tutorial/sample-note.txt:1-8` y estado `COMPLETED`. Es evidencia local de esa lectura y respuesta. El asistente global aparece configurado con `gemma4:31b`; no debe confundirse con el modelo fijado al agente lector.

La grabación demuestra una lectura acotada del archivo de ejemplo y una respuesta real del proveedor. No demuestra que Frontend Auditor auditara el código fuente del proyecto, que modificara archivos o que ejecutara un job. La propuesta cancelada tampoco crea un nuevo agente.

La captura se hizo sobre la UI local de `127.0.0.1:8081`. El vídeo se produjo el 2026-10-10 y refleja ese estado de la aplicación.
