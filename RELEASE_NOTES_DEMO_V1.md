# BAGO Agentic Data Lab — One-Command Governed Knowledge Agent Demo v1.0.0

## Release status

- Version: `1.0.0`
- Release tag: `v1.0.0`
- Scope: deterministic local fixture demo; no architecture additions or live cloud calls.
- Canonical command: `python demo.py`
- Output directory: `demo_output/`

## What is released

One command runs the existing governed knowledge-agent path and writes five JSON artifacts: `summary.json`, `agent_run.json`, `receipts.json`, `trace.json`, and `evaluation.json`. The canonical execution is preserved in `evidence/one_command_demo/`.

The sample question asks which policy supersedes the previous policy and what evidence validates it. The canonical fixture result is PASS, with two retrieval hits, a 15-event LocalTrace, and structural evaluation score 1.0. The score is not an answer-quality metric.

## Reproduction

Python 3.11+; create and activate a virtual environment, then install `requirements.txt`. No credentials, environment variables, Docker, network, or paid service are required for the local demo.

```bash
python -m pip install -r requirements.txt
python demo.py
python -m pytest tests -q
python scripts/generate_dynamic_readme.py --check --skip-tests
```

Windows PowerShell setup is documented in `docs/one_command_demo.md`.

## Verification record

The release candidate passed the clean-clone Windows/Python 3.11 execution and generated all five artifacts with matching run/trace IDs. The local full suite reports 151 passing tests; the README check and `compileall` pass. GitHub Actions is configured to run the same demo and existing local service checks; a remote Actions run for this release commit is not claimed until observed.

At freeze time the release commit and annotated Git tag identify the immutable source snapshot. Verify the exact commit with:

```bash
git rev-parse v1.0.0^{commit}
git ls-remote origin refs/tags/v1.0.0
```

## Artifact guide and demo explanations

- `docs/one_command_demo.md` — install, one-command usage, outputs, governance, limits.
- `docs/one_command_demo_walkthrough.md` — 30-second, 90-second, and five-minute explanations.
- `evidence/one_command_demo/` — canonical input/output summary, agent run, receipts, trace, evaluation.

## Explicit boundaries

- Provider call in this demo is injected fixture behavior, not AWS Bedrock transport.
- `aws_live` and `openmetadata_live` are `NOT_RUN` for this canonical local demo.
- The evaluator checks trace/evidence/governance structure, not semantic answer quality.
- The local sandbox is not a production container, OS firewall, or production isolation boundary.
- Existing STATE.md remains authoritative for separate cloud claims and limitations.

## Freeze policy

This v1.0.0 release is frozen. Any later change to source or canonical outputs must be released under a new version/tag, not applied in place to `v1.0.0`.
