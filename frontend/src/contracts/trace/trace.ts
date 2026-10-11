/** Decision Inspector trace contract mapped from LocalTrace; it is never an authority. */

export type TraceCorrelationState = "linked" | "missing";

export interface TraceCorrelation {
  runId: string;
  agentId?: string;
  toolCallId?: string;
  claimId?: string;
  actionId?: string;
  /** Correlations absent from the source stay explicitly missing. */
  claimState: TraceCorrelationState;
  actionState: TraceCorrelationState;
}

export interface TraceTimelineEvent {
  eventId: string;
  traceId: string;
  sequence: number;
  name: string;
  kind: string;
  /** Preserve source result verbatim: e.g. DENY/ERROR must never become success. */
  status: string;
  parentEventId?: string;
  parentState: "root" | "resolved" | "missing";
  correlation: TraceCorrelation;
  /** Payload values (including redaction markers) are passed through unchanged. */
  attributes: Record<string, unknown>;
  evidenceRefs: string[];
}

export interface TraceGap {
  kind: "sequence_gap" | "missing_parent" | "duplicate_event_id";
  eventId?: string;
  detail: string;
}

export interface TraceTimeline {
  traceId: string;
  runId: string;
  events: TraceTimelineEvent[];
  gaps: TraceGap[];
  chronology: "sequence";
  causality: "parent_event_id";
  jaegerCorrelation: "available" | "unavailable";
}

export interface LocalTraceRecord {
  trace_id: string;
  run_id: string;
  events: Array<{
    event_id: string;
    trace_id: string;
    sequence: number;
    name: string;
    kind: string;
    status: string;
    parent_event_id?: string | null;
    attributes?: Record<string, unknown>;
    evidence_refs?: string[];
  }>;
}

export function validateTraceTimeline(value: TraceTimeline): string[] {
  const errors: string[] = [];
  if (!value.traceId.trim() || !value.runId.trim()) errors.push("trace and run ids are required");
  const ids = new Set<string>();
  for (const event of value.events) {
    if (!event.eventId.trim()) errors.push("event id is required");
    if (ids.has(event.eventId)) errors.push(`duplicate event id: ${event.eventId}`);
    ids.add(event.eventId);
  }
  for (let i = 1; i < value.events.length; i += 1) {
    if (value.events[i - 1].sequence > value.events[i].sequence) errors.push("events must be ordered by sequence");
  }
  return errors;
}
