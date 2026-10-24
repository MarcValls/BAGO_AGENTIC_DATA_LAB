import {presentAgentError} from './AgentTaskForm'
import {AgentPresentationError} from './AgentTaskForm'
import {useI18n, t, formatDate, formatNumber, apiError, errorMessage} from '../i18n'
import { useEffect, useRef, useState } from 'react'
import AgentTaskForm, { taskError, type TaskDefinition } from './AgentTaskForm'
import './AgentTasks.css'

type Agent = { id: string; config: { name: string; description: string } }
type SavedTask = { agent_id: string; task: TaskDefinition | null; revision: string }
type TaskRun = {
  run_id: string; agent_id: string; task_revision: string; task_snapshot: TaskDefinition;
  rendered_prompt: string; provider_id: string; model_id: string; workspace_root: string;
  source_run_id: string | null; created_at: string; completed_at: string | null;
  status: 'running' | 'answered' | 'failed'; answer: string | null; error: { code: string; message: string } | null;
}
const emptyTask = (): TaskDefinition => ({ prompt: '', dates: [] })
const copyTask = (task: TaskDefinition): TaskDefinition => ({ prompt: task.prompt, dates: task.dates.map(date => ({ ...date })) })
const signature = (task: TaskDefinition | null) => JSON.stringify(task === null ? null : { prompt: task.prompt, dates: task.dates.map(date => ({ key: date.key, label: date.label, value: date.value })) })
const outcome = (status: TaskRun['status']) => status === 'answered' ? t('agents.AgentTasks.respuesta_recibida') : status === 'running' ? t('agents.AgentTasks.en_curso') : t('agents.AgentTasks.fallida')
const record = (value: unknown): value is Record<string, unknown> => value !== null && typeof value === 'object' && !Array.isArray(value)
const text = (value: unknown): value is string => typeof value === 'string'
const nonempty = (value: unknown): value is string => text(value) && Boolean(value.trim())
const validTask = (value: unknown): value is TaskDefinition => record(value) && text(value.prompt) && Array.isArray(value.dates) && value.dates.every(date => record(date) && text(date.key) && text(date.label) && text(date.value)) && !taskError(value as unknown as TaskDefinition)
function savedResponse(value: unknown, agentId: string): SavedTask {
  if (!record(value) || value.agent_id !== agentId || !text(value.revision) || !value.revision || (value.task !== null && !validTask(value.task))) throw new AgentPresentationError(() => t('agents.AgentTasks.el_servidor_devolvio_una_tarea_invalida_o_de_otro_agente'))
  return value as unknown as SavedTask
}
function runResponse(value: unknown, agentId: string): TaskRun {
  if (!record(value) || value.agent_id !== agentId || !nonempty(value.run_id) || !nonempty(value.task_revision) || !validTask(value.task_snapshot) || !nonempty(value.rendered_prompt) || !text(value.workspace_root) || !(value.source_run_id === null || nonempty(value.source_run_id)) || !['running', 'answered', 'failed'].includes(String(value.status)) || !text(value.created_at) || Number.isNaN(Date.parse(value.created_at)) || !(value.completed_at === null || (text(value.completed_at) && !Number.isNaN(Date.parse(value.completed_at)))) || !(value.answer === null || text(value.answer)) || !(value.error === null || (record(value.error) && nonempty(value.error.code) && nonempty(value.error.message))) || !nonempty(value.provider_id) || !nonempty(value.model_id)) throw new AgentPresentationError(() => t('agents.AgentTasks.el_servidor_devolvio_una_ejecucion_invalida_o_de_otro_agente'))
  const ended = text(value.completed_at) && Date.parse(value.completed_at) >= Date.parse(value.created_at)
  const coherent = value.status === 'running' ? value.completed_at === null && value.answer === null && value.error === null
    : value.status === 'answered' ? ended && nonempty(value.answer) && value.error === null
      : ended && value.answer === null && value.error !== null
  if (!coherent) throw new AgentPresentationError(() => t('agents.AgentTasks.el_servidor_devolvio_un_estado_de_ejecucion_incoherente'))
  return value as unknown as TaskRun
}
function historyResponse(value: unknown, agentId: string): TaskRun[] {
  if (!record(value) || !Array.isArray(value.runs)) throw new AgentPresentationError(() => t('agents.AgentTasks.el_servidor_devolvio_un_historial_invalido'))
  return value.runs.map(item => runResponse(item, agentId))
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(path, options)
  const body = await response.json().catch(() => null)
  if (!response.ok) throw apiError(body, response.status, 'agents')
  return body as T
}

export default function AgentTasks({ initialAgentId = '' }: { initialAgentId?: string } = {}) {
  useI18n()
  const [agents, setAgents] = useState<Agent[]>([])
  const [listLoading, setListLoading] = useState(true)
  const [listError, setListError] = useState<string | Error>('')
  const [reload, setReload] = useState(0)
  const [agentId, setAgentId] = useState(initialAgentId)
  const [saved, setSaved] = useState<SavedTask | null>(null)
  const [draft, setDraft] = useState<TaskDefinition>(emptyTask)
  const [runs, setRuns] = useState<TaskRun[]>([])
  const [loading, setLoading] = useState(false)
  const [taskReload, setTaskReload] = useState(0)
  const [historyLoading, setHistoryLoading] = useState(false)
  const [busy, setBusy] = useState<'save' | 'run' | null>(null)
  const [error, setError] = useState<string | Error>('')
  const [historyError, setHistoryError] = useState<string | Error>('')
  const [notice, setNotice] = useState<string | Error>('')
  const [sourceRun, setSourceRun] = useState<string | null>(null)
  const [forceDirty, setForceDirty] = useState(false)
  const generation = useRef(0)
  const historyGeneration = useRef(0)
  const activeRequest = useRef<AbortController | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    setListLoading(true); setListError('')
    void request<{ agents: Agent[] }>('/api/agents/list', { signal: controller.signal }).then(data => {
      if (!controller.signal.aborted) {
        if (!Array.isArray(data?.agents) || !data.agents.every(agent => record(agent) && text(agent.id) && record(agent.config) && text(agent.config.name) && text(agent.config.description))) throw new AgentPresentationError(() => t('agents.AgentTasks.el_servidor_devolvio_una_lista_de_agentes_invalida'))
        setAgents(data.agents)
      }
    }).catch(cause => { if (!controller.signal.aborted) setListError(cause) }).finally(() => { if (!controller.signal.aborted) setListLoading(false) })
    return () => controller.abort()
  }, [reload])

  useEffect(() => {
    const current = ++generation.current
    const historyCurrent = ++historyGeneration.current
    const controller = new AbortController()
    activeRequest.current?.abort(); activeRequest.current = controller
    setSaved(null); setDraft(emptyTask()); setRuns([]); setError(''); setHistoryError(''); setNotice(''); setBusy(null); setSourceRun(null); setForceDirty(false)
    if (!agentId) { setLoading(false); setHistoryLoading(false); return () => controller.abort() }
    setLoading(true); setHistoryLoading(true)
    void request<SavedTask>(`/api/agents/${encodeURIComponent(agentId)}/task`, { signal: controller.signal }).then(data => {
      if (controller.signal.aborted || current !== generation.current) return
      const next = savedResponse(data, agentId)
      setSaved(next)
      setDraft(next.task ? copyTask(next.task) : { prompt: agents.find(agent => agent.id === agentId)?.config.description || '', dates: [] })
    }).catch(cause => { if (!controller.signal.aborted && current === generation.current) setError(cause) }).finally(() => { if (!controller.signal.aborted && current === generation.current) setLoading(false) })
    void request<{ runs: TaskRun[] }>(`/api/agents/${encodeURIComponent(agentId)}/task-runs?limit=50`, { signal: controller.signal }).then(data => {
      if (!controller.signal.aborted && current === generation.current && historyCurrent === historyGeneration.current) setRuns(historyResponse(data, agentId))
    }).catch(cause => { if (!controller.signal.aborted && current === generation.current && historyCurrent === historyGeneration.current) setHistoryError(cause) }).finally(() => { if (!controller.signal.aborted && current === generation.current && historyCurrent === historyGeneration.current) setHistoryLoading(false) })
    return () => controller.abort()
  }, [agentId, agents, taskReload])
  useEffect(() => () => { generation.current++; activeRequest.current?.abort() }, [])

  const dirty = forceDirty || signature(draft) !== signature(saved?.task ?? null)
  const invalid = taskError(draft)
  const updateDraft = (task: TaskDefinition) => { setDraft(task); setNotice(''); setError('') }
  const save = async () => {
    if (!saved || busy || invalid) return
    const current = generation.current
    const controller = new AbortController(); activeRequest.current = controller
    setBusy('save'); setError(''); setNotice('')
    try {
      const data = await request<SavedTask>(`/api/agents/${encodeURIComponent(agentId)}/task`, { method: 'PUT', signal: controller.signal, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ task: draft, expected_revision: saved.revision }) })
      if (controller.signal.aborted || current !== generation.current) return
      const next = savedResponse(data, agentId)
      if (!next.task) throw new AgentPresentationError(() => t('agents.AgentTasks.el_servidor_no_confirmo_la_tarea_guardada'))
      setSaved(next); setDraft(copyTask(next.task)); setForceDirty(false); setNotice(new AgentPresentationError(() => t('agents.AgentTasks.tarea_guardada')))
    } catch (cause) { if (!controller.signal.aborted && current === generation.current) setError(cause instanceof Error ? cause : new AgentPresentationError(() => t('agents.AgentTasks.no_se_pudo_guardar'))) }
    finally { if (!controller.signal.aborted && current === generation.current) setBusy(null) }
  }
  const run = async () => {
    if (!saved?.task || dirty || busy || invalid) return
    const current = generation.current
    const expected = { agentId, revision: saved.revision, task: copyTask(saved.task), sourceRunId: sourceRun, priorIds: new Set(runs.map(item => item.run_id)) }
    const controller = new AbortController(); activeRequest.current = controller
    setBusy('run'); setError(''); setNotice(new AgentPresentationError(() => t('agents.AgentTasks.ejecutando_tarea')))
    try {
      const result = await request<TaskRun>(`/api/agents/${encodeURIComponent(expected.agentId)}/task-runs`, { method: 'POST', signal: controller.signal, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ expected_revision: expected.revision, confirmed: true, source_run_id: expected.sourceRunId }) })
      if (controller.signal.aborted || current !== generation.current) return
      const next = runResponse(result, expected.agentId)
      if (next.task_revision !== expected.revision || signature(next.task_snapshot) !== signature(expected.task) || next.source_run_id !== expected.sourceRunId || expected.priorIds.has(next.run_id)) throw new AgentPresentationError(() => t('agents.AgentTasks.la_respuesta_no_corresponde_a_la_tarea_enviada_actualiza_el_historial'))
      historyGeneration.current++; setHistoryLoading(false)
      setRuns(previous => [next, ...previous.filter(item => item.run_id !== next.run_id)])
      setNotice(new AgentPresentationError(() => outcome(next.status)))
    } catch (cause) { if (!controller.signal.aborted && current === generation.current) { setError(cause instanceof Error ? cause : new AgentPresentationError(() => t('agents.AgentTasks.no_se_pudo_ejecutar'))); setNotice('') } }
    finally { if (!controller.signal.aborted && current === generation.current) setBusy(null) }
  }
  const refreshHistory = async () => {
    const current = generation.current
    const historyCurrent = ++historyGeneration.current
    setHistoryError(''); setHistoryLoading(true)
    try {
      const result = await request<{ runs: TaskRun[] }>(`/api/agents/${encodeURIComponent(agentId)}/task-runs?limit=50`)
      if (current === generation.current && historyCurrent === historyGeneration.current) setRuns(historyResponse(result, agentId))
    } catch (cause) { if (current === generation.current && historyCurrent === historyGeneration.current) setHistoryError(cause instanceof Error ? cause : new AgentPresentationError(() => t('agents.AgentTasks.historial_no_disponible'))) }
    finally { if (current === generation.current && historyCurrent === historyGeneration.current) setHistoryLoading(false) }
  }

  return <section className="agent-tasks" aria-label={t('agents.AgentTasks.tareas_de_agentes')}>
    <header className="agent-tasks-heading"><h2>{t('agents.AgentTasks.tareas')}</h2><label>{t('agents.AgentTasks.agente')}<select aria-label={t('agents.AgentTasks.agente_para_tareas')} value={agentId} disabled={listLoading} onChange={event => {
      generation.current++; activeRequest.current?.abort(); setSaved(null); setRuns([]); setDraft(emptyTask()); setError(''); setNotice(''); setAgentId(event.target.value)
    }}><option value="">{t('agents.AgentTasks.selecciona_un_agente')}</option>{agents.map(agent => <option key={agent.id} value={agent.id}>{agent.config.name}</option>)}</select></label></header>
    {listLoading && <p role="status">{t('agents.AgentManagement.cargando_agentes')}</p>}
    {listError && <div role="alert">{typeof listError === 'string' ? listError : presentAgentError(listError)} <button type="button" onClick={() => setReload(value => value + 1)}>{t('agents.AgentBuilder.reintentar')}</button></div>}
    {!listLoading && !listError && !agents.length && <p role="status">{t('agents.AgentTasks.crea_un_agente_para_guardar_su_tarea')}</p>}
    {agentId && <div className="agent-tasks-layout">
      <section className="agent-task-editor" aria-label={t('agents.AgentTasks.tarea_guardada_2')}>
        {loading ? <p role="status">{t('agents.AgentTasks.cargando_tarea')}</p> : saved && <>
          <AgentTaskForm value={draft} onChange={updateDraft} disabled={Boolean(busy)} />
          <div className="agent-task-actions"><button type="button" disabled={Boolean(busy) || !dirty || Boolean(invalid)} onClick={() => void save()}>{busy === 'save' ? t('agents.AgentTasks.guardando') : t('agents.AgentTasks.guardar_tarea')}</button><button type="button" className="primary-action" disabled={Boolean(busy) || dirty || !saved.task || Boolean(invalid)} onClick={() => void run()}>{busy === 'run' ? t('agents.AgentTasks.ejecutando') : t('agents.AgentTasks.ejecutar_tarea')}</button><span>{dirty ? t('agents.AgentTasks.sin_guardar') : t('agents.AgentTasks.guardada')}</span></div>
          {invalid && <small className="agent-task-validation">{invalid}</small>}
        </>}
        {error && <div role="alert"><p>{typeof error === 'string' ? error : presentAgentError(error)}</p><button type="button" disabled={Boolean(busy)} onClick={() => setTaskReload(value => value + 1)}>{t('agents.AgentTasks.recargar_tarea_guardada')}</button></div>}
        {notice && <p role="status">{typeof notice === 'string' ? notice : presentAgentError(notice)}</p>}
      </section>
      <section className="agent-task-history" aria-label={t('agents.AgentTasks.historial_de_tareas')}><header><h3>{t('agents.AgentTasks.historial')} <small>{runs.length}</small></h3><button type="button" disabled={historyLoading || Boolean(busy)} onClick={() => void refreshHistory()}>{t('agents.AgentManagement.actualizar')}</button></header>
        {historyLoading && <p role="status">{t('agents.AgentTasks.cargando_historial')}</p>}
        {historyError && <p role="alert">{typeof historyError === 'string' ? historyError : presentAgentError(historyError)}</p>}
        {!runs.length && !historyLoading && !historyError && <p>{t('agents.AgentTasks.sin_ejecuciones')}</p>}
        {runs.map(item => <details key={item.run_id} className="agent-task-run"><summary><strong className={`task-run-${item.status}`}>{outcome(item.status)}</strong><time dateTime={item.created_at}>{formatDate(item.created_at)}</time></summary>
          <p className="agent-task-run-prompt">{item.task_snapshot.prompt}</p>
          {item.task_snapshot.dates.length > 0 && <dl className="agent-task-run-dates">{item.task_snapshot.dates.map(date => <div key={date.key}><dt>{date.label}</dt><dd><time dateTime={date.value}>{date.value}</time></dd></div>)}</dl>}
          {item.answer !== null && <pre className="agent-task-answer">{item.answer}</pre>}
          {item.error && <p role="alert">{item.error.message} <code>{item.error.code}</code></p>}
          <div className="agent-task-run-meta"><code>{item.run_id}</code><span>{item.provider_id} · {item.model_id}</span>{item.completed_at && <span>{t('agents.AgentTasks.finalizada')} <time dateTime={item.completed_at}>{formatDate(item.completed_at)}</time></span>}</div>
          <button type="button" disabled={Boolean(busy) || loading || !saved} onClick={() => { setDraft(copyTask(item.task_snapshot)); setForceDirty(true); setSourceRun(item.run_id); setError(''); setNotice(new AgentPresentationError(() => t('agents.AgentTasks.copia_preparada_guarda_antes_de_ejecutar'))) }}>{t('agents.AgentTasks.relanzar')}</button>
        </details>)}
      </section>
    </div>}
  </section>
}
