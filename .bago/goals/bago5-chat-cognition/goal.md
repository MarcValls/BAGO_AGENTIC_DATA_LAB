# Goal: expose a bounded BAGO5-inspired cognitive context in ADL chat

## Objective

Adapt selected native BAGO5 cognition/attention concepts to ADL's app-assistant and selected-agent model chats so a user can compare the default prompt with a visibly instrumented BAGO5-inspired prompt mode.

## Acceptance criteria

- The exact BAGO5 source snapshot and relevant source hashes are recorded; BAGO5 remains unchanged.
- ADL adds no runtime import/dependency on BAGO5.
- Baseline is the default. A one-message control enables bounded BAGO5-inspired attention for both assistant and selected-agent chat.
- The deterministic focus changes the actual model system prompt and is visible and persisted with the assistant response.
- Focus selection is bounded and deterministic; local trace evidence stores focus metadata, not the user message or model answer.
- UI describes the layer as experimental prompt guidance, not hidden model reasoning.
- No automatic plasticity or truth score is applied to free-form model answers.
- Focused tests, full suite, frontend build, generated README and consistency check pass; final diff and served UI are inspected.

## Source boundary

Reference: `E:\proyectos curriculum\BAGO5_DEV\BAGO5.0`, BAGO5 HEAD `aa383c8266935c2f346a1464ad3200f055731c16`. The source tree is undergoing relocation; the four native files inspected hash to the same Git blobs as their prior committed paths at that HEAD. See `evidence/VERIFICATION.md` for hashes and reuse boundaries.

## Status

`VALIDATED` for ADL implementation and mocked API/UI behavior. Live-model behavior remains `NOT_RUN` because the configured provider reports unavailable secure credential storage.

## ADL candidate

Branch `codex/adl-directory-duplicate-scan-20261013`, based at `ac8bdf1b19f587a5ae553f13e846c7d41e1e507b`. This continues in the already dirty candidate from the preceding ADL request; existing changes were preserved.
