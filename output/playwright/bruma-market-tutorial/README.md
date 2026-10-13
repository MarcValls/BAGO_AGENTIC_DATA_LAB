# Tutorial demo — Bruma Market

Video tutorial en español: [`tutorial-bruma-market.mp4`](tutorial-bruma-market.mp4) (voz local y subtítulos incluidos). Subtítulos independientes: [`tutorial-bruma-market.srt`](tutorial-bruma-market.srt).

> Bruma Market y todos los pedidos, fechas, importes y políticas de este material son ficticios. El vídeo documenta dos conversaciones reales de agentes ejecutadas con el proveedor Ollama Cloud configurado en la aplicación. No se procesaron datos de clientes reales.

## Flujo del tutorial

1. Abre BAGO Agentic Data Lab y comprueba en **Settings → Ollama Provider** que el proveedor aparece `ready`. El modelo de estos perfiles hereda el modelo configurado: `gemma4:31b`.
2. En **Agent Builder → Create Custom Agent**, crea **Bruma Market · Extractor de pedidos**. Déjalo como `RAG`; define un prompt que solicite campos tipados, fechas UTC, cálculo de horas cuando ambas fechas estén presentes y `null` cuando falten. No selecciones herramientas de acción.
3. Guarda y crea **Bruma Market · Revisor de política**. Su prompt debe codificar la regla exacta, los estados posibles, el formato JSON y la prohibición de ejecutar acciones.
4. Ve a **Chat**, selecciona el extractor, marca **Authorize exact project files for this message** y autoriza solo `output/playwright/bruma-market-tutorial/inputs/orders.csv`. Pide la extracción JSON.
5. Selecciona el revisor. Autoriza en ese turno `orders.csv`, `policy.md` y `qa-expected.md`. Pide decisiones por pedido con citas y sin reembolsar.
6. Comprueba la respuesta, los archivos leídos y las trazas. En esta ejecución las decisiones coinciden con el fixture QA; las trazas reportan `local_only`, no exportación Jaeger.

## Perfiles que se crearon

Los perfiles completos, incluidos los prompts de sistema y sus identificadores, están en [`cloud-runs/profiles.json`](cloud-runs/profiles.json). La creación del perfil lo guarda en la aplicación; la llamada al modelo ocurre al conversar con él.

La selección `RAG` del Builder es un tipo de perfil. En este demo, el dato de entrada llega por la lectura puntual de archivos autorizados en Chat; no se preparó ni se validó un índice vectorial de Bruma Market. Los perfiles tampoco reciben permisos para ejecutar reembolsos.

## Datos y resultados

- Archivos ficticios de entrada: [`inputs/orders.csv`](inputs/orders.csv), [`inputs/policy.md`](inputs/policy.md) y [`inputs/qa-expected.md`](inputs/qa-expected.md).
- Respuesta de extracción preservada del chat: [`cloud-runs/run-1.json`](cloud-runs/run-1.json); JSON extraído: [`extracted/orders.json`](extracted/orders.json).
- Respuesta de revisión preservada del chat: [`cloud-runs/run-2.json`](cloud-runs/run-2.json); decisiones en [`extracted/policy-decisions.json`](extracted/policy-decisions.json).
- Recibos `ALLOW`, rutas, líneas y SHA-256: [`extracted/run-evidence.json`](extracted/run-evidence.json).

| Pedido | Resultado demo | Importe de envío elegible |
|---|---|---:|
| BM-1001 | Elegible: 32 h tarde, EXPRESS | 7,90 € |
| BM-1002 | No elegible: exactamente 24 h | — |
| BM-1003 | No elegible: método STANDARD | — |
| BM-1004 | Pendiente: sin fecha de entrega | — |

El modelo omitió `evidence_paths` en su JSON de extracción. El recibo del runtime sí identifica el CSV autorizado, las líneas leídas y su huella; el video explica esta diferencia entre citas generadas y evidencia del sistema.

## Evidencia y alcance

- Dos perfiles nuevos permanecen disponibles en la aplicación con proveedor `ollama-cloud` y modelo `gemma4:31b`.
- Dos turnos de chat de agente terminaron con `source: ollama` y respuestas persistidas; identificadores de traza: `trace-e884fa5f23414206` y `trace-63cc286f9d574a38`.
- El extractor leyó el CSV. El revisor leyó la política, el CSV y el QA. Todos los eventos de lectura registrados fueron `ALLOW` y están enlazados a hashes de contenido.
- Resultado validado contra los cuatro casos de QA sintéticos. `actions_executed` está vacío; no se emitió ningún reembolso.
- El empaquetado del video usa voz española local de Windows; no generó otra llamada de voz en cloud.

Los identificadores y hashes son evidencia de esta ejecución en la copia local del proyecto. No implican certificación independiente, exportación remota de trazas, exactitud para una política real ni preparación para producción.
