# Goal: one-shot and signal-waiting agents

## Objective
Adapt the ADL's next platform/agent-engineering capability to this candidate: let a user create a bounded one-shot agent and, separately, define an agent that waits for an explicit signal. Start with a frontend/backend discovery spiral, then decide a safe MVP from concrete project seams and evidence.

## Authority and known decision
- User asked to activate the BAGO frontend and backend agent pack in a project-adapted spiral.
- Career focus carried forward from the user's previous answer: AI platform and agent engineering.
- `.bago/goals/ADL-CONVERSATION-LIBRARY-001/goal.md` and `status.json` record this as the next `PROPOSED` objective. Its open questions remain open: signal sources/event types and authorization, lifetime, idempotency, retry, cancellation, and audit rules.
- Existing capability-manager contract keeps `agent.run` fail-closed until the permit, sandbox, executor, and receipt path is actually connected. Preserve that boundary.

## Candidate and preservation
- Candidate worktree: `C:\Users\AMTEC_Terminal_1º\AppData\Local\Temp\BAGO_ADL_agent_evaluation_lab_20261010`
- Branch: `codex/adl-agent-evaluation-lab-20261010`
- Base HEAD: `1e4d9f930da1225ce61ce27def897f76d57a08fc`
- This candidate has substantial existing dirty implementation and evidence. Do not reset, clean, stage, commit, sync, or broaden changes outside this goal's isolated team-runtime evidence until an implementation contract is agreed.
- The repository-root `.bago/team/runtime/state.json` belongs to an already terminal mission. This goal uses a separate team runtime under its own `.bago/goals` directory.

## First spiral boundary
The current iteration activates independent read-only frontend and backend audits. They will map lifecycle UI, chat/provider entry points, endpoint/storage seams, existing execution authorization and observability. The coordinator will synthesize those maps into an implementation-ready contract and enumerate unresolved choices. This discovery pass does not activate execution, invent a signal provider, schedule background work, or claim that an agent is monitoring a source.

## Acceptance for this iteration
1. Record candidate branch/HEAD and preserve pre-existing working tree.
2. Obtain separate frontend and backend handoffs through the BAGO team protocol, each bound to current source evidence and explicit `NOT_RUN` claims.
3. Synthesize one-shot and signal-wait lifecycle states, data/API/UI boundary, failure/cancellation/idempotency/audit requirements, and the smallest viable signal source candidates.
4. Mark unresolved identity, source, or authorization choices `PROPOSED`; do not implement unsafe execution before they are decided.
5. Verify all handoffs and report which implementation step can safely start next.

## Status
`EXECUTED` for the discovery iteration: W01-W04 completed in the isolated team runtime; both audits and the lifecycle contract passed `teamctl verify`. This does not mean the feature is implemented or validated at runtime. Implementation remains unstarted; the first real signal source and actor/authorization boundary remain `PROPOSED`.

## Evidence from this iteration
- `team-runtime/evidence/W01_SCOPE.md` - exact candidate and preservation boundary.
- `team-runtime/evidence/W02_FRONTEND.md` - frontend creation/chat/Runner audit.
- `team-runtime/evidence/W03_BACKEND.md` - backend persistence/authorization/execution audit.
- `team-runtime/evidence/W04_LIFECYCLE_CONTRACT.md` - proposed lifecycle and next bounded spiral.
- `team-runtime/.bago/team/runtime/handoffs/` - machine-checked handoffs; `teamctl verify` returned PASS with terminal gate DONE.
