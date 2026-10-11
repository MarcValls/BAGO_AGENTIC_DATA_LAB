<!-- BAGO_AGENT_DECISION_TEAM_v0.1.0 -->
## BAGO Agent Decision Engineering Team
For work involving agent conclusions, evidence, provenance, traces, proposed actions, authorization or receipts:
- Read .codex-team-kit/protocol/TEAM_PROTOCOL.md.
- Use .codex-team-kit/missions/agent-decision-inspector.json unless the user names another mission.
- Use python .codex-team-kit/scripts/teamctl.py ... as the coordination authority.
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
