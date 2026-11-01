## Branch base freshness

Before creating an implementation worktree, fetch the intended remote base
(normally `origin/main`), record its exact SHA, and create the work branch from
that fetched ref. Do not use a similarly named local branch or an older task
branch as the base. Before publishing, fetch again and compare the branch's
merge base with the refreshed remote base. If the remote advanced, rebase or
recreate the candidate and rerun affected checks. Record both base SHAs in the
goal evidence.

<!-- BAGO_AGENT_DECISION_TEAM_v0.1.0 -->
## BAGO Agent Decision Engineering Team
For work involving agent conclusions, evidence, provenance, traces, proposed actions, authorization or receipts:
- Read .bago/team/kit/protocol/TEAM_PROTOCOL.md.
- Use .bago/team/kit/missions/agent-decision-inspector.json unless the user names another mission.
- Use python .bago/team/kit/scripts/teamctl.py ... as the coordination authority.
- For each assigned role, read plugins/bago-agent-decision-engineering-team/skills/<role>/SKILL.md before editing.
- Start only READY work; use pair to decide safe parallelism; never infer completion from chat alone.
- Every completed work item requires a materialized handoff and verify PASS.
- If native multi-agent collaboration is available, spawn safe batch members in parallel; otherwise preserve the same DAG sequentially.
- Final completion requires the mission terminal gate.
<!-- /BAGO_AGENT_DECISION_TEAM_v0.1.0 -->

## Generated README at work closure

The person or agent closing any repository work is responsible for refreshing
the generated README before reporting completion:

1. Run `python scripts/generate_dynamic_readme.py` after the work is complete.
   This renders `README.md` from its canonical sources and runs the full test
   suite to record the passing count.
2. Run `python scripts/generate_dynamic_readme.py --check --skip-tests` and
   require PASS.
3. Include both results in the closure evidence. If either command fails, keep
   the work open until repaired or record the precise blocker and mark closure
   incomplete.

Never edit `README.md` manually; make any needed correction in its canonical
source and regenerate it.

## Continuity and receipt of delegated work

- Continue through each necessary and already authorized stage in the current task; do not end after naming a next action that can be performed now.
- Recheck mission identity, candidate, scopes, approval, STOP, and revocation before every effect. Registration and delegation never grant additional authority.
- A delegated recap remains pending until it is actually received. Once received, bind it to its work item and candidate and validate scope, changed paths, checks, evidence, and residual risks before recording or acting on it. A recap alone is not execution proof or independent verification.
- Do not close while required recaps, handoffs, checks, approvals, or acceptance criteria are pending. Continue other independent authorized work where possible; report the exact blocker for the affected item.
- Never auto-resume across explicit STOP, pending authorization, revocation, scope conflict, critical error, mandatory human decision, or host restriction. Use a resume mechanism only if it exists and its contract permits the action.
