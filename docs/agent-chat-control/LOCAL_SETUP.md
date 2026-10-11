# Run the Ollama chat UI on Windows

The provider settings require the API to run on the Windows host so Python can use Windows Credential Manager for an API key and can reach the user's local Ollama service for CLI-session mode.

1. Install Node.js and Python 3.11.
2. In PowerShell, enter the repository root. Run `npm ci` from `frontend` if its `node_modules` directory is missing.
3. Activate the Python environment that contains the project dependencies. If FastAPI, Uvicorn, or keyring are missing, run `python -m pip install -r requirements.txt fastapi uvicorn` in that environment.
4. Run `scripts/run-local-ui.ps1`.
5. Open **Provider settings**, choose API key or local CLI session, then select a model. The app never reads Ollama CLI credentials; sign in through Ollama itself before selecting that mode.

The launcher builds the UI and binds the API to `127.0.0.1`. It prefers port 8080 and scans upward through 9000 when another process owns that port. A per-checkout launcher record stores the exact process ID, process start time, and port. On the next launch it stops only that recorded process when the identity still matches, then starts one replacement; it never stops an unrelated process. The chosen port is passed to the API and added to the local HTTP/WebSocket origin allowlist. The launcher waits for a healthy API before opening the UI. Server logs are written under `%LOCALAPPDATA%\BAGO\AgentChat\logs`; launcher identity records are under `%LOCALAPPDATA%\BAGO\AgentChat\instances`. It does not configure credentials or make a model request.

The Docker UI remains available for other portfolio views and persists agent/provider/job data through host mounts. Its provider controls are intentionally disabled because the container cannot safely use Windows Credential Manager or the host's loopback Ollama service.
