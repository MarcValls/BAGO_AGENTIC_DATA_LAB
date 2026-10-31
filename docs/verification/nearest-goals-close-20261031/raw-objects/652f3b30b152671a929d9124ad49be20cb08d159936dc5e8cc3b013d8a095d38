import {presentAgentError} from './AgentTaskForm'
import {agentStateLabel} from './AgentTaskForm'
import {AgentPresentationError} from './AgentTaskForm'
import {useI18n, t, formatDate, formatNumber, apiError, errorMessage} from '../i18n'
import './AgentEvaluationLab.css'
import { FormEvent, useCallback, useEffect, useMemo, useState } from 'react'

type Agent = { id: string; config: { name: string; provider_id?: string | null; model_id?: string | null } }
type Model = { model_id: string; display_name?: string }
type EvaluationCase = { id: string; name: string; prompt: string; must_include: string[]; must_not_include: string[] }
type Suite = { id: string; name: string; agent_id: string; version: number; revision: number; cases: EvaluationCase[]; created_at: string; updated_at: string }
type Check = { name: string; passed: boolean; detail: string }
type CaseResult = { case_id: string; name: string; status: 'PASS' | 'FAIL' | 'ERROR'; checks: Check[]; answer_preview: string; duration_ms: number; trace: { trace_id?: string; trace_state: string; jaeger_trace_id?: string; jaeger_url?: string }; error_code?: string }
type Run = { id: string; suite_id: string; suite_version: number; suite_name: string; agent_id: string; agent_name: string; agent_config_fingerprint: string; provider_id: string; model_id: string; status: 'PASS' | 'FAIL' | 'ERROR' | 'PARTIAL'; total_cases: number; passed_cases: number; failed_cases: number; error_cases: number; duration_ms: number; started_at: string; completed_at: string; cases: CaseResult[] }
type Fetcher = typeof fetch

async function jsonRequest<T>(fetcher: Fetcher, path: string, init?: RequestInit): Promise<T> {
  const response = await fetcher(path, init)
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    throw apiError(body, response.status, 'agents')
  }
  return response.json() as Promise<T>
}

export const evaluationApi = {
  agents: (fetcher: Fetcher = fetch) => jsonRequest<{ agents: Agent[] }>(fetcher, '/api/agents/list'),
  models: (fetcher: Fetcher = fetch) => jsonRequest<{ models: Model[] }>(fetcher, '/api/providers/ollama/models'),
  providerStatus: (fetcher: Fetcher = fetch) => jsonRequest<{ state: string; model_id?: string | null }>(fetcher, '/api/providers/ollama/status'),
  suites: (fetcher: Fetcher = fetch) => jsonRequest<{ suites: Suite[] }>(fetcher, '/api/evaluations/suites'),
  runs: (fetcher: Fetcher = fetch) => jsonRequest<{ runs: Run[] }>(fetcher, '/api/evaluations/runs?limit=50'),
  createSuite: (body: { name: string; agent_id: string; cases: EvaluationCase[] }, fetcher: Fetcher = fetch) => jsonRequest<{ suite: Suite }>(fetcher, '/api/evaluations/suites', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }),
  updateSuite: (suite: Suite, body: { name: string; agent_id: string; cases: EvaluationCase[] }, fetcher: Fetcher = fetch) => jsonRequest<{ suite: Suite }>(fetcher, `/api/evaluations/suites/${encodeURIComponent(suite.id)}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ...body, expected_revision: suite.revision }) }),
  run: (suite: Suite, modelId: string, fetcher: Fetcher = fetch) => jsonRequest<{ run: Run }>(fetcher, `/api/evaluations/suites/${encodeURIComponent(suite.id)}/run`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ revision: suite.revision, model_id: modelId }) }),
}

const newCase = (): EvaluationCase => ({ id: `case_${globalThis.crypto?.randomUUID?.() ?? Date.now()}`, name: 'Case 1', prompt: '', must_include: [], must_not_include: [] })
const lines = (value: string) => value.split('\n').map((item) => item.trim()).filter(Boolean)

export default function AgentEvaluationLab({ initialAgentId = '' }: { initialAgentId?: string } = {}) {
  useI18n()
  const [agents, setAgents] = useState<Agent[]>([])
  const [models, setModels] = useState<Model[]>([])
  const [suites, setSuites] = useState<Suite[]>([])
  const [runs, setRuns] = useState<Run[]>([])
  const [selectedSuiteId, setSelectedSuiteId] = useState('')
  const [selectedRunId, setSelectedRunId] = useState('')
  const [editorOpen, setEditorOpen] = useState(Boolean(initialAgentId))
  const [suitesExpanded, setSuitesExpanded] = useState(true)
  const [agentId, setAgentId] = useState(initialAgentId)
  const [modelId, setModelId] = useState('')
  const [suiteName, setSuiteName] = useState('')
  const [cases, setCases] = useState<EvaluationCase[]>([newCase()])
  const [busy, setBusy] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | Error>('')
  const [unavailable, setUnavailable] = useState(false)
  const [loading, setLoading] = useState(true)

  const selectedSuite = suites.find((suite) => suite.id === selectedSuiteId)
  const selectedRun = runs.find((run) => run.id === selectedRunId)
  const modelBelongsToCatalog = models.some((model) => model.model_id === modelId)
  const callCount = selectedSuite?.cases.length ?? 0

  const refresh = useCallback(async () => {
    setLoading(true); setError(''); setUnavailable(false)
    try {
      const results = await Promise.all([evaluationApi.agents(), evaluationApi.models(), evaluationApi.providerStatus(), evaluationApi.suites(), evaluationApi.runs()])
      const catalog = results[1].models ?? []
      const verifiedModels = results[2].state === 'ready' && results[2].model_id
        ? catalog.filter((model) => model.model_id === results[2].model_id)
        : []
      setAgents(results[0].agents ?? []); setModels(verifiedModels); setSuites(results[3].suites ?? []); setRuns(results[4].runs ?? [])
      setModelId((current) => verifiedModels.some((model) => model.model_id === current) ? current : verifiedModels[0]?.model_id ?? '')
    } catch (cause) {
      const message = cause instanceof Error && 'originalDetail' in cause ? String(cause.originalDetail) : cause instanceof Error ? cause.message : ''
      setError(cause instanceof Error ? cause : new AgentPresentationError(() => t('agents.AgentEvaluationLab.evaluation_lab_data_could_not_be_loaded'))); setUnavailable((cause instanceof Error && 'status' in cause && cause.status === 404) || message.toLowerCase().includes('404') || message.toLowerCase().includes('unavailable') || message.toLowerCase().includes('not found'))
    } finally { setLoading(false) }
  }, [])

  useEffect(() => { void refresh() }, [refresh])
  useEffect(() => {
    if (!selectedSuite) return
    setSuiteName(selectedSuite.name); setAgentId(selectedSuite.agent_id); setCases(selectedSuite.cases.map((item) => ({ ...item, must_include: [...item.must_include], must_not_include: [...item.must_not_include] })))
  }, [selectedSuite])
  const updateCase = (index: number, update: Partial<EvaluationCase>) => setCases((items) => items.map((item, current) => current === index ? { ...item, ...update } : item))
  const selectSuite = (suite: Suite) => { setSelectedSuiteId(suite.id); setSelectedRunId(''); setEditorOpen(false); setError('') }
  const selectRun = (run: Run) => { setSelectedRunId(run.id); setSelectedSuiteId(''); setEditorOpen(false); setError('') }
  const startNewSuite = () => { setSelectedSuiteId(''); setSelectedRunId(''); setSuiteName(''); setAgentId(''); setCases([newCase()]); setEditorOpen(true); setError('') }
  const editSuite = () => {
    if (!selectedSuite) return
    setSuiteName(selectedSuite.name); setAgentId(selectedSuite.agent_id)
    setCases(selectedSuite.cases.map(item => ({ ...item, must_include: [...item.must_include], must_not_include: [...item.must_not_include] })))
    setEditorOpen(true); setError('')
  }
  const saveSuite = async (event: FormEvent) => {
    event.preventDefault(); setSaving(true); setError('')
    try {
      const body = { name: suiteName.trim(), agent_id: agentId, cases }
      const response = selectedSuite ? await evaluationApi.updateSuite(selectedSuite, body) : await evaluationApi.createSuite(body)
      await refresh()
      setSelectedSuiteId(response.suite.id)
      setEditorOpen(false)
    } catch (cause) { setError(cause instanceof Error ? cause : new AgentPresentationError(() => t('agents.AgentEvaluationLab.suite_could_not_be_saved'))) }
    finally { setSaving(false) }
  }
  const runSuite = async () => {
    if (!selectedSuite || !modelId || !modelBelongsToCatalog || busy) return
    setBusy(true); setError(''); setSelectedRunId('')
    try { const response = await evaluationApi.run(selectedSuite, modelId); await refresh(); setSelectedRunId(response.run.id); setSelectedSuiteId('') }
    catch (cause) { setError(cause instanceof Error ? cause : new AgentPresentationError(() => t('agents.AgentEvaluationLab.evaluation_run_failed'))) }
    finally { setBusy(false) }
  }

  const currentAgent = useMemo(() => agents.find((agent) => agent.id === selectedSuite?.agent_id), [agents, selectedSuite])

  if (loading) return <section className="evaluation-lab" aria-label={t('agents.AgentEvaluationLab.agent_evaluation_lab')}><p role="status">{t('agents.AgentEvaluationLab.loading_evaluation_workspace')}</p></section>
  if (unavailable) return <section className="evaluation-lab" aria-labelledby="evaluation-lab-title"><p className="eval-kicker">{t('agents.AgentEvaluationLab.workspace')}</p><h2 id="evaluation-lab-title">{t('agents.AgentEvaluationLab.agent_evaluation_lab')}</h2><div className="eval-state eval-error" role="alert"><strong>{t('agents.AgentEvaluationLab.evaluation_service_unavailable')}</strong><p>{typeof error === 'string' ? error : presentAgentError(error)}</p><button type="button" onClick={() => void refresh()}>{t('agents.AgentEvaluationLab.retry')}</button></div></section>

  return <section className="evaluation-lab" aria-label={t('agents.AgentEvaluationLab.agent_evaluation_lab')}>
    {error && <div className="eval-state eval-error" role="alert"><strong>{t('agents.AgentEvaluationLab.request_could_not_be_completed')}</strong><p>{typeof error === 'string' ? error : presentAgentError(error)}</p><button type="button" onClick={() => setError('')}>{t('agents.AgentEvaluationLab.dismiss')}</button></div>}
    <div className={`eval-layout ${suitesExpanded ? '' : 'suites-collapsed'}`}>
      <aside className={`eval-suites ${suitesExpanded ? '' : 'is-collapsed'}`} aria-label={t('agents.AgentEvaluationLab.saved_evaluation_suites')}>
        <div className="eval-section-heading eval-suites-heading">
          {suitesExpanded && <><h3>{t('agents.AgentEvaluationLab.suites')}</h3><button type="button" onClick={startNewSuite}>{t('agents.AgentEvaluationLab.new_suite')}</button></>}
          <button
            type="button"
            className="eval-suites-toggle"
            aria-label={suitesExpanded ? t('agents.AgentEvaluationLab.collapse_suites_and_run_history') : t('agents.AgentEvaluationLab.expand_suites_and_run_history')}
            aria-expanded={suitesExpanded}
            aria-controls="eval-suites-content"
            onClick={() => setSuitesExpanded((expanded) => !expanded)}
          >{suitesExpanded ? '‹' : '›'}</button>
        </div>
        <div id="eval-suites-content" hidden={!suitesExpanded}>
          {suites.map((suite) => <button type="button" className={`eval-suite-option ${suite.id === selectedSuiteId ? 'selected' : ''}`} key={suite.id} onClick={() => selectSuite(suite)}><strong>{suite.name}</strong><span>{t('agents.evaluation.suiteVersionCases',{version:formatNumber(suite.version),count:formatNumber(suite.cases.length)})}</span></button>)}
          <div className="eval-section-heading eval-history-heading"><h3>{t('agents.AgentEvaluationLab.run_history')}</h3><span>{runs.length}</span></div>
          {runs.length === 0 ? <p className="eval-empty">{t('agents.AgentEvaluationLab.no_runs_recorded')}</p> : runs.map((run) => <button type="button" className={`eval-run-option ${run.id === selectedRunId ? 'selected' : ''}`} key={run.id} onClick={() => selectRun(run)}><strong>{agentStateLabel(run.status)}</strong><span>{run.suite_name} v{run.suite_version}</span><code>{run.id}</code></button>)}
        </div>
      </aside>
      <div className="eval-main">
        {editorOpen && <form className="eval-editor" onSubmit={(event) => void saveSuite(event)}>
          <div className="eval-section-heading"><div><p className="eval-kicker">{t('agents.AgentEvaluationLab.suite_editor')}</p><h3>{selectedSuite ? t('agents.AgentEvaluationLab.edit_p0_next_version', {p0: selectedSuite.name}) : t('agents.AgentEvaluationLab.create_a_suite')}</h3></div>{selectedSuite && <span className="eval-version">{t('agents.AgentEvaluationLab.saved_v')}{selectedSuite.version}</span>}</div>
          <p className="eval-privacy-note">{t('agents.AgentEvaluationLab.do_not_include_passwords_api_keys_tokens_or_other_secrets_in_agent_pro')}</p>
          <label>{t('agents.AgentEvaluationLab.suite_name')}<input value={suiteName} maxLength={100} required onChange={(event) => setSuiteName(event.target.value)} /></label>
          <div className="eval-two-columns"><label>{t('agents.AgentEvaluationLab.agent')}<select value={agentId} required onChange={(event) => setAgentId(event.target.value)}><option value="">{t('agents.AgentEvaluationLab.select_an_existing_agent')}</option>{agents.map((agent) => <option key={agent.id} value={agent.id}>{agent.config.name} · {agent.id}</option>)}</select></label><label>{t('agents.AgentEvaluationLab.verified_ollama_model')}<select value={modelId} required onChange={(event) => setModelId(event.target.value)} disabled={!models.length}><option value="">{t('agents.AgentEvaluationLab.select_a_verified_model')}</option>{models.map((model) => <option key={model.model_id} value={model.model_id}>{model.display_name || model.model_id}</option>)}</select></label></div>
          {agents.length === 0 && <p className="eval-prerequisite" role="status">{t('agents.AgentEvaluationLab.create_an_application_agent_before_building_a_suite')}</p>}
          {models.length === 0 && <p className="eval-prerequisite" role="status">{t('agents.AgentEvaluationLab.no_verified_ollama_model_is_available_verify_a_model_in_settings_befor')}</p>}
          <div className="eval-cases-heading"><h4>{t('agents.evaluation.casesCount',{count:formatNumber(cases.length)})}</h4><button type="button" onClick={() => setCases((items) => [...items, { ...newCase(), name: `Case ${items.length + 1}` }])} disabled={cases.length >= 10}>{t('agents.AgentEvaluationLab.add_case')}</button></div>
          {cases.map((item, index) => <fieldset className="eval-case" key={item.id}><legend>{t('agents.evaluation.caseNumber',{count:formatNumber(index+1)})}</legend><button className="eval-remove-case" type="button" onClick={() => setCases((items) => items.length > 1 ? items.filter((_, current) => current !== index) : items)} aria-label={t('agents.AgentEvaluationLab.remove_case_p0', {p0: index + 1})} disabled={cases.length === 1}>{t('agents.AgentEvaluationLab.remove')}</button><label>{t('agents.AgentEvaluationLab.case_name')}<input value={item.name} maxLength={100} required onChange={(event) => updateCase(index, { name: event.target.value })} /></label><label>{t('agents.AgentEvaluationLab.prompt')}<textarea value={item.prompt} maxLength={4000} required rows={3} onChange={(event) => updateCase(index, { prompt: event.target.value })} /></label><div className="eval-two-columns"><label>{t('agents.AgentEvaluationLab.must_include')} <small>{t('agents.AgentEvaluationLab.one_assertion_per_line_up_to_8_each_up_to_240_characters')}</small><textarea value={item.must_include.join('\n')} rows={2} onChange={(event) => updateCase(index, { must_include: lines(event.target.value).slice(0, 8).map((value) => value.slice(0, 240)) })} /></label><label>{t('agents.AgentEvaluationLab.must_not_include')} <small>{t('agents.AgentEvaluationLab.one_assertion_per_line_up_to_8_each_up_to_240_characters')}</small><textarea value={item.must_not_include.join('\n')} rows={2} onChange={(event) => updateCase(index, { must_not_include: lines(event.target.value).slice(0, 8).map((value) => value.slice(0, 240)) })} /></label></div></fieldset>)}
          <button className="eval-save" type="submit" disabled={saving || busy || cases.length < 1 || cases.length > 10 || !agentId || !suiteName.trim() || cases.some((item) => !item.prompt.trim() || !item.name.trim())}>{saving ? t('agents.AgentEvaluationLab.saving_suite') : selectedSuite ? t('agents.AgentEvaluationLab.save_as_new_version') : t('agents.AgentEvaluationLab.save_suite')}</button>
          <button type="button" className="eval-cancel" onClick={() => setEditorOpen(false)} disabled={saving}>{t('agents.AgentBuilder.cancel')}</button>
        </form>}
        {!editorOpen && !selectedSuite && !selectedRun && <section className="eval-selection" aria-label={t('agents.AgentEvaluationLab.evaluation_selection')}><h3>{t('agents.AgentEvaluationLab.select_a_suite_or_run')}</h3><p>{t('agents.AgentEvaluationLab.choose_a_saved_suite_to_review_it_or_a_past_run_to_see_its_results')}</p></section>}
        {!editorOpen && selectedSuite && !selectedRun && <section className="eval-review" aria-labelledby="eval-review-title">
          <div className="eval-section-heading"><div><p className="eval-kicker">{t('agents.AgentEvaluationLab.review_before_inference')}</p><h3 id="eval-review-title">{t('agents.AgentEvaluationLab.run_review')}</h3></div><button type="button" onClick={editSuite} disabled={busy}>{t('agents.AgentEvaluationLab.edit_suite')}</button></div>
          <dl><div><dt>{t('agents.AgentEvaluationLab.suite')}</dt><dd>{selectedSuite.name} v{selectedSuite.version}</dd></div><div><dt>{t('agents.AgentEvaluationLab.agent')}</dt><dd>{currentAgent?.config.name ?? t('agents.AgentEvaluationLab.choose_an_agent')}</dd></div><div><dt>{t('agents.AgentEvaluationLab.effective_model')}</dt><dd>{modelId || t('agents.AgentEvaluationLab.choose_a_discovered_model')}</dd></div><div><dt>{t('agents.AgentEvaluationLab.provider_requests')}</dt><dd>{t('agents.evaluation.requestsCount',{count:formatNumber(callCount)})}</dd></div></dl>
          <label className="eval-model-picker">{t('agents.AgentEvaluationLab.verified_ollama_model')}<select value={modelId} required onChange={event => setModelId(event.target.value)} disabled={!models.length || busy}><option value="">{t('agents.AgentEvaluationLab.select_a_verified_model')}</option>{models.map(model => <option key={model.model_id} value={model.model_id}>{model.display_name || model.model_id}</option>)}</select></label>
          {models.length === 0 && <p className="eval-prerequisite" role="status">{t('agents.AgentEvaluationLab.no_verified_ollama_model_is_available_verify_a_model_in_settings_befor')}</p>}
          <details className="eval-suite-cases"><summary>{t('agents.evaluation.savedCasesCount',{count:formatNumber(selectedSuite.cases.length)})}</summary>{selectedSuite.cases.map(item => <article className="eval-result-case" key={item.id}><h4>{item.name}</h4><pre>{item.prompt}</pre>{item.must_include.length > 0 && <p><strong>{t('agents.AgentEvaluationLab.must_include_2')}</strong> {item.must_include.join(' · ')}</p>}{item.must_not_include.length > 0 && <p><strong>{t('agents.AgentEvaluationLab.must_not_include_2')}</strong> {item.must_not_include.join(' · ')}</p>}</article>)}</details>
          <p>{t('agents.AgentEvaluationLab.run_sends_each_saved_prompt_to_ollama_cloud')}</p><button className="eval-run-button" type="button" onClick={() => void runSuite()} disabled={busy || saving || !modelId || !modelBelongsToCatalog}>{busy ? t('agents.AgentEvaluationLab.running_evaluation') : t('agents.AgentEvaluationLab.run_evaluation')}</button>
        </section>}
        {selectedRun && <section className="eval-results" aria-labelledby="eval-results-title"><p className="eval-kicker">{t('agents.AgentEvaluationLab.persisted_run')} {selectedRun.id}</p><h3 id="eval-results-title">{agentStateLabel(selectedRun.status)} · {selectedRun.suite_name} v{selectedRun.suite_version}</h3>{selectedRun.status === 'ERROR' && <p className="eval-state eval-error" role="alert"><strong>{t('agents.AgentEvaluationLab.evaluation_run_error')}</strong><span> {t('agents.AgentEvaluationLab.the_run_did_not_complete_this_is_a_provider_or_execution_error_not_a_d')}</span></p>}<dl className="eval-run-identity"><div><dt>{t('agents.AgentEvaluationLab.agent')}</dt><dd>{selectedRun.agent_name} ({selectedRun.agent_id})</dd></div><div><dt>{t('agents.AgentEvaluationLab.model')}</dt><dd>{selectedRun.provider_id} · {selectedRun.model_id}</dd></div><div><dt>{t('agents.AgentEvaluationLab.config_fingerprint')}</dt><dd><code>{selectedRun.agent_config_fingerprint}</code></dd></div><div><dt>{t('agents.AgentEvaluationLab.cases_2_3')}</dt><dd>{t('agents.evaluation.resultCounts',{passed:formatNumber(selectedRun.passed_cases),failed:formatNumber(selectedRun.failed_cases),errors:formatNumber(selectedRun.error_cases)})}</dd></div><div><dt>{t('agents.AgentEvaluationLab.cost')}</dt><dd>{t('agents.AgentEvaluationLab.not_reported_by_provider')}</dd></div></dl>{selectedRun.cases.map((result) => <article className="eval-result-case" key={result.case_id}><h4>{agentStateLabel(result.status)} · {result.name}</h4>{result.status === 'ERROR' && <p className="eval-state eval-error" role="alert"><strong>{t('agents.AgentEvaluationLab.provider_or_execution_error')}</strong><span> {t('agents.AgentEvaluationLab.no_deterministic_assertion_result_is_available_for_this_case')}</span></p>}<p>{result.duration_ms} ms{result.error_code ? ` · ${result.error_code}` : ''}</p><ul>{result.checks.map((check, index) => <li key={`${check.name}-${index}`}><strong>{agentStateLabel(check.passed ? 'PASS' : 'FAIL')}</strong> · {check.name}: {check.detail}</li>)}</ul>{result.answer_preview && <details><summary>{t('agents.AgentEvaluationLab.answer_preview')}</summary><pre>{result.answer_preview}</pre></details>}<p>{result.trace.trace_state === 'local_trace_failed' ? <><strong>{t('agents.AgentEvaluationLab.localtrace_not_saved')}</strong> {result.trace.trace_id && <span>{t('agents.AgentEvaluationLab.provisional_trace_id_not_persisted')} <code>{result.trace.trace_id}</code>. </span>}{t('agents.AgentEvaluationLab.trace_lookup_is_unavailable')}</> : result.trace.trace_state === 'saved' && result.trace.trace_id ? <>{t('agents.AgentEvaluationLab.localtrace_saved')} <code>{result.trace.trace_id}</code></> : <>{t('agents.AgentEvaluationLab.localtrace_unavailable')} {result.trace.trace_state || t('agents.AgentEvaluationLab.unknown_trace_state')}.</>}</p>{result.trace.jaeger_trace_id && result.trace.jaeger_url && <a href={result.trace.jaeger_url} target="_blank" rel="noreferrer">{t('agents.evaluation.openTrace',{id:result.trace.jaeger_trace_id})}</a>}</article>)}</section>}
      </div>
    </div>
  </section>
}
