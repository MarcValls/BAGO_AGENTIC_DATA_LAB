# Local launcher port reuse follow-up

## Behavior implemented

- The launcher owns a per-checkout record under `%LOCALAPPDATA%\BAGO\AgentChat\instances` with checkout path, launcher PID/start time, actual listener PID/start time, port, and URL.
- On relaunch it stops the listener only when its recorded PID/start time and BAGO server command line still match, then stops the associated venv launcher process when its PID/start time/path match.
- It prefers port 8080 and selects the first available port up through 9000 when another process owns the preferred port. It never stops a process absent a valid matching launcher record.
- `BAGO_API_PORT` controls the server port. The selected loopback origins are included in HTTP CORS and WebSocket origin validation.

## Verification on this worktree

- PowerShell parser: PASS.
- `npm run build`: PASS; 126 Vite modules.
- Running `scripts/run-local-ui.ps1` with 8080 occupied by unrelated Docker/WSL listeners selected 8081 and returned a healthy host-mode API.
- Re-running the launcher terminated the recorded listener PID 39252 and started a new listener PID 41392 on the same 8081 port.
- `GET /api/health`: `{"status":"ok"}`.
- CORS preflight from `http://127.0.0.1:8081`: allowed origin matched the selected port.
- Provider status: `not_configured`, runtime `host`; no secret or model request was used.
- The unrelated listener on 8080 was not stopped. An unrelated Python listener on 8082 was also left untouched.

The instance now running for manual UI use is at `http://127.0.0.1:8081`. The managed restart and occupied-port fallback were observed during this verification.
