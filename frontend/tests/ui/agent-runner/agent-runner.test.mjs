import assert from 'node:assert/strict'
import { after, afterEach, describe, it } from 'node:test'
import { JSDOM } from 'jsdom'
import { createServer } from 'vite'

const dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://localhost:5173/' })
Object.assign(globalThis, {
  window: dom.window,
  document: dom.window.document,
  HTMLElement: dom.window.HTMLElement,
  Node: dom.window.Node,
  Event: dom.window.Event,
  MouseEvent: dom.window.MouseEvent,
  getComputedStyle: dom.window.getComputedStyle,
  requestAnimationFrame: callback => setTimeout(callback, 0),
  cancelAnimationFrame: id => clearTimeout(id),
  IS_REACT_ACT_ENVIRONMENT: true,
})
Object.defineProperty(globalThis, 'navigator', { configurable: true, value: dom.window.navigator })

const server = await createServer({ server: { middlewareMode: true }, appType: 'custom' })
const React = await import('react')
const { act, cleanup, fireEvent, render, screen, waitFor } = await import('@testing-library/react')
const { default: AgentRunner } = await server.ssrLoadModule('/src/components/AgentRunner.tsx')
const agent = {
  id: 'agent_review_1',
  config: {
    name: 'Workspace reviewer', description: 'Review a bounded workspace change.', type: 'tool',
    system_prompt: 'Review carefully.', tools: ['sandbox.run'], provider_id: 'ollama-cloud', model_id: 'model-1',
  },
  created_at: '2026-10-19T00:00:00Z',
}

let currentSocket
class MockWebSocket {
  static OPEN = 1
  constructor(url) {
    this.url = url
    this.readyState = 0
    this.sent = []
    currentSocket = this
  }
  send(frame) { this.sent.push(JSON.parse(frame)) }
  open() { this.readyState = MockWebSocket.OPEN; this.onopen?.({ type: 'open' }) }
  message(frame) { this.onmessage?.({ data: JSON.stringify(frame) }) }
  close() { this.readyState = 3; this.onclose?.({ type: 'close' }) }
}
globalThis.WebSocket = MockWebSocket

function jsonResponse(value, ok = true) {
  return { ok, json: async () => value }
}

function stubAgentFetch({ agents = [agent], fail = false } = {}) {
  const original = globalThis.fetch
  globalThis.fetch = async url => {
    if (String(url) === '/api/agents/list') {
      if (fail) throw new Error('internal details must not reach the UI')
      return jsonResponse({ agents })
    }
    throw new Error(`Unexpected request: ${String(url)}`)
  }
  return () => { globalThis.fetch = original }
}

function receive(socket, frame) {
  act(() => socket.message(frame))
}

async function openProposalFlow() {
  render(React.createElement(AgentRunner))
  fireEvent.click(await screen.findByRole('button', { name: /Workspace reviewer/ }))
  fireEvent.change(screen.getByRole('textbox', { name: 'Task' }), { target: { value: 'Inspect the current workspace.' } })
  fireEvent.click(screen.getByRole('button', { name: 'Start task' }))
  await waitFor(() => assert.ok(currentSocket))
  assert.match(currentSocket.url, /^ws:\/\/localhost:8080\/ws\/agents\/run$/)
  act(() => currentSocket.open())
  await waitFor(() => assert.equal(currentSocket.sent.length, 1))
  assert.deepEqual(currentSocket.sent[0], { type: 'start', agent_id: agent.id, task: 'Inspect the current workspace.' })
  return currentSocket
}

function proposalFrame(overrides = {}) {
  return {
    type: 'proposal', run_id: 'run-adl-1', agent_id: agent.id, proposal_id: 'proposal-1',
    request_id: 'request-1', effect_id: 'filesystem.write', approval_required: true,
    target: { path: 'reports/review.txt' },
    arguments: { content: 'Reviewed content', expected_exists: false },
    operation_sha256: 'a'.repeat(64), world_state_digest: 'b'.repeat(64),
    expires_at: '2026-10-19T01:00:00Z', task_status: 'awaiting_review', effect_status: 'proposed',
    ...overrides,
  }
}

function completedFrame(overrides = {}) {
  return {
    type: 'completed', run_id: 'run-adl-1', proposal_id: 'proposal-1', request_id: 'request-1',
    effect_id: 'filesystem.write', task_status: 'effect_completed', effect_status: 'success',
    approval: { state: 'approved', request_id: 'request-1', decision_id: 'decision-1', proof_id: 'proof-1' },
    execution: { request_id: 'request-1', receipt_id: 'receipt-1', ber_execution_id: 'ber-exec-1', verified_success: true, authorization: { state: 'ALLOW', permit_id: 'permit-1' } },
    trace: {
      trace_id: 'trace-ber-1', run_id: 'ber-exec-1', events: [
        { event_id: 'event-1', sequence: 0, name: 'ber.effect.run', kind: 'WORKFLOW', status: 'SUCCESS' },
        { event_id: 'event-2', sequence: 1, name: 'ber.receipt', kind: 'RECEIPT', status: 'SUCCESS' },
      ],
    },
    ...overrides,
  }
}

afterEach(() => { cleanup(); currentSocket = undefined })
after(async () => { await server.close(); dom.window.close() })

describe('BER Agent Runner UI', () => {
  it('renders loading, empty and profile request error states', async () => {
    let resolveFetch
    const originalFetch = globalThis.fetch
    globalThis.fetch = () => new Promise(resolve => { resolveFetch = resolve })
    render(React.createElement(AgentRunner))
    assert.ok(await screen.findByRole('status'))
    await act(async () => resolveFetch(jsonResponse({ agents: [] })))
    assert.ok(await screen.findByText('No saved agent profiles were provided.'))
    cleanup()

    globalThis.fetch = async () => { throw new Error('private transport detail') }
    render(React.createElement(AgentRunner))
    assert.match((await screen.findByRole('alert')).textContent, /Agent profiles could not be loaded/)
    assert.doesNotMatch(screen.getByRole('alert').textContent, /private transport detail/)
    globalThis.fetch = originalFetch
  })

  it('renders the exact proposal before review and sends only proposal_id with the chosen decision', async () => {
    const restoreFetch = stubAgentFetch()
    try {
      const socket = await openProposalFlow()
      receive(socket, proposalFrame())
      assert.ok(await screen.findByRole('heading', { name: 'Review proposed action' }))
      assert.ok(screen.getByText(/reports\/review\.txt/))
      assert.ok(screen.getByText(/Reviewed content/))
      assert.equal(screen.queryByText('challenge-1'), null)
      fireEvent.click(screen.getByRole('button', { name: 'Approve proposal' }))
      await waitFor(() => assert.equal(socket.sent.length, 2))
      assert.deepEqual(socket.sent[1], { type: 'decision', proposal_id: 'proposal-1', decision: 'approve' })
      assert.equal(JSON.stringify(socket.sent[1]).includes('challenge_id'), false)
      assert.equal(JSON.stringify(socket.sent[1]).includes('content'), false)
      assert.ok(screen.getByText(/waiting for the BAGO authorization and execution outcome/i))
    } finally { restoreFetch() }
  })

  it('shows success only for completed, verified_success and exact proposal, request, effect and receipt identities', async () => {
    const restoreFetch = stubAgentFetch()
    try {
      const socket = await openProposalFlow()
      receive(socket, proposalFrame())
      await screen.findByRole('heading', { name: 'Review proposed action' })
      fireEvent.click(screen.getByRole('button', { name: 'Approve proposal' }))
      receive(socket, completedFrame())
      assert.ok(await screen.findByRole('heading', { name: 'Verified BER execution' }))
      assert.match(screen.getByRole('status').textContent, /identity-matched verified receipt/i)
      assert.ok(screen.getByText('receipt-1'))
      assert.equal(screen.getAllByText('ber-exec-1').length, 2)
      assert.ok(screen.getByRole('region', { name: 'LocalTrace projection' }))
      assert.match(screen.getByText(/ADL projection is observational/).textContent, /BAGO authorization and the BER receipt remain authoritative/)
    } finally { restoreFetch() }
  })

  it('downgrades completed frames with any mismatched ID to unverified and never renders success', async () => {
    const restoreFetch = stubAgentFetch()
    try {
      const socket = await openProposalFlow()
      receive(socket, proposalFrame())
      await screen.findByRole('heading', { name: 'Review proposed action' })
      fireEvent.click(screen.getByRole('button', { name: 'Approve proposal' }))
      receive(socket, completedFrame({ request_id: 'request-other' }))
      assert.ok(await screen.findByRole('heading', { name: 'Execution unverified' }))
      assert.match(screen.getByRole('status').textContent, /not success/i)
      assert.equal(screen.queryByRole('heading', { name: 'Verified BER execution' }), null)
    } finally { restoreFetch() }
  })

  it('requires the BAGO approval decision to match the prepared request when approval is required', async () => {
    const restoreFetch = stubAgentFetch()
    try {
      const socket = await openProposalFlow()
      receive(socket, proposalFrame())
      await screen.findByRole('heading', { name: 'Review proposed action' })
      fireEvent.click(screen.getByRole('button', { name: 'Approve proposal' }))
      receive(socket, completedFrame({ approval: { state: 'approved', request_id: 'other-request' } }))
      assert.ok(await screen.findByRole('heading', { name: 'Execution unverified' }))
      assert.equal(screen.queryByRole('heading', { name: 'Verified BER execution' }), null)
    } finally { restoreFetch() }
  })

  it('rejects a proposal frame that exposes a BAGO challenge identifier', async () => {
    const restoreFetch = stubAgentFetch()
    try {
      const socket = await openProposalFlow()
      receive(socket, proposalFrame({ challenge_id: 'secret-challenge' }))
      assert.match((await screen.findByRole('alert')).textContent, /proposal is incomplete/i)
      assert.equal(screen.queryByText('secret-challenge'), null)
      assert.equal(screen.queryByRole('button', { name: 'Approve proposal' }), null)
    } finally { restoreFetch() }
  })

  it('keeps rejection, cancellation, authorization denial and task answers distinct from success', async () => {
    const restoreFetch = stubAgentFetch()
    try {
      let socket = await openProposalFlow()
      receive(socket, proposalFrame())
      await screen.findByRole('heading', { name: 'Review proposed action' })
      fireEvent.click(screen.getByRole('button', { name: 'Reject proposal' }))
      assert.deepEqual(socket.sent[1], { type: 'decision', proposal_id: 'proposal-1', decision: 'reject' })
      receive(socket, { type: 'rejected', run_id: 'run-adl-1', proposal_id: 'proposal-1', request_id: 'request-1', effect_status: 'not_executed' })
      assert.ok(await screen.findByRole('heading', { name: 'Proposal rejected' }))
      assert.equal(screen.queryByRole('heading', { name: 'Verified BER execution' }), null)
    } finally { restoreFetch() }

    cleanup()
    const restoreFetch2 = stubAgentFetch()
    try {
      const socket = await openProposalFlow()
      receive(socket, proposalFrame())
      await screen.findByRole('heading', { name: 'Review proposed action' })
      fireEvent.click(screen.getByRole('button', { name: 'Cancel proposal' }))
      assert.deepEqual(socket.sent[1], { type: 'decision', proposal_id: 'proposal-1', decision: 'cancel' })
      receive(socket, { type: 'cancelled', run_id: 'run-adl-1', proposal_id: 'proposal-1', request_id: 'request-1', effect_status: 'not_executed' })
      assert.ok(await screen.findByRole('heading', { name: 'Proposal cancelled' }))
    } finally { restoreFetch2() }
  })

  it('renders authorization denial and provider-only task results as non-execution outcomes', async () => {
    const restoreFetch = stubAgentFetch()
    try {
      const socket = await openProposalFlow()
      receive(socket, proposalFrame())
      await screen.findByRole('heading', { name: 'Review proposed action' })
      fireEvent.click(screen.getByRole('button', { name: 'Approve proposal' }))
      receive(socket, { type: 'authorization_denied', run_id: 'run-adl-1', proposal_id: 'proposal-1', request_id: 'request-1', authorization: { state: 'DENY' }, effect_status: 'not_executed' })
      assert.ok(await screen.findByRole('heading', { name: 'Authorization denied' }))
    } finally { restoreFetch() }

    cleanup()
    const restoreFetch2 = stubAgentFetch()
    try {
      const socket = await openProposalFlow()
      receive(socket, { type: 'task_result', run_id: 'run-adl-1', task_status: 'answered', effect_status: 'not_started', answer: 'Read-only answer.' })
      assert.ok(await screen.findByRole('heading', { name: 'Task answer' }))
      assert.match(screen.getByRole('status').textContent, /without starting an effect/i)
      assert.equal(screen.queryByRole('heading', { name: 'Verified BER execution' }), null)
    } finally { restoreFetch2() }
  })

  it('renders backend errors as alerts without exposing exception details or falling back to sandbox', async () => {
    const restoreFetch = stubAgentFetch()
    try {
      const socket = await openProposalFlow()
      receive(socket, { type: 'error', code: 'runtime_unavailable', data: 'Pinned runtime is unavailable.' })
      const alert = await screen.findByRole('alert')
      assert.match(alert.textContent, /runtime_unavailable/)
      assert.match(alert.textContent, /Pinned runtime is unavailable/)
      assert.equal(screen.queryByText(/SandboxManager/i), null)
      assert.equal(socket.sent.length, 1)
    } finally { restoreFetch() }
  })
})
