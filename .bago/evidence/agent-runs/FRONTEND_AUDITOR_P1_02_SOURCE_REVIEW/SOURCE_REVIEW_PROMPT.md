# Solicitud enviada al Frontend Auditor

## Identidad del material fuente

- Checkout de origen: `C:\Users\AMTEC_Terminal_1º\AppData\Local\Temp\BAGO_AGENTIC_DATA_LAB_chat_control`
- HEAD base: `69b4f4b1ead2552b527e6e48868ab36cc2b38cbc`
- El bloque **antes** reproduce el archivo en ese HEAD; blob Git de `AgentRunner.tsx`: `5b20c3544aed12634fb4b7572878886c0714ef67`.
- El bloque **después** reproduce el archivo del worktree tras la reparación de W01; SHA-256 actual de `frontend/src/components/AgentRunner.tsx`: `DEFB5670BA4FE415DE6E65ED7C621F4F7C7806DF988E91FC73DDD85F11A22315`.
- El bloque del servidor reproduce `src/api/server.py` en el HEAD indicado; blob Git: `10f4ad48d5d3c06f9805e978ba2a8932e671a143`.
- Informe de origen: `C:\Users\AMTEC_Terminal_1º\BAGO_AGENTIC_DATA_LAB\.bago\CRIT-BAGO-ADL-FRONTEND-20261009-01.md`, sección P1-02.

## Texto enviado

Revisa el hallazgo P1-02 contrastando los fragmentos de código fuente de abajo. Estos fragmentos se han extraído de los archivos identificados arriba y se incluyen íntegros en el mensaje que recibes. Analiza su contenido directamente. **No digas que abriste el checkout, leíste archivos por tu cuenta ni ejecutaste pruebas:** este chat no te concede esas herramientas. Distingue el defecto original de la corrección actual. Cita archivo y líneas del fragmento, determina si el hallazgo se confirma en el HEAD, si el cambio actual lo corrige y qué evidencia adicional haría falta para validar la UI en ejecución. No propongas cambiar nada más.

Hallazgo P1-02: Agent Runner ofrecía Run mientras `POST /ws/agents/run` responde `execution_unavailable`; además, ante cualquier mensaje `done`, mostraba una notificación de éxito aunque `exit_code` fuera distinto de cero.

### Antes: `frontend/src/components/AgentRunner.tsx` (HEAD, líneas 62–91)

```tsx
      ws.onopen = () => {
        ws.send(JSON.stringify({
          agent_id: agent.id,
          config: agent.config,
        }))
        setLogs(['[INFO] Connecting to agent execution service...'])
      }

      ws.onmessage = (event) => {
        const msg = JSON.parse(event.data)

        if (msg.type === 'stdout') {
          setLogs((prev) => [...prev, msg.data])
        } else if (msg.type === 'done') {
          const result: ExecutionResult = {
            job_id: msg.job_id,
            status: msg.exit_code === 0 ? 'success' : 'failed',
            duration_ms: msg.duration_ms || 0,
            cost_usd: msg.cost_usd || 0,
          }
          setResult(result)
          setIsRunning(false)
          ws.close()
          showNotification('success', `Agent ${agent.config.name} executed successfully`)
        } else if (msg.type === 'error') {
          setLogs((prev) => [...prev, `[ERROR] ${msg.data}`])
          setIsRunning(false)
          ws.close()
          showNotification('error', `Agent execution failed: ${msg.data}`)
        }
      }
```

### Servidor: `src/api/server.py` (HEAD, líneas 968–985)

```python
@app.websocket("/ws/agents/run")
async def websocket_agent_run(websocket: WebSocket) -> None:
    """Fail closed until an agent has a real governed execution path."""
    if not await _accept_local_websocket(websocket):
        return
    try:
        await websocket.send_json({
            "type": "error",
            "code": "execution_unavailable",
            "data": "Agent execution is unavailable: no governed execution capability is registered. No job was started or recorded.",
        })
    except (RuntimeError, WebSocketDisconnect):
        pass
    finally:
        try:
            await websocket.close(code=1008)
        except RuntimeError:
            pass
```

### Después: `frontend/src/components/AgentRunner.tsx` (worktree, líneas 24–25, 57–61, 84–107, 186–219)

```tsx
// /ws/agents/run intentionally fails closed until a governed executor exists.
const AGENT_EXECUTION_AVAILABLE = false

  const executeAgent = async (agent: Agent) => {
    if (!AGENT_EXECUTION_AVAILABLE) {
      showNotification('error', 'Agent execution is unavailable: no governed execution capability is registered.')
      return
    }
    // transport and response handlers follow
  }

        } else if (msg.type === 'done') {
          const exitCode = Number.isInteger(msg.exit_code) ? msg.exit_code as number : null
          const result: ExecutionResult = {
            job_id: msg.job_id,
            status: exitCode === 0 ? 'success' : 'failed',
            duration_ms: msg.duration_ms || 0,
            cost_usd: msg.cost_usd || 0,
            exit_code: exitCode,
          }
          setResult(result)
          setIsRunning(false)
          ws.close()
          if (exitCode === 0) {
            showNotification('success', `Agent ${agent.config.name} executed successfully`)
          } else {
            showNotification('error', `Agent execution failed: terminal exit code ${exitCode ?? 'missing'}`)
          }
        } else if (msg.type === 'error') {
          const errorCode = typeof msg.code === 'string' ? msg.code : 'unknown_error'
          const errorData = typeof msg.data === 'string' ? msg.data : JSON.stringify(msg.data ?? 'No error details provided')
          setLogs((prev) => [...prev, `[ERROR] ${errorCode}: ${errorData}`])
        }
```

La vista actual añade un estado visible de indisponibilidad y presenta el botón deshabilitado con la etiqueta `Run unavailable`.
