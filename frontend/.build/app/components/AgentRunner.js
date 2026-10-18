import { Fragment as _Fragment, jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import './AgentRunner.css';
import { useState, useEffect } from 'react';
import AgentBuilder from './AgentBuilder';
// /ws/agents/run intentionally fails closed until a governed executor exists.
const AGENT_EXECUTION_AVAILABLE = false;
export default function AgentRunner() {
    const [agents, setAgents] = useState([]);
    const [loading, setLoading] = useState(true);
    const [selectedAgent, setSelectedAgent] = useState(null);
    const [editingAgent, setEditingAgent] = useState(false);
    const [isRunning, setIsRunning] = useState(false);
    const [logs, setLogs] = useState([]);
    const [result, setResult] = useState(null);
    const [notification, setNotification] = useState(null);
    useEffect(() => {
        fetchAgents();
    }, []);
    const fetchAgents = async () => {
        try {
            const response = await fetch('/api/agents/list');
            const data = await response.json();
            setAgents(data.agents || []);
        }
        catch (error) {
            showNotification('error', 'Failed to load agents');
        }
        finally {
            setLoading(false);
        }
    };
    const showNotification = (type, message) => {
        setNotification({ type, message });
        setTimeout(() => setNotification(null), 3000);
    };
    const executeAgent = async (agent) => {
        if (!AGENT_EXECUTION_AVAILABLE) {
            showNotification('error', 'Agent execution is unavailable: no governed execution capability is registered.');
            return;
        }
        setSelectedAgent(agent);
        setIsRunning(true);
        setLogs([]);
        setResult(null);
        try {
            const ws = new WebSocket('ws://localhost:8080/ws/agents/run');
            ws.onopen = () => {
                ws.send(JSON.stringify({
                    agent_id: agent.id,
                    config: agent.config,
                }));
                setLogs(['[INFO] Connecting to agent execution service...']);
            };
            ws.onmessage = (event) => {
                const msg = JSON.parse(event.data);
                if (msg.type === 'stdout') {
                    setLogs((prev) => [...prev, msg.data]);
                }
                else if (msg.type === 'done') {
                    const exitCode = Number.isInteger(msg.exit_code) ? msg.exit_code : null;
                    const result = {
                        job_id: msg.job_id,
                        status: exitCode === 0 ? 'success' : 'failed',
                        duration_ms: msg.duration_ms || 0,
                        cost_usd: msg.cost_usd || 0,
                        exit_code: exitCode,
                    };
                    setResult(result);
                    setIsRunning(false);
                    ws.close();
                    if (exitCode === 0) {
                        showNotification('success', `Agent ${agent.config.name} executed successfully`);
                    }
                    else {
                        showNotification('error', `Agent execution failed: terminal exit code ${exitCode ?? 'missing'}`);
                    }
                }
                else if (msg.type === 'error') {
                    const errorCode = typeof msg.code === 'string' ? msg.code : 'unknown_error';
                    const errorData = typeof msg.data === 'string' ? msg.data : JSON.stringify(msg.data ?? 'No error details provided');
                    setLogs((prev) => [...prev, `[ERROR] ${errorCode}: ${errorData}`]);
                    setIsRunning(false);
                    ws.close();
                    showNotification('error', `Agent execution failed: ${msg.data}`);
                }
            };
            ws.onerror = () => {
                showNotification('error', 'WebSocket connection error');
                setIsRunning(false);
            };
        }
        catch (error) {
            showNotification('error', `Execution error: ${error}`);
            setIsRunning(false);
        }
    };
    const downloadAgentExport = async () => {
        try {
            const response = await fetch('/api/agents/export');
            if (response.ok) {
                const blob = await response.blob();
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'agents-export.json';
                a.click();
                URL.revokeObjectURL(url);
                showNotification('success', 'Agents exported successfully');
            }
        }
        catch (error) {
            showNotification('error', 'Failed to export agents');
        }
    };
    const importAgentZip = async (file) => {
        try {
            const formData = new FormData();
            formData.append('file', file);
            const response = await fetch('/api/agents/import', {
                method: 'POST',
                body: formData,
            });
            if (response.ok) {
                showNotification('success', 'Agents imported successfully');
                fetchAgents();
            }
        }
        catch (error) {
            showNotification('error', 'Failed to import agents');
        }
    };
    if (loading) {
        return _jsx("div", { className: "agent-runner", children: _jsx("p", { role: "status", children: "Loading agent profiles\u2026" }) });
    }
    return (_jsxs("div", { className: "agent-runner", children: [notification && (_jsx("div", { className: `notification notification-${notification.type}`, children: notification.message })), _jsx("div", { className: "runner-header", children: _jsxs("div", { className: "runner-actions", children: [_jsx("button", { onClick: downloadAgentExport, className: "btn btn-secondary btn-small", "aria-label": "Export all agents", title: "Export all agents", children: "\u2193 Export" }), _jsxs("label", { className: "btn btn-secondary btn-small", title: "Import agents from ZIP", children: ["\u2191 Import", _jsx("input", { type: "file", accept: ".zip", "aria-label": "Import agents from ZIP", onChange: (e) => e.target.files && importAgentZip(e.target.files[0]) })] })] }) }), _jsx("div", { className: "execution-unavailable", role: "status", children: "Agent execution is unavailable. No governed execution capability is registered; Run is disabled." }), _jsxs("div", { className: "runner-grid", children: [_jsxs("div", { className: "agents-panel", children: [_jsxs("h3", { children: ["Available Agents (", agents.length, ")"] }), agents.length === 0 ? (_jsx("p", { children: "No agents created yet. Create one in Agent Builder." })) : (_jsx("div", { className: "agents-list", children: agents.map((agent) => (_jsxs("div", { className: `agent-item ${selectedAgent?.id === agent.id ? 'selected' : ''}`, role: "button", tabIndex: 0, "aria-label": `Open profile for ${agent.config.name}`, onClick: () => { setSelectedAgent(agent); setEditingAgent(false); }, onKeyDown: (event) => {
                                        if (event.key === 'Enter' || event.key === ' ') {
                                            event.preventDefault();
                                            setSelectedAgent(agent);
                                            setEditingAgent(false);
                                        }
                                    }, children: [_jsxs("div", { className: "agent-item-header", children: [_jsx("strong", { children: agent.config.name }), _jsx("span", { className: "badge", children: agent.config.type })] }), _jsx("p", { className: "agent-item-desc", children: agent.config.description }), _jsxs("p", { className: "agent-item-tools", children: ["Tools: ", agent.config.tools.length] }), _jsx("button", { onClick: (e) => {
                                                e.stopPropagation();
                                                executeAgent(agent);
                                            }, disabled: !AGENT_EXECUTION_AVAILABLE || isRunning, className: "btn btn-primary btn-small", title: "Agent execution is unavailable until a governed execution capability is registered.", children: "Run unavailable" })] }, agent.id))) }))] }), selectedAgent && _jsx("section", { className: "agent-profile-panel", "aria-label": `Agent profile: ${selectedAgent.config.name}`, children: editingAgent ? _jsx(AgentBuilder, { inline: true, agentId: selectedAgent.id, initialAgent: selectedAgent.config, onBack: () => setEditingAgent(false), onAgentCreated: (config) => {
                                setAgents((current) => current.map((agent) => agent.id === selectedAgent.id ? { ...agent, config } : agent));
                                setSelectedAgent((current) => current?.id === selectedAgent.id ? { ...current, config } : current);
                                setEditingAgent(false);
                                void fetchAgents();
                            } }) : _jsxs(_Fragment, { children: [_jsxs("header", { className: "agent-profile-header", children: [_jsxs("div", { children: [_jsx("span", { className: "agent-profile-kicker", children: "AGENT PROFILE" }), _jsx("h3", { children: selectedAgent.config.name }), _jsx("span", { className: "badge", children: selectedAgent.config.type })] }), _jsxs("div", { className: "agent-profile-actions", children: [_jsx("button", { type: "button", className: "btn btn-primary btn-small", onClick: () => setEditingAgent(true), children: "Edit agent" }), _jsx("button", { type: "button", className: "btn btn-secondary btn-small", onClick: () => { setSelectedAgent(null); setEditingAgent(false); }, children: "Close" })] })] }), _jsxs("dl", { className: "agent-profile-fields", children: [_jsxs("div", { children: [_jsx("dt", { children: "Description" }), _jsx("dd", { children: selectedAgent.config.description || 'No description provided.' })] }), _jsxs("div", { children: [_jsx("dt", { children: "Provider and model" }), _jsxs("dd", { children: [selectedAgent.config.provider_id || 'No provider recorded', " \u00B7 ", selectedAgent.config.model_id || 'No model assigned'] })] }), _jsxs("div", { children: [_jsxs("dt", { children: ["Tools (", selectedAgent.config.tools.length, ")"] }), _jsx("dd", { children: selectedAgent.config.tools.length ? _jsx("ul", { children: selectedAgent.config.tools.map((tool) => _jsx("li", { children: _jsx("code", { children: tool }) }, tool)) }) : 'No tools assigned' })] }), _jsxs("div", { className: "agent-profile-prompt", children: [_jsx("dt", { children: "System prompt" }), _jsx("dd", { children: _jsx("pre", { children: selectedAgent.config.system_prompt || 'No system prompt provided.' }) })] }), _jsxs("div", { children: [_jsx("dt", { children: "Created" }), _jsx("dd", { children: _jsx("time", { dateTime: selectedAgent.created_at, children: new Date(selectedAgent.created_at).toLocaleString() }) })] })] })] }) })] })] }));
}
