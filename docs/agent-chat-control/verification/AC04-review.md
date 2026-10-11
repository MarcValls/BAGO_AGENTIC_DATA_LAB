# AC04 Independent Review

Status: PASS (static/source review; P0=0, P1=0, P2=1)

## Candidate identity

- Repository HEAD: `4d6a0a95932cb4167b8f6a8caa6fdfcd79f4abff`
- Candidate fingerprint: `1e57cd050d9940c9bb2311df384f6f3397b14229b99b3443729f86127dc9376f`
- Fingerprint method: SHA-256 of `HEAD<TAB><head>
` followed by sorted `relative/path<TAB>SHA256(file bytes)
` records for 90 files under `src/**` and `frontend/src/**`, plus `requirements.txt`, `Dockerfile.ui`, `docker-compose.ui.yml`, and `docs/agent-chat-control/contracts/CONTROL_PLANE_V1.md`.
- The aggregate binds source and contract files; generated `frontend/dist` output and coordination files are excluded.

## Review findings

### P0: 0; P1: 0

The previously identified fake Runner success, missing legacy WebSocket model fallback, and unguarded WebSocket Origin findings are closed in the final candidate by AC09 and AC10. Static source inspection confirms:

- `/ws/agents/run` requires an allowed local Origin, responds `execution_unavailable`, closes the connection, and does not create/save a job or emit success/done.
- `/ws/agents/chat` requires an allowed local Origin, reloads the agent by ID, chooses its pinned model or the request-scoped selected model, and returns readiness/provider errors without writing the fallback into the agent record.
- All three WebSocket routes (`/ws/demo/run`, `/ws/agents/run`, `/ws/agents/chat`) call the shared Origin check before accepting or performing work. The guard requires an exact match against validated local UI origins. This is a browser-origin defense, not authentication against local software.
- CORS accepts explicit localhost/loopback origins only, credentials are disabled, Docker host ports bind to loopback, and standalone module startup defaults to loopback and rejects a non-loopback host outside container mode.
- In container mode, provider status is `unsupported_runtime`, backend configuration/request calls fail closed, and Docker persists agent/provider/job directories. Native host launch selects loopback Ollama and OS credential storage.
- Provider API shapes and error handling do not return API keys; credentials are stored through the OS credential backend, not browser storage or agent/chat records. The browser submits a key only to the write-only provider endpoint and clears its component state after saving.
- Agent records are loaded server-side; IDs and schemas are validated; model-generated draft content stays a proposal until the explicit Create agent action. Cancel does not create. Chat intent handling maps to bounded known operations/views, and model output is not dispatched as an arbitrary tool or URL.
- The explicit legacy demo route runs a fixed repository demo with boolean options; agent Runner execution is fail-closed. The chat itself does not invoke either route.

### P2: provider key input remains editable in container UI

`ProviderSettings.tsx` disables authentication choices, save, model selection, and model actions when `runtime_mode === 'container'`, but the password input itself remains enabled. The backend rejects container-mode writes and calls, and no request is sent until a save action; the key remains only in component memory. This is a UI consistency/usability defect, not a P1 exposure. Disable the input in a later UI-only correction.

## Checks run against final source

| Check | Result | Evidence |
|---|---|---|
| `npm run build` (frontend) | PASS | TypeScript/Vite build; 126 modules transformed. |
| `python -m compileall -q src/api/server.py src/providers/ollama.py` | PASS | No compilation errors. |
| `docker compose -f docker-compose.ui.yml config --quiet` | PASS | Compose accepted the loopback ports, container marker, and mounts. |
| `git diff --check` | PASS | No whitespace errors; Git printed line-ending conversion warnings. |
| `python .bago/team/kit/scripts/teamctl.py verify` | PASS | Coordination state and completed handoffs validated before AC04 submission. |
| AC09/AC10 route and Origin source inspection | PASS | Final `src/api/server.py` hash is `c8b5bb35ec8bf0c1fbb3972c8be815aff70fd785e32c5ebd962a461134acfda6`, matching AC10. |
| Automated tests | NOT_RUN | Not requested in this review assignment. |
| Browser/manual keyboard and screen-reader review | NOT_RUN | No browser session was started. |
| Native launcher, Docker runtime, live WebSocket handshake, OS credential store, and Ollama provider calls | NOT_RUN | No app process, credentials, or provider request was used. |

## Handoff/hash reconciliation

Final changed-source hashes were compared against the latest handoffs: `src/api/server.py` and the contract match AC10; provider adapter, ProviderSettings, Compose, launcher, and local setup match AC08; unchanged UI files match AC03; provider package and requirements match AC02. Older AC01/02/03/06/07/08/09 hashes for files later amended by accepted change requests are superseded by the downstream handoffs, not unexplained candidate mismatches. AC10 handoff payload validates through `teamctl verify`.

## Remaining limitations

- Runtime behavior is not certified: the local launcher, Docker UI, WebSocket handshakes, secure store, and Ollama Cloud/local CLI were not executed.
- Host-local loopback and Origin checks do not authenticate a hostile local process; LAN deployment remains unsupported.
- Governed agent job execution is intentionally unavailable until an authorized capability and traceable result exist.
