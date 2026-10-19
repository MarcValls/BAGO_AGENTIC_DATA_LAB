/**
 * Read-only projection of supplied trace events. Correlation fields are copied
 * from explicit source identifiers; this contract grants no execution authority.
 */

export interface TraceEventSource {
  event_id: string;
  trace_id: string;
  sequence: number;
  name: string;
  kind: string;
  status: string;
  parent_event_id?: string | null;
  attributes?: Record<string, unknown>;
  evidence_refs?: string[];
}

export interface TraceSource {
  trace_id: string;
  run_id: string;
  events: TraceEventSource[];
}

export interface TraceCorrelations {
  /** Present only when supplied as attributes.agent_id. */
  agentId?: string;
  /** Present only when supplied as attributes.tool_call_id. */
  toolCallId?: string;
  proposalId?: string;
  requestId?: string;
  claimId?: string;
  actionId?: string;
  executionId?: string;
  executionRequestId?: string;
  permitId?: string;
  receiptId?: string;
}

export interface TraceTimelineEvent {
  eventId: string;
  traceId: string;
  sequence: number;
  name: string;
  kind: string;
  /** Verbatim source outcome; errors and denials must never become success. */
  status: string;
  parentEventId?: string;
  parentState: "root" | "resolved" | "missing";
  /** Run identity is taken from the supplied trace envelope. */
  runId: string;
  correlations: TraceCorrelations;
  /** Values and redaction markers pass through without interpretation. */
  attributes: Record<string, unknown>;
  evidenceRefs: string[];
}

export interface TraceGap {
  kind: "sequence_gap" | "missing_parent" | "duplicate_event_id" | "trace_id_mismatch" | "invalid_sequence";
  eventId?: string;
  detail: string;
}

export interface TraceTimeline {
  traceId: string;
  runId: string;
  events: TraceTimelineEvent[];
  gaps: TraceGap[];
  /** Display order is supplied sequence; parent links separately describe causality. */
  chronology: "sequence";
  causality: "parent_event_id";
}

/** Contract-level validation; data gaps remain inspectable and are not repaired. */
export function validateTraceTimeline(value: TraceTimeline): string[] {
  const errors: string[] = [];
  if (!value.traceId?.trim() || !value.runId?.trim()) errors.push("trace and run ids are required");
  const ids = new Set<string>();
  let previousSequence = -1;
  for (const event of value.events) {
    if (!event.eventId?.trim()) errors.push("event id is required");
    if (ids.has(event.eventId)) errors.push(`duplicate event id: ${event.eventId}`);
    ids.add(event.eventId);
    if (!Number.isInteger(event.sequence) || event.sequence < 0) errors.push(`invalid sequence for event ${event.eventId}`);
    if (event.sequence < previousSequence) errors.push("events must be ordered by sequence");
    previousSequence = event.sequence;
    if (!event.status?.trim()) errors.push(`status is required for event ${event.eventId}`);
    if (event.parentState === "missing" && !value.gaps.some(gap => gap.kind === "missing_parent" && gap.eventId === event.eventId)) {
      errors.push(`missing parent is not represented as a gap for event ${event.eventId}`);
    }
  }
  return errors;
}
