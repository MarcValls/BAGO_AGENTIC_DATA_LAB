import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState, useEffect } from 'react';
import './AgentRunner.css';
export default function AgentRunner() {
    const [agents, setAgents] = useState([]);
    const [loading, setLoading] = useState(true);
    const [selectedAgent, setSelectedAgent] = useState(null);
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
                    const result = {
                        job_id: msg.job_id,
                        status: msg.exit_code === 0 ? 'success' : 'failed',
                        duration_ms: msg.duration_ms || 0,
                        cost_usd: msg.cost_usd || 0,
                    };
                    setResult(result);
                    setIsRunning(false);
                    ws.close();
                    showNotification('success', `Agent ${agent.config.name} executed successfully`);
                }
                else if (msg.type === 'error') {
                    setLogs((prev) => [...prev, `[ERROR] ${msg.data}`]);
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
    const downloadAgentZip = async () => {
        try {
            const response = await fetch('/api/agents/export');
            if (response.ok) {
                const blob = await response.blob();
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'agents-export.zip';
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
        return _jsx("div", { className: "agent-runner", children: "Loading agents..." });
    }
    return (_jsxs("div", { className: "agent-runner", children: [notification && (_jsx("div", { className: `notification notification-${notification.type}`, children: notification.message })), _jsxs("div", { className: "runner-header", children: [_jsx("h2", { children: "\uD83C\uDFAF Agent Runner" }), _jsxs("div", { className: "runner-actions", children: [_jsx("button", { onClick: downloadAgentZip, className: "btn btn-secondary btn-small", children: "\u2B07\uFE0F Export All" }), _jsxs("label", { className: "btn btn-secondary btn-small", children: ["\u2B06\uFE0F Import", _jsx("input", { type: "file", accept: ".zip", onChange: (e) => e.target.files && importAgentZip(e.target.files[0]), style: { display: 'none' } })] })] })] }), _jsxs("div", { className: "runner-grid", children: [_jsxs("div", { className: "agents-panel", children: [_jsxs("h3", { children: ["Available Agents (", agents.length, ")"] }), agents.length === 0 ? (_jsx("p", { style: { color: 'rgba(255, 255, 255, 0.5)' }, children: "No agents created yet. Create one in Agent Builder." })) : (_jsx("div", { className: "agents-list", children: agents.map((agent) => (_jsxs("div", { className: `agent-item ${selectedAgent?.id === agent.id ? 'selected' : ''}`, onClick: () => setSelectedAgent(agent), children: [_jsxs("div", { className: "agent-item-header", children: [_jsx("strong", { children: agent.config.name }), _jsx("span", { className: "badge", children: agent.config.type })] }), _jsx("p", { className: "agent-item-desc", children: agent.config.description }), _jsxs("p", { className: "agent-item-tools", children: ["Tools: ", agent.config.tools.length] }), _jsx("button", { onClick: (e) => {
                                                e.stopPropagation();
                                                executeAgent(agent);
                                            }, disabled: isRunning, className: "btn btn-primary btn-small", children: isRunning && selectedAgent?.id === agent.id ? '⏳ Running' : '▶ Run' })] }, agent.id))) }))] }), selectedAgent && (_jsxs("div", { className: "execution-panel", children: [_jsxs("h3", { children: ["Execution: ", selectedAgent.config.name] }), _jsxs("div", { className: "execution-logs", children: [_jsx("h4", { children: "Logs" }), _jsx("div", { className: "logs-box", children: logs.length === 0 ? (_jsx("p", { style: { color: 'rgba(255, 255, 255, 0.4)' }, children: "Awaiting execution..." })) : (logs.map((line, idx) => (_jsx("div", { className: "log-line", children: line }, idx)))) })] }), result && (_jsxs("div", { className: "execution-result", children: [_jsx("h4", { children: "Result" }), _jsxs("div", { className: "result-details", children: [_jsxs("div", { children: [_jsx("strong", { children: "Status:" }), " ", _jsx("span", { className: `badge badge-${result.status}`, children: result.status })] }), _jsxs("div", { children: [_jsx("strong", { children: "Job ID:" }), " ", _jsx("code", { children: result.job_id })] }), _jsxs("div", { children: [_jsx("strong", { children: "Duration:" }), " ", (result.duration_ms / 1000).toFixed(2), "s"] }), _jsxs("div", { children: [_jsx("strong", { children: "Cost:" }), " $", result.cost_usd.toFixed(4)] })] })] }))] }))] })] }));
}
