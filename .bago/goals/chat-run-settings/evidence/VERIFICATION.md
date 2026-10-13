# Chat, task runs and persistent settings - final evidence

Implemented in isolated worktree from freshly fetched origin/main d760c5aea9b678ee1f723b6825f79f1f055de7be; that base already contains b5512e1. Applied the task delta to live main HEAD 4e6673a9f5c26ccccf24dc09739702b65d78ca4c only after clean-worktree and affected-file equality checks. No checkout, reset, commit or publish of main occurred. The HEAD and existing local commits were preserved. Exact task source hashes are in source_snapshot.json, and all task implementation sources match between isolated candidate and live root.

Chat has only exact-file one-use permission; persistent baseline/BAGO5 mode is configured in Settings and visible in the header. Agent Runs hosts the existing local directory duplicate scanner with source scope, one-use authorization, findings and trace. Generic agent profile execution remains unavailable. Control has no sidebar item; legacy control navigation maps to Agent Runs.

Settings reports actual workspace/context/handoff/state, conversation-database and cognition-trace locations without reading their contents, opening the database, creating stores or granting reads. Path relocation is not implemented; paths are read-only metadata. Cognition preference persists in the browser, with explicit ephemeral fallback if storage is unavailable.

Checks executed:
- R03: focused metadata tests -> 2 PASS, including no content reads, storage creation, database connection or secret exposure.
- R02: npm ci and npm run build -> PASS; final isolated build index-10e3c7f0.js / index-31081d7f.css.
- Live main: python scripts/generate_dynamic_readme.py -> README generado: 234 tests; python scripts/generate_dynamic_readme.py --check --skip-tests -> README verificado (234 tests).
- git diff --check -> PASS on candidate and live main, then repeated after final evidence/handoff.
- Runtime: restarted only identified PID 42576 with its existing Python311 executable and root, new PID39304, loopback8081 host mode. Health ok; /api/chat/context reports actual live root.
- During verification, unrelated ProviderSettings.tsx/.css edits and a main frontend rebuild occurred. These edits and their generated .build artifacts were preserved. Final served index-fa31b7eb.js / index-58c4d3ee.css bytes match disk SHA256; independent review reloaded this final bundle and confirmed placement.
- R04 independent browser review -> PASS, P0=0/P1=0/P2=0 observed, final console0 errors/0 warnings. Checks include both mocked chat request modes, persistence/reload, context real/error/retry/empty, storage denial, scan consent reset and failed scan without receipt, generic execution disabled, keyboard Settings access. See R04-review.md for scope, scripts and screenshots.

NOT_RUN: real model inference (configured secure credential storage unavailable); R04 real successful scan (existing scanner tests own success coverage); fleeting browser loading-state timing assertion; unrelated pre-existing Inspector adversarial cases. No real model requests or scan writes were made by the browser review. This validation covers placement and metadata, not generalized agent execution or model behavior.

All five mission items and W12 terminal gate must be DONE with teamctl verify PASS; state and handoffs are in this goal's .bago/team/runtime.
