# BAGO Agentic Data Lab — manual frontend source audit

**Identificador de auditoría:** `CRIT-BAGO-ADL-FRONTEND-20261009-01`  
**Autor / auditor:** ChatGPT — GPT-6 (OpenAI); revisión manual estática asistida por IA. No se atribuye la ejecución a Codex CLI.  
**Fecha y hora de emisión del informe original:** 2026-10-09 16:21:09 CEST (`Europe/Madrid`, UTC+02:00; según marca de modificación del archivo, no bitácora de ejecución).  
**Fecha y hora de esta revisión de metadatos:** 2026-10-09 16:21:48 CEST (`Europe/Madrid`, UTC+02:00).  
**Revisión del documento:** `1.1` — únicamente se añade identificación y atribución; los hallazgos originales se conservan.  
**Disposition:** **NOT VALIDATED**; source-only review. **P0: 0; P1: 9; P2: 9.** These counts describe findings in the inspected snapshot, not runtime-confirmed incidents.

## Candidate, scope, and evidence boundary

- **Repository candidate:** `BAGO_AGENTIC_DATA_LAB_chat_control`, branch `codex/agent-chat-control-v1`; **base HEAD** `4d6a0a95932cb4167b8f6a8caa6fdfcd79f4abff`. The pack explicitly reports worktree modifications: the archive is **not** asserted to be a clean checkout of this SHA. Snapshot packaging date: 2026-10-09.
- **Inspected:** `frontend/src/App.tsx`, `App.css`, `AgentChat`, `ProviderSettings`, remaining supplied UI components, Decision Inspector/adapters/contracts, `frontend/vite.config.ts`, `src/api/server.py`, `src/providers/ollama.py`, `scripts/run-local-ui.ps1`, and the handoff. Backend inspected **only** for frontend API/WebSocket contracts and security boundaries. All findings refer to **lines in these packed files**.
- **Integrity of input:** uploaded ZIP SHA-256 `fc279afdf56a5179748faf99a466b5fbf2953a71bcb3aadf70df577855961543` matches the supplied sidecar; **59/59** manifest-listed files match `SHA256SUMS.txt` after translating its `20261009\...` path prefix to the extracted layout. This is package-integrity checking, **not** application verification.
- **Provider baseline:** `not_configured` (handoff); no key or live provider evidence included. The handoff's reported local UI URL `http://127.0.0.1:8081` is historical context, **not** independently checked.
- **Evidence classification:** *Confirmed source defect* means a deterministic inconsistency or unguarded path visible in code; its manifestation in a browser remains **NOT_RUN**. *Risk* identifies a conditional outcome requiring suitable data or interaction. A declared backend route does not prove its availability in a running process.

## P0 — Critical

**None found within reviewed source scope.** This does not certify absence of runtime P0 defects.

## P1 — Major

### P1-01 — WebSocket clients target the wrong port when the launcher relocates
- **Status/confidence:** Confirmed source defect / **High**.
- **Location:** `frontend/src/components/AgentRunner.tsx:59-66`; `frontend/src/components/Control.tsx:22-29,199-203`; `scripts/run-local-ui.ps1:94-110,154-160`; `src/api/server.py:215-221`.
- **Evidence:** Both clients hard-code `ws://localhost:8080`, whereas the launcher chooses the first free port from 8080–9000 and serves the UI on that port. The WS server also enforces an exact allowed `Origin`.
- **User impact:** With the UI at 8081, Runner/Control WS does **not** connect to the UI's corresponding backend. It can fail the handshake, or target a different listener on 8080 (potentially disclosing the transmitted agent configuration to that listener); the exact observed outcome is not verified. Same-origin HTTP requests do not share this defect.
- **Correction:** Build the URL from `window.location.host` and `location.protocol` (`ws:`/`wss:`), centralize it, and stop displaying 8080 as the fixed endpoint. Include a port-relocation integration check before release.

### P1-02 — The exposed Agent Runner promises an execution capability explicitly unavailable on the server
- **Status/confidence:** Confirmed contract/UI mismatch / **High**.
- **Location:** `frontend/src/components/AgentRunner.tsx:53-97,188-197`; `src/api/server.py:832-849`.
- **Evidence:** Runner offers **Run**, waits for `stdout`/`done`, and can declare success, but `/ws/agents/run` sends only `type:error`, `code:execution_unavailable`, then closes with 1008; it starts **no** agent job. Runner also reports success for any hypothetical `done` regardless of `exit_code` (`:75-85`).
- **User impact:** The interface advertises an executable agent even though the authoritative backend intentionally fails closed. The actual server's error is supported, but the controls and status semantics are misleading.
- **Correction:** Mark this legacy view **Execution unavailable**, disable/remove Run until a governed executor exists, display server `code`, and accept success only on an explicitly successful terminal result with `exit_code === 0`.

### P1-03 — The persisted-agent create boundary does not require a provider-listed model
- **Status/confidence:** Confirmed validation gap / **High**.
- **Location:** `frontend/src/components/AgentBuilder.tsx:4-15,96-108,280-286`; `frontend/src/components/AgentChat.tsx:160-169,195-207,256`; `src/api/server.py:594-611`; `src/providers/ollama.py:41-45,98-103,223-245`.
- **Evidence:** The chat draft UI checks membership in a backend-returned `listed` model array. The legacy Builder sends **no model** and delegates selection to saved provider settings. The backend accepts either a client-supplied model ID or saved `model_id`, checking only syntax, not current `/models` membership; provider config itself permits any syntactically valid ID. Create requires a configured provider, **not** a confirmed listed model.
- **User impact:** A stored agent may pin an unlisted/unavailable model despite the stated confirmed-model workflow. A user could see **Agent Created** yet be unable to chat. This does **not** imply inference was tested.
- **Correction:** At `/api/agents/create`, require a model present in the model list **for the current auth configuration**, or explicitly classify an unverified selection and block creation under the confirmed-model contract. Add model selection to Builder; keep draft-only generation separate from persistence.

### P1-04 — In-flight chat replies can be assigned to a different selected agent
- **Status/confidence:** Confirmed async state race / **High**.
- **Location:** `frontend/src/components/AgentChat.tsx:110-135,228-229,235-245,252-255`.
- **Evidence:** A send captures `selectedAgent`, issues a request, and later appends the response to component-level `messages`. During `sending`, agent-switch and **App assistant** buttons remain enabled and immediately clear messages/change selection. No request ID, conversation ID, abort, or active-selection check guards the late response.
- **User impact:** A response for agent A can appear in agent B's conversation, or a cleared App assistant chat, under the wrong speaker name. Conditional on switching before response.
- **Correction:** Give each conversation a stable ID and bind responses to it; abort/ignore obsolete requests on switching; optionally disable switching while pending, with an explicit cancellation affordance.

### P1-05 — Inspector can present trace events belonging to a different run
- **Status/confidence:** Confirmed correlation-validation gap / **High**.
- **Location:** `frontend/src/features/decision-inspector/integration/DecisionInspector.tsx:59-62,83-101,135-150,175-180`; `frontend/src/adapters/trace/localTraceAdapter.ts:4-6,31-38`.
- **Evidence:** A conclusion derives its identity from `agent_run.run_id`; `trace` is accepted whenever it has strings for `trace_id`/`run_id` and an events array. Neither mapping nor rendering requires `trace.run_id === agent_run.run_id` or checks event trace/run identities.
- **User impact:** A mixed/stale `/api/artifacts` bundle could show another run's timeline alongside the current conclusion as if correlated. No such mixed bundle is supplied in the snapshot; exposure is data-conditional.
- **Correction:** Reject or quarantine mismatched run IDs, surface an explicit **correlation mismatch** state, and validate event-level trace identity before offering navigation links.

### P1-06 — Action receipts can be marked matched without required proposal identities
- **Status/confidence:** Confirmed matching gap / **High**.
- **Location:** `frontend/src/adapters/action/agentRun.ts:86-106,138-145`; `frontend/src/contracts/action/action.ts:76-81`.
- **Evidence:** A receipt found by `receipt_id` is accepted as `matched` unless a **present** receipt `request_id` or `permit_id` *conflicts* with the proposal; missing identity values are not treated as mismatches. `validateActionBundle` repeats the same optional-when-present comparison. A success state requires a `matched` receipt, so this weak association can be consequential. The integration layer does first filter receipt arrays by run ID (`DecisionInspector.tsx:38-55`).
- **User impact:** For incomplete source receipts, the Inspector may overstate receipt association and show `succeeded` rather than `unverified`, even with no authoritative request/permit match.
- **Correction:** Define mandatory receipt-link identifiers and require **presence and equality** for every expected `run_id`, `request_id`, `permit_id`, and explicit receipt ID before `matched`; otherwise use `missing`/`mismatch`/`unknown` and preserve the raw record separately.

### P1-07 — Failed demo attempts are routed to potentially old evidence
- **Status/confidence:** Confirmed UI flow defect / **High**.
- **Location:** `frontend/src/components/Control.tsx:37-43,86-91`; `frontend/src/App.tsx:50-68,94-112`; `src/api/server.py:225-255,370-443`.
- **Evidence:** WS and HTTP handlers invoke `onDemoRun()` after **any** `done` or parsed HTTP response, including nonzero `exit_code`. App's callback refreshes `/api/artifacts` and switches directly to Inspector. The artifacts route simply reads the latest on-disk bundle; no completed `job_id`/run identity is correlated with the triggering attempt.
- **User impact:** A failed new execution can navigate to and display old successful artifacts, with no binding between what just ran and what is inspected. This is especially risky for evidence-facing portfolio claims.
- **Correction:** Navigate only after confirmed success **and** a fresh bundle whose run/job identity matches the launched execution; keep failures in Control with explicit status and retry. Show artifact timestamp/identity even for read-only browsing.

### P1-08 — Legacy agent export/import reports success while its data contract is not a ZIP import/export
- **Status/confidence:** Confirmed source defect / **High**.
- **Location:** `frontend/src/components/AgentRunner.tsx:104-135,154-165`; `src/api/server.py:774-798`.
- **Evidence:** Export returns JSON (`{agents, export_date, count}`), but the browser saves it as `agents-export.zip`. Import accepts `.zip` in the UI; server's handler is a stub returning `{"status":"imported","count":0}` and performs no import. UI reports success whenever HTTP `ok` is true without evaluating imported count. Request binding for `file: Any` is not proven without executing FastAPI.
- **User impact:** Downloaded archive is mislabeled; users can be told they imported agents when the handler has not stored any.
- **Correction:** Either disable both affordances as **not implemented**, or provide a real versioned JSON/ZIP contract with validation, count/warnings, and truthful filenames/status labels.

### P1-09 — Evaluation view makes unconditional validation claims
- **Status/confidence:** Confirmed presentation defect / **High**.
- **Location:** `frontend/src/components/Evaluation.tsx:20-41,70-95`.
- **Evidence:** The page reads `evaluation.status` and check results above, but **What Was Validated** always displays seven ticked claims (including no unauthorized effects), and **Interpretation** declares broad end-to-end guarantees without conditioning them on actual passed checks or evidence completeness.
- **User impact:** The view can assert guarantees even for a `FAIL`, incomplete, or incompatible evaluation artifact; users may mistake static text for verified evidence.
- **Correction:** Derive every assertion from explicit, keyed checks and referenceable evidence. Clearly distinguish a governance score from model-answer quality and external service validation. When absent/failed, label `NOT_VERIFIED` rather than displaying a checkmark.

## P2 — Moderate

### P2-01 — Provider model choices are stale after auth changes or discovery failure
- **Status/confidence:** Confirmed source state-management defect / **High**.
- **Location:** `frontend/src/components/ProviderSettings.tsx:42-75,80-103,131-139`.
- **Evidence:** Changing `authMode` does not clear `models`/`modelId`; `loadModels()` replaces the array only on success. Save/verify buttons are gated by a nonempty string, not membership in the currently loaded list.
- **User impact:** A model from a previous auth mode may be presented as selectable or submitted for a different one; a failed refresh can leave stale options visible.
- **Correction:** Invalidate models and model selection on mode/config changes and failed discovery; reselect from the current provider response only. Label selection vs **listed** vs **live response verified** distinctly.

### P2-02 — API errors are not decoded consistently in legacy views
- **Status/confidence:** Confirmed source defect / **High**.
- **Location:** `frontend/src/components/AgentBuilder.tsx:104-123,293-298`; `frontend/src/components/Control.tsx:76-96`; compare `AgentChat.tsx:29-37` and `ProviderSettings.tsx:9-16`.
- **Evidence:** Main chat and provider settings recognize `detail.message`; Builder reduces non-2xx to a generic error; Control's HTTP path reads success-shaped fields without checking `response.ok` or extracting `detail`. Backend emits structured errors, including 409/422/503 (`src/api/server.py:172-175,306-312,594-610`).
- **User impact:** Users are not told to configure a model, resolve validation, or retry a provider connection when the server already supplied an actionable reason.
- **Correction:** Reuse a single safe HTTP error decoder across all views and distinguish provider setup, invalid request, unavailable execution, and network failures.

### P2-03 — Agent inventory and job-history failures can look like empty data
- **Status/confidence:** Confirmed source defect / **High**.
- **Location:** `frontend/src/components/AgentRunner.tsx:36-45,139-174`; `frontend/src/components/JobHistory.tsx:29-45,96-100`.
- **Evidence:** Neither fetch path checks `response.ok`. Runner defaults to `[]` on missing `agents`; History defaults to `[]` on missing `jobs` and logs fetch errors only to the console. After initial loading, the History UI shows **No jobs yet** even when data could not be fetched.
- **User impact:** Operators cannot distinguish zero records from a broken/unavailable API.
- **Correction:** Use explicit `loading | ready | empty | error` states, validate response shapes, show retry, and retain the last good list only when flagged stale.

### P2-04 — Job-history detail UI expects fields its list API does not return
- **Status/confidence:** Confirmed contract mismatch / **High**.
- **Location:** `frontend/src/components/JobHistory.tsx:13-16,199-223`; `src/api/server.py:156-166,721-741`.
- **Evidence:** UI conditionally renders selected job `stdout`/`stderr`, but `JobResponse` and `/api/jobs/list` do not include those fields. Also, `selectedJob` holds a snapshot object not updated when polling refreshes `jobs` (`JobHistory.tsx:26,35-39,115-120`).
- **User impact:** Detailed logs are absent and selected-job status/details may remain stale while the list updates.
- **Correction:** Fetch a supported job-detail response containing logs if authorized, or remove unsupported fields; store selected ID and resolve it against each refreshed list.

### P2-05 — Legacy creation, selection, and file import have keyboard/label gaps
- **Status/confidence:** Confirmed markup defect / **High**.
- **Location:** `frontend/src/components/AgentBuilder.tsx:153-161,177-215`; `frontend/src/components/AgentRunner.tsx:157-165,176-198`; `frontend/src/components/JobHistory.tsx:115-120`.
- **Evidence:** Template cards and runner agent rows use clickable `<div>`; History uses clickable `<tr>`, all without keyboard activation semantics. Builder's standalone `<label>` elements lack `htmlFor`/nested fields; file input is `display:none` inside a styled label.
- **User impact:** Keyboard-only users cannot reach some selection actions; form fields can lack accessible names; import is not a reliable keyboard target.
- **Correction:** Use real `<button>` elements or explicit keyboard equivalents; pair labels/IDs; implement a focusable file-picker trigger. Verify with keyboard and screen reader later.

### P2-06 — WebSocket closing without a terminal message can leave Control in `running`
- **Status/confidence:** Confirmed stale closure path; manifestation conditional / **Medium**.
- **Location:** `frontend/src/components/Control.tsx:13-20,32-68`.
- **Evidence:** `onclose` checks the render-captured `status` (`if (status === 'running')`) rather than request-local terminal state; `setStatus('running')` does not update the handler's closed-over value. No connection timeout/terminal watchdog exists.
- **User impact:** A clean/abrupt close not preceded by a handled `error`/`done` may retain a running indicator and disabled run actions.
- **Correction:** Track completion in a request-local ref/variable, make `onclose` terminal unless a valid completion has been processed, and add a timeout and intentional-disconnect handling.

### P2-07 — Portfolio rendering trusts loosely typed artifact bodies
- **Status/confidence:** Risk from confirmed missing guards / **Medium**.
- **Location:** `frontend/src/App.tsx:17-23,50-64,101-112`; `frontend/src/components/Summary.tsx:39-43`; `Retrieval.tsx:49-66`; `Trace.tsx:24-29`; `Evaluation.tsx:32-37`; `src/api/server.py:225-255`.
- **Evidence:** `Artifacts` fields are `any`; backend loads JSON without schema validation; views directly call `.toFixed()` on expected numbers and `.map()` on expected arrays. App has a fetch-error state but no render-time malformed-bundle boundary.
- **User impact:** A present but incomplete or incompatible artifact bundle can throw during rendering instead of displaying which evidence is missing.
- **Correction:** Validate and version `/api/artifacts` at ingress (server or client), guard per-view fields, and render an explicit `invalid/unsupported artifact schema` state.

### P2-08 — Navigation does not manage focus after view changes
- **Status/confidence:** Source-level accessibility concern / **Medium**.
- **Location:** `frontend/src/App.tsx:84-99`; `App.css:16-23,30-42`; `frontend/src/components/ProviderSettings.tsx:124-126`; `frontend/src/features/decision-inspector/shell/InspectorShell.tsx:37-40`.
- **Evidence:** Buttons swap whole view content but do not move focus or announce the new view's heading; `<details>` remains open after selecting a portfolio item. Child views introduce nested `<main>` and extra `<h1>` landmarks. CSS contains breakpoints, but mobile behavior has not been visually checked.
- **User impact:** Keyboard/screen-reader users may lose context after navigation and navigate ambiguous landmarks; menu overlay may persist.
- **Correction:** Focus the newly mounted view heading/container, close the portfolio menu upon navigation, use a single page-level `<main>` and coherent heading hierarchy; validate narrow viewports later.

### P2-09 — Sending another app-assistant message silently discards an editable proposal
- **Status/confidence:** Confirmed source defect / **High**.
- **Location:** `frontend/src/components/AgentChat.tsx:110-120,195-226,253-262`.
- **Evidence:** `sendMessage` executes `setDraft(null)` for **every** new message before determining intent. The proposal has a separate **Cancel proposal** action, but typing and sending any unrelated message drops unsaved edits without confirmation.
- **User impact:** Work-in-progress draft changes disappear even though the user did not explicitly cancel or create the agent.
- **Correction:** Keep the draft across unrelated chat turns; require explicit cancel/replace confirmation, or isolate draft editor state from the conversation state.

## Review notes by requested area

- **Navigation / artifacts:** Chat is the default (`App.tsx:47,95`); portfolio evidence is lazy-gated by `/api/artifacts` with a loading/unavailable fallback and a Control shortcut (`:50-63,75,101-112`). The fallback does not identify stale-but-present bundles; see P1-07/P2-07/P2-08.
- **Provider setup / secrets:** API-key and local CLI modes are explicit (`ProviderSettings.tsx:129-139`). UI uses an in-memory password field, sends the key only in the config PUT, and clears the field in `finally` (`:87-103`). No `localStorage`, `sessionStorage`, password echo, or chat-history insertion was identified in the reviewed frontend. Backend stores auth mode/model in `ollama.json` and a key through an approved OS keyring (`ollama.py:62-79,98-144`); status/models/verify do not serialize the key (`:150-183,223-258`). The global validation handler avoids echoing rejected submitted values (`server.py:172-175`). **This is source evidence, not an independently tested guarantee of process logs, proxies, storage permissions, or live secret safety.** Container mode returns `unsupported_runtime` and blocks provider mutations (`ollama.py:48-59,150-160`), with corresponding disabled controls in the UI. Model listing is expressly non-generative; `ready` requires a successful model chat in this process (`ollama.py:181-183,261-273`). P2-01 applies.
- **Agent creation:** `/api/chat/control` `draft_agent` returns `created: false` and does not call `_write_agent` (`server.py:661-682`); persistence occurs only on separate `/api/agents/create` (`:594-611`). Chat draft review is editable, requires a listed model from the backend, and provides explicit Create/Cancel (`AgentChat.tsx:152-175,195-226,256`). The default `not_configured` provider prevents model-generated drafts and persistence through the normal backend preconditions. **Not all creation entry points enforce listed-model confirmation:** see P1-03.
- **Agent chat:** `/api/agents/{agent_id}/chat` retrieves server-owned configuration, bounds history (30 entries, 4,000 characters each), and rejects unsupported roles; no tool execution is supplied (`server.py:694-716`). The UI bounds history to 30 and checks `source === 'ollama'` (`AgentChat.tsx:122-134`). Main chat/provider error helpers handle string `detail` and object `detail.message`; the selection race is P1-04. Chat's `aria-live` transcript is present, but announcement quality and focus restoration are **NOT_RUN**.
- **Inspector:** Read-only action controls are deliberately disabled (`ActionReview.tsx:96-103`). It preserves missing claims and unknown freshness rather than synthesizing support (`DecisionInspector.tsx:76-101,113-128`; `evidence.ts:56-95`). Run correlation and strict receipt identity remain P1-05/P1-06. Displaying source attributes is not proof they were redacted upstream (`TraceTimeline.tsx:12-26`).
- **Legacy Runner / Control:** `/ws/agents/run` intentionally fails closed; `/ws/demo/run` genuinely declares `stdout`, `done(exit_code,job_id)`, and `error`, subject to origin validation (`server.py:451-532,832-849`). Port mismatch, false-positive success affordances, and stale evidence routing are P1-01/P1-02/P1-07; close-state handling is P2-06. Additional unused `AgentExecutor.js` contains the same port-8080 assumption but is not imported by the supplied App tree (`AgentExecutor.js:15`).
- **Accessibility / responsive:** Main chat offers labels, native buttons/selects, status/error roles, and a single-column layout below 760px (`AgentChat.tsx:232-262`; `AgentChat.css:77-86`); provider settings stacks auth choices below 650px (`ProviderSettings.css:48-54`). Legacy keyboard/label issues remain P2-05. No viewport or assistive-technology result is claimed.
- **Error/empty/loading:** The primary chat exposes inventory loading/error/empty, request errors, and model-unavailable notices (`AgentChat.tsx:73-100,239-259`). Provider UI distinguishes configured/unverified and container status. Legacy views are inconsistent (P2-02/P2-03); artifact schema failures are not explicitly represented (P2-07).

## NOT_RUN / not independently verified

Browser rendering or interaction; visual/narrow-viewport screenshots; keyboard/screen-reader audit; TypeScript compilation; tests; frontend build/lint; Python imports or API startup; requests to any HTTP or WebSocket endpoint; demo execution; agent execution; agent creation/import/export in a live backend; model listing, verification or inference; Ollama local/cloud calls; any API-key or credential action; network capture; dynamic-port runtime trial; OS keyring or file-permission inspection; CI; dependency vulnerability scanning. **No application source, configuration, manifests, or backend files were modified.** Only this audit report was created after read-only extraction and hash checking.

## Questions / limitations

1. Does the intended acceptance policy require **current model-list membership** or only a syntactically valid explicitly saved model? P1-03 reports the gap against the stated *backend-confirmed model* requirement; no change to that policy is assumed.
2. Are action receipts guaranteed upstream to contain `run_id`, `request_id`, `permit_id`, and `receipt_id`, and are mixed-run artifact bundles impossible by construction? Those producer contracts and actual demo artifacts are **not included**. If guaranteed, reproduce these checks at the Inspector boundary rather than assuming guarantees from unbundled code.
3. Is legacy Runner intended to remain navigable, or should it be hidden until execution is implemented? Current server intentionally provides no run capability.
4. Does a real `/api/agents/import` multipart request pass FastAPI binding for the current `file: Any` declaration? The implementation is demonstrably a no-op, but HTTP status/validation is **NOT_RUN**.
5. What is the canonical artifact-schema version and the run/job correlation field for `/api/artifacts`? The snapshot includes no schema declaration or runtime artifact examples sufficient to settle this.
6. The handoff reports an existing UI on port 8081, but no network access, process state, deployment configuration, or browser evidence was used; do not extrapolate this report to the active service or other repository revisions.

**Final disposition: SOURCE AUDIT COMPLETE; PRODUCT VALIDATION NOT PERFORMED.** Recommended remediation order: **P1-05/P1-06/P1-07 (evidence integrity) → P1-03 (creation boundary) → P1-01/P1-02/P1-08 (legacy/runtime truthfulness) → P1-04/P1-09 (conversation/evaluation presentation), then P2.** Re-audit a newly frozen snapshot with explicit regressions; do not label this candidate `VERIFIED` or `VALIDATED` from source review alone.
