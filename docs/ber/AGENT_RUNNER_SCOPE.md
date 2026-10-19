# ADL Agent Runner over BAGO Embedded Runtime

Status: **FROZEN SCOPE** for the BER Agent Runner follow-up mission.

## Authority and runtime

- ADL loads the persisted agent profile by `agent_id`; browser-supplied agent
  configuration is display-only and is not execution authority.
- The requested workspace is resolved and bound through the existing
  `src/context/workspace_binding.py`. A binding describes repository identity
  and freshness; it does not authorize an effect.
- Model/tool proposals are untrusted. ADL maps only registered agent tools to
  BER's typed effect profile. No legacy SandboxManager or
  `ExecutionGateway` path is an execution fallback.
- The exact pinned archive and lock remain the only BER runtime source.
  BAGO owns approval challenges, permits, effect execution and receipts.
  ADL owns the Agent Runner conversation, human-facing review, and LocalTrace
  projection.
- Agent execution is available only when the host runtime and the configured
  provider are available. Provider setup/credentials remain separate from
  execution authorization.

## Interaction boundary

The runner accepts a persisted `agent_id`, a bound workspace and a bounded
user task. It emits inspectable proposal, authorization, execution, receipt,
trace, completion and error states. A proposed action must be prepared by BER
before it is shown to the user. The approval control refers to that exact
proposal and challenge; changing the effect or its arguments invalidates the
approval. Rejection, timeout, disconnect, stale workspace identity, or any
runtime/provider error ends without a success state.

The allowed effects are limited to BER's registered profile:

- `filesystem.read`
- `filesystem.write`
- `process.inspect`
- `process.execute`

The exact approval requirement comes from the BER preparation response.
Effects marked as requiring approval cannot execute before an explicit human
approval bound to the current challenge. Read-only `process.inspect` may use
the BER server's own authorization policy. `filesystem.delete`,
`process.terminate`, arbitrary shell commands, and tools without a typed BER
mapping remain unavailable.

## Evidence and success

Each run, proposal, BER request, authorization decision, permit, receipt and
trace event keeps its own source identity. A BER receipt remains BAGO evidence;
an ADL LocalTrace or UI projection cannot mint or relabel it. A run may report
successful execution only after ADL verifies a successful BER result and exact
request/receipt linkage. Missing, malformed or mismatched receipts remain
failed or unverified. Task completion text is separate from effect execution
success.

The API contract will be materialized by W14 before the UI consumer starts.
W15 consumes that frozen contract. W16 independently probes unauthorized,
rejected, stale/replayed approval, unsupported effect, provider/runtime error,
and missing/mismatched receipt paths. The final Runner gate does not authorize
publishing or deployment.
