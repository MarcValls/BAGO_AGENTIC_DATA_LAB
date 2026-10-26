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

const server = await createServer({ server: { middlewareMode: true, hmr: false }, appType: 'custom' })
const React = await import('react')
const { act, cleanup, fireEvent, render, screen, within } = await import('@testing-library/react')
const { default: CapabilityManager } = await server.ssrLoadModule('/src/components/CapabilityManager.tsx')
const {setLocale} = await server.ssrLoadModule('/src/i18n/index.ts')
setLocale('en')

const proposals = { proposals: [] }
const mcpCapability = {
  id: 'mcp.execute', name: 'MCP execution', provider: 'local', effect: 'EXECUTE',
  status: 'MODULE_PRESENT_NOT_CONNECTED', integration: 'MODULE_PRESENT_NOT_CONNECTED',
  summary: 'Connection is not currently available.', limits: {}, source_fingerprints: {},
  source_available: true, fingerprint: 'a'.repeat(64),
}
const jsonResponse = (body, status = 200) => ({ ok: status >= 200 && status < 300, status, json: async () => body })

function stubFetch({ capabilities = [] } = {}) {
  const original = globalThis.fetch
  const calls = []
  globalThis.fetch = async (input, init = {}) => {
    const url = String(input)
    calls.push({ url, method: init.method ?? 'GET', body: init.body })
    if (url === '/api/capabilities') return jsonResponse({ capabilities })
    if (url === '/api/capabilities/proposals?status=all&limit=100') return jsonResponse(proposals)
    throw new Error(`Unexpected request: ${url}`)
  }
  return { calls, restore: () => { globalThis.fetch = original } }
}

afterEach(() => cleanup())
after(async () => { await server.close(); dom.window.close() })

describe('Capability Manager MCP connection route', () => {
  it('renders the catalog loading state and truthful empty state without demo controls', async () => {
    let releaseCatalog
    const original = globalThis.fetch
    const calls = []
    globalThis.fetch = async (input, init = {}) => {
      const url = String(input)
      calls.push({ url, method: init.method ?? 'GET' })
      if (url === '/api/capabilities') return new Promise((resolve) => { releaseCatalog = resolve })
      if (url === '/api/capabilities/proposals?status=all&limit=100') return jsonResponse(proposals)
      throw new Error(`Unexpected request: ${url}`)
    }
    try {
      render(React.createElement(CapabilityManager))
      assert.ok(screen.getByText(/Loading capability catalog and proposals/))
      await act(async () => releaseCatalog(jsonResponse({ capabilities: [] })))
      assert.ok(await screen.findByText('No capability records were returned by the backend.'))
      assert.ok(screen.getByText(/No saved proposals/))
      assert.equal(screen.queryByRole('button', { name: /fixture|demonstration/i }), null)
      assert.equal(screen.queryByRole('heading', { name: 'Local MCP fixture' }), null)
      assert.ok(calls.every((call) => call.method === 'GET' && !call.url.includes('/demo/')))
    } finally { globalThis.fetch = original }
  })

  it('lists the actual MCP capability and exposes configuration and quick options without executing it', async () => {
    const stub = stubFetch({ capabilities: [mcpCapability] })
    const destinations = []
    try {
      render(React.createElement(CapabilityManager, { onNavigate: (destination) => destinations.push(destination) }))
      await screen.findByText('mcp.execute')
      assert.ok(screen.getAllByText(/MODULE_PRESENT_NOT_CONNECTED/).length >= 1)
      const quickOptions = screen.getByRole('navigation', { name: 'Quick options' })
      assert.ok(within(quickOptions).getByRole('button', { name: 'Connections and execution' }))
      const capabilityCard = screen.getByRole('article')
      fireEvent.click(within(capabilityCard).getByRole('button', { name: 'External connections' }))
      assert.deepEqual(destinations, ['connections'])
      assert.equal(stub.calls.some((call) => call.url.startsWith('/api/connections')), false)
      assert.deepEqual(stub.calls.map((call) => call.url), ['/api/capabilities', '/api/capabilities/proposals?status=all&limit=100'])
      assert.ok(stub.calls.every((call) => call.method === 'GET' && !call.url.includes('/demo/')))
      assert.equal(screen.queryByRole('button', { name: /Run local MCP fixture/ }), null)
    } finally { stub.restore() }
  })

  it('surfaces catalog errors with retry and makes no transport request', async () => {
    const original = globalThis.fetch
    const calls = []
    globalThis.fetch = async (input, init = {}) => {
      const url = String(input)
      calls.push({ url, method: init.method ?? 'GET' })
      if (url === '/api/capabilities') return jsonResponse({ detail: { message: 'Capability service unavailable.' } }, 503)
      if (url === '/api/capabilities/proposals?status=all&limit=100') return jsonResponse(proposals)
      throw new Error(`Unexpected request: ${url}`)
    }
    try {
      render(React.createElement(CapabilityManager))
      assert.match((await screen.findByRole('alert')).textContent, /Capability service unavailable/)
      assert.ok(screen.getByRole('button', { name: 'Reload' }))
      assert.ok(calls.every((call) => call.method === 'GET' && !call.url.includes('/demo/')))
    } finally { globalThis.fetch = original }
  })
})
