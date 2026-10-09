# W02 — Auditoría real de código para P1-02

## Ejecución observada

- App ADL: `http://127.0.0.1:8084` en el worktree `codex/conversation-library-v1`, HEAD `69b4f4b1ead2552b527e6e48868ab36cc2b38cbc`.
- Agente persistido: `ADL Read Evidence Agent` (`agent_d3e63db8b4704080b924a05fb1ab71fc`).
- Respuesta de ambas llamadas: HTTP 200, `source=ollama`; LocalTrace identifica `ollama-cloud` y `gemma4:31b`; estado del provider después de inferencia: `ready`.
- Conversación persistida: `conv_438e701c29684bfab97adbd3abac098b`, cuatro mensajes en revisión 4.
- Lectura comprobada en los recibos: brief P1-02 líneas 1-20; `AgentRunner.tsx` líneas 1-250; extracto backend líneas 1-28, que copia `src/api/server.py` líneas 1227-1247.

## Límite de lectura del backend

El lector del chat limita un archivo completo a 32 KiB. `src/api/server.py` mide 55,939 bytes; la primera llamada real lo rechazó. Para completar la auditoría, se preparó un extracto literal del endpoint, ligado al HEAD y al SHA-256 del archivo fuente registrado en `W01_TARGET_SNAPSHOT.json`. El agente leyó el extracto mediante la misma herramienta acotada. Por tanto, se afirma inspección de ese extracto de código con procedencia, no lectura directa del archivo grande por el agente.

## Dictamen del agente

- El backend confirma el cierre seguro: envía `execution_unavailable`, dice que no se inició ni registró trabajo y cierra con código 1008.
- En el snapshot activo, el Runner no presenta una capacidad disponible: declara `AGENT_EXECUTION_AVAILABLE = false`, muestra `Run unavailable`, deshabilita el botón y explica que no se inició ningún trabajo.
- El estado exitoso depende de `exit_code === 0`; los códigos de error del servidor se agregan a los logs.
- **Conclusión provisional:** la afirmación original de desajuste UI/backend queda corregida en los archivos de frontend actualmente modificados; el endpoint backend sigue sin ejecutar agentes, por diseño. La comprobación dinámica W03 y la revisión independiente W05 aún deben confirmar este dictamen.

## Artefactos

- `W02_AGENT_AUDIT.json`: primera respuesta real, que cubre el brief y el frontend y registra el rechazo del archivo backend completo.
- `W02_AGENT_AUDIT_COMPLETION.json`: segunda respuesta real, con lectura del extracto backend y dictamen integrado.
- `P1_02_BACKEND_EXCERPT.txt`: excerpt con cabecera de procedencia, rango original y SHA-256 del fuente.
- LocalTrace de la primera respuesta: `.bago/traces/agent-chat/trace-263199de3de94db9.json`.
- LocalTrace de la segunda respuesta: `.bago/traces/agent-chat/trace-5928204206a14073.json`.

**Aún no se afirma validación dinámica del WebSocket, lectura directa del archivo backend completo ni ejecución de un agente/job.**
