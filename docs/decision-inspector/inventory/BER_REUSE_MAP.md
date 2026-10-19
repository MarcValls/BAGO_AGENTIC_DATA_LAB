# ADL / BER reuse and authority map (W01)

Status: **PREPARED** for `AGENT_DECISION_INSPECTOR_V1`; this inventory freezes
the observed candidate surface and maps existing owners. It introduces no new
contract or implementation.

## Frozen candidate identity

| Field | Observed value |
|---|---|
| Repository | `BAGO5_ADL` |
| Worktree | `.worktrees/adl-ber-integration-20261019` |
| Branch | `codex/adl-ber-integration-20261019` |
| HEAD | `585fe4635596b1bd253fb8ba6d5b736ebf133ee9` |
| HEAD tree | `9a31954f855d3e38c371eadc145fa488813b9aec` |
| Snapshot state | HEAD was clean at worktree creation; at W01 inspection there were pre-existing edits in `tests/test_semantic_navigation.py` and `.bago/team/runtime/{events.jsonl,state.json}`, plus the ADL BER goal directory. These were not edited by W01. |
| Candidate files read | Working-tree contents of the files named below; their SHA-256 values are recorded in the W01 handoff. |

The earlier `docs/decision-inspector/inventory/REPOSITORY_INVENTORY.md` describes
a different checkout and snapshot (2026-10-08, old branch/HEAD). It remains
historical evidence and is not the identity source for this map.

## Reusable ADL primitives

| Concern | Existing ADL owner and shape | Reuse boundary / gap |
|---|---|---|
| Run and proposal projection | `src/agent/governed_knowledge_agent.py`: `AgentRun`, `AgentToolProposal`, `AgentDecisionReceipt`, `to_dict()`; carries run/request/proposal IDs, tool/effect, authorization decision, called/outcome, receipt IDs, retrieval/citations and error fields. | Reuse as supplied observations. The run record is not BER authority and is not a BAGO permit. Do not infer claims or approval evidence from an answer. |
| Local execution receipt | `src/sandbox/receipt.py`: immutable `SandboxReceipt` and `SandboxExecutionResult`; request/permit/sandbox IDs, capability, profile, operation, status, filesystem/network modes, duration, process output hashes/byte counts, error and evidence refs. `src/sandbox/manager.py` creates receipts for success/denial/failure. | Useful legacy receipt shape for compatibility and inspector display. It is not a BER receipt or durable authorization ledger; do not present it as proof that the BAGO BER gateway executed. |
| LocalTrace | `src/observability/local_trace.py`: immutable `TraceEvent` and `LocalTrace`, with event/trace/run IDs, ordered sequence, kind/status, explicit parent link, attributes and evidence refs. `LocalTraceBuilder.from_agent_run()` joins proposal/permit/receipt and optional sandbox observations. | Reuse the ADL-owned evidence projection. Parent links express declared causality; sequence expresses ordering. This builder does not authorize, execute, sign, or independently validate an external receipt. |
| Trace evaluation | `src/evaluation/local_evals.py`: `EvaluationCheck`, `EvaluationReport`, `LocalTraceEvaluator`; evaluates workflow coverage, retrieval evidence, permit linkage, receipt linkage, unauthorized effects, and optional sandbox-receipt presence. | Reuse for local trace invariants. PASS means these structural checks passed for that trace; it is not a BER runtime or OS-isolation certification. |
| Agent evaluation lab | `src/evaluation/agent_lab.py`: validation, SQLite `EvaluationStore`, suite/run snapshots and grading results; API in `src/api/server.py`. | Reuse for named evaluation suites and recorded run results. It does not grant execution authorization or establish BAGO source identity. |
| Legacy proposal/permit types | `src/orchestration/state_graph.py`: `ExecutionRequest`, `Permit`, `Receipt`, `AuthorizationDecision`, `ExecutionOutcome`. | Preserve only for the legacy route and compatibility. The old request hash omits parameters and is truncated; `Permit.signed_by` is a label and `is_valid()` checks time only. These types cannot be promoted to BER identity, signature, or permit authority. |
| Legacy execution gateway and filesystem/process | `src/execution/gateway.py`, `src/sandbox/{manager,filesystem,process,backend,specification}.py`, `src/orchestration/governed_execution.py`. Typed operations pass through a local policy/backend and receipt path; the backend explicitly is not an OS container. `FilesystemOperation` currently has read/write only; write does not expose BER's expected-existence/prior-digest precondition. | Preserve as legacy behavior and regression surface; do not copy into BER or claim it supplies BER's stronger revalidation. Keep delete unavailable. |
| Agent Runner route | `src/api/server.py` `/ws/agents/run`; `tests/test_agent_execution_unavailable.py`. Current route fails closed with `execution_unavailable`. | Keep unavailable until the BER integration's explicit standalone, parity and receipt gates pass. A UI or LocalTrace projection cannot change this state. |
| Existing Inspector artifacts | `docs/decision-inspector/contracts/{evidence,trace,action}/**`, `docs/decision-inspector/ux/UX_CONTRACT.md`, `docs/decision-inspector/FINAL_STATUS.md`, and `frontend/src/features/decision-inspector/**` / its tests. | Reuse existing read-only projection contracts and surfaces after consumers inspect their actual current status. The inspector displays supplied evidence and action state; it cannot approve, mint permits, execute effects, or turn a missing receipt into success. |

Key source-file hashes at W01 snapshot (SHA-256):

| Path | SHA-256 |
|---|---|
| `src/sandbox/receipt.py` | `91fcc2f8eb2805cfe34b6f2dd0b8dcbad1e28f3ea5be906fdeaf7cfb4753e1eb` |
| `src/observability/local_trace.py` | `62fcabd1f0fd40a2c39887e7ddfcb4f43e3af50ffed4446973348d582e158abb` |
| `src/evaluation/local_evals.py` | `f9a7c79d375aa9ab5d118cb51ed2ecbcd7ef1816bc2a763826ce31e124ac0547` |
| `src/evaluation/agent_lab.py` | `ecfc3baf02fa0d4bd9bbf5cb3643820ad6f192b5a18127339fc465b1cceccabc` |
| `src/execution/gateway.py` | `543d840857931ff69b41530fd6b8fe8ea6276039e21661bc0ba197d080fe1e26` |
| `src/sandbox/manager.py` | `07b24bf62cab172b65c58652177076c3080bd4d333d31325f28af747817173ae` |
| `src/sandbox/filesystem.py` | `231a500f1fe32f6fc476d9446bf492a4e9f25eb0694cb6fcc2bd5d76a16a9b07` |
| `src/orchestration/governed_execution.py` | `57e17fd831a94a6d090c22b6a8f15457841b194e6e1031602c8bad159f77c5b5` |
| `src/agent/governed_knowledge_agent.py` | `0290389a62c473a6df5e7b02817b435cad8a6ba1debdf08e23358a4ddf92d027` |
| `src/orchestration/state_graph.py` | `622324cd47059f7ef9190675cd4b68d63547dde773bd4d3cefbf090254f1781a` |

## BAGO / ADL ownership boundary

BER source reference inspected read-only: `C:\Users\AMTEC_Terminal_1º\BAGO`,
branch `publish/worktree-groups-20261003-7f5d47a6`, HEAD
`5fb6f2f0c57f29de1b42bbb2efb4a57c86aa032d`, `release_version.txt` `4.11.10`.
That source checkout is dirty in unrelated BAGO files; W01 made no changes
there. The integration candidate must continue to bind any derived artifact to
the reviewed source commit and its file hashes, not a version label alone.

| BAGO-owned authority / effect | ADL-owned observation / projection |
|---|---|
| BER authorization and permit issuance/validation (`backend/.bago/core/authorization_boundary.py`, `execution_request.py`). | ADL run/proposal context and read-only inspector projection. An ADL proposal or UI state cannot mint or widen a permit. |
| Effect registration and dispatch (`effect_registry.py`, `execution_gateway.py`, `execution_adapter_contract.py`). | ADL may show the explicitly supplied capability, request, execution and receipt states; it must preserve unknown/unavailable values. |
| Typed filesystem/process effects under reviewed adapters (`execution_adapters/filesystem.py`, `execution_adapters/process.py`) and the BAGO world-state observation/revalidation boundary (`world_state_snapshot.py`). | ADL LocalTrace and Evaluation may reference BAGO receipt/evidence identifiers and check supplied linkage; they do not execute or revalidate the world state. |
| Execution claim lifecycle (`execution_claims.py`) and BAGO's authoritative execution outcome/receipt. | ADL stores/displays a projection and links it to run/trace/evaluation only when IDs and source evidence match. |

`filesystem.delete` remains **BLOCKED** for BER until a verified canonical
BAGO delete adapter and dispatch-time world-state revalidation exist. The
presence of delete operations in other BAGO modules is not evidence that this
BER capability is registered or safe. The ADL legacy filesystem write path
also lacks the required create/modify preconditions (`expected_exists` plus
prior digest); BER must enforce those at its own authority boundary.

## Frozen consumers and limits

- W02 and W03 may use this inventory as a frozen input. W04/W05 should consume
  the later evidence/action contracts and may not reinterpret ADL display data
  as authority.
- The repository already contains evidence, trace and action contract files
  from prior work. Their existence is not proof that every current UI route,
  BER integration, or browser state is verified.
- This is a static source review. It did not call BAGO BER, execute an effect,
  validate a BAGO receipt, run the browser, or claim BER runtime availability.
- No implementation code or existing historical inventory was changed for
  W01.
