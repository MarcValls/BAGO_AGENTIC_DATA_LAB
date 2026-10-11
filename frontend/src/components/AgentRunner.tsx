import { useState, useEffect } from 'react'
import './AgentRunner.css'

interface Agent {
  id: string
  config: {
    name: string
    description: string
    type: string
    system_prompt: string
    tools: string[]
  }
  created_at: string
}

interface ExecutionResult {
  job_id?: string
  status: string
  duration_ms: number
  cost_usd: number
  exit_code: number | null
}

// /ws/agents/run intentionally fails closed until a governed executor exists.
const AGENT_EXECUTION_AVAILABLE = false

export default function AgentRunner() {
  const [agents, setAgents] = useState<Agent[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null)
  const [isRunning, setIsRunning] = useState(false)
  const [logs, setLogs] = useState<string[]>([])
  const [result, setResult] = useState<ExecutionResult | null>(null)
  const [notification, setNotification] = useState<{ type: 'success' | 'error'; message: string } | null>(null)

  useEffect(() => {
    fetchAgents()
  }, [])

  const fetchAgents = async () => {
    try {
      const response = await fetch('/api/agents/list')
      const data = await response.json()
      setAgents(data.agents || [])
    } catch (error) {
      showNotification('error', 'Failed to load agents')
    } finally {
      setLoading(false)
    }
  }

  const showNotification = (type: 'success' | 'error', message: string) => {
    setNotification({ type, message })
    setTimeout(() => setNotification(null), 3000)
  }

  const executeAgent = async (agent: Agent) => {
    if (!AGENT_EXECUTION_AVAILABLE) {
      showNotification('error', 'Agent execution is unavailable: no governed execution capability is registered.')
      return
    }

    setSelectedAgent(agent)
    setIsRunning(true)
    setLogs([])
    setResult(null)

    try {
      const ws = new WebSocket('ws://localhost:8080/ws/agents/run')

      ws.onopen = () => {
        ws.send(JSON.stringify({
          agent_id: agent.id,
          config: agent.config,
        }))
        setLogs(['[INFO] Connecting to agent execution service...'])
      }

      ws.onmessage = (event) => {
        const msg = JSON.parse(event.data)

        if (msg.type === 'stdout') {
          setLogs((prev) => [...prev, msg.data])
        } else if (msg.type === 'done') {
          const exitCode = Number.isInteger(msg.exit_code) ? msg.exit_code as number : null
          const result: ExecutionResult = {
            job_id: msg.job_id,
            status: exitCode === 0 ? 'success' : 'failed',
            duration_ms: msg.duration_ms || 0,
            cost_usd: msg.cost_usd || 0,
            exit_code: exitCode,
          }
          setResult(result)
          setIsRunning(false)
          ws.close()
          if (exitCode === 0) {
            showNotification('success', `Agent ${agent.config.name} executed successfully`)
          } else {
            showNotification('error', `Agent execution failed: terminal exit code ${exitCode ?? 'missing'}`)
          }
        } else if (msg.type === 'error') {
          const errorCode = typeof msg.code === 'string' ? msg.code : 'unknown_error'
          const errorData = typeof msg.data === 'string' ? msg.data : JSON.stringify(msg.data ?? 'No error details provided')
          setLogs((prev) => [...prev, `[ERROR] ${errorCode}: ${errorData}`])
          setIsRunning(false)
          ws.close()
          showNotification('error', `Agent execution failed: ${msg.data}`)
        }
      }

      ws.onerror = () => {
        showNotification('error', 'WebSocket connection error')
        setIsRunning(false)
      }
    } catch (error) {
      showNotification('error', `Execution error: ${error}`)
      setIsRunning(false)
    }
  }

  const downloadAgentZip = async () => {
    try {
      const response = await fetch('/api/agents/export')
      if (response.ok) {
        const blob = await response.blob()
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = 'agents-export.zip'
        a.click()
        URL.revokeObjectURL(url)
        showNotification('success', 'Agents exported successfully')
      }
    } catch (error) {
      showNotification('error', 'Failed to export agents')
    }
  }

  const importAgentZip = async (file: File) => {
    try {
      const formData = new FormData()
      formData.append('file', file)
      const response = await fetch('/api/agents/import', {
        method: 'POST',
        body: formData,
      })
      if (response.ok) {
        showNotification('success', 'Agents imported successfully')
        fetchAgents()
      }
    } catch (error) {
      showNotification('error', 'Failed to import agents')
    }
  }

  if (loading) {
    return <div className="agent-runner">Loading agents...</div>
  }

  return (
    <div className="agent-runner">
      {notification && (
        <div className={`notification notification-${notification.type}`}>
          {notification.message}
        </div>
      )}

      <div className="runner-header">
        <h2>🎯 Agent Runner</h2>
        <div className="runner-actions">
          <button onClick={downloadAgentZip} className="btn btn-secondary btn-small">
            ⬇️ Export All
          </button>
          <label className="btn btn-secondary btn-small">
            ⬆️ Import
            <input
              type="file"
              accept=".zip"
              onChange={(e) => e.target.files && importAgentZip(e.target.files[0])}
              style={{ display: 'none' }}
            />
          </label>
        </div>
      </div>

      <div className="execution-unavailable" role="status">
        Agent execution is unavailable. No governed execution capability is registered; Run is disabled.
      </div>

      <div className="runner-grid">
        <div className="agents-panel">
          <h3>Available Agents ({agents.length})</h3>
          {agents.length === 0 ? (
            <p style={{ color: 'rgba(255, 255, 255, 0.5)' }}>No agents created yet. Create one in Agent Builder.</p>
          ) : (
            <div className="agents-list">
              {agents.map((agent) => (
                <div
                  key={agent.id}
                  className={`agent-item ${selectedAgent?.id === agent.id ? 'selected' : ''}`}
                  onClick={() => setSelectedAgent(agent)}
                >
                  <div className="agent-item-header">
                    <strong>{agent.config.name}</strong>
                    <span className="badge">{agent.config.type}</span>
                  </div>
                  <p className="agent-item-desc">{agent.config.description}</p>
                  <p className="agent-item-tools">Tools: {agent.config.tools.length}</p>
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      executeAgent(agent)
                    }}
                    disabled={!AGENT_EXECUTION_AVAILABLE || isRunning}
                    className="btn btn-primary btn-small"
                    title="Agent execution is unavailable until a governed execution capability is registered."
                  >
                    Run unavailable
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {selectedAgent && (
          <div className="execution-panel">
            <h3>Execution: {selectedAgent.config.name}</h3>

            <div className="execution-logs">
              <h4>Logs</h4>
              <div className="logs-box">
                {logs.length === 0 ? (
                  <p style={{ color: 'rgba(255, 255, 255, 0.4)' }}>Execution unavailable. No job was started.</p>
                ) : (
                  logs.map((line, idx) => (
                    <div key={idx} className="log-line">
                      {line}
                    </div>
                  ))
                )}
              </div>
            </div>

            {result && (
              <div className="execution-result">
                <h4>Result</h4>
                <div className="result-details">
                  <div>
                    <strong>Status:</strong> <span className={`badge badge-${result.status}`}>{result.status}</span>
                  </div>
                  <div>
                    <strong>Job ID:</strong> <code>{result.job_id || 'N/A'}</code>
                  </div>
                  <div>
                    <strong>Duration:</strong> {(result.duration_ms / 1000).toFixed(2)}s
                  </div>
                  <div>
                    <strong>Cost:</strong> ${result.cost_usd.toFixed(4)}
                  </div>
                  <div>
                    <strong>Exit code:</strong> <code>{result.exit_code ?? 'missing'}</code>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
