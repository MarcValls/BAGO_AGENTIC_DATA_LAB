# BAGO5 cognitive context in ADL chat - verification record

## Candidate and source binding

- ADL repository: `BAGO_AGENTIC_DATA_LAB`, branch `codex/adl-directory-duplicate-scan-20261013`, candidate HEAD `ac8bdf1b19f587a5ae553f13e846c7d41e1e507b`; implementation changes remain uncommitted in the worktree alongside the preceding directory-scan work.
- BAGO5 source: `E:\proyectos curriculum\BAGO5_DEV\BAGO5.0`, HEAD `aa383c8266935c2f346a1464ad3200f055731c16` (`Refactor code structure for improved readability and maintainability`). The source tree currently represents a relocation with uncommitted deletes/additions. For each file below, current bytes were checked with `git hash-object` against the old committed path at that HEAD; the Git blobs match.
- Source SHA-256: `native/bago5/cognition.py` `dafe7c7a93a1b0efeb9249ff4d59e5289b30daa01fa8b27c860a48b2a0d2ba0b`; `ontology.py` `7c5b850037b28c10b1434ff220c7d1bf6479573e984b658da05e1b5b0e9af7fc`; `prediction.py` `dd2124b3c63dbec7f495b7de9aeb9da24e96d5ac617341a78bf7ac43bee28651`; `plasticity.py` `84625ed1bb18238625f4c823be466d67879b058baab527ee0546005cba0907ba`.
- No files in BAGO5 were changed. ADL contains no runtime import from the BAGO5 workspace.

## Adaptation

- `src/cognition/bago5_chat.py` adapts BAGO5's typed semantic units, bounded cognitive workspace, weighted activation and attention ranking into a deterministic lexical cue graph for free-form chat. The top six activations, two-hop propagation, and 32-expansion budget are fixed and visible. Selected strategy guidance is appended to the model system prompt.
- The chat composer applies the experimental context to the next model response only. Baseline stays the default. Both the ADL assistant chat and selected-agent chat accept the mode. Each assistant message displays its mode, focus cue labels and scores, profile limits, and local trace ID.
- Cognitive traces persist focus/mode metadata only; tests confirm they omit the user message and model answer. Conversation messages remain stored by the existing conversation library as before.
- BAGO5 prediction/plasticity are not applied to open-ended model answers. The BAGO5 reference requires an independent station oracle for prediction comparison and verified evidence for plasticity; a model's free-form answer is not either of those. No truth score or learned weight is inferred from chat output.

## Verification performed

- Focused: `python -m pytest tests/test_bago5_chat_cognition.py tests/test_agent_chat_trace.py tests/test_conversation_library.py -q -p no:cacheprovider --basetemp=.pytest-tmp-cognition` -> `13 passed`, with one existing Python 3.14/Pydantic V1 warning.
- Full suite and generated README: `python scripts/generate_dynamic_readme.py` -> `README generado: 232 tests`.
- README consistency: `python scripts/generate_dynamic_readme.py --check --skip-tests` -> `README verificado (232 tests)`.
- Frontend: `npm run build` -> TypeScript and Vite pass; final assets `/assets/index-32e590e5.js` and `/assets/index-6167e5c8.css`.
- Python syntax: `python -m py_compile src/cognition/bago5_chat.py src/api/server.py` -> passed.
- Live runtime: port 8081 was restarted after confirming its previous process command and repository working directory. `/api/health` returns `ok`; served HTML references the final assets.
- Live chat provider status: `ollama-cloud`, model `gemma4:31b`, state `error`, message `Secure credential storage is unavailable.` A real provider/model inference is therefore `NOT_RUN`; no prompt was sent to Ollama Cloud.
- Rendered browser: Playwright at 8081 shows the per-turn BAGO5 checkbox, baseline-default text and bounded-context disclosure. A network-intercepted UI smoke test asserted the request carries `cognitive_mode=bago5` and rendered a mocked response with focus scores and trace ID. The mock did not call a model or write a conversation. Browser console reported zero errors and zero warnings; one unrelated verbose diagnostic referred to the existing chat password form.
- Focused mocked API tests verify prompt injection and trace persistence for assistant and selected-agent modes, plus baseline behavior.
- `git diff --check` -> passed on the final worktree after the evidence and handoff updates.

## Limits and next step

This feature guides model output through deterministic prompt cues; it does not expose model-internal reasoning or implement generalized semantic cognition. The cues are lexical and may miss or misclassify intent. Baseline comparison should use the same prompt in a fresh conversation because chat history can otherwise differ. To observe an actual provider response, configure working Ollama secure credential storage in the app's provider settings; do not place provider secrets in chat.
