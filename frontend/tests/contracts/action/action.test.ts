import assert from "node:assert/strict";
import { test } from "node:test";
import { actionBundleFromAgentRun } from "../../../src/adapters/action/agentRun";
import { validateActionBundle } from "../../../src/contracts/action/action";

test("proposal, authorization, availability and execution remain distinct", () => {
  const bundle = actionBundleFromAgentRun({
    run_id: "run-1",
    proposals: [{ proposal_id: "proposal-1", request_id: "request-1", tool_name: "publish", effect_type: "WRITE", rationale: "Requested by the run", decision: "REQUIRE_HUMAN", called: false }],
  });
  const action = bundle.actions[0];
  assert.equal(action.risk, "mutating");
  assert.equal(action.approval, "required");
  assert.equal(action.eligibility.state, "unknown");
  assert.equal(action.capability.state, "unknown");
  assert.equal(action.availability.state, "unknown");
  assert.equal(action.authorization.state, "requires_approval");
  assert.equal(action.execution.state, "not_started");
  assert.equal(action.receiptLink.state, "unknown");
  assert.deepEqual(validateActionBundle(bundle), []);
});

test("expired permit is separate from the recorded ALLOW decision", () => {
  const bundle = actionBundleFromAgentRun({
    proposals: [{ proposal_id: "p-expired", request_id: "r-expired", tool_name: "read", effect_type: "READ", decision: "ALLOW", permit_id: "permit-expired" }],
  }, {
    permits: { "permit-expired": { permit_id: "permit-expired", issued_at: "2025-01-01T00:00:00Z", expires_at: "2025-01-02T00:00:00Z", signed_by: "policy" } },
    asOf: "2025-01-03T00:00:00Z",
  });
  assert.equal(bundle.actions[0].authorization.state, "authorized");
  assert.equal(bundle.actions[0].authorization.permitValidity, "expired");
});

test("rejection and execution failure remain visible with their reason and receipt", () => {
  const bundle = actionBundleFromAgentRun({
    proposals: [{ proposal_id: "p-denied", request_id: "r-denied", tool_name: "delete", effect_type: "DELETE", decision: "DENY", called: false, outcome: "FAILURE", receipt_id: "receipt-denied", error_message: "policy denied" }],
    decision_receipts: [{ receipt_id: "receipt-denied", request_id: "r-denied", decision: "DENY", execution_outcome: "FAILURE", actual_effect: {}, evidence_refs: ["localtrace://event-1"], error_message: "policy denied" }],
  });
  const action = bundle.actions[0];
  assert.equal(action.authorization.state, "rejected");
  assert.equal(action.authorization.reason, "policy denied");
  assert.equal(action.execution.state, "failed");
  assert.equal(action.receiptLink.state, "matched");
  assert.equal(action.receiptLink.receipt?.evidenceRefs[0], "localtrace://event-1");
});

test("declared missing receipt and mismatched receipt are not treated as success", () => {
  const missing = actionBundleFromAgentRun({
    proposals: [{ proposal_id: "p-missing", request_id: "r-missing", decision: "ALLOW", called: true, outcome: "SUCCESS", receipt_id: "receipt-absent" }],
  });
  assert.equal(missing.actions[0].receiptLink.state, "missing");
  assert.equal(missing.actions[0].execution.state, "unverified");
  assert.ok(validateActionBundle(missing).length === 0);

  const mismatch = actionBundleFromAgentRun({
    proposals: [{ proposal_id: "p-mismatch", request_id: "r-1", decision: "ALLOW", permit_id: "permit-1", receipt_id: "receipt-1" }],
    mcp_receipts: [{ receipt_id: "receipt-1", request_id: "r-other", permit_id: "permit-other", execution_outcome: "SUCCESS", evidence_refs: [] }],
  });
  assert.equal(mismatch.actions[0].receiptLink.state, "mismatch");
});

test("receipt absence and unprovided action id stay unknown instead of being synthesized", () => {
  const bundle = actionBundleFromAgentRun({ proposals: [{ request_id: "r-unknown" }] });
  assert.equal(bundle.actions[0].id, undefined);
  assert.equal(bundle.actions[0].authorization.state, "unknown");
  assert.equal(bundle.actions[0].execution.state, "unknown");
  assert.equal(bundle.actions[0].receiptLink.state, "unknown");
  assert.deepEqual(validateActionBundle(bundle), []);
});
