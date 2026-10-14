# CRIT-ADL-SKILLS-001-RETEST-1

Status: `PREPARED`

## Objective

Retest the L2 and L4 evidence review against the repository at base
`a066792f4ad878ded812cda0220fc1a4c0925289`. Correct the L2 overlap test so it
proves stored chunks exist, strengthen the L4 offline ranking benchmark, report
the three skill levels within the evidence scope, and obtain a green full CI run.

## Acceptance

- L2 overlap verification queries the persisted document rows and fails when
  fewer than two chunks or no adjacent overlap exists.
- L4 compares lexical, deterministic hash-semantic and hybrid retrieval on a
  larger labelled corpus at Recall@1/Recall@3 and MRR, with policy-aware labels.
- The skill matrix and generated README describe local implementation and
  remaining limits without claiming production relevance or professional
  proficiency.
- The complete local suite and README consistency check pass.
- GitHub Actions for the candidate commit passes the full test suite.

## Base and candidate

- Fetched `origin/main` before branching: `a066792f4ad878ded812cda0220fc1a4c0925289`.
- Candidate branch: `codex/crit-adl-skills-001-retest-1`.
- Candidate commit and remote CI result: pending.
