import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import './AgentRunner.css';
import { useEffect, useRef, useState } from 'react';
import AgentBuilder from './AgentBuilder';
function isRecord(value) {
    return value !== null && typeof value === 'object' && !Array.isArray(value);
}
function hasText(value) {
    return typeof value === 'string' && value.trim().length > 0;
}
function readProposal(value, selectedAgentId) {
    if (!isRecord(value) || value.type !== 'proposal')
        return undefined;
    if ('challenge_id' in value || 'permit_token' in value || 'permit' in value)
        return undefined;
    if (value.agent_id !== selectedAgentId || !hasText(value.run_id) || !hasText(value.proposal_id) || !hasText(value.request_id) || !hasText(value.effect_id))
        return undefined;
    if (typeof value.approval_required !== 'boolean' || !isRecord(value.target) || !isRecord(value.arguments))
        return undefined;
    if (!hasText(value.operation_sha256) || value.task_status !== 'awaiting_review' || value.effect_status !== 'proposed')
        return undefined;
    return value;
}
function websocketUrl() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.hostname || 'localhost';
    const port = window.location.port === '5173' ? '8080' : window.location.port || '8080';
    return `${protocol}//${host}:${port}/ws/agents/run`;
}
function exactCompletion(value, proposal) {
    const execution = value.execution;
    const approval = value.approval;
    const approvalMatches = !proposal.approval_required || (isRecord(approval)
        && approval.request_id === proposal.request_id
        && typeof approval.state === 'string'
        && ['approved', 'authorized', 'ALLOW'].includes(approval.state));
    return value.type === 'completed'
        && approvalMatches
        && value.run_id === proposal.run_id
        && value.proposal_id === proposal.proposal_id
        && value.request_id === proposal.request_id
        && value.effect_id === proposal.effect_id
        && isRecord(execution)
        && execution.verified_success === true
        && execution.request_id === proposal.request_id
        && hasText(execution.receipt_id)
        && hasText(execution.ber_execution_id);
}
function displayValue(value) {
    if (typeof value === 'string' && value.length)
        return value;
    if (value === null || value === undefined || value === '')
        return 'Not provided';
    try {
        return JSON.stringify(value, null, 2);
    }
    catch {
        return 'Not provided';
    }
}
function authorizationState(outcome) {
    if (isRecord(outcome.approval) && hasText(outcome.approval.state))
        return outcome.approval.state;
    if (isRecord(outcome.authorization) && hasText(outcome.authorization.state))
        return outcome.authorization.state;
    if (isRecord(outcome.execution) && isRecord(outcome.execution.authorization) && hasText(outcome.execution.authorization.state))
        return outcome.execution.authorization.state;
    if (outcome.type === 'rejected' || outcome.type === 'cancelled')
        return 'Not requested';
    return 'Not provided';
}
function LocalTraceProjection({ trace, expectedExecutionId }) {
    if (!isRecord(trace))
        return _jsx("p", { role: "status", children: "LocalTrace projection not provided." });
    const traceId = hasText(trace.trace_id) ? trace.trace_id : undefined;
    const traceRunId = hasText(trace.run_id) ? trace.run_id : undefined;
    const events = Array.isArray(trace.events) ? trace.events.filter(isRecord) : [];
    const bound = Boolean(traceId && traceRunId && (!expectedExecutionId || traceRunId === expectedExecutionId));
    return (_jsxs("section", { className: "agent-runner__trace", "aria-label": "LocalTrace projection", children: [_jsx("h4", { children: "LocalTrace projection" }), _jsx("p", { children: "This ADL projection is observational; BAGO authorization and the BER receipt remain authoritative." }), _jsxs("dl", { children: [_jsxs("div", { children: [_jsx("dt", { children: "Trace ID" }), _jsx("dd", { children: _jsx("code", { children: traceId || 'Not provided' }) })] }), _jsxs("div", { children: [_jsx("dt", { children: "BER execution ID" }), _jsx("dd", { children: _jsx("code", { children: traceRunId || 'Not provided' }) })] }), _jsxs("div", { children: [_jsx("dt", { children: "Identity binding" }), _jsx("dd", { children: bound ? 'Matches supplied BER execution ID' : 'Unverified or mismatched' })] })] }), events.length ? _jsx("ol", { "aria-label": "LocalTrace events", children: events.map((event, index) => (_jsxs("li", { children: [_jsx("strong", { children: displayValue(event.name) }), _jsxs("span", { children: ["Status: ", displayValue(event.status)] }), _jsxs("span", { children: ["Event ID: ", _jsx("code", { children: displayValue(event.event_id) })] }), _jsxs("span", { children: ["Sequence: ", displayValue(event.sequence)] })] }, hasText(event.event_id) ? event.event_id : `event-${index}`))) }) : _jsx("p", { children: "No LocalTrace events were provided." })] }));
}
const stateMessages = {
    idle: 'Select an agent and enter a task to begin.',
    connecting: 'Connecting to the governed Agent Runner.',
    awaiting_proposal: 'The server is preparing a response or a reviewable proposal.',
    awaiting_review: 'Review the exact proposed effect and arguments before choosing.',
    decision_pending: 'Your decision was sent; waiting for the BAGO authorization and execution outcome.',
    task_answered: 'The task was answered without starting an effect.',
    rejected: 'The proposal was rejected. No effect was executed.',
    cancelled: 'The proposal was cancelled. No effect was executed.',
    authorization_denied: 'BAGO did not authorize this proposal. No effect was executed.',
    completed: 'BAGO BER completed the effect and returned an identity-matched verified receipt.',
    execution_unverified: 'Execution or receipt identity could not be verified. This is not success.',
    error: 'The Agent Runner could not complete this session.',
};
export default function AgentRunner() {
    const [agents, setAgents] = useState([]);
    const [loading, setLoading] = useState(true);
    const [agentsError, setAgentsError] = useState(null);
    const [selectedAgent, setSelectedAgent] = useState(null);
    const [editingAgent, setEditingAgent] = useState(false);
    const [task, setTask] = useState('');
    const [runState, setRunState] = useState('idle');
    const [proposal, setProposal] = useState(null);
    const [outcome, setOutcome] = useState(null);
    const [decision, setDecision] = useState(null);
    const socketRef = useRef(null);
    const terminalRef = useRef(false);
    useEffect(() => {
        void fetchAgents();
        return () => {
            socketRef.current?.close();
            socketRef.current = null;
        };
    }, []);
    const fetchAgents = async () => {
        setLoading(true);
        setAgentsError(null);
        try {
            const response = await fetch('/api/agents/list');
            if (!response.ok)
                throw new Error('Agent profiles could not be loaded.');
            const data = await response.json();
            const listed = isRecord(data) && Array.isArray(data.agents) ? data.agents.filter(isRecord) : [];
            setAgents(listed);
            setSelectedAgent(current => current ? listed.find(agent => agent.id === current.id) ?? null : null);
        }
        catch {
            setAgentsError('Agent profiles could not be loaded. Retry the request.');
        }
        finally {
            setLoading(false);
        }
    };
    const startRun = (event) => {
        event.preventDefault();
        if (!selectedAgent || !task.trim() || socketRef.current || loading)
            return;
        setProposal(null);
        setOutcome(null);
        setDecision(null);
        terminalRef.current = false;
        setRunState('connecting');
        let currentProposal = null;
        let socket;
        try {
            socket = new WebSocket(websocketUrl());
            socketRef.current = socket;
        }
        catch {
            terminalRef.current = true;
            socketRef.current = null;
            setRunState('error');
            setOutcome({ type: 'error', code: 'connection_failed', data: 'The local Agent Runner connection could not be opened.' });
            return;
        }
        const finish = () => {
            terminalRef.current = true;
            if (socketRef.current === socket)
                socketRef.current = null;
            socket.close();
        };
        socket.onopen = () => {
            setRunState('awaiting_proposal');
            try {
                socket.send(JSON.stringify({ type: 'start', agent_id: selectedAgent.id, task: task.trim() }));
            }
            catch {
                finish();
                setRunState('error');
                setOutcome({ type: 'error', code: 'send_failed', data: 'The task could not be sent to the local Agent Runner.' });
            }
        };
        socket.onmessage = (event) => {
            let frame;
            try {
                frame = JSON.parse(String(event.data));
            }
            catch {
                finish();
                setRunState('error');
                setOutcome({ type: 'error', code: 'invalid_message', data: 'The Agent Runner returned an unreadable message.' });
                return;
            }
            if (!isRecord(frame) || typeof frame.type !== 'string') {
                finish();
                setRunState('error');
                setOutcome({ type: 'error', code: 'invalid_message', data: 'The Agent Runner returned an unsupported message.' });
                return;
            }
            if (frame.type === 'proposal') {
                const received = readProposal(frame, selectedAgent.id);
                if (!received) {
                    finish();
                    setRunState('error');
                    setOutcome({ type: 'error', code: 'invalid_proposal', data: 'The proposal is incomplete or does not match the selected profile.' });
                    return;
                }
                currentProposal = received;
                setProposal(received);
                setRunState('awaiting_review');
                return;
            }
            const result = frame;
            if (frame.type === 'task_result') {
                finish();
                setOutcome(result);
                setRunState(result.task_status === 'answered' && result.effect_status === 'not_started' && typeof result.answer === 'string' ? 'task_answered' : 'error');
                return;
            }
            if (frame.type === 'rejected' || frame.type === 'cancelled') {
                finish();
                const matches = Boolean(currentProposal && result.run_id === currentProposal.run_id && result.proposal_id === currentProposal.proposal_id && result.request_id === currentProposal.request_id && result.effect_status === 'not_executed');
                setOutcome(result);
                setRunState(matches ? frame.type : 'error');
                return;
            }
            if (frame.type === 'authorization_denied') {
                finish();
                const matches = Boolean(currentProposal && result.run_id === currentProposal.run_id && result.proposal_id === currentProposal.proposal_id && result.request_id === currentProposal.request_id && result.effect_status === 'not_executed');
                setOutcome(result);
                setRunState(matches ? 'authorization_denied' : 'error');
                return;
            }
            if (frame.type === 'completed' || frame.type === 'execution_unverified') {
                finish();
                setOutcome(result);
                setRunState(currentProposal && exactCompletion(result, currentProposal) ? 'completed' : 'execution_unverified');
                return;
            }
            if (frame.type === 'error') {
                finish();
                setOutcome(result);
                setRunState('error');
                return;
            }
            finish();
            setOutcome({ type: 'error', code: 'unsupported_message', data: `The Agent Runner returned unsupported state “${frame.type}”.` });
            setRunState('error');
        };
        socket.onerror = () => {
            if (terminalRef.current)
                return;
            finish();
            setOutcome({ type: 'error', code: 'websocket_error', data: 'The local Agent Runner connection failed.' });
            setRunState('error');
        };
        socket.onclose = () => {
            if (terminalRef.current)
                return;
            terminalRef.current = true;
            if (socketRef.current === socket)
                socketRef.current = null;
            setOutcome({ type: 'error', code: 'client_disconnected', data: 'The connection closed before a terminal outcome was received.' });
            setRunState('error');
        };
    };
    const decide = (choice) => {
        const socket = socketRef.current;
        if (!socket || socket.readyState !== WebSocket.OPEN || !proposal || runState !== 'awaiting_review')
            return;
        setDecision(choice);
        setRunState('decision_pending');
        try {
            socket.send(JSON.stringify({ type: 'decision', proposal_id: proposal.proposal_id, decision: choice }));
        }
        catch {
            socket.close();
            socketRef.current = null;
            terminalRef.current = true;
            setOutcome({ type: 'error', code: 'decision_send_failed', data: 'The review decision could not be sent.' });
            setRunState('error');
        }
    };
    const downloadAgentExport = async () => {
        try {
            const response = await fetch('/api/agents/export');
            if (!response.ok)
                throw new Error();
            const blob = await response.blob();
            const url = URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = url;
            link.download = 'agents-export.json';
            link.click();
            URL.revokeObjectURL(url);
        }
        catch {
            setAgentsError('Agent profiles could not be exported.');
        }
    };
    const importAgentZip = async (file) => {
        try {
            const formData = new FormData();
            formData.append('file', file);
            const response = await fetch('/api/agents/import', { method: 'POST', body: formData });
            if (!response.ok)
                throw new Error();
            await fetchAgents();
        }
        catch {
            setAgentsError('The agent profile archive could not be imported.');
        }
    };
    if (loading)
        return _jsxs("div", { className: "agent-runner", children: [_jsx("h2", { children: "Agent Runner" }), _jsx("p", { role: "status", children: "Loading agent profiles." })] });
    return (_jsxs("div", { className: "agent-runner", children: [_jsxs("header", { className: "runner-header", children: [_jsx("h2", { children: "Agent Runner" }), _jsxs("div", { className: "runner-actions", children: [_jsx("button", { type: "button", onClick: downloadAgentExport, className: "btn btn-secondary btn-small", "aria-label": "Export all agents", children: "Export all agents" }), _jsxs("label", { className: "btn btn-secondary btn-small", children: ["Import agents", _jsx("input", { type: "file", accept: ".zip", "aria-label": "Import agent profiles from ZIP", onChange: event => { const file = event.target.files?.[0]; if (file)
                                            void importAgentZip(file); } })] })] })] }), agentsError && _jsxs("section", { className: "agent-runner__error", role: "alert", children: [_jsx("p", { children: agentsError }), _jsx("button", { type: "button", onClick: () => void fetchAgents(), children: "Retry profile request" })] }), _jsxs("section", { className: "agents-panel", "aria-labelledby": "runner-agents-title", children: [_jsx("h3", { id: "runner-agents-title", children: "Select an agent profile" }), !agentsError && agents.length === 0 ? _jsx("p", { children: "No saved agent profiles were provided." }) : _jsx("ul", { className: "agents-list", children: agents.map(agent => _jsx("li", { className: selectedAgent?.id === agent.id ? 'selected' : undefined, children: _jsxs("button", { type: "button", "aria-pressed": selectedAgent?.id === agent.id, onClick: () => { setSelectedAgent(agent); setEditingAgent(false); }, children: [_jsx("strong", { children: agent.config.name }), _jsx("span", { children: agent.config.description }), _jsxs("span", { children: ["Provider: ", agent.config.provider_id || 'Not provided', " \u00B7 Model: ", agent.config.model_id || 'Not provided'] })] }) }, agent.id)) })] }), selectedAgent && _jsxs("section", { className: "agent-profile-panel", "aria-labelledby": "runner-profile-title", children: [_jsxs("header", { className: "agent-profile-header", children: [_jsxs("div", { children: [_jsx("span", { className: "agent-profile-kicker", children: "SAVED PROFILE" }), _jsx("h3", { id: "runner-profile-title", children: selectedAgent.config.name })] }), _jsx("button", { type: "button", className: "btn btn-secondary btn-small", onClick: () => setEditingAgent(current => !current), children: editingAgent ? 'Close editor' : 'Edit profile' })] }), editingAgent ? _jsx(AgentBuilder, { inline: true, agentId: selectedAgent.id, initialAgent: selectedAgent.config, onBack: () => setEditingAgent(false), onAgentCreated: config => {
                            setAgents(current => current.map(agent => agent.id === selectedAgent.id ? { ...agent, config } : agent));
                            setSelectedAgent(current => current?.id === selectedAgent.id ? { ...current, config } : current);
                            setEditingAgent(false);
                            void fetchAgents();
                        } }) : _jsxs("dl", { className: "agent-profile-fields", children: [_jsxs("div", { children: [_jsx("dt", { children: "Provider and model" }), _jsxs("dd", { children: [selectedAgent.config.provider_id || 'Not provided', " \u00B7 ", selectedAgent.config.model_id || 'Not provided'] })] }), _jsxs("div", { children: [_jsx("dt", { children: "Registered tools" }), _jsx("dd", { children: selectedAgent.config.tools.length ? selectedAgent.config.tools.join(', ') : 'No tools registered' })] })] })] }), _jsxs("form", { className: "agent-runner__task", onSubmit: startRun, children: [_jsx("label", { htmlFor: "agent-runner-task", children: "Task" }), _jsx("textarea", { id: "agent-runner-task", value: task, onChange: event => setTask(event.target.value), maxLength: 8000, rows: 4, placeholder: "Describe what this agent should do in the bound workspace." }), _jsx("button", { type: "submit", className: "btn btn-primary", disabled: !selectedAgent || !task.trim() || runState === 'connecting' || runState === 'awaiting_proposal' || runState === 'awaiting_review' || runState === 'decision_pending', children: "Start task" })] }), _jsxs("section", { className: "agent-runner__session", "aria-labelledby": "agent-runner-session-title", children: [_jsx("h3", { id: "agent-runner-session-title", children: "Run review and outcome" }), _jsx("p", { className: `agent-runner__status agent-runner__status--${runState}`, role: "status", "aria-live": "polite", children: stateMessages[runState] }), runState === 'error' && outcome && _jsxs("p", { className: "agent-runner__safe-error", role: "alert", children: [_jsx("strong", { children: outcome.code || 'runner_error' }), ": ", typeof outcome.data === 'string' ? outcome.data : 'No safe error details were provided.'] }), proposal && _jsxs("article", { className: "agent-runner__proposal", "aria-labelledby": "agent-runner-proposal-title", children: [_jsx("h4", { id: "agent-runner-proposal-title", children: "Review proposed action" }), _jsx("p", { children: "This is proposed intent. Nothing has executed yet." }), _jsxs("dl", { children: [_jsxs("div", { children: [_jsx("dt", { children: "Proposal ID" }), _jsx("dd", { children: _jsx("code", { children: proposal.proposal_id }) })] }), _jsxs("div", { children: [_jsx("dt", { children: "Run ID" }), _jsx("dd", { children: _jsx("code", { children: proposal.run_id }) })] }), _jsxs("div", { children: [_jsx("dt", { children: "Request ID" }), _jsx("dd", { children: _jsx("code", { children: proposal.request_id }) })] }), _jsxs("div", { children: [_jsx("dt", { children: "Effect" }), _jsx("dd", { children: _jsx("code", { children: proposal.effect_id }) })] }), _jsxs("div", { children: [_jsx("dt", { children: "Target" }), _jsx("dd", { children: _jsx("pre", { children: JSON.stringify(proposal.target, null, 2) }) })] }), _jsxs("div", { children: [_jsx("dt", { children: "Arguments" }), _jsx("dd", { children: _jsx("pre", { children: JSON.stringify(proposal.arguments, null, 2) }) })] }), _jsxs("div", { children: [_jsx("dt", { children: "Operation SHA-256" }), _jsx("dd", { children: _jsx("code", { children: proposal.operation_sha256 }) })] }), _jsxs("div", { children: [_jsx("dt", { children: "World-state digest" }), _jsx("dd", { children: _jsx("code", { children: displayValue(proposal.world_state_digest) }) })] }), _jsxs("div", { children: [_jsx("dt", { children: "Proposal expiry" }), _jsx("dd", { children: displayValue(proposal.expires_at) })] }), _jsxs("div", { children: [_jsx("dt", { children: "BAGO approval" }), _jsx("dd", { children: proposal.approval_required ? 'Required after your review' : 'Not required by BAGO; your review is still required' })] })] }), _jsxs("div", { className: "agent-runner__decision-actions", "aria-label": "Review decision", children: [_jsx("button", { type: "button", onClick: () => decide('approve'), disabled: runState !== 'awaiting_review', children: "Approve proposal" }), _jsx("button", { type: "button", onClick: () => decide('reject'), disabled: runState !== 'awaiting_review', children: "Reject proposal" }), _jsx("button", { type: "button", onClick: () => decide('cancel'), disabled: runState !== 'awaiting_review', children: "Cancel proposal" })] }), decision && _jsxs("p", { children: ["Submitted review decision: ", _jsx("strong", { children: decision })] })] }), outcome?.type === 'task_result' && _jsxs("section", { className: "agent-runner__answer", "aria-label": "Task answer", children: [_jsx("h4", { children: "Task answer" }), _jsx("p", { children: typeof outcome.answer === 'string' ? outcome.answer : 'Answer not provided.' }), _jsxs("p", { children: ["Task status: ", displayValue(outcome.task_status), " \u00B7 Effect status: ", displayValue(outcome.effect_status)] })] }), outcome && (outcome.type === 'completed' || outcome.type === 'execution_unverified' || outcome.type === 'authorization_denied' || outcome.type === 'rejected' || outcome.type === 'cancelled') && _jsxs("section", { className: "agent-runner__outcome", "aria-label": "Governed action outcome", children: [_jsx("h4", { children: runState === 'completed' ? 'Verified BER execution' : runState === 'authorization_denied' ? 'Authorization denied' : runState === 'rejected' ? 'Proposal rejected' : runState === 'cancelled' ? 'Proposal cancelled' : 'Execution unverified' }), _jsxs("dl", { children: [_jsxs("div", { children: [_jsx("dt", { children: "Run ID" }), _jsx("dd", { children: _jsx("code", { children: displayValue(outcome.run_id) }) })] }), _jsxs("div", { children: [_jsx("dt", { children: "Proposal ID" }), _jsx("dd", { children: _jsx("code", { children: displayValue(outcome.proposal_id) }) })] }), _jsxs("div", { children: [_jsx("dt", { children: "Request ID" }), _jsx("dd", { children: _jsx("code", { children: displayValue(outcome.request_id) }) })] }), _jsxs("div", { children: [_jsx("dt", { children: "Effect ID" }), _jsx("dd", { children: _jsx("code", { children: displayValue(outcome.effect_id) }) })] }), _jsxs("div", { children: [_jsx("dt", { children: "Review decision" }), _jsx("dd", { children: displayValue(decision) })] }), _jsxs("div", { children: [_jsx("dt", { children: "BAGO authorization" }), _jsx("dd", { children: authorizationState(outcome) })] }), _jsxs("div", { children: [_jsx("dt", { children: "Execution status" }), _jsx("dd", { children: runState === 'completed' ? 'completed · verified_success true · exact IDs matched' : runState === 'authorization_denied' || runState === 'rejected' || runState === 'cancelled' ? 'not executed' : 'unverified · not success' })] }), _jsxs("div", { children: [_jsx("dt", { children: "BER execution ID" }), _jsx("dd", { children: _jsx("code", { children: displayValue(isRecord(outcome.execution) ? outcome.execution.ber_execution_id : undefined) }) })] }), _jsxs("div", { children: [_jsx("dt", { children: "Receipt ID" }), _jsx("dd", { children: _jsx("code", { children: displayValue(isRecord(outcome.execution) ? outcome.execution.receipt_id : undefined) }) })] })] }), _jsx(LocalTraceProjection, { trace: outcome.trace, expectedExecutionId: isRecord(outcome.execution) && hasText(outcome.execution.ber_execution_id) ? outcome.execution.ber_execution_id : undefined })] })] })] }));
}
