# ADL provider registration

## Objective

Redesign provider settings as a provider-centered registration page. Give each
provider its own selectable tab and show the registration method that applies
to it. Keep account registration, saved configuration, authentication, live
provider connectivity, and agent-run support as distinct states.

## Scope

- Reuse the provider setup patterns found in the local BAGO checkout without
  changing that checkout.
- Preserve the existing Ollama configuration and model-check workflow.
- Add registrations for the provider types already catalogued in
  `docs/provider-models-screen.md`, including OpenAI Codex CLI and GitHub
  Copilot CLI.
- Store credentials only through the operating-system credential store; return
  only whether a credential exists.
- Do not claim new provider registrations can run through ADL chat or agent
  execution until that runtime route is separately implemented.

## Capability demonstration route

1. Open Settings > Provider & models.
2. Select GitHub Copilot, choose CLI or token registration, and save.
3. Confirm ADL reports `configured_unverified`; it must not report live access.
4. Select OpenAI Codex and save its CLI registration independently.
5. Reload the page and confirm both registrations remain present and no secret
   value is returned to the browser.
6. Select Ollama and confirm its current status, model listing, save, and
   non-generative availability check remain available.

Expected observable: provider-specific registration controls and persisted
registration state, with secrets write-only and unsupported live execution
clearly identified.

## Candidate and limitations

- Baseline: `provider-registration-prechange-20261019` at
  `ed3a778378bdbf7e792a78849e80b821e3771fe7`.
- Baseline snapshot SHA-256:
  `1457caa6fbeca66f4aead0ba0dbcdea2ea602a4ed2d7281f41dd8c43afaf53e0`.
- BAGO source checkout was dirty at task entry and is reference-only.
- Live authentication and inference with Codex, GitHub Copilot, or other new
  providers are outside this registration increment.
- UI and backend checks will be recorded against the final candidate.
