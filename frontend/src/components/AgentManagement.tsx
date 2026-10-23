import {presentAgentError} from './AgentTaskForm'
import {agentStateLabel} from './AgentTaskForm'
import {AgentPresentationError} from './AgentTaskForm'
import {useI18n, t, formatDate, formatNumber, apiError, errorMessage} from '../i18n'
import { useCallback, useEffect, useRef, useState } from 'react'
import AgentBuilder, { type AgentConfig } from './AgentBuilder'
import './AgentManagement.css'

type Profile = { id: string; config: AgentConfig; created_at: string }
type Review = { agent_id: string; name: string; revision: string; deletable: boolean; blockers: string[]; preserved: string[] }
type Props = { onCreate: () => void; onTest: (id: string) => void; onEvaluate: (id: string) => void }

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init)
  const body = await response.json().catch(() => null)
  if (!response.ok) throw apiError(body, response.status, 'agents')
  return body as T
}
function profile(value: Profile, id?: string): Profile {
  if (!value || typeof value.id !== 'string' || (id && value.id !== id) || !value.config || typeof value.config.name !== 'string' || typeof value.config.description !== 'string' || !Array.isArray(value.config.tools)) throw new AgentPresentationError(() => t('agents.AgentManagement.el_servidor_devolvio_un_perfil_invalido_o_de_otro_agente'))
  return value
}

export default function AgentManagement({ onCreate, onTest, onEvaluate }: Props) {
  useI18n()
  const [agents, setAgents] = useState<Profile[]>([])
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | Error>('')
  const [notice, setNotice] = useState<string | Error>('')
  const [warnings, setWarnings] = useState(0)
  const [editing, setEditing] = useState<Profile | null>(null)
  const [review, setReview] = useState<Review | null>(null)
  const [confirmed, setConfirmed] = useState(false)
  const [busy, setBusy] = useState(false)
  const generation = useRef(0)
  const controller = useRef<AbortController | null>(null)
  const reviewRegion = useRef<HTMLElement | null>(null)
  const reviewTrigger = useRef<HTMLElement | null>(null)
  useEffect(() => {
    if (review) {
      reviewRegion.current?.focus({ preventScroll: true })
      reviewRegion.current?.scrollIntoView?.({ block: 'nearest' })
    }
  }, [review])
  const closeReview = () => {
    setReview(null); setConfirmed(false)
    reviewTrigger.current?.focus()
  }

  const refresh = useCallback(async () => {
    const current = ++generation.current
    controller.current?.abort()
    const next = new AbortController(); controller.current = next
    setLoading(true); setError(''); setReview(null); setConfirmed(false)
    try {
      const data = await request<{ agents: Profile[]; warning_count?: number }>('/api/agents/list', { signal: next.signal })
      if (!Array.isArray(data?.agents)) throw new AgentPresentationError(() => t('agents.AgentManagement.el_servidor_no_devolvio_una_lista_valida_de_agentes'))
      const loaded = data.agents.map(item => profile(item))
      if (current === generation.current && !next.signal.aborted) { setAgents(loaded); setWarnings(data.warning_count || 0) }
    } catch (cause) { if (current === generation.current && !next.signal.aborted) setError(cause instanceof Error ? cause : new AgentPresentationError(() => t('agents.AgentManagement.no_se_pudo_cargar_la_lista'))) }
    finally { if (current === generation.current && !next.signal.aborted) setLoading(false) }
  }, [])
  useEffect(() => { void refresh(); return () => { generation.current++; controller.current?.abort() } }, [refresh])

  const select = async (id: string, action: 'edit' | 'delete') => {
    if (action === 'delete') reviewTrigger.current = document.activeElement instanceof HTMLElement ? document.activeElement : null
    const current = ++generation.current
    setBusy(true); setError(''); setNotice(''); setReview(null); setConfirmed(false)
    try {
      if (action === 'edit') {
        const loaded = profile(await request<Profile>(`/api/agents/${encodeURIComponent(id)}`), id)
        if (current === generation.current) setEditing(loaded)
      } else {
        const loaded = await request<Review>(`/api/agents/${encodeURIComponent(id)}/deletion-review`)
        if (loaded?.agent_id !== id || !/^[a-f0-9]{64}$/.test(loaded.revision) || typeof loaded.deletable !== 'boolean' || !Array.isArray(loaded.blockers)) throw new AgentPresentationError(() => t('agents.AgentManagement.la_revision_de_eliminacion_no_es_valida'))
        if (current === generation.current) setReview(loaded)
      }
    } catch (cause) { if (current === generation.current) setError(cause instanceof Error ? cause : new AgentPresentationError(() => t('agents.AgentManagement.no_se_pudo_abrir_el_agente'))) }
    finally { if (current === generation.current) setBusy(false) }
  }
  const remove = async () => {
    if (!review || !confirmed || !review.deletable || busy) return
    const selected = review
    setBusy(true); setError('')
    try {
      const result = await request<{ id: string; state: string }>(`/api/agents/${encodeURIComponent(selected.agent_id)}`, { method: 'DELETE', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ confirmed: true, expected_revision: selected.revision }) })
      if (result?.id !== selected.agent_id || result.state !== 'deleted') throw new AgentPresentationError(() => t('agents.AgentManagement.no_se_pudo_comprobar_la_eliminacion_del_perfil'))
      setNotice(new AgentPresentationError(() => t('agents.AgentManagement.perfil_p0_eliminado_se_conservaron_sus_conversaciones_trazas_e_histori', {p0: selected.name})))
      await refresh()
    } catch (cause) { setError(cause instanceof Error ? cause : new AgentPresentationError(() => t('agents.AgentManagement.no_se_pudo_eliminar'))); setConfirmed(false) }
    finally { setBusy(false) }
  }

  const shown = agents.filter(agent => `${agent.config.name} ${agent.config.description} ${agent.id} ${agentStateLabel(agent.config.type)}`.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase()))
  if (editing) return <section className="agent-management" aria-label={t('agents.AgentManagement.editar_agente')}><button type="button" onClick={() => { setEditing(null); void refresh() }}>{t('agents.AgentManagement.volver_a_agentes')}</button><details><summary>{t('agents.AgentManagement.identidad_del_perfil')}</summary><code>{editing.id}</code></details><AgentBuilder key={editing.id} agentId={editing.id} initialAgent={editing.config} onBack={() => setEditing(null)} onAgentCreated={() => { setEditing(null); setNotice(new AgentPresentationError(() => t('agents.AgentManagement.cambios_guardados_en_el_perfil'))); void refresh() }} /></section>
  return <section className="agent-management" aria-labelledby="agent-management-title">
    <header><div><p className="app-kicker">{t('agents.AgentManagement.bago_biblioteca_de_perfiles')}</p><h1 id="agent-management-title">{t('agents.AgentManagement.agentes')}</h1></div><div className="agent-management-actions"><button type="button" onClick={onCreate}>{t('agents.AgentManagement.crear_agente')}</button><button type="button" disabled={loading || busy} onClick={() => void refresh()}>{t('agents.AgentManagement.actualizar')}</button></div></header>
    <label className="agent-management-search">{t('agents.AgentManagement.buscar_agente')}<input type="search" value={query} onChange={event => setQuery(event.target.value)} placeholder={t('agents.AgentManagement.nombre_descripcion_tipo_o_identificador')} /></label>
    {loading && <p role="status">{t('agents.AgentManagement.cargando_agentes')}</p>}
    {!loading && <p role="status">{t('agents.management.count',{shown:formatNumber(shown.length),total:formatNumber(agents.length)})}</p>}
    {warnings > 0 && <p role="alert">{t('agents.management.warnings',{count:formatNumber(warnings)})}</p>}
    {error && <div role="alert"><p>{typeof error === 'string' ? error : presentAgentError(error)}</p><button type="button" onClick={() => void refresh()}>{t('agents.AgentManagement.actualizar_y_reintentar')}</button></div>}
    {notice && <p role="status">{typeof notice === 'string' ? notice : presentAgentError(notice)}</p>}
    {!loading && !error && !agents.length && <div className="agent-management-empty"><h2>{t('agents.AgentManagement.aun_no_hay_agentes_guardados')}</h2><p>{t('agents.AgentManagement.crea_el_primero_para_definir_su_tarea_proveedor_y_herramientas')}</p><button type="button" onClick={onCreate}>{t('agents.AgentManagement.crear_mi_primer_agente')}</button></div>}
    {!loading && agents.length > 0 && !shown.length && <p>{t('agents.AgentManagement.no_hay_agentes_que_coincidan_con_la_busqueda')}</p>}
    <div className="agent-management-grid">{shown.map(agent => <article key={agent.id} aria-label={t('agents.AgentManagement.agente_p0', {p0: agent.config.name})}><h2>{agent.config.name}</h2><span className="agent-management-type">{agentStateLabel(agent.config.type)}</span><p>{agent.config.description}</p><p className="agent-management-model">{agent.config.provider_id || t('agents.AgentManagement.proveedor_sin_asignar')} · {agent.config.model_id || t('agents.AgentManagement.modelo_sin_asignar')}</p><details><summary>{t('agents.AgentManagement.identidad_del_perfil')}</summary><code>{agent.id}</code></details><div className="agent-management-actions"><button type="button" disabled={busy || loading} onClick={() => void select(agent.id, 'edit')}>{t('agents.AgentManagement.editar')}</button><button type="button" disabled={busy || loading} onClick={() => onTest(agent.id)}>{t('agents.AgentManagement.probar_tarea')}</button><button type="button" disabled={busy || loading} onClick={() => onEvaluate(agent.id)}>{t('agents.AgentManagement.evaluar')}</button><button type="button" className="agent-management-danger" disabled={busy || loading} onClick={() => void select(agent.id, 'delete')}>{t('agents.AgentManagement.eliminar_perfil')}</button></div></article>)}</div>
    {busy && <p role="status">{t('agents.AgentManagement.comprobando_la_operacion')}</p>}
    {review && <section ref={reviewRegion} tabIndex={-1} onKeyDown={event => { if (event.key === 'Escape' && !busy) { event.preventDefault(); closeReview() } }} className="agent-management-review" role="region" aria-label={t('agents.AgentManagement.confirmar_eliminacion')}><h2>{t('agents.management.deleteTitle',{name:review.name})}</h2><p>{t('agents.AgentManagement.se_quitara_el_perfil_de_la_biblioteca_sus_conversaciones_trazas_evalua')}</p><p><code>{review.agent_id}</code></p><details><summary>{t('agents.AgentManagement.revision_sha_256_del_perfil')}</summary><code>{review.revision}</code></details>{!review.deletable && <p role="alert">{t('agents.management.blocked',{blockers:review.blockers.join(', ')})}</p>}<label><input type="checkbox" checked={confirmed} disabled={!review.deletable || busy} onChange={event => setConfirmed(event.target.checked)} />{t('agents.AgentManagement.confirmo_que_quiero_eliminar_este_perfil')}</label><div className="agent-management-actions"><button type="button" className="agent-management-danger" disabled={!confirmed || !review.deletable || busy} onClick={() => void remove()}>{t('agents.AgentManagement.confirmar_eliminacion')}</button><button type="button" disabled={busy} onClick={closeReview}>{t('agents.AgentManagement.cancelar')}</button></div></section>}
  </section>
}
