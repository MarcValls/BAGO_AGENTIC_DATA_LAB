import { Fragment as _Fragment, jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import './ActionReview.css';
import { validateActionBundle } from '../../../contracts/action/action';
import { InspectorStateView } from '../shared/InspectorState';
const authorizationLabel = {
    authorized: 'Authorized by recorded decision',
    rejected: 'Rejected by recorded decision',
    requires_approval: 'Human approval required',
    expired: 'Authorization expired',
    revoked: 'Authorization revoked',
    unknown: 'Authorization state unknown',
};
const receiptLabel = {
    matched: 'Matched receipt',
    missing: 'Receipt declared but unavailable',
    mismatch: 'Receipt mismatch',
    unknown: 'Receipt link unknown',
};
function display(value) {
    return value || 'Not provided';
}
function readable(value) {
    return value ? value.replace(/_/g, ' ') : 'Unknown';
}
/** Defend the display boundary as well as the upstream adapter's receipt link. */
function receiptState(action) {
    const { state, receiptId, receipt } = action.receiptLink;
    if (state !== 'matched')
        return state;
    if (!receipt || !receiptId || receiptId !== receipt.id || !action.requestId || !receipt.requestId || action.requestId !== receipt.requestId)
        return 'mismatch';
    if (action.authorization.permitId && action.authorization.permitId !== receipt.permitId)
        return 'mismatch';
    const effectType = receipt.effectType;
    if (action.effectType && effectType && action.effectType !== effectType)
        return 'mismatch';
    return 'matched';
}
function executionState(action, linkedReceipt) {
    if (action.execution.state === 'succeeded' && linkedReceipt !== 'matched')
        return 'unverified';
    return readable(action.execution.state);
}
function ReceiptDetails({ action }) {
    const link = action.receiptLink;
    const state = receiptState(action);
    return (_jsxs("section", { className: `action-review__receipt action-review__receipt--${state}`, "aria-label": "Execution receipt", children: [_jsx("h4", { children: "Receipt" }), _jsx("p", { children: _jsx("strong", { children: receiptLabel[state] }) }), link.receiptId && _jsxs("p", { children: ["Receipt ID: ", _jsx("code", { children: link.receiptId })] }), state === 'missing' && _jsx("p", { children: "The source declares a receipt, but no matching receipt record was provided." }), state === 'mismatch' && _jsx("p", { children: "The available receipt does not match the proposal identifiers. Its outcome is not accepted as this action's receipt." }), state === 'unknown' && _jsx("p", { children: "No receipt relationship was established from the supplied source data." }), link.receipt && _jsxs(_Fragment, { children: ['source' in link.receipt && _jsxs("p", { children: ["Receipt source: ", String(link.receipt.source)] }), _jsxs("p", { children: ["Receipt outcome: ", display(link.receipt.outcome)] }), _jsxs("p", { children: ["Request ID: ", _jsx("code", { children: display(link.receipt.requestId) })] }), _jsxs("p", { children: ["Permit ID: ", _jsx("code", { children: display(link.receipt.permitId) })] }), link.receipt.error && _jsxs("p", { children: ["Receipt error: ", link.receipt.error] }), link.receipt.evidenceRefs.length > 0
                        ? _jsx("ul", { "aria-label": "Receipt evidence references", children: link.receipt.evidenceRefs.map((ref, index) => _jsx("li", { children: _jsx("code", { children: ref }) }, `${ref}-${index}`)) })
                        : _jsx("p", { children: "Receipt evidence references: none provided." })] }), executionState(action, state) === 'unverified' && _jsx("p", { role: "status", children: "The source reports success, but it is unverified because an identity-matched receipt is unavailable." })] }));
}
function ActionCard({ action, index }) {
    const title = action.id ? `Action ${action.id}` : `Proposed action ${index + 1} (identifier not provided)`;
    const linkedReceipt = receiptState(action);
    return (_jsxs("article", { className: "action-review__card", "aria-labelledby": `action-title-${index}`, children: [_jsxs("header", { children: [_jsx("h3", { id: `action-title-${index}`, children: title }), _jsx("p", { className: "action-review__proposal-state", children: "Proposed intent \u00B7 display only" })] }), _jsxs("dl", { className: "action-review__facts", children: [_jsxs("div", { children: [_jsx("dt", { children: "Run ID" }), _jsx("dd", { children: _jsx("code", { children: display(action.runId) }) })] }), _jsxs("div", { children: [_jsx("dt", { children: "Request ID" }), _jsx("dd", { children: _jsx("code", { children: display(action.requestId) }) })] }), _jsxs("div", { children: [_jsx("dt", { children: "Tool" }), _jsx("dd", { children: display(action.toolName) })] }), _jsxs("div", { children: [_jsx("dt", { children: "Transport" }), _jsx("dd", { children: display(action.transport) })] }), _jsxs("div", { children: [_jsx("dt", { children: "Effect type" }), _jsxs("dd", { children: [display(action.effectType), " \u00B7 risk: ", action.risk.replace('_', ' ')] })] }), _jsxs("div", { children: [_jsx("dt", { children: "Proposal reason" }), _jsx("dd", { children: display(action.proposalReason) })] }), _jsxs("div", { children: [_jsx("dt", { children: "Approval state" }), _jsx("dd", { children: action.approval === 'required' ? 'Required by recorded decision' : action.approval === 'not_required' ? 'Not required by recorded decision' : 'Not established' })] })] }), action.arguments && _jsx("p", { className: "action-review__arguments-note", children: "Arguments were supplied but are hidden here unless a source provides an explicitly redacted view." }), _jsxs("section", { className: "action-review__ladder", "aria-label": "Authorization and execution lifecycle", children: [_jsx("h4", { children: "Action lifecycle" }), _jsxs("ol", { children: [_jsxs("li", { children: [_jsx("strong", { children: "Capability" }), _jsxs("span", { children: [action.capability.state, action.capability.name ? ` · ${action.capability.name}` : ''] })] }), _jsxs("li", { children: [_jsx("strong", { children: "Eligibility" }), _jsxs("span", { children: [action.eligibility.state, action.eligibility.reason ? ` · ${action.eligibility.reason}` : ''] })] }), _jsxs("li", { children: [_jsx("strong", { children: "Authorization decision" }), _jsx("span", { children: authorizationLabel[action.authorization.state] ?? 'Authorization state unknown' }), _jsxs("span", { children: ["Permit validity: ", readable(action.authorization.permitValidity)] }), _jsxs("span", { children: ["Permit ID: ", _jsx("code", { children: display(action.authorization.permitId) })] }), action.authorization.actor && _jsxs("span", { children: ["Actor: ", action.authorization.actor] }), action.authorization.reason && _jsxs("span", { children: ["Reason: ", action.authorization.reason] })] }), _jsxs("li", { children: [_jsx("strong", { children: "Availability" }), _jsxs("span", { children: [action.availability.state, action.availability.reason ? ` · ${action.availability.reason}` : ''] })] }), _jsxs("li", { children: [_jsx("strong", { children: "Execution" }), _jsx("span", { children: executionState(action, linkedReceipt) }), _jsxs("span", { children: ["Call recorded: ", action.execution.called === undefined ? 'unknown' : action.execution.called ? 'yes' : 'no'] }), _jsxs("span", { children: ["Outcome: ", display(action.execution.outcome)] }), action.execution.error && _jsxs("span", { children: ["Error: ", action.execution.error] })] })] })] }), _jsx(ReceiptDetails, { action: action })] }));
}
export function ActionReview({ bundle, state = { status: 'ready' } }) {
    if (state.status !== 'ready')
        return _jsxs("section", { className: "action-review", children: [_jsx("h2", { children: "Proposed actions" }), _jsx(InspectorStateView, { state: state })] });
    if (!bundle)
        return _jsxs("section", { className: "action-review", children: [_jsx("h2", { children: "Proposed actions" }), _jsx(InspectorStateView, { state: { status: 'unknown', message: 'Action proposal data was not provided by the source.' } })] });
    const errors = validateActionBundle(bundle).filter(error => !(error.includes('receipt') || error.includes('reports success without a matched receipt')));
    if (errors.length > 0)
        return _jsxs("section", { className: "action-review", children: [_jsx("h2", { children: "Proposed actions" }), _jsx(InspectorStateView, { state: { status: 'unsupported', message: `Action data is invalid or unsupported: ${errors.join('; ')}` } })] });
    if (bundle.actions.length === 0)
        return _jsxs("section", { className: "action-review", children: [_jsx("h2", { children: "Proposed actions" }), _jsx(InspectorStateView, { state: { status: 'empty', message: 'This run has no proposed actions.' } })] });
    return _jsxs("section", { className: "action-review", "aria-labelledby": "action-review-title", children: [_jsxs("header", { className: "action-review__header", children: [_jsxs("div", { children: [_jsx("h2", { id: "action-review-title", children: "Proposed actions" }), _jsx("p", { children: "Inspection only. A recorded authorization decision does not prove execution; execution is unverified without a matching receipt. This view does not grant BAGO authority." })] }), bundle.runId && _jsxs("p", { children: ["Run ID: ", _jsx("code", { children: bundle.runId })] })] }), _jsx("div", { className: "action-review__list", children: bundle.actions.map((action, index) => _jsx(ActionCard, { action: action, index: index }, action.id ?? `${action.requestId ?? 'unknown'}-${index}`)) })] });
}
