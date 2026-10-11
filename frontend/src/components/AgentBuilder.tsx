import { useState } from 'react'
import './AgentBuilder.css'

interface AgentConfig {
  name: string
  description: string
  type: 'rag' | 'tool' | 'multi-agent'
  system_prompt: string
  tools: string[]
  retrieval_config?: {
    mode: 'hybrid' | 'semantic' | 'lexical'
    top_k: number
  }
  sandbox_profile?: string
}

interface AgentBuilderProps {
  onAgentCreated?: (agent: AgentConfig) => void
}

const TOOL_OPTIONS = [
  { id: 'bedrock.converse', label: 'AWS Bedrock Converse' },
  { id: 'mcp.execute', label: 'MCP Execute' },
  { id: 'ontology.query', label: 'Ontology SPARQL' },
  { id: 'retrieval.search', label: 'Retrieval Search' },
  { id: 'sandbox.run', label: 'Sandbox Execution' },
]

const AGENT_TEMPLATES: Record<string, AgentConfig> = {
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
}

export default function AgentBuilder({ onAgentCreated }: AgentBuilderProps) {
  const [step, setStep] = useState<'select' | 'configure' | 'preview' | 'complete'>('select')
  const [agent, setAgent] = useState<AgentConfig>({
    name: '',
    description: '',
    type: 'rag',
    system_prompt: '',
    tools: [],
  })
  const [selectedTemplate, setSelectedTemplate] = useState<string | null>(null)
  const [createdAgents, setCreatedAgents] = useState<AgentConfig[]>([])
  const [saving, setSaving] = useState(false)
  const [saveStatus, setSaveStatus] = useState<'idle' | 'success' | 'error'>('idle')

  const loadTemplate = (templateId: string) => {
    const template = AGENT_TEMPLATES[templateId as keyof typeof AGENT_TEMPLATES]
    if (template) {
      setAgent({ ...template })
      setSelectedTemplate(templateId)
      setStep('configure')
    }
  }

  const startCustom = () => {
    setAgent({
      name: '',
      description: '',
      type: 'rag',
      system_prompt: '',
      tools: [],
    })
    setSelectedTemplate(null)
    setStep('configure')
  }

  const updateAgent = (updates: Partial<AgentConfig>) => {
    setAgent((prev) => ({ ...prev, ...updates }))
  }

  const toggleTool = (toolId: string) => {
    setAgent((prev) => ({
      ...prev,
      tools: prev.tools.includes(toolId)
        ? prev.tools.filter((t) => t !== toolId)
        : [...prev.tools, toolId],
    }))
  }

  const saveAgent = async () => {
    if (!agent.name || !agent.description) {
      setSaveStatus('error')
      return
    }

    setSaving(true)
    try {
      const response = await fetch('/api/agents/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(agent),
      })

      if (response.ok) {
        setSaveStatus('success')
        setCreatedAgents((prev) => [...prev, agent])
        setTimeout(() => {
          setStep('complete')
          if (onAgentCreated) onAgentCreated(agent)
        }, 1000)
      } else {
        setSaveStatus('error')
      }
    } catch (error) {
      setSaveStatus('error')
      console.error('Error saving agent:', error)
    } finally {
      setSaving(false)
    }
  }

  const reset = () => {
    setStep('select')
    setAgent({
      name: '',
      description: '',
      type: 'rag',
      system_prompt: '',
      tools: [],
    })
    setSelectedTemplate(null)
    setSaveStatus('idle')
  }

  return (
    <div className="agent-builder">
      <div className="wizard-header">
        <h2>🤖 Agent Builder</h2>
        <p>Create and configure AI agents with governance</p>
      </div>

      {step === 'select' && (
        <div className="wizard-step">
          <h3>Choose a Starting Point</h3>

          <div className="templates-grid">
            {Object.entries(AGENT_TEMPLATES).map(([id, template]) => (
              <div key={id} className="template-card" onClick={() => loadTemplate(id)}>
                <h4>{template.name}</h4>
                <p>{template.description}</p>
                <div className="template-meta">
                  <span className="badge">{template.type}</span>
                  <span className="badge">{template.tools.length} tools</span>
                </div>
              </div>
            ))}
          </div>

          <div className="separator">— or —</div>

          <button onClick={startCustom} className="btn btn-secondary btn-large">
            ✏️ Create Custom Agent
          </button>
        </div>
      )}

      {step === 'configure' && (
        <div className="wizard-step">
          <h3>Configure Agent</h3>

          <div className="form-group">
            <label>Agent Name *</label>
            <input
              type="text"
              value={agent.name}
              onChange={(e) => updateAgent({ name: e.target.value })}
              placeholder="e.g., Customer Support Agent"
              className="form-input"
            />
          </div>

          <div className="form-group">
            <label>Description *</label>
            <textarea
              value={agent.description}
              onChange={(e) => updateAgent({ description: e.target.value })}
              placeholder="What does this agent do?"
              className="form-textarea"
              rows={3}
            />
          </div>

          <div className="form-group">
            <label>Agent Type</label>
            <select
              value={agent.type}
              onChange={(e) => updateAgent({ type: e.target.value as any })}
              className="form-select"
            >
              <option value="rag">RAG (Retrieval-Augmented Generation)</option>
              <option value="tool">Tool-based Agent</option>
              <option value="multi-agent">Multi-Agent Orchestrator</option>
            </select>
          </div>

          <div className="form-group">
            <label>System Prompt</label>
            <textarea
              value={agent.system_prompt}
              onChange={(e) => updateAgent({ system_prompt: e.target.value })}
              placeholder="System instructions for the agent..."
              className="form-textarea"
              rows={4}
            />
          </div>

          <div className="form-group">
            <label>Available Tools</label>
            <div className="tools-list">
              {TOOL_OPTIONS.map((tool) => (
                <label key={tool.id} className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={agent.tools.includes(tool.id)}
                    onChange={() => toggleTool(tool.id)}
                  />
                  <span>{tool.label}</span>
                </label>
              ))}
            </div>
          </div>

          <div className="button-group">
            <button onClick={() => setStep('preview')} className="btn btn-primary btn-large">
              ➜ Preview
            </button>
            <button onClick={() => setStep('select')} className="btn btn-secondary">
              Back
            </button>
          </div>
        </div>
      )}

      {step === 'preview' && (
        <div className="wizard-step">
          <h3>Review Configuration</h3>

          <div className="preview-panel">
            <div className="preview-field">
              <strong>Name:</strong> {agent.name}
            </div>
            <div className="preview-field">
              <strong>Description:</strong> {agent.description}
            </div>
            <div className="preview-field">
              <strong>Type:</strong> <span className="badge">{agent.type}</span>
            </div>
            <div className="preview-field">
              <strong>System Prompt:</strong>
              <div className="preview-code">{agent.system_prompt}</div>
            </div>
            <div className="preview-field">
              <strong>Tools ({agent.tools.length}):</strong>
              <div className="tools-preview">
                {agent.tools.map((tool) => (
                  <span key={tool} className="badge badge-tool">
                    {TOOL_OPTIONS.find((t) => t.id === tool)?.label || tool}
                  </span>
                ))}
              </div>
            </div>
          </div>

          <div className="button-group">
            <button
              onClick={saveAgent}
              disabled={saving || !agent.name}
              className={`btn btn-primary btn-large ${saving ? 'disabled' : ''}`}
            >
              {saving ? '⏳ Saving...' : '💾 Save Agent'}
            </button>
            <button onClick={() => setStep('configure')} className="btn btn-secondary">
              Back
            </button>
          </div>

          {saveStatus === 'success' && (
            <div className="status-message success">✓ Agent saved successfully!</div>
          )}
          {saveStatus === 'error' && (
            <div className="status-message error">✗ Error saving agent. Try again.</div>
          )}
        </div>
      )}

      {step === 'complete' && (
        <div className="wizard-step">
          <div className="completion-panel">
            <div className="completion-icon">✓</div>
            <h3>Agent Created!</h3>
            <p className="agent-name">{agent.name}</p>

            <div className="completion-details">
              <p><strong>Type:</strong> {agent.type}</p>
              <p><strong>Tools:</strong> {agent.tools.length} available</p>
            </div>

            <div className="button-group">
              <button onClick={reset} className="btn btn-primary btn-large">
                ➕ Create Another Agent
              </button>
              <button onClick={reset} className="btn btn-secondary">
                Done
              </button>
            </div>
          </div>
        </div>
      )}

      {createdAgents.length > 0 && (
        <div className="created-agents">
          <h3>Created Agents</h3>
          <div className="agents-list">
            {createdAgents.map((a, idx) => (
              <div key={idx} className="agent-card">
                <div className="agent-card-header">
                  <strong>{a.name}</strong>
                  <span className="badge">{a.type}</span>
                </div>
                <p>{a.description}</p>
                <div className="agent-card-tools">
                  {a.tools.slice(0, 3).map((tool) => (
                    <span key={tool} className="badge badge-small">
                      {tool.split('.')[1]}
                    </span>
                  ))}
                  {a.tools.length > 3 && <span className="badge badge-small">+{a.tools.length - 3}</span>}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
