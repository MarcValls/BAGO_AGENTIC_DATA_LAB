# Independent review: Frontend Auditor and Jaeger evidence

**Review date:** 2026-10-10 (Europe/Madrid)  
**Candidate:** `codex/adl-agent-evaluation-lab-20261010`, HEAD `1e4d9f930da1225ce61ce27def897f76d57a08fc`  
**Scope:** Read-only inspection of `.goals/ADL-FRONTEND-AUDITOR-JAEGER-001` evidence and current P1-02 source. No Ollama request, code edit, job, or source mutation was performed by this reviewer.

## Supported claims

1. **A real application chat response is evidenced at the ADL persistence layer.** `receipt.json` records `POST /api/agents/{agent_id}/chat`, `provider_response_source=ollama`, provider `ollama-cloud`, model `gemma4:31b`, agent `agent_6b99c36e601c4a868213da340fdf47e5`, `workspace_read_enabled_for_turn=true`, conversation `conv_067d162a49ff47788ebdb2679fa71554`, and trace `trace-0dd06579c7774b63`. The isolated agent record shows the same provider/model and `tools=[]`.

2. **The response artifact matches the persisted assistant response.** Read-only SQLite access to the temporary conversation database found two messages for the recorded conversation. The assistant message's SHA-256 is `116ca426eadfc3cd32e770aa38a419744e031c672c009ee7d9a57f37150de092`, matching the receipt. After excluding the report title and its final newline, `agent_response.md` matches that persisted assistant message. The receipt records no secret-bearing response preview elsewhere.

3. **Two source reads are recorded for the audited turn.** The conversation reference and LocalTrace list exactly `frontend/src/components/AgentRunner.tsx:1-250` and `src/api/server.py:1525-1550`. Current code at those cited lines supports the core P1-02 UI claim: `AGENT_EXECUTION_AVAILABLE=false`, an early return before WebSocket creation, an unavailable status, and a disabled `Run unavailable` button. The backend handler at the cited current range emits `execution_unavailable` and closes with code `1008`. Current file hashes observed during this review are AgentRunner `D6BCFF256F3ED47C8B8EDA0DE657B0E2727D660EC452C389FFCCC147565A7DAB` and server `16FBAC9E16DB9878B30CEDDD633DE0C6CE68AD9F729A2DD5E6D4F61F7C91DD74`.

4. **The Jaeger projection is independently queryable and correlated.** A read-only GET to the Jaeger trace API returned HTTP 200 for `f6bb1ebd27045f19f14495befc42835b`, with one `agent.chat` span under service `adl-frontend-auditor-proof`. Its tags match LocalTrace ID `trace-0dd06579c7774b63`, run ID, agent ID, `ollama-cloud`, `gemma4:31b`, and the two source ranges. This independently supports one-span projection and trace/model/source correlation. It is an observability projection, not the answer or execution authority.

5. **The historical finding is mitigated in the current source snapshot at the UI/backend boundary.** The visible source no longer promises an executable Run action where this backend has no governed executor. The existing deterministic backend test `tests/test_agent_execution_unavailable.py` asserts `execution_unavailable` and the no-job message, but this reviewer did not run it. The chat response explicitly labels its own tests/commands as `NOT_RUN`.

## Gaps and limits

- **Exact-file authorization is not technically enforced.** The receipt proves the model read exactly the two requested paths on this turn. The server grants a request-scoped boolean that exposes the bounded `read_workspace_file` tool, but the helper accepts other readable project-relative files subject to path, sensitive-name, file-size and line-count checks. The two-file restriction is in the agent prompt and observed reads, not an allowlist enforced by the tool. Therefore “only these two files were authorized” is not supported; “these are the only two files recorded as read” is supported.

- **The read receipt is path/range-bound, not content-hash-bound.** HEAD is recorded, but the candidate source files are dirty and their hashes are absent from the live receipt, LocalTrace and Jaeger tags. The reviewer checked that the current files still contain the cited code, but the evidence does not cryptographically bind the bytes read at request time to the present dirty files.

- **No target Jaeger screenshot was found.** `jaeger_query.json` and this review's API GET prove queryability, but no screenshot for trace `f6bb1ebd27045f19f14495befc42835b` is in the goal evidence. The existing `output/playwright/jaeger-localtrace-04b58bb.png` depicts a different `agent.run` trace `04b58bb` with 15 spans, so it is not visual evidence for this Frontend Auditor `agent.chat` trace. The goal's `status.json` still says screenshot and Jaeger query are `NOT_RUN`; that status is stale relative to the receipts/API readback and should be reconciled by the goal owner.

- **No independent browser/UI observation for this run.** Static source and a backend test source support the P1-02 interpretation, but the live auditor turn did not run tests or commands and there is no contemporaneous rendered Agent Runner capture in this goal's evidence.

- **No current conversation API readback.** The SQLite conversation database is readable in `mode=ro` and its assistant response hash matches the receipt. GETs to the local API conversation route on ports 8080, 8081, and 8084 returned HTTP 404 during this review. Therefore the durable database evidence is verified; a live API response for this conversation is not currently available.

- **A cost representation conflicts with the “not reported” label.** The target LocalTrace event says `cost_status=not_reported`, and Jaeger includes that tag, but the enclosing LocalTrace JSON also serializes top-level `cost_usd: 0.0`. No provider charge is established by that zero; do not claim zero cost. Jaeger does not expose a cost tag in the queried span.

- **A second LocalTrace exists but is not the target receipt.** `trace-5a657ed775e9409b` records an earlier `agent.chat` with only the AgentRunner source and no matching Jaeger query in this evidence set. It must not be conflated with the completed two-source audit trace `trace-0dd06579c7774b63`.

- **The model identifier is `gemma4:31b`.** Evidence does not establish equivalence to any different cloud catalog identifier such as `gemma4:31b-cloud`.

## Evidence status

- **Verified by this reviewer:** response SHA against the read-only persisted assistant message; source references in the conversation and LocalTrace; current source lines/hashes; Jaeger GET and matching span tags; no target Jaeger screenshot in the goal evidence; current API route GETs returned 404.
- **Not run by this reviewer:** provider generation, backend tests, browser tests, job execution, source edits, or another Jaeger export. The previous live generation is supported by the app receipt/LocalTrace/database records, not repeated here.
- **Verdict:** The application-level live Ollama chat/read/source-citation path and Jaeger correlation are supported with bounded evidence. P1-02's UI mismatch is corrected in the current dirty source snapshot. Exact two-file authorization, content-hash binding at read time, contemporaneous UI proof, target Jaeger screenshot and zero-cost claims are not supported. Treat goal acceptance as **PARTIAL**, not fully closed.
