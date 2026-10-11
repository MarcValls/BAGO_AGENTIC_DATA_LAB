/** Decision Inspector evidence contract, mapped to the existing AgentRun and retrieval artifacts. */

export type EvidenceRelation = "supports" | "contradicts" | "context_only" | "insufficient";
export type EvidenceFreshness = "current" | "stale" | "unknown";

/** Identity supplied by RetrievalResponse.EvidenceRef; absent fields stay absent. */
export interface EvidenceSnapshotIdentity {
  chunkId?: string;
  documentId?: string;
  sourceUri?: string;
  revision?: string;
}

export interface DecisionEvidence {
  /** Stable reference, normally EvidenceRef.citation from RetrievalResponse. */
  id: string;
  artifactRef?: string;
  sourceIdentity?: string;
  snapshot?: EvidenceSnapshotIdentity;
  freshness: EvidenceFreshness;
  /** Optional digest or artifact version supplied by the source; never synthesized. */
  contentFingerprint?: string;
  excerpt?: string;
}

export interface ClaimEvidenceLink {
  evidenceId: string;
  relation: EvidenceRelation;
}

export interface DecisionClaim {
  id: string;
  text: string;
  /** Explicitly empty means unsupported or evidence was not attached. */
  evidence: ClaimEvidenceLink[];
  confidence?: number;
}

export interface DecisionConclusion {
  schema: "decision-conclusion/v1";
  id: string;
  runId?: string;
  text: string;
  claims: DecisionClaim[];
  evidence: DecisionEvidence[];
  confidence?: number;
}

export interface ExpectedEvidenceSnapshot {
  sourceUri?: string;
  revision?: string;
  chunkId?: string;
  documentId?: string;
}

/** Preserve unknown freshness when there is no comparison snapshot. */
export function assessEvidenceFreshness(
  actual: EvidenceSnapshotIdentity | undefined,
  expected: ExpectedEvidenceSnapshot | undefined,
): EvidenceFreshness {
  if (!actual || !expected) return "unknown";
  const compared: Array<keyof ExpectedEvidenceSnapshot> = ["sourceUri", "revision", "chunkId", "documentId"];
  let hasComparableIdentity = false;
  for (const key of compared) {
    const expectedValue = expected[key];
    if (expectedValue === undefined || expectedValue === "") continue;
    hasComparableIdentity = true;
    const actualValue = actual[key];
    if (actualValue === undefined || actualValue === "") return "unknown";
    if (actualValue !== expectedValue) return "stale";
  }
  return hasComparableIdentity ? "current" : "unknown";
}

/** Adapt a RetrievalResponse hit without guessing provenance or freshness. */
export function evidenceFromRetrievalHit(hit: {
  evidence?: { citation?: string; chunk_id?: string; document_id?: string; source_uri?: string; revision?: string };
  chunk_id?: string;
  document_id?: string;
}): DecisionEvidence {
  const source = hit.evidence;
  const snapshot: EvidenceSnapshotIdentity = {
    ...(source?.chunk_id || hit.chunk_id ? { chunkId: source?.chunk_id || hit.chunk_id } : {}),
    ...(source?.document_id || hit.document_id ? { documentId: source?.document_id || hit.document_id } : {}),
    ...(source?.source_uri ? { sourceUri: source.source_uri } : {}),
    ...(source?.revision ? { revision: source.revision } : {}),
  };
  const id = source?.citation || "";
  return {
    id,
    ...(id ? { artifactRef: id } : {}),
    ...(source?.source_uri ? { sourceIdentity: source.source_uri } : {}),
    ...(Object.keys(snapshot).length ? { snapshot } : {}),
    freshness: "unknown",
  };
}

/** Deterministic JSON representation for fingerprints and reproducible handoffs. */
export function canonicalDecisionJson(value: unknown): string {
  const normalize = (item: unknown): unknown => {
    if (Array.isArray(item)) return item.map(normalize);
    if (item !== null && typeof item === "object") {
      return Object.fromEntries(Object.entries(item as Record<string, unknown>)
        .filter(([, child]) => child !== undefined)
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([key, child]) => [key, normalize(child)]));
    }
    return item;
  };
  return JSON.stringify(normalize(value));
}

export function validateDecisionConclusion(value: DecisionConclusion): string[] {
  const errors: string[] = [];
  if (value.schema !== "decision-conclusion/v1") errors.push("unsupported schema");
  if (!value.id.trim()) errors.push("conclusion id is required");
  if (!Array.isArray(value.claims) || !Array.isArray(value.evidence)) errors.push("claims and evidence must be arrays");
  if (value.confidence !== undefined && (value.confidence < 0 || value.confidence > 1)) errors.push("conclusion confidence must be between 0 and 1");
  const evidenceIds = new Set(value.evidence.map(item => item.id));
  if (evidenceIds.size !== value.evidence.length) errors.push("evidence ids must be unique");
  const claimIds = new Set<string>();
  for (const claim of value.claims) {
    if (!claim.id.trim() || claimIds.has(claim.id)) errors.push(`claim id is empty or duplicated: ${claim.id}`);
    claimIds.add(claim.id);
    if (!Array.isArray(claim.evidence)) errors.push(`claim ${claim.id} evidence must be an explicit array`);
    if (claim.confidence !== undefined && (claim.confidence < 0 || claim.confidence > 1)) errors.push(`claim ${claim.id} confidence must be between 0 and 1`);
    for (const link of claim.evidence) {
      if (!evidenceIds.has(link.evidenceId)) errors.push(`claim ${claim.id} references unknown evidence ${link.evidenceId}`);
    }
  }
  for (const item of value.evidence) {
    if (!item.id.trim()) errors.push("evidence id is required");
    if (!["current", "stale", "unknown"].includes(item.freshness)) errors.push(`evidence ${item.id} has invalid freshness`);
  }
  return errors;
}
