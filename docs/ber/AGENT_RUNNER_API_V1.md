# ADL Agent Runner WebSocket API v1

Status: **PREPARED by W14** for W15; freeze with the W14 handoff.

## Authority boundary

Connect to `/ws/agents/run` from the local UI origin. The first frame must be a
JSON object with exactly these fields:

```json
{"type":"start","agent_id":"agent_0123456789abcdef","task":"Review the current project."}
```

`agent_id` resolves a persisted ADL profile on the server. Browser-supplied
profile configuration, provider, model, tool, effect, target, arguments,
workspace path, BER challenge, permit and receipt values are never execution
authority. The server binds its configured workspace with
`src/context/workspace_binding.py`; the client cannot choose a filesystem root.
The saved profile must use the existing Ollama provider. In container runtime,
or when provider setup/model or the pinned BER runtime is unavailable, the
request fails closed.
The encoded start frame is capped at 9,024 characters and the task at 8,000
characters. A decision frame is capped at 1,024 characters.

The provider may return at most one `sandbox.run` proposal, and only if that
tool is present in the saved profile. `sandbox.run` is only a profile selector
for this boundary; it never falls back to ADL's legacy SandboxManager. The
server accepts only BER v0.1 typed operations:

- `filesystem.read`: workspace-relative `target.path`, no arguments.
- `filesystem.write`: workspace-relative path, bounded UTF-8 text, and exact
  create/modify preconditions. A modify requires the prior SHA-256.
- `process.inspect`: `git` with one exact read-only query from BER's profile.
- `process.execute`: the current Python executable with argv beginning
  `-m pytest`; no shell, command string, script or arbitrary executable.

`filesystem.delete`, `process.terminate`, unknown effects, extra fields,
multiple model tool calls, invalid paths, changed workspaces and unsupported
process argv are rejected before BER preparation. Model output is untrusted.

## Proposal and decision frames

After BAGO BER `prepare` succeeds, the server sends a `proposal` frame:

```json
{
  "type":"proposal",
  "run_id":"run_<id>",
  "agent_id":"agent_<id>",
  "proposal_id":"proposal_<id>",
  "request_id":"<BAGO request id>",
  "effect_id":"filesystem.write",
  "approval_required":true,
  "target":{"path":"reports/review.txt"},
  "arguments":{"content":"reviewed text","expected_exists":false},
  "operation_sha256":"<canonical operation digest>",
  "world_state_digest":"<BAGO world state digest>",
  "expires_at":"<BAGO challenge expiry>",
  "task_status":"awaiting_review",
  "effect_status":"proposed"
}
```

W15 displays the proposed target and arguments for human review. The digest and
server-held prepared operation bind approval to the exact operation. The UI
receives only the ADL `proposal_id`; the BAGO `challenge_id` stays server-side
in the pending proposal. The UI must send only this decision frame; it must
not echo effect data or challenge identifiers:

```json
{"type":"decision","proposal_id":"proposal_<id>","decision":"approve"}
```

`decision` is exactly `approve`, `reject`, or `cancel`. Reject/cancel consumes
the pending ADL proposal and closes its BER client without calling approve or
execute. For a prepared action with `approval_required:true`, ADL calls
`BerClient.approve` on the stored challenge using the local UI channel, checks
the approval's request ID against the prepared request, then executes that
same challenge. If BAGO states `approval_required:false`, ADL still waits for
the user's review decision; on `approve`, it executes through BAGO's own
server-policy boundary without fabricating a human BAGO permit.

Proposal IDs and challenges are single-use within the WebSocket session.
Replay, mismatch, disconnect before the decision, stale workspace identity,
runtime/provider failure, rejection and cancellation do not record success.
The backend never accepts a permit token from the browser and never returns
the token issued internally by BAGO.

## Outcome frames

- `task_result`: text answer only; `task_status:"answered"` and
  `effect_status:"not_started"`. It is not an executed action or job success.
- `rejected` / `cancelled`: the proposal ended with `effect_status:"not_executed"`.
- `authorization_denied`: BAGO did not authorize the exact request; no execute
  call follows.
- `completed`: emitted only after the execution response has an exact prepared
  request ID and effect ID, non-empty BER execution ID, `executed:true`,
  `ok:true`, and the same non-empty receipt ID both outside and inside the
  result. `execution.verified_success` is then true.
- `execution_unverified`: execution returned but one or more exact receipt or
  request checks failed. `execution.verified_success:false`; this is never a
  success state.
- `error`: safe code and message, with no raw provider response, credentials,
  model arguments or exception text.

Completion frames include only request/receipt/execution IDs, the BAGO
authorization decision/permit IDs, an ADL LocalTrace projection derived from
the pinned BER artifact identity, and verification state. They omit permit
tokens and raw process stdout/stderr. The projection is included only when the
BER execution identity is complete; it never repairs a mismatched request,
effect, or receipt.
ADL does not create a legacy job record for a proposal or unverified result.
The trace is a projection of BAGO source identifiers; it is not an authorization
or receipt authority. The BAGO receipt remains the canonical evidence.

## Errors and retry

The server uses stable error codes including `invalid_message`,
`invalid_decision`,
`agent_unavailable`, `provider_unavailable`, `runtime_unavailable`,
`workspace_stale`, `effect_not_allowed`, `process_profile_denied`,
`proposal_not_pending`, `client_disconnected`, `ber_prepare_failed`, and
`ber_execution_failed`. A failed session closes its BER client. A client must
start a new WebSocket run after an error; it cannot resubmit approval or reuse
a prior proposal ID. Error text is intentionally generic so credentials and
provider response bodies do not enter API messages or logs.

## W15 integration requirements

- Render the proposal before presenting approve/reject/cancel choices.
- Bind the user's choice to the returned `proposal_id`; send no client-authored
  operation fields.
- Keep proposal, BAGO approval decision, execution outcome, receipt and task
  answer as distinct UI states.
- Show success only for `completed` with `verified_success:true` and exact IDs.
- Treat `execution_unverified`, missing trace/receipt data and errors as
  non-success states. Never invoke legacy sandbox execution as fallback.
