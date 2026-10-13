# R04 independent placement verification

Verdict: PASS for the frozen chat/run/settings placement acceptance. P0=0, P1=0, P2=0 observed. This is a bounded placement review, not a certification of every pre-existing Inspector or agent executor behavior.

Verified actual live runtime http://127.0.0.1:8081 from main checkout C:\Users\AMTEC_Terminal_1º\BAGO_AGENTIC_DATA_LAB. Candidate implementation handoffs R02 and R03 read independently. Initial browser used index-10e3c7f0.js. After concurrent unrelated provider rebuild, a fresh unmocked final browser loaded index-fa31b7eb.js and the placement persisted. No implementation source was changed by R04.

## PASS evidence

- Chat has exactly one composer checkbox: exact project file authorization for one message. No directory scanner or cognition checkbox in the composer. Header opens Cognition & context Settings. Baseline defaults; BAGO5 setting survives reload.
- Mocked model HTTP requests captured BAGO5 cognitive_mode for both /api/chat/control and /api/agents/agent_32e8de8d36064f09b0b5e105375047de/chat. Ordinary requests have neither workspace_read_authorization_id nor workspace_scan_authorization_id. Both returned intentional 503s and displayed explicit failure. Model inference was not performed.
- Sidebar has Agent Runs and no Control destination. Agent Runs renders the local bounded scanner. Without path and consent, Scan is disabled. A path alone remains disabled. Consent enables the form, directory edit clears it, and an attempted mocked failure also clears it. Simulated 503 scan failure displays an alert without a completed report or receipt. Generic profiles all have disabled Run unavailable buttons.
- Real /api/chat/context binds workspace_root to main checkout; conversation path is the actual C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO\AgenticDataLab\conversations\library.sqlite3. Metadata presents presence, bounded cognition settings and description; no contents or source text. UI explicitly says viewing locations does not authorize content sending and that general/cross-project memory engines are not connected.
- Intercepted context 500 displays explicit error with no stale path list. Retry into empty paths displays an explicit empty state.
- Denied localStorage getItem falls back to Baseline. Denied setItem shows explicit preference warning while BAGO5 remains effective for current page; reload returns to Baseline.
- Keyboard focus on chat cognition header followed by Enter opens Settings. Standard radios and close button are accessible. Screenshots visually inspected: r04-agent-runs.png and r04-final-settings.png.
- Final fresh unmocked console: zero errors and zero warnings. One existing verbose password-form username accessibility diagnostic. During fault injections only expected resource errors appeared: 503 assistant, agent and scan; 500 context. No application exception was observed.

## Scope and NOT_RUN

- Live model inference: NOT_RUN because provider was unavailable; all model/scan mutation requests were intercepted. No real conversation or scan write was made by the browser review.
- Browser dynamic Loading assertion: NOT_RUN to completion; the short delay raced the assertion. Source has explicit Loading backend context locations state. Error/retry/empty were independently verified afterwards. No false PASS recorded for this assertion.
- Fresh real successful directory scan: NOT_RUN in R04; existing backend scan tests and root full-suite checks own that coverage.
- Exact-file consumption API revalidation, expired/revoked authorization, mismatched receipt/action/run, unsupported claim, stale/contradictory evidence and missing provenance: NOT_RUN as new dynamic adversarial scenarios because the mission changed placement and metadata rather than those existing execution/Inspector contracts. Single-use reset remains observable in source at AgentChat.tsx:434; source scope selection is untouched.
- Failed tool/run representation and unauthorized scan: exercised through disabled UI and mocked failure/no report. Full semantic scanner authorization security is covered outside this bounded browser review.

Reproducible browser interaction scripts: r04-browser.cjs (normal placement and mocked failures), r04-errors.cjs / r04-states.cjs (state attempts; do not infer that their entire timing-sensitive scripts completed). State fallback and final smoke commands were run directly through Playwright CLI and their returned PASS results are recorded above. All independent browser sessions closed.
