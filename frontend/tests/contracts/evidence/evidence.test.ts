import assert from "node:assert/strict";
import { test } from "node:test";
import {
  assessEvidenceFreshness,
  canonicalDecisionJson,
  evidenceFromRetrievalHit,
  validateDecisionConclusion,
  type DecisionConclusion,
} from "../../../src/contracts/decision/evidence";

const sample = (): DecisionConclusion => ({
  schema: "decision-conclusion/v1",
  id: "conclusion-1",
  runId: "agent_run_1",
  text: "Policy v2 is active and QA validates it.",
  claims: [
    { id: "claim-policy", text: "Policy v2 is active.", evidence: [{ evidenceId: "policy-v2", relation: "supports" }] },
    { id: "claim-qa", text: "QA validates the policy.", evidence: [{ evidenceId: "qa", relation: "supports" }, { evidenceId: "policy-v2", relation: "contradicts" }] },
    { id: "claim-unbound", text: "No evidence supplied.", evidence: [] },
  ],
  evidence: [
    { id: "policy-v2", artifactRef: "fixtures/policy.md#revision=2", sourceIdentity: "fixtures/policy.md", snapshot: { sourceUri: "fixtures/policy.md", revision: "2", chunkId: "p2" }, freshness: "unknown" },
    { id: "qa", artifactRef: "fixtures/qa.md#revision=1", freshness: "unknown" },
  ],
});

test("unsupported claims remain explicit and multiple or contradictory links are retained", () => {
  const conclusion = sample();
  assert.deepEqual(validateDecisionConclusion(conclusion), []);
  assert.deepEqual(conclusion.claims[2].evidence, []);
  assert.equal(conclusion.claims[1].evidence.length, 2);
  assert.equal(conclusion.claims[1].evidence[1].relation, "contradicts");
});

test("stale, current, and missing snapshot identity are distinguished", () => {
  const snapshot = { sourceUri: "fixtures/policy.md", revision: "2", chunkId: "p2" };
  assert.equal(assessEvidenceFreshness(snapshot, { sourceUri: "fixtures/policy.md", revision: "3", chunkId: "p2" }), "stale");
  assert.equal(assessEvidenceFreshness(snapshot, { sourceUri: "fixtures/policy.md", revision: "2" }), "current");
  assert.equal(assessEvidenceFreshness(snapshot, undefined), "unknown");
  assert.equal(assessEvidenceFreshness({ sourceUri: "fixtures/policy.md" }, { sourceUri: "fixtures/policy.md", revision: "2" }), "unknown");
});

test("retrieval adapter carries supplied source and revision, but never asserts freshness", () => {
  const evidence = evidenceFromRetrievalHit({
    chunk_id: "policy-v2",
    document_id: "policy",
    evidence: { citation: "fixtures/policy.md#revision=2", chunk_id: "policy-v2", document_id: "policy", source_uri: "fixtures/policy.md", revision: "2" },
  });
  assert.equal(evidence.id, "fixtures/policy.md#revision=2");
  assert.equal(evidence.snapshot?.revision, "2");
  assert.equal(evidence.freshness, "unknown");
  const missing = evidenceFromRetrievalHit({});
  assert.equal(missing.id, "");
  assert.equal(missing.snapshot, undefined);
});

test("references must resolve and serialization is key-order deterministic", () => {
  const invalid = sample();
  invalid.claims[0].evidence.push({ evidenceId: "missing", relation: "supports" });
  assert.ok(validateDecisionConclusion(invalid).some(error => error.includes("unknown evidence")));
  assert.equal(canonicalDecisionJson({ z: 1, a: { y: 2, x: 3 } }), canonicalDecisionJson({ a: { x: 3, y: 2 }, z: 1 }));
});
