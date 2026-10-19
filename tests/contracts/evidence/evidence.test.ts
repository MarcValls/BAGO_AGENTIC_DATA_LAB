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
  runId: "run-1",
  text: "Observed answer; claim decomposition supplied explicitly.",
  claims: [
    { id: "claim-supported", text: "Policy v2 is active.", evidence: [{ evidenceId: "policy-v2", relation: "supports" }] },
    { id: "claim-conflict", text: "QA validates policy v2.", evidence: [{ evidenceId: "qa", relation: "supports" }, { evidenceId: "policy-v2", relation: "contradicts" }] },
    { id: "claim-unsupported", text: "No evidence supplied.", evidence: [] },
  ],
  evidence: [
    { id: "policy-v2", artifactRef: "docs/policy.md#revision=2", sourceIdentity: "docs/policy.md", snapshot: { sourceUri: "docs/policy.md", revision: "2", chunkId: "p2", documentId: "policy" }, freshness: "unknown" },
    { id: "qa", freshness: "unknown" },
  ],
});

test("unsupported claims remain unsupported and multiple contradictory links are explicit", () => {
  const value = sample();
  assert.deepEqual(validateDecisionConclusion(value), []);
  assert.deepEqual(value.claims[2].evidence, []);
  assert.equal(value.claims[1].evidence.length, 2);
  assert.equal(value.claims[1].evidence[1].relation, "contradicts");
});

test("unknown, stale and current snapshot identity are distinguished", () => {
  const actual = { sourceUri: "docs/policy.md", revision: "2", chunkId: "p2" };
  assert.equal(assessEvidenceFreshness(actual, { sourceUri: "docs/policy.md", revision: "3" }), "stale");
  assert.equal(assessEvidenceFreshness(actual, { sourceUri: "docs/policy.md", revision: "2" }), "current");
  assert.equal(assessEvidenceFreshness(actual, undefined), "unknown");
  assert.equal(assessEvidenceFreshness({ sourceUri: "docs/policy.md" }, { sourceUri: "docs/policy.md", revision: "2" }), "unknown");
});

test("ADL retrieval adapter preserves supplied identity but does not assert freshness", () => {
  const evidence = evidenceFromRetrievalHit({
    chunk_id: "p2",
    document_id: "policy",
    evidence: { citation: "docs/policy.md#revision=2", chunk_id: "p2", document_id: "policy", source_uri: "docs/policy.md", revision: "2" },
  });
  assert.equal(evidence.id, "docs/policy.md#revision=2");
  assert.equal(evidence.snapshot?.revision, "2");
  assert.equal(evidence.freshness, "unknown");
  const missing = evidenceFromRetrievalHit({});
  assert.equal(missing.id, "");
  assert.equal(missing.snapshot, undefined);
  assert.equal(missing.sourceIdentity, undefined);
});

test("references resolve, invalid relations fail, and canonical serialization is deterministic", () => {
  const invalid = sample();
  invalid.claims[0].evidence.push({ evidenceId: "missing", relation: "supports" });
  assert.ok(validateDecisionConclusion(invalid).some(error => error.includes("unknown evidence")));
  const malformed = sample();
  (malformed.claims[0].evidence[0] as { relation: string }).relation = "guessed";
  assert.ok(validateDecisionConclusion(malformed).some(error => error.includes("invalid evidence relation")));
  assert.equal(canonicalDecisionJson({ z: 1, a: { y: 2, x: 3 } }), canonicalDecisionJson({ a: { x: 3, y: 2 }, z: 1 }));
});
