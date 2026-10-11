import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from 'react';
import './AgentBuilder.css';
const TOOL_OPTIONS = [
    { id: 'bedrock.converse', label: 'AWS Bedrock Converse' },
    { id: 'mcp.execute', label: 'MCP Execute' },
    { id: 'ontology.query', label: 'Ontology SPARQL' },
    { id: 'retrieval.search', label: 'Retrieval Search' },
    { id: 'sandbox.run', label: 'Sandbox Execution' },
];
const AGENT_TEMPLATES = {
    'rag-basic': {
        name: 'Basic RAG Agent',
        description: 'Simple retrieval-augmented generation agent',
        type: 'rag',
        system_prompt: 'You are a helpful assistant that answers questions based on retrieved context.',
        tools: ['retrieval.search', 'bedrock.converse'],
        retrieval_config: { mode: 'hybrid', top_k: 5 },
    },
    'multi-tool': {
        name: 'Multi-Tool Agent',
        description: 'Agent with multiple tool capabilities',
        type: 'multi-agent',
        system_prompt: 'You are an intelligent agent with access to multiple tools. Use them appropriately.',
        tools: ['retrieval.search', 'bedrock.converse', 'ontology.query', 'mcp.execute'],
        sandbox_profile: 'test_runner',
    },
};
export default function AgentBuilder({ onAgentCreated }) {
    const [step, setStep] = useState('select');
    const [agent, setAgent] = useState({
        name: '',
        description: '',
        type: 'rag',
        system_prompt: '',
        tools: [],
    });
    const [selectedTemplate, setSelectedTemplate] = useState(null);
    const [createdAgents, setCreatedAgents] = useState([]);
    const [saving, setSaving] = useState(false);
    const [saveStatus, setSaveStatus] = useState('idle');
    const loadTemplate = (templateId) => {
        const template = AGENT_TEMPLATES[templateId];
        if (template) {
            setAgent({ ...template });
            setSelectedTemplate(templateId);
            setStep('configure');
        }
    };
    const startCustom = () => {
        setAgent({
            name: '',
            description: '',
            type: 'rag',
            system_prompt: '',
            tools: [],
        });
        setSelectedTemplate(null);
        setStep('configure');
    };
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
        if (!agent.name || !agent.description) {
            setSaveStatus('error');
            return;
        }
        setSaving(true);
        try {
            const response = await fetch('/api/agents/create', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(agent),
            });
            if (response.ok) {
                setSaveStatus('success');
                setCreatedAgents((prev) => [...prev, agent]);
                setTimeout(() => {
                    setStep('complete');
                    if (onAgentCreated)
                        onAgentCreated(agent);
                }, 1000);
            }
            else {
                setSaveStatus('error');
            }
        }
        catch (error) {
            setSaveStatus('error');
            console.error('Error saving agent:', error);
        }
        finally {
            setSaving(false);
        }
    };
    const reset = () => {
        setStep('select');
        setAgent({
            name: '',
            description: '',
            type: 'rag',
            system_prompt: '',
            tools: [],
        });
        setSelectedTemplate(null);
        setSaveStatus('idle');
    };
    return (_jsxs("div", { className: "agent-builder", children: [_jsxs("div", { className: "wizard-header", children: [_jsx("h2", { children: "\uD83E\uDD16 Agent Builder" }), _jsx("p", { children: "Create and configure AI agents with governance" })] }), step === 'select' && (_jsxs("div", { className: "wizard-step", children: [_jsx("h3", { children: "Choose a Starting Point" }), _jsx("div", { className: "templates-grid", children: Object.entries(AGENT_TEMPLATES).map(([id, template]) => (_jsxs("div", { className: "template-card", onClick: () => loadTemplate(id), children: [_jsx("h4", { children: template.name }), _jsx("p", { children: template.description }), _jsxs("div", { className: "template-meta", children: [_jsx("span", { className: "badge", children: template.type }), _jsxs("span", { className: "badge", children: [template.tools.length, " tools"] })] })] }, id))) }), _jsx("div", { className: "separator", children: "\u2014 or \u2014" }), _jsx("button", { onClick: startCustom, className: "btn btn-secondary btn-large", children: "\u270F\uFE0F Create Custom Agent" })] })), step === 'configure' && (_jsxs("div", { className: "wizard-step", children: [_jsx("h3", { children: "Configure Agent" }), _jsxs("div", { className: "form-group", children: [_jsx("label", { children: "Agent Name *" }), _jsx("input", { type: "text", value: agent.name, onChange: (e) => updateAgent({ name: e.target.value }), placeholder: "e.g., Customer Support Agent", className: "form-input" })] }), _jsxs("div", { className: "form-group", children: [_jsx("label", { children: "Description *" }), _jsx("textarea", { value: agent.description, onChange: (e) => updateAgent({ description: e.target.value }), placeholder: "What does this agent do?", className: "form-textarea", rows: 3 })] }), _jsxs("div", { className: "form-group", children: [_jsx("label", { children: "Agent Type" }), _jsxs("select", { value: agent.type, onChange: (e) => updateAgent({ type: e.target.value }), className: "form-select", children: [_jsx("option", { value: "rag", children: "RAG (Retrieval-Augmented Generation)" }), _jsx("option", { value: "tool", children: "Tool-based Agent" }), _jsx("option", { value: "multi-agent", children: "Multi-Agent Orchestrator" })] })] }), _jsxs("div", { className: "form-group", children: [_jsx("label", { children: "System Prompt" }), _jsx("textarea", { value: agent.system_prompt, onChange: (e) => updateAgent({ system_prompt: e.target.value }), placeholder: "System instructions for the agent...", className: "form-textarea", rows: 4 })] }), _jsxs("div", { className: "form-group", children: [_jsx("label", { children: "Available Tools" }), _jsx("div", { className: "tools-list", children: TOOL_OPTIONS.map((tool) => (_jsxs("label", { className: "checkbox-label", children: [_jsx("input", { type: "checkbox", checked: agent.tools.includes(tool.id), onChange: () => toggleTool(tool.id) }), _jsx("span", { children: tool.label })] }, tool.id))) })] }), _jsxs("div", { className: "button-group", children: [_jsx("button", { onClick: () => setStep('preview'), className: "btn btn-primary btn-large", children: "\u279C Preview" }), _jsx("button", { onClick: () => setStep('select'), className: "btn btn-secondary", children: "Back" })] })] })), step === 'preview' && (_jsxs("div", { className: "wizard-step", children: [_jsx("h3", { children: "Review Configuration" }), _jsxs("div", { className: "preview-panel", children: [_jsxs("div", { className: "preview-field", children: [_jsx("strong", { children: "Name:" }), " ", agent.name] }), _jsxs("div", { className: "preview-field", children: [_jsx("strong", { children: "Description:" }), " ", agent.description] }), _jsxs("div", { className: "preview-field", children: [_jsx("strong", { children: "Type:" }), " ", _jsx("span", { className: "badge", children: agent.type })] }), _jsxs("div", { className: "preview-field", children: [_jsx("strong", { children: "System Prompt:" }), _jsx("div", { className: "preview-code", children: agent.system_prompt })] }), _jsxs("div", { className: "preview-field", children: [_jsxs("strong", { children: ["Tools (", agent.tools.length, "):"] }), _jsx("div", { className: "tools-preview", children: agent.tools.map((tool) => (_jsx("span", { className: "badge badge-tool", children: TOOL_OPTIONS.find((t) => t.id === tool)?.label || tool }, tool))) })] })] }), _jsxs("div", { className: "button-group", children: [_jsx("button", { onClick: saveAgent, disabled: saving || !agent.name, className: `btn btn-primary btn-large ${saving ? 'disabled' : ''}`, children: saving ? '⏳ Saving...' : '💾 Save Agent' }), _jsx("button", { onClick: () => setStep('configure'), className: "btn btn-secondary", children: "Back" })] }), saveStatus === 'success' && (_jsx("div", { className: "status-message success", children: "\u2713 Agent saved successfully!" })), saveStatus === 'error' && (_jsx("div", { className: "status-message error", children: "\u2717 Error saving agent. Try again." }))] })), step === 'complete' && (_jsx("div", { className: "wizard-step", children: _jsxs("div", { className: "completion-panel", children: [_jsx("div", { className: "completion-icon", children: "\u2713" }), _jsx("h3", { children: "Agent Created!" }), _jsx("p", { className: "agent-name", children: agent.name }), _jsxs("div", { className: "completion-details", children: [_jsxs("p", { children: [_jsx("strong", { children: "Type:" }), " ", agent.type] }), _jsxs("p", { children: [_jsx("strong", { children: "Tools:" }), " ", agent.tools.length, " available"] })] }), _jsxs("div", { className: "button-group", children: [_jsx("button", { onClick: reset, className: "btn btn-primary btn-large", children: "\u2795 Create Another Agent" }), _jsx("button", { onClick: reset, className: "btn btn-secondary", children: "Done" })] })] }) })), createdAgents.length > 0 && (_jsxs("div", { className: "created-agents", children: [_jsx("h3", { children: "Created Agents" }), _jsx("div", { className: "agents-list", children: createdAgents.map((a, idx) => (_jsxs("div", { className: "agent-card", children: [_jsxs("div", { className: "agent-card-header", children: [_jsx("strong", { children: a.name }), _jsx("span", { className: "badge", children: a.type })] }), _jsx("p", { children: a.description }), _jsxs("div", { className: "agent-card-tools", children: [a.tools.slice(0, 3).map((tool) => (_jsx("span", { className: "badge badge-small", children: tool.split('.')[1] }, tool))), a.tools.length > 3 && _jsxs("span", { className: "badge badge-small", children: ["+", a.tools.length - 3] })] })] }, idx))) })] }))] }));
}
