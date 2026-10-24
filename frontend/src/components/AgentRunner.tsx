import {presentAgentError} from './AgentTaskForm'
import {agentStateLabel} from './AgentTaskForm'
import {AgentPresentationError} from './AgentTaskForm'
import {useI18n, t, formatDate, formatNumber, apiError, errorMessage} from '../i18n'
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
  if (value === null || value === undefined || value === '') return t('agents.AgentRunner.not_provided')
  try { return JSON.stringify(value, null, 2) } catch { return t('agents.AgentRunner.not_provided') }
}

function authorizationState(outcome: OutcomeFrame): string {
  if (isRecord(outcome.approval) && hasText(outcome.approval.state)) return outcome.approval.state
  if (isRecord(outcome.authorization) && hasText(outcome.authorization.state)) return outcome.authorization.state
  if (isRecord(outcome.execution) && isRecord(outcome.execution.authorization) && hasText(outcome.execution.authorization.state)) return outcome.execution.authorization.state
  if (outcome.type === 'rejected' || outcome.type === 'cancelled') return t('agents.AgentRunner.not_requested')
  return t('agents.AgentRunner.not_provided')
}

function LocalTraceProjection({ trace, expectedExecutionId }: { trace: unknown; expectedExecutionId?: string }) {
  useI18n()
  if (!isRecord(trace)) return <p role="status">{t('agents.AgentRunner.localtrace_projection_not_provided')}</p>
  const traceId = hasText(trace.trace_id) ? trace.trace_id : undefined
  const traceRunId = hasText(trace.run_id) ? trace.run_id : undefined
  const events = Array.isArray(trace.events) ? trace.events.filter(isRecord) : []
  const bound = Boolean(traceId && traceRunId && (!expectedExecutionId || traceRunId === expectedExecutionId))
  return (
    <section className="agent-runner__trace" aria-label={t('agents.AgentRunner.localtrace_projection')}>
      <h4>{t('agents.AgentRunner.localtrace_projection')}</h4>
      <p>{t('agents.AgentRunner.this_adl_projection_is_observational_bago_authorization_and_the_ber_re')}</p>
      <dl>
        <div><dt>{t('agents.AgentRunner.trace_id')}</dt><dd><code>{traceId || t('agents.AgentRunner.not_provided')}</code></dd></div>
        <div><dt>{t('agents.AgentRunner.ber_execution_id')}</dt><dd><code>{traceRunId || t('agents.AgentRunner.not_provided')}</code></dd></div>
        <div><dt>{t('agents.AgentRunner.identity_binding')}</dt><dd>{bound ? t('agents.AgentRunner.matches_supplied_ber_execution_id') : t('agents.AgentRunner.unverified_or_mismatched')}</dd></div>
      </dl>
      {events.length ? <ol aria-label={t('agents.AgentRunner.localtrace_events')}>{events.map((event, index) => (
        <li key={hasText(event.event_id) ? event.event_id : `event-${index}`}>
          <strong>{displayValue(event.name)}</strong>
          <span>{t('agents.AgentRunner.status')} {displayValue(event.status)}</span>
          <span>{t('agents.AgentRunner.event_id')} <code>{displayValue(event.event_id)}</code></span>
          <span>{t('agents.AgentRunner.sequence')} {displayValue(event.sequence)}</span>
        </li>
      ))}</ol> : <p>{t('agents.AgentRunner.no_localtrace_events_were_provided')}</p>}
    </section>
  )
}

const stateMessages: Record<RunState, string> = {
  get idle() { return t('agents.AgentRunner.select_an_agent_and_enter_a_task_to_begin') },
  get connecting() { return t('agents.AgentRunner.connecting_to_the_governed_agent_runner') },
  get awaiting_proposal() { return t('agents.AgentRunner.the_server_is_preparing_a_response_or_a_reviewable_proposal') },
  get awaiting_review() { return t('agents.AgentRunner.review_the_exact_proposed_effect_and_arguments_before_choosing') },
  get decision_pending() { return t('agents.AgentRunner.your_decision_was_sent_waiting_for_the_bago_authorization_and_executio') },
  get task_answered() { return t('agents.AgentRunner.the_task_was_answered_without_starting_an_effect') },
  get rejected() { return t('agents.AgentRunner.the_proposal_was_rejected_no_effect_was_executed') },
  get cancelled() { return t('agents.AgentRunner.the_proposal_was_cancelled_no_effect_was_executed') },
  get authorization_denied() { return t('agents.AgentRunner.bago_did_not_authorize_this_proposal_no_effect_was_executed') },
  get completed() { return t('agents.AgentRunner.bago_ber_completed_the_effect_and_returned_an_identity_matched_verifie') },
  get execution_unverified() { return t('agents.AgentRunner.execution_or_receipt_identity_could_not_be_verified_this_is_not_succes') },
  get error() { return t('agents.AgentRunner.the_agent_runner_could_not_complete_this_session') },
}

export default function AgentRunner() {
  useI18n()
  const [agents, setAgents] = useState<Agent[]>([])
  const [loading, setLoading] = useState(true)
  const [agentsError, setAgentsError] = useState<string | Error>(null)
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
      if (!response.ok) throw new AgentPresentationError(() => t('agents.AgentRunner.agent_profiles_could_not_be_loaded'))
      const data: unknown = await response.json()
      const listed = isRecord(data) && Array.isArray(data.agents) ? data.agents.filter(isRecord) as unknown as Agent[] : []
      setAgents(listed)
      setSelectedAgent(current => current ? listed.find(agent => agent.id === current.id) ?? null : null)
    } catch {
      setAgentsError(new AgentPresentationError(() => t('agents.AgentRunner.agent_profiles_could_not_be_loaded_retry_the_request')))
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
      setOutcome({ type: 'error', code: 'connection_failed', get data() { return t('agents.AgentRunner.the_local_agent_runner_connection_could_not_be_opened') } })
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
        setOutcome({ type: 'error', code: 'send_failed', get data() { return t('agents.AgentRunner.the_task_could_not_be_sent_to_the_local_agent_runner') } })
      }
    }

    socket.onmessage = (event) => {
      let frame: unknown
      try { frame = JSON.parse(String(event.data)) } catch {
        finish()
        setRunState('error')
        setOutcome({ type: 'error', code: 'invalid_message', get data() { return t('agents.AgentRunner.the_agent_runner_returned_an_unreadable_message') } })
        return
      }
      if (!isRecord(frame) || typeof frame.type !== 'string') {
        finish()
        setRunState('error')
        setOutcome({ type: 'error', code: 'invalid_message', get data() { return t('agents.AgentRunner.the_agent_runner_returned_an_unsupported_message') } })
        return
      }

      if (frame.type === 'proposal') {
        const received = readProposal(frame, selectedAgent.id)
        if (!received) {
          finish()
          setRunState('error')
          setOutcome({ type: 'error', code: 'invalid_proposal', get data() { return t('agents.AgentRunner.the_proposal_is_incomplete_or_does_not_match_the_selected_profile') } })
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
      setOutcome({ type: 'error', code: 'unsupported_message', get data() { return t('agents.AgentRunner.the_agent_runner_returned_unsupported_state_p0', {p0: String(frame.type)}) } })
      setRunState('error')
    }

    socket.onerror = () => {
      if (terminalRef.current) return
      finish()
      setOutcome({ type: 'error', code: 'websocket_error', get data() { return t('agents.AgentRunner.the_local_agent_runner_connection_failed') } })
      setRunState('error')
    }

    socket.onclose = () => {
      if (terminalRef.current) return
      terminalRef.current = true
      if (socketRef.current === socket) socketRef.current = null
      setOutcome({ type: 'error', code: 'client_disconnected', get data() { return t('agents.AgentRunner.the_connection_closed_before_a_terminal_outcome_was_received') } })
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
      setOutcome({ type: 'error', code: 'decision_send_failed', get data() { return t('agents.AgentRunner.the_review_decision_could_not_be_sent') } })
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
      setAgentsError(new AgentPresentationError(() => t('agents.AgentRunner.agent_profiles_could_not_be_exported')))
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
      setAgentsError(new AgentPresentationError(() => t('agents.AgentRunner.the_agent_profile_archive_could_not_be_imported')))
    }
  }

  if (loading) return <div className="agent-runner"><h2>{t('agents.AgentRunner.agent_runner')}</h2><p role="status">{t('agents.AgentRunner.loading_agent_profiles')}</p></div>

  return (
    <div className="agent-runner">
      <header className="runner-header">
        <h2>{t('agents.AgentRunner.agent_runner')}</h2>
        <div className="runner-actions">
          <button type="button" onClick={downloadAgentExport} className="btn btn-secondary btn-small" aria-label={t('agents.AgentRunner.export_all_agents')}>{t('agents.AgentRunner.export_all_agents')}</button>
          <label className="btn btn-secondary btn-small">{t('agents.AgentRunner.import_agents')} <input type="file" accept=".zip" aria-label={t('agents.AgentRunner.import_agent_profiles_from_zip')} onChange={event => { const file = event.target.files?.[0]; if (file) void importAgentZip(file) }} />
          </label>
        </div>
      </header>

      {agentsError && <section className="agent-runner__error" role="alert"><p>{typeof agentsError === 'string' ? agentsError : presentAgentError(agentsError)}</p><button type="button" onClick={() => void fetchAgents()}>{t('agents.AgentRunner.retry_profile_request')}</button></section>}

      <section className="agents-panel" aria-labelledby="runner-agents-title">
        <h3 id="runner-agents-title">{t('agents.AgentRunner.select_an_agent_profile')}</h3>
        {!agentsError && agents.length === 0 ? <p>{t('agents.AgentRunner.no_saved_agent_profiles_were_provided')}</p> : <ul className="agents-list">
          {agents.map(agent => <li key={agent.id} className={selectedAgent?.id === agent.id ? 'selected' : undefined}>
            <button type="button" aria-pressed={selectedAgent?.id === agent.id} onClick={() => { setSelectedAgent(agent); setEditingAgent(false) }}>
              <strong>{agent.config.name}</strong><span>{agent.config.description}</span><span>{t('agents.AgentRunner.provider')} {agent.config.provider_id || t('agents.AgentRunner.not_provided')} {t('agents.AgentRunner.model')} {agent.config.model_id || t('agents.AgentRunner.not_provided')}</span>
            </button>
          </li>)}
        </ul>}
      </section>

      {selectedAgent && <section className="agent-profile-panel" aria-labelledby="runner-profile-title">
        <header className="agent-profile-header">
          <div><span className="agent-profile-kicker">{t('agents.AgentRunner.saved_profile')}</span><h3 id="runner-profile-title">{selectedAgent.config.name}</h3></div>
          <button type="button" className="btn btn-secondary btn-small" onClick={() => setEditingAgent(current => !current)}>{editingAgent ? t('agents.AgentRunner.close_editor') : t('agents.AgentRunner.edit_profile')}</button>
        </header>
        {editingAgent ? <AgentBuilder inline agentId={selectedAgent.id} initialAgent={selectedAgent.config} onBack={() => setEditingAgent(false)} onAgentCreated={config => {
          setAgents(current => current.map(agent => agent.id === selectedAgent.id ? { ...agent, config } : agent))
          setSelectedAgent(current => current?.id === selectedAgent.id ? { ...current, config } : current)
          setEditingAgent(false)
          void fetchAgents()
        }} /> : <dl className="agent-profile-fields">
          <div><dt>{t('agents.AgentRunner.provider_and_model')}</dt><dd>{selectedAgent.config.provider_id || t('agents.AgentRunner.not_provided')} · {selectedAgent.config.model_id || t('agents.AgentRunner.not_provided')}</dd></div>
          <div><dt>{t('agents.AgentRunner.registered_tools')}</dt><dd>{selectedAgent.config.tools.length ? selectedAgent.config.tools.join(', ') : t('agents.AgentRunner.no_tools_registered')}</dd></div>
        </dl>}
      </section>}

      <form className="agent-runner__task" onSubmit={startRun}>
        <label htmlFor="agent-runner-task">{t('agents.AgentRunner.task')}</label>
        <textarea id="agent-runner-task" value={task} onChange={event => setTask(event.target.value)} maxLength={8000} rows={4} placeholder={t('agents.AgentRunner.describe_what_this_agent_should_do_in_the_bound_workspace')} />
        <button type="submit" className="btn btn-primary" disabled={!selectedAgent || !task.trim() || runState === 'connecting' || runState === 'awaiting_proposal' || runState === 'awaiting_review' || runState === 'decision_pending'}>{t('agents.AgentRunner.start_task')}</button>
      </form>

      <section className="agent-runner__session" aria-labelledby="agent-runner-session-title">
        <h3 id="agent-runner-session-title">{t('agents.AgentRunner.run_review_and_outcome')}</h3>
        <p className={`agent-runner__status agent-runner__status--${runState}`} role="status" aria-live="polite">{stateMessages[runState]}</p>
        {runState === 'error' && outcome && <p className="agent-runner__safe-error" role="alert"><strong>{outcome.code || 'runner_error'}</strong>: {typeof outcome.data === 'string' ? outcome.data : t('agents.AgentRunner.no_safe_error_details_were_provided')}</p>}

        {proposal && <article className="agent-runner__proposal" aria-labelledby="agent-runner-proposal-title">
          <h4 id="agent-runner-proposal-title">{t('agents.AgentRunner.review_proposed_action')}</h4>
          <p>{t('agents.AgentRunner.this_is_proposed_intent_nothing_has_executed_yet')}</p>
          <dl>
            <div><dt>{t('agents.AgentRunner.proposal_id')}</dt><dd><code>{proposal.proposal_id}</code></dd></div>
            <div><dt>{t('agents.AgentRunner.run_id')}</dt><dd><code>{proposal.run_id}</code></dd></div>
            <div><dt>{t('agents.AgentRunner.request_id')}</dt><dd><code>{proposal.request_id}</code></dd></div>
            <div><dt>{t('agents.AgentRunner.effect')}</dt><dd><code>{proposal.effect_id}</code></dd></div>
            <div><dt>{t('agents.AgentRunner.target')}</dt><dd><pre>{JSON.stringify(proposal.target, null, 2)}</pre></dd></div>
            <div><dt>{t('agents.AgentRunner.arguments')}</dt><dd><pre>{JSON.stringify(proposal.arguments, null, 2)}</pre></dd></div>
            <div><dt>{t('agents.AgentRunner.operation_sha_256')}</dt><dd><code>{proposal.operation_sha256}</code></dd></div>
            <div><dt>{t('agents.AgentRunner.world_state_digest')}</dt><dd><code>{displayValue(proposal.world_state_digest)}</code></dd></div>
            <div><dt>{t('agents.AgentRunner.proposal_expiry')}</dt><dd>{displayValue(proposal.expires_at)}</dd></div>
            <div><dt>{t('agents.AgentRunner.bago_approval')}</dt><dd>{proposal.approval_required ? t('agents.AgentRunner.required_after_your_review') : t('agents.AgentRunner.not_required_by_bago_your_review_is_still_required')}</dd></div>
          </dl>
          <div className="agent-runner__decision-actions" aria-label={t('agents.AgentRunner.review_decision')}>
            <button type="button" onClick={() => decide('approve')} disabled={runState !== 'awaiting_review'}>{t('agents.AgentRunner.approve_proposal')}</button>
            <button type="button" onClick={() => decide('reject')} disabled={runState !== 'awaiting_review'}>{t('agents.AgentRunner.reject_proposal')}</button>
            <button type="button" onClick={() => decide('cancel')} disabled={runState !== 'awaiting_review'}>{t('agents.AgentRunner.cancel_proposal')}</button>
          </div>
          {decision && <p>{t('agents.AgentRunner.submitted_review_decision')} <strong>{agentStateLabel(decision)}</strong></p>}
        </article>}

        {outcome?.type === 'task_result' && <section className="agent-runner__answer" aria-label={t('agents.AgentRunner.task_answer')}>
          <h4>{t('agents.AgentRunner.task_answer')}</h4><p>{typeof outcome.answer === 'string' ? outcome.answer : t('agents.AgentRunner.answer_not_provided')}</p>
          <p>{t('agents.AgentRunner.task_status')} {displayValue(outcome.task_status)} {t('agents.AgentRunner.effect_status')} {displayValue(outcome.effect_status)}</p>
        </section>}

        {outcome && (outcome.type === 'completed' || outcome.type === 'execution_unverified' || outcome.type === 'authorization_denied' || outcome.type === 'rejected' || outcome.type === 'cancelled') && <section className="agent-runner__outcome" aria-label={t('agents.AgentRunner.governed_action_outcome')}>
          <h4>{runState === 'completed' ? t('agents.AgentRunner.verified_ber_execution') : runState === 'authorization_denied' ? t('agents.AgentRunner.authorization_denied') : runState === 'rejected' ? t('agents.AgentRunner.proposal_rejected') : runState === 'cancelled' ? t('agents.AgentRunner.proposal_cancelled') : t('agents.AgentRunner.execution_unverified')}</h4>
          <dl>
            <div><dt>{t('agents.AgentRunner.run_id')}</dt><dd><code>{displayValue(outcome.run_id)}</code></dd></div>
            <div><dt>{t('agents.AgentRunner.proposal_id')}</dt><dd><code>{displayValue(outcome.proposal_id)}</code></dd></div>
            <div><dt>{t('agents.AgentRunner.request_id')}</dt><dd><code>{displayValue(outcome.request_id)}</code></dd></div>
            <div><dt>{t('agents.AgentRunner.effect_id')}</dt><dd><code>{displayValue(outcome.effect_id)}</code></dd></div>
            <div><dt>{t('agents.AgentRunner.review_decision')}</dt><dd>{displayValue(decision)}</dd></div>
            <div><dt>{t('agents.AgentRunner.bago_authorization')}</dt><dd>{authorizationState(outcome)}</dd></div>
            <div><dt>{t('agents.AgentRunner.execution_status')}</dt><dd>{runState === 'completed' ? t('agents.AgentRunner.completed_verified_success_true_exact_ids_matched') : runState === 'authorization_denied' || runState === 'rejected' || runState === 'cancelled' ? t('agents.AgentRunner.not_executed') : t('agents.AgentRunner.unverified_not_success')}</dd></div>
            <div><dt>{t('agents.AgentRunner.ber_execution_id')}</dt><dd><code>{displayValue(isRecord(outcome.execution) ? outcome.execution.ber_execution_id : undefined)}</code></dd></div>
            <div><dt>{t('agents.AgentRunner.receipt_id')}</dt><dd><code>{displayValue(isRecord(outcome.execution) ? outcome.execution.receipt_id : undefined)}</code></dd></div>
          </dl>
          <LocalTraceProjection trace={outcome.trace} expectedExecutionId={isRecord(outcome.execution) && hasText(outcome.execution.ber_execution_id) ? outcome.execution.ber_execution_id : undefined} />
        </section>}
      </section>
    </div>
  )
}
