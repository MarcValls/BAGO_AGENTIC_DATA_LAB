# W03 — Frontend audit: capability manager and chat integration

- Candidate: `C:\Users\AMTEC_Terminal_1º\AppData\Local\Temp\BAGO_AGENTIC_DATA_LAB_conversation_library`
- Branch/HEAD: `codex/conversation-library-v1` / `69b4f4b1ead2552b527e6e48868ab36cc2b38cbc`
- Scope: read-only inspection of frontend and chat-control contract. Worktree was deliberately dirty at start; no source or state files were edited. Tests: `NOT_RUN` (inspection task).
- Source hashes below bind findings to the examined dirty candidate contents; they are not commit blobs and do not imply those changes are committed.

## Findings

### Navigation and view ownership

`frontend/src/App.tsx` (`SHA256 AE8F2C63131B100C69CBCD46B3ED80755FDBF3105660F11DF8D358772C554AD2`) owns the current view via `activeTab`, defaults to `chat`, and routes workspace, portfolio, and settings view buttons through a single `navigation` array (lines 25–40, 43–48, 84–92). It mounts `AgentChat` only while the chat tab is active, alongside `ProviderSettings`, `AgentBuilder`, `AgentRunner`, and `DecisionInspector` in the view switch (lines 94–111). Chat-originated navigation maps `traces` to `trace` and updates the same root-owned tab (lines 70–73).

**Integration point:** add a single `capabilities`/`capability_manager` view to `AppView`, `AssistantView`, and `navigation`; mount its dedicated manager component in the app view switch. This keeps navigation ownership in `App.tsx` and prevents a second nested router. Keep it in the primary workspace list if users must reach it quickly; avoid burying an operational control surface under “Other portfolio views.”

### Chat intent, API calls, and state ownership

`frontend/src/components/AgentChat.tsx` (`SHA256 A983E89F288387807AE1B7C856806B4D5BB7829BB442376854A8D70E9ED2D720`) defines a closed `ControlOperation` union (`chat`, `help`, `list_agents`, `draft_agent`, `navigate`) and a closed `ExistingView` union (lines 24–29). `inferIntent` is a deterministic client-side regex router; it recognizes help, agent listing, agent drafting, and navigation to enumerated existing views, with all other prompts falling back to ordinary chat (lines 44–75). No capability-management operation is currently represented.

Chat owns local React state for agent inventory/loading, selected agent, current messages, conversation list/active conversation/library mode, draft/model loading, and request/error status (lines 79–99; lifecycle and persistence calls around 102–205). It creates/loads conversation records via `/api/conversations`, sends selected-agent turns to `/api/agents/{id}/chat`, and sends assistant turns to `/api/chat/control` with the inferred operation (lines 235–267). It refreshes inventory through `/api/agents/list` (around lines 102–113), and the draft card calls `/api/agents/create` only from the explicit Create action (lines 313–330).

**Integration point:** add explicit, typed capability intents and a server-returned proposal card. Chat may ask for inventory/status or propose a change, but should not interpret model prose as an executable function call. Keep proposal details and review/cancel state in the current chat UI; after an authoritative mutation response, refresh the manager from the backend API rather than maintaining a separate client-side capability catalog. If the capability draft must survive navigation/reload, persist it server-side as a proposal resource with identity/revision/expiry and reload it; component state alone will be lost when the chat view unmounts.

### Existing review UI is inspection-only

`frontend/src/features/decision-inspector/actions/ActionReview.tsx` (`SHA256 9CA57134B5AF68BFB7DE4293FCFD55B514C1A1B4DC37AFB5DE9FDE0C4EB2603F`) renders an action lifecycle review from supplied evidence data, labels it “Inspection only,” and keeps Approve/Reject/Request evidence buttons disabled (lines 53–103, 109–121). `frontend/src/contracts/action/action.ts` (`SHA256 E235A43E16B706695A325B91BC955C88AD5EBABA887A2922C84E3BDF5B7872BD`) models capability, eligibility, authorization, availability, execution, and receipt-link states separately (lines 1–55); validation rejects success without an explicit call and a matched receipt (lines 64–82). Its adapter is explicitly display-only (`frontend/src/adapters/action/agentRun.ts`, `SHA256 15C06F7967B34C29C109E6A85ED52189157191D867D4D170C89018E37EFDE8DC`, line 70 onward).

**Recommendation:** reuse the lifecycle vocabulary and visual separation, not this artifact-bound read-only component as the manager's authority or mutation layer. A manager needs a live API-backed catalog/status view, while review cards should be bound to immutable proposal IDs, exact capability/version, requested scope/effect, requester, expiry, and backend decision state. Keep lifecycle stages visible but compact: `registered → available → eligible → authorization required/authorized → executed → verified`; unknown/unavailable states should remain explicit.

### Provider settings are an adjacent, distinct control

`frontend/src/components/ProviderSettings.tsx` (`SHA256 169A7DF3AC23D88DB0B4741A13EBB1D88A462F58A78F0423C5E0A3EDF1D7A4B6`) calls provider status, model listing, config-save, and verify endpoints (respectively `/api/providers/ollama/status`, `/models`, `/config`, `/verify`; lines 46, 65, 90, 112). Its provider/model controls describe connection and model availability, not application action capabilities. Do not conflate “Ollama ready” or model listed with a registered/executable tool.

## Authority boundary: what the frontend cannot grant

The current contract `docs/agent-chat-control/contracts/CONTROL_PLANE_V1.md` (`SHA256 98DE492E09BECFDFF66DA36922BF16E533A5FEF6F7F5440452D1E207E52EAD67`) says the chat only provides text, lists agents, drafts agents, and navigates; it may not call arbitrary APIs/tools inferred from model output (lines 26–32). It also says app effects and job dispatch are unavailable implicitly, and execution requires a registered capability, backend authority/permit path, and traceable result (lines 34–50). Bounded project reading is read-only and turn-scoped; it cannot write or execute commands (lines 52–54). The AgentChat UI likewise says the read option cannot write files or run jobs (near line 398).

Therefore UI controls, chat instructions, a model response, local React state, a listed tool ID, or disabled/enabled buttons cannot themselves register a capability, make it eligible, authorize it, create a permit, execute it, or prove an effect. Every transition that matters must be checked and recorded by the backend authority and returned with a stable decision/receipt reference. Frontend must display server-confirmed state; it must not synthesize `authorized`, `executed`, or `verified` from user clicks or LLM text.

## Low-cognitive-load MVP flow

1. **Capability Manager view:** list registered capabilities with one-line purpose, owner, version, effect class, current availability, eligibility reason, and whether human authorization is required. Start read-only.
2. **Chat request:** user asks to enable/configure/use a named capability; assistant can identify the catalog item and prepare a typed proposal. Unknown capability names stay unresolved proposals; no fuzzy match should silently select an executable item.
3. **Review card:** show the exact capability/version, requested scope, data/effect, duration, and risk in plain language. Provide `Cancel` and an explicit backend proposal/authorization action only when that operation is supported. Default is no permission.
4. **Server result:** refresh catalog/state and show the returned transition and reference. Distinguish “registered” from “available,” “eligible,” “authorized,” “executed,” and “verified.” To prove execution, show a matched backend receipt, not merely a success message.
5. **Chat follow-up:** direct run requests to a separately governed execution request. Until W02/W04 establish a live backend contract, the chat should state execution unavailable and offer the manager/status view.

## Handoff to W04

- Preserve root `App.tsx` as the sole view router; capability manager should be one new root-level view, deep-linkable from chat through a fixed enum.
- Keep provider/model availability separate from action-capability state.
- Reuse lifecycle labels/schema concepts from the Inspector, but keep the manager live and backend-owned; current `ActionReview` is display-only and its buttons are intentionally disabled.
- Chat should make typed requests/proposals; human decision is a separate explicit step, and backend authority must revalidate on every transition.
- Source audit only. Backend registration/persistence/permit/gateway behavior must be established by W02 before defining clickable authorization/execution controls.

## Verification boundary

- Read-only inspection against the HEAD and source hashes listed above.
- No tests, build, browser interaction, API probe, or live capability operation was run (`NOT_RUN`).
- No source files were edited. This report is an integration map/recommendation, not evidence that any capability manager exists or that execution can be authorized.

