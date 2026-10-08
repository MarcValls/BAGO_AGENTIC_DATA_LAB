import type { LocalTraceRecord, TraceGap, TraceTimeline, TraceTimelineEvent } from "../../contracts/trace/trace";

/** Project existing LocalTrace data without inferring causality or UI/Jaeger links. */
export function localTraceToTimeline(source: LocalTraceRecord): TraceTimeline {
  const sorted = [...(source.events || [])].sort((a, b) => a.sequence - b.sequence);
  const ids = new Set(sorted.map(event => event.event_id));
  const seenIds = new Set<string>();
  const gaps: TraceGap[] = [];
  const events: TraceTimelineEvent[] = sorted.map((event, index) => {
    if (seenIds.has(event.event_id)) gaps.push({ kind: "duplicate_event_id", eventId: event.event_id, detail: "Duplicate source event identity" });
    seenIds.add(event.event_id);
    if (index > 0 && event.sequence > sorted[index - 1].sequence + 1) {
      gaps.push({ kind: "sequence_gap", eventId: event.event_id, detail: `Missing sequence ${sorted[index - 1].sequence + 1} through ${event.sequence - 1}` });
    }
    const parentEventId = event.parent_event_id || undefined;
    const parentState = !parentEventId ? "root" : ids.has(parentEventId) ? "resolved" : "missing";
    if (parentState === "missing") gaps.push({ kind: "missing_parent", eventId: event.event_id, detail: `Parent event ${parentEventId} is unavailable` });
    const attributes = { ...(event.attributes || {}) };
    const optional = (key: string) => typeof attributes[key] === "string" && attributes[key] ? String(attributes[key]) : undefined;
    const proposalId = optional("proposal_id");
    const requestId = optional("request_id");
    return {
      eventId: event.event_id,
      traceId: event.trace_id,
      sequence: event.sequence,
      name: event.name,
      kind: event.kind,
      status: event.status,
      ...(parentEventId ? { parentEventId } : {}),
      parentState,
      correlation: {
        runId: source.run_id,
        ...(optional("agent_id") ? { agentId: optional("agent_id") } : {}),
        ...((requestId || proposalId) ? { toolCallId: requestId || proposalId } : {}),
        ...(optional("claim_id") ? { claimId: optional("claim_id") } : {}),
        ...(optional("action_id") ? { actionId: optional("action_id") } : {}),
        claimState: optional("claim_id") ? "linked" : "missing",
        actionState: optional("action_id") ? "linked" : "missing",
      },
      attributes,
      evidenceRefs: [...(event.evidence_refs || [])],
    };
  });
  return {
    traceId: source.trace_id,
    runId: source.run_id,
    events,
    gaps,
    chronology: "sequence",
    causality: "parent_event_id",
    jaegerCorrelation: "unavailable",
  };
}
