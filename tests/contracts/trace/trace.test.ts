import assert from "node:assert/strict";
import { test } from "node:test";
import { localTraceToTimeline } from "../../../src/adapters/trace/localTraceAdapter";
import { validateTraceTimeline, type TraceSource } from "../../../src/contracts/trace/trace";

const sample = (): TraceSource => ({
  trace_id: "trace-1", run_id: "run-1",
  events: [
    { event_id: "tool", trace_id: "trace-1", sequence: 2, name: "tool_call", kind: "tool", status: "ERROR", parent_event_id: "absent", attributes: { request_id: "req-1", payload: "[REDACTED]" }, evidence_refs: [] },
    { event_id: "root", trace_id: "trace-1", sequence: 0, name: "agent.run", kind: "workflow", status: "COMPLETED", attributes: {}, evidence_refs: [] },
  ],
});

test("sorts chronology while preserving explicit parent causality and missing gaps", () => {
  const timeline = localTraceToTimeline(sample());
  assert.deepEqual(timeline.events.map(event => event.sequence), [0, 2]);
  assert.equal(timeline.events[1].parentState, "missing");
  assert.equal(timeline.events[1].status, "ERROR");
  assert.equal(timeline.gaps.some(gap => gap.kind === "sequence_gap"), true);
  assert.equal(timeline.gaps.some(gap => gap.kind === "missing_parent"), true);
  assert.equal(timeline.chronology, "sequence");
  assert.equal(timeline.causality, "parent_event_id");
});

test("copies explicit BER and decision identifiers without deriving missing correlations", () => {
  const value = sample();
  value.events[0].attributes = {
    proposal_id: "proposal-1", request_id: "request-1", tool_call_id: "call-1",
    claim_id: "claim-1", action_id: "action-1", execution_id: "execution-1",
    execution_request_id: "exec-request-1", permit_id: "permit-1", receipt_id: "receipt-1",
  };
  const event = localTraceToTimeline(value).events.find(item => item.eventId === "tool")!;
  assert.deepEqual(event.correlations, {
    toolCallId: "call-1", proposalId: "proposal-1", requestId: "request-1",
    claimId: "claim-1", actionId: "action-1", executionId: "execution-1",
    executionRequestId: "exec-request-1", permitId: "permit-1", receiptId: "receipt-1",
  });
  assert.equal(event.runId, "run-1");
  const absent = localTraceToTimeline(sample()).events.find(item => item.eventId === "tool")!;
  assert.deepEqual(absent.correlations, { requestId: "req-1" });
  assert.equal((absent.correlations as Record<string, unknown>).toolCallId, undefined);
  assert.equal((absent.correlations as Record<string, unknown>).receiptId, undefined);
});

test("retains duplicate event IDs, failed statuses, redaction markers and trace identity mismatches", () => {
  const value = sample();
  value.events[0].trace_id = "other-trace";
  value.events.push({ ...value.events[0], sequence: 3 });
  const timeline = localTraceToTimeline(value);
  assert.equal(timeline.events.filter(event => event.eventId === "tool").length, 2);
  assert.equal(timeline.events.find(event => event.eventId === "tool")?.status, "ERROR");
  assert.equal(timeline.events.find(event => event.eventId === "tool")?.attributes.payload, "[REDACTED]");
  assert.equal(timeline.gaps.some(gap => gap.kind === "duplicate_event_id"), true);
  assert.equal(timeline.gaps.some(gap => gap.kind === "trace_id_mismatch"), true);
  assert.ok(validateTraceTimeline(timeline).some(error => error.includes("duplicate event id")));
});

test("claim and action links are absent unless supplied on the event", () => {
  const event = localTraceToTimeline(sample()).events.find(item => item.eventId === "tool")!;
  assert.equal(event.correlations.claimId, undefined);
  assert.equal(event.correlations.actionId, undefined);
});
