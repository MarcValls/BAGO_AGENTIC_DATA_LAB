import { Fragment as _Fragment, jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import './App.css';
import { useCallback, useEffect, useRef, useState } from 'react';
import axios from 'axios';
import Summary from './components/Summary';
import Retrieval from './components/Retrieval';
import Authorization from './components/Authorization';
import Trace from './components/Trace';
import Evaluation from './components/Evaluation';
import AgentBuilder from './components/AgentBuilder';
import GovernedFixtureRunner from './components/GovernedFixtureRunner';
import AgentTasks from './components/AgentTasks';
import AgentChat from './components/AgentChat';
import CapabilityManager from './components/CapabilityManager';
import JobHistory from './components/JobHistory';
import AgentEvaluationLab from './components/AgentEvaluationLab';
import ProviderSettings from './components/ProviderSettings';
import CognitionSettings, { readCognitiveMode } from './components/CognitionSettings';
import { DecisionInspector } from './features/decision-inspector';
import { BerEffectRecordInspector } from './features/ber-effect-inspector/BerEffectRecordInspector';
const navigation = [
    { id: 'chat', label: 'Chat', layer: 'interaction' },
    { id: 'workspace', label: 'Workspace', layer: 'interaction' },
    { id: 'capabilities', label: 'Capabilities', layer: 'interaction' },
    { id: 'builder', label: 'Agent Builder', layer: 'interaction' },
    { id: 'runner', label: 'Agent Runs', layer: 'interaction' },
    { id: 'evaluation_lab', label: 'Agent Evaluation Lab', layer: 'interaction' },
    { id: 'inspector', label: 'Decision Inspector', layer: 'data' },
    { id: 'ber_record', label: 'BER Effect Record', layer: 'data' },
    { id: 'jobs', label: 'Job History', layer: 'data' },
    { id: 'summary', label: 'Summary', layer: 'data' },
    { id: 'retrieval', label: 'Retrieval & Ontology', layer: 'data' },
    { id: 'authorization', label: 'Authorization', layer: 'data' },
    { id: 'trace', label: 'Trace', layer: 'data' },
    { id: 'evaluation', label: 'Evaluation', layer: 'data' },
];
const interactionNavigation = navigation.filter((item) => item.layer === 'interaction');
const dataNavigation = navigation.filter((item) => item.layer === 'data');
const interactionIcons = {
    chat: '◌',
    workspace: '▣',
    capabilities: '◇',
    builder: '⊞',
    runner: '▷',
    evaluation_lab: '▦',
    control: '⌘',
};
function isDataView(view) {
    return dataNavigation.some((item) => item.id === view);
}
function useScrollActivity() {
    const [scrolling, setScrolling] = useState(false);
    const idleTimer = useRef(null);
    const onScroll = useCallback(() => {
        setScrolling(true);
        if (idleTimer.current !== null)
            window.clearTimeout(idleTimer.current);
        idleTimer.current = window.setTimeout(() => {
            idleTimer.current = null;
            setScrolling(false);
        }, 700);
    }, []);
    useEffect(() => () => {
        if (idleTimer.current !== null)
            window.clearTimeout(idleTimer.current);
    }, []);
    return { scrolling, onScroll };
}
function App() {
    const [artifacts, setArtifacts] = useState(null);
    const [loadingArtifacts, setLoadingArtifacts] = useState(true);
    const [artifactError, setArtifactError] = useState(null);
    const [activeInteractionView, setActiveInteractionView] = useState('chat');
    const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
    const [activeDataView, setActiveDataView] = useState('inspector');
    const [dataLayerOpen, setDataLayerOpen] = useState(false);
    const [settingsOpen, setSettingsOpen] = useState(false);
    const [settingsView, setSettingsView] = useState('cognition');
    const [cognitiveMode, setCognitiveMode] = useState(readCognitiveMode);
    const [demoRefresh, setDemoRefresh] = useState(0);
    const [advancedRunsOpen, setAdvancedRunsOpen] = useState(false);
    const dataLayerRef = useRef(null);
    const settingsDialogRef = useRef(null);
    const appScroll = useScrollActivity();
    const settingsScroll = useScrollActivity();
    const dataScroll = useScrollActivity();
    useEffect(() => {
        const fetchArtifacts = async () => {
            try {
                const response = await axios.get('/api/artifacts');
                setArtifacts(response.data);
                setArtifactError(null);
            }
            catch (error) {
                setArtifactError(error instanceof Error ? error.message : 'Run artifacts are unavailable.');
            }
            finally {
                setLoadingArtifacts(false);
            }
        };
        void fetchArtifacts();
    }, [demoRefresh]);
    const navigateFromChat = useCallback((view) => {
        if (view === 'provider_settings') {
            setSettingsView('providers');
            setSettingsOpen(true);
            return;
        }
        if (view === 'cognition_settings') {
            setSettingsView('cognition');
            setSettingsOpen(true);
            return;
        }
        const tab = view === 'traces' ? 'trace' : view === 'control' ? 'runner' : view;
        if (isDataView(tab)) {
            setActiveDataView(tab);
            setDataLayerOpen(true);
        }
        else {
            setActiveInteractionView(tab);
        }
    }, []);
    const openSettings = useCallback(() => { setSettingsView('cognition'); setSettingsOpen(true); }, []);
    const openProviderSettings = useCallback(() => { setSettingsView('providers'); setSettingsOpen(true); }, []);
    const openCognitionSettings = useCallback(() => { setSettingsView('cognition'); setSettingsOpen(true); }, []);
    const openInspect = useCallback(() => setDataLayerOpen(true), []);
    useEffect(() => {
        const dialog = dataLayerRef.current;
        if (!dialog)
            return;
        if (dataLayerOpen && !dialog.open)
            dialog.showModal();
        if (!dataLayerOpen && dialog.open)
            dialog.close();
    }, [dataLayerOpen]);
    useEffect(() => {
        const dialog = settingsDialogRef.current;
        if (!dialog)
            return;
        if (settingsOpen && !dialog.open)
            dialog.showModal();
        if (!settingsOpen && dialog.open)
            dialog.close();
    }, [settingsOpen]);
    const activeInteractionLabel = interactionNavigation.find((item) => item.id === activeInteractionView)?.label ?? 'Workspace';
    return (_jsxs("div", { className: `app-shell ${activeInteractionView === 'chat' ? 'app-shell--chat' : ''} ${sidebarCollapsed ? 'app-shell--sidebar-collapsed' : ''}`, children: [_jsxs("aside", { id: "workspace-sidebar-content", className: `workspace-sidebar ${activeInteractionView === 'chat' ? 'workspace-sidebar--chat' : ''} ${sidebarCollapsed ? 'workspace-sidebar--collapsed' : ''}`, "aria-label": "Workspace sidebar", children: [_jsxs("div", { className: "workspace-sidebar-brand", children: [_jsx("img", { className: "workspace-sidebar-logo", src: "/brand/BAGO_logotipo_horizontal.svg", alt: "BAGO" }), _jsx("img", { className: "workspace-sidebar-symbol", src: "/brand/BAGO_simbolo_negativo.svg", alt: "", "aria-hidden": "true" })] }), _jsx("nav", { className: "primary-navigation", "aria-label": "Interaction layer", children: _jsxs("div", { className: "navigation-group", children: [interactionNavigation.map((item) => (_jsxs("button", { type: "button", className: `navigation-item ${activeInteractionView === item.id ? 'active' : ''}`, "aria-label": item.label, title: sidebarCollapsed ? item.label : undefined, "aria-current": activeInteractionView === item.id ? 'page' : undefined, onClick: () => setActiveInteractionView(item.id), children: [_jsx("span", { className: "navigation-item-icon", "aria-hidden": "true", children: interactionIcons[item.id] }), _jsx("span", { children: item.label })] }, item.id))), _jsxs("button", { type: "button", className: `navigation-item ${dataLayerOpen ? 'active' : ''}`, "aria-label": "Open Inspect", title: sidebarCollapsed ? 'Inspect' : undefined, "aria-pressed": dataLayerOpen, "aria-haspopup": "dialog", "aria-controls": "data-layer", onClick: openInspect, children: [_jsx("span", { className: "navigation-item-icon", "aria-hidden": "true", children: "\u25EB" }), _jsx("span", { children: "Inspect" })] })] }) }), _jsxs("footer", { className: "workspace-sidebar-footer", children: [_jsxs("button", { type: "button", className: "navigation-item settings-trigger", "aria-label": "Open settings", title: sidebarCollapsed ? 'Settings' : undefined, "aria-haspopup": "dialog", "aria-expanded": settingsOpen, "aria-controls": "settings-layer", onClick: openSettings, children: [_jsx("span", { className: "navigation-item-icon", "aria-hidden": "true", children: "\u2699" }), _jsx("span", { children: "Settings" })] }), _jsx("button", { type: "button", className: "sidebar-collapse-button", "aria-label": sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar', "aria-expanded": !sidebarCollapsed, "aria-controls": "workspace-sidebar-content", title: sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar', onClick: () => setSidebarCollapsed((collapsed) => !collapsed), children: _jsx("span", { "aria-hidden": "true", children: sidebarCollapsed ? '›' : '‹' }) })] })] }), _jsx("div", { className: "app-main", children: _jsxs("main", { className: `app-view ${activeInteractionView === 'chat' ? 'app-view--chat' : ''} ${appScroll.scrolling ? 'scroll-active' : ''}`, "aria-label": `${activeInteractionLabel} view`, tabIndex: 0, onScroll: appScroll.onScroll, children: [activeInteractionView === 'chat' && _jsx(AgentChat, { onNavigate: navigateFromChat, onOpenProviderSettings: openProviderSettings, onOpenCognitionSettings: openCognitionSettings, cognitiveMode: cognitiveMode }), activeInteractionView === 'workspace' && _jsx(CognitionSettings, { mode: cognitiveMode, onModeChange: setCognitiveMode, workspaceOnly: true }), activeInteractionView === 'capabilities' && _jsx(CapabilityManager, {}), activeInteractionView === 'builder' && _jsx(AgentBuilder, { onBack: () => setActiveInteractionView('chat'), onAgentCreated: () => setDemoRefresh((previous) => previous + 1) }), activeInteractionView === 'runner' && _jsxs(_Fragment, { children: [_jsx(AgentTasks, {}), _jsxs("details", { className: "agent-tasks-advanced", open: advancedRunsOpen, onToggle: event => setAdvancedRunsOpen(event.currentTarget.open), children: [_jsx("summary", { children: "Avanzado \u00B7 ejecuci\u00F3n gobernada de demostraci\u00F3n" }), advancedRunsOpen && _jsx(GovernedFixtureRunner, { apiBase: window.location.origin })] })] }), activeInteractionView === 'evaluation_lab' && _jsx(AgentEvaluationLab, {})] }) }), _jsxs("dialog", { ref: settingsDialogRef, id: "settings-layer", className: "settings-layer", "aria-labelledby": "settings-layer-title", onCancel: () => setSettingsOpen(false), onClose: () => setSettingsOpen(false), children: [_jsxs("header", { className: "settings-layer-header", children: [_jsxs("div", { children: [_jsx("p", { className: "app-kicker", children: "Preferences" }), _jsx("h2", { id: "settings-layer-title", children: "Settings" })] }), _jsx("button", { type: "button", className: "settings-layer-close", autoFocus: true, onClick: () => setSettingsOpen(false), "aria-label": "Close settings", children: _jsx("span", { "aria-hidden": "true", children: "\u00D7" }) })] }), _jsxs("div", { className: "settings-layer-layout", children: [_jsxs("nav", { className: "settings-layer-navigation", "aria-label": "Settings sections", children: [_jsx("span", { className: "navigation-caption", children: "Configure" }), _jsx("button", { type: "button", className: `navigation-item ${settingsView === 'cognition' ? 'active' : ''}`, "aria-current": settingsView === 'cognition' ? 'page' : undefined, onClick: () => setSettingsView('cognition'), children: "Cognition and context" }), _jsx("button", { type: "button", className: `navigation-item ${settingsView === 'providers' ? 'active' : ''}`, "aria-current": settingsView === 'providers' ? 'page' : undefined, onClick: () => setSettingsView('providers'), children: "Proveedores y modelos" })] }), _jsx("section", { className: `settings-layer-content ${settingsScroll.scrolling ? 'scroll-active' : ''}`, "aria-label": settingsView === 'providers' ? 'Provider and model settings' : 'Cognition and context settings', tabIndex: 0, onScroll: settingsScroll.onScroll, children: settingsView === 'providers'
                                    ? _jsx(ProviderSettings, {})
                                    : _jsx(CognitionSettings, { mode: cognitiveMode, onModeChange: setCognitiveMode, showWorkspaceLocations: true }) })] })] }), _jsxs("dialog", { ref: dataLayerRef, id: "data-layer", className: "data-layer", "aria-labelledby": "data-layer-title", onCancel: () => setDataLayerOpen(false), onClose: () => setDataLayerOpen(false), children: [_jsxs("header", { className: "data-layer-header", children: [_jsxs("div", { className: "data-layer-heading", children: [_jsx("p", { className: "app-kicker", children: "Inspect" }), _jsx("h2", { id: "data-layer-title", children: dataNavigation.find((item) => item.id === activeDataView)?.label ?? 'Data layer' })] }), _jsx("button", { type: "button", className: "settings-layer-close", "aria-label": "Back to Workspace", title: "Back to Workspace", autoFocus: true, onClick: () => setDataLayerOpen(false), children: _jsx("span", { "aria-hidden": "true", children: "\u00D7" }) })] }), _jsxs("div", { className: "data-layer-layout", children: [_jsxs("nav", { className: "data-layer-navigation", "aria-label": "Data views", children: [_jsx("span", { className: "navigation-caption", children: "Observe" }), dataNavigation.map((item) => (_jsx("button", { type: "button", className: `navigation-item ${activeDataView === item.id ? 'active' : ''}`, "aria-current": activeDataView === item.id ? 'page' : undefined, onClick: () => setActiveDataView(item.id), children: item.label }, item.id)))] }), _jsx("section", { className: `data-layer-content ${dataScroll.scrolling ? 'scroll-active' : ''}`, "aria-label": `${dataNavigation.find((item) => item.id === activeDataView)?.label ?? 'Data'} view`, tabIndex: 0, onScroll: dataScroll.onScroll, children: activeDataView === 'ber_record' ? _jsx(BerEffectRecordInspector, {}) : activeDataView === 'jobs' ? _jsx(JobHistory, {}) : loadingArtifacts
                                    ? _jsxs("div", { className: "app-view-state", role: "status", children: [_jsx("span", { className: "spinner" }), _jsx("p", { children: "Loading portfolio artifacts\u2026" })] })
                                    : artifactError || !artifacts
                                        ? _jsxs("section", { className: "artifact-unavailable", role: "status", children: [_jsx("p", { className: "app-kicker", children: "Portfolio evidence" }), _jsx("h2", { children: "Artifacts are not available yet" }), _jsx("p", { children: artifactError ?? 'No artifact bundle was returned.' }), _jsx("p", { children: "No portfolio artifact bundle is available. Directory scan reports are shown in Agent Runs." }), _jsx("button", { type: "button", className: "navigation-item active", onClick: () => { setDataLayerOpen(false); setActiveInteractionView('runner'); }, children: "Open Agent Runs" })] })
                                        : _jsxs(_Fragment, { children: [activeDataView === 'inspector' && _jsx(DecisionInspector, { artifacts: artifacts }), activeDataView === 'summary' && _jsx(Summary, { data: artifacts }), activeDataView === 'retrieval' && _jsx(Retrieval, { data: artifacts }), activeDataView === 'authorization' && _jsx(Authorization, { data: artifacts }), activeDataView === 'trace' && _jsx(Trace, { data: artifacts }), activeDataView === 'evaluation' && _jsx(Evaluation, { data: artifacts })] }) })] })] })] }));
}
export default App;
