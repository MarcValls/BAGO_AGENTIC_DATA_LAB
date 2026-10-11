import type {
  ActionInspectionBundle,
  ActionReceipt,
  ActionRisk,
  AuthorizationState,
  ProposedAction,
} from "../../contracts/action/action";

type Raw = Record<string, unknown>;

const text = (value: unknown): string | undefined => typeof value === "string" && value.length ? value : undefined;
const object = (value: unknown): Raw | undefined => value !== null && typeof value === "object" && !Array.isArray(value) ? value as Raw : undefined;
const arr = (value: unknown): Raw[] => Array.isArray(value) ? value.map(object).filter((item): item is Raw => Boolean(item)) : [];

function risk(effect: string | undefined): ActionRisk {
  if (!effect) return "unknown";
  if (effect === "READ") return "read_only";
  if (["WRITE", "CREATE", "DELETE"].includes(effect)) return "mutating";
  if (["EXTERNAL_API", "EXTERNAL_TOOL"].includes(effect)) return "external";
  return "unknown";
}

function authorization(decision: unknown, permit: Raw | undefined, asOf?: string): AuthorizationState {
  const normalized = text(decision)?.toUpperCase();
  if (normalized === "DENY") return "rejected";
  if (normalized === "REQUIRE_HUMAN") return "requires_approval";
  if (normalized !== "ALLOW") return "unknown";
  return "authorized";
}

function permitValidity(permit: Raw | undefined, asOf?: string): ProposedAction["authorization"]["permitValidity"] {
  if (!permit || !asOf) return "unknown";
  const issuedAt = text(permit.issued_at);
  const expiresAt = text(permit.expires_at);
  if (!issuedAt || !expiresAt) return "unknown";
  const now = Date.parse(asOf);
  const issued = Date.parse(issuedAt);
  const expires = Date.parse(expiresAt);
  if (![now, issued, expires].every(Number.isFinite)) return "unknown";
  if (now < issued) return "not_yet_valid";
  if (now > expires) return "expired";
  return "valid";
}

function receiptFrom(raw: Raw): ActionReceipt | undefined {
  const id = text(raw.receipt_id);
  if (!id) return undefined;
  const refs = Array.isArray(raw.evidence_refs) ? raw.evidence_refs.filter((item): item is string => typeof item === "string") : [];
  return {
    id,
    ...(text(raw.request_id) ? { requestId: text(raw.request_id) } : {}),
    ...(text(raw.permit_id) ? { permitId: text(raw.permit_id) } : {}),
    ...(text(raw.execution_outcome ?? raw.status) ? { outcome: text(raw.execution_outcome ?? raw.status) } : {}),
    ...(object(raw.actual_effect) ? { actualEffect: object(raw.actual_effect) } : {}),
    evidenceRefs: refs,
    ...(text(raw.error_message ?? raw.error_message) ? { error: text(raw.error_message) } : {}),
    ...(typeof raw.duration_ms === "number" ? { durationMs: raw.duration_ms } : {}),
  };
}

function executionState(called: unknown, outcome: unknown): ProposedAction["execution"]["state"] {
  const normalized = text(outcome)?.toUpperCase();
  if (normalized === "SUCCESS") return called === true ? "succeeded" : "unknown";
  if (normalized === "FAILURE" || normalized === "TIMEOUT" || normalized === "DENIED") return "failed";
  if (normalized === "PARTIAL") return "partial";
  if (called === false) return "not_started";
  return "unknown";
}

/** Project AgentRun proposals and their receipt streams into a display-only model. */
export function actionBundleFromAgentRun(
  run: { run_id?: string; proposals?: unknown; decision_receipts?: unknown; mcp_receipts?: unknown; provider_receipt?: unknown },
  options: {
    permits?: Record<string, Raw>;
    capabilityStates?: Record<string, "available" | "unavailable">;
    eligibility?: Record<string, { state: "eligible" | "ineligible"; reason?: string }>;
    availability?: Record<string, { state: "available" | "unavailable"; reason?: string }>;
    asOf?: string;
  } = {},
): ActionInspectionBundle {
  const runId = text(run.run_id);
  const receipts = [...arr(run.decision_receipts), ...arr(run.mcp_receipts)];
  const provider = object(run.provider_receipt);
  if (provider) receipts.push(provider);

  const actions = arr(run.proposals).map((proposal): ProposedAction => {
    const id = text(proposal.proposal_id);
    const requestId = text(proposal.request_id);
    const permitId = text(proposal.permit_id);
    const permit = (permitId && options.permits?.[permitId]) || undefined;
    const suppliedReceiptId = text(proposal.receipt_id);
    const candidates = receipts.filter(receipt => requestId && receipt.request_id === requestId);
    const exactReceipt = suppliedReceiptId ? receipts.find(receipt => receipt.receipt_id === suppliedReceiptId) : undefined;
    const selectedReceipt = exactReceipt ?? (!suppliedReceiptId && candidates.length === 1 ? candidates[0] : undefined);
    const normalizedReceipt = selectedReceipt ? receiptFrom(selectedReceipt) : undefined;
    const linkState: ProposedAction["receiptLink"]["state"] = selectedReceipt
      ? ((requestId && text(selectedReceipt.request_id) !== requestId) || (permitId && text(selectedReceipt.permit_id) && text(selectedReceipt.permit_id) !== permitId) ? "mismatch" : "matched")
      : suppliedReceiptId ? (candidates.some(candidate => text(candidate.receipt_id) !== suppliedReceiptId) ? "mismatch" : "missing") : candidates.length > 1 ? "mismatch" : candidates.length === 0 ? "unknown" : "missing";
    const decision = proposal.decision;
    const authState = authorization(decision, permit, options.asOf);
    const effectType = text(proposal.effect_type);
    const toolName = text(proposal.tool_name);
    const rawCalled = typeof proposal.called === "boolean" ? proposal.called : undefined;
    const outcome = text(proposal.outcome) ?? normalizedReceipt?.outcome;
    const mappedExecution = executionState(rawCalled, outcome);
    const verifiedExecution = mappedExecution === "succeeded" && linkState !== "matched" ? "unverified" : mappedExecution;
    const explicitAvailability = toolName ? options.availability?.[toolName] : undefined;
    const explicitEligibility = id ? options.eligibility?.[id] : undefined;
    const capabilityState = toolName ? options.capabilityStates?.[toolName] : undefined;
    const argumentsValue = object(proposal.arguments);
    const requestedDecision: AuthorizationState = authState;

    return {
      schema: "governed-action/v1",
      ...(id ? { id } : {}),
      ...(runId ? { runId } : {}),
      ...(requestId ? { requestId } : {}),
      ...(toolName ? { toolName } : {}),
      ...(text(proposal.transport) ? { transport: text(proposal.transport) } : {}),
      ...(effectType ? { effectType } : {}),
      ...(argumentsValue ? { arguments: argumentsValue } : {}),
      ...(text(proposal.proposed_by) ? { proposedBy: text(proposal.proposed_by) } : {}),
      ...(text(proposal.rationale) ? { proposalReason: text(proposal.rationale) } : {}),
      risk: risk(effectType),
      approval: text(decision)?.toUpperCase() === "REQUIRE_HUMAN" ? "required" : "unknown",
      capability: { state: capabilityState ?? "unknown", ...(toolName ? { name: toolName } : {}) },
      eligibility: explicitEligibility ?? { state: "unknown" },
      authorization: {
        state: requestedDecision,
        permitValidity: permitValidity(permit, options.asOf),
        ...(permitId ? { permitId } : {}),
        ...(text(permit?.signed_by) ? { actor: text(permit?.signed_by) } : {}),
        ...(text(permit?.rationale) ? { reason: text(permit?.rationale) } : requestedDecision === "rejected" || requestedDecision === "requires_approval" ? { reason: text(proposal.error_message) ?? "Decision recorded; no separate reason supplied." } : {}),
        ...(text(permit?.issued_at) ? { issuedAt: text(permit?.issued_at) } : {}),
        ...(text(permit?.expires_at) ? { expiresAt: text(permit?.expires_at) } : {}),
      },
      availability: { state: explicitAvailability?.state ?? "unknown", ...(text(proposal.transport) ? { transport: text(proposal.transport) } : {}), ...(explicitAvailability?.reason ? { reason: explicitAvailability.reason } : {}) },
      execution: {
        state: verifiedExecution,
        ...(rawCalled !== undefined ? { called: rawCalled } : {}),
        ...(outcome ? { outcome } : {}),
        ...(text(proposal.error_message) ? { error: text(proposal.error_message) } : {}),
      },
      receiptLink: { state: linkState, ...(suppliedReceiptId ? { receiptId: suppliedReceiptId } : normalizedReceipt ? { receiptId: normalizedReceipt.id } : {}), ...(normalizedReceipt ? { receipt: normalizedReceipt } : {}) },
    };
  });
  return { schema: "governed-action-bundle/v1", ...(runId ? { runId } : {}), actions };
}
