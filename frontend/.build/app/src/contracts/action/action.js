/** Read-only inspection model for governed proposals, permits and receipts. */
export function validateActionBundle(bundle) {
    const errors = [];
    if (bundle.schema !== "governed-action-bundle/v1")
        errors.push("unsupported action bundle schema");
    const ids = new Set();
    for (const action of bundle.actions) {
        if (action.id !== undefined) {
            if (!action.id.trim() || ids.has(action.id))
                errors.push(`action id is empty or duplicated: ${action.id}`);
            ids.add(action.id);
        }
        if (!action.capability || !action.eligibility || !action.authorization || !action.availability || !action.execution || !action.receiptLink) {
            errors.push(`action ${action.id} is missing a lifecycle state`);
        }
        if (action.receiptLink.state === "matched" && !action.receiptLink.receipt)
            errors.push(`action ${action.id} marks a missing receipt as matched`);
        if (action.receiptLink.state === "matched" && action.receiptLink.receipt && action.receiptLink.receiptId !== action.receiptLink.receipt.id)
            errors.push(`action ${action.id} receipt id does not match its linked receipt`);
        if (action.receiptLink.state === "matched" && action.requestId && action.receiptLink.receipt?.requestId && action.requestId !== action.receiptLink.receipt.requestId)
            errors.push(`action ${action.id} receipt request id does not match its proposal`);
        if (action.receiptLink.state === "matched" && action.authorization.permitId && action.receiptLink.receipt?.permitId && action.authorization.permitId !== action.receiptLink.receipt.permitId)
            errors.push(`action ${action.id} receipt permit id does not match its authorization`);
        if (action.execution.state === "succeeded" && action.execution.called !== true)
            errors.push(`action ${action.id} reports success without an explicit call`);
        if (action.execution.state === "succeeded" && action.receiptLink.state !== "matched")
            errors.push(`action ${action.id} reports success without a matched receipt`);
    }
    return errors;
}
