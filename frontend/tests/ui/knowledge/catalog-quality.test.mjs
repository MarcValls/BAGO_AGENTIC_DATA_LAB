import assert from 'node:assert/strict'
import { after, afterEach, describe, it } from 'node:test'
import { JSDOM } from 'jsdom'
import { createServer } from 'vite'

const dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://localhost/' })
Object.assign(globalThis, { window: dom.window, document: dom.window.document, HTMLElement: dom.window.HTMLElement, Node: dom.window.Node, Event: dom.window.Event, MouseEvent: dom.window.MouseEvent, getComputedStyle: dom.window.getComputedStyle, requestAnimationFrame: callback => setTimeout(callback, 0), cancelAnimationFrame: id => clearTimeout(id), IS_REACT_ACT_ENVIRONMENT: true })
Object.defineProperty(globalThis, 'navigator', { configurable: true, value: dom.window.navigator })
const server = await createServer({ server: { middlewareMode: true }, appType: 'custom' })
const React = await import('react')
const { act, cleanup, fireEvent, render, screen } = await import('@testing-library/react')
const { default: CatalogQuality } = await server.ssrLoadModule('/src/components/CatalogQuality.tsx')
const {setLocale} = await server.ssrLoadModule('/src/i18n/index.ts')
setLocale('en') // Explicit English expectation; product default remains Spanish.


const status = { state: 'healthy', configured: true, healthy: true, service_kind: 'local_openmetadata' }
const receipts = [
  { label: 'search', receipt_id: 'om-search-1', operation: 'search', decision: 'ALLOW', outcome: 'SUCCESS', result_count: 2, error_kind: null, path: '/api/v1/search/query' },
  { label: 'lineage readback', receipt_id: 'om-lineage-1', operation: 'get_lineage', decision: 'ALLOW', outcome: 'SUCCESS', result_count: 1, error_kind: null, path: '/api/v1/lineage' },
  { label: 'owner patch', receipt_id: 'om-owner-1', operation: 'assign_ownership', decision: 'ALLOW', outcome: 'SUCCESS', result_count: 1, error_kind: null, path: '/api/v1/tables' },
  { label: 'schema version', receipt_id: 'om-schema-1', operation: 'register_schema_version', decision: 'ALLOW', outcome: 'SUCCESS', result_count: 1, error_kind: null, path: '/api/v1/tables' },
  { label: 'quality rule definition', receipt_id: 'om-quality-1', operation: 'create_quality_rule', decision: 'ALLOW', outcome: 'SUCCESS', result_count: 1, error_kind: null, path: '/api/v1/dataQuality/testCases' },
  { label: 'transport denial', receipt_id: 'om-denied-1', operation: 'write', decision: 'REQUIRE_HUMAN', outcome: 'FAILURE', result_count: 0, error_kind: 'approval_required', path: '/api/v1/tables' },
]
const result = { run_id: 'catalog-run-1', status: 'PASS', checks: ['search', 'lineage', 'owner', 'schema', 'quality', 'governance'].map(name => ({ name, status: 'PASS', detail: `${name} verified` })), receipts, cleanup_requested: true, cleanup_status: 'PASS', error: null, service_kind: 'local_openmetadata' }
const response = (body, statusCode = 200) => ({ ok: statusCode >= 200 && statusCode < 300, status: statusCode, json: async () => body })
function stubFetch(run) {
  const previous = globalThis.fetch
  const calls = []
  globalThis.fetch = async (url, init = {}) => { calls.push({ url: String(url), init }); return run(url, init) }
  return { calls, restore: () => { globalThis.fetch = previous } }
}
const flush = () => act(async () => { await new Promise(resolve => setTimeout(resolve, 0)) })

afterEach(() => cleanup())
after(async () => { await server.close(); dom.window.close() })

describe('Local OpenMetadata catalog-quality route', () => {
  it('checks health only on mount; no catalog write starts before explicit confirmation', async () => {
    const stub = stubFetch(async url => url.endsWith('/status') ? response(status) : response(result))
    try {
      render(React.createElement(CatalogQuality)); await flush()
      assert.deepEqual(stub.calls.map(call => call.url), ['/api/catalog/openmetadata/status'])
      const button = screen.getByRole('button', { name: 'Run local OpenMetadata catalog check' })
      assert.equal(button.disabled, true)
      fireEvent.click(button)
      assert.equal(stub.calls.some(call => call.init.method === 'POST'), false)
      fireEvent.click(screen.getByLabelText(/I confirm running validation/))
      fireEvent.click(button)
      assert.equal(stub.calls.filter(call => call.init.method === 'POST').length, 1)
      assert.deepEqual(JSON.parse(stub.calls.find(call => call.init.method === 'POST').init.body), { confirm_run: true })
    } finally { stub.restore() }
  })

  it('renders all API checks, exact receipts, pretransport denial and cleanup state', async () => {
    const stub = stubFetch(async url => url.endsWith('/status') ? response(status) : response(result))
    try {
      render(React.createElement(CatalogQuality)); await flush()
      fireEvent.click(screen.getByLabelText(/I confirm running validation/))
      fireEvent.click(screen.getByRole('button', { name: 'Run local OpenMetadata catalog check' }))
      assert.ok(await screen.findByRole('region', { name: 'Catalog validation result' }))
      for (const label of ['search', 'lineage', 'owner', 'schema', 'quality', 'governance']) assert.ok(screen.getByText(label, { exact: true }))
      for (const receipt of receipts) assert.ok(screen.getByText(receipt.receipt_id))
      assert.ok(screen.getByText('REQUIRE_HUMAN'))
      assert.ok(screen.getAllByText('PASS', { exact: true }).length >= 1)
      assert.match(document.querySelector('.catalog-quality-limit').textContent, /does not start continuous/i)
    } finally { stub.restore() }
  })

  it('distinguishes an unconfigured service and prevents running the live route', async () => {
    const stub = stubFetch(async () => response({ state: 'unavailable', configured: false, healthy: false, service_kind: 'local_openmetadata' }))
    try {
      render(React.createElement(CatalogQuality)); await flush()
      assert.match(screen.getByRole('status').textContent, /not configured or unavailable/i)
      fireEvent.click(screen.getByLabelText(/I confirm running validation/))
      assert.equal(screen.getByRole('button', { name: 'Run local OpenMetadata catalog check' }).disabled, true)
      assert.equal(stub.calls.some(call => call.init.method === 'POST'), false)
    } finally { stub.restore() }
  })

  it('shows service errors and validation errors without a success record', async () => {
    const unavailable = stubFetch(async () => response({ detail: { message: 'health unavailable' } }, 503))
    try {
      render(React.createElement(CatalogQuality));
      assert.match((await screen.findByRole('alert')).textContent, /health unavailable/)
      assert.equal(screen.queryByRole('region', { name: 'Catalog validation result' }), null)
    } finally { unavailable.restore() }
    cleanup()
    const failed = stubFetch(async url => url.endsWith('/status') ? response(status) : response({ detail: { message: 'validation failed safely' } }, 503))
    try {
      render(React.createElement(CatalogQuality)); await flush()
      fireEvent.click(screen.getByLabelText(/I confirm running validation/)); fireEvent.click(screen.getByRole('button', { name: 'Run local OpenMetadata catalog check' }))
      assert.match((await screen.findByRole('alert')).textContent, /validation failed safely/)
      assert.equal(screen.queryByRole('region', { name: 'Catalog validation result' }), null)
    } finally { failed.restore() }
  })

  it('marks cleanup failure explicitly even when individual checks returned', async () => {
    const failedCleanup = { ...result, status: 'FAIL', cleanup_status: 'PARTIAL' }
    const stub = stubFetch(async url => url.endsWith('/status') ? response(status) : response(failedCleanup))
    try {
      render(React.createElement(CatalogQuality)); await flush()
      fireEvent.click(screen.getByLabelText(/I confirm running validation/)); fireEvent.click(screen.getByRole('button', { name: 'Run local OpenMetadata catalog check' }))
      assert.ok(await screen.findByRole('alert'))
      assert.match(document.querySelector('.catalog-quality-result').textContent, /PARTIAL/)
      assert.match(document.querySelector('.catalog-quality-result').textContent, /Cleanup was not confirmed/i)
    } finally { stub.restore() }
  })
})
