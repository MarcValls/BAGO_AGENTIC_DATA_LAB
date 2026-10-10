# L1 reference-test audit — baseline

## Candidate and run

- Repository: `BAGO_AGENTIC_DATA_LAB`
- Branch: `codex/l1-governed-execution-evidence-20261010`
- HEAD: `aebead4373025c07a4d2c63052890288133d6a4b`
- Worktree: clean before the baseline run
- Test file SHA-256: `FA8EE5A925F9C61066966CCC0AE8331E157EB103DB82FAFAC343C993C58430DD`
- Source SHA-256: `2F070F5FC7F6A85BF0250A82B7F4B1C49CC71D14900699885613DE8F6B69FC11`
- Command: `python -m pytest tests/test_l1_governance.py -q`
- Result: `7 passed, 5 warnings in 0.87s`
- Warnings: Python 3.14 / Pydantic V1 compatibility and four legacy `datetime.utcnow()` deprecations.

This is baseline execution evidence only. The terminal output was observed in
the current session; it is not a frozen stdout artifact. A final run receipt
must be materialized and hashed at the final candidate.

## Claim-to-test map

| Reference test | Production behavior reached at baseline | Initial evidence judgment |
|---|---|---|
| `test_langgraph_cannot_execute_directly` (line 29) | Calls production `authorization_gate` with a WRITE `ExecutionRequest`; asserts denial and no permit for that request. | `PARTIAL`: direct gate behavior is exercised, but the full compiled graph is not tested with a material-action request. |
| `test_permit_reuse_denied` (line 82) | Creates a `Permit`, a local `used_permits` set, and computes validity in the test. It does not call a production replay store or gateway. | `NOT_PROVEN`: the test proves its fixture logic, not system anti-replay enforcement. |
| `test_document_without_provenance_rejected` (line 128) | Builds local dictionaries and filters them in the test; does not call `retrieve_context` or a production provenance validator. | `NOT_PROVEN`: production ingestion/retrieval rejection is not exercised. |
| `test_superseded_chunk_filtered_in_retrieval` (line 187) | Filters local dictionaries using `is_current`; does not call the production retrieval path. | `NOT_PROVEN`: stale-version exclusion in the system is not exercised. |
| `test_mcp_tool_unregistered_denied` (line 227) | Looks up a local dictionary; does not invoke a production tool registry or authorization path. | `NOT_PROVEN`: registry enforcement is not exercised by L1. |
| `test_bedrock_provider_timeout_controlled_failure` (line 263) | Constructs a `Receipt` in test code; does not call a Bedrock adapter or production timeout handling. | `NOT_PROVEN`: provider timeout and receipt behavior are not exercised. |
| `test_governed_agent_graph_end_to_end` (line 308) | Invokes the compiled production graph for a safe retrieval query and checks basic fields. | `PARTIAL`: proves one safe-query graph path, not authorization/denial behavior end to end. |

## Source observations

- `authorization_gate` is implemented in `src/orchestration/state_graph.py`
  and explicitly denies WRITE/CREATE/DELETE requests in the baseline source.
- `execute_actions` consumes issued permits, then synthesizes mock effects and
  receipts. That is local simulation, not a real governed material execution.
- `retrieve_context` returns a hard-coded mock chunk. L1 does not provide the
  ingestion/provenance/version-filtering or MCP registry/provider timeout
  implementations asserted by several test names.

## Baseline conclusion

The reference suite passes, but **only the authorization gate case directly
exercises one of the named production controls**, and the safe-query integration
case covers a narrow graph path. The suite is not sufficient evidence for all
seven claims. Preserve the historical tests as references; strengthen tests
against production behavior where it exists and explicitly lower claims for
missing L1 capabilities. Do not mark L1 broadly `VALIDATED` from this baseline.
