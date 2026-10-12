import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import './Control.css';
import './WindowsSurface.css';
import { useState } from 'react';
import TerminalPane from './TerminalPane';
import WindowPanel from './WindowPanel';
export default function Control({ onDemoRun }) {
    const [isRunning, setIsRunning] = useState(false);
    const [logs, setLogs] = useState([]);
    const [writeEvidence, setWriteEvidence] = useState(false);
    const [jsonOutput, setJsonOutput] = useState(false);
    const [status, setStatus] = useState('idle');
    const [exitCode, setExitCode] = useState(null);
    const runDemoWebSocket = async () => {
        setIsRunning(true);
        setLogs([]);
        setStatus('running');
        setExitCode(null);
        try {
            const websocketUrl = new URL('/ws/demo/run', window.location.href);
            websocketUrl.protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const ws = new WebSocket(websocketUrl);
            ws.onopen = () => {
                ws.send(JSON.stringify({
                    write_evidence: writeEvidence,
                    json_output: jsonOutput,
                }));
            };
            ws.onmessage = (event) => {
                const msg = JSON.parse(event.data);
                if (msg.type === 'stdout') {
                    setLogs((prev) => [...prev, msg.data]);
                }
                else if (msg.type === 'done') {
                    setExitCode(msg.exit_code);
                    setStatus(msg.exit_code === 0 ? 'success' : 'error');
                    setIsRunning(false);
                    ws.close();
                    if (onDemoRun)
                        onDemoRun();
                }
                else if (msg.type === 'error') {
                    setLogs((prev) => [...prev, `ERROR: ${msg.data}`]);
                    setStatus('error');
                    setIsRunning(false);
                    ws.close();
                }
            };
            ws.onerror = (error) => {
                setLogs((prev) => [...prev, `WebSocket error: ${error}`]);
                setStatus('error');
                setIsRunning(false);
            };
            ws.onclose = () => {
                if (status === 'running') {
                    setStatus('error');
                    setIsRunning(false);
                }
            };
        }
        catch (error) {
            setLogs((prev) => [...prev, `Connection error: ${error}`]);
            setStatus('error');
            setIsRunning(false);
        }
    };
    const runDemoHTTP = async () => {
        setIsRunning(true);
        setLogs([]);
        setStatus('running');
        setExitCode(null);
        try {
            const response = await fetch('/api/demo/run', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    write_evidence: writeEvidence,
                    json_output: jsonOutput,
                }),
            });
            const data = await response.json();
            setLogs((data.stdout + '\n' + data.stderr).split('\n').filter(Boolean));
            setExitCode(data.exit_code);
            setStatus(data.exit_code === 0 ? 'success' : 'error');
            setIsRunning(false);
            if (onDemoRun)
                onDemoRun();
        }
        catch (error) {
            setLogs((prev) => [...prev, `Error: ${error}`]);
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
        a.download = `demo-logs-${new Date().toISOString()}.txt`;
        a.click();
        URL.revokeObjectURL(url);
    };
    const clearLogs = () => {
        setLogs([]);
    };
    return (_jsxs("div", { className: "control-container", children: [_jsxs(WindowPanel, { title: "Demo orchestration", description: "Run and inspect the existing demo", className: "control-panel", children: [_jsxs("div", { className: "control-section", children: [_jsx("h3", { children: "Execute Demo" }), _jsxs("div", { className: "control-options", children: [_jsxs("label", { className: "checkbox", children: [_jsx("input", { type: "checkbox", checked: writeEvidence, onChange: (e) => setWriteEvidence(e.target.checked), disabled: isRunning }), "Write Evidence Bundle"] }), _jsxs("label", { className: "checkbox", children: [_jsx("input", { type: "checkbox", checked: jsonOutput, onChange: (e) => setJsonOutput(e.target.checked), disabled: isRunning }), "JSON Output"] })] }), _jsxs("div", { className: "button-group", children: [_jsx("button", { onClick: runDemoWebSocket, disabled: isRunning, className: `btn btn-primary ${isRunning ? 'disabled' : ''}`, children: isRunning ? 'Running...' : 'Run demo (WebSocket)' }), _jsx("button", { onClick: runDemoHTTP, disabled: isRunning, className: `btn btn-secondary ${isRunning ? 'disabled' : ''}`, children: isRunning ? 'Running...' : 'Run demo (HTTP)' })] })] }), _jsxs("div", { className: "status-section", children: [_jsxs("div", { className: `status-badge ${status}`, children: [status === 'idle' && 'Idle', status === 'running' && 'Running', status === 'success' && 'Success', status === 'error' && 'Error'] }), exitCode !== null && (_jsxs("div", { className: "exit-code", children: ["Exit Code: ", _jsx("strong", { children: exitCode })] }))] }), _jsxs("div", { className: "logs-section", children: [_jsxs("div", { className: "logs-header", children: [_jsx("h3", { children: "Execution Logs" }), _jsxs("div", { className: "logs-actions", children: [_jsx("button", { onClick: clearLogs, className: "btn btn-small", disabled: isRunning, children: "Clear" }), _jsx("button", { onClick: downloadLogs, className: "btn btn-small", disabled: logs.length === 0, children: "Download" })] })] }), _jsx(TerminalPane, { status: status, exitCode: exitCode, logs: logs, emptyMessage: "No logs yet. Run demo to see output." })] })] }), _jsxs("div", { className: "control-sidebar", children: [_jsxs("div", { className: "card", children: [_jsx("h3", { children: "Quick Info" }), _jsxs("p", { children: [_jsx("strong", { children: "Endpoint:" }), " ", window.location.origin] }), _jsxs("p", { children: [_jsx("strong", { children: "WebSocket:" }), " ", window.location.protocol === 'https:' ? 'wss:' : 'ws:', "//", window.location.host, "/ws/demo/run"] }), _jsxs("p", { children: [_jsx("strong", { children: "API:" }), " /api/demo/run (POST)"] })] }), _jsxs("div", { className: "card", children: [_jsx("h3", { children: "What This Does" }), _jsxs("ul", { children: [_jsxs("li", { children: ["Executes ", _jsx("code", { children: "python demo.py" })] }), _jsx("li", { children: "Streams logs in real time" }), _jsx("li", { children: "Captures exit code" }), _jsx("li", { children: "Optional evidence bundle" }), _jsx("li", { children: "Optional JSON output" }), _jsx("li", { children: "Downloadable logs" })] })] }), _jsxs("div", { className: "card", children: [_jsx("h3", { children: "Next Steps" }), _jsxs("ul", { children: [_jsx("li", { children: "1. Run demo via this panel" }), _jsx("li", { children: "2. Check logs for errors" }), _jsx("li", { children: "3. Refresh Summary tab" }), _jsx("li", { children: "4. View results" })] })] })] })] }));
}
