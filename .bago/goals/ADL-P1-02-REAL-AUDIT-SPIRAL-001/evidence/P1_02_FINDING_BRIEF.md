# P1-02 audit input

## Provenance

- Source artifact: `C:\Users\AMTEC_Terminal_1º\BAGO_AGENTIC_DATA_LAB\.bago\CRIT-BAGO-ADL-FRONTEND-20261009-01.md`
- Source section: lines 31-36, finding `P1-02`.
- The original audit is a static source review against a prior packed snapshot. It says product validation was not performed.
- This brief carries the claim into the current candidate audit; it does not assert that the finding still applies.

## Claim to re-evaluate

**P1-02 — The exposed Agent Runner promises an execution capability explicitly unavailable on the server.**

Original evidence: Agent Runner offers Run, waits for `stdout`/`done`, and can declare success; `/ws/agents/run` sends `type:error`, `code:execution_unavailable`, then closes with 1008 without starting a job. The original report also claimed Runner reported success for any hypothetical `done` regardless of `exit_code`.

Original suggested correction: label execution unavailable, disable/remove Run, display the server error code, and report success only when the terminal result explicitly has exit code 0.

## Audit question

Inspect only the project-relative files `frontend/src/components/AgentRunner.tsx` and `src/api/server.py` in the currently running ADL checkout. Compare the current source with the claim above. State which parts remain, which are corrected, and which require the live endpoint probe. Cite exact line ranges returned by the read tool. Do not use source memory or another checkout as evidence.
