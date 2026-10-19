# Decision evidence contract v1

Status: **PREPARED** for W02; frozen when the teamctl handoff validates.

## Mapping to existing artifacts

`AgentRun.to_dict()` supplies the run id, answer, citations and `retrieval` payload. `RetrievalResponse.to_dict()` supplies hits whose `evidence` is the serialized `EvidenceRef`: citation, chunk id, document id, source URI and revision. The W02 TypeScript `DecisionConclusion` is an inspection view over those existing artifacts; it is not a new execution or evidence authority. Claim decomposition is supplied by the consumer and must not be fabricated from an answer automatically.

W02 contract owner: `src/contracts/decision/evidence.ts`. Contract tests:
`tests/contracts/evidence/evidence.test.ts`. The existing frontend copy at
`frontend/src/contracts/decision/evidence.ts` predates this mission and remains
in its existing frontend scope; it is not silently treated as W02's source of
truth. The inspector consumers must reconcile/import this frozen contract in a
separately scoped integration work item before claiming they consume it.

## Contract

- A conclusion has an explicit ordered claim list and evidence inventory. Confidence is optional metadata in `[0, 1]`, never proof.
- Each claim has an explicit evidence-link array; empty means no linked evidence. Links state `supports`, `contradicts`, `context_only`, or `insufficient` independently.
- Evidence may retain its source reference and retrieval snapshot identity. Missing source/revision remains missing; the adapter does not derive it from citation text.
- Freshness is `unknown` unless an actual identity can be compared with an expected identity. A known mismatch is `stale`; matching supplied fields are `current`. No evidence object is silently dropped when stale.
- `canonicalDecisionJson` sorts object keys recursively while preserving array order and omitting undefined object properties for stable serialization.
- Validation checks explicit arrays, unique identifiers, link resolution, relation vocabulary and confidence bounds. It does not claim that a citation's contents support its claim.

## Limits and consumer guidance

The current AgentRun answer/citations alone do not contain human-reviewed claim decomposition or a content digest. Consumers must preserve that gap. Retrieval hit metadata can populate the available source and snapshot fields. `LocalTrace.evidence_refs` is a separate trace relation; W04 owns its mapping. This contract does not resolve citations to files, verify artifact bytes, or certify semantic entailment.

## Verification

Compile `src/contracts/decision/evidence.ts` and
`tests/contracts/evidence/evidence.test.ts` with the repository TypeScript
compiler using strict mode, then run the emitted test with `node --test`.
Contract tests cover unsupported claims, multiple and contradictory evidence,
stale/current/unknown snapshot identity, missing provenance, unresolved links,
invalid relations and deterministic serialization.
