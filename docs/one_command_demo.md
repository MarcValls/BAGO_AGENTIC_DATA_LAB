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
- Once the dependencies are installed, the local fixture demo does not require API keys, network access, Docker, an AWS account, or a paid service. Installing the dependencies may require access to a package source.

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

**Question:** `¿Qué política aplica a los pedidos exprés que llegan con más de 24 horas de retraso y qué evidencia valida la regla?`

**Answer:** `Para pedidos exprés con más de 24 horas de retraso, la política vigente devuelve el coste del envío; el acta de QA valida la regla.` The answer includes citations to the committed policy-v2 and validation-receipt fixtures. Run-specific IDs, durations, timestamps, and sandbox receipt hashes can vary; the observed local fixture produced `PASS`, two retrieval hits, zero ontology contradictions, 15 trace events, and evaluation score `1.0`.

## Artifacts

| File | What to inspect |
|---|---|
| `summary.json` | Human-first result: query, answer, overall/evaluation status and score, retrieval/ontology/sandbox counters, run/trace/evaluation IDs, output file names. |
| `agent_run.json` | Agent input/output, citations, retrieved context metadata, proposals, provider fixture receipt, ontology result, and agent-stage trace. |
| `receipts.json` | Provider fixture receipt, ontology reasoning receipt, sandbox execution receipt, and any agent decision/MCP receipts. Empty decision/MCP lists mean this fixture did not propose those effects. |
| `trace.json` | Ordered LocalTrace events, parent IDs, evidence refs, run ID and trace ID. |
| `evaluation.json` | Deterministic structural checks and their evidence refs; this evaluates trace/governance linkage, not natural-language answer quality. |

The five files are written after the demo returns a result. They are written individually and can overwrite files in the selected output directory; the set is not an atomic transaction. If writing is interrupted, inspect the output and run again in a new directory before treating the files as a complete bundle. An uncaught error exits non-zero and may produce a Python traceback.

## Governance controls observed

- Fixture metadata/citations are retained through governed retrieval.
- The Bedrock-shaped client is injected; no AWS transport occurs (`aws_live: NOT_RUN`).
- The typed sandbox request uses a temporary workspace and the `test_runner` profile with network mode `DENY`. This is a policy setting; it does not establish OS-level network isolation.
- Provider and sandbox operations carry permit/receipt IDs.
- Trace/evaluation check workflow coverage, retrieval evidence, permit/receipt linkage, absence of unauthorized effects, and sandbox receipt linkage.

## Stack and CI

Python, LangGraph, Pydantic, GovernedRAG, local ontology engine, local restricted sandbox, LocalTraceBuilder, LocalTraceEvaluator, pytest, GitHub Actions. The local CI configuration includes the public E2E, vector-store validation, local OpenMetadata/Jaeger validations, compile check, and one-command demo; the legacy README generator check and its tests are disabled. A configured step is not evidence that a particular candidate passed CI.

## Presenting the demo

**30 seconds:** A fictional late-delivery question produces a fixture-backed answer, citations, receipts, a trace, and a structural evaluation. No live provider is called.

**90 seconds:** Run `python demo.py` in a prepared environment. Read the question and answer in `summary.json`. Follow the run ID through `agent_run.json`, `receipts.json`, and `trace.json`, then the trace ID through `receipts.json`, `trace.json`, and `evaluation.json`. The evaluation checks evidence and governance linkage; it is not an assessment of answer quality.

**5 minutes:** Show the two retrieved policy/QA sources, the ontology result, the injected provider receipt, and the typed sandbox receipt. Follow the receipt references into the ordered trace and evaluation checks. Explain that IDs change between runs, the five files must be read as one bundle, and live AWS and OpenMetadata are outside this fixture's evidence.

## Limitations

This is a deterministic local fixture demo. It does not validate live AWS, Bedrock Knowledge Base, remote OpenMetadata, commercetools, production observability, answer quality, or production sandbox isolation. The injected provider fixture is not an LLM call. `0.0 USD` describes this local run only; separate live Bedrock billing remains `NOT_PROVEN` as stated in `STATE.md`.

## What to watch

1. The query and citations in `agent_run.json`.
2. `receipts.json`: `ALLOW`/success on the injected provider fixture and successful typed sandbox receipt.
3. `trace.json`: agent → retrieval → ontology/provider → sandbox → receipt linkage.
4. `evaluation.json`: every structural governance check passes; score is `1.0` for this fixture.
5. The explicit `NOT_RUN` external boundaries in `summary.json`.
