import {presentAgentError} from './AgentTaskForm'
import {AgentPresentationError} from './AgentTaskForm'
import {useI18n, t, formatDate, formatNumber, apiError, errorMessage} from '../i18n'
import { useEffect, useId, useRef, useState } from 'react'
import AgentTaskForm, { taskError, type TaskDefinition } from './AgentTaskForm'
import TaskExecutionPanel from './TaskExecutionPanel'
import './AgentTasks.css'
import './AgentTaskResponse.css'

type Agent = { id: string; config: { name: string; description: string } }
type SavedTask = { agent_id: string; task: TaskDefinition | null; revision: string }
type TaskRun = {
  run_id: string; agent_id: string; task_revision: string; task_snapshot: TaskDefinition;
  rendered_prompt: string; provider_id: string; model_id: string; workspace_root: string;
  source_run_id: string | null; created_at: string; completed_at: string | null;
  status: 'running' | 'answered' | 'failed'; answer: string | null; error: { code: string; message: string } | null;
}
type Reviewer = {agent_id: string; name: string; profile_sha256: string; provider_id: string; model_id: string}
type TaskReview = {review_id: string; source_agent_id: string; source_run_id: string; source_sha256: string;
  source_snapshot: TaskRun; reviewer_agent_id: string; reviewer_profile_sha256: string; reviewer_name: string;
  status: 'running' | 'answered' | 'failed'; answer: string | null; error: {code: string; message: string} | null;
  created_at: string; completed_at: string | null; review_request: string}
type ReviewContext = {source_run: TaskRun; source_sha256: string; reviewers: Reviewer[]; reviews: TaskReview[]}
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
const digest = (value: unknown): value is string => text(value) && /^[a-f0-9]{64}$/.test(value)
const runSignature = (run: TaskRun) => JSON.stringify([run.run_id, run.agent_id, run.task_revision, signature(run.task_snapshot),
  run.rendered_prompt, run.provider_id, run.model_id, run.workspace_root, run.source_run_id, run.created_at, run.completed_at,
  run.status, run.answer, run.error?.code ?? null, run.error?.message ?? null])
function reviewResponse(value: unknown, source: TaskRun, sourceHash: string): TaskReview {
  const invalid = () => new AgentPresentationError(() => t('agents.AgentTasks.invalid_review'))
  if (!record(value) || !nonempty(value.review_id) || value.source_agent_id !== source.agent_id || value.source_run_id !== source.run_id ||
      value.source_sha256 !== sourceHash || !nonempty(value.reviewer_agent_id) || value.reviewer_agent_id === source.agent_id ||
      !digest(value.reviewer_profile_sha256) || !text(value.reviewer_name) || !nonempty(value.review_request) ||
      !['running', 'answered', 'failed'].includes(String(value.status)) || !text(value.created_at) || Number.isNaN(Date.parse(value.created_at)) ||
      !(value.completed_at === null || (text(value.completed_at) && !Number.isNaN(Date.parse(value.completed_at)))) ||
      !(value.answer === null || text(value.answer)) || !(value.error === null || (record(value.error) && nonempty(value.error.code) && nonempty(value.error.message)))) throw invalid()
  if (runSignature(runResponse(value.source_snapshot, source.agent_id)) !== runSignature(source)) throw invalid()
  let requestData: unknown
  try { requestData = JSON.parse(value.review_request) } catch { throw invalid() }
  if (!record(requestData) || requestData.source_agent_id !== source.agent_id || requestData.source_run_id !== source.run_id ||
      requestData.source_sha256 !== sourceHash || runSignature(runResponse(requestData.source_snapshot, source.agent_id)) !== runSignature(source)) throw invalid()
  const ended = text(value.completed_at) && Date.parse(value.completed_at) >= Date.parse(value.created_at)
  const coherent = value.status === 'running' ? value.completed_at === null && value.answer === null && value.error === null
    : value.status === 'answered' ? ended && nonempty(value.answer) && value.error === null : ended && value.answer === null && value.error !== null
  if (!coherent) throw invalid()
  return value as unknown as TaskReview
}
function reviewContextResponse(value: unknown, source: TaskRun): ReviewContext {
  const invalid = () => new AgentPresentationError(() => t('agents.AgentTasks.invalid_review'))
  if (!record(value) || !digest(value.source_sha256) || !Array.isArray(value.reviewers) || !Array.isArray(value.reviews)) throw invalid()
  const received = runResponse(value.source_run, source.agent_id)
  if (runSignature(received) !== runSignature(source)) throw new AgentPresentationError(() => t('agents.AgentTasks.review_source_changed'))
  const seen = new Set<string>()
  const reviewers = value.reviewers.map(item => {
    if (!record(item) || !nonempty(item.agent_id) || item.agent_id === source.agent_id || seen.has(item.agent_id) || !text(item.name) ||
        !digest(item.profile_sha256) || !nonempty(item.provider_id) || !nonempty(item.model_id)) throw invalid()
    seen.add(item.agent_id); return item as unknown as Reviewer
  })
  return {source_run: received, source_sha256: value.source_sha256, reviewers,
    reviews: value.reviews.map(item => reviewResponse(item, received, value.source_sha256 as string))}
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(path, options)
  const body = await response.json().catch(() => null)
  if (!response.ok) throw apiError(body, response.status, 'agents')
  return body as T
}

export default function AgentTasks({ initialAgentId = '' }: { initialAgentId?: string } = {}) {
  useI18n()
  const reviewUid = useId()
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
  const [busy, setBusy] = useState<'save' | 'run' | 'edit' | 'review' | null>(null)
  const [error, setError] = useState<string | Error>('')
  const [historyError, setHistoryError] = useState<string | Error>('')
  const [notice, setNotice] = useState<string | Error>('')
  const [sourceRun, setSourceRun] = useState<string | null>(null)
  const [forceDirty, setForceDirty] = useState(false)
  const editor = useRef<HTMLElement | null>(null)
  const [editConfirm, setEditConfirm] = useState(false), [focusEditor, setFocusEditor] = useState(false)
  const [reviewSource, setReviewSource] = useState<TaskRun | null>(null), [reviewContext, setReviewContext] = useState<ReviewContext | null>(null)
  const [reviewerId, setReviewerId] = useState('')
  const [reviewLoading, setReviewLoading] = useState(false), [reviewError, setReviewError] = useState<string | Error>('')
  const reviewHeading = useRef<HTMLHeadingElement | null>(null)
  const reviewGeneration = useRef(0)
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
    setEditConfirm(false); setFocusEditor(false); setReviewSource(null); setReviewContext(null); setReviewError(''); setReviewLoading(false)
    reviewGeneration.current++
    if (listLoading) {setLoading(true);setHistoryLoading(true);return () => controller.abort()}
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
  }, [agentId, agents, taskReload, listLoading])
  useEffect(() => () => { generation.current++; activeRequest.current?.abort() }, [])
  useEffect(() => { if (focusEditor && !busy && !loading) {
    const input = editor.current?.querySelector<HTMLTextAreaElement>('textarea')
    input?.focus(); input?.scrollIntoView?.({block: 'center'}); setFocusEditor(false)
  } }, [focusEditor, busy, loading])
  useEffect(() => { if (reviewSource) reviewHeading.current?.focus() }, [reviewSource])

  const dirty = forceDirty || signature(draft) !== signature(saved?.task ?? null)
  const invalid = taskError(draft)
  const updateDraft = (task: TaskDefinition) => { setDraft(task); setNotice(''); setError('') }
  const editCurrent = async (discard = false) => {
    if (busy || loading || !saved) return
    if (dirty && !discard) { setEditConfirm(true); return }
    const current = generation.current, priorRevision = saved.revision, priorSource = sourceRun
    const controller = new AbortController(); activeRequest.current = controller
    setBusy('edit'); setEditConfirm(false); setError(''); setNotice('')
    try {
      const data = await request<SavedTask>(`/api/agents/${encodeURIComponent(agentId)}/task`, {signal: controller.signal})
      if (controller.signal.aborted || current !== generation.current) return
      const next = savedResponse(data, agentId)
      setSaved(next); setDraft(next.task ? copyTask(next.task) : emptyTask()); setForceDirty(false)
      setSourceRun(!dirty && next.revision === priorRevision ? priorSource : null)
      setFocusEditor(true); setNotice(new AgentPresentationError(() => t('agents.AgentTasks.manual_edit_notice')))
    } catch (cause) { if (!controller.signal.aborted && current === generation.current) setError(cause instanceof Error ? cause : new AgentPresentationError(() => t('agents.AgentTasks.no_se_pudo_guardar'))) }
    finally { if (!controller.signal.aborted && current === generation.current) setBusy(null) }
  }
  const openReview = async (source: TaskRun) => {
    if (busy || source.status !== 'answered' || source.agent_id !== agentId) return
    const current = generation.current, reviewCurrent = ++reviewGeneration.current
    setReviewSource(source); setReviewContext(null); setReviewerId(''); setReviewError(''); setReviewLoading(true)
    try {
      const data = await request<unknown>(`/api/agents/${encodeURIComponent(source.agent_id)}/task-runs/${encodeURIComponent(source.run_id)}/reviews`)
      if (current === generation.current && reviewCurrent === reviewGeneration.current) {
        const context = reviewContextResponse(data, source)
        setReviewContext(context)
        if (!context.reviews.length && context.reviewers.length === 1) {
          setReviewerId(context.reviewers[0].agent_id)
          void executeReview(context.reviewers[0].agent_id, context, source)
        }
      }
    } catch (cause) { if (current === generation.current && reviewCurrent === reviewGeneration.current) setReviewError(cause instanceof Error ? cause : String(cause)) }
    finally { if (current === generation.current && reviewCurrent === reviewGeneration.current) setReviewLoading(false) }
  }
  const closeReview = () => { if (!busy) {reviewGeneration.current++; setReviewSource(null); setReviewContext(null); setReviewLoading(false)} }
  const reviewLock = useRef(false)
  const executeReview = async (selectedId = reviewerId, context = reviewContext, source = reviewSource) => {
    const selected = context?.reviewers.find(item => item.agent_id === selectedId)
    if (!source || !context || !selected || busy || reviewLock.current || selected.agent_id === agentId || source.agent_id !== agentId) return
    const current = generation.current
    reviewLock.current = true
    const controller = new AbortController(); activeRequest.current = controller
    setBusy('review'); setReviewError('')
    try {
      const data = await request<unknown>(`/api/agents/${encodeURIComponent(source.agent_id)}/task-runs/${encodeURIComponent(source.run_id)}/reviews`, {
        method: 'POST', signal: controller.signal, headers: {'Content-Type': 'application/json'}, body: JSON.stringify({
          reviewer_agent_id: selected.agent_id, expected_source_sha256: context.source_sha256,
          expected_reviewer_sha256: selected.profile_sha256, confirmed: true})})
      if (controller.signal.aborted || current !== generation.current) return
      const result = reviewResponse(data, context.source_run, context.source_sha256)
      if (result.reviewer_agent_id !== selected.agent_id || result.reviewer_profile_sha256 !== selected.profile_sha256) throw new AgentPresentationError(() => t('agents.AgentTasks.invalid_review'))
      setReviewContext({...context, reviews: [result, ...context.reviews.filter(item => item.review_id !== result.review_id)]})
    } catch (cause) { if (!controller.signal.aborted && current === generation.current) setReviewError(cause instanceof Error ? cause : String(cause)) }
    finally { reviewLock.current = false; if (!controller.signal.aborted && current === generation.current) setBusy(null) }
  }
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
  const selectedReviewer = reviewContext?.reviewers.find(item => item.agent_id === reviewerId)
  const reviewPanel = reviewSource ? (<section className="agent-task-review-panel" role="region" aria-labelledby={`${reviewUid}-heading`} onKeyDown={event => {
      if (event.key === 'Escape' && !busy) {closeReview(); return}
    }}>
      <h3 id={`${reviewUid}-heading`} tabIndex={-1} ref={reviewHeading}>{t('agents.AgentTasks.independent_review')}</h3>
      <p>{t('agents.AgentTasks.review_scope')}</p><p><code>{reviewSource.run_id}</code></p>
      {reviewLoading && <p role="status">{t('agents.AgentTasks.loading_review')}</p>}
      {reviewError && <p role="alert">{typeof reviewError === 'string' ? reviewError : presentAgentError(reviewError)}</p>}
      {reviewContext && <>
        <details><summary>{t('agents.AgentTasks.review_snapshot')}</summary><code>{reviewContext.source_sha256}</code><h4>{t('agents.AgentTasks.sent_request')}</h4><pre>{reviewContext.source_run.rendered_prompt}</pre><h4>{t('agents.AgentTasks.agent_answer')}</h4><pre>{reviewContext.source_run.answer}</pre></details>
        <label>{t('agents.AgentTasks.reviewer_label')}<select value={reviewerId} disabled={Boolean(busy)} onChange={event => {setReviewerId(event.target.value); if(event.target.value)void executeReview(event.target.value)}}><option value="">{t('agents.AgentTasks.choose_reviewer')}</option>{reviewContext.reviewers.map(item => <option key={item.agent_id} value={item.agent_id}>{item.name || item.agent_id} · {item.provider_id} / {item.model_id}</option>)}</select></label>
        {selectedReviewer && <details><summary>{t('agents.AgentTasks.review_binding')}</summary><code>{selectedReviewer.agent_id}</code><code>{selectedReviewer.profile_sha256}</code></details>}
        {!reviewContext.reviewers.length && <p role="status">{t('agents.AgentTasks.no_reviewer')}</p>}
        {busy==='review'&&<p role="status">{t('agents.AgentTasks.reviewing')}</p>}
        {reviewError&&<button type="button" disabled={Boolean(busy)||!reviewerId} onClick={()=>void executeReview()}>{t('agents.AgentBuilder.reintentar')}</button>}
        <h4>{t('agents.AgentTasks.saved_reviews')}</h4>
        {!reviewContext.reviews.length && <p>{t('agents.AgentTasks.no_reviews')}</p>}
        {reviewContext.reviews.map(item => <article className="agent-task-review-result" key={item.review_id}>
          <h4>{item.reviewer_name || item.reviewer_agent_id} · {outcome(item.status)}</h4><code>{item.review_id}</code>
          <p>{t('agents.AgentTasks.review_advisory')}</p>
          {item.answer !== null && <pre>{item.answer}</pre>}{item.error && <p role="alert">{item.error.message} <code>{item.error.code}</code></p>}
          <details><summary>{t('agents.AgentTasks.review_binding')}</summary><code>{item.source_run_id}</code><code>{item.source_sha256}</code><code>{item.reviewer_agent_id}</code><code>{item.reviewer_profile_sha256}</code></details>
        </article>)}
      </>}
      <button type="button" disabled={Boolean(busy) || reviewLoading} onClick={() => void openReview(reviewSource)}>{t('agents.AgentManagement.actualizar')}</button>
      <button type="button" disabled={Boolean(busy)} onClick={closeReview}>{t('agents.AgentTasks.close_review')}</button>
    </section>) : null


  return <section className="agent-tasks" aria-label={t('agents.AgentTasks.tareas_de_agentes')}>
    <header className="agent-tasks-heading"><h2>{t('agents.AgentTasks.tareas')}</h2><label>{t('agents.AgentTasks.agente')}<select aria-label={t('agents.AgentTasks.agente_para_tareas')} value={agentId} disabled={listLoading} onChange={event => {
      generation.current++; activeRequest.current?.abort(); setSaved(null); setRuns([]); setDraft(emptyTask()); setError(''); setNotice(''); setAgentId(event.target.value)
    }}><option value="">{t('agents.AgentTasks.selecciona_un_agente')}</option>{agents.map(agent => <option key={agent.id} value={agent.id}>{agent.config.name}</option>)}</select></label></header>
    {listLoading && <p role="status">{t('agents.AgentManagement.cargando_agentes')}</p>}
    {listError && <div role="alert">{typeof listError === 'string' ? listError : presentAgentError(listError)} <button type="button" onClick={() => setReload(value => value + 1)}>{t('agents.AgentBuilder.reintentar')}</button></div>}
    <TaskExecutionPanel sourceIdentity={agentId&&saved?`${agentId}:${saved.revision}`:'new-task'} taskText={saved?.task?.prompt||''}/>
    {!listLoading && !listError && !agents.length && <p role="status">{t('agents.AgentTasks.crea_un_agente_para_guardar_su_tarea')}</p>}
    {agentId && <div className="agent-tasks-layout">
      <section className="agent-task-editor" ref={editor} aria-label={t('agents.AgentTasks.tarea_guardada_2')}>
        {loading ? <p role="status">{t('agents.AgentTasks.cargando_tarea')}</p> : saved && <>
          <AgentTaskForm value={draft} onChange={updateDraft} disabled={Boolean(busy)} />
          <div className="agent-task-actions"><button type="button" disabled={Boolean(busy)} onClick={() => void editCurrent()}>{t('agents.AgentTasks.edit_manually')}</button><button type="button" disabled={Boolean(busy) || !dirty || Boolean(invalid)} onClick={() => void save()}>{busy === 'save' ? t('agents.AgentTasks.guardando') : t('agents.AgentTasks.guardar_tarea')}</button><button type="button" className="primary-action" disabled={Boolean(busy) || dirty || !saved.task || Boolean(invalid)} onClick={() => void run()}>{busy === 'run' ? t('agents.AgentTasks.ejecutando') : t('agents.AgentTasks.ejecutar_tarea')}</button><span>{dirty ? t('agents.AgentTasks.sin_guardar') : t('agents.AgentTasks.guardada')}</span></div>
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
          <div className="agent-task-result"><h4>{t('agents.AgentTasks.agent_answer')}</h4>
            {item.answer !== null && <><p className="agent-task-answer-scope">{t('agents.AgentTasks.answer_scope')}</p><pre className="agent-task-answer">{item.answer}</pre></>}
            {item.status === 'running' && <p role="status">{t('agents.AgentTasks.awaiting_answer')}</p>}
            {item.error && <p role="alert">{item.error.message} <code>{item.error.code}</code></p>}
          </div>
          <details className="agent-task-sent-request"><summary>{t('agents.AgentTasks.sent_request')}</summary>
            <p className="agent-task-run-prompt">{item.rendered_prompt}</p>
            {item.task_snapshot.dates.length > 0 && <dl className="agent-task-run-dates">{item.task_snapshot.dates.map(date => <div key={date.key}><dt>{date.label}</dt><dd><time dateTime={date.value}>{date.value}</time></dd></div>)}</dl>}
          </details>
          <div className="agent-task-run-meta"><code>{item.run_id}</code><span>{item.provider_id} · {item.model_id}</span>{item.completed_at && <span>{t('agents.AgentTasks.finalizada')} <time dateTime={item.completed_at}>{formatDate(item.completed_at)}</time></span>}</div>
          <button type="button" disabled={Boolean(busy) || loading || !saved} onClick={() => { setDraft(copyTask(item.task_snapshot)); setForceDirty(true); setSourceRun(item.run_id); setError(''); setNotice(new AgentPresentationError(() => t('agents.AgentTasks.copia_preparada_guarda_antes_de_ejecutar'))) }}>{t('agents.AgentTasks.relanzar')}</button>
          <button type="button" disabled={Boolean(busy) || reviewLoading || item.status !== 'answered'} onClick={() => void openReview(item)}>{t('agents.AgentTasks.independent_review')}</button>
          {reviewSource?.run_id===item.run_id&&reviewPanel}
          {item.status==='answered'&&<TaskExecutionPanel sourceIdentity={item.run_id} taskText={item.rendered_prompt}/>}
          <p className="agent-task-answer-scope">{t('agents.AgentTasks.copy_scope')}</p>
        </details>)}
      </section>
    </div>}
    {editConfirm && <section className="agent-task-action-dialog" role="alertdialog" aria-label={t('agents.AgentTasks.edit_manually')} onKeyDown={event => {if (event.key === 'Escape') setEditConfirm(false)}}>
      <p>{t('agents.AgentTasks.discard_draft_notice')}</p><button type="button" onClick={() => void editCurrent(true)}>{t('agents.AgentTasks.load_saved_task')}</button><button type="button" onClick={() => setEditConfirm(false)}>{t('agents.AgentManagement.cancelar')}</button>
    </section>}

  </section>
}
