import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import './AgentBuilder.css';
import { useCallback, useEffect, useState } from 'react';
import AgentTaskForm, { taskError } from './AgentTaskForm';
const TOOL_OPTIONS = [
    { id: 'bedrock.converse', label: 'AWS Bedrock Converse' },
    { id: 'mcp.execute', label: 'MCP Execute' },
    { id: 'ontology.query', label: 'Ontology SPARQL' },
    { id: 'retrieval.search', label: 'Retrieval Search' },
    { id: 'sandbox.run', label: 'Sandbox Execution' },
];
export default function AgentBuilder({ onAgentCreated, onBack, initialAgent, agentId, inline = false }) {
    const editing = Boolean(agentId);
    const [step, setStep] = useState('configure');
    const [agent, setAgent] = useState(initialAgent ? { ...initialAgent, task: initialAgent.task ? { ...initialAgent.task, dates: initialAgent.task.dates.map(date => ({ ...date })) } : { prompt: initialAgent.description, dates: [] } } : {
        name: '',
        description: '',
        type: 'rag',
        system_prompt: '',
        tools: [],
        task: { prompt: '', dates: [] },
    });
    const [createdAgents, setCreatedAgents] = useState([]);
    const [saving, setSaving] = useState(false);
    const [saveStatus, setSaveStatus] = useState('idle');
    const [saveError, setSaveError] = useState('');
    const [providers, setProviders] = useState([]);
    const [providersLoading, setProvidersLoading] = useState(true);
    const [providerError, setProviderError] = useState('');
    const loadProviders = useCallback(async (signal) => {
        setProvidersLoading(true);
        setProviderError('');
        try {
            const response = await fetch('/api/providers/chat-models', { signal });
            if (!response.ok)
                throw new Error('No se pudo cargar el registro de proveedores.');
            const data = await response.json();
            if (!Array.isArray(data?.models))
                throw new Error('El servidor no devolvió los proveedores disponibles.');
            if (!signal?.aborted)
                setProviders(data.models);
        }
        catch (cause) {
            if (!signal?.aborted)
                setProviderError(cause instanceof Error ? cause.message : 'No se pudieron cargar los proveedores.');
        }
        finally {
            if (!signal?.aborted)
                setProvidersLoading(false);
        }
    }, []);
    useEffect(() => {
        const controller = new AbortController();
        void loadProviders(controller.signal);
        return () => controller.abort();
    }, [loadProviders]);
    const eligibleModels = providers.filter(provider => !provider.agent_types || provider.agent_types.includes(agent.type));
    const selectedProviderId = agent.provider_id || eligibleModels[0]?.provider_id || 'ollama-cloud';
    const selectedProvider = eligibleModels.find(provider => provider.provider_id === selectedProviderId && (!agent.model_id || provider.model_id === agent.model_id));
    const providerOptions = eligibleModels.filter((provider, index, items) => items.findIndex(item => item.provider_id === provider.provider_id) === index);
    const updateAgent = (updates) => {
        setAgent((prev) => ({ ...prev, ...updates }));
    };
    const toggleTool = (toolId) => {
        setAgent((prev) => ({
            ...prev,
            tools: prev.tools.includes(toolId)
                ? prev.tools.filter((t) => t !== toolId)
                : [...prev.tools, toolId],
        }));
    };
    const saveAgent = async () => {
        if (!agent.name || !agent.description || !agent.task || taskError(agent.task)) {
            setSaveStatus('error');
            setSaveError(!agent.task ? 'Escribe una tarea.' : taskError(agent.task));
            return;
        }
        setSaving(true);
        setSaveError('');
        try {
            const response = await fetch(editing ? `/api/agents/${encodeURIComponent(agentId)}` : '/api/agents/create', {
                method: editing ? 'PUT' : 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(editing ? agent : { ...agent, provider_id: selectedProviderId, model_id: agent.model_id || selectedProvider?.model_id || null }),
            });
            if (response.ok) {
                const record = await response.json();
                if (!record?.config)
                    throw new Error('El servidor no devolvió el perfil guardado.');
                const saved = record.config;
                setAgent(saved);
                setSaveStatus('success');
                setCreatedAgents((prev) => [...prev, saved]);
                setTimeout(() => {
                    setStep('complete');
                    if (onAgentCreated)
                        onAgentCreated(saved);
                }, 1000);
            }
            else {
                const body = await response.json().catch(() => null);
                setSaveError(body?.detail?.message || `The profile could not be saved (${response.status}).`);
                setSaveStatus('error');
            }
        }
        catch (error) {
            setSaveStatus('error');
            setSaveError(error instanceof Error ? error.message : 'The profile could not be saved.');
        }
        finally {
            setSaving(false);
        }
    };
    const reset = () => {
        setStep('configure');
        setAgent({
            name: '',
            description: '',
            type: 'rag',
            system_prompt: '',
            tools: [],
            task: { prompt: '', dates: [] },
        });
        setSaveStatus('idle');
        setSaveError('');
    };
    return (_jsxs("div", { className: `agent-builder${inline ? ' agent-builder-inline' : ''}`, children: [(!inline || editing) && _jsx("div", { className: "wizard-header", children: _jsx("h2", { children: editing ? 'Edit agent' : '🤖 Agent Builder' }) }), step === 'configure' && (_jsxs("div", { className: "wizard-step", children: [_jsx("h3", { children: editing ? 'Agent profile' : 'Configure Agent' }), _jsxs("div", { className: "form-group", children: [_jsx("label", { children: "Agent Name *" }), _jsx("input", { type: "text", value: agent.name, onChange: (e) => updateAgent({ name: e.target.value }), placeholder: "e.g., Customer Support Agent", className: "form-input" })] }), _jsxs("div", { className: "form-group", children: [_jsx("label", { children: "Description *" }), _jsx("textarea", { value: agent.description, onChange: (e) => updateAgent({ description: e.target.value }), placeholder: "What does this agent do?", className: "form-textarea", rows: 3 })] }), _jsx("div", { className: "form-group", children: _jsx(AgentTaskForm, { value: agent.task || { prompt: agent.description, dates: [] }, onChange: task => updateAgent({ task }) }) }), _jsxs("div", { className: "form-group", children: [_jsx("label", { children: "Agent Type" }), _jsxs("select", { value: agent.type, onChange: (e) => updateAgent(editing ? { type: e.target.value } : { type: e.target.value, provider_id: null, model_id: null }), className: "form-select", children: [_jsx("option", { value: "rag", children: "RAG (Retrieval-Augmented Generation)" }), _jsx("option", { value: "tool", children: "Tool-based Agent" }), _jsx("option", { value: "multi-agent", children: "Multi-Agent Orchestrator" })] })] }), _jsxs("div", { className: "form-group", children: [_jsx("label", { htmlFor: "agent-provider", children: "Proveedor" }), providersLoading && _jsx("p", { role: "status", children: "Cargando proveedores\u2026" }), providerError && _jsxs("div", { role: "alert", children: [_jsx("p", { children: providerError }), _jsx("button", { type: "button", className: "btn btn-secondary", onClick: () => void loadProviders(), children: "Reintentar" })] }), _jsxs("select", { id: "agent-provider", value: selectedProviderId, disabled: providersLoading || Boolean(providerError), className: "form-select", onChange: event => {
                                    const next = eligibleModels.find(provider => provider.provider_id === event.target.value);
                                    if (next)
                                        updateAgent({ provider_id: next.provider_id, model_id: next.model_id });
                                }, children: [!providerOptions.length && _jsx("option", { value: selectedProviderId, children: providersLoading ? 'Cargando…' : 'Sin proveedores disponibles' }), providerOptions.map(provider => _jsxs("option", { value: provider.provider_id, disabled: !['ready', 'configured_unverified'].includes(provider.state) || !provider.model_id, children: [provider.label || (provider.provider_id === 'ollama-cloud' ? 'Ollama' : provider.provider_id === 'openai-platform' ? 'OpenAI Platform' : 'GitHub Copilot'), " \u00B7 ", provider.state === 'ready' ? 'acceso comprobado' : provider.state === 'configured_unverified' ? 'registrado, sin comprobar' : 'configura primero'] }, provider.provider_id))] })] }), _jsxs("div", { className: "form-group", children: [_jsx("label", { htmlFor: "agent-model", children: "Modelo" }), _jsxs("select", { id: "agent-model", value: agent.model_id || selectedProvider?.model_id || '', className: "form-select", disabled: !eligibleModels.some(item => item.provider_id === selectedProviderId && item.model_id), onChange: event => updateAgent({ provider_id: selectedProviderId, model_id: event.target.value }), children: [eligibleModels.filter(item => item.provider_id === selectedProviderId && item.model_id).map(item => _jsx("option", { value: item.model_id, children: item.model_id }, item.model_id)), editing && agent.model_id && !eligibleModels.some(item => item.provider_id === selectedProviderId && item.model_id === agent.model_id) && _jsxs("option", { value: agent.model_id, children: [agent.model_id, " (perfil guardado)"] }), !selectedProvider?.model_id && _jsx("option", { value: "", children: "Configura un modelo en Provider Settings" })] })] }), _jsxs("div", { className: "form-group", children: [_jsx("label", { children: "System Prompt" }), _jsx("textarea", { value: agent.system_prompt, onChange: (e) => updateAgent({ system_prompt: e.target.value }), placeholder: "System instructions for the agent...", className: "form-textarea", rows: 4 })] }), _jsxs("div", { className: "form-group", children: [_jsx("label", { children: "Available Tools" }), _jsx("div", { className: "tools-list", children: TOOL_OPTIONS.map((tool) => (_jsxs("label", { className: "checkbox-label", children: [_jsx("input", { type: "checkbox", checked: agent.tools.includes(tool.id), onChange: () => toggleTool(tool.id) }), _jsx("span", { children: tool.label })] }, tool.id))) })] }), _jsxs("div", { className: "button-group", children: [_jsx("button", { onClick: () => setStep('preview'), disabled: !agent.task || Boolean(taskError(agent.task)) || (!editing && !selectedProvider), className: "btn btn-primary btn-large", children: "\u279C Preview" }), (!inline || editing) && _jsx("button", { type: "button", onClick: onBack, className: "btn btn-secondary", children: editing ? 'Cancel' : 'Back' })] })] })), step === 'preview' && (_jsxs("div", { className: "wizard-step", children: [_jsx("h3", { children: "Review Configuration" }), _jsxs("div", { className: "preview-panel", children: [_jsxs("div", { className: "preview-field", children: [_jsx("strong", { children: "Name:" }), " ", agent.name] }), _jsxs("div", { className: "preview-field", children: [_jsx("strong", { children: "Description:" }), " ", agent.description] }), _jsxs("div", { className: "preview-field", children: [_jsx("strong", { children: "Tarea:" }), _jsx("div", { className: "preview-code", children: agent.task?.prompt }), agent.task?.dates.map(date => _jsxs("div", { children: [date.label, ": ", date.value] }, date.key))] }), _jsxs("div", { className: "preview-field", children: [_jsx("strong", { children: "Type:" }), " ", _jsx("span", { className: "badge", children: agent.type })] }), _jsxs("div", { className: "preview-field", children: [_jsx("strong", { children: "Proveedor y modelo:" }), " ", selectedProvider?.label || selectedProviderId, " \u00B7 ", agent.model_id || selectedProvider?.model_id || 'Sin seleccionar'] }), _jsxs("div", { className: "preview-field", children: [_jsx("strong", { children: "System Prompt:" }), _jsx("div", { className: "preview-code", children: agent.system_prompt })] }), _jsxs("div", { className: "preview-field", children: [_jsxs("strong", { children: ["Tools (", agent.tools.length, "):"] }), _jsx("div", { className: "tools-preview", children: agent.tools.map((tool) => (_jsx("span", { className: "badge badge-tool", children: TOOL_OPTIONS.find((t) => t.id === tool)?.label || tool }, tool))) })] })] }), _jsxs("div", { className: "button-group", children: [_jsx("button", { onClick: saveAgent, disabled: saving || !agent.name || !agent.task || Boolean(taskError(agent.task)), className: `btn btn-primary btn-large ${saving ? 'disabled' : ''}`, children: saving ? '⏳ Saving...' : editing ? 'Save changes' : '💾 Save Agent' }), _jsx("button", { onClick: () => setStep('configure'), className: "btn btn-secondary", children: "Back" })] }), saveStatus === 'success' && (_jsx("div", { className: "status-message success", children: "\u2713 Agent saved successfully!" })), saveStatus === 'error' && (_jsxs("div", { className: "status-message error", role: "alert", children: ["\u2717 ", saveError || 'Error saving agent. Try again.'] }))] })), step === 'complete' && (_jsx("div", { className: "wizard-step", children: _jsxs("div", { className: "completion-panel", children: [_jsx("div", { className: "completion-icon", children: "\u2713" }), _jsx("h3", { children: editing ? 'Changes saved' : 'Agent Created!' }), _jsx("p", { className: "agent-name", children: agent.name }), _jsxs("div", { className: "completion-details", children: [_jsxs("p", { children: [_jsx("strong", { children: "Type:" }), " ", agent.type] }), _jsxs("p", { children: [_jsx("strong", { children: "Tools:" }), " ", agent.tools.length, " available"] })] }), _jsxs("div", { className: "button-group", children: [_jsx("button", { onClick: reset, className: "btn btn-primary btn-large", children: "\u2795 Create Another Agent" }), _jsx("button", { onClick: reset, className: "btn btn-secondary", children: "Done" })] })] }) })), createdAgents.length > 0 && (_jsxs("div", { className: "created-agents", children: [_jsx("h3", { children: "Created Agents" }), _jsx("div", { className: "agents-list", children: createdAgents.map((a, idx) => (_jsxs("div", { className: "agent-card", children: [_jsxs("div", { className: "agent-card-header", children: [_jsx("strong", { children: a.name }), _jsx("span", { className: "badge", children: a.type })] }), _jsx("p", { children: a.description }), _jsxs("div", { className: "agent-card-tools", children: [a.tools.slice(0, 3).map((tool) => (_jsx("span", { className: "badge badge-small", children: tool.split('.')[1] }, tool))), a.tools.length > 3 && _jsxs("span", { className: "badge badge-small", children: ["+", a.tools.length - 3] })] })] }, idx))) })] }))] }));
}
