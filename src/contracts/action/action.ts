/** Read-only projection of action intent, governance observations and receipts. */

export type CapabilityState = "available" | "unavailable" | "unknown";
export type EligibilityState = "eligible" | "ineligible" | "unknown";
export type AuthorizationState = "authorized" | "rejected" | "requires_approval" | "expired" | "revoked" | "unknown";
export type PermitValidity = "valid" | "expired" | "not_yet_valid" | "revoked" | "unknown";
export type AvailabilityState = "available" | "unavailable" | "unknown";
export type ExecutionState = "not_started" | "succeeded" | "unverified" | "failed" | "partial" | "unknown";
export type ReceiptLinkState = "matched" | "missing" | "mismatch" | "unknown";
export type ActionRisk = "read_only" | "mutating" | "external" | "unknown";

export interface ActionReceipt {
  id: string;
  requestId?: string;
  permitId?: string;
  effectType?: string;
  outcome?: string;
  actualEffect?: Record<string, unknown>;
  evidenceRefs: string[];
  error?: string;
  durationMs?: number;
  /** A receipt projected from ADL remains an observation, not BER authority. */
  source: "adl-agent-run";
}

export interface ProposedAction {
  schema: "governed-action/v1";
  /** The supplied proposal ID; never synthesized by this contract. */
  id?: string;
  proposalState: "proposed";
  runId?: string;
  requestId?: string;
  toolName?: string;
  transport?: string;
  effectType?: string;
  arguments?: Record<string, unknown>;
  proposedBy?: string;
  proposalReason?: string;
  risk: ActionRisk;
  approval: "required" | "not_required" | "unknown";
  capability: { state: CapabilityState; name?: string };
  eligibility: { state: EligibilityState; reason?: string };
  authorization: {
    state: AuthorizationState;
    permitValidity: PermitValidity;
    permitId?: string;
    actor?: string;
    reason?: string;
    issuedAt?: string;
    expiresAt?: string;
  };
  availability: { state: AvailabilityState; transport?: string; reason?: string };
  execution: { state: ExecutionState; called?: boolean; outcome?: string; error?: string };
  receiptLink: { state: ReceiptLinkState; receiptId?: string; receipt?: ActionReceipt };
}

export interface ActionInspectionBundle {
  schema: "governed-action-bundle/v1";
  runId?: string;
  actions: ProposedAction[];
}

/** Structural checks only; this does not validate signatures or grant authority. */
export function validateActionBundle(bundle: ActionInspectionBundle): string[] {
  const errors: string[] = [];
  if (!bundle || bundle.schema !== "governed-action-bundle/v1") return ["unsupported action bundle schema"];
  if (!Array.isArray(bundle.actions)) return ["actions must be an array"];
  const ids = new Set<string>();
  for (const action of bundle.actions) {
    if (action.schema !== "governed-action/v1") errors.push(`action ${action.id} has unsupported schema`);
    if (action.proposalState !== "proposed") errors.push(`action ${action.id} has invalid proposal state`);
    if (action.id !== undefined) {
      if (!action.id.trim() || ids.has(action.id)) errors.push(`action id is empty or duplicated: ${action.id}`);
      ids.add(action.id);
    }
    if (!action.capability || !action.eligibility || !action.authorization || !action.availability || !action.execution || !action.receiptLink) {
      errors.push(`action ${action.id} is missing a lifecycle state`);
      continue;
    }
    const receipt = action.receiptLink.receipt;
    if (action.receiptLink.state === "matched" && !receipt) errors.push(`action ${action.id} marks a missing receipt as matched`);
    if (action.receiptLink.state === "matched" && receipt) {
      if (!action.requestId || !receipt.requestId || action.requestId !== receipt.requestId) errors.push(`action ${action.id} matched receipt lacks an exact request id match`);
      if (action.receiptLink.receiptId !== receipt.id) errors.push(`action ${action.id} receipt id does not match its linked receipt`);
      if (action.authorization.permitId && action.authorization.permitId !== receipt.permitId) errors.push(`action ${action.id} receipt permit id does not match its authorization`);
      if (action.effectType && receipt.effectType && action.effectType !== receipt.effectType) errors.push(`action ${action.id} receipt effect does not match its proposal`);
    }
    if (action.execution.state === "succeeded" && action.execution.called !== true) errors.push(`action ${action.id} reports success without an explicit call`);
    if (action.execution.state === "succeeded" && action.receiptLink.state !== "matched") errors.push(`action ${action.id} reports success without a matched receipt`);
  }
  return errors;
}
