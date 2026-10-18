import './AgentBuilder.css'
import { useState } from 'react'

export interface AgentConfig {
  name: string
  description: string
  type: 'rag' | 'tool' | 'multi-agent'
  system_prompt: string
  provider_id?: 'ollama-cloud' | null
  model_id?: string | null
  tools: string[]
  retrieval_config?: {
    mode: 'hybrid' | 'semantic' | 'lexical'
    top_k: number
  } | null
  sandbox_profile?: string
}

interface AgentBuilderProps {
  onAgentCreated?: (agent: AgentConfig) => void
  onBack?: () => void
  initialAgent?: AgentConfig
  agentId?: string
  inline?: boolean
}

const TOOL_OPTIONS = [
  { id: 'bedrock.converse', label: 'AWS Bedrock Converse' },
  { id: 'mcp.execute', label: 'MCP Execute' },
  { id: 'ontology.query', label: 'Ontology SPARQL' },
  { id: 'retrieval.search', label: 'Retrieval Search' },
  { id: 'sandbox.run', label: 'Sandbox Execution' },
]

export default function AgentBuilder({ onAgentCreated, onBack, initialAgent, agentId, inline = false }: AgentBuilderProps) {
  const editing = Boolean(agentId)
  const [step, setStep] = useState<'configure' | 'preview' | 'complete'>('configure')
  const [agent, setAgent] = useState<AgentConfig>(initialAgent ? { ...initialAgent } : {
    name: '',
    description: '',
    type: 'rag',
    system_prompt: '',
    tools: [],
  })
  const [createdAgents, setCreatedAgents] = useState<AgentConfig[]>([])
  const [saving, setSaving] = useState(false)
  const [saveStatus, setSaveStatus] = useState<'idle' | 'success' | 'error'>('idle')
  const [saveError, setSaveError] = useState('')

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
    setSaveError('')
    try {
      const response = await fetch(editing ? `/api/agents/${encodeURIComponent(agentId as string)}` : '/api/agents/create', {
        method: editing ? 'PUT' : 'POST',
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
        const body = await response.json().catch(() => null) as { detail?: { message?: string } } | null
        setSaveError(body?.detail?.message || `The profile could not be saved (${response.status}).`)
        setSaveStatus('error')
      }
    } catch (error) {
      setSaveStatus('error')
      setSaveError(error instanceof Error ? error.message : 'The profile could not be saved.')
    } finally {
      setSaving(false)
    }
  }

  const reset = () => {
    setStep('configure')
    setAgent({
      name: '',
      description: '',
      type: 'rag',
      system_prompt: '',
      tools: [],
    })
    setSaveStatus('idle')
    setSaveError('')
  }

  return (
    <div className={`agent-builder${inline ? ' agent-builder-inline' : ''}`}>
      {(!inline || editing) && <div className="wizard-header">
        <h2>{editing ? 'Edit agent' : '🤖 Agent Builder'}</h2>
      </div>}

      {step === 'configure' && (
        <div className="wizard-step">
          <h3>{editing ? 'Agent profile' : 'Configure Agent'}</h3>

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
            {(!inline || editing) && <button type="button" onClick={onBack} className="btn btn-secondary">{editing ? 'Cancel' : 'Back'}</button>}
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
              {saving ? '⏳ Saving...' : editing ? 'Save changes' : '💾 Save Agent'}
            </button>
            <button onClick={() => setStep('configure')} className="btn btn-secondary">
              Back
            </button>
          </div>

          {saveStatus === 'success' && (
            <div className="status-message success">✓ Agent saved successfully!</div>
          )}
          {saveStatus === 'error' && (
            <div className="status-message error" role="alert">✗ {saveError || 'Error saving agent. Try again.'}</div>
          )}
        </div>
      )}

      {step === 'complete' && (
        <div className="wizard-step">
          <div className="completion-panel">
            <div className="completion-icon">✓</div>
            <h3>{editing ? 'Changes saved' : 'Agent Created!'}</h3>
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
