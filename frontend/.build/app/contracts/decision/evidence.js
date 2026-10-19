/**
 * Read-only decision/evidence projection over ADL AgentRun and RetrievalResponse.
 * This contract records supplied observations; it is not authorization or BER authority.
 */
/** Freshness is unknown unless an explicit expected identity is comparable. */
export function assessEvidenceFreshness(actual, expected) {
    if (!actual || !expected)
        return "unknown";
    const keys = ["sourceUri", "revision", "chunkId", "documentId"];
    let compared = false;
    for (const key of keys) {
        const expectedValue = expected[key];
        if (expectedValue === undefined || expectedValue === "")
            continue;
        compared = true;
        const actualValue = actual[key];
        if (actualValue === undefined || actualValue === "")
            return "unknown";
        if (actualValue !== expectedValue)
            return "stale";
    }
    return compared ? "current" : "unknown";
}
/** Maps an actual ADL retrieval hit without inventing a source, revision or freshness. */
export function evidenceFromRetrievalHit(hit) {
    const source = hit.evidence;
    const snapshot = {
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
export function canonicalDecisionJson(value) {
    const normalize = (item) => {
        if (Array.isArray(item))
            return item.map(normalize);
        if (item !== null && typeof item === "object") {
            return Object.fromEntries(Object.entries(item)
                .filter(([, child]) => child !== undefined)
                .sort(([left], [right]) => left.localeCompare(right))
                .map(([key, child]) => [key, normalize(child)]));
        }
        return item;
    };
    return JSON.stringify(normalize(value));
}
export function validateDecisionConclusion(value) {
    const errors = [];
    if (!value || typeof value !== "object")
        return ["conclusion must be an object"];
    if (value.schema !== "decision-conclusion/v1")
        errors.push("unsupported schema");
    if (!value.id?.trim())
        errors.push("conclusion id is required");
    if (!Array.isArray(value.claims) || !Array.isArray(value.evidence))
        return [...errors, "claims and evidence must be arrays"];
    if (value.confidence !== undefined && (!Number.isFinite(value.confidence) || value.confidence < 0 || value.confidence > 1))
        errors.push("conclusion confidence must be between 0 and 1");
    const evidenceIds = new Set();
    for (const item of value.evidence) {
        if (!item.id?.trim())
            errors.push("evidence id is required");
        else if (evidenceIds.has(item.id))
            errors.push(`evidence id is duplicated: ${item.id}`);
        evidenceIds.add(item.id);
        if (!["current", "stale", "unknown"].includes(item.freshness))
            errors.push(`evidence ${item.id} has invalid freshness`);
    }
    const claimIds = new Set();
    for (const claim of value.claims) {
        if (!claim.id?.trim() || claimIds.has(claim.id))
            errors.push(`claim id is empty or duplicated: ${claim.id}`);
        claimIds.add(claim.id);
        if (!Array.isArray(claim.evidence)) {
            errors.push(`claim ${claim.id} evidence must be an explicit array`);
            continue;
        }
        if (claim.confidence !== undefined && (!Number.isFinite(claim.confidence) || claim.confidence < 0 || claim.confidence > 1))
            errors.push(`claim ${claim.id} confidence must be between 0 and 1`);
        for (const link of claim.evidence) {
            if (!evidenceIds.has(link.evidenceId))
                errors.push(`claim ${claim.id} references unknown evidence ${link.evidenceId}`);
            if (!["supports", "contradicts", "context_only", "insufficient"].includes(link.relation))
                errors.push(`claim ${claim.id} has invalid evidence relation`);
        }
    }
    return errors;
}
