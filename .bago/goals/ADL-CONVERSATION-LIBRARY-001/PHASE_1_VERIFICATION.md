# ADL Conversation Library - Phase 1 Verification

**Goal:** `ADL-CONVERSATION-LIBRARY-001`  
**Candidate HEAD:** `69b4f4b1ead2552b527e6e48868ab36cc2b38cbc`  
**Branch:** `codex/conversation-library-v1`  
**Worktree:** `%USERPROFILE%/AppData/Local/Temp/BAGO_AGENTIC_DATA_LAB_conversation_library`

## Implemented boundary

- New conversation domain: `src/conversations/library.py` and `src/conversations/__init__.py`.
- Default database: `%LOCALAPPDATA%/BAGO/AgenticDataLab/conversations/library.sqlite3`; tests can set `BAGO_CONVERSATION_DB_PATH` to isolate browser/recovery runs.
- One fixed project identity (`bago-agentic-data-lab:default`) and owners limited to the ADL App Assistant or configured ADL agent IDs. No Codex conversation import or other-project selector is present.
- Conversation rows own stable IDs, project/owner identity, timestamps, title, lifecycle status, and a revision. Message rows own stable IDs, per-conversation sequence, role, content, timestamp/status, and optional JSON source/trace references.
- The conversation store has no provider credential fields. Provider configuration and OS credential storage remain separate. Chat history is loaded by the backend from the conversation ID; the browser does not submit saved history as authority.
- The App Assistant and each configured agent have separate lists and threads. The UI supports new/open, rename, archive, soft-delete, and restore.

## Acceptance audit

### App Assistant capability correction (2026-10-09)

- The React chat routes standalone greetings and explicit “what can you do?” queries to the backend `help` operation instead of relying on an unconstrained model answer.
- The backend's localized, persisted response explicitly says that the user can request an agent draft in chat, review/edit it, and save only by choosing **Create agent**. It also accurately states that this chat does not start jobs or modify files.
- Direct agent creation requests still route to `draft_agent`; `POST /api/agents/create` remains the separate confirmation action. The assistant cannot silently create the agent.
- Evidence: `tests/test_conversation_library.py::test_app_assistant_greeting_explains_agent_creation_without_model_claims` proves the persisted response and verifies the model is not called for a greeting. `npm run build` passed for the React client.
- Scope: source and automated API behavior verified in this worktree. The running app in the user's other checkout was not restarted or exercised in this check.

| # | Requirement | Evidence | Result |
|---|---|---|---|
| 1 | Stable conversation identity, owner/project binding, timestamps, lifecycle, title, revision | `test_owner_scoping_restart_and_message_references_are_persistent`; browser API state after recovery | **VERIFIED** |
| 2 | Stable ordered messages with source/trace references; provider secrets kept out of this store | SQLite schema and message serialization in `src/conversations/library.py`; persistence/reference test | **VERIFIED** |
| 3 | Separate per-user SQLite store | Default-path assertion in `test_default_database_is_per_user_and_outside_repository`; browser exercised an isolated SQLite file via the path override | **VERIFIED** |
| 4 | Backend-authoritative history | App Assistant and agent endpoints load history from the conversation ID; `AgentChat.tsx` sends ID/revision without `conversation_history`; saved-history unit test | **VERIFIED** |
| 5 | Separate App Assistant and per-agent threads survive owner switching | Real-browser snapshots switched App Assistant → `Library test agent` → App Assistant; both histories remained distinct | **VERIFIED** |
| 6 | New/open/recent, rename, archive, soft-delete, restore | Real-browser workflow performed each action; archived/trash/active views returned the expected controls and rows | **VERIFIED** |
| 7 | Sources and trace IDs remain attached when supplied; absent evidence is not invented | Persistence test checked a source path and trace ID; browser reopened agent messages with `trace-test-1` / `trace-test-2` references | **VERIFIED** (reference persistence only; those `trace-test-*` values are fixtures, not real executions) |
| 8 | Revision concurrency prevents silent overwrite | `test_revision_conflicts_and_rename_archive_delete_restore` rejects stale revision | **VERIFIED** |
| 9 | Three App Assistant replies, two separate conversations for one agent, owner switching, restart recovery, metadata/message retrieval, and lifecycle | The assistant thread has four exchanges, including the deterministic capability greeting. Browser-created agent threads `conv_fddf034826a34cb68f0207f5d335d970` and `conv_4a1cff90cb4644c58299ea6739d1b696` each have their own user/assistant pair. The backend was restarted with a local mock provider for those two turns, restored to its normal provider adapter, then a fresh headed browser (PID `44476`) reopened the App Assistant and both agent threads. The new browser retrieved conversation list/details with HTTP 200. A separate failed-provider probe conversation was renamed, archived/restored, soft-deleted/restored, and ended active at revision 6. | **VERIFIED** for persistence, owner separation, restart recovery, metadata, and lifecycle. Agent responses/traces are explicitly synthetic fixtures; live Ollama generation was not run. |
| 10 | Backend and real-browser verification without requiring an LLM to reopen history | Focused backend tests plus Playwright on a fresh browser process after backend restart; network log shows conversation GETs on reopen; no model generation was used | **VERIFIED** |

## Executed verification

- `python -m pytest tests/test_conversation_library.py tests/test_agent_chat_trace.py tests/test_agent_draft_retry.py -q` → **8 passed**. Python 3.14 emitted the existing LangChain Pydantic V1 compatibility warning.
- `python -m compileall -q src/conversations src/api/server.py` → **PASS**.
- `npm run build` in `frontend/` → **PASS** (`tsc -b`, Vite 4.5.14; 126 modules transformed).
- `git diff --check` → **PASS** (Git emitted the existing LF-to-CRLF working-copy warning for `AgentChat.tsx`).
- `npx.cmd --yes --package @playwright/cli playwright-cli -s=adl-library ...` drove the actual headed browser at `http://127.0.0.1:8084/`. The fixture agent chat endpoint was exercised twice through the UI and real FastAPI route. A temporary `sitecustomize` hook replaced `ollama.chat` and trace creation only in the mock server process; it returned visible `TEST FIXTURE ONLY` responses, wrote exactly two local-mock call records, and issued no Ollama/Cloud requests. The fixture agent JSON was restored to its original no-model configuration afterward.
- Backend PID `43804` ran the test-only local mock on port `8084` and the isolated database path; it was stopped and the normal `uvicorn src.api.server:app` process restarted as PID `40912` with the original environment and database path. Provider status remained `not_configured`.
- The Playwright session `adl-library` was closed. A new headed browser session opened at PID `44476`. It loaded the assistant thread, switched to the agent, and retrieved both separate conversations; Playwright network records show assistant and agent conversation list/detail GETs returned `200`. The previous browser PID was not captured.
- After restart, the real UI sent `Hola!` to the deterministic App Assistant capability route; the saved reply advertises agent drafting and review/confirmation. `POST /api/chat/control` returned `200` without a provider call.
- Raw restart/API/message/trace receipt: `BROWSER_RESTART_RECEIPT.json`. Fixture model-call ledger: `MOCK_AGENT_CHAT_CALLS.jsonl`.
- Screenshots: `agent-browser-alpha.png`, `agent-browser-beta.png`, `agent-browser-recovered-alpha.png`, `agent-browser-recovered-beta.png`, and `assistant-capabilities-browser.png` under `.bago/goals/ADL-CONVERSATION-LIBRARY-001/`. Earlier App Assistant/agent screenshots remain under `output/playwright/`.

## Limits and residual evidence

- Ollama was `not_configured` in the dedicated worktree test server. No paid/cloud model call or live agent generation was performed. This did not prevent list/open/resume/library lifecycle checks.
- Playwright logged one unrelated pre-existing `GET /api/artifacts` → `404` on page load. Conversation APIs returned `200` and the library flow completed.
- `python .bago/bin/bago.py verify ...` was **NOT_RUN** because `.bago/bin/bago.py` is absent in this worktree. The focused tests, build, direct API observations, and browser evidence above are the available verification.
- The browser fixture agent and test database contain intentionally synthetic sample chats/traces. The database is isolated by `BAGO_CONVERSATION_DB_PATH`; the agent fixture was restored to `provider_id: null` and `model_id: null`. These are not live agent reasoning or real LocalTrace/Jaeger evidence.
- `npm run lint` is **NOT_RUN**; the frontend package has no installed ESLint executable, as found during the earlier build check.
- Final recheck on 2026-10-09: the focused suite again reported **8 passed**; `npm run build` again passed with 126 modules transformed; `git diff --check` passed with the existing LF-to-CRLF warning.
- Read-only inspection of the isolated SQLite file confirmed both recovered browser conversation IDs still exist with the expected agent/project binding, revision 2, and ordered user/assistant messages. The candidate backend process (PID `40912`) returned `/api/health` HTTP `200` on port `8084`.

## Candidate identity after implementation

- HEAD remains `69b4f4b1ead2552b527e6e48868ab36cc2b38cbc`; no commit, push, merge, or sync was performed.
- The pre-goal dirty-state fingerprints and source baseline remain in `goal.md`. The implementation remains an uncommitted diff in this dedicated worktree; other pre-existing work was preserved.
- The source `codex/agent-chat-control-v1` worktree remains at the same HEAD and tracked-diff fingerprint it had before this goal (`9bb0259e8730ec77d7427b1b9ff4c3e235b12f278b2193de7cd8a9f9540105b4`). The full 46-entry pre-goal status inventory was recovered from the Codex session record; its normalized SHA-256 matches the frozen fingerprint `3256bedc478acd6ab53c2d08ce830c93af9dd32b3c24495fbf00e274e2606c53`. All 46 paths remain present with the same Git status; the only three additional paths are this goal's `PHASE_0_REUSE_MAP.md`, `goal.md`, and `status.json`. No baseline path is missing and no status code changed.
- One pre-existing untracked server stdout log has a later modification time because its already-running API process continued writing runtime output. It remains present and the output was appended. Other baseline untracked files have modification times before this goal. Individual pre-goal content hashes were not captured for untracked files, so byte-for-byte identity of every untracked file is not claimed.
- `SOURCE_WORKTREE_SNAPSHOT_20261009.json` stores the recovered 46-entry baseline, reconciliation, and current working-file hashes so subsequent work can detect changes.
- The final candidate worktree has 32 status entries. `git diff --binary HEAD` SHA-256: `d597096fdf35e1b0db1cfa0d7434bd6c82b9932ffe0b671738d050e323db131b` (90,440 bytes). This tracked diff includes changes that predate this goal; it is not a goal-only patch fingerprint. No commit, push, merge, or sync was performed.
