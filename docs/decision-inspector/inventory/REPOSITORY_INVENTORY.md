# Decision Inspector repository inventory

Snapshot time: 2026-10-08T16:52Z (UTC)
Repository: `C:\Users\AMTEC_Terminal_1º\BAGO_AGENTIC_DATA_LAB`
Branch: `real-world/openmetadata-28860-v1.1`
HEAD: `c87f619d4a167bca854de4bbda75e2574c076c75`
Working tree: pre-existing untracked frontend build outputs (`frontend/src/**/*.js`, Vite declarations/config output, TypeScript build info); pack install additions (`AGENTS.md`, `.agents/`, `.codex/`, `.codex-team-kit/`, `plugins/`); mission runtime `.codex-team/` created for this execution. No tracked source modifications were present at inventory time.

## Reuse map

| Need | Existing owner/source | Existing shape and consumer |
|---|---|---|
| Agent conclusion/run | `src/agent/governed_knowledge_agent.py` | `AgentRun` serializes run id, status, query, answer, citations, retrieval, proposals, decision receipts, tool receipts, and trace reference. |
| Evidence-bearing trace | `src/observability/local_trace.py` | Immutable `LocalTrace` and ordered `TraceEvent` contain trace/run/event ids, parent event, kind, status, attributes, and evidence references. `LocalTrace` is the evidence source of truth. |
| Trace transport | `src/observability/otel_bridge.py` | Projects local events to OTLP; Jaeger indexes/query-displays this projection. It does not grant authority or prove UI behavior. |
| Authorization and proposed tools | `src/agent/governed_knowledge_agent.py`, adapters under `src/adapters/` | Proposals are separately authorized and executed through permit-bearing adapter calls. UI must preserve these distinctions. |
| Execution receipt | `src/sandbox/receipt.py` | Immutable sandbox receipt records operation, status, filesystem/network mode, duration, argv/exit code, stdout/stderr hashes and evidence refs. |
| Evaluation | `src/evaluation/local_evals.py` | Evaluates a `LocalTrace`, returns checks, score, status and evidence references. |
| Artifact API | `src/api/server.py` | Read endpoints expose the existing JSON artifact bundle; WebSocket routes handle agent runs. Artifacts live in `demo_output/latest/`. |
| Existing UI | `frontend/src/App.tsx`, `frontend/src/components/*.tsx` | React/Vite dashboard already has Summary, Retrieval, Authorization, Trace and Evaluation tabs plus Builder, Runner, Chat, Control and Jobs. Trace and receipt content are currently displayed as raw event/JSON-oriented panels. |
| Browser trace evidence | `scripts/run_l15_otel_live_validation.py`, `infra/observability/docker-compose.yml` | Local Jaeger query service is available at port 16686; OTLP HTTP is port 4318. A current Jaeger query returned 15-span traces for `bago-agentic-data-lab`; it validates backend projection, not React rendering. |

The current frontend loads `/api/artifacts` through Vite's `/api -> http://localhost:8080` proxy. The API and frontend were not running at snapshot time. Existing JSON artifacts are present; `trace.json` has 15 events, a trace id and run id. No UI-linked Jaeger URL or UI-specific telemetry correlation was found in the inspected source.

## Boundary map

- User-visible scope for the requested UI work is `frontend/src/**`; contracts and architecture must fit the existing React/Vite build. The default mission's proposed `src/features/decision-inspector/**` paths do not match this repository and must be adapted through an explicit change request before implementation.
- Reuse current run/artifact, LocalTrace, authorization, permit, receipt and evaluation owners. Do not create a second source of truth for evidence or execution authority.
- Keep a conclusion/proposal visually separate from a permit, an executed effect and its receipt. Missing or stale evidence must remain visible as missing/stale.
- A Jaeger screenshot is evidence of the collector's trace projection only. A separate real browser screenshot is needed to show UI behavior; neither replaces LocalTrace or backend receipts.
- No external AWS/remote collector behavior is inferred from local fixtures. Jaeger is local and was already running (`bago-otel-jaeger-1`).
- Current Git state includes user-preexisting untracked build output from the prior work. Preserve it; do not stage or clean it as part of the UI work.

## Fingerprint sample

- `src/agent/governed_knowledge_agent.py`: `0290389a62c473a6df5e7b02817b435cad8a6ba1debdf08e23358a4ddf92d027`
- `src/observability/local_trace.py`: `7ad4b0a23f4dac5b2aa39c291bb6ebce3cfd97675529937bff048a4738bcf663`
- `src/observability/otel_bridge.py`: `29a1c9a82005ec5ec7ffb8c5ab489e1f220427657a53fb29b2f2737014b58b82`
- `src/sandbox/receipt.py`: `91fcc2f8eb2805cfe34b6f2dd0b8dcbad1e28f3ea5be906fdeaf7cfb4753e1eb`
- `src/api/server.py`: `459497b1130df1a2ead4d3e27538a6dac26529303c3bcf9ec69cb7b49d46b709`
- `frontend/src/App.tsx`: `5dbbd902e2005a65b317b5418981180f74e0464f2cbab465e181a9406a772389`
- `frontend/src/components/Trace.tsx`: `ec61738c26ec927253aac8a1f19c1f9e4b68779ea49ece45fa569ce324ac9f95`
- `frontend/src/components/Authorization.tsx`: `12962cf9b87f88960ad5fce58fd88819554014e85f715ef89f60df7da566c013`
- `demo_output/latest/trace.json`: `ef93a7da313c391f63f07f98c4d0a9498321d03b1d36234abb42788e2f0ae136`
