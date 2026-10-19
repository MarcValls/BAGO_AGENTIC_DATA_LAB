# ADL capability preservation map

Baseline candidate: ADL `585fe4635596b1bd253fb8ba6d5b736ebf133ee9`.
BER is not connected yet. This map records current owners and migration intent;
it does not claim the protected capabilities have passed post-integration
regression.

| Capability | Current owner and source | Existing verification surface | Consumer | Future owner / action |
|---|---|---|---|---|
| Filesystem and process execution | ADL legacy `src/execution/gateway.py`, `src/sandbox/*`, `src/orchestration/governed_execution.py` | `tests/test_sandbox.py`; `tests/test_agent_execution_unavailable.py`; related API tests | API and local sandbox workflows | `WRAP` legacy behind a compatibility facade; BAGO owns new permits, gateway, adapters and receipts. Keep legacy until parity. |
| Agent Runner | `src/api/server.py` `/ws/agents/run` explicitly rejects with `execution_unavailable`; `frontend/src/components/AgentRunner.tsx` displays unavailable state | `tests/test_agent_execution_unavailable.py` | ADL Agent Runner UI | `BLOCKED` until standalone, receipt, evidence and parity gates pass; then `ADAPT` to BER without reporting success absent a linked terminal receipt. |
| Provider Registration | `src/providers/registration.py`, provider API and `frontend/src/components/ProviderSettings.tsx` | `.bago/goals/ADL-PROVIDER-REGISTRATION-001/goal.md`; baseline test suite | Settings and provider setup | `KEEP`; setup is not authentication or runtime availability. BER work must not turn registration into execution authority. |
| Ollama and Agent Chat | `src/providers/ollama.py`, chat routes and `frontend/src/components/ProviderSettings.tsx` | `tests/test_agent_chat_trace.py`; `tests/test_provider_cognition_repair.py` | Agent Chat and chat trace | `KEEP`; runtime-provider behavior stays independent of BER unless an explicit execution route is added. |
| Conversation Library | `src/conversations/library.py` and chat UI | `tests/test_conversation_library.py` | Agent Chat | `KEEP`. |
| LocalTrace and evaluation | `src/observability/local_trace.py`, `src/evaluation/local_evals.py` | `tests/test_agent_chat_trace.py`; `tests/test_agent_evaluation_lab.py`; full suite | Trace, evaluation and inspector | ADL remains owner. `ADAPT` receipt projection through a BER adapter; retain legacy inputs and linkage checks. |
| Decision Inspector | `frontend/src/features/decision-inspector/**`, action/evidence/trace contracts and adapters | `frontend/tests/ui/decision-inspector/**` | Human review of claims, actions, traces and receipts | ADL remains owner. `ADAPT` only where BER receipt fields need an explicit mapping; never grant authorization from the inspector. |
| ETL and Ontology | `src/etl/**`, `src/metadata/**` | `tests/test_l2_etl_pipeline.py`, `tests/test_ontology_generator.py`, `tests/test_l3_ontology.py`, `tests/test_l10_ontology_engine.py` | Data and metadata workflows | `KEEP`. |
| RAG and vector store | `src/retrieval/**` | `tests/test_retrieval_accuracy.py`, `tests/test_retrieval_benchmark.py`, `tests/test_sqlite_vector_store.py` | Retrieval and agent context | `KEEP`. |
| MCP | `src/adapters/mcp_adapter.py` and governance code | `tests/test_mcp_governance.py` | MCP workflows | `KEEP`; BER does not make MCP executable by itself. |
| Bedrock | `src/adapters/bedrock_*` | `tests/test_bedrock_integration.py`, `tests/test_bedrock_kb_adapter.py` | Provider/knowledge workflows | `KEEP`. |
| OpenMetadata | `src/adapters/openmetadata_adapter.py` | `tests/test_openmetadata_adapter.py` | Catalog and lineage workflows | `KEEP`. |
| Public demo and historical L0-L15 | `src/**`, `.bago/canon/ROADMAP.md`, `.bago/canon/STATE.md` | `tests/test_public_e2e_demo.py`; full suite and current L0-L15 evidence | Demos and capability proof | `KEEP`; run the full relevant regression before compatibility validation. |
| Docker packaging | Docker workflow files and CI contracts | `tests/test_docker_workflow.py`; Docker build not run because the daemon is unavailable | Local/CI packaging | `ADAPT` to include the verified BER bundle. Packaging and clean-machine acceptance stay blocked until Docker is available. |
| Authorization, Permit, execution claims and material receipts | Currently ADL legacy request/permit/sandbox; target implementation in the BAGO source worktree | BAGO authorization, gateway and execution-claim tests plus new BER adversarial tests | BER server and ADL evidence projection | BAGO owns authority and execution. Derive the artifact from the pinned source; do not duplicate or retire BAGO owners. |

No row is classified `RETIRE_LATER` yet. Deletion and retirement require their
own parity evidence and an explicit later gate. `filesystem.delete` stays
`BLOCKED`.
