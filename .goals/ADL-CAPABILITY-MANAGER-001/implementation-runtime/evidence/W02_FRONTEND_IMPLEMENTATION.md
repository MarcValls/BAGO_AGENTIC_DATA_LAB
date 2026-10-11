# W02 - Capability Manager frontend implementation

- Work item: `W02`, role `frontend-engineer` / `bago_frontend_engineer`.
- Candidate: `C:\Users\AMTEC_Terminal_1º\AppData\Local\Temp\BAGO_AGENTIC_DATA_LAB_conversation_library`.
- Branch and base HEAD: `codex/conversation-library-v1` / `69b4f4b1ead2552b527e6e48868ab36cc2b38cbc`.
- Lifecycle: **EXECUTED**; source build **VERIFIED**. Not VALIDATED because live API and browser verification are incomplete.
- Worktree was already dirty at task start, including `AgentChat.tsx` and `AgentChat.css`; those changes were preserved and this work was layered onto them. No cleanup, revert, commit, sync, or process restart was performed.

## Implemented

- Added `Capabilities` to the existing root router in `frontend/src/App.tsx`; there is no second router.
- Added `CapabilityManager.tsx` and CSS. On mount and refresh it reads the backend catalog and persisted proposal list. It displays returned status, effect, provider, integration state, source availability/fingerprints, limits, authority notice, proposal revisions/expiry, and explicit cancel controls. Loading, empty, and error states are present.
- Extended the chat's deterministic intent handling for capability inventory/status, proposal requests, and navigation to the manager. These capability requests use the backend catalog endpoint directly; model prose is not used as a function call.
- A proposal request displays an editable review card. Capability selection is from the exact backend catalog entries; no fuzzy choice is made. Summary and requested scope must be reviewed and non-empty before an explicit Save action calls `POST /api/capabilities/proposals` with the active `conversation_id`.
- Cancel uses an explicit UI button and the server-returned revision. Catalog/proposal state is refreshed from API responses. Neither operation grants authority, runs code, or creates jobs.
- Persisted proposal cards are reloaded by `conversation_id`. The current backend has no arbitrary chat-message append endpoint, so locally rendered inventory replies and proposal-system notices are **not** added to the durable transcript. The proposal record itself is persisted by the API.

## Verification evidence

1. `npm --prefix frontend run build` — **PASS**. `tsc -b` and Vite production build completed; 128 modules transformed.
2. `npm --prefix frontend run lint` — **FAIL (tool unavailable)**. The script ran, but Windows reported `"eslint" no se reconoce como un comando interno o externo`; no ESLint executable is installed in this checkout. No dependency was installed.
3. `git diff --check -- frontend/src/App.tsx frontend/src/components/AgentChat.tsx frontend/src/components/AgentChat.css` — **PASS**.
4. `GET http://127.0.0.1:8084/api/capabilities` — **HTTP 404**. The listener on 8084 is Python/Uvicorn launched from this candidate's `.venv-ollama-spiral`, but the active process does not expose the W01 route; live frontend-to-backend integration is therefore **NOT_VERIFIED**. This result is recorded as a likely stale server process, not as proof of source/API failure. No restart was attempted, per orchestrator instruction.
5. Browser/rendered visual inspection — **NOT_RUN**. `cua.getState()` returned no apps and no browsers; no dependency was installed.
6. Frontend test suite — **NOT_RUN**; no test command or test file was added as part of W02.

## Scope and remaining risks

- Source write scope: only `frontend/src/App.tsx`, `frontend/src/components/AgentChat.tsx`, `frontend/src/components/AgentChat.css`, `frontend/src/components/CapabilityManager.tsx`, `frontend/src/components/CapabilityManager.css`.
- The build verifies the final TypeScript/Vite source compiles. It does not prove browser interactions or live API operation.
- Need a browser-backed interaction check and a server exposing these exact candidate routes before claiming end-to-end integration.
- ESLint cannot run until the repository provides its executable; this task did not install packages.
- Proposal creation/cancellation are records only. No authenticated actor approval, capability enablement, agent/job execution, or execution receipt exists in this UI increment. Agent Runner remains fail-closed.
- Conversation transcript limitation is described above; proposals remain queryable through the backend and linked to their conversation ID.

## Handoff

`W03` may independently inspect the five scoped frontend files and the build/lint/runtime evidence. The orchestrator should resolve the 8084 listener/runtime mismatch before any live demonstration. No commit or synchronization was made.
