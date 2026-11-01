import assert from 'node:assert/strict'
import { after, afterEach, describe, it } from 'node:test'
import { readFileSync } from 'node:fs'
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
const { cleanup, fireEvent, render, screen, within } = await import('@testing-library/react')
const { default: CapabilityManager } = await server.ssrLoadModule('/src/components/CapabilityManager.tsx')
const { setLocale } = await server.ssrLoadModule('/src/i18n/index.ts')
setLocale('en')

const jsonResponse = (body) => ({ ok: true, status: 200, json: async () => body })
const capability = (id) => ({
  id, name: id, provider: 'local', effect: 'READ', status: 'AVAILABLE', integration: 'CONNECTED',
  summary: `${id} summary`, limits: {}, source_fingerprints: {}, source_available: true, fingerprint: 'a'.repeat(64),
})

async function mountCatalog(ids) {
  const calls = []
  const original = globalThis.fetch
  globalThis.fetch = async (input, init = {}) => {
    const url = String(input)
    calls.push({ url, method: init.method ?? 'GET' })
    if (url === '/api/capabilities') return jsonResponse({ capabilities: ids.map(capability) })
    if (url === '/api/capabilities/proposals?status=all&limit=100') return jsonResponse({ proposals: [] })
    throw new Error(`Unexpected request: ${url}`)
  }
  render(React.createElement(CapabilityManager))
  await screen.findByRole('tablist')
  return { calls, restore: () => { globalThis.fetch = original } }
}

afterEach(() => cleanup())
after(async () => { await server.close(); dom.window.close() })

describe('Capability Manager category tabs', () => {
  it('shows All, six counted categories and Uncategorized; keyboard navigation preserves every entry once', async () => {
    const stub = await mountCatalog(['document_inventory', 'workspace.read_text', 'agent.run', 'development_read', 'delivery_review', 'mcp.execute', 'vendor.future'])
    try {
      const tablist = screen.getByRole('tablist', { name: 'Capabilities' })
      const all = within(tablist).getByRole('tab', { name: 'All (7)' })
      const documents = within(tablist).getByRole('tab', { name: 'Documents (1)' })
      assert.equal(within(tablist).getAllByRole('tab').length, 8) // All, six stable groups, and Uncategorized
      assert.equal(all.getAttribute('aria-selected'), 'true')
      assert.equal(within(screen.getByRole('tabpanel')).getAllByRole('article').length, 7) // one card per returned capability
      assert.deepEqual(
        Array.from(screen.getByRole('tabpanel').querySelectorAll('.capability-card-heading code')).map((item) => item.textContent),
        ['document_inventory', 'workspace.read_text', 'agent.run', 'development_read', 'delivery_review', 'mcp.execute', 'vendor.future'],
      )
      assert.ok(within(tablist).getByRole('tab', { name: 'Files and workspace (1)' }))
      assert.ok(within(tablist).getByRole('tab', { name: 'Agents and evaluation (1)' }))
      assert.ok(within(tablist).getByRole('tab', { name: 'BAGO5 development (1)' }))
      assert.ok(within(tablist).getByRole('tab', { name: 'Review and delivery (1)' }))
      assert.ok(within(tablist).getByRole('tab', { name: 'Connections and execution (1)' }))
      const uncategorized = within(tablist).getByRole('tab', { name: 'Uncategorized (1)' })
      assert.equal(uncategorized.getAttribute('aria-selected'), 'false')

      documents.focus()
      fireEvent.keyDown(documents, { key: 'ArrowRight' })
      const workspace = within(tablist).getByRole('tab', { name: 'Files and workspace (1)' })
      assert.equal(document.activeElement, workspace)
      assert.equal(workspace.getAttribute('aria-selected'), 'true')
      assert.match(screen.getByRole('tabpanel').textContent, /workspace\.read_text/)
      fireEvent.keyDown(workspace, { key: 'Home' })
      assert.equal(all.getAttribute('aria-selected'), 'true')
      fireEvent.keyDown(all, { key: 'End' })
      assert.equal(uncategorized.getAttribute('aria-selected'), 'true')
      assert.deepEqual(stub.calls.map((call) => call.url), ['/api/capabilities', '/api/capabilities/proposals?status=all&limit=100'])
    } finally { stub.restore() }
  })

  it('keeps quick options before the tab content and uses them to switch the selected panel', async () => {
    const stub = await mountCatalog(['document_inventory', 'mcp.execute'])
    try {
      const quickNav = screen.getByRole('navigation', { name: 'Quick options' })
      const quickDetails = quickNav.closest('details')
      const tabs = screen.getByRole('tablist')
      assert.ok(quickDetails)
      assert.ok(quickDetails.compareDocumentPosition(tabs) & Node.DOCUMENT_POSITION_FOLLOWING)
      fireEvent.click(within(quickNav).getByRole('button', { name: 'Connections and execution' }))
      assert.equal(within(tabs).getByRole('tab', { name: 'Connections and execution (1)' }).getAttribute('aria-selected'), 'true')
      assert.match(screen.getByRole('tabpanel').textContent, /mcp\.execute/)
      assert.deepEqual(stub.calls.map((call) => call.method), ['GET', 'GET'])
    } finally { stub.restore() }
  })

  it('shows a clear empty state for the always-visible uncategorized category', async () => {
    const stub = await mountCatalog(['document_inventory'])
    try {
      const tablist = screen.getByRole('tablist')
      const uncategorized = within(tablist).getByRole('tab', { name: 'Uncategorized (0)' })
      fireEvent.click(uncategorized)
      assert.equal(uncategorized.getAttribute('aria-selected'), 'true')
      assert.match(screen.getByRole('tabpanel').textContent, /There are no capabilities in Uncategorized/)
    } finally { stub.restore() }
  })

  it('does not position the quick menu over viewport content', () => {
    const css = readFileSync(new URL('../../../src/components/CapabilityManager.css', import.meta.url), 'utf8')
    assert.match(css, /\.capability-quick-menu\s*\{\s*position:\s*static/)
    assert.doesNotMatch(css, /\.capability-quick-menu\s*\{[^}]*position:\s*fixed/s)
    assert.doesNotMatch(css, /\.capability-manager:has\(\.capability-quick-menu/)
  })
})

