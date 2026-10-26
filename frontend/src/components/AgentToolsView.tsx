import { useCallback, useEffect, useState } from 'react'
import { apiError, t, useI18n } from '../i18n'
import AgentBuilder, { type AgentConfig } from './AgentBuilder'
import './AgentToolsView.css'

type AgentProfile = { id: string; config: AgentConfig }
type CatalogTool = { id: string; name: string; name_en?: string; status: string; summary?: string; assignable?: boolean }
type Props = { onOpenConnections: () => void; onCreateAgent: () => void }

async function readJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(path, { signal })
  const body = await response.json().catch(() => null)
  if (!response.ok) throw apiError(body, response.status, 'agents')
  return body as T
}

function validProfile(value: unknown, id?: string): value is AgentProfile {
  if (!value || typeof value !== 'object') return false
  const profile = value as AgentProfile
  return typeof profile.id === 'string' && (!id || profile.id === id)
    && !!profile.config && typeof profile.config.name === 'string'
    && typeof profile.config.description === 'string' && Array.isArray(profile.config.tools)
}

export default function AgentToolsView({ onOpenConnections, onCreateAgent }: Props) {
  const { locale } = useI18n()
  const [tools, setTools] = useState<CatalogTool[]>([])
  const [agents, setAgents] = useState<AgentProfile[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<Error | null>(null)
  const [selected, setSelected] = useState<AgentProfile | null>(null)
  const [loadingAgent, setLoadingAgent] = useState(false)
  const [generation, setGeneration] = useState(0)

  const refresh = useCallback(async (signal?: AbortSignal) => {
    setLoading(true); setError(null)
    try {
      const [catalog, listed] = await Promise.all([
        readJson<{ agent_tools?: CatalogTool[] }>('/api/capabilities', signal),
        readJson<{ agents?: AgentProfile[] }>('/api/agents/list', signal),
      ])
      if (!Array.isArray(catalog?.agent_tools) || catalog.agent_tools.some(item => !item || typeof item.id !== 'string' || typeof item.name !== 'string' || typeof item.status !== 'string')) throw new Error('Invalid tool catalog')
      if (!Array.isArray(listed?.agents) || listed.agents.some(item => !validProfile(item))) throw new Error('Invalid agent list')
      if (!signal?.aborted) { setTools(catalog.agent_tools.filter(item => item.assignable !== false)); setAgents(listed.agents) }
    } catch (cause) {
      if (!signal?.aborted) setError(cause instanceof Error ? cause : new Error(t('agentTools.loadAssignmentError')))
    } finally { if (!signal?.aborted) setLoading(false) }
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    void refresh(controller.signal)
    return () => controller.abort()
  }, [refresh, generation])

  const editAgent = async (id: string) => {
    setLoadingAgent(true); setError(null)
    try {
      const loaded = await readJson<unknown>(`/api/agents/${encodeURIComponent(id)}`)
      if (!validProfile(loaded, id)) throw new Error('Agent profile did not match the selected ID')
      setSelected(loaded)
    } catch (cause) { setError(cause instanceof Error ? cause : new Error(t('agentTools.loadAssignmentError'))) }
    finally { setLoadingAgent(false) }
  }

  if (selected) return <section className="agent-tools-view" aria-labelledby="agent-tools-title">
    <button type="button" className="agent-tools-back" onClick={() => { setSelected(null); setGeneration(value => value + 1) }}>{t('agentTools.backToTools')}</button>
    <div className="agent-tools-limit" role="note">{t('agentTools.assignmentLimit')}</div>
    <AgentBuilder key={selected.id} inline agentId={selected.id} initialAgent={selected.config} onBack={() => { setSelected(null); setGeneration(value => value + 1) }} onAgentCreated={() => { setSelected(null); setGeneration(value => value + 1) }} />
  </section>

  return <section className="agent-tools-view" aria-labelledby="agent-tools-title">
    <header className="agent-tools-header">
      <div><p className="app-kicker">{t('commerce.agents_455')}</p><h1 id="agent-tools-title">{t('agentTools.assignmentTitle')}</h1><p>{t('agentTools.assignmentIntro')}</p></div>
      <div className="agent-tools-actions">
        <button type="button" onClick={() => setGeneration(value => value + 1)} disabled={loading}>{t('agentTools.refreshAssignment')}</button>
        <button type="button" onClick={onOpenConnections}>{t('agentTools.connections')}</button>
      </div>
    </header>
    <p className="agent-tools-limit" role="note">{t('agentTools.assignmentLimit')}</p>
    {loading && <p role="status">{t('agentTools.loadingAssignment')}</p>}
    {error && <div className="agent-tools-error" role="alert"><p>{t('agentTools.loadAssignmentError')}</p><button type="button" onClick={() => setGeneration(value => value + 1)}>{t('agentTools.retryAssignment')}</button></div>}
    {!loading && !error && agents.length === 0 && <div className="agent-tools-empty"><p>{t('agentTools.noAgentProfiles')}</p><button type="button" onClick={onCreateAgent}>{t('agentTools.createAgent')}</button></div>}
    {!loading && !error && tools.length > 0 && <ul className="agent-tools-list" aria-label={t('agentTools.assignmentTitle')}>
      {tools.map(tool => {
        const assigned = agents.filter(agent => agent.config.tools.includes(tool.id))
        return <li key={tool.id} className="agent-tools-row">
          <div className="agent-tools-main"><strong>{locale === 'en' ? tool.name_en || tool.name : tool.name}</strong><code>{tool.id}</code>{tool.summary && <p>{tool.summary}</p>}</div>
          <div className="agent-tools-state"><span>{t('agentTools.catalogStatus')}</span><code data-status={tool.status.toLowerCase()}>{tool.status === 'AVAILABLE' ? t('agentTools.available') : tool.status === 'UNAVAILABLE' ? t('agentTools.unavailable') : tool.status}</code></div>
          <div className="agent-tools-assigned"><span>{t('agentTools.assignedAgents')}</span>{assigned.length ? <ul>{assigned.map(agent => <li key={agent.id}><button type="button" onClick={() => void editAgent(agent.id)} disabled={loadingAgent}>{agent.config.name}</button></li>)}</ul> : <span className="agent-tools-unassigned">{t('agentTools.noAssignedAgents')}</span>}</div>
        </li>
      })}
    </ul>}
    {!loading && !error && agents.length > 0 && <section aria-labelledby="agent-tools-profiles-title" className="agent-tools-profiles">
      <h2 id="agent-tools-profiles-title">{t('agentTools.agentProfiles')}</h2>
      <ul>{agents.map(agent => <li key={agent.id}><span><strong>{agent.config.name}</strong><small>{agent.config.tools.length} · {t('agentTools.assignedTools')}</small></span><button type="button" onClick={() => void editAgent(agent.id)} disabled={loadingAgent}>{t('agentTools.editAssignment')}</button></li>)}</ul>
    </section>}
    {loadingAgent && <p role="status">{t('agentTools.loadingAssignment')}</p>}
    {!loading && !error && tools.length === 0 && agents.length > 0 && <p role="status">{t('agentTools.toolsUnavailable')}</p>}
  </section>
}
