# Agent Evaluation Lab follow-up verification — 2026-10-15

## Snapshot

- Repository: `BAGO5_ADL`
- Branch: `main`
- HEAD at verification: `c7b8e2ded64d7f004e82a3a8bfd7891ce9b39490`
- The working tree contained task changes and pre-existing unrelated state. Test evidence is tied to this observed source snapshot, whose product/test file hashes are listed below; no commit was created.
- Follow-up mission: `ADL_AGENT_EVALUATION_TRACE_FAILURE_FOLLOWUP_20261015`.

## Verification results

| Check | Result | Evidence |
|---|---|---|
| Focused backend | PASS | `python -m pytest tests/test_agent_evaluation_lab.py tests/test_capability_manager.py tests/test_agent_chat_trace.py -q` → 29 passed, 1 Python 3.14/Pydantic-v1 compatibility warning. Includes deterministic LocalTrace persistence failure coverage using a local filesystem failure fixture. |
| Frontend UI | PASS | `npm run test:ui` → 16 passed, 0 failed, including 5 API-client assertions and rendered failure/trace states. |
| Frontend production build | PASS | `npm run build` → TypeScript build and Vite production bundle succeeded; 121 modules transformed. Existing Vite deprecation notices were emitted. |
| Full repository suite / README generation | PASS | `python scripts/generate_dynamic_readme.py` → README generated after 249 tests passed. |
| Generated README consistency | PASS | `python scripts/generate_dynamic_readme.py --check --skip-tests` → README verified; suite NOT_RUN by this command (249 cases collected). |
| Whitespace check | PASS | `git diff --check`. |
| Team coordination | PASS | W01–W03 handoffs independently verified by `teamctl`; W04 terminal verification recorded after this evidence was materialized. |

## Product behavior proved

- A failed LocalTrace filesystem persistence is returned and stored as `trace_state=local_trace_failed`, with `trace_local_saved=false`. Its trace ID is explicitly provisional and the UI labels the trace unsaved with lookup unavailable.
- The run remains persisted locally and its GET result agrees with the POST result; the test forbids job creation and stubs provider discovery/chat, so it makes no network or model call.
- Provider/execution errors render as ERROR and remain distinct from deterministic assertion failures.
- API-client tests now load the actual TSX module using the declared Vite tooling; no package dependency was added.

## Product objective and limits

The product is a local, reviewable ADL Agent Evaluation Lab: define small versioned prompt suites with authored deterministic checks, choose an existing agent and available Ollama model, explicitly launch runs, persist local suite/history and per-case outcomes, and inspect effective agent/model, duration, and trace identity. It is not an LLM-as-judge or general answer-quality score.

The follow-up did not make a live Ollama request. The only genuine-provider evidence remains the historical run from 2026-10-10, which predates final detector hardening. Jaeger projection for an Evaluation Lab run and frontend lint remain NOT_RUN. Accordingly implementation is EXECUTED and verification remains PARTIAL; this evidence does not claim every acceptance criterion is freshly verified.

## Source fingerprints

SHA-256 at verification time:

```text
src/evaluation/agent_lab.py ecfc3baf02fa0d4bd9bbf5cb3643820ad6f192b5a18127339fc465b1cceccabc
src/api/server.py e6c9d2588a44baf57a523ada8b3506da7d1460ae41b1e25030b2938c132df569
tests/test_agent_evaluation_lab.py 5f212046aaa6dbd72ddfc36bdfed0af39875a2fc3600b51645155823d1e2ebaf
frontend/src/components/AgentEvaluationLab.tsx 0aac8d92ec8ccf7701c8f11a0d1b9741995d3c5d526dc58d687cbaeec46a7ddb
frontend/tests/ui/agent-evaluation-lab/agent-evaluation-lab.test.mjs 94a6cd9d35bac45b7a8bc1a34f1ae561f78db1ef15a92bfe066a6fcb8e521da1
frontend/tests/ui/agent-evaluation-lab/rendered.test.mjs 04454f0f145d0df26b67615f79993040a1d160120ba2c0217f6c3e3f4d4d9277
README.md d3fe67c98594716bdcc3552565bff52b0c8118801646f9387acd292094e03953
```
