# W12 terminal closure

## Acceptance

- BAGO5 experimental chat must send a turn to the selected provider and show the persisted model response/cognition metadata.
- Provider readiness must reflect successful inference and authentication failure accurately.
- Chat must occupy the available content width.
- Agent profiles must remain under Agent Runs; redundant page-title text must be removed.
- Keep user provider configuration private and preserve unrelated local changes.

## Execution and evidence

- Pinned dependency `keyring==25.6.0` is installed in the actual Python311 runtime. The Windows Vault backend is available there.
- At 2026-10-13 09:11 Madrid, BAGO5 sent `Responde exactamente: ADL BAGO5 conectado` through the selected Ollama model `gemma4:31b`; the saved response was `ADL BAGO5 conectado`. Provider status is `ready`. Conversation `conv_6b0896b186234333ba28fb1706ab2ee8`; cognition trace `trace-2c53f77c1f3d4b75`.
- The chat main panel now fills its flex container. Live measurements at 1920x1080, 1280x800 and 800x700 show the main panel reaching the right edge without horizontal overflow.
- Live Agent Runs view retains all ten profiles in the existing panel under the scanner. The duplicate `Agent Runs` heading is absent; the `Agent profiles` subheading remains.
- Frontend build: PASS; actual HTTP JS/CSS asset digests match disk. R04 independent review: PASS, P0=0, P1=0; console errors/warnings=0. Full generated-README run: PASS, 247 tests. README consistency check: PASS, 247 tests.
- No credential value is present in this evidence. Main HEAD remains `18b07ac9088ecf7ba32fb4c39c6112f1bb0eb631`; changes are uncommitted and the local provider settings change is preserved.

## Residual

R04 recorded one P2: stored BAGO5 focus scores lack human-readable labels. This is non-blocking for the stated acceptance. Generic agent-run execution remains unavailable and disabled.

Detailed independent measurements, source/assets fingerprints, screenshots and repeatable browser review: `R04-review.md`, `r04-chat-1920.png`, `r04-runs-1920.png`, `r04-live.cjs`.
