# BER compatibility and protected L0-L15 regression matrix

Candidate: ADL branch `codex/adl-ber-integration-20261019`, base
`585fe4635596b1bd253fb8ba6d5b736ebf133ee9`; BAGO source commit
`5fb6f2f0c57f29de1b42bbb2efb4a57c86aa032d`.

## Side-by-side semantic parity

`tests/runtime/ber/test_legacy_parity.py` drives the existing ADL
`SandboxManager` and the packaged BER independently against equivalent
temporary workspaces. Receipt identities and permit authorities are expected
to differ: ADL legacy receipts use `sandbox://`, while BER issues its own
receipt and approval identities. The parity claim is about user-visible
effect outcome, not identical provenance or authorization owners.

| Effect | Legacy route | BER route | Matched outcome | Additional BER boundary |
|---|---|---|---|---|
| Read | `FilesystemRequest(READ)` under `READ_ONLY_AGENT` | `filesystem.read` with approved challenge | Same returned text and successful receipt | BER receipt is BAGO-issued and ADL trace is only a projection. |
| Create | `FilesystemRequest(WRITE)` under `REPOSITORY_WORKER` | `filesystem.write`, `expected_exists=false`, BAGO approval | Same resulting file bytes | Workspace-relative target and BAGO-owned authorization. |
| Modify | Legacy typed write over an existing target | `filesystem.write`, `expected_exists=true` plus its current SHA-256, BAGO approval | Same resulting file bytes; ADL adapter preserves Windows legacy newline conversion | BER rejects stale existence/content before dispatch. |
| Typed process inspection | `ProcessRequest(GIT_READ, GitOperation.STATUS)` | `process.inspect` with exact read-only Git argv | Same `git status --porcelain` output | Server-policy authorization; no approval prompt. |
| Typed process execution | `ProcessRequest(RUN_TESTS, pytest -q tests)` | `process.execute` with exact `sys.executable -m pytest -q tests`, BAGO approval | Both run one passing test | On Windows only validated `%APPDATA%` under `%USERPROFILE%` is added for Python user-site discovery; unrelated custom env stays filtered. |

The explicit compatibility adapter is
`src/runtime/ber/compatibility.py`. It adapts only the legacy text newline
representation before BER prepares the request. It does not authorize, execute,
or issue a receipt. BAGO still owns the execution and receipt.

`filesystem.delete` is absent from both routes in this integration and remains
`BLOCKED`. `process.terminate` is not exposed by BER.

## Protected L0-L15 surface

The full ADL pytest suite is the regression gate for the phase-level
capabilities. These are the focused canonical files exercised within that full
suite; overlapping integration tests intentionally appear under more than one
level when they protect a shared boundary.

| Level | Protected behavior | Focused regression files |
|---|---|---|
| L0 | Repository/README baseline and generated artifact consistency | `tests/test_dynamic_readme.py`, README generation and `--check --skip-tests` |
| L1 | Governed graph, approval, receipts and execution boundary | `tests/test_l1_governance.py`, `tests/test_l1_integrated_graph.py` |
| L2 | Ingestion and persisted ETL behavior | `tests/test_l2_etl_pipeline.py` |
| L3 | Metadata, ontology and evidence references | `tests/test_l3_ontology.py`, `tests/test_l3_evidence.py`, `tests/test_metadata_schema.py`, `tests/test_ontology_generator.py` |
| L4 | Governed RAG accuracy and repeatable benchmark | `tests/test_retrieval_accuracy.py`, `tests/test_retrieval_benchmark.py` |
| L5 | MCP discovery, authorization and tool invocation | `tests/test_mcp_governance.py` |
| L6 | Bedrock provider adapter behavior | `tests/test_bedrock_integration.py` |
| L7 | Bedrock Knowledge Base adapter behavior | `tests/test_bedrock_kb_adapter.py` |
| L8 | OpenMetadata search and lineage adapter | `tests/test_openmetadata_adapter.py` |
| L9 | End-to-end governed agent and workspace binding | `tests/test_l9_end_to_end_agent.py`, `tests/test_workspace_binding.py` |
| L10 | Governed ontology engine | `tests/test_l10_ontology_engine.py` |
| L11 | Legacy sandbox, path boundaries and typed process behavior | `tests/test_sandbox.py`, `tests/test_agent_execution_unavailable.py`, `tests/runtime/ber/test_legacy_parity.py` |
| L12 | LocalTrace and deterministic evaluation | `tests/test_l12_observability.py`, `tests/test_agent_chat_trace.py`, `tests/test_agent_evaluation_lab.py`, BER trace tests |
| L13 | Public E2E and CI contracts | `tests/test_public_e2e_demo.py`, `tests/test_docker_workflow.py` |
| L14 | Persistent local vector store and retrieval reload | `tests/test_sqlite_vector_store.py` |
| L15 | OpenTelemetry span projection | `tests/test_l15_otel_bridge.py` |

Protected non-level capabilities are also included in the full suite: provider
registration/Ollama (`tests/test_provider_cognition_repair.py`), conversation
library (`tests/test_conversation_library.py`), Agent Runner fail-closed
behavior (`tests/test_agent_execution_unavailable.py`), and Decision Inspector
(`frontend/tests/ui/decision-inspector/**`).

This matrix maps tests to the protected surface; passing source tests alone
does not prove standalone packaging, Agent Runner integration, or parity for
unlisted effects. Those remain separate acceptance gates.
