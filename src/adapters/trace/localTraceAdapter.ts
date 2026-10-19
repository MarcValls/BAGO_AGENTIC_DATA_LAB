import type { TraceCorrelations, TraceGap, TraceSource, TraceTimeline, TraceTimelineEvent } from "../../contracts/trace/trace";

function suppliedId(attributes: Record<string, unknown>, key: string): string | undefined {
  const value = attributes[key];
  return typeof value === "string" && value.trim() ? value : undefined;
}

function correlations(attributes: Record<string, unknown>): TraceCorrelations {
  const fields: Array<[keyof TraceCorrelations, string]> = [
    ["agentId", "agent_id"],
    ["toolCallId", "tool_call_id"],
    ["proposalId", "proposal_id"],
    ["requestId", "request_id"],
    ["claimId", "claim_id"],
    ["actionId", "action_id"],
    ["executionId", "execution_id"],
    ["executionRequestId", "execution_request_id"],
    ["permitId", "permit_id"],
    ["receiptId", "receipt_id"],
  ];
  return Object.fromEntries(fields.flatMap(([target, source]) => {
    const value = suppliedId(attributes, source);
    return value ? [[target, value]] : [];
  })) as TraceCorrelations;
}

/**
 * Projects LocalTrace-like data into a timeline. It preserves source events,
 * sorts only for chronology, and never derives identity from names/order/refs.
 */
export function localTraceToTimeline(source: TraceSource): TraceTimeline {
  const input = Array.isArray(source.events) ? source.events : [];
  const sorted = input.map((event, index) => ({ event, index }))
    .sort((left, right) => left.event.sequence - right.event.sequence || left.index - right.index);
  const ids = new Set(input.map(event => event.event_id));
  const seen = new Set<string>();
  const gaps: TraceGap[] = [];
  let previousSequence: number | undefined;

  const events: TraceTimelineEvent[] = sorted.map(({ event }) => {
    if (seen.has(event.event_id)) gaps.push({ kind: "duplicate_event_id", eventId: event.event_id, detail: "Duplicate source event identity; both events are retained" });
    seen.add(event.event_id);
    if (!Number.isInteger(event.sequence) || event.sequence < 0) {
      gaps.push({ kind: "invalid_sequence", eventId: event.event_id, detail: `Invalid source sequence: ${event.sequence}` });
    }
    if (previousSequence !== undefined && Number.isInteger(event.sequence) && event.sequence > previousSequence + 1) {
      gaps.push({ kind: "sequence_gap", eventId: event.event_id, detail: `Missing sequence ${previousSequence + 1} through ${event.sequence - 1}` });
    }
    previousSequence = Number.isInteger(event.sequence) ? event.sequence : previousSequence;

    if (event.trace_id !== source.trace_id) gaps.push({ kind: "trace_id_mismatch", eventId: event.event_id, detail: `Event trace ${event.trace_id} differs from envelope trace ${source.trace_id}` });
    const parentEventId = typeof event.parent_event_id === "string" && event.parent_event_id ? event.parent_event_id : undefined;
    const parentState = !parentEventId ? "root" : ids.has(parentEventId) ? "resolved" : "missing";
    if (parentState === "missing") gaps.push({ kind: "missing_parent", eventId: event.event_id, detail: `Parent event ${parentEventId} is unavailable` });
    return {
      eventId: event.event_id,
      traceId: event.trace_id,
      sequence: event.sequence,
      name: event.name,
      kind: event.kind,
      status: event.status,
      ...(parentEventId ? { parentEventId } : {}),
      parentState,
      runId: source.run_id,
      correlations: correlations(event.attributes || {}),
      attributes: { ...(event.attributes || {}) },
      evidenceRefs: [...(event.evidence_refs || [])],
    };
  });
  return { traceId: source.trace_id, runId: source.run_id, events, gaps, chronology: "sequence", causality: "parent_event_id" };
}
