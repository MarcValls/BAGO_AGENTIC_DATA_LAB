import { Fragment as _Fragment, jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useMemo, useState } from 'react';
import { actionBundleFromAgentRun } from '../../../adapters/action/agentRun';
import { localTraceToTimeline } from '../../../adapters/trace/localTraceAdapter';
import { evidenceFromRetrievalHit } from '../../../contracts/decision/evidence';
import { ActionReview } from '../actions/ActionReview';
import { EvidenceExplorer } from '../evidence/EvidenceExplorer';
import { InspectorShell } from '../shell/InspectorShell';
import { TraceTimeline as TraceTimelineView } from '../trace/TraceTimeline';
import './DecisionInspector.css';
function record(value) {
    return value !== null && typeof value === 'object' && !Array.isArray(value)
        ? value
        : undefined;
}
function text(value) {
    return typeof value === 'string' && value.trim() ? value : undefined;
}
/** Receipt association requires source identity, even when receipt arrays are nested in a run. */
function runBoundActionSource(run) {
    const runId = text(run.run_id);
    const receiptsForThisRun = (value) => {
        if (!runId || !Array.isArray(value))
            return [];
        return value.filter(item => {
            const receipt = record(item);
            return receipt !== undefined && text(receipt.run_id) === runId;
        });
    };
    const providerReceipt = record(run.provider_receipt);
    return {
        ...run,
        decision_receipts: receiptsForThisRun(run.decision_receipts),
        mcp_receipts: receiptsForThisRun(run.mcp_receipts),
        provider_receipt: runId && providerReceipt && text(providerReceipt.run_id) === runId ? providerReceipt : undefined,
    };
}
/** Maps only source-supplied identities and values; it never decomposes answer text into claims. */
export function decisionInspectorModel(artifacts) {
    const run = artifacts.agent_run;
    const runId = text(run.run_id);
    const retrieval = record(run.retrieval);
    const hits = Array.isArray(retrieval?.hits) ? retrieval.hits.map(record).filter((item) => Boolean(item)) : [];
    const evidenceById = new Map();
    for (const hit of hits) {
        const rawEvidence = record(hit.evidence);
        const mapped = evidenceFromRetrievalHit({
            ...(rawEvidence ? { evidence: rawEvidence } : {}),
            ...(text(hit.chunk_id) ? { chunk_id: text(hit.chunk_id) } : {}),
            ...(text(hit.document_id) ? { document_id: text(hit.document_id) } : {}),
        });
        if (mapped.id)
            evidenceById.set(mapped.id, mapped);
    }
    const citations = Array.isArray(run.citations) ? run.citations.filter((item) => typeof item === 'string') : [];
    for (const citation of citations) {
        if (citation.trim() && !evidenceById.has(citation)) {
            evidenceById.set(citation, { id: citation, artifactRef: citation, freshness: 'unknown' });
        }
    }
    const evidence = [...evidenceById.values()];
    const conclusion = runId ? {
        schema: 'decision-conclusion/v1',
        id: runId,
        runId,
        text: text(run.answer) ?? '',
        claims: [],
        evidence,
    } : undefined;
    const trace = record(artifacts.trace);
    const timeline = trace && typeof trace.trace_id === 'string' && typeof trace.run_id === 'string' && Array.isArray(trace.events)
        ? localTraceToTimeline(trace)
        : undefined;
    return {
        conclusion,
        evidence,
        timeline,
        actions: actionBundleFromAgentRun(runBoundActionSource(run)),
    };
}
const views = [
    { id: 'overview', label: 'Decision' },
    { id: 'trace', label: 'Trace' },
    { id: 'actions', label: 'Actions' },
];
function EvidenceInventory({ evidence }) {
    if (evidence.length === 0)
        return _jsx("p", { role: "status", children: "No citation or retrieval evidence was provided by this run." });
    return _jsxs("section", { className: "decision-inspector__inventory", "aria-label": "Retrieved evidence references", children: [_jsx("p", { children: "These references were retrieved for the run. The source did not provide structured claim links, so support is not inferred." }), _jsx("ul", { children: evidence.map((item, index) => _jsxs("li", { children: [_jsxs("h3", { children: ["Reference ", index + 1] }), _jsx("p", { children: _jsx("code", { children: item.artifactRef || item.id || 'Reference not provided' }) }), _jsxs("dl", { children: [_jsxs("div", { children: [_jsx("dt", { children: "Source" }), _jsx("dd", { children: _jsx("code", { children: item.sourceIdentity || item.snapshot?.sourceUri || 'Not provided' }) })] }), _jsxs("div", { children: [_jsx("dt", { children: "Revision" }), _jsx("dd", { children: item.snapshot?.revision || 'Not provided' })] }), _jsxs("div", { children: [_jsx("dt", { children: "Freshness" }), _jsx("dd", { children: item.freshness === 'unknown' ? 'Not established' : item.freshness })] }), _jsxs("div", { children: [_jsx("dt", { children: "Claim relation" }), _jsx("dd", { children: "Not provided" })] })] })] }, `${item.id}-${index}`)) })] });
}
export function DecisionInspector({ artifacts }) {
    const [view, setView] = useState('overview');
    const [section, setSection] = useState('conclusion');
    const [claimId, setClaimId] = useState();
    const [actionId, setActionId] = useState();
    const model = useMemo(() => decisionInspectorModel(artifacts), [artifacts]);
    const runId = model.conclusion?.runId || 'Not provided';
    const selectedAction = actionId ? model.actions.actions.find(action => action.id === actionId) : undefined;
    const actionBundle = selectedAction ? { ...model.actions, actions: [selectedAction] } : model.actions;
    const runStatus = text(artifacts.agent_run.status) || 'Not provided';
    const conclusion = model.conclusion ? _jsxs(_Fragment, { children: [_jsxs("section", { className: "decision-inspector__summary", "aria-label": "Agent conclusion", children: [_jsxs("p", { className: "decision-inspector__eyebrow", children: ["Source supplied conclusion \u00B7 run ", runId] }), _jsx("h2", { children: text(artifacts.agent_run.query) || 'Query not provided' }), _jsx("p", { className: "decision-inspector__answer", children: model.conclusion.text || 'Conclusion text not provided.' })] }), _jsxs("div", { className: "decision-inspector__summary-grid", children: [_jsxs("div", { children: [_jsx("span", { children: "Evidence references" }), _jsx("strong", { children: model.evidence.length })] }), _jsxs("div", { children: [_jsx("span", { children: "Structured claims" }), _jsx("strong", { children: model.conclusion.claims.length ? model.conclusion.claims.length : 'Not provided' })] }), _jsxs("div", { children: [_jsx("span", { children: "Trace events" }), _jsx("strong", { children: model.timeline?.events.length ?? 'Not provided' })] }), _jsxs("div", { children: [_jsx("span", { children: "Proposed actions" }), _jsx("strong", { children: model.actions.actions.length })] })] }), _jsx(InspectorShell, { conclusions: [model.conclusion], selectedConclusionId: model.conclusion.id, initialSection: section, sections: {
                    conclusion: _jsxs("div", { className: "decision-inspector__answer-detail", children: [_jsx("h3", { children: "Conclusion source" }), _jsx("p", { children: "The answer above is the source supplied by this run." }), _jsx("p", { children: "Claims are not derived from answer text or citations." })] }),
                    claims: _jsx(EvidenceExplorer, { conclusion: model.conclusion, initialClaimId: claimId }, `claims-${claimId || 'none'}`),
                    evidence: _jsx(EvidenceInventory, { evidence: model.evidence }),
                    provenance: _jsx(EvidenceExplorer, { conclusion: model.conclusion, initialClaimId: claimId }, `provenance-${claimId || 'none'}`),
                } }, section)] }) : _jsxs("section", { className: "decision-inspector__empty", role: "status", children: [_jsx("h2", { children: "Run identity unavailable" }), _jsx("p", { children: "The source did not provide a run ID, so the inspector cannot create a stable conclusion identity." })] });
    return _jsxs("section", { className: "decision-inspector-page", "aria-label": "BAGO decision inspector", children: [_jsxs("header", { className: "decision-inspector-page__header", children: [_jsxs("div", { children: [_jsx("p", { className: "decision-inspector__eyebrow", children: "Governed agent run" }), _jsx("h1", { children: "Decision Inspector" }), _jsx("p", { children: "Follow the source conclusion through evidence, trace, actions and receipts." }), _jsxs("code", { children: ["Run ID: ", runId] })] }), _jsx("span", { className: "decision-inspector-page__status", children: runStatus })] }), _jsx("nav", { className: "decision-inspector-page__nav", "aria-label": "Inspector views", children: views.map(item => _jsx("button", { type: "button", "aria-current": view === item.id ? 'page' : undefined, onClick: () => { setView(item.id); setActionId(undefined); }, children: item.label }, item.id)) }), view === 'overview' && conclusion, view === 'trace' && _jsx(TraceTimelineView, { timeline: model.timeline, state: model.timeline ? { status: 'ready' } : { status: 'unknown', message: 'The source did not provide a trace for this run.' }, onClaimNavigate: id => { setClaimId(id); setSection('claims'); setView('overview'); }, onActionNavigate: id => { setActionId(id); setView('actions'); } }), view === 'actions' && _jsxs(_Fragment, { children: [actionId && !selectedAction && _jsxs("p", { role: "status", children: ["Action ", actionId, " was referenced by the trace but was not included in the supplied action data."] }), _jsx(ActionReview, { bundle: actionBundle })] })] });
}
