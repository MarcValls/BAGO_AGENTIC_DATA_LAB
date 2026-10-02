# One-Command Governed Knowledge Agent Demo

## What it demonstrates

A deterministic local execution of the existing governed knowledge-agent path:

```text
QUESTION → AGENT → GOVERNED RETRIEVAL → EXECUTION → RECEIPTS → TRACE → EVALUATION
```

The agent retrieves two fixture-backed policy/evidence chunks, reasons over the local ontology, calls an injected Bedrock-shaped fixture (not AWS), runs one typed pytest operation through `LocalRestrictedBackend`, links receipts into a `LocalTrace`, and evaluates trace coverage and governance invariants.

## Requirements and clean-clone command

- Python 3.11 or newer.
- Git and a repository checkout.
- No API keys, environment variables, network access, Docker, AWS account, or paid service are required for this demo.

POSIX shell:

```bash
git clone https://github.com/MarcValls/BAGO_AGENTIC_DATA_LAB.git
cd BAGO_AGENTIC_DATA_LAB
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python demo.py
```

Windows PowerShell:

```powershell
git clone https://github.com/MarcValls/BAGO_AGENTIC_DATA_LAB.git
Set-Location BAGO_AGENTIC_DATA_LAB
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python demo.py
```

The one-command execution writes the five JSON files to `demo_output/`. To use another path:

```bash
python demo.py --output-dir path/to/output
```

PowerShell accepts the same `--output-dir` option. Relative paths are resolved from the repository root; absolute paths are also accepted.

## Canonical fixture question and expected result

**Question:** `¿Qué sustituye a la política anterior y qué evidencia la valida?`

**Answer:** `La política vigente sustituye a la anterior y la evidencia enlazada valida esa relación.` The answer includes citations to the committed policy-v2 and validation-receipt fixtures. Run-specific IDs, durations, timestamps, and sandbox receipt hashes can vary; semantic results are expected to remain `PASS`, two retrieval hits, zero ontology contradictions, 15 trace events, and evaluation score `1.0`.

## Artifacts

| File | What to inspect |
|---|---|
| `summary.json` | Human-first result: query, answer, overall/evaluation status and score, retrieval/ontology/sandbox counters, run/trace/evaluation IDs, output file names. |
| `agent_run.json` | Agent input/output, citations, retrieved context metadata, proposals, provider fixture receipt, ontology result, and agent-stage trace. |
| `receipts.json` | Provider fixture receipt, ontology reasoning receipt, sandbox execution receipt, and any agent decision/MCP receipts. Empty decision/MCP lists mean this fixture did not propose those effects. |
| `trace.json` | Ordered LocalTrace events, parent IDs, evidence refs, run ID and trace ID. |
| `evaluation.json` | Deterministic structural checks and their evidence refs; this evaluates trace/governance linkage, not natural-language answer quality. |

The five files are written only after a successful run. Each JSON file is replaced atomically. A failed demo prints a JSON error to stderr and exits non-zero; it does not claim PASS. If interrupted during output writing, rerun the command to regenerate the set.

## Governance controls observed

- Fixture metadata/citations are retained through governed retrieval.
- The Bedrock-shaped client is injected; no AWS transport occurs (`aws_live: NOT_RUN`).
- Typed sandbox request is bounded to the temporary workspace and `test_runner` profile; network mode is deny.
- Provider and sandbox operations carry permit/receipt IDs.
- Trace/evaluation check workflow coverage, retrieval evidence, permit/receipt linkage, absence of unauthorized effects, and sandbox receipt linkage.

## Stack and CI

Python, LangGraph, Pydantic, GovernedRAG, local ontology engine, local restricted sandbox, LocalTraceBuilder, LocalTraceEvaluator, pytest, GitHub Actions. The workflow runs the full suite, generated README check, public E2E, vector-store validation, local OpenMetadata/Jaeger validations, compile check, and the one-command artifact contract tests.

## Limitations

This is a deterministic local fixture demo. It does not validate live AWS, Bedrock Knowledge Base, remote OpenMetadata, commercetools, production observability, answer quality, or production sandbox isolation. The injected provider fixture is not an LLM call. `0.0 USD` describes this local run only; separate live Bedrock billing remains `NOT_PROVEN` as stated in `STATE.md`.

## What to watch

1. The query and citations in `agent_run.json`.
2. `receipts.json`: `ALLOW`/success on the injected provider fixture and successful typed sandbox receipt.
3. `trace.json`: agent → retrieval → ontology/provider → sandbox → receipt linkage.
4. `evaluation.json`: every structural governance check passes; score is `1.0` for this fixture.
5. The explicit `NOT_RUN` external boundaries in `summary.json`.
