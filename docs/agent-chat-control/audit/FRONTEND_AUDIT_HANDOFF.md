# Frontend audit handoff

## Candidate and running UI

- Repository: `C:\Users\AMTEC_Terminal_1º\AppData\Local\Temp\BAGO_AGENTIC_DATA_LAB_chat_control`
- Branch: `codex/agent-chat-control-v1`
- UI: `http://127.0.0.1:8081` (host mode; current Ollama provider state is `not_configured`)
- Entry/navigation: `frontend/src/App.tsx`, `frontend/src/App.css`
- Main agent-creation/chat flow: `frontend/src/components/AgentChat.tsx`, `AgentChat.css`
- Provider configuration: `frontend/src/components/ProviderSettings.tsx`, `ProviderSettings.css`
- Legacy builder/runner, demo and portfolio: `AgentBuilder.tsx`, `AgentRunner.tsx`, `Control.tsx`, `JobHistory.tsx`, `Summary.tsx`, `Retrieval.tsx`, `Authorization.tsx`, `Trace.tsx`, `Evaluation.tsx` under `frontend/src/components/`.
- Inspector feature: `frontend/src/features/decision-inspector/`.
- API and authoritative request/response validation: `src/api/server.py`; Ollama provider logic: `src/providers/ollama.py`.

## Endpoints called by the frontend

| Method | Path | Frontend use |
|---|---|---|
| GET | `/api/artifacts` | Loads artifact bundle for Inspector and portfolio views. |
| GET | `/api/agents/list` | Chat inventory, legacy Builder/Runner. |
| POST | `/api/chat/control` | App assistant operations: chat, list agents, draft agent, navigate. |
| GET | `/api/providers/ollama/models` | Confirmed model choices in Provider Settings and agent draft review. |
| POST | `/api/agents/create` | Saves a reviewed agent draft or legacy Builder form. |
| POST | `/api/agents/{agent_id}/chat` | Live chat with a selected agent. |
| GET | `/api/providers/ollama/status` | Provider state and current auth/model selection. |
| PUT | `/api/providers/ollama/config` | Saves selected auth mode/model; API key is write-only. |
| POST | `/api/providers/ollama/verify` | Non-generative model listing check. |
| GET | `/api/jobs/list` | Job History. |
| POST | `/api/demo/run` | HTTP path for demo execution from Control. |
| WS | `/ws/demo/run` | Streaming demo execution from Control. |
| WS | `/ws/agents/run` | Legacy Runner; backend currently fails closed with execution unavailable. |
| GET | `/api/agents/export` | Downloads agent export. |
| POST | `/api/agents/import` | Imports uploaded agent archive. |

Backend also declares additional APIs not called by this frontend; see route decorators in `src/api/server.py` before expanding the review scope.

## Contract anchors

- `AgentConfig`, `AgentCreateRequest`, `OllamaConfigRequest`, `OllamaVerifyRequest`, and `ControlChatRequest` are declared near the top of `src/api/server.py`.
- Agent draft remains a proposal (`created: false`); creation is a separate explicit `POST /api/agents/create`.
- Provider config must not expose the API key in status/list responses.
- Provider model discovery reports listed availability; it does not prove inference works.
- `/ws/agents/run` is intentionally unavailable pending a governed execution path.

## Known review targets

- `AgentRunner.tsx` and `Control.tsx` hard-code WebSocket URLs to `ws://localhost:8080`. The local launcher now selects another port when 8080 belongs to another process; these two WebSocket clients therefore need review against dynamic-port startup.
- The Runner UI's legacy success/error interpretation should be checked against the backend's fail-closed WebSocket protocol.
- Validate provider setup states, empty/error model discovery, editable AI draft, explicit create/cancel, and disabled creation without a backend-confirmed model.
- Verify keyboard/focus behavior, responsive layout, loading/error states and handling of backend `detail.message` vs generic errors.

## Audit boundary

This packet is sufficient for a source-level frontend and API-contract audit. To audit live provider behavior, the user must configure Ollama in Provider Settings and initiate their own model request. No credential is included here. The current server is host-local; browser automation was unavailable to this session, so UI visual interaction has not been independently observed.
