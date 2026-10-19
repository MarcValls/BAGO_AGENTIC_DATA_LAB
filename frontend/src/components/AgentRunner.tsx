import './AgentRunner.css'
import { useEffect, useRef, useState } from 'react'
import AgentBuilder, { type AgentConfig } from './AgentBuilder'

interface Agent {
  id: string
  config: {
    name: string
    description: string
    type: AgentConfig['type']
    system_prompt: string
    tools: string[]
    provider_id?: AgentConfig['provider_id']
    model_id?: AgentConfig['model_id']
    retrieval_config?: AgentConfig['retrieval_config']
  }
  created_at: string
}

interface ProposalFrame {
  type: 'proposal'
  run_id: string
  agent_id: string
  proposal_id: string
  request_id: string
  effect_id: string
  approval_required: boolean
  target: Record<string, unknown>
  arguments: Record<string, unknown>
  operation_sha256: string
  world_state_digest?: string
  expires_at?: string
  task_status: 'awaiting_review'
  effect_status: 'proposed'
}

type RunState =
  | 'idle' | 'connecting' | 'awaiting_proposal' | 'awaiting_review' | 'decision_pending'
  | 'task_answered' | 'rejected' | 'cancelled' | 'authorization_denied'
  | 'completed' | 'execution_unverified' | 'error'

type Decision = 'approve' | 'reject' | 'cancel'

interface OutcomeFrame {
  type: string
  run_id?: string
  proposal_id?: string
  request_id?: string
  effect_id?: string
  effect_status?: string
  task_status?: string
  answer?: string
  authorization?: Record<string, unknown>
  approval?: Record<string, unknown> | null
  execution?: Record<string, unknown>
  trace?: Record<string, unknown> | null
  code?: string
  data?: string
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
}

function hasText(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0
}

function readProposal(value: unknown, selectedAgentId: string): ProposalFrame | undefined {
  if (!isRecord(value) || value.type !== 'proposal') return undefined
  if ('challenge_id' in value || 'permit_token' in value || 'permit' in value) return undefined
  if (value.agent_id !== selectedAgentId || !hasText(value.run_id) || !hasText(value.proposal_id) || !hasText(value.request_id) || !hasText(value.effect_id)) return undefined
  if (typeof value.approval_required !== 'boolean' || !isRecord(value.target) || !isRecord(value.arguments)) return undefined
  if (!hasText(value.operation_sha256) || value.task_status !== 'awaiting_review' || value.effect_status !== 'proposed') return undefined
  return value as unknown as ProposalFrame
}

function websocketUrl(): string {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.hostname || 'localhost'
  const port = window.location.port === '5173' ? '8080' : window.location.port || '8080'
  return `${protocol}//${host}:${port}/ws/agents/run`
}

function exactCompletion(value: OutcomeFrame, proposal: ProposalFrame): boolean {
  const execution = value.execution
  const approval = value.approval
  const approvalMatches = !proposal.approval_required || (
    isRecord(approval)
    && approval.request_id === proposal.request_id
    && typeof approval.state === 'string'
    && ['approved', 'authorized', 'ALLOW'].includes(approval.state)
  )
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
    && hasText(execution.ber_execution_id)
}

function displayValue(value: unknown): string {
  if (typeof value === 'string' && value.length) return value
  if (value === null || value === undefined || value === '') return 'Not provided'
  try { return JSON.stringify(value, null, 2) } catch { return 'Not provided' }
}

function authorizationState(outcome: OutcomeFrame): string {
  if (isRecord(outcome.approval) && hasText(outcome.approval.state)) return outcome.approval.state
  if (isRecord(outcome.authorization) && hasText(outcome.authorization.state)) return outcome.authorization.state
  if (isRecord(outcome.execution) && isRecord(outcome.execution.authorization) && hasText(outcome.execution.authorization.state)) return outcome.execution.authorization.state
  if (outcome.type === 'rejected' || outcome.type === 'cancelled') return 'Not requested'
  return 'Not provided'
}

function LocalTraceProjection({ trace, expectedExecutionId }: { trace: unknown; expectedExecutionId?: string }) {
  if (!isRecord(trace)) return <p role="status">LocalTrace projection not provided.</p>
  const traceId = hasText(trace.trace_id) ? trace.trace_id : undefined
  const traceRunId = hasText(trace.run_id) ? trace.run_id : undefined
  const events = Array.isArray(trace.events) ? trace.events.filter(isRecord) : []
  const bound = Boolean(traceId && traceRunId && (!expectedExecutionId || traceRunId === expectedExecutionId))
  return (
    <section className="agent-runner__trace" aria-label="LocalTrace projection">
      <h4>LocalTrace projection</h4>
      <p>This ADL projection is observational; BAGO authorization and the BER receipt remain authoritative.</p>
      <dl>
        <div><dt>Trace ID</dt><dd><code>{traceId || 'Not provided'}</code></dd></div>
        <div><dt>BER execution ID</dt><dd><code>{traceRunId || 'Not provided'}</code></dd></div>
        <div><dt>Identity binding</dt><dd>{bound ? 'Matches supplied BER execution ID' : 'Unverified or mismatched'}</dd></div>
      </dl>
      {events.length ? <ol aria-label="LocalTrace events">{events.map((event, index) => (
        <li key={hasText(event.event_id) ? event.event_id : `event-${index}`}>
          <strong>{displayValue(event.name)}</strong>
          <span>Status: {displayValue(event.status)}</span>
          <span>Event ID: <code>{displayValue(event.event_id)}</code></span>
          <span>Sequence: {displayValue(event.sequence)}</span>
        </li>
      ))}</ol> : <p>No LocalTrace events were provided.</p>}
    </section>
  )
}

const stateMessages: Record<RunState, string> = {
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
}

export default function AgentRunner() {
  const [agents, setAgents] = useState<Agent[]>([])
  const [loading, setLoading] = useState(true)
  const [agentsError, setAgentsError] = useState<string | null>(null)
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null)
  const [editingAgent, setEditingAgent] = useState(false)
  const [task, setTask] = useState('')
  const [runState, setRunState] = useState<RunState>('idle')
  const [proposal, setProposal] = useState<ProposalFrame | null>(null)
  const [outcome, setOutcome] = useState<OutcomeFrame | null>(null)
  const [decision, setDecision] = useState<Decision | null>(null)
  const socketRef = useRef<WebSocket | null>(null)
  const terminalRef = useRef(false)

  useEffect(() => {
    void fetchAgents()
    return () => {
      socketRef.current?.close()
      socketRef.current = null
    }
  }, [])

  const fetchAgents = async () => {
    setLoading(true)
    setAgentsError(null)
    try {
      const response = await fetch('/api/agents/list')
      if (!response.ok) throw new Error('Agent profiles could not be loaded.')
      const data: unknown = await response.json()
      const listed = isRecord(data) && Array.isArray(data.agents) ? data.agents.filter(isRecord) as unknown as Agent[] : []
      setAgents(listed)
      setSelectedAgent(current => current ? listed.find(agent => agent.id === current.id) ?? null : null)
    } catch {
      setAgentsError('Agent profiles could not be loaded. Retry the request.')
    } finally {
      setLoading(false)
    }
  }

  const startRun = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!selectedAgent || !task.trim() || socketRef.current || loading) return
    setProposal(null)
    setOutcome(null)
    setDecision(null)
    terminalRef.current = false
    setRunState('connecting')

    let currentProposal: ProposalFrame | null = null
    let socket: WebSocket
    try {
      socket = new WebSocket(websocketUrl())
      socketRef.current = socket
    } catch {
      terminalRef.current = true
      socketRef.current = null
      setRunState('error')
      setOutcome({ type: 'error', code: 'connection_failed', data: 'The local Agent Runner connection could not be opened.' })
      return
    }

    const finish = () => {
      terminalRef.current = true
      if (socketRef.current === socket) socketRef.current = null
      socket.close()
    }

    socket.onopen = () => {
      setRunState('awaiting_proposal')
      try {
        socket.send(JSON.stringify({ type: 'start', agent_id: selectedAgent.id, task: task.trim() }))
      } catch {
        finish()
        setRunState('error')
        setOutcome({ type: 'error', code: 'send_failed', data: 'The task could not be sent to the local Agent Runner.' })
      }
    }

    socket.onmessage = (event) => {
      let frame: unknown
      try { frame = JSON.parse(String(event.data)) } catch {
        finish()
        setRunState('error')
        setOutcome({ type: 'error', code: 'invalid_message', data: 'The Agent Runner returned an unreadable message.' })
        return
      }
      if (!isRecord(frame) || typeof frame.type !== 'string') {
        finish()
        setRunState('error')
        setOutcome({ type: 'error', code: 'invalid_message', data: 'The Agent Runner returned an unsupported message.' })
        return
      }

      if (frame.type === 'proposal') {
        const received = readProposal(frame, selectedAgent.id)
        if (!received) {
          finish()
          setRunState('error')
          setOutcome({ type: 'error', code: 'invalid_proposal', data: 'The proposal is incomplete or does not match the selected profile.' })
          return
        }
        currentProposal = received
        setProposal(received)
        setRunState('awaiting_review')
        return
      }

      const result = frame as unknown as OutcomeFrame
      if (frame.type === 'task_result') {
        finish()
        setOutcome(result)
        setRunState(result.task_status === 'answered' && result.effect_status === 'not_started' && typeof result.answer === 'string' ? 'task_answered' : 'error')
        return
      }
      if (frame.type === 'rejected' || frame.type === 'cancelled') {
        finish()
        const matches = Boolean(currentProposal && result.run_id === currentProposal.run_id && result.proposal_id === currentProposal.proposal_id && result.request_id === currentProposal.request_id && result.effect_status === 'not_executed')
        setOutcome(result)
        setRunState(matches ? frame.type : 'error')
        return
      }
      if (frame.type === 'authorization_denied') {
        finish()
        const matches = Boolean(currentProposal && result.run_id === currentProposal.run_id && result.proposal_id === currentProposal.proposal_id && result.request_id === currentProposal.request_id && result.effect_status === 'not_executed')
        setOutcome(result)
        setRunState(matches ? 'authorization_denied' : 'error')
        return
      }
      if (frame.type === 'completed' || frame.type === 'execution_unverified') {
        finish()
        setOutcome(result)
        setRunState(currentProposal && exactCompletion(result, currentProposal) ? 'completed' : 'execution_unverified')
        return
      }
      if (frame.type === 'error') {
        finish()
        setOutcome(result)
        setRunState('error')
        return
      }

      finish()
      setOutcome({ type: 'error', code: 'unsupported_message', data: `The Agent Runner returned unsupported state “${frame.type}”.` })
      setRunState('error')
    }

    socket.onerror = () => {
      if (terminalRef.current) return
      finish()
      setOutcome({ type: 'error', code: 'websocket_error', data: 'The local Agent Runner connection failed.' })
      setRunState('error')
    }

    socket.onclose = () => {
      if (terminalRef.current) return
      terminalRef.current = true
      if (socketRef.current === socket) socketRef.current = null
      setOutcome({ type: 'error', code: 'client_disconnected', data: 'The connection closed before a terminal outcome was received.' })
      setRunState('error')
    }
  }

  const decide = (choice: Decision) => {
    const socket = socketRef.current
    if (!socket || socket.readyState !== WebSocket.OPEN || !proposal || runState !== 'awaiting_review') return
    setDecision(choice)
    setRunState('decision_pending')
    try {
      socket.send(JSON.stringify({ type: 'decision', proposal_id: proposal.proposal_id, decision: choice }))
    } catch {
      socket.close()
      socketRef.current = null
      terminalRef.current = true
      setOutcome({ type: 'error', code: 'decision_send_failed', data: 'The review decision could not be sent.' })
      setRunState('error')
    }
  }

  const downloadAgentExport = async () => {
    try {
      const response = await fetch('/api/agents/export')
      if (!response.ok) throw new Error()
      const blob = await response.blob()
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = 'agents-export.json'
      link.click()
      URL.revokeObjectURL(url)
    } catch {
      setAgentsError('Agent profiles could not be exported.')
    }
  }

  const importAgentZip = async (file: File) => {
    try {
      const formData = new FormData()
      formData.append('file', file)
      const response = await fetch('/api/agents/import', { method: 'POST', body: formData })
      if (!response.ok) throw new Error()
      await fetchAgents()
    } catch {
      setAgentsError('The agent profile archive could not be imported.')
    }
  }

  if (loading) return <div className="agent-runner"><h2>Agent Runner</h2><p role="status">Loading agent profiles.</p></div>

  return (
    <div className="agent-runner">
      <header className="runner-header">
        <h2>Agent Runner</h2>
        <div className="runner-actions">
          <button type="button" onClick={downloadAgentExport} className="btn btn-secondary btn-small" aria-label="Export all agents">Export all agents</button>
          <label className="btn btn-secondary btn-small">Import agents
            <input type="file" accept=".zip" aria-label="Import agent profiles from ZIP" onChange={event => { const file = event.target.files?.[0]; if (file) void importAgentZip(file) }} />
          </label>
        </div>
      </header>

      {agentsError && <section className="agent-runner__error" role="alert"><p>{agentsError}</p><button type="button" onClick={() => void fetchAgents()}>Retry profile request</button></section>}

      <section className="agents-panel" aria-labelledby="runner-agents-title">
        <h3 id="runner-agents-title">Select an agent profile</h3>
        {!agentsError && agents.length === 0 ? <p>No saved agent profiles were provided.</p> : <ul className="agents-list">
          {agents.map(agent => <li key={agent.id} className={selectedAgent?.id === agent.id ? 'selected' : undefined}>
            <button type="button" aria-pressed={selectedAgent?.id === agent.id} onClick={() => { setSelectedAgent(agent); setEditingAgent(false) }}>
              <strong>{agent.config.name}</strong><span>{agent.config.description}</span><span>Provider: {agent.config.provider_id || 'Not provided'} · Model: {agent.config.model_id || 'Not provided'}</span>
            </button>
          </li>)}
        </ul>}
      </section>

      {selectedAgent && <section className="agent-profile-panel" aria-labelledby="runner-profile-title">
        <header className="agent-profile-header">
          <div><span className="agent-profile-kicker">SAVED PROFILE</span><h3 id="runner-profile-title">{selectedAgent.config.name}</h3></div>
          <button type="button" className="btn btn-secondary btn-small" onClick={() => setEditingAgent(current => !current)}>{editingAgent ? 'Close editor' : 'Edit profile'}</button>
        </header>
        {editingAgent ? <AgentBuilder inline agentId={selectedAgent.id} initialAgent={selectedAgent.config} onBack={() => setEditingAgent(false)} onAgentCreated={config => {
          setAgents(current => current.map(agent => agent.id === selectedAgent.id ? { ...agent, config } : agent))
          setSelectedAgent(current => current?.id === selectedAgent.id ? { ...current, config } : current)
          setEditingAgent(false)
          void fetchAgents()
        }} /> : <dl className="agent-profile-fields">
          <div><dt>Provider and model</dt><dd>{selectedAgent.config.provider_id || 'Not provided'} · {selectedAgent.config.model_id || 'Not provided'}</dd></div>
          <div><dt>Registered tools</dt><dd>{selectedAgent.config.tools.length ? selectedAgent.config.tools.join(', ') : 'No tools registered'}</dd></div>
        </dl>}
      </section>}

      <form className="agent-runner__task" onSubmit={startRun}>
        <label htmlFor="agent-runner-task">Task</label>
        <textarea id="agent-runner-task" value={task} onChange={event => setTask(event.target.value)} maxLength={8000} rows={4} placeholder="Describe what this agent should do in the bound workspace." />
        <button type="submit" className="btn btn-primary" disabled={!selectedAgent || !task.trim() || runState === 'connecting' || runState === 'awaiting_proposal' || runState === 'awaiting_review' || runState === 'decision_pending'}>Start task</button>
      </form>

      <section className="agent-runner__session" aria-labelledby="agent-runner-session-title">
        <h3 id="agent-runner-session-title">Run review and outcome</h3>
        <p className={`agent-runner__status agent-runner__status--${runState}`} role="status" aria-live="polite">{stateMessages[runState]}</p>
        {runState === 'error' && outcome && <p className="agent-runner__safe-error" role="alert"><strong>{outcome.code || 'runner_error'}</strong>: {typeof outcome.data === 'string' ? outcome.data : 'No safe error details were provided.'}</p>}

        {proposal && <article className="agent-runner__proposal" aria-labelledby="agent-runner-proposal-title">
          <h4 id="agent-runner-proposal-title">Review proposed action</h4>
          <p>This is proposed intent. Nothing has executed yet.</p>
          <dl>
            <div><dt>Proposal ID</dt><dd><code>{proposal.proposal_id}</code></dd></div>
            <div><dt>Run ID</dt><dd><code>{proposal.run_id}</code></dd></div>
            <div><dt>Request ID</dt><dd><code>{proposal.request_id}</code></dd></div>
            <div><dt>Effect</dt><dd><code>{proposal.effect_id}</code></dd></div>
            <div><dt>Target</dt><dd><pre>{JSON.stringify(proposal.target, null, 2)}</pre></dd></div>
            <div><dt>Arguments</dt><dd><pre>{JSON.stringify(proposal.arguments, null, 2)}</pre></dd></div>
            <div><dt>Operation SHA-256</dt><dd><code>{proposal.operation_sha256}</code></dd></div>
            <div><dt>World-state digest</dt><dd><code>{displayValue(proposal.world_state_digest)}</code></dd></div>
            <div><dt>Proposal expiry</dt><dd>{displayValue(proposal.expires_at)}</dd></div>
            <div><dt>BAGO approval</dt><dd>{proposal.approval_required ? 'Required after your review' : 'Not required by BAGO; your review is still required'}</dd></div>
          </dl>
          <div className="agent-runner__decision-actions" aria-label="Review decision">
            <button type="button" onClick={() => decide('approve')} disabled={runState !== 'awaiting_review'}>Approve proposal</button>
            <button type="button" onClick={() => decide('reject')} disabled={runState !== 'awaiting_review'}>Reject proposal</button>
            <button type="button" onClick={() => decide('cancel')} disabled={runState !== 'awaiting_review'}>Cancel proposal</button>
          </div>
          {decision && <p>Submitted review decision: <strong>{decision}</strong></p>}
        </article>}

        {outcome?.type === 'task_result' && <section className="agent-runner__answer" aria-label="Task answer">
          <h4>Task answer</h4><p>{typeof outcome.answer === 'string' ? outcome.answer : 'Answer not provided.'}</p>
          <p>Task status: {displayValue(outcome.task_status)} · Effect status: {displayValue(outcome.effect_status)}</p>
        </section>}

        {outcome && (outcome.type === 'completed' || outcome.type === 'execution_unverified' || outcome.type === 'authorization_denied' || outcome.type === 'rejected' || outcome.type === 'cancelled') && <section className="agent-runner__outcome" aria-label="Governed action outcome">
          <h4>{runState === 'completed' ? 'Verified BER execution' : runState === 'authorization_denied' ? 'Authorization denied' : runState === 'rejected' ? 'Proposal rejected' : runState === 'cancelled' ? 'Proposal cancelled' : 'Execution unverified'}</h4>
          <dl>
            <div><dt>Run ID</dt><dd><code>{displayValue(outcome.run_id)}</code></dd></div>
            <div><dt>Proposal ID</dt><dd><code>{displayValue(outcome.proposal_id)}</code></dd></div>
            <div><dt>Request ID</dt><dd><code>{displayValue(outcome.request_id)}</code></dd></div>
            <div><dt>Effect ID</dt><dd><code>{displayValue(outcome.effect_id)}</code></dd></div>
            <div><dt>Review decision</dt><dd>{displayValue(decision)}</dd></div>
            <div><dt>BAGO authorization</dt><dd>{authorizationState(outcome)}</dd></div>
            <div><dt>Execution status</dt><dd>{runState === 'completed' ? 'completed · verified_success true · exact IDs matched' : runState === 'authorization_denied' || runState === 'rejected' || runState === 'cancelled' ? 'not executed' : 'unverified · not success'}</dd></div>
            <div><dt>BER execution ID</dt><dd><code>{displayValue(isRecord(outcome.execution) ? outcome.execution.ber_execution_id : undefined)}</code></dd></div>
            <div><dt>Receipt ID</dt><dd><code>{displayValue(isRecord(outcome.execution) ? outcome.execution.receipt_id : undefined)}</code></dd></div>
          </dl>
          <LocalTraceProjection trace={outcome.trace} expectedExecutionId={isRecord(outcome.execution) && hasText(outcome.execution.ber_execution_id) ? outcome.execution.ber_execution_id : undefined} />
        </section>}
      </section>
    </div>
  )
}
