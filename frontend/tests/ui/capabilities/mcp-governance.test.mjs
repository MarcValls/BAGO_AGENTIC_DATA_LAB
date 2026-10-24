import assert from 'node:assert/strict'
import { after, afterEach, describe, it } from 'node:test'
import { JSDOM } from 'jsdom'
import { createServer } from 'vite'

const dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://localhost/' })
Object.assign(globalThis, {
  window: dom.window, document: dom.window.document, HTMLElement: dom.window.HTMLElement,
  Node: dom.window.Node, Event: dom.window.Event, MouseEvent: dom.window.MouseEvent,
  getComputedStyle: dom.window.getComputedStyle,
  requestAnimationFrame: (callback) => setTimeout(callback, 0),
  cancelAnimationFrame: (id) => clearTimeout(id), IS_REACT_ACT_ENVIRONMENT: true,
})
Object.defineProperty(globalThis, 'navigator', { configurable: true, value: dom.window.navigator })

const server = await createServer({ server: { middlewareMode: true }, appType: 'custom' })
const React = await import('react')
const { act, cleanup, fireEvent, render, screen, waitFor } = await import('@testing-library/react')
const { default: CapabilityManager } = await server.ssrLoadModule('/src/components/CapabilityManager.tsx')
const {setLocale,t} = await server.ssrLoadModule('/src/i18n/index.ts')
setLocale('en') // Explicit English expectation; product default remains Spanish.


const catalog = { capabilities: [] }
const proposals = { proposals: [] }
const fixture = {
  run_id: 'mcp_demo_test_1', status: 'completed', transport: 'stdio', source_kind: 'repository_local_fixture', server: 'bago-local-demo',
  discovered: [
    { name: 'get_lab_status', fingerprint: 'sha256:read-tool' },
    { name: 'propose_lab_note', fingerprint: 'sha256:write-tool' },
  ],
  registered: [
    { name: 'get_lab_status', effect_type: 'READ' },
    { name: 'propose_lab_note', effect_type: 'WRITE' },
  ],
  read_call: {
    receipt_id: 'mcp_receipt_read_1', decision: 'ALLOW', actual_effect: { called: true },
    receipt: { receipt_id: 'mcp_receipt_read_1', request_id: 'request_read_1', decision: 'ALLOW', outcome: 'SUCCESS', actual_effect: { called: true } },
  },
  write_call: {
    receipt_id: 'mcp_receipt_write_1', decision: 'REQUIRE_HUMAN', actual_effect: { called: false },
    receipt: { receipt_id: 'mcp_receipt_write_1', request_id: 'request_write_1', decision: 'REQUIRE_HUMAN', outcome: 'BLOCKED', actual_effect: { called: false } },
  },
  trace: { trace_id: 'trace_mcp_test_1', events: [{ event_id: 'event_read_1' }, { event_id: 'event_write_denied_1' }] },
  evidence: { path: '.bago/traces/mcp-governance/mcp_demo_test_1.json', sha256: 'a'.repeat(64) },
}

const jsonResponse = (body, status = 200) => ({ ok: status >= 200 && status < 300, status, json: async () => body })
function stubFetch({ run = async () => jsonResponse(fixture) } = {}) {
  const original = globalThis.fetch
  const calls = []
  globalThis.fetch = async (input, init = {}) => {
    const url = String(input)
    calls.push({ url, method: init.method ?? 'GET', body: init.body })
    if (url === '/api/connections') return jsonResponse({ connections: [] })
    if (url === '/api/capabilities') return jsonResponse(catalog)
    if (url === '/api/capabilities/proposals?status=all&limit=100') return jsonResponse(proposals)
    if (url === '/api/demo/mcp-governance') return run(url, init)
    throw new Error(`Unexpected request: ${url}`)
  }
  return { calls, restore: () => { globalThis.fetch = original } }
}

afterEach(() => cleanup())
after(async () => { await server.close(); dom.window.close() })

describe('Capability Manager local MCP governance route', () => {
  it('renders the catalog loading state and then a truthful empty state', async () => {
    let releaseCatalog
    const original = globalThis.fetch
    globalThis.fetch = async (input) => {
      const url = String(input)
      if (url === '/api/connections') return jsonResponse({ connections: [] })
      if (url === '/api/capabilities') return new Promise((resolve) => { releaseCatalog = resolve })
      if (url === '/api/capabilities/proposals?status=all&limit=100') return jsonResponse(proposals)
      throw new Error(`Unexpected request: ${url}`)
    }
    try {
      render(React.createElement(CapabilityManager))
      assert.ok(screen.getByText(/Loading capability catalog and proposals/))
      await act(async () => releaseCatalog(jsonResponse(catalog)))
      assert.ok(await screen.findByText('No capability records were returned by the backend.'))
      assert.ok(screen.getByText(/No saved proposals/))
    } finally { globalThis.fetch = original }
  })

  it('scopes the local fixture and exposes external configuration without implicit transport calls', async () => {
    const stub = stubFetch()
    try {
      render(React.createElement(CapabilityManager))
      const button = await screen.findByRole('button', { name: 'Run local MCP fixture' })
      assert.match(screen.getByText(/This demonstration starts only/).textContent, /External connections/)
      assert.ok(screen.getByRole('heading', { name: 'External connections' }))
      assert.equal(stub.calls.some((call) => call.method !== 'GET'), false)
      assert.equal(stub.calls.some((call) => call.url === '/api/demo/mcp-governance'), false)
      assert.equal(button.disabled, false)
    } finally { stub.restore() }
  })

  it('shows an accessible loading state only after the user starts the fixed fixture', async () => {
    let release
    const stub = stubFetch({ run: () => new Promise((resolve) => { release = resolve }) })
    try {
      render(React.createElement(CapabilityManager))
      fireEvent.click(await screen.findByRole('button', { name: 'Run local MCP fixture' }))
      assert.ok(await screen.findByText(/Running the local MCP fixture and recording its observed calls/))
      assert.equal(screen.getByRole('button', { name: 'Running local fixture…' }).disabled, true)
      const request = stub.calls.find((call) => call.url === '/api/demo/mcp-governance')
      assert.equal(request.method, 'POST')
      assert.deepEqual(JSON.parse(request.body), {})
      await act(async () => release(jsonResponse(fixture)))
      assert.ok(await screen.findByRole('region', { name: 'Local MCP fixture result' }))
    } finally { stub.restore() }
  })

  it('renders discovered effects, actual READ/WRITE transport states, receipts, trace and evidence', async () => {
    const stub = stubFetch()
    try {
      render(React.createElement(CapabilityManager))
      fireEvent.click(await screen.findByRole('button', { name: 'Run local MCP fixture' }))
      assert.ok(await screen.findByText(/The READ call reached MCP; the WRITE call was denied before transport/))
      assert.ok(screen.getByText('get_lab_status'))
      assert.ok(screen.getByText('propose_lab_note'))
      assert.ok(screen.getByText('Effect: READ'))
      assert.ok(screen.getByText('Effect: WRITE'))
      assert.ok(screen.getByText('mcp_receipt_read_1'))
      assert.ok(screen.getByText('mcp_receipt_write_1'))
      assert.ok(screen.getByText('trace_mcp_test_1'))
      assert.ok(screen.getByText(/\.bago\/traces\/mcp-governance\/mcp_demo_test_1\.json/))
      assert.ok(screen.getByText('a'.repeat(64)))
      fireEvent.click(screen.getByText('Inspect READ receipt'))
      assert.ok(screen.getByText(/"outcome": "SUCCESS"/))
      fireEvent.click(screen.getByText('Inspect WRITE receipt'))
      assert.ok(screen.getByText(/"outcome": "BLOCKED"/))
      assert.equal(stub.calls.filter((call) => call.url === '/api/demo/mcp-governance').length, 1)
    } finally { stub.restore() }
  })

  it('reports request errors and malformed or unsafe outcomes without claiming success', async () => {
    const errorStub = stubFetch({ run: async () => jsonResponse({ detail: { message: 'Local fixture unavailable.' } }, 503) })
    try {
      render(React.createElement(CapabilityManager))
      fireEvent.click(await screen.findByRole('button', { name: 'Run local MCP fixture' }))
      assert.match((await screen.findByRole('alert')).textContent, /Local fixture unavailable/)
      assert.equal(screen.queryByRole('status', { name: /READ call reached MCP/ }), null)
    } finally { errorStub.restore(); cleanup() }

    const badStub = stubFetch({ run: async () => jsonResponse({ ...fixture, write_call: { ...fixture.write_call, actual_effect: { called: true } } }) })
    try {
      render(React.createElement(CapabilityManager))
      fireEvent.click(await screen.findByRole('button', { name: 'Run local MCP fixture' }))
      assert.ok(await screen.findByText(/required policy is not demonstrated/i))
      assert.equal(screen.queryByText(/The READ call reached MCP; the WRITE call was denied before transport/), null)
    } finally { badStub.restore() }
  })
})
