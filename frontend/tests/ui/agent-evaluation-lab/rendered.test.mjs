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
      if (url === '/api/evaluations/suites') return Promise.resolve(jsonResponse({ suites: [suite] }))
      return Promise.resolve(jsonResponse({ runs: [] }))
    })
    render(React.createElement(AgentEvaluationLab))
    assert.match(screen.getByRole('status').textContent, /Loading evaluation workspace/)
    releaseAgents(jsonResponse({ agents: [agent] }))
    await screen.findByRole('heading', { name: 'Agent Evaluation Lab' })
    restore()
  })

  it('renders empty inventory and history without invented data', async () => {
    const restore = stubFetch(standardFetch({ agents: [], models: [], suites: [], runs: [] }))
    render(React.createElement(AgentEvaluationLab))
    await screen.findByText(/No saved suites yet/)
    assert.ok(screen.getByText('No runs recorded.'))
    assert.ok(screen.getByText(/Create an application agent/))
    assert.equal(getByButtonName('Run evaluation').disabled, true)
    restore()
  })

  it('shows unavailable service and retry for a missing evaluation endpoint', async () => {
    const restore = stubFetch(standardFetch({ failureUrl: '/api/evaluations/suites', failureStatus: 404, failureMessage: 'Evaluation service not found.' }))
    render(React.createElement(AgentEvaluationLab))
    await screen.findByText('Evaluation service unavailable')
    assert.ok(screen.getByText('Evaluation service not found.'))
    assert.ok(getByButtonName('Retry'))
    restore()
  })

  it('renders a failed discovery request as an explicit alert', async () => {
    const restore = stubFetch(standardFetch({ failureUrl: '/api/agents/list', failureMessage: 'Agent inventory unavailable.' }))
    render(React.createElement(AgentEvaluationLab))
    assert.match((await screen.findByRole('alert')).textContent, /Agent inventory unavailable/)
    restore()
  })

  it('keeps Run disabled for a stale model and enables it after selecting a discovered model', async () => {
    const restore = stubFetch(standardFetch())
    render(React.createElement(AgentEvaluationLab))
    fireEvent.click(await screen.findByRole('button', { name: /Response contract/ }))
    await waitFor(() => assert.ok(screen.getByText('Support agent', { selector: 'dd' })))
    const runButton = getByButtonName('Run evaluation')
    assert.equal(runButton.disabled, true)
    fireEvent.change(screen.getByLabelText('Confirmed Ollama model'), { target: { value: model.model_id } })
    await waitFor(() => assert.equal(runButton.disabled, false))
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
      if (url === '/api/evaluations/suites') return jsonResponse({ suites: [savedSuite] })
      if (url.startsWith('/api/evaluations/runs')) return jsonResponse({ runs: [] })
      throw new Error(`Unexpected request: ${url}`)
    })
    render(React.createElement(AgentEvaluationLab))
    fireEvent.click(await screen.findByRole('button', { name: /Response contract/ }))
    assert.equal(screen.getByLabelText('Suite name').value, suite.name)
    assert.equal(screen.getByLabelText('Prompt').value, 'Say hello')
    assert.equal(screen.getByLabelText(/Must include/).value, 'hello')
    fireEvent.change(screen.getByLabelText('Confirmed Ollama model'), { target: { value: model.model_id } })
    assert.ok(screen.getByText(/Provider requests/).parentElement.textContent.includes('1'))
    assert.ok(screen.getByText(/Effective model/).parentElement.textContent.includes('gemma4:31b-cloud'))
    assert.equal(getByButtonName('Run evaluation').disabled, false)
    assert.equal(runCalls, 0, 'suite review must not start inference')
    fireEvent.change(screen.getByLabelText('Suite name'), { target: { value: 'Response contract revised' } })
    fireEvent.change(screen.getByLabelText('Prompt'), { target: { value: 'Say hello in one sentence' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save as new version' }))
    await waitFor(() => assert.equal(updateRequest?.body.expected_revision, suite.revision))
    assert.equal(updateRequest.url, `/api/evaluations/suites/${suite.id}`)
    assert.equal(updateRequest.body.name, 'Response contract revised')
    assert.equal(updateRequest.body.cases[0].prompt, 'Say hello in one sentence')
    assert.deepEqual(updateRequest.body.cases[0].must_include, ['hello'])
    await screen.findByText('Saved v2')
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
    fireEvent.change(screen.getByLabelText('Confirmed Ollama model'), { target: { value: model.model_id } })
    const runButton = getByButtonName('Run evaluation')
    await waitFor(() => assert.equal(runButton.disabled, false))
    assert.equal(calls.some(([url]) => url.endsWith('/run')), false)
    fireEvent.click(runButton)
    await screen.findByRole('heading', { name: /PASS · Response contract v1/ })
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
      if (url === '/api/evaluations/suites') return jsonResponse({ suites: [suite] })
      if (url.startsWith('/api/evaluations/runs')) return jsonResponse({ runs: savedRuns })
      throw new Error(`Unexpected request: ${url}`)
    })
    render(React.createElement(AgentEvaluationLab))
    fireEvent.click(await screen.findByRole('button', { name: /Response contract/ }))
    fireEvent.change(screen.getByLabelText('Confirmed Ollama model'), { target: { value: model.model_id } })
    fireEvent.click(await screen.findByRole('button', { name: 'Run evaluation' }))
    await screen.findByText('local-only')
    assert.equal(screen.queryByRole('link', { name: /Jaeger/ }), null)
    restore()
  })
})

describe('Agent Runner P1-02 rendered regression', () => {
  it('keeps Run disabled and states that governed execution is unavailable', async () => {
    const restore = stubFetch(async () => jsonResponse({ agents: [{ id: agent.id, config: { name: 'Read only reviewer', description: 'Audit', type: 'tool', system_prompt: 'review', tools: [] } }] }))
    render(React.createElement(AgentRunner))
    const runButton = await screen.findByRole('button', { name: 'Run unavailable' })
    assert.equal(runButton.disabled, true)
    assert.match(screen.getByRole('status').textContent.toLowerCase(), /no governed execution capability is registered/)
    restore()
  })
})
