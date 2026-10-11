# Frontend Auditor — live source audit

**VERDICTO DE AUDITORÍA: P1-02**

**ESTADO:** SOLUCIONADO (Fixed)

**FACTS:**
1.  **Frontend:** En `frontend/src/components/AgentRunner.tsx`, se ha implementado una bandera de control `AGENT_EXECUTION_AVAILABLE = false` (línea 25). 
2.  **Frontend:** El botón de ejecución ahora tiene el atributo `disabled={!AGENT_EXECUTION_AVAILABLE || isRunning}` (línea 214), el texto `"Run unavailable"` (línea 218) y un mensaje informativo explícito en la UI: `"Agent execution is unavailable. No governed execution capability is registered; Run is disabled."` (líneas 186-188).
3.  **Frontend:** La función `executeAgent` intercepta el flujo antes de intentar la conexión WebSocket: `if (!AGENT_EXECUTION_AVAILABLE) { showNotification('error', ...); return }` (líneas 58-61).
4.  **Servidor:** El endpoint `/ws/agents/run` en `src/api/server.py` mantiene el comportamiento de rechazo, enviando el código de error `"execution_unavailable"` (línea 1538) y cerrando la conexión con código `1008` (línea 1545).

**CONCLUSION:**
El hallazgo histórico P1-02 (donde la UI ofrecía la opción "Run" a pesar de que el servidor la rechazaba) ya no es cierto. El candidato actual ha sincronizado el estado de la interfaz con la capacidad del servidor, deshabilitando el botón de ejecución y notificando al usuario el estado de indisponibilidad antes de que se realice cualquier intento de llamada al servidor.

**NOT_RUN:**
No se han ejecutado tests ni comandos de entorno.
