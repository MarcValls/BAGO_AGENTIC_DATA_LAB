import assert from "node:assert/strict";
import { test } from "node:test";
import { actionBundleFromAgentRun } from "../../../src/adapters/action/agentRun";
import { validateActionBundle } from "../../../src/contracts/action/action";

test("proposal intent, eligibility, capability, authorization, availability and execution stay separate", () => {
  const bundle = actionBundleFromAgentRun({
    run_id: "run-1",
    proposals: [{ proposal_id: "proposal-1", request_id: "request-1", tool_name: "publish", effect_type: "WRITE", rationale: "Requested by the run", decision: "REQUIRE_HUMAN", called: false }],
  });
  const action = bundle.actions[0];
  assert.equal(action.proposalState, "proposed");
  assert.equal(action.risk, "mutating");
  assert.equal(action.approval, "required");
  assert.equal(action.eligibility.state, "unknown");
  assert.equal(action.capability.state, "unknown");
  assert.equal(action.availability.state, "unknown");
  assert.equal(action.authorization.state, "requires_approval");
  assert.equal(action.execution.state, "not_started");
  assert.equal(action.receiptLink.state, "missing");
  assert.deepEqual(validateActionBundle(bundle), []);
});

test("expired and revoked permits are distinguished from the recorded authorization decision", () => {
  const expired = actionBundleFromAgentRun({ proposals: [{ proposal_id: "p-expired", decision: "ALLOW", permit_id: "permit-expired" }] }, {
    permits: { "permit-expired": { issued_at: "2025-01-01T00:00:00Z", expires_at: "2025-01-02T00:00:00Z" } },
    asOf: "2025-01-03T00:00:00Z",
  }).actions[0];
  assert.equal(expired.authorization.state, "authorized");
  assert.equal(expired.authorization.permitValidity, "expired");
  const revoked = actionBundleFromAgentRun({ proposals: [{ decision: "ALLOW", permit_id: "p" }] }, {
    permits: { p: { revoked: true } },
  }).actions[0];
  assert.equal(revoked.authorization.state, "authorized");
  assert.equal(revoked.authorization.permitValidity, "revoked");
});

test("denial and execution failure retain source reason and receipt evidence", () => {
  const bundle = actionBundleFromAgentRun({
    proposals: [{ proposal_id: "p-denied", request_id: "r-denied", tool_name: "delete", effect_type: "DELETE", decision: "DENY", called: false, outcome: "FAILURE", receipt_id: "receipt-denied", error_message: "policy denied" }],
    decision_receipts: [{ receipt_id: "receipt-denied", request_id: "r-denied", decision: "DENY", execution_outcome: "FAILURE", actual_effect: {}, evidence_refs: ["trace://event-1"], error_message: "policy denied" }],
  });
  const action = bundle.actions[0];
  assert.equal(action.authorization.state, "rejected");
  assert.equal(action.authorization.reason, "policy denied");
  assert.equal(action.execution.state, "failed");
  assert.equal(action.receiptLink.state, "matched");
  assert.equal(action.receiptLink.receipt?.evidenceRefs[0], "trace://event-1");
  assert.equal(action.receiptLink.receipt?.source, "adl-agent-run");
});

test("success without receipt and mismatched request, permit or effect is never success", () => {
  const missing = actionBundleFromAgentRun({
    proposals: [{ proposal_id: "p-missing", request_id: "r-missing", decision: "ALLOW", called: true, outcome: "SUCCESS", receipt_id: "receipt-absent" }],
  }).actions[0];
  assert.equal(missing.receiptLink.state, "missing");
  assert.equal(missing.execution.state, "unverified");
  assert.deepEqual(validateActionBundle({ schema: "governed-action-bundle/v1", actions: [missing] }), []);

  const mismatch = actionBundleFromAgentRun({
    proposals: [{ request_id: "r-1", decision: "ALLOW", permit_id: "permit-1", effect_type: "WRITE", called: true, outcome: "SUCCESS", receipt_id: "receipt-1" }],
    mcp_receipts: [{ receipt_id: "receipt-1", request_id: "r-other", permit_id: "permit-other", effect_type: "DELETE", execution_outcome: "SUCCESS", evidence_refs: [] }],
  }).actions[0];
  assert.equal(mismatch.receiptLink.state, "mismatch");
  assert.equal(mismatch.execution.state, "unverified");
});

test("receipt is not matched without exact request and permit identities", () => {
  const noRequest = actionBundleFromAgentRun({
    proposals: [{ receipt_id: "receipt-1", permit_id: "permit-1" }],
    mcp_receipts: [{ receipt_id: "receipt-1", permit_id: "permit-1" }],
  }).actions[0];
  assert.equal(noRequest.receiptLink.state, "mismatch");
  const noPermit = actionBundleFromAgentRun({
    proposals: [{ request_id: "r-1", receipt_id: "receipt-2", permit_id: "permit-2" }],
    mcp_receipts: [{ receipt_id: "receipt-2", request_id: "r-1" }],
  }).actions[0];
  assert.equal(noPermit.receiptLink.state, "mismatch");
});

test("duplicate receipt candidates and unprovided proposal IDs remain explicit", () => {
  const bundle = actionBundleFromAgentRun({
    proposals: [{ request_id: "r-1" }],
    decision_receipts: [{ receipt_id: "a", request_id: "r-1" }],
    mcp_receipts: [{ receipt_id: "b", request_id: "r-1" }],
  });
  assert.equal(bundle.actions[0].id, undefined);
  assert.equal(bundle.actions[0].authorization.state, "unknown");
  assert.equal(bundle.actions[0].receiptLink.state, "mismatch");
  assert.deepEqual(validateActionBundle(bundle), []);
});
