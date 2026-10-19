import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import './TraceTimeline.css';
import { InspectorStateView } from '../shared/InspectorState';
function eventCorrelations(event) {
    if ('correlations' in event)
        return event.correlations;
    const { correlation } = event;
    return {
        ...(correlation.agentId ? { agentId: correlation.agentId } : {}),
        // The legacy projector overloaded request/proposal IDs as toolCallId. Do not
        // display that value as a tool call until the canonical W04 projection feeds it.
        ...(correlation.claimId ? { claimId: correlation.claimId } : {}),
        ...(correlation.actionId ? { actionId: correlation.actionId } : {}),
    };
}
function Payload({ event }) {
    const values = Object.entries(event.attributes);
    const renderValue = (value) => {
        if (value === null || typeof value !== 'object')
            return String(value);
        return JSON.stringify(value, null, 2);
    };
    return _jsxs("details", { className: "decision-trace__payload", children: [_jsx("summary", { children: "Inspect supplied event attributes" }), values.length === 0 ? _jsx("p", { children: "Event attributes not provided by the source." }) : _jsx("dl", { children: values.map(([key, value]) => _jsxs("div", { className: "decision-trace__attribute", children: [_jsx("dt", { children: key }), _jsx("dd", { children: _jsx("pre", { children: renderValue(value) }) })] }, key)) }), _jsx("p", { className: "decision-trace__redaction-note", children: "Redaction markers are shown as received; the inspector cannot verify upstream redaction." })] });
}
function Correlation({ event, onClaimNavigate, onActionNavigate }) {
    const ids = eventCorrelations(event);
    const supplied = [
        ['Agent', ids.agentId], ['Tool call', ids.toolCallId], ['Proposal', 'proposalId' in ids ? ids.proposalId : undefined],
        ['Request', 'requestId' in ids ? ids.requestId : undefined], ['Claim', ids.claimId], ['Action', ids.actionId],
        ['Execution', 'executionId' in ids ? ids.executionId : undefined], ['Execution request', 'executionRequestId' in ids ? ids.executionRequestId : undefined],
        ['Permit', 'permitId' in ids ? ids.permitId : undefined], ['Receipt', 'receiptId' in ids ? ids.receiptId : undefined],
    ];
    const visible = supplied.filter(([, id]) => Boolean(id));
    return _jsxs("section", { className: "decision-trace__correlation", "aria-label": "Source-supplied correlation identifiers", children: [_jsx("h4", { children: "Correlation identifiers" }), visible.length > 0 ? _jsx("dl", { children: visible.map(([label, id]) => _jsxs("div", { children: [_jsx("dt", { children: label }), _jsx("dd", { children: id ? label === 'Claim' && onClaimNavigate
                                ? _jsxs("button", { type: "button", onClick: () => onClaimNavigate(id), children: ["Claim: ", _jsx("code", { children: id })] })
                                : label === 'Action' && onActionNavigate
                                    ? _jsxs("button", { type: "button", onClick: () => onActionNavigate(id), children: ["Action: ", _jsx("code", { children: id })] })
                                    : _jsx("code", { children: id })
                                : 'Correlation unavailable' })] }, label)) }) : _jsx("p", { children: "No optional correlation identifiers were supplied." }), !ids.claimId && _jsx("p", { children: "Claim correlation unavailable." }), !ids.actionId && _jsx("p", { children: "Action correlation unavailable." }), _jsx("p", { children: "Identifiers are copied from the source event. Correlation does not establish authorization or execution." })] });
}
export function TraceTimeline({ timeline, state = { status: 'ready' }, onClaimNavigate, onActionNavigate }) {
    if (state.status !== 'ready')
        return _jsxs("section", { className: "decision-trace", "aria-labelledby": "decision-trace-title", children: [_jsx("h2", { id: "decision-trace-title", children: "Trace timeline" }), _jsx(InspectorStateView, { state: state })] });
    if (!timeline)
        return _jsxs("section", { className: "decision-trace", "aria-labelledby": "decision-trace-title", children: [_jsx("h2", { id: "decision-trace-title", children: "Trace timeline" }), _jsx(InspectorStateView, { state: { status: 'unknown', message: 'Trace data was not provided by the source.' } })] });
    if (timeline.events.length === 0)
        return _jsxs("section", { className: "decision-trace", "aria-labelledby": "decision-trace-title", children: [_jsx("h2", { id: "decision-trace-title", children: "Trace timeline" }), _jsx(InspectorStateView, { state: { status: 'empty', message: 'This run has no trace events.' } })] });
    return _jsxs("section", { className: "decision-trace", "aria-labelledby": "decision-trace-title", children: [_jsxs("header", { className: "decision-trace__header", children: [_jsxs("div", { children: [_jsx("h2", { id: "decision-trace-title", children: "Trace timeline" }), _jsxs("p", { children: ["Supplied trace ", _jsx("code", { children: timeline.traceId }), " \u00B7 Run ", _jsx("code", { children: timeline.runId })] })] }), _jsx("p", { className: "decision-trace__authority", role: "note", children: "Trace data is an observation. It does not establish BER authorization or execution." })] }), _jsx("p", { className: "decision-trace__model", children: "Chronology: supplied sequence. Causality: explicit parent event. Sequence order does not imply causation." }), timeline.gaps.length > 0 && _jsxs("aside", { className: "decision-trace__gaps", "aria-label": "Trace gaps", children: [_jsxs("h3", { children: ["Trace gaps (", timeline.gaps.length, ")"] }), _jsx("ul", { children: timeline.gaps.map((gap, index) => _jsxs("li", { children: [_jsx("strong", { children: gap.kind.replace(/_/g, ' ') }), ": ", gap.detail] }, `${gap.kind}-${gap.eventId || 'trace'}-${index}`)) })] }), _jsx("ol", { className: "decision-trace__events", "aria-label": "Trace events in supplied sequence order", children: timeline.events.map(event => _jsx("li", { className: "decision-trace__event", children: _jsxs("article", { "aria-labelledby": `trace-event-${event.sequence}-${event.eventId}`, children: [_jsxs("header", { children: [_jsxs("span", { className: "decision-trace__sequence", children: ["Sequence ", event.sequence] }), _jsx("h3", { id: `trace-event-${event.sequence}-${event.eventId}`, children: event.name || 'Unnamed event' }), _jsxs("span", { className: "decision-trace__status", children: ["Status: ", event.status || 'Not provided'] })] }), _jsxs("dl", { className: "decision-trace__facts", children: [_jsxs("div", { children: [_jsx("dt", { children: "Event ID" }), _jsx("dd", { children: _jsx("code", { children: event.eventId || 'Not provided' }) })] }), _jsxs("div", { children: [_jsx("dt", { children: "Event trace ID" }), _jsx("dd", { children: _jsx("code", { children: event.traceId || 'Not provided' }) })] }), _jsxs("div", { children: [_jsx("dt", { children: "Kind" }), _jsx("dd", { children: event.kind || 'Not provided' })] }), _jsxs("div", { children: [_jsx("dt", { children: "Declared causal parent" }), _jsx("dd", { children: event.parentState === 'root' ? 'Root event (no parent supplied)' : event.parentState === 'resolved' ? _jsx("code", { children: event.parentEventId }) : `Parent unavailable: ${event.parentEventId || 'not provided'}` })] }), _jsxs("div", { children: [_jsx("dt", { children: "Evidence references" }), _jsx("dd", { children: event.evidenceRefs.length ? event.evidenceRefs.map((ref, index) => _jsxs("code", { children: [ref, " "] }, `${ref}-${index}`)) : 'No evidence references linked' })] })] }), _jsx(Correlation, { event: event, onClaimNavigate: onClaimNavigate, onActionNavigate: onActionNavigate }), _jsx(Payload, { event: event })] }) }, `${event.eventId}-${event.sequence}`)) })] });
}
