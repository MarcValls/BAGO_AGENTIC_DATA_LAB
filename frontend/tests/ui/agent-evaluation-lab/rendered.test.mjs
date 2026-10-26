import assert from 'node:assert/strict'
import { after, afterEach, describe, it } from 'node:test'
import { JSDOM } from 'jsdom'
import { createServer } from 'vite'

const dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://localhost/' })
Object.assign(globalThis, {
  window: dom.window,
  document: dom.window.document,
  HTMLElement: dom.window.HTMLElement,
  Node: dom.window.Node,
  Event: dom.window.Event,
  MouseEvent: dom.window.MouseEvent,
  getComputedStyle: dom.window.getComputedStyle,
  requestAnimationFrame: (callback) => setTimeout(callback, 0),
  cancelAnimationFrame: (id) => clearTimeout(id),
  IS_REACT_ACT_ENVIRONMENT: true,
})
Object.defineProperty(globalThis, 'navigator', { configurable: true, value: dom.window.navigator })

const server = await createServer({ server: { middlewareMode: true }, appType: 'custom' })
const React = await import('react')
const testing = await import('@testing-library/react')
const { cleanup, fireEvent, render, screen, waitFor } = testing
const { default: AgentEvaluationLab } = await server.ssrLoadModule('/src/components/AgentEvaluationLab.tsx')
const {setLocale,t} = await server.ssrLoadModule('/src/i18n/index.ts')
setLocale('en') // Explicit English expectation; product default remains Spanish.

const { default: AgentRunner } = await server.ssrLoadModule('/src/components/AgentRunner.tsx')

const suite = {
  id: 'evalsuite_demo', name: 'Response contract', agent_id: 'agent_1234abcd', version: 1, revision: 1,
  cases: [{ id: 'case_greeting', name: 'Greeting', prompt: 'Say hello', must_include: ['hello'], must_not_include: ['password'] }],
  created_at: '2026-10-10T10:00:00Z', updated_at: '2026-10-10T10:00:00Z',
}
const agent = { id: suite.agent_id, config: { name: 'Support agent', provider_id: 'ollama-cloud', model_id: 'retired-model' } }
const model = { provider_id: 'ollama-cloud', model_id: 'gemma4:31b-cloud', display_name: 'Gemma 4 Cloud', source: 'configured-provider', availability_confidence: 'listed' }
const traceResult = {
  case_id: 'case_greeting', name: 'Greeting', status: 'PASS', checks: [{ name: 'required: hello', passed: true, detail: 'Found required text.' }],
  answer_preview: 'Hello there.', duration_ms: 77,
  trace: { trace_id: 'local-trace-abc', trace_state: 'saved', jaeger_trace_id: 'jaeger-123', jaeger_url: 'http://localhost:16686/trace/jaeger-123' },
}
const run = {
  id: 'evalrun_demo', suite_id: suite.id, suite_version: 1, suite_name: suite.name, agent_id: agent.id, agent_name: agent.config.name,
  agent_config_fingerprint: 'sha256:config-fingerprint', provider_id: 'ollama-cloud', model_id: model.model_id, status: 'PASS', total_cases: 1,
  passed_cases: 1, failed_cases: 0, error_cases: 0, duration_ms: 77, started_at: '2026-10-10T10:01:00Z', completed_at: '2026-10-10T10:01:01Z', cases: [traceResult],
}

function jsonResponse(body, status = 200) {
  return { ok: status >= 200 && status < 300, status, json: async () => body }
}
function standardFetch(overrides = {}) {
  let runs = [...(overrides.runs ?? [])]
  return async (input, init) => {
    const url = String(input)
    if (overrides.failureUrl === url) return jsonResponse({ detail: { message: overrides.failureMessage ?? 'Service unavailable.' } }, overrides.failureStatus ?? 503)
    if (init?.method === 'POST' && url.endsWith('/run')) { runs = [run, ...runs]; return jsonResponse({ run }) }
    if (url === '/api/agents/list') return jsonResponse({ agents: overrides.agents ?? [agent] })
    if (url === '/api/providers/ollama/models') return jsonResponse({ models: overrides.models ?? [model] })
    if (url === '/api/providers/ollama/status') return jsonResponse({ state: overrides.providerState ?? 'ready', model_id: overrides.verifiedModelId ?? model.model_id })
    if (url === '/api/evaluations/suites') return jsonResponse({ suites: overrides.suites ?? [suite] })
    if (url.startsWith('/api/evaluations/runs')) return jsonResponse({ runs })
    throw new Error(`Unexpected request: ${url}`)
  }
}
const fetchRestorers = []
function stubFetch(fetcher) {
  const original = globalThis.fetch
  globalThis.fetch = fetcher
  let restored = false
  const restore = () => { if (!restored) { globalThis.fetch = original; restored = true } }
  fetchRestorers.push(restore)
  return restore
}
const getByButtonName = (pattern) => screen.getByRole('button', { name: pattern })

afterEach(() => { cleanup(); for (const restore of fetchRestorers.splice(0)) restore() })
after(async () => { await server.close(); dom.window.close() })

describe('Agent Evaluation Lab rendered behavior', () => {
  it('shows loading state while inventory discovery is pending', async () => {
    let releaseAgents
    const restore = stubFetch((input) => {
      const url = String(input)
      if (url === '/api/agents/list') return new Promise((resolve) => { releaseAgents = resolve })
      if (url === '/api/providers/ollama/models') return Promise.resolve(jsonResponse({ models: [model] }))
      if (url === '/api/providers/ollama/status') return Promise.resolve(jsonResponse({ state: 'ready', model_id: model.model_id }))
      if (url === '/api/evaluations/suites') return Promise.resolve(jsonResponse({ suites: [suite] }))
      return Promise.resolve(jsonResponse({ runs: [] }))
    })
    render(React.createElement(AgentEvaluationLab))
    assert.match(screen.getByRole('status').textContent, /Loading evaluation workspace/)
    releaseAgents(jsonResponse({ agents: [agent] }))
    await screen.findByText('Select a suite or run')
    assert.equal(screen.queryByText('Loading evaluation workspace.'), null)
    restore()
  })

  it('renders empty inventory and history without invented data', async () => {
    const restore = stubFetch(standardFetch({ agents: [], models: [], suites: [], runs: [] }))
    render(React.createElement(AgentEvaluationLab))
    await screen.findByText('Select a suite or run')
    // Empty suite state intentionally has no instructional placeholder.
    assert.equal(screen.queryByText(/No saved suites yet/), null)
    assert.equal(document.querySelector('.eval-suites .eval-empty'), null)
    assert.ok(screen.getByText('No runs recorded.'))
    assert.equal(screen.queryByLabelText('Suite name'), null)
    assert.equal(screen.queryByRole('button', { name: 'Run evaluation' }), null)
    fireEvent.click(getByButtonName('New suite'))
    assert.ok(screen.getByText('Create a suite'))
    assert.ok(screen.getByText(/No verified Ollama model is available/))
    assert.equal(getByButtonName('Save suite').disabled, true)
    const panel = screen.getByLabelText('Saved evaluation suites')
    const content = panel.querySelector('#eval-suites-content')
    const toggle = getByButtonName('Collapse suites and run history')
    fireEvent.click(toggle)
    assert.equal(toggle.getAttribute('aria-expanded'), 'false')
    assert.equal(content.hidden, true)
    assert.ok(panel.classList.contains('is-collapsed'))
    assert.ok(panel.parentElement.classList.contains('suites-collapsed'))
    const expand = getByButtonName('Expand suites and run history')
    fireEvent.click(expand)
    assert.equal(expand.getAttribute('aria-expanded'), 'true')
    assert.equal(content.hidden, false)
    assert.ok(screen.getByText('No runs recorded.'))
    restore()
  })

  it('shows unavailable service and retry for a missing evaluation endpoint', async () => {
    const restore = stubFetch(standardFetch({ failureUrl: '/api/evaluations/suites', failureStatus: 404, failureMessage: 'Evaluation service not found.' }))
    render(React.createElement(AgentEvaluationLab))
    await screen.findByText('Evaluation service unavailable')
    assert.ok(screen.getByText(/Evaluation service not found./))
    assert.ok(getByButtonName('Retry'))
    restore()
  })

  it('renders a failed discovery request as an explicit alert', async () => {
    const restore = stubFetch(standardFetch({ failureUrl: '/api/agents/list', failureMessage: 'Agent inventory unavailable.' }))
    render(React.createElement(AgentEvaluationLab))
    assert.match((await screen.findByRole('alert')).textContent, /Agent inventory unavailable/)
    restore()
  })

  it('preselects only the verified model and does not inherit an agent model that is unverified', async () => {
    const restore = stubFetch(standardFetch())
    render(React.createElement(AgentEvaluationLab))
    fireEvent.click(await screen.findByRole('button', { name: /Response contract/ }))
    await waitFor(() => assert.ok(screen.getByText('Support agent', { selector: 'dd' })))
    const runButton = getByButtonName('Run evaluation')
    assert.equal(screen.getByLabelText('Verified Ollama model').value, model.model_id)
    assert.equal(screen.getByText(/Effective model/).parentElement.textContent.includes(model.model_id), true)
    assert.equal(runButton.disabled, false)
    restore()
  })

  it('loads persisted suite values into the editor and saves edits with the expected revision', async () => {
    let savedSuite = { ...suite, cases: suite.cases.map((item) => ({ ...item, must_include: [...item.must_include], must_not_include: [...item.must_not_include] })) }
    let updateRequest
    let runCalls = 0
    const restore = stubFetch(async (input, init) => {
      const url = String(input)
      if (init?.method === 'POST' && url.endsWith('/run')) { runCalls += 1; return jsonResponse({ run }) }
      if (init?.method === 'PUT') {
        updateRequest = { url, body: JSON.parse(init.body) }
        savedSuite = { ...savedSuite, name: updateRequest.body.name, version: 2, revision: 2, cases: updateRequest.body.cases }
        return jsonResponse({ suite: savedSuite })
      }
      if (url === '/api/agents/list') return jsonResponse({ agents: [agent] })
      if (url === '/api/providers/ollama/models') return jsonResponse({ models: [model] })
      if (url === '/api/providers/ollama/status') return jsonResponse({ state: 'ready', model_id: model.model_id })
      if (url === '/api/evaluations/suites') return jsonResponse({ suites: [savedSuite] })
      if (url.startsWith('/api/evaluations/runs')) return jsonResponse({ runs: [] })
      throw new Error(`Unexpected request: ${url}`)
    })
    render(React.createElement(AgentEvaluationLab))
    fireEvent.click(await screen.findByRole('button', { name: /Response contract/ }))
    assert.equal(screen.queryByLabelText('Suite name'), null)
    assert.ok(screen.getByText(/Provider requests/).parentElement.textContent.includes('1'))
    assert.ok(screen.getByText(/Effective model/).parentElement.textContent.includes('gemma4:31b-cloud'))
    assert.equal(getByButtonName('Run evaluation').disabled, false)
    fireEvent.click(getByButtonName('Edit suite'))
    assert.equal(screen.getByLabelText('Suite name').value, suite.name)
    assert.equal(screen.getByLabelText('Prompt').value, 'Say hello')
    assert.equal(screen.getByLabelText(/Must include/).value, 'hello')
    assert.equal(screen.getByLabelText('Verified Ollama model').value, model.model_id)
    assert.equal(screen.queryByRole('button', { name: 'Run evaluation' }), null)
    assert.equal(runCalls, 0, 'suite review must not start inference')
    fireEvent.change(screen.getByLabelText('Suite name'), { target: { value: 'Response contract revised' } })
    fireEvent.change(screen.getByLabelText('Prompt'), { target: { value: 'Say hello in one sentence' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save as new version' }))
    await waitFor(() => assert.equal(updateRequest?.body.expected_revision, suite.revision))
    assert.equal(updateRequest.url, `/api/evaluations/suites/${suite.id}`)
    assert.equal(updateRequest.body.name, 'Response contract revised')
    assert.equal(updateRequest.body.cases[0].prompt, 'Say hello in one sentence')
    assert.deepEqual(updateRequest.body.cases[0].must_include, ['hello'])
    await screen.findByText('Response contract revised v2')
    assert.equal(screen.queryByLabelText('Suite name'), null)
    restore()
  })

  it('opens the editor explicitly and hides it when browsing saved runs', async () => {
    const calls = []
    const backend = standardFetch({ runs: [run] })
    const restore = stubFetch(async (input, init) => { calls.push([String(input), init]); return backend(input, init) })
    render(React.createElement(AgentEvaluationLab))
    await screen.findByText('Select a suite or run')
    fireEvent.click(getByButtonName('New suite'))
    assert.ok(screen.getByLabelText('Suite name'))
    fireEvent.click(getByButtonName(/PASS.*Response contract/))
    await screen.findByRole('heading', { name: /Passed \(PASS\) · Response contract v1/ })
    assert.equal(screen.queryByLabelText('Suite name'), null)
    assert.equal(screen.queryByRole('heading', { name: 'Run review' }), null)
    fireEvent.click(getByButtonName(/Response contract.*1 cases/))
    assert.ok(screen.getByRole('heading', { name: 'Run review' }))
    assert.equal(screen.queryByRole('heading', { name: /Passed \(PASS\) · Response contract v1/ }), null)
    fireEvent.click(getByButtonName('Edit suite'))
    fireEvent.change(screen.getByLabelText('Suite name'), { target: { value: 'Unsaved change' } })
    fireEvent.click(getByButtonName('Cancel'))
    assert.ok(screen.getByText('Response contract v1', { selector: 'dd' }))
    fireEvent.click(getByButtonName('Edit suite'))
    assert.equal(screen.getByLabelText('Suite name').value, suite.name)
    assert.equal(calls.some(([, init]) => init?.method === 'POST' || init?.method === 'PUT'), false)
    restore()
  })

  it('calls the provider only after Run and renders saved LocalTrace and confirmed Jaeger identity', async () => {
    const calls = []
    const backend = standardFetch()
    const restore = stubFetch(async (input, init) => {
      calls.push([String(input), init])
      return backend(input, init)
    })
    render(React.createElement(AgentEvaluationLab))
    fireEvent.click(await screen.findByRole('button', { name: /Response contract/ }))
    assert.equal(screen.getByLabelText('Verified Ollama model').value, model.model_id)
    const runButton = getByButtonName('Run evaluation')
    await waitFor(() => assert.equal(runButton.disabled, false))
    assert.equal(calls.some(([url]) => url.endsWith('/run')), false)
    fireEvent.click(runButton)
    await screen.findByRole('heading', { name: /Passed \(PASS\) · Response contract v1/ })
    assert.ok(screen.getByText('local-trace-abc'))
    const link = screen.getByRole('link', { name: /Open confirmed trace jaeger-123/ })
    assert.equal(link.href, 'http://localhost:16686/trace/jaeger-123')
    assert.equal(calls.filter(([url]) => url.endsWith('/run')).length, 1)
    restore()
  })

  it('does not fabricate a Jaeger link when the run has only LocalTrace identity', async () => {
    const noJaegerRun = { ...run, cases: [{ ...traceResult, trace: { trace_id: 'local-only', trace_state: 'saved' } }] }
    let savedRuns = []
    const restore = stubFetch(async (input, init) => {
      const url = String(input)
      if (init?.method === 'POST' && url.endsWith('/run')) { savedRuns = [noJaegerRun]; return jsonResponse({ run: noJaegerRun }) }
      if (url === '/api/agents/list') return jsonResponse({ agents: [agent] })
      if (url === '/api/providers/ollama/models') return jsonResponse({ models: [model] })
      if (url === '/api/providers/ollama/status') return jsonResponse({ state: 'ready', model_id: model.model_id })
      if (url === '/api/evaluations/suites') return jsonResponse({ suites: [suite] })
      if (url.startsWith('/api/evaluations/runs')) return jsonResponse({ runs: savedRuns })
      throw new Error(`Unexpected request: ${url}`)
    })
    render(React.createElement(AgentEvaluationLab))
    fireEvent.click(await screen.findByRole('button', { name: /Response contract/ }))
    assert.equal(screen.getByLabelText('Verified Ollama model').value, model.model_id)
    fireEvent.click(await screen.findByRole('button', { name: 'Run evaluation' }))
    await screen.findByText('local-only')
    assert.equal(screen.queryByRole('link', { name: /Jaeger/ }), null)
    restore()
  })

  it('labels a provisional trace ID as unsaved after LocalTrace persistence fails', async () => {
    const failedTraceRun = {
      ...run,
      status: 'FAIL',
      failed_cases: 1,
      cases: [{
        ...traceResult,
        status: 'FAIL',
        checks: [{ name: 'trace_local_saved', passed: false, detail: 'LocalTrace persistence failed.' }],
        trace: { trace_id: 'provisional-trace-456', trace_state: 'local_trace_failed' },
      }],
    }
    const restore = stubFetch(standardFetch({ runs: [failedTraceRun] }))
    render(React.createElement(AgentEvaluationLab))
    fireEvent.click(await screen.findByRole('button', { name: /FAIL.*Response contract/ }))
    await screen.findByText('LocalTrace not saved.')
    assert.ok(screen.getByText('provisional-trace-456'))
    assert.match(screen.getByText(/Provisional trace ID/).textContent, /not persisted/)
    assert.equal(screen.queryByText(/LocalTrace saved:/), null)
    assert.equal(screen.queryByRole('link', { name: /Jaeger/ }), null)
    restore()
  })

  it('renders an ERROR run as provider execution failure, distinct from assertion failure', async () => {
    const errorRun = {
      ...run,
      id: 'evalrun_error',
      status: 'ERROR',
      passed_cases: 0,
      failed_cases: 0,
      error_cases: 1,
      cases: [{
        ...traceResult,
        status: 'ERROR',
        error_code: 'provider_unavailable',
        checks: [],
        answer_preview: '',
        trace: { trace_state: 'unavailable' },
      }],
    }
    const restore = stubFetch(standardFetch({ runs: [errorRun] }))
    render(React.createElement(AgentEvaluationLab))
    fireEvent.click(await screen.findByRole('button', { name: /ERROR.*Response contract/ }))
    await screen.findByText('Evaluation run error')
    assert.match(screen.getAllByRole('alert')[0].textContent, /provider or execution error/i)
    assert.ok(screen.getByText(/No deterministic assertion result is available/))
    assert.equal(screen.queryByText(/FAIL · required:/), null)
    restore()
  })
})

describe('Agent Runner P1-02 rendered regression', () => {
  it('requires a selected profile and explicit task before a governed run can start', async () => {
    const restore = stubFetch(async () => jsonResponse({ agents: [{ id: agent.id, config: { name: 'Read only reviewer', description: 'Audit', type: 'tool', system_prompt: 'review', tools: [] } }] }))
    try {
      render(React.createElement(AgentRunner))
      const runButton = await screen.findByRole('button', { name: 'Start task' })
      assert.equal(runButton.disabled, true)
      assert.equal(screen.queryByText(/Run unavailable/), null)
      assert.equal(screen.queryByText(/legacy SandboxManager/), null)
    } finally { restore() }
  })

  it('downloads the JSON export with a JSON filename', async () => {
    const requested = []
    const restoreFetch = stubFetch(async (input) => {
      const url = String(input)
      requested.push(url)
      if (url === '/api/agents/list') return jsonResponse({ agents: [] })
      if (url === '/api/agents/export') return { ok: true, blob: async () => new Blob(['{}'], { type: 'application/json' }) }
      throw new Error(`Unexpected request: ${url}`)
    })
    const originalCreateObjectURL = URL.createObjectURL
    const originalRevokeObjectURL = URL.revokeObjectURL
    const originalAnchorClick = window.HTMLAnchorElement.prototype.click
    let downloadedFilename = ''
    URL.createObjectURL = () => 'blob:agent-export'
    URL.revokeObjectURL = () => {}
    window.HTMLAnchorElement.prototype.click = function () { downloadedFilename = this.download }

    try {
      render(React.createElement(AgentRunner))
      fireEvent.click(await screen.findByRole('button', { name: 'Export all agents' }))
      await waitFor(() => assert.equal(downloadedFilename, 'agents-export.json'))
      assert.ok(requested.includes('/api/agents/export'))
    } finally {
      URL.createObjectURL = originalCreateObjectURL
      URL.revokeObjectURL = originalRevokeObjectURL
      window.HTMLAnchorElement.prototype.click = originalAnchorClick
      restoreFetch()
    }
  })
})
