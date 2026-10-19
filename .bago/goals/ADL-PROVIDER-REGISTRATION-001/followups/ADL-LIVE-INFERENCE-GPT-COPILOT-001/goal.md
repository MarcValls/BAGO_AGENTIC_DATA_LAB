# OpenAI Platform and GitHub Copilot live agent inference

## Objective

Integrate OpenAI Platform and GitHub Copilot registrations with saved-agent chat
and the existing BER Agent Runner. Keep other provider registrations explicitly
marked as not integrated.

## Acceptance criteria

- Agent profiles can select OpenAI Platform or GitHub Copilot and their saved
  model; backend rejects a model that does not match the provider registration.
- Agent chat and Agent Runner dispatch to the saved provider.
- Copilot tool calls can only become typed proposals consumed by the existing
  BER approval flow; the provider SDK does not execute application effects.
- Provider settings distinguish integration from live verification and offer a
  user-triggered minimal inference check with usage disclosure.
- Credentials remain write-only in the UI and server logs/errors.

## Scope and limits

Supported registration IDs: `openai-platform` and `github-copilot`. Ollama keeps
its existing path. Other registrations, including Codex CLI, remain separate
and unsupported by this runtime. No live provider request is run during code
implementation. A live check may incur small provider usage and must be invoked
by the user from Provider Settings.

## Status

`VERIFIED` for local integration and regression coverage. The final README
generation passed 322 Python tests; its consistency check passed. Four rendered
component tests and the frontend production build passed. The actual ADL Python
environment now has the pinned Copilot SDK and passed 20 provider checks.

The server at `http://127.0.0.1:8080` was reloaded and its health, provider
inventory, HTML and linked assets were observed with read-only HTTP requests.
Both new providers report `not_configured` and `chat_and_agent_runner`.
External inference is `NOT_RUN` until the user registers a provider and invokes
the disclosed live check. Browser visual observation is `NOT_RUN` because no
browser was connected. Do not infer external `VALIDATED`/`DEMONSTRABLE` from the
simulated transport checks.

See `evidence/VERIFICATION.md`, `evidence/runtime.json` and
`evidence/candidate.json` for commands, results, scope and exact content hashes.
