# Auditoría real de P1-02 — evidencia ADL, navegador y Jaeger

**Resultado para el snapshot activo:** `P1-02 CORREGIDO EN LA INTERFAZ; BACKEND FAIL-CLOSED VERIFICADO`. El dictamen se limita al worktree, proceso y hashes descritos aquí. El informe original sigue describiendo su snapshot anterior.

## Identidad del candidato

- Worktree: `BAGO_AGENTIC_DATA_LAB_conversation_library`
- Rama / HEAD: `codex/conversation-library-v1` / `69b4f4b1ead2552b527e6e48868ab36cc2b38cbc`
- Runtime: `http://127.0.0.1:8084`; Uvicorn PID 46248 y listener PID 43528.
- La fuente estaba modificada localmente durante la auditoría. El SHA-256 de `AgentRunner.tsx` era `D6BCFF256F3ED47C8B8EDA0DE657B0E2727D660EC452C389FFCCC147565A7DAB`; el de `server.py`, `958A6C7A2A1BAF0A04B8AD3BC76F36B0F80BB52AD8AA5E4718E01C480EC30A7E`.
- El hallazgo original procede de `.bago/CRIT-BAGO-ADL-FRONTEND-20261009-01.md`, líneas 31-36, SHA-256 `EB331E30BC5F9E720CF2C714E8E02766F8488980C72413FF8B3F9F8AB1BA48BF`. Ese reporte indicaba auditoría estática de un snapshot anterior, con validación de producto `NOT_RUN`.

## Lo que hizo el agente ADL

El agente `ADL Read Evidence Agent` (`agent_d3e63db8b4704080b924a05fb1ab71fc`) contestó dos solicitudes por la API real de ADL. Ambas respuestas devolvieron HTTP 200, `source=ollama`, y sus LocalTrace registran `provider_id=ollama-cloud`, `model_id=gemma4:31b` y `outcome=response_received`. El catálogo cloud listaba `gemma4:31b`; el identificador distinto `gemma4:31b-cloud` no se probó ni se afirma equivalente.

En la primera respuesta el agente leyó, mediante `read_workspace_file`, el brief del hallazgo (líneas 1-20) y `frontend/src/components/AgentRunner.tsx` (líneas 1-250). Identificó `AGENT_EXECUTION_AVAILABLE = false`, botón `Run unavailable` deshabilitado, aviso explícito y éxito condicionado a `exit_code === 0`.

El lector no pudo abrir `src/api/server.py` directamente porque el archivo completo mide 55,939 bytes y el límite es 32 KiB. Para no ocultar esa limitación, se creó `P1_02_BACKEND_EXCERPT.txt`: copia literal de las líneas 1227-1247, con HEAD y SHA-256 de la fuente. En la segunda solicitud el agente leyó ese extracto (líneas 1-28) y concluyó que el backend envía `execution_unavailable`, indica que no inicia ni registra trabajos y cierra con 1008. El recibo de lectura prueba que leyó el extracto vinculado; **no** que la herramienta abriera directamente el archivo grande.

La conversación `conv_438e701c29684bfab97adbd3abac098b` terminó con cuatro mensajes. La lectura SQLite fue de solo lectura: cuatro filas, contenido y referencias idénticos a la API, incluidas las citas de fuente y ambos trace IDs. Véase `W04_SQLITE_API_READBACK.json`.

## Comparación visual con Jaeger

| Momento | Evidencia ADL / navegador | LocalTrace persistido | Jaeger |
|---|---|---|---|
| Auditoría inicial | El recibo W02 registra respuesta Ollama y lectura del brief + `AgentRunner.tsx`. | `trace-263199de3de94db9`, SHA-256 `CE301EDF5D3D25736AA12227D193DF138D6C9BC52B1D4D6F2F61F8D73CEB9710`; 2 fuentes. | `f326600e04b693653e56a20b83eb062a`, un span `agent.chat` con `OK`, `gemma4:31b`, `ollama-cloud` y ambas fuentes. |
| Auditoría completada | La respuesta W02 cita el extracto backend y distingue lo corregido de lo que permanece. | `trace-5928204206a14073`, SHA-256 `03DD91B6E8491918845C5CC91EF397C5FB869002E57226CF039084346A7C367F`; lectura del extracto líneas 1-28. | `db0817ebe3087ca9807ba0c78f94c522`, un span `agent.chat` con `OK`, el mismo modelo/provider y la fuente del extracto. |
| Runner visible | [Captura del Runner](../../../output/playwright/p1-02-agent-runner-live-20261009.png): aviso `Execution unavailable`; dos botones `Run unavailable` deshabilitados. DOM: `W03_AGENT_RUNNER_DOM.yml`. | No es un evento del agente; prueba aparte del estado visible de la UI. | La captura Jaeger no representa la UI; Jaeger corrobora metadatos de los turnos del agente. |

Captura de detalles del segundo span: [Jaeger con provider, modelo, estado y fuente](p1-02-jaeger-span-details-20261009.png). SHA-256 `2CF2EA410F24EC3C4861C30004E587C273D076381BDC9D04420C97BFE2CA5FC6`.

Los dos LocalTrace se exportaron **después** de las respuestas al OTLP local (`127.0.0.1:4318`). Jaeger devolvió HTTP 200 para ambos IDs y un span por trace. LocalTrace sigue siendo la fuente local original; la app respondió `trace_state=local_only` y no añadió un enlace Jaeger automáticamente. Los detalles de exportación y lectura están en `W04_JAEGER_PROJECTION.json`.

## Comprobación dinámica del endpoint

La prueba se conectó a `/ws/agents/run` sin enviar mensaje de ejecución ni configuración de agente. Con el origen permitido `http://127.0.0.1:8080`, el handshake fue HTTP 101, el servidor contestó `execution_unavailable` y cerró con 1008. `/api/jobs/list` devolvió cero trabajos antes y después.

El origen de la página activa (`http://127.0.0.1:8084`) recibió HTTP 403 en el handshake porque no está en la lista de orígenes permitidos del proceso. Es una incidencia de configuración de origen separada; no se debe presentar la conexión con origen 8080 como una conexión same-origin de la página 8084. El Runner deshabilitado no intentó abrir el WebSocket durante la prueba visual.

## Veredicto y límites

- **P1-02 en el candidato actual:** verificado como corregido en la capa UI que generaba la falsa promesa: el estado se explica y `Run` no se puede activar. La lógica también acepta éxito solo con código de salida 0 y agrega el código de error a los logs.
- **Backend:** mantiene el cierre intencional sin ejecutar agentes; el frame y el código 1008 se confirmaron dinámicamente desde un origen permitido.
- **Lectura real por el modelo:** demostrada sobre el finding y el código frontend, y sobre un extracto literal del handler backend ligado por hash. No se afirma lectura directa del `server.py` completo.
- **No realizado:** ejecución de agente/job, modificación de código, auditoría de todos los endpoints, validación de la consola para un handshake same-origin aceptado, reporte de coste del proveedor.
- **Límite de atribución:** el dictamen aplica al snapshot sucio con hashes listados; no reemplaza ni invalida el informe original para el snapshot que examinó.

## Recibos de la espiral

- W01: `W01_TARGET_SNAPSHOT.json`
- W02: `W02_SOURCE_AUDIT_RESULT.md`, `W02_AGENT_AUDIT.json`, `W02_AGENT_AUDIT_COMPLETION.json`
- W03: `W03_BROWSER_EVIDENCE.json`, `W03_RUNTIME_PROBE.json`, `W03_AGENT_RUNNER_DOM.yml`
- W04: `W04_SQLITE_API_READBACK.json`, `W04_JAEGER_PROJECTION.json`
