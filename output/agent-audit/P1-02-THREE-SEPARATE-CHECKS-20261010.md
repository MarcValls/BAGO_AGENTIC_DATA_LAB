# Tres comprobaciones separadas — P1-02 — 2026-10-10

Worktree: `BAGO_AGENTIC_DATA_LAB_chat_control`, HEAD `057b2d8bdaed8b459e3777d81761b2650256c42f`.

## 1. Rechazo del mensaje de seguimiento por historial largo

El seguimiento anterior fue rechazado con `422 invalid_history`. La ruta limita cada entrada del historial a 4000 caracteres (`src/api/server.py:914-919`). Reproduje el mismo guard con una entrada sintética de 4001 caracteres: recibió HTTP 422 y `detail.code=invalid_history`. El handler rechaza esa entrada antes de entrar en la rama del proveedor; esta reproducción no invocó Ollama.

Recibo reproducible: `output/agent-audit/P1-02-history-limit-reproduction-20261010.txt`.

La reproducción confirma el motivo y la clase de respuesta; no reutiliza ni recupera el payload exacto del seguimiento original.

## 2. Conversación limpia con el mismo agente y extracto corto

Cambié a App assistant y volví a seleccionar el Frontend Auditor persistido (`agent_b5665184bed24811ad59e90c8c4fdc9f`). La vista quedó vacía antes del envío. Con lectura de workspace autorizada solo para ese mensaje, el agente leyó el extracto corto `output/agent-audit/P1-02-server-websocket-source-excerpt-v2.txt:1-25` y devolvió la respuesta con hash, endpoint, líneas fuente 1065-1084, `execution_unavailable`, no creación de job y cierre 1008.

La nueva LocalTrace es `trace-594b271c44be48fa`; registra respuesta recibida, `ollama-cloud`, modelo `kimi-k2.6`, mismo agent id y una lectura del archivo. Ver `.bago/traces/agent-chat/trace-594b271c44be48fa.json` y captura `.playwright-cli/page-2026-10-10T20-42-23-312Z.png`.

## 3. Comprobación directa del backend sin perder trazas

Conecté un cliente WebSocket real a `ws://127.0.0.1:8081/ws/agents/run`, con Origin local permitido. El handshake fue aceptado; el servidor envió `type=error`, `code=execution_unavailable` y el texto `No job was started or recorded.`. Después cerró con `PolicyViolation` (1008). No envié payload de ejecución.

Recibo: `output/agent-audit/P1-02-backend-websocket-live-20261010.txt`. El SHA-256 actual de `src/api/server.py` coincide con el del extracto leído: `a014d08c303f3343e3f008c0adf77dd5f45d27acab505577b99530e4b8bbb2c2`.

Las trazas anteriores siguen presentes: `trace-1b479e9145e54d54` (lectura conjunta anterior) y `trace-4fb5341c9bfb4f16` (lectura anterior del extracto v2). La nueva conversación añadió `trace-594b271c44be48fa`; no reemplazó ninguna.

## Estado

Las tres comprobaciones quedan separadas y ejecutadas. La respuesta directa del backend y la nueva lectura del agente concuerdan con el comportamiento fail-closed del HEAD inspeccionado. No ejecuté la suite de tests del repositorio.
