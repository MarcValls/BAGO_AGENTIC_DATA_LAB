# Frontend Auditor P1-02: comparación UI y Jaeger

**Estado:** `VERIFIED` para esta interacción concreta y su proyección local a Jaeger. `VALIDATED` no aplica: la conversación demuestra una respuesta del agente y su observabilidad, no confirma por sí sola que el hallazgo P1-02 sea correcto ni que el producto esté listo para producción.

## Identidad de la ejecución

| Campo | Evidencia observada |
|---|---|
| Fecha y hora | 9 de octubre de 2026, aproximadamente 18:46:07–18:48:00 Europe/Madrid |
| Checkout | `C:\Users\AMTEC_Terminal_1º\AppData\Local\Temp\BAGO_AGENTIC_DATA_LAB_chat_control` |
| Rama / HEAD | `codex/agent-chat-control-v1` / `69b4f4b1ead2552b527e6e48868ab36cc2b38cbc` al preparar la demostración |
| Agente | `Frontend Auditor` (`agent_b5665184bed24811ad59e90c8c4fdc9f`) |
| Proveedor y modelo solicitados | `ollama-cloud` / `kimi-k2.6` (modelo fijado en el perfil del agente) |
| Trace ID local (LocalTrace) | `trace-1c3470a70b0a4313` |
| Trace ID de Jaeger | `687d4cfb825c134d1d24d80c6a4bbf82` |
| Operación Jaeger | `agent.chat` — servicio `bago-agentic-data-lab` — 1 span |
| Duración | 112,916 ms en LocalTrace; 112,916,752 μs / 1m 53s en Jaeger |

## Comparación de evidencia

| Afirmación | Interfaz visible | LocalTrace | Jaeger | Resultado |
|---|---|---|---|---|
| El agente recibió el hallazgo P1-02 y respondió | La captura muestra la petición y la respuesta completa en la conversación de `Frontend Auditor`. | Evento `agent.chat`, estado `COMPLETED`, resultado `response_received`. El contenido del mensaje no se registra. | Span `agent.chat`, estado OTel `OK`. | Coinciden como una llamada completada; la UI conserva el contenido y los rastros guardan solo metadatos. |
| Se utilizó el perfil `kimi-k2.6` | La cabecera de conversación y el agente seleccionado muestran `kimi-k2.6`. | `attributes.model_id = kimi-k2.6`. | Tag `bago.event.model_id = kimi-k2.6`. | Coincide en los tres niveles. |
| UI, rastro local y Jaeger representan la misma petición | La UI muestra ambos IDs debajo de la respuesta. | `trace_id = trace-1c3470a70b0a4313`. | El tag `bago.trace_id` contiene ese mismo ID local; el ID nativo de Jaeger es `687d4cfb825c134d1d24d80c6a4bbf82`. | Correlación directa mediante el ID local transportado como atributo; los IDs nativos se mantienen diferenciados. |
| El span mide la llamada al modelo | La respuesta de la UI llega tras el indicador `Waiting for Ollama`. | Tiempos de inicio y fin capturados alrededor de la llamada; `duration_ms = 112916`. | Inicio `October 9 2026, 18:46:07.193`; duración `1m 53s`. | La duración Jaeger coincide con el intervalo del evento local, con la precisión correspondiente a cada formato. |
| Datos sensibles excluidos de la proyección | El prompt y la respuesta son visibles en la UI y su captura. | El JSON solo contiene agente, proveedor, modelo, estado, tiempos e IDs; no contiene prompt, historial, respuesta ni credencial. | Tags sin contenido del prompt, historial, respuesta o credencial. | La separación está comprobada para este evento. |

## Respuesta del agente observada

El agente calificó el hallazgo como **Alta**, citó el texto suministrado, recomendó deshabilitar o explicar la ejecución mientras el backend indique `execution_unavailable` y no marcar éxito sin un `exit_code` de éxito explícito. También indicó que no verificó la ubicación contractual de `exit_code`, la fuente previa de `execution_unavailable` ni el tratamiento UI acordado para fallos.

Esta respuesta es el análisis del agente a partir de la información escrita en el prompt. **No es una validación independiente del código ni del informe de auditoría.** El agente tiene `tools=[]` y el chat no le concede inspección del repositorio ni ejecución.

## Proveniencia del modelo y precisión de la afirmación

El registro persistido del perfil fija `provider_id=ollama-cloud` y `model_id=kimi-k2.6`. El endpoint selecciona ese `model_id` del perfil y lo entrega al adaptador Ollama. El span exportado registra el mismo valor solicitado. La configuración global del asistente de aplicación sigue siendo `gemma4:31b-cloud`; corresponde a otra ruta y no se usó para esta conversación con el agente.

La respuesta del proveedor no expone metadatos independientes de modelo en el adaptador actual. Por eso, la evidencia confirma **el modelo solicitado/enviado por la aplicación (`kimi-k2.6`)**, no una atestación independiente del modelo interno al que Ollama Cloud enrutó la petición.

## Artefactos y comprobaciones

- Captura de la conversación UI: [`output/playwright/agent-chat-ui-jaeger-20261009.png`](../../../output/playwright/agent-chat-ui-jaeger-20261009.png).
- Captura de la traza Jaeger: [`output/playwright/agent-chat-jaeger-trace-20261009.png`](../../../output/playwright/agent-chat-jaeger-trace-20261009.png).
- SHA-256 UI: `0D871F2B8D2080E7700FCD1B3A617BDDD3D6D8089E8623FD98EFFB2C3B364C68`; Jaeger: `FFB9DCE49803021F068906E8D8504F85A90F74F5B23E1613E3DC2E920051AE91`.
- Evento local: [trace-1c3470a70b0a4313.json](../../traces/agent-chat/trace-1c3470a70b0a4313.json).
- Jaeger UI: `http://127.0.0.1:16686/trace/687d4cfb825c134d1d24d80c6a4bbf82`.
- Consulta de API observada: `GET /api/traces/687d4cfb825c134d1d24d80c6a4bbf82` devolvió un span `agent.chat`, servicio `bago-agentic-data-lab`, con `bago.trace_id=trace-1c3470a70b0a4313`, `bago.event.agent_id=agent_b5665184bed24811ad59e90c8c4fdc9f` y `bago.event.model_id=kimi-k2.6`.
- Captura realizada con Playwright en navegador visible. Build del frontend completada. Pruebas enfocadas: `python -m pytest tests/test_agent_chat_trace.py tests/test_l15_otel_bridge.py -q` → `5 passed`.
- Las huellas SHA-256 de los contratos modificados coinciden con los hashes propuestos en CR-011 y CR-012.

## Límites

- Jaeger es una proyección de observabilidad; `LocalTrace` conserva la evidencia local de origen.
- La traza cubre una petición completada. Las rutas de error del proveedor no se incluyeron en esta demostración.
- La duración refleja la petición síncrona completa a Ollama Cloud desde el backend, no solo tiempo de inferencia medido internamente por el proveedor.
- Esta ejecución no modificó archivos del producto mediante el agente ni ejecutó el trabajo descrito en P1-02.

