# Canonical demo walkthrough

The canonical run is preserved under `evidence/one_command_demo/`. Its five JSON files carry the same `run_id` and `trace_id`; the narrative below describes those artifacts, not a separate execution.

## 30-second explanation

This demo answers one policy question using local, committed fixtures. The agent retrieves the current policy and its validation evidence, applies local ontology reasoning, calls an injected provider fixture, executes a typed pytest request in the restricted local sandbox, and records receipts and a trace. A deterministic evaluator checks that retrieval, authorization, receipt, and sandbox evidence are linked. The observed fixture result is PASS; no AWS or other remote provider is called.

## 90-second explanation

The question asks which policy supersedes the previous one and what validates it. GovernedRAG returns two evidence-bearing fixture chunks. The agent and ontology engine produce the answer and policy paths. The Bedrock-shaped adapter uses a deterministic injected client, so the run exercises the provider receipt contract without AWS credentials or transport. A typed `RUN_TESTS` capability is authorized and executed through `LocalRestrictedBackend` with workspace-scoped writes and network denied. The trace joins the agent stages, retrieval, provider, ontology, sandbox, and receipts by IDs and evidence references. `LocalTraceEvaluator` checks trace root/workflow coverage, retrieval evidence, permit and receipt linkage, absence of unauthorized effects, and sandbox receipt. The sample result is 15 events and score 1.0. That score means structural checks passed; it is not a model-quality score.

## Five-minute technical walkthrough

1. Open `summary.json`: read the exact question/answer, status, counters, `run_id`, `trace_id`, and evaluation score. External live boundaries are `NOT_RUN`.
2. Open `agent_run.json`: follow `run_id`, query, answer, citations, retrieval hits, provider fixture receipt, ontology reasoning and stage trace.
3. Open `receipts.json`: compare provider `request_id`/`permit_id`/`receipt_id`, ontology receipt, and sandbox receipt. Empty agent decision/MCP receipt arrays mean this scenario made no such tool proposals; they are not missing evidence.
4. Open `trace.json`: check ordered event names, parent event IDs, receipt/evidence links, `run_id`, and `trace_id`.
5. Open `evaluation.json`: verify its `trace_id` matches the trace and each named structural check is true. The evaluator tests evidence/governance structure, not answer correctness or production readiness.
6. Re-run `python demo.py`; IDs and execution metadata can change between runs. The fixture answer, retrieval count, 15-event workflow, governance checks, and evaluation PASS should remain equivalent.

## Canonical evidence

- Input and final answer: `evidence/one_command_demo/summary.json`
- Full agent run: `evidence/one_command_demo/agent_run.json`
- Receipts: `evidence/one_command_demo/receipts.json`
- Trace: `evidence/one_command_demo/trace.json`
- Evaluation: `evidence/one_command_demo/evaluation.json`

The canonical run uses the committed fixture and local sandbox only. Do not present it as a live AWS request, production observability, a production sandbox, or an LLM answer-quality evaluation.
