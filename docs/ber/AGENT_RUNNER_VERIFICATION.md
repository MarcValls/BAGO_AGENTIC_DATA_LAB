# W16 Agent Runner independent verification

**Candidate:** `codex/adl-ber-integration-20261019`, HEAD `585fe4635596b1bd253fb8ba6d5b736ebf133ee9`  
**Scope:** deterministic backend, WebSocket, UI and frontend build checks. No live provider credentials or material effects were used.

## Verdict

P0: **0**. P1: **0**. P2: **0**. The tested candidate satisfies W16's adversarial checks. This is not the mission terminal gate: live Ollama/BER execution and the standalone container smoke remain `NOT_RUN` for W17.

## Adversarial verification

| Boundary | Evidence | Result |
|---|---|---|
| Authority comes from the saved profile and current configured workspace | `test_websocket_uses_persisted_profile_server_challenge_and_exact_receipt`; `test_websocket_rejects_client_authored_profile_or_workspace_fields` | PASS. Client-supplied provider/model/workspace fields receive `invalid_message`; successful fixture run uses the saved profile and bound workspace. |
| BER challenge and permit remain server side | Integrated WebSocket test confirms proposal and completion omit `challenge_id`/`permit_token`, while the fake BER receives its stored challenge for approve and execute. | PASS. |
| Explicit authorization, replay, request binding and rejection | `test_rejection_and_cancellation_do_not_approve_or_execute`, `test_approval_is_bound_to_server_held_request_and_uses_no_client_permit`, `test_typed_process_receipt_and_permit_replay_denial`; the W15 UI suite also verifies request ID matching. | PASS. Rejection/cancellation do not approve or execute; mismatched approval and replay are denied. |
| Disconnect and stale workspace | Integrated disconnect test and `test_stale_workspace_and_disconnect_fail_before_execution`; integrated synthetic Git HEAD drift test. | PASS. BER is closed without approve/execute after disconnect; stale binding is rejected before approval. |
| Exact completion receipt and trace correlation | `test_model_proposal_is_prepared_by_ber_and_success_requires_exact_receipt`; `test_missing_or_mismatched_receipt_never_records_success`; integrated fixture checks `request_id`, `receipt_id`, and trace `run_id == ber_execution_id`; UI tests reject mismatched IDs. | PASS. Missing or wrong identities cannot render verified success. |
| Effect allowlist and dangerous operations | `test_blocked_effects_shell_shapes_and_invalid_paths_never_reach_ber_prepare`; `test_typed_process_receipt_and_permit_replay_denial`; API contract. | PASS. `filesystem.delete`, `process.terminate`, arbitrary shell and invalid paths do not reach BER prepare; process inspection and Python pytest are bounded forms. |
| Provider/runtime failures | `test_provider_and_runtime_errors_are_redacted_and_do_not_make_success`, `test_unavailable_provider_and_profile_without_registered_ber_tool_fail_closed`; container status fixture test. | PASS. Unsupported provider/runtime states fail closed and errors do not create success. |
| Malformed WebSocket start | W15R replacement test `tests/test_agent_execution_unavailable.py` sends malformed JSON and asserts `invalid_message` before runner or BER construction. | PASS. This replaces the obsolete test that waited for a start frame without sending one. |

The WebSocket integration tests use FastAPI's in-process TestClient, temporary Git workspaces, and fake provider/BER adapters. They verify the actual route and backend wiring without calling a live Ollama service or a BER runtime.

## Executed verification

| Command | Result |
|---|---|
| `python -m pytest tests/runtime/ber/test_agent_runner.py tests/runtime/ber/test_client.py tests/runtime/ber/test_observability.py tests/test_provider_cognition_repair.py -q` | PASS, 41 passed. Existing Python 3.14 / Pydantic v1 compatibility warning. |
| `python -m pytest tests/verification/agent-runner/test_websocket_integration.py tests/test_agent_execution_unavailable.py -q` | PASS, 6 passed: five integrated WebSocket adversarial cases plus the W15R malformed-start regression. Same existing dependency warning. |
| `node --test tests/ui/agent-runner/agent-runner.test.mjs` (from `frontend/`) | PASS, 9 passed. |
| `npm run test:ui --prefix frontend` | PASS, 17 passed. |
| `npm run build --prefix frontend` | PASS, TypeScript build and Vite production build (129 modules). |
| `python .bago/team/kit/scripts/teamctl.py verify` | PASS after W16 handoff; existing orphan warnings AC01–AC10 and W01–W12 are preserved. |

## NOT_RUN and limits

- Live Ollama inference: `NOT_RUN`. The verification deliberately used a fake provider and no user credentials; this proves the tested boundary behavior, not provider availability or a live inference result.
- Live BER runtime and end-to-end effect: `NOT_RUN`. Tests use a fake BER client and temporary fixtures; no real authorization or filesystem effect was executed.
- Standalone container smoke: `NOT_RUN` in W16. The focused container-mode unit fixture confirms `unsupported_runtime` without credentials or network access; it is not a container launch smoke.
- Full repository test suite and generated README closure: outside W16's focused verification. W17 owns the terminal gate and must run the mission's full relevant checks.

## W14 history note

Two W14 records exist and must not be conflated. The archived pre-correction handoff at `.bago/team/runtime/history/BER_RUNNER_FOLLOWUP_PRE_SCOPE_EXPANSION_20261019/W14.json` records API SHA-256 `8a2eb9e47ce1c91e883f67d5d38a5d5f47fa437c6ede57c8e6052f4a2df898f2` and runner SHA-256 `37e891c8d09aeedfdd9af2ef3f324d6f27d97a0c991b81c4510ef0db30c04266`. The current corrective handoff `.bago/team/runtime/handoffs/W14.json` records API SHA-256 `070f14fd8dda84fba5c61873fda848d0351b9aedfd91865dc23eeb709ec5600d` and runner SHA-256 `61a4196324403dd667b5245eac968943498f078c3f52374c59b2f51b02181a87`. Current file hashes match the corrective values. The corrected contract keeps the BAGO challenge server-side and exposes only the ADL proposal ID to the UI.

## Findings

No P0/P1/P2 findings remain open for W16's assigned scope. The historical obsolete WebSocket test was corrected under W15R and independently passed as part of this verification. The live-runtime limits above remain explicit `NOT_RUN`, not a claim of runtime validation.
