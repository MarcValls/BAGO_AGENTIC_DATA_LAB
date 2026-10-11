# Manual frontend audit - Codex CLI

You are auditing the BAGO Agentic Data Lab frontend snapshot in this directory.

## Objective

Perform a read-only source audit of the React frontend and the API/WebSocket contracts it consumes. Focus on correctness, user-visible states, accessibility, security boundaries, and runtime compatibility. The backend source is included only to establish the authoritative route and validation behavior.

## Rules

- Do not modify application source, configuration, package manifests, or the included backend.
- Do not run tests, builds, provider calls, or any action that sends a credential.
- Do not claim browser/runtime behavior as verified from source inspection.
- Treat the current provider state as `not_configured`; no API key is included.
- Distinguish confirmed defects from risks/questions. Do not infer that an endpoint works merely because the UI calls it.
- Keep findings concise and actionable. Every finding needs severity (P0/P1/P2), affected file and line(s), evidence, user impact, and a recommended correction.

## Audit scope

1. `frontend/src/App.tsx` and `App.css`: chat-first navigation, other portfolio views, loading/error and artifact routing.
2. `frontend/src/components/AgentChat.tsx` and `.css`: assistant intent routing, agent inventory, draft generation, editable review, backend-confirmed model selection, explicit create/cancel, agent chat, request errors and empty/loading states.
3. `frontend/src/components/ProviderSettings.tsx` and `.css`: API-key vs local CLI choice, secret handling, status/model/verification flows, container/host states.
4. Remaining components and `frontend/src/features/decision-inspector/`: API use, route integration, accessibility, and unsupported/stale UI behavior.
5. `src/api/server.py` and `src/providers/ollama.py`: only to check the actual route methods, payload shapes, server-side validation, credential boundaries, and WebSocket origin checks that the UI relies on.
6. `scripts/run-local-ui.ps1`: port selection and frontend WebSocket compatibility.

## Known review prompts (verify these independently)

- `AgentRunner.tsx` and `Control.tsx` construct WebSocket URLs with port 8080, while the local launcher can select a later port. Determine whether this breaks those views on a dynamically selected port.
- The Runner UI expects `done`/success messages, while the backend intentionally fails closed for `/ws/agents/run`. Check whether displayed status and error handling match the actual server protocol.
- Check that all create paths require a confirmed model and that draft generation does not persist an agent before confirmation.
- Check whether the UI handles backend error shapes consistently, including `detail.message`.
- Review provider secrets for accidental persistence, echo, logging, or inclusion in chat/history. Do not enter or invent a secret.
- Check loading, empty, unavailable, error, cancellation, keyboard, focus, labels, narrow viewport, and stale-selection states.

## API inventory

Consult `FRONTEND_AUDIT_HANDOFF.md` for the complete set of endpoints called by the UI. Treat route declarations and request models in `src/api/server.py` as the source of truth for this snapshot.

## Output

Create only `AUDIT_REPORT.md` in this extracted pack with:

- Candidate/scope summary and explicit evidence boundary.
- Findings grouped P0, P1, P2; if none, say none found within reviewed scope.
- For each finding: file:line, evidence, user impact, recommendation, and confidence.
- Short review notes for navigation, provider setup, agent creation, agent chat, Inspector, legacy Runner/Control, accessibility, and error states.
- `NOT_RUN` list for browser, tests, builds, model/provider calls, and anything else not executed.
- Questions/limitations where the source snapshot is insufficient.

Do not mark the product validated or claim a clean bill of health. This is a manual source audit of a packaged snapshot only.
