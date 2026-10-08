# Decision Inspector trace contract v1

Status: contract mapped from `src/observability/local_trace.py` and `demo_output/latest/trace.json`. LocalTrace remains the evidence-bearing source of truth; Jaeger is a projection only.

## Mapping

`LocalTrace.trace_id/run_id` map to timeline identity. Events preserve `event_id`, `trace_id`, `sequence`, `name`, `kind`, `status`, `parent_event_id`, attributes and evidence references. The adapter sorts display chronology by `sequence`; it reports gaps and duplicate identities. Causality is exclusively the explicit parent link and is reported separately from chronological position.

Run correlation is carried from the LocalTrace envelope. Existing tool records may expose `request_id` and/or `proposal_id`, which are preserved as tool-call correlation. Claim and action identifiers are linked only when explicitly present as `claim_id` / `action_id`; otherwise their state is `missing`. They are not inferred from event order, evidence references, or names. Current sample trace has no claim/action IDs and has no UI-to-Jaeger trace URL; Jaeger correlation is therefore `unavailable`.

## Integrity and failure behavior

Statuses and attributes pass through unchanged, including failed/denied outcomes and visible redaction markers. Missing parent events, sequence gaps, duplicate event IDs, absent claim/action correlation and absent Jaeger correlation remain explicit. No failure is translated to success. A payload omitted upstream cannot be reconstructed by this read-only adapter.

Focused contract checks cover out-of-order input, chronology versus parent causality, missing parent/correlation, failed calls, redaction pass-through and duplicate IDs. These checks do not establish browser behavior or Jaeger availability.
