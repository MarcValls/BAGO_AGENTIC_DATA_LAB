import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from 'react';
import './AgentExecutor.css';
export default function AgentExecutor({ agent, onExecutionComplete }) {
    const [isRunning, setIsRunning] = useState(false);
    const [logs, setLogs] = useState([]);
    const [result, setResult] = useState(null);
    const [status, setStatus] = useState('idle');
    const executeAgent = async () => {
        setIsRunning(true);
        setLogs([]);
        setStatus('running');
        setResult(null);
        try {
            const ws = new WebSocket('ws://localhost:8080/ws/agents/run');
            ws.onopen = () => {
                ws.send(JSON.stringify({
                    agent_id: agent.id,
                    config: agent.config,
                }));
                setLogs((prev) => [...prev, `[INFO] Connecting to agent execution service...`]);
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
                        exit_code: msg.exit_code,
                        duration_ms: msg.duration_ms || 0,
                        cost_usd: msg.cost_usd || 0,
                        metrics: msg.metrics,
                    };
                    setResult(result);
                    setStatus(msg.exit_code === 0 ? 'success' : 'error');
                    setIsRunning(false);
                    ws.close();
                    if (onExecutionComplete)
                        onExecutionComplete(result);
                }
                else if (msg.type === 'error') {
                    setLogs((prev) => [...prev, `[ERROR] ${msg.data}`]);
                    setStatus('error');
                    setIsRunning(false);
                    ws.close();
                }
            };
            ws.onerror = (error) => {
                setLogs((prev) => [...prev, `[ERROR] WebSocket error: ${error}`]);
                setStatus('error');
                setIsRunning(false);
            };
        }
        catch (error) {
            setLogs((prev) => [...prev, `[ERROR] ${error}`]);
            setStatus('error');
            setIsRunning(false);
        }
    };
    const downloadLogs = () => {
        const content = logs.join('\n');
        const blob = new Blob([content], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `agent-${agent.id}-logs.txt`;
        a.click();
        URL.revokeObjectURL(url);
    };
    return (_jsxs("div", { className: "agent-executor", children: [_jsxs("div", { className: "executor-header", children: [_jsx("h3", { children: agent.config.name }), _jsx("button", { onClick: executeAgent, disabled: isRunning, className: `btn btn-primary ${isRunning ? 'disabled' : ''}`, children: isRunning ? '⏳ Running...' : '▶ Execute' })] }), _jsxs("div", { className: "executor-info", children: [_jsxs("p", { children: [_jsx("strong", { children: "Type:" }), " ", agent.config.type] }), _jsxs("p", { children: [_jsx("strong", { children: "Description:" }), " ", agent.config.description] }), agent.config.tools.length > 0 && (_jsxs("p", { children: [_jsx("strong", { children: "Tools:" }), " ", agent.config.tools.join(', ')] }))] }), _jsxs("div", { className: `status-badge ${status}`, children: [status === 'idle' && '⚪ Idle', status === 'running' && '🟡 Running', status === 'success' && '🟢 Success', status === 'error' && '🔴 Error'] }), _jsxs("div", { className: "executor-logs", children: [_jsxs("div", { className: "logs-header", children: [_jsx("h4", { children: "Execution Logs" }), _jsx("button", { onClick: downloadLogs, disabled: logs.length === 0, className: "btn btn-small", children: "Download" })] }), _jsx("div", { className: "logs-content", children: logs.length === 0 ? (_jsx("p", { style: { color: 'rgba(255, 255, 255, 0.4)' }, children: "No logs yet." })) : (logs.map((line, idx) => (_jsx("div", { className: "log-line", children: line }, idx)))) })] }), result && (_jsxs("div", { className: "executor-result", children: [_jsx("h4", { children: "Execution Result" }), _jsxs("div", { className: "result-grid", children: [_jsxs("div", { className: "result-item", children: [_jsx("strong", { children: "Job ID:" }), _jsx("code", { children: result.job_id })] }), _jsxs("div", { className: "result-item", children: [_jsx("strong", { children: "Status:" }), _jsx("span", { className: `badge badge-${result.status}`, children: result.status })] }), _jsxs("div", { className: "result-item", children: [_jsx("strong", { children: "Duration:" }), _jsxs("span", { children: [(result.duration_ms / 1000).toFixed(2), "s"] })] }), _jsxs("div", { className: "result-item", children: [_jsx("strong", { children: "Cost:" }), _jsxs("span", { children: ["$", result.cost_usd.toFixed(4)] })] }), _jsxs("div", { className: "result-item", children: [_jsx("strong", { children: "Exit Code:" }), _jsx("code", { children: result.exit_code })] })] }), result.metrics && Object.keys(result.metrics).length > 0 && (_jsxs("div", { className: "result-metrics", children: [_jsx("h5", { children: "Metrics" }), Object.entries(result.metrics).map(([key, value]) => (_jsxs("div", { className: "metric-item", children: [_jsxs("strong", { children: [key, ":"] }), " ", JSON.stringify(value)] }, key)))] }))] }))] }));
}
