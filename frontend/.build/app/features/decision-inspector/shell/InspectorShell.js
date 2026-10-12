import { Fragment as _Fragment, jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import './InspectorShell.css';
import { useState } from 'react';
import { InspectorStateView } from '../shared/InspectorState';
export function selectConclusion(items, id) {
    return id == null ? undefined : items.find(item => item.id === id);
}
const sectionLabels = {
    conclusion: 'Conclusion', claims: 'Claims', evidence: 'Evidence', provenance: 'Provenance',
};
export function InspectorShell({ conclusions, selectedConclusionId, onConclusionSelect, state = { status: 'ready' }, sections = {}, initialSection = 'conclusion' }) {
    const [internalId, setInternalId] = useState(null);
    const [section, setSection] = useState(initialSection);
    const activeId = selectedConclusionId === undefined ? internalId : selectedConclusionId;
    const selected = selectConclusion(conclusions, activeId);
    const choose = (id) => {
        setInternalId(id);
        onConclusionSelect?.(id);
        setSection('conclusion');
    };
    return (_jsxs("main", { className: "decision-inspector", "aria-labelledby": "decision-inspector-title", children: [_jsxs("header", { className: "decision-inspector__header", children: [_jsx("h1", { id: "decision-inspector-title", children: "Decision Inspector" }), selected?.runId && _jsxs("p", { className: "decision-inspector__identity", children: [_jsx("span", { children: "Run ID:" }), " ", _jsx("code", { children: selected.runId })] })] }), conclusions.length > 0 && _jsx("nav", { className: "decision-inspector__selection", "aria-label": "Select a conclusion", children: _jsx("ul", { children: conclusions.map(conclusion => (_jsx("li", { children: _jsx("button", { type: "button", "aria-current": selected?.id === conclusion.id ? 'true' : undefined, onClick: () => choose(conclusion.id), children: conclusion.text || `Conclusion ${conclusion.id}` }) }, conclusion.id))) }) }), _jsx(InspectorStateView, { state: conclusions.length === 0 && state.status === 'ready' ? { status: 'empty', message: 'No conclusions were provided by the source.' } : state, children: selected ? _jsxs(_Fragment, { children: [_jsxs("p", { className: "decision-inspector__breadcrumb", "aria-label": "Current location", children: ["Run ", selected.runId || 'Not provided', " ", _jsx("span", { "aria-hidden": "true", children: "\u203A" }), " ", sectionLabels[section]] }), _jsx("nav", { className: "decision-inspector__sections", "aria-label": "Conclusion details", children: Object.keys(sectionLabels).map(key => (_jsx("button", { type: "button", "aria-pressed": section === key, onClick: () => setSection(key), children: sectionLabels[key] }, key))) }), _jsxs("section", { className: "decision-inspector__content", "aria-labelledby": "decision-inspector-section-title", children: [_jsx("h2", { id: "decision-inspector-section-title", children: sectionLabels[section] }), sections[section] ?? _jsx("p", { children: section === 'conclusion' ? selected.text : `${sectionLabels[section]} data not provided.` })] })] }) : conclusions.length > 0 && _jsx(InspectorStateView, { state: { status: 'unknown', message: activeId ? `Conclusion ${activeId} was not found in the supplied data.` : 'Select a conclusion to inspect it.' } }) })] }));
}
