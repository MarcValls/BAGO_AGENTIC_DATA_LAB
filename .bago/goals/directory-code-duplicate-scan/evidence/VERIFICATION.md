# Directory duplicate-code scan verification

## Candidate binding

- Repository: `BAGO_AGENTIC_DATA_LAB`
- Branch: `codex/adl-directory-duplicate-scan-20261013`
- Base and current HEAD: `ac8bdf1b19f587a5ae553f13e846c7d41e1e507b`; implementation is in the uncommitted working tree.
- Live API: `http://127.0.0.1:8081`, restarted from this repository after confirming listener PID 25236 used `python -m src.api.server` and this working directory; new process PID 29512.
- Served frontend: `/assets/index-8c0f2231.js` and `/assets/index-358e1eea.css`.

## Product result

- `frontend/src/components/Control.tsx` replaces demo orchestration with a real exact-directory, opt-in scanner. Control asks for one project-relative directory and explicit one-run read-only authorization, then shows counts, line references, SHA-256 manifest and local trace ID.
- The live scanner is deterministic and local. It detects repeated normalized five-line blocks across supported source extensions and normalized Python AST function-body structure. It does not execute code or send source contents to a model. Non-Python analysis is exact-block only.
- Directory grants are explicit, single-use, and bound to owner, conversation and revision. Traversal, hidden/runtime/secret folders and symlinks are excluded. Bounds: five authorized directories, 300 files, 256 KiB per file, 10 MiB and 150,000 source lines total, 20,000 lines per file, and 200 findings.
- The app assistant/selected agent tool loop can use the same scanner. The capability catalog reports `workspace.scan_duplicates` as `AVAILABLE/CONNECTED`. General `agent.run` remains fail-closed.
- Legacy demo APIs and test fixtures remain outside the Control view. Served bundle inspection confirms `Code duplicate scanner` is present and `Demo orchestration` / `Run demo` labels are absent.

## Verification performed

- Focused: `python -m pytest tests/test_team_monitor_api.py tests/test_code_duplicates.py tests/test_workspace_read.py tests/test_capability_manager.py tests/test_agent_chat_trace.py tests/test_agent_execution_unavailable.py -q -p no:cacheprovider --basetemp=.pytest-tmp-dup` -> `28 passed`, one Python 3.14/Pydantic V1 compatibility warning.
- Full suite and generated README: `python scripts/generate_dynamic_readme.py` -> `README generado: 226 tests`.
- README consistency: `python scripts/generate_dynamic_readme.py --check --skip-tests` -> `README verificado (226 tests)`.
- Frontend: `npm run build` -> TypeScript and Vite passed; final asset `/assets/index-8c0f2231.js`.
- Python syntax: `python -m py_compile src/agent_tools/code_duplicates.py src/api/server.py` -> passed.
- Whitespace: `git diff --check` -> passed before final evidence update; repeat after it.
- Live API: `/api/health` -> `{"status":"ok"}`; OpenAPI includes `POST /api/workspace-scan/run`; capability inventory lists `workspace.scan_duplicates` as `AVAILABLE/CONNECTED` with read-only bounds. Served HTML references the final JS and CSS assets.
- Rendered UI at 8081: Control view visibly presents “Code duplicate scanner”, exact project-relative directory input, unchecked one-run authorization, privacy text and scan bounds. A disposable fixture with two TypeScript files produced one exact repeated-block finding at lines 1-5, 2 scanned files, 10 scanned lines, a SHA-256 manifest, and a `local_only` trace ID. Screenshot: `%TEMP%\adl-control-scanner-final.png`. Playwright reported zero errors and zero warnings; one verbose browser accessibility diagnostic about the unrelated chat password form was emitted.
- The UI fixture directory, its generated trace file, and test conversation were cleaned after capture (conversation soft-deleted). No user-selected source directory was scanned; no model/provider request was made.
- Generated README test side effects containing `job_type=demo` were checked; no such job files remain.
- `python .bago/bin/bago.py verify` is `NOT_RUN`: this checkout has no `.bago/bin/bago.py` entrypoint.

## Limits

This is not semantic clone detection. Python AST normalization can produce false positives. Non-Python languages receive exact-block detection only. The generic Agent Runner, shell execution, writes and continuous monitoring remain unavailable.
