/**
 * Read-only decision/evidence projection over ADL AgentRun and RetrievalResponse.
 * This contract records supplied observations; it is not authorization or BER authority.
 */

export type EvidenceRelation = "supports" | "contradicts" | "context_only" | "insufficient";
export type EvidenceFreshness = "current" | "stale" | "unknown";

/** Fields supplied by RetrievalResponse.EvidenceRef; absent provenance stays absent. */
export interface EvidenceSnapshotIdentity {
  chunkId?: string;
  documentId?: string;
  sourceUri?: string;
  revision?: string;
}

export interface DecisionEvidence {
  /** Stable reference supplied by the source adapter, commonly EvidenceRef.citation. */
  id: string;
  artifactRef?: string;
  sourceIdentity?: string;
  snapshot?: EvidenceSnapshotIdentity;
  freshness: EvidenceFreshness;
  /** Supplied digest/version only; this contract never computes content identity. */
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
  /** Explicitly empty means no evidence is linked; it does not imply support. */
  evidence: ClaimEvidenceLink[];
  confidence?: number;
}

export interface DecisionConclusion {
  schema: "decision-conclusion/v1";
  id: string;
  runId?: string;
  text: string;
  /** Claim decomposition is supplied by a consumer, never inferred from answer text. */
  claims: DecisionClaim[];
  evidence: DecisionEvidence[];
  confidence?: number;
}

export type ExpectedEvidenceSnapshot = EvidenceSnapshotIdentity;

/** Freshness is unknown unless an explicit expected identity is comparable. */
export function assessEvidenceFreshness(
  actual: EvidenceSnapshotIdentity | undefined,
  expected: ExpectedEvidenceSnapshot | undefined,
): EvidenceFreshness {
  if (!actual || !expected) return "unknown";
  const keys: Array<keyof EvidenceSnapshotIdentity> = ["sourceUri", "revision", "chunkId", "documentId"];
  let compared = false;
  for (const key of keys) {
    const expectedValue = expected[key];
    if (expectedValue === undefined || expectedValue === "") continue;
    compared = true;
    const actualValue = actual[key];
    if (actualValue === undefined || actualValue === "") return "unknown";
    if (actualValue !== expectedValue) return "stale";
  }
  return compared ? "current" : "unknown";
}

/** Maps an actual ADL retrieval hit without inventing a source, revision or freshness. */
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

/** Stable JSON for contract fingerprints; array order remains semantically significant. */
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
  if (!value || typeof value !== "object") return ["conclusion must be an object"];
  if (value.schema !== "decision-conclusion/v1") errors.push("unsupported schema");
  if (!value.id?.trim()) errors.push("conclusion id is required");
  if (!Array.isArray(value.claims) || !Array.isArray(value.evidence)) return [...errors, "claims and evidence must be arrays"];
  if (value.confidence !== undefined && (!Number.isFinite(value.confidence) || value.confidence < 0 || value.confidence > 1)) errors.push("conclusion confidence must be between 0 and 1");
  const evidenceIds = new Set<string>();
  for (const item of value.evidence) {
    if (!item.id?.trim()) errors.push("evidence id is required");
    else if (evidenceIds.has(item.id)) errors.push(`evidence id is duplicated: ${item.id}`);
    evidenceIds.add(item.id);
    if (!["current", "stale", "unknown"].includes(item.freshness)) errors.push(`evidence ${item.id} has invalid freshness`);
  }
  const claimIds = new Set<string>();
  for (const claim of value.claims) {
    if (!claim.id?.trim() || claimIds.has(claim.id)) errors.push(`claim id is empty or duplicated: ${claim.id}`);
    claimIds.add(claim.id);
    if (!Array.isArray(claim.evidence)) { errors.push(`claim ${claim.id} evidence must be an explicit array`); continue; }
    if (claim.confidence !== undefined && (!Number.isFinite(claim.confidence) || claim.confidence < 0 || claim.confidence > 1)) errors.push(`claim ${claim.id} confidence must be between 0 and 1`);
    for (const link of claim.evidence) {
      if (!evidenceIds.has(link.evidenceId)) errors.push(`claim ${claim.id} references unknown evidence ${link.evidenceId}`);
      if (!["supports", "contradicts", "context_only", "insufficient"].includes(link.relation)) errors.push(`claim ${claim.id} has invalid evidence relation`);
    }
  }
  return errors;
}
