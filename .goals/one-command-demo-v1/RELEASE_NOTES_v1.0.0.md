# BAGO Agentic Data Lab — One-Command Governed Knowledge Agent Demo v1.0.0

**Status:** VERIFIED · RELEASED · FROZEN
**Source commit:** `b584235ecfdbc2ecb1c3d601ce40fb4f973ff2e8`
**Release tag:** `v1.0.0`

## Demo

Run `python demo.py` from the repository root. The launcher creates/reuses `.venv`, installs the pinned requirements if needed, runs the existing Bruma Market fictional-client governed E2E scenario, and writes a reviewable evidence bundle to `demo_output/latest/`.

The canonical question asks what policy applies when a fictional Bruma Market express order is more than 24 hours late and what evidence validates the rule. The verified local fixture retrieves two sources, returns the shipping-fee refund rule, executes a typed sandbox test, records provider/ontology/sandbox receipts, projects 15 events into LocalTrace, and passes all seven structural governance checks (score 1.0). This is not a semantic answer-quality score or a live model call.

## Canonical outputs

The attached `governed-agent-demo-evidence-37073597974.zip` contains the five JSON files uploaded by the successful GitHub Actions run at the release source SHA:

- `summary.json`
- `agent_run.json`
- `receipts.json`
- `trace.json`
- `evaluation.json`

Run ID, trace ID, receipt IDs, evidence references and evaluation checks are cross-linked in the bundle. The workflow artifact is also available from CI run `37073597974`.

## Verification

- GitHub Actions CI run `37073597974`: **success**, source SHA `b584235ecfdbc2ecb1c3d601ce40fb4f973ff2e8`.
- Full test suite: **148 passed**.
- Generated README consistency: **pass**.
- Public E2E and one-command demo: **pass**; evidence bundle uploaded.
- Local vector store, OpenMetadata 1.12.6, Jaeger/OpenTelemetry, compile checks: **pass** in CI.
- Independent critical review: **P0=0, P1=0; RELEASE VERIFIED**.
- Clean clone on Windows/Python 3.11: requirements installed, `py -3.11 demo.py` bootstrapped its own `.venv` and emitted all five artifacts successfully.

## Reproduction

```powershell
git clone https://github.com/MarcValls/BAGO_AGENTIC_DATA_LAB.git
Set-Location BAGO_AGENTIC_DATA_LAB
py -3.11 demo.py
```

Or with Python on PATH:

```bash
python demo.py
```

First run requires package-index access to install Python dependencies. The demo itself makes no cloud requests and requires no API credentials, Docker, or paid service.

## Boundaries

- Bruma Market and policy/evidence records are fictional deterministic fixtures.
- Bedrock-shaped provider is injected locally; `aws_live=NOT_RUN`.
- Remote OpenMetadata/commercetools and production observability are not claimed by this demo.
- Evaluator checks governance/evidence structure, not model answer quality.

## Freeze policy

Tag `v1.0.0` is immutable. Any future code, documentation, or canonical output change belongs in a new version/tag; do not move this tag or replace its release asset in place.
