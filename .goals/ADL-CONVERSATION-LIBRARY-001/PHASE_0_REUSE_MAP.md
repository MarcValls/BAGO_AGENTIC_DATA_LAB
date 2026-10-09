# Phase 0 — Conversation Library Reuse Map

**Goal:** `ADL-CONVERSATION-LIBRARY-001`  
**Candidate:** `69b4f4b1ead2552b527e6e48868ab36cc2b38cbc`  
**Remote main observed:** `78e4d9ff2bc69b4cda6352fedfe5df4c9adbf743`  
**Classification:** local source inspection; no product behavior inferred from a remote snapshot.

## Freeze and drift

The isolated worktree is on `codex/agent-chat-control-v1`. Its HEAD is one commit ahead and one commit behind the observed remote `main`, with merge base `4d6a0a95932cb4167b8f6a8caa6fdfcd79f4abff`. The worktree was already dirty before this goal: the tracked-diff and status fingerprints are recorded in `goal.md`. Existing `AGENT_CHAT_CONTROL_PLANE_V1` state is terminal `DONE`; this goal does not mutate that state or its frozen contracts.

## Current responsibilities

| Existing component | Classification | Evidence and boundary |
|---|---|---|
| `frontend/src/components/AgentChat.tsx` message state and owner selector | **EXTEND** | Messages are held in React state. `openControlChat` and `selectAgent` clear them, so owner switching discards the visible thread. Add conversation selection and persistence behavior here or extract a feature component without replacing agent inventory/draft flows. |
| `POST /api/chat/control` | **EXTEND** | Handles one App Assistant request at a time and returns an answer; it does not load or store a conversation. Accept a server-owned conversation ID and persist user/assistant messages around the existing provider call. |
| `POST /api/agents/{agent_id}/chat` | **EXTEND** | Accepts up to 30 history entries supplied by the browser. Replace that history authority with backend retrieval by conversation ID while retaining server-loaded agent configuration and current capability boundaries. |
| `_write_agent` / `_load_agent` | **REUSE** | Agent identity is already generated as `agent_` plus `uuid.uuid4().hex` and validated against the filename. The remote proposal's warning about Python `hash(name)` is stale for this local candidate; do not rewrite agent identity for this goal. |
| `src/jobs/__init__.py` and `jobs/history/*.json` | **REUSE AS SEPARATE DOMAIN** | These records track job execution status/output/metrics. They are not user chat transcripts and must not become the conversation store. |
| `src/retrieval/sqlite_vector_store.py` | **REUSE PATTERN ONLY** | Provides local SQLite connection/schema patterns for vector chunks. Keep its DB and tables separate from private conversation history. |
| `src/observability/local_trace.py`, `.bago/traces/agent-chat/` | **REUSE** | LocalTrace owns execution/trace evidence. Persist only real LocalTrace/Jaeger IDs and source receipts as message references; do not duplicate traces or claim trace evidence for the App Assistant when none exists. |
| `src/providers/ollama.py`, OS keyring, `.bago/providers/ollama.json` | **REUSE AS SEPARATE DOMAIN** | Provider identity/model/auth mode are provider configuration; secret material is in OS credential storage. Conversation rows must never include API keys or keyring payloads. |
| `.gitignore` and repository-local `.bago/` runtime data | **DO NOT REUSE FOR CHAT CONTENT** | Current local state/evidence under `.bago` appears as untracked data. Store private conversation content outside the repository under per-user local application data. |
| New conversation models/repository/service/API module | **NEW** | Own conversation IDs, message order, revisions, lifecycle (active/archived/deleted), and persistent message/source metadata. Separate this domain from jobs, vector retrieval, agents, provider configuration, and traces. |
| New conversation-library UI | **NEW / EXTEND** | Add recent conversation list and new/open/rename/archive/delete/restore controls. Preserve the existing chat composer, read opt-in, agent list, and draft-review flow. |

## Phase 1 boundary decisions

- The project ID is the current ADL workspace identity; no selector or access to other project roots is introduced.
- A single per-user SQLite database is separate from the existing vector index and jobs store.
- Opening a conversation is a local read and must not invoke Ollama.
- Resuming a conversation may use its saved messages as server-loaded model context. Any prior read-files checkbox, file capability grant, or other authorization is not carried forward; the user must opt in again per message.
- Conversation content is historical data, not canonical memory or authority. No context search, memory promotion, agent-execution recovery, idempotency protocol, or external chat import is part of this MVP.
- Trace/source references are retained only when the relevant response actually supplies them. Their linked systems remain the authority for evidence state.

## Phase 0 conclusion

No second chat-history owner exists in the current local implementation. Existing jobs, vector index, provider configuration, and LocalTrace each own different data. The MVP needs one new conversation store and one UI/library feature, while extending the existing chat routes and AgentChat owner switcher. The local stable agent UUID means cross-references can bind to identity, not visible names.

