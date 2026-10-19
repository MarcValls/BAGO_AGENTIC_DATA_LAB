import { Fragment as _Fragment, jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import './InspectorState.css';
const defaultMessages = {
    loading: 'Loading run artifacts',
    empty: 'No artifacts are available for this run.',
    error: 'The requested resource could not be loaded.',
    unsupported: 'This data type is not supported by the current inspector.',
    partial: 'Some source data was not provided or is unavailable.',
    stale: 'The supplied source identity does not match the expected identity.',
    unverified: 'The source did not provide enough matching identity to verify this result.',
    unknown: 'The source did not provide enough information to determine this state.',
};
const stateHeadings = {
    loading: 'Loading',
    empty: 'Nothing to inspect',
    error: 'Unable to load',
    unsupported: 'Unsupported data',
    partial: 'Partial data',
    stale: 'Stale data',
    unverified: 'Unverified',
    unknown: 'State unknown',
};
export function InspectorStateView({ state, children }) {
    if (state.status === 'ready')
        return _jsx(_Fragment, { children: children });
    const message = state.status === 'error' ? state.message : state.message || defaultMessages[state.status];
    const liveRole = state.status === 'error' ? 'alert' : 'status';
    return (_jsxs("section", { className: `decision-inspector-state decision-inspector-state--${state.status}`, role: liveRole, "aria-live": state.status === 'error' ? 'assertive' : 'polite', children: [_jsx("h2", { children: stateHeadings[state.status] }), _jsx("p", { children: message }), state.status === 'error' && state.onRetry && _jsx("button", { type: "button", onClick: state.onRetry, children: "Retry" })] }));
}
const supportLabels = {
    supported: 'Supported by linked evidence',
    unsupported: 'No supporting evidence linked',
    missing: 'Referenced evidence is unavailable',
    stale: 'Evidence is stale',
    contradictory: 'Conflicting evidence is reported',
    unknown: 'Evidence support is unknown',
};
export function EvidenceSupportStatus({ status }) {
    return _jsx("span", { className: `decision-inspector-support decision-inspector-support--${status}`, children: supportLabels[status] });
}
export const freshnessLabel = (freshness) => ({
    current: 'Current',
    stale: 'Stale',
    unknown: 'Freshness not established',
}[freshness]);
