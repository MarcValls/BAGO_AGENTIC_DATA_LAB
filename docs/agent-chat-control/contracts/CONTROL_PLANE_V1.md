# Agent Chat Control Plane v1 — contracts

Status: v1.2 runtime and compatibility amendments accepted for AC06–AC08; original v1 remains historical. Scope is the first working vertical slice: provider setup, agent inventory, reviewed conversational creation, and real Ollama chat. It does not claim general app control or governed job execution.

## Provider configuration

One provider is initially supported: `ollama-cloud`. The user selects one authentication mode in the UI:

- `api_key`: call `https://ollama.com/api/...` from the backend with the bearer key. Store the key in the operating system credential store. The UI may submit a new key but must never read it back, put it in browser storage, or include it in chat history or agent JSON.
- `local_cli`: use the local Ollama HTTP service at loopback. Ollama owns its signed-in state. The application must not inspect or copy Ollama's auth files. The state `local_service_available` only confirms the local service responds; it does not prove Cloud authentication. A Cloud model response is `verified` only after a user-initiated request succeeds.

Provider state is one of `not_configured`, `needs_authentication`, `local_service_unavailable`, `configured_unverified`, `ready`, `unsupported_runtime`, or `error`. `ready` requires a successful provider/model check from the current process. Never infer it from a stored checkbox or a model catalog.

Only the canonical Ollama Cloud host and loopback Ollama endpoint are allowed in v1. Do not accept arbitrary provider URLs from the browser. Model discovery results carry `provider_id`, `model_id`, display name, and discovery source; a public catalog entry is not proof that the user's account can run it.

The first release is host-local: the API defaults to loopback, the Docker UI port is published on `127.0.0.1`, and browser CORS is limited to explicit local UI origins. CORS origin overrides are rejected unless every origin uses `localhost`, `127.0.0.1` or `::1`; credentialed CORS is disabled. Every WebSocket handshake also requires an exact `Origin` match against this validated local origin allowlist; missing or non-local origins are rejected before any endpoint work. LAN exposure is unsupported until the application has an authenticated API boundary; changing the CORS allowlist alone is not sufficient authorization.

The supported Ollama provider runtime is the host-local app launched by `scripts/run-local-ui.ps1`. The Docker UI keeps application data on host-mounted paths but reports Ollama provider setup as unsupported: its container cannot access the host OS credential vault or host-loopback Ollama service. The UI disables provider configuration in that runtime and shows the host-local launch path instead of accepting a key that cannot be stored securely.

## Agent record and inventory

An application agent is a persisted record with a stable `agent_id`, `config`, and `created_at`. New records use a random `agent_` plus 32 lowercase hex digit ID. For backward compatibility, valid existing records with `agent_` plus 8–32 lowercase hex digits remain visible when the ID matches the filename. Its config contains name, description, type, system prompt, optional provider/model IDs, and tool IDs selected from the server allowlist. It never contains provider credentials.

`GET /api/agents/list` is the authoritative inventory for user-created application agents. It returns records the backend successfully parsed and a count; malformed files are reported as an inventory warning rather than silently presented as valid agents. Older valid records may omit provider/model IDs; the API must preserve and return those fields as null, without rewriting the file. Agent chat may use the currently selected provider/model in memory for that request only and must not auto-migrate the persisted record. It does not claim to inventory Codex subagents or every framework process in the wider BAGO installation.

## Chat operations

The control chat can provide assistant text, list agents from the backend inventory, draft an agent config, and navigate to a named existing view. It may not call arbitrary URLs, APIs, shell commands, or tools inferred from model output.

An agent creation turn returns an `agent_draft` proposal. The UI displays the full validated configuration and offers explicit **Create agent** and **Cancel** actions. Only the create action calls the mutating endpoint. The backend validates the body again, assigns a random ID, and persists it. An LLM response alone is never a creation or authorization event.

Per-agent chat sends only the selected `agent_id`, user message, and bounded conversation history. The backend reloads the config by ID; it does not trust a config or tool list supplied by the browser. The model must be configured and available before a live response is attempted. For a legacy record with no model, use only the explicitly selected current provider/model for that request; do not persist the fallback into the record. Provider errors are surfaced; there is no simulated fallback.

## Authorization boundary

The first slice can list, draft, create after explicit human confirmation, and navigate. Creating an agent changes local application state, so it always requires the explicit create control. Job dispatch, file changes, provider mutation, GitHub actions, and other app effects are not available as implicit chat tools. The legacy `/ws/agents/run` transport is fail-closed and must not create a job or report success until a registered capability runs through the backend authority/permit path and produces a traceable result. Any future capability must be explicitly registered, checked by that path, and produce a traceable result before the chat can report execution.

## API shape owned by AC02

- `GET /api/providers/ollama/status` - non-secret provider state, including the active runtime mode and whether provider setup is supported there.
- `PUT /api/providers/ollama/config` — select `api_key` or `local_cli`; secret write is write-only.
- `GET /api/providers/ollama/models` — available/discoverable models with source and availability confidence.
- `POST /api/providers/ollama/verify` — explicit connectivity/model verification; any generation cost must be disclosed before the request.
- `POST /api/chat/control` — one control-chat turn, returning assistant text and optional validated agent draft.
- `POST /api/agents/{agent_id}/chat` — live chat against server-loaded agent config.
- Existing `GET /api/agents/list` and `POST /api/agents/create` remain the inventory/create authority; IDs must be generated server-side.

All errors are structured and must not contain credentials, authorization headers, or provider response bodies that could echo secrets.
