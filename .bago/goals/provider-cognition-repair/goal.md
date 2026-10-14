# Provider, BAGO5 cognition and chat layout repair

Status: **VALIDATED** for the requested behavior, live layout and placement.

Acceptance: the actual 8081 Python runtime supports secure Ollama credential lookup; BAGO5 experimental chat requests reach the saved Ollama model; provider status reflects successful inference or an authentication failure; Chat fills its available viewport; Agent profiles stay in Agent Runs and duplicate page title is removed. Do not expose credentials or equate chat inference with governed agent execution.

Base and final identity: main HEAD `18b07ac9088ecf7ba32fb4c39c6112f1bb0eb631`, unchanged; source edits are uncommitted in that checkout. A fetched isolated candidate supplied backend/UI repair. The user refreshed authentication in Provider Settings; the local provider configuration file remains modified and was preserved. No credential value was recorded.

Execution: installed pinned `keyring==25.6.0` into the Python311 interpreter serving port8081; Windows Vault backend confirmed. A real BAGO5 turn in conversation `conv_6b0896b186234333ba28fb1706ab2ee8` returned `ADL BAGO5 conectado` using `gemma4:31b`. Provider status moved from `configured_unverified` to `ready`. Trace `trace-2c53f77c1f3d4b75` records bounded prompt focus metadata, not hidden model reasoning.

UI: `.app-view--chat > .control-chat > .control-chat-main` now expands to the remaining flex width. The redundant Agent Runs page heading is removed; `Agent profiles` and its existing profile list stay in place below the duplicate scanner.

Verification: frontend production build PASS; Playwright live measurements at 1920x1080,1280x800 and800x700 show chat filling the available width; ten profiles remain in Agent Runs; served JS/CSS SHA-256 match files on disk. Independent R04 PASS with P0=0, P1=0. Full repository suite PASS:247 tests via `python scripts/generate_dynamic_readme.py`. README check PASS: `python scripts/generate_dynamic_readme.py --check --skip-tests`. See `evidence/R04-review.md` and `.bago/team/runtime/handoffs/R02.json`, `R03.json`, `R04.json` for source-bound evidence.

Residual P2: the focus chips on a persisted BAGO5 reply expose scores without human-readable labels. The cognition profile and trace remain visible; this does not block the requested provider, response, layout or placement acceptance. General agent run execution remains unavailable and disabled.
