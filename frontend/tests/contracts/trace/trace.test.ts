import assert from "node:assert/strict";
import { test } from "node:test";
import { localTraceToTimeline } from "../../../src/adapters/trace/localTraceAdapter";
import { validateTraceTimeline, type LocalTraceRecord } from "../../../src/contracts/trace/trace";

const source = (): LocalTraceRecord => ({
  trace_id: "trace-1", run_id: "run-1",
  events: [
    { event_id: "child", trace_id: "trace-1", sequence: 2, name: "tool_call", kind: "tool", status: "ERROR", parent_event_id: "absent", attributes: { request_id: "req-1", payload: "[REDACTED]" }, evidence_refs: [] },
    { event_id: "root", trace_id: "trace-1", sequence: 0, name: "agent.run", kind: "workflow", status: "COMPLETED", attributes: {}, evidence_refs: [] },
  ],
});

test("sequence chronology is sorted independently from parent causality and reports gaps", () => {
  const timeline = localTraceToTimeline(source());
  assert.deepEqual(timeline.events.map(event => event.sequence), [0, 2]);
  assert.equal(timeline.events[1].parentState, "missing");
  assert.equal(timeline.events[1].status, "ERROR");
  assert.equal(timeline.gaps.some(gap => gap.kind === "sequence_gap"), true);
  assert.equal(timeline.gaps.some(gap => gap.kind === "missing_parent"), true);
  assert.equal(timeline.causality, "parent_event_id");
});

test("correlations remain absent unless explicitly supplied; failures and redaction pass through", () => {
  const timeline = localTraceToTimeline(source());
  const event = timeline.events[1];
  assert.equal(event.correlation.toolCallId, "req-1");
  assert.equal(event.correlation.claimState, "missing");
  assert.equal(event.correlation.actionState, "missing");
  assert.equal(event.attributes.payload, "[REDACTED]");
  assert.equal(event.status, "ERROR");
  assert.equal(timeline.jaegerCorrelation, "unavailable");
});

test("duplicate identities are retained and made visible rather than silently deduplicated", () => {
  const value = source();
  value.events.push({ ...value.events[0], sequence: 3 });
  const timeline = localTraceToTimeline(value);
  assert.equal(timeline.events.filter(event => event.eventId === "child").length, 2);
  assert.equal(timeline.gaps.some(gap => gap.kind === "duplicate_event_id"), true);
  assert.ok(validateTraceTimeline(timeline).some(error => error.includes("duplicate event id")));
});

test("explicit claim and action correlation is carried without inference", () => {
  const value = source();
  value.events[0].attributes = { claim_id: "claim-7", action_id: "action-2" };
  const event = localTraceToTimeline(value).events.find(item => item.eventId === "child")!;
  assert.equal(event.correlation.claimId, "claim-7");
  assert.equal(event.correlation.claimState, "linked");
  assert.equal(event.correlation.actionId, "action-2");
  assert.equal(event.correlation.actionState, "linked");
});
