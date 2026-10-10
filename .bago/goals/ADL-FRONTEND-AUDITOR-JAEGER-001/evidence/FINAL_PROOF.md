# Final proof: Frontend Auditor, P1-02 and Jaeger

**Candidate:** `codex/adl-agent-evaluation-lab-20261010`, base HEAD `1e4d9f930da1225ce61ce27def897f76d57a08fc`; working tree remains uncommitted.  
**Goal status:** `EXECUTED`; `VALIDATION PARTIAL`.

## What is now evidenced

1. **Real model-backed application audit.** The isolated candidate API used `POST /api/agents/create`, persisted an agent record named **Frontend Auditor** configured for `ollama-cloud` / `gemma4:31b`, then used `POST /api/agents/{agent_id}/chat` with request-scoped workspace-read enabled. The returned `source` is `ollama`; the provider response was not a fixture. Conversation storage is under the system temporary directory, and the created agent JSON and response are retained under `evidence/live-audit/`.

2. **The agent inspected the two relevant current source ranges.** The persisted chat references and LocalTrace record exactly:
   - `frontend/src/components/AgentRunner.tsx:1-250`
   - `src/api/server.py:1525-1550`

   The response concludes P1-02 is solved. Current UI evidence is at `AgentRunner.tsx:25`, `58-61`, `186-188`, and `214-218`: the execution flag is false, the code exits before WebSocket creation, the page explains execution is unavailable, and Run is disabled. The backend handler is at `server.py:1530-1546`: it emits `execution_unavailable`, states that no job was started or recorded, then closes with `1008`.

3. **The LocalTrace is projected into Jaeger and retrievable.** Local trace `trace-0dd06579c7774b63` has state `exported`. Jaeger API returned HTTP 200 for trace `f6bb1ebd27045f19f14495befc42835b`, with one `agent.chat` span for service `adl-frontend-auditor-proof`. The span tags match provider `ollama-cloud`, model `gemma4:31b`, the agent ID, run ID, LocalTrace ID, and both source ranges. Evidence: `live-audit/receipt.json`, `live-audit/traces/trace-0dd06579c7774b63.json`, `live-audit/jaeger_query.json`, and the real Jaeger UI capture `live-audit/jaeger-trace.png`.

4. **P1-02 behavior has an independent executable regression check.** `python -m pytest tests/test_agent_execution_unavailable.py tests/test_workspace_read.py tests/test_capability_manager.py tests/test_agent_evaluation_lab.py -q` passed **29 tests**. The new WebSocket test asserts the server rejects the run and confirms no job was started or recorded. Frontend `npm run test:ui` passed **14 tests**, including rendered edit/revision, error, model availability, explicit Run, result/LocalTrace/Jaeger identity, and disabled Agent Runner states. `npm run build` passed.

## Limits and remaining work

- This is a real isolated candidate API test, not a claim that the agent modified source or that an execution job ran. The model response correctly says its own tests/commands were `NOT_RUN`; the deterministic tests above were run separately afterward.
- `allow_workspace_read` grants the bounded reader for the turn; the tool does not technically allowlist exactly the two requested paths. This run's receipt records exactly those two reads. The reader remains read-only, bounded to 250 lines per read, 4 calls per turn, 3 tool rounds, and 256 KiB per file. Secret scanning is heuristic.
- The source-read receipt records path and range, not a content hash at read time. Current hashes are recorded in `live-audit/current_source_hashes.json` and match the independent review's later source read, but this is not a cryptographic contemporaneous read receipt.
- The LocalTrace has `cost_status=not_reported` and serializes top-level `cost_usd: 0.0`; no cost claim is made.
- `npm run lint` was attempted and failed before linting because `eslint` is not installed (`eslint` is not recognized). This is not a clean ESLint result.
- Python Ruff was also attempted; it reports three `F811` duplicate-definition findings in `src/api/server.py` (`export_agents`, `list_workflows`, `dispatch_workflow`). Those duplicates are present in the candidate base HEAD as well. Python compilation and `git diff --check` passed.
- A repeat from the isolated command-line context could not read the configured Windows credential store. The real live response above remains supported by the app receipt, SQLite response hash, LocalTrace, and Jaeger correlation. The local app on ports 8081/8084 reports Ollama `configured_unverified`; no secret was accessed or printed.
- No commit, push, merge, sync, or production execution occurred. The Frontend Auditor itself made no writes; the implementation/test work in this candidate was performed separately.
