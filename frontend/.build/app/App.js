import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useEffect, useState } from 'react';
import axios from 'axios';
import Summary from './components/Summary';
import Retrieval from './components/Retrieval';
import Authorization from './components/Authorization';
import Trace from './components/Trace';
import Evaluation from './components/Evaluation';
import Control from './components/Control';
import AgentBuilder from './components/AgentBuilder';
import AgentRunner from './components/AgentRunner';
import AgentChat from './components/AgentChat';
import JobHistory from './components/JobHistory';
import { DecisionInspector } from './features/decision-inspector';
import './App.css';
const portfolioViews = [
    { id: 'builder', label: 'Agent Builder' },
    { id: 'chat', label: 'Agent Chat' },
    { id: 'runner', label: 'Agent Runner' },
    { id: 'control', label: 'Control' },
    { id: 'jobs', label: 'Job History' },
    { id: 'summary', label: 'Summary' },
    { id: 'retrieval', label: 'Retrieval & Ontology' },
    { id: 'authorization', label: 'Authorization' },
    { id: 'trace', label: 'Trace' },
    { id: 'evaluation', label: 'Evaluation' },
];
function App() {
    const [artifacts, setArtifacts] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [activeTab, setActiveTab] = useState('inspector');
    const [demoRefresh, setDemoRefresh] = useState(0);
    useEffect(() => {
        const fetchArtifacts = async () => {
            try {
                const response = await axios.get('/api/artifacts');
                setArtifacts(response.data);
                setError(null);
            }
            catch (err) {
                setError(err instanceof Error ? err.message : 'Failed to load artifacts');
            }
            finally {
                setLoading(false);
            }
        };
        fetchArtifacts();
    }, [demoRefresh]);
    const handleDemoRun = () => {
        setDemoRefresh((previous) => previous + 1);
        setActiveTab('inspector');
    };
    if (loading)
        return _jsxs("main", { className: "container app-state", children: [_jsx("div", { className: "spinner", role: "status" }), _jsx("p", { children: "Loading run artifacts\u2026" })] });
    if (error)
        return _jsx("main", { className: "container app-state", children: _jsxs("section", { className: "card", role: "alert", children: [_jsx("h1", { children: "Run artifacts unavailable" }), _jsx("p", { children: error }), _jsxs("p", { children: ["Run ", _jsx("code", { children: "python demo.py" }), " to create a governed demo artifact bundle."] })] }) });
    if (!artifacts)
        return _jsx("main", { className: "container app-state", children: _jsx("p", { role: "status", children: "No run data was provided." }) });
    return (_jsxs("main", { className: "container", children: [_jsxs("header", { className: "header", children: [_jsxs("div", { children: [_jsx("p", { className: "app-kicker", children: "BAGO \u00B7 Governed Knowledge Agent" }), _jsx("h1", { children: "Agentic Data Lab" })] }), _jsx("span", { className: `badge ${artifacts.summary.status === 'PASS' ? 'success' : 'error'}`, children: artifacts.summary.status })] }), _jsx("button", { className: "inspector-home", type: "button", "aria-current": activeTab === 'inspector' ? 'page' : undefined, onClick: () => setActiveTab('inspector'), children: "Decision Inspector" }), activeTab === 'inspector' && _jsx(DecisionInspector, { artifacts: artifacts }), _jsxs("details", { className: "portfolio-views", children: [_jsx("summary", { children: "Other portfolio views" }), _jsx("nav", { className: "tabs", "aria-label": "Other portfolio views", children: portfolioViews.map((view) => _jsx("button", { className: `tab ${activeTab === view.id ? 'active' : ''}`, onClick: () => setActiveTab(view.id), children: view.label }, view.id)) }), activeTab === 'builder' && _jsx(AgentBuilder, { onAgentCreated: handleDemoRun }), activeTab === 'chat' && _jsx(AgentChat, {}), activeTab === 'runner' && _jsx(AgentRunner, {}), activeTab === 'control' && _jsx(Control, { onDemoRun: handleDemoRun }), activeTab === 'jobs' && _jsx(JobHistory, {}), activeTab === 'summary' && _jsx(Summary, { data: artifacts }), activeTab === 'retrieval' && _jsx(Retrieval, { data: artifacts }), activeTab === 'authorization' && _jsx(Authorization, { data: artifacts }), activeTab === 'trace' && _jsx(Trace, { data: artifacts }), activeTab === 'evaluation' && _jsx(Evaluation, { data: artifacts })] })] }));
}
export default App;
