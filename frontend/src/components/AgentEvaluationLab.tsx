import { FormEvent, useCallback, useEffect, useMemo, useState } from 'react'
import './AgentEvaluationLab.css'

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
    let message = `Request failed (${response.status}).`
    try { const body = await response.json(); if (typeof body?.detail?.message === 'string') message = body.detail.message; else if (typeof body?.detail === 'string') message = body.detail } catch { /* safe status message */ }
    throw new Error(message)
  }
  return response.json() as Promise<T>
}

export const evaluationApi = {
  agents: (fetcher: Fetcher = fetch) => jsonRequest<{ agents: Agent[] }>(fetcher, '/api/agents/list'),
  models: (fetcher: Fetcher = fetch) => jsonRequest<{ models: Model[] }>(fetcher, '/api/providers/ollama/models'),
  suites: (fetcher: Fetcher = fetch) => jsonRequest<{ suites: Suite[] }>(fetcher, '/api/evaluations/suites'),
  runs: (fetcher: Fetcher = fetch) => jsonRequest<{ runs: Run[] }>(fetcher, '/api/evaluations/runs?limit=50'),
  createSuite: (body: { name: string; agent_id: string; cases: EvaluationCase[] }, fetcher: Fetcher = fetch) => jsonRequest<{ suite: Suite }>(fetcher, '/api/evaluations/suites', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }),
  updateSuite: (suite: Suite, body: { name: string; agent_id: string; cases: EvaluationCase[] }, fetcher: Fetcher = fetch) => jsonRequest<{ suite: Suite }>(fetcher, `/api/evaluations/suites/${encodeURIComponent(suite.id)}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ...body, expected_revision: suite.revision }) }),
  run: (suite: Suite, modelId: string, fetcher: Fetcher = fetch) => jsonRequest<{ run: Run }>(fetcher, `/api/evaluations/suites/${encodeURIComponent(suite.id)}/run`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ revision: suite.revision, model_id: modelId }) }),
}

const newCase = (): EvaluationCase => ({ id: `case_${globalThis.crypto?.randomUUID?.() ?? Date.now()}`, name: 'Case 1', prompt: '', must_include: [], must_not_include: [] })
const lines = (value: string) => value.split('\n').map((item) => item.trim()).filter(Boolean)

export default function AgentEvaluationLab() {
  const [agents, setAgents] = useState<Agent[]>([])
  const [models, setModels] = useState<Model[]>([])
  const [suites, setSuites] = useState<Suite[]>([])
  const [runs, setRuns] = useState<Run[]>([])
  const [selectedSuiteId, setSelectedSuiteId] = useState('')
  const [selectedRunId, setSelectedRunId] = useState('')
  const [agentId, setAgentId] = useState('')
  const [modelId, setModelId] = useState('')
  const [suiteName, setSuiteName] = useState('')
  const [cases, setCases] = useState<EvaluationCase[]>([newCase()])
  const [busy, setBusy] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [unavailable, setUnavailable] = useState(false)
  const [loading, setLoading] = useState(true)

  const selectedSuite = suites.find((suite) => suite.id === selectedSuiteId)
  const selectedRun = runs.find((run) => run.id === selectedRunId)
  const modelBelongsToCatalog = models.some((model) => model.model_id === modelId)
  const callCount = cases.length

  const refresh = useCallback(async () => {
    setLoading(true); setError(''); setUnavailable(false)
    try {
      const results = await Promise.all([evaluationApi.agents(), evaluationApi.models(), evaluationApi.suites(), evaluationApi.runs()])
      setAgents(results[0].agents ?? []); setModels(results[1].models ?? []); setSuites(results[2].suites ?? []); setRuns(results[3].runs ?? [])
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : 'Evaluation Lab data could not be loaded.'
      setError(message); setUnavailable(message.toLowerCase().includes('404') || message.toLowerCase().includes('unavailable') || message.toLowerCase().includes('not found'))
    } finally { setLoading(false) }
  }, [])

  useEffect(() => { void refresh() }, [refresh])
  useEffect(() => {
    if (!selectedSuite) return
    setSuiteName(selectedSuite.name); setAgentId(selectedSuite.agent_id); setCases(selectedSuite.cases.map((item) => ({ ...item, must_include: [...item.must_include], must_not_include: [...item.must_not_include] })))
  }, [selectedSuite])
  useEffect(() => { if (!agentId) return; const agent = agents.find((item) => item.id === agentId); if (agent?.config.model_id && models.some((item) => item.model_id === agent.config.model_id)) setModelId(agent.config.model_id) }, [agentId, agents, models])

  const updateCase = (index: number, update: Partial<EvaluationCase>) => setCases((items) => items.map((item, current) => current === index ? { ...item, ...update } : item))
  const startNewSuite = () => { setSelectedSuiteId(''); setSuiteName(''); setAgentId(''); setCases([newCase()]); setError('') }
  const saveSuite = async (event: FormEvent) => {
    event.preventDefault(); setSaving(true); setError('')
    try {
      const body = { name: suiteName.trim(), agent_id: agentId, cases }
      const response = selectedSuite ? await evaluationApi.updateSuite(selectedSuite, body) : await evaluationApi.createSuite(body)
      await refresh()
      setSelectedSuiteId(response.suite.id)
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Suite could not be saved.') }
    finally { setSaving(false) }
  }
  const runSuite = async () => {
    if (!selectedSuite || !modelId || !modelBelongsToCatalog || busy) return
    setBusy(true); setError(''); setSelectedRunId('')
    try { const response = await evaluationApi.run(selectedSuite, modelId); await refresh(); setSelectedRunId(response.run.id) }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Evaluation run failed.') }
    finally { setBusy(false) }
  }

  const currentAgent = useMemo(() => agents.find((agent) => agent.id === agentId), [agents, agentId])

  if (loading) return <section className="evaluation-lab" aria-labelledby="evaluation-lab-title"><p role="status">Loading evaluation workspace…</p></section>
  if (unavailable) return <section className="evaluation-lab" aria-labelledby="evaluation-lab-title"><p className="eval-kicker">Workspace</p><h2 id="evaluation-lab-title">Agent Evaluation Lab</h2><div className="eval-state eval-error" role="alert"><strong>Evaluation service unavailable</strong><p>{error}</p><button type="button" onClick={() => void refresh()}>Retry</button></div></section>

  return <section className="evaluation-lab" aria-labelledby="evaluation-lab-title">
    <header className="eval-header"><div><p className="eval-kicker">Workspace · deterministic checks</p><h2 id="evaluation-lab-title">Agent Evaluation Lab</h2><p>Compare an existing agent against saved cases. Checks are explicit substring rules, not a general quality score.</p></div><button type="button" onClick={() => void refresh()} disabled={busy || saving}>Refresh</button></header>
    {error && <div className="eval-state eval-error" role="alert"><strong>Request could not be completed</strong><p>{error}</p><button type="button" onClick={() => setError('')}>Dismiss</button></div>}
    <div className="eval-layout">
      <aside className="eval-suites" aria-label="Saved evaluation suites"><div className="eval-section-heading"><h3>Suites</h3><button type="button" onClick={startNewSuite}>New suite</button></div>
        {suites.length === 0 ? <p className="eval-empty">No saved suites yet. Create a suite to define a repeatable check.</p> : suites.map((suite) => <button type="button" className={`eval-suite-option ${suite.id === selectedSuiteId ? 'selected' : ''}`} key={suite.id} onClick={() => setSelectedSuiteId(suite.id)}><strong>{suite.name}</strong><span>v{suite.version} · {suite.cases.length} cases</span></button>)}
        <div className="eval-section-heading eval-history-heading"><h3>Run history</h3><span>{runs.length}</span></div>
        {runs.length === 0 ? <p className="eval-empty">No runs recorded.</p> : runs.map((run) => <button type="button" className={`eval-run-option ${run.id === selectedRunId ? 'selected' : ''}`} key={run.id} onClick={() => setSelectedRunId(run.id)}><strong>{run.status}</strong><span>{run.suite_name} v{run.suite_version}</span><code>{run.id}</code></button>)}
      </aside>
      <div className="eval-main">
        <form className="eval-editor" onSubmit={(event) => void saveSuite(event)}>
          <div className="eval-section-heading"><div><p className="eval-kicker">Suite editor</p><h3>{selectedSuite ? `Edit ${selectedSuite.name} · next version` : 'Create a suite'}</h3></div>{selectedSuite && <span className="eval-version">Saved v{selectedSuite.version}</span>}</div>
          <p className="eval-privacy-note">Do not include passwords, API keys, tokens, or other secrets in agent prompts or evaluation cases. Secret detection is heuristic.</p>
          <label>Suite name<input value={suiteName} maxLength={100} required onChange={(event) => setSuiteName(event.target.value)} /></label>
          <div className="eval-two-columns"><label>Agent<select value={agentId} required onChange={(event) => setAgentId(event.target.value)}><option value="">Select an existing agent</option>{agents.map((agent) => <option key={agent.id} value={agent.id}>{agent.config.name} · {agent.id}</option>)}</select></label><label>Confirmed Ollama model<select value={modelId} required onChange={(event) => setModelId(event.target.value)}><option value="">Select a discovered model</option>{models.map((model) => <option key={model.model_id} value={model.model_id}>{model.display_name || model.model_id}</option>)}</select></label></div>
          {agents.length === 0 && <p className="eval-prerequisite" role="status">Create an application agent before building a suite.</p>}
          {models.length === 0 && <p className="eval-prerequisite" role="status">No configured Ollama models are available. Runs are disabled until a model is discovered.</p>}
          <div className="eval-cases-heading"><h4>Cases ({cases.length}/10)</h4><button type="button" onClick={() => setCases((items) => [...items, { ...newCase(), name: `Case ${items.length + 1}` }])} disabled={cases.length >= 10}>Add case</button></div>
          {cases.map((item, index) => <fieldset className="eval-case" key={item.id}><legend>Case {index + 1}</legend><button className="eval-remove-case" type="button" onClick={() => setCases((items) => items.length > 1 ? items.filter((_, current) => current !== index) : items)} aria-label={`Remove case ${index + 1}`} disabled={cases.length === 1}>Remove</button><label>Case name<input value={item.name} maxLength={100} required onChange={(event) => updateCase(index, { name: event.target.value })} /></label><label>Prompt<textarea value={item.prompt} maxLength={4000} required rows={3} onChange={(event) => updateCase(index, { prompt: event.target.value })} /></label><div className="eval-two-columns"><label>Must include <small>One assertion per line, up to 8; each up to 240 characters</small><textarea value={item.must_include.join('\n')} rows={2} onChange={(event) => updateCase(index, { must_include: lines(event.target.value).slice(0, 8).map((value) => value.slice(0, 240)) })} /></label><label>Must not include <small>One assertion per line, up to 8; each up to 240 characters</small><textarea value={item.must_not_include.join('\n')} rows={2} onChange={(event) => updateCase(index, { must_not_include: lines(event.target.value).slice(0, 8).map((value) => value.slice(0, 240)) })} /></label></div></fieldset>)}
          <button className="eval-save" type="submit" disabled={saving || busy || cases.length < 1 || cases.length > 10 || !agentId || !suiteName.trim() || cases.some((item) => !item.prompt.trim() || !item.name.trim())}>{saving ? 'Saving suite…' : selectedSuite ? 'Save as new version' : 'Save suite'}</button>
        </form>
        <section className="eval-review" aria-labelledby="eval-review-title"><p className="eval-kicker">Review before inference</p><h3 id="eval-review-title">Run review</h3><dl><div><dt>Suite</dt><dd>{selectedSuite ? `${selectedSuite.name} v${selectedSuite.version}` : 'Save this suite first'}</dd></div><div><dt>Agent</dt><dd>{currentAgent?.config.name ?? 'Choose an agent'}</dd></div><div><dt>Effective model</dt><dd>{modelId || 'Choose a discovered model'}</dd></div><div><dt>Provider requests</dt><dd>{callCount} · one call per case</dd></div></dl><p>Run sends each saved prompt to Ollama Cloud. No calls are made while editing.</p><button className="eval-run-button" type="button" onClick={() => void runSuite()} disabled={!selectedSuite || busy || saving || !modelId || !modelBelongsToCatalog}>{busy ? 'Running evaluation…' : 'Run evaluation'}</button></section>
        {selectedRun && <section className="eval-results" aria-labelledby="eval-results-title"><p className="eval-kicker">Persisted run · {selectedRun.id}</p><h3 id="eval-results-title">{selectedRun.status} · {selectedRun.suite_name} v{selectedRun.suite_version}</h3><dl className="eval-run-identity"><div><dt>Agent</dt><dd>{selectedRun.agent_name} ({selectedRun.agent_id})</dd></div><div><dt>Model</dt><dd>{selectedRun.provider_id} · {selectedRun.model_id}</dd></div><div><dt>Config fingerprint</dt><dd><code>{selectedRun.agent_config_fingerprint}</code></dd></div><div><dt>Cases</dt><dd>{selectedRun.passed_cases} passed · {selectedRun.failed_cases} failed · {selectedRun.error_cases} errors</dd></div><div><dt>Cost</dt><dd>Not reported by provider</dd></div></dl>{selectedRun.cases.map((result) => <article className="eval-result-case" key={result.case_id}><h4>{result.status} · {result.name}</h4><p>{result.duration_ms} ms{result.error_code ? ` · ${result.error_code}` : ''}</p><ul>{result.checks.map((check, index) => <li key={`${check.name}-${index}`}><strong>{check.passed ? 'PASS' : 'FAIL'}</strong> · {check.name}: {check.detail}</li>)}</ul>{result.answer_preview && <details><summary>Answer preview</summary><pre>{result.answer_preview}</pre></details>}<p>LocalTrace: {result.trace.trace_id ? <code>{result.trace.trace_id}</code> : result.trace.trace_state || 'unavailable'}</p>{result.trace.jaeger_trace_id && result.trace.jaeger_url && <a href={result.trace.jaeger_url} target="_blank" rel="noreferrer">Open confirmed trace {result.trace.jaeger_trace_id} in Jaeger</a>}</article>)}</section>}
      </div>
    </div>
  </section>
}
