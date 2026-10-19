# Decision Inspector trace projection contract v1

Status: **PREPARED** for the ADL BER candidate. This is a read-only projection
of supplied `TraceSource` data. `LocalTrace` remains an ADL observation; this
contract cannot authorize an operation, validate a BAGO permit, or establish
that BER executed an effect.

## Identity and correlation

The timeline envelope copies `trace_id` and `run_id` from its source. Each row
preserves its source `event_id`, `trace_id`, sequence, name, kind, status,
parent ID, attributes and evidence references. The adapter sorts rows by the
supplied sequence for chronology. Causality is represented separately by the
explicit `parent_event_id`; display order does not establish a parent relation.

Correlation values are copied only from the corresponding explicit event
attributes: `agent_id`, `tool_call_id`, `proposal_id`, `request_id`, `claim_id`,
`action_id`, `execution_id`, `execution_request_id`, `permit_id` and
`receipt_id`. These identifiers remain separate. In particular, a request or
proposal ID is not relabeled as a tool-call ID, and an evidence reference is
not parsed to infer a receipt ID. The run ID comes from the supplied trace
envelope; absent optional event identifiers remain absent.

An event whose trace ID differs from the envelope is preserved and accompanied
by a `trace_id_mismatch` gap. Duplicate event IDs are preserved and reported.
Missing parent events, sequence gaps and invalid sequence values are visible
gaps; the adapter does not repair or conceal them. Source statuses, including
DENY, ERROR and unknown values, and redaction markers pass through unchanged.

## Validation boundary

`validateTraceTimeline` checks required envelope/event identity, ordering,
sequence validity, duplicate event IDs, status presence and explicit reporting
of missing parents. Structural validation does not verify source authenticity,
receipt signatures, BAGO authority, causal truth, payload completeness, BER
execution or browser rendering. A matching identifier is a correlation only;
it does not make an event or receipt authoritative.

Contract tests cover out-of-order input, chronology versus causality, sequence
gaps, missing parents, failed status pass-through, redaction pass-through,
duplicate IDs, event/envelope trace mismatch, explicit execution/receipt and
claim/action identifiers, and absent correlations. They do not exercise a live
BER runtime or validate BAGO receipts.
