# W01 - Candidate and scope binding

## Candidate snapshot
- Repository/worktree: `C:\Users\AMTEC_Terminal_1º\AppData\Local\Temp\BAGO_ADL_agent_evaluation_lab_20261010`
- Branch: `codex/adl-agent-evaluation-lab-20261010`
- HEAD: `1e4d9f930da1225ce61ce27def897f76d57a08fc`
- Existing pre-agent dirty state at spiral start: 79 status entries with `--untracked-files=all`; status stream SHA-256 `a51c2106aba3058675f93150add5cc73323f2ffe06bfa3a2c7c7a7d1496cf25e`.
- Existing tracked diff SHA-256: `89f1b5a642cdfd20b58df4ba7bf26991611488dd0e1afbdf6732ac439badfe83`.
- The user workspace has many existing changes, including chat, provider, capability, evaluation, trace, tests, and previous spiral state. They are preserved. This mission writes only its isolated goal/team-runtime records.

## Authority carried forward
- The conversation-library goal marks one-shot and signal-waiting agents `PROPOSED`, with signal source/event, actor identity, authorization, lifetime, idempotency, retry, cancellation, and audit behavior open.
- The capability-manager contract says `agent.run` remains unavailable until the authorization/permit, sandbox, execution gateway, and receipt path are connected and verified.
- Career focus is platform and AI-agent engineering, as selected by the user. The current project already has local agent chat, a persistent chat library, a capability manager and proposal flow, LocalTrace/Jaeger projection, and an evaluation lab; agents must verify these against current source instead of assuming every component is live.

## First safe batch
W02 frontend and W03 backend are both read-only audits. They have separate report/draft paths and may run in parallel. No product edit or execution permission is included. W04 will synthesize their findings and keep signal/authorization decisions proposed where evidence or user choice is missing.
