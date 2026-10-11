/** Read-only inspection model for governed proposals, permits and receipts. */

export type KnownState = "known" | "unknown";
export type CapabilityState = "available" | "unavailable" | "unknown";
export type EligibilityState = "eligible" | "ineligible" | "unknown";
export type AuthorizationState = "authorized" | "rejected" | "requires_approval" | "unknown";
export type PermitValidity = "valid" | "expired" | "not_yet_valid" | "unknown";
export type AvailabilityState = "available" | "unavailable" | "unknown";
export type ExecutionState = "not_started" | "succeeded" | "unverified" | "failed" | "partial" | "unknown";
export type ReceiptLinkState = "matched" | "missing" | "mismatch" | "unknown";
export type ActionRisk = "read_only" | "mutating" | "external" | "unknown";

export interface ActionActorReason {
  actor?: string;
  reason?: string;
}

export interface ActionReceipt {
  id: string;
  requestId?: string;
  permitId?: string;
  outcome?: string;
  actualEffect?: Record<string, unknown>;
  evidenceRefs: string[];
  error?: string;
  durationMs?: number;
}

export interface ProposedAction {
  schema: "governed-action/v1";
  id?: string;
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

export function validateActionBundle(bundle: ActionInspectionBundle): string[] {
  const errors: string[] = [];
  if (bundle.schema !== "governed-action-bundle/v1") errors.push("unsupported action bundle schema");
  const ids = new Set<string>();
  for (const action of bundle.actions) {
    if (action.id !== undefined) {
      if (!action.id.trim() || ids.has(action.id)) errors.push(`action id is empty or duplicated: ${action.id}`);
      ids.add(action.id);
    }
    if (!action.capability || !action.eligibility || !action.authorization || !action.availability || !action.execution || !action.receiptLink) {
      errors.push(`action ${action.id} is missing a lifecycle state`);
    }
    if (action.receiptLink.state === "matched" && !action.receiptLink.receipt) errors.push(`action ${action.id} marks a missing receipt as matched`);
    if (action.receiptLink.state === "matched" && action.receiptLink.receipt && action.receiptLink.receiptId !== action.receiptLink.receipt.id) errors.push(`action ${action.id} receipt id does not match its linked receipt`);
    if (action.receiptLink.state === "matched" && action.requestId && action.receiptLink.receipt?.requestId && action.requestId !== action.receiptLink.receipt.requestId) errors.push(`action ${action.id} receipt request id does not match its proposal`);
    if (action.receiptLink.state === "matched" && action.authorization.permitId && action.receiptLink.receipt?.permitId && action.authorization.permitId !== action.receiptLink.receipt.permitId) errors.push(`action ${action.id} receipt permit id does not match its authorization`);
    if (action.execution.state === "succeeded" && action.execution.called !== true) errors.push(`action ${action.id} reports success without an explicit call`);
    if (action.execution.state === "succeeded" && action.receiptLink.state !== "matched") errors.push(`action ${action.id} reports success without a matched receipt`);
  }
  return errors;
}
