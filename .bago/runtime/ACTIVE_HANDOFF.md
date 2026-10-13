# Active handoff

Goal: `.bago/goals/bago5-chat-cognition/goal.md`

Status: `VALIDATED` for the ADL implementation and mocked API/UI behavior; live provider/model inference is `NOT_RUN` because configured Ollama secure credential storage is unavailable.

ADL candidate: local branch `codex/adl-directory-duplicate-scan-20261013`, base and current HEAD `ac8bdf1b19f587a5ae553f13e846c7d41e1e507b`; all changes remain uncommitted and unpublished. This same dirty candidate includes the preceding directory duplicate scanner implementation and its closure artifacts; those changes were preserved.

BAGO5 source: `E:\proyectos curriculum\BAGO5_DEV\BAGO5.0`, HEAD `aa383c8266935c2f346a1464ad3200f055731c16`. The source tree is mid-relocation; the native cognition/ontology/prediction/plasticity files read were compared with their committed blobs and left untouched. ADL has no BAGO5 runtime dependency.

ADL chat offers a one-message BAGO5-inspired attention mode for both the app assistant and selected agents. Baseline remains default. The bounded, deterministic lexical cue graph selects up to six focus nodes over at most two hops and appends selected strategy guidance to the actual system prompt. The response displays mode/focus/score/limits and stores a local trace containing no prompt or response text. Prediction/plasticity are excluded because open-ended model output has no independent BAGO5 station oracle or verified outcome evidence.

Verification: 232 full-suite tests, focused 13, frontend build, README generation/check and Python compile passed. Port 8081 serves `index-32e590e5.js` and `index-6167e5c8.css`; Playwright confirmed the toggle and a network-mocked request/response renders the BAGO5 focus panel. API tests verified both app assistant and selected-agent prompts and trace metadata. No actual Ollama inference ran: `/api/providers/ollama/status` reports `state=error`, `Secure credential storage is unavailable.` Full details and limitations are in `.bago/goals/bago5-chat-cognition/evidence/VERIFICATION.md`.
