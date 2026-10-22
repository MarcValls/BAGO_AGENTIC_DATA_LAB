import assert from 'node:assert/strict'
import { after, afterEach, describe, it } from 'node:test'
import { JSDOM } from 'jsdom'
import { createServer } from 'vite'

const dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://localhost/' })
Object.assign(globalThis, { window: dom.window, document: dom.window.document, HTMLElement: dom.window.HTMLElement, Node: dom.window.Node, Event: dom.window.Event, MouseEvent: dom.window.MouseEvent, getComputedStyle: dom.window.getComputedStyle, requestAnimationFrame: (callback) => setTimeout(callback, 0), cancelAnimationFrame: (id) => clearTimeout(id), IS_REACT_ACT_ENVIRONMENT: true })
Object.defineProperty(globalThis, 'navigator', { configurable: true, value: dom.window.navigator })
const server = await createServer({ server: { middlewareMode: true }, appType: 'custom' })
const React = await import('react')
const { act, cleanup, fireEvent, render, screen } = await import('@testing-library/react')
const { default: OntologyReview } = await server.ssrLoadModule('/src/components/OntologyReview.tsx')

const proposal = { proposal_id: 'batch-01', source: { path: 'docs/map.md', sha256: 'a'.repeat(64) }, entities: [{ id: 'entity-a', label: 'A' }], relations: [{ proposal_id: 'rel-01', type: 'depends_on', source_id: 'entity-a', target_id: 'entity-b', evidence: { source_path: 'docs/map.md', source_sha256: 'a'.repeat(64), line_number: 7, line: 'A depends on B.' }, validator: { status: 'PASS', reason: null } }, { proposal_id: 'rel-invalid', type: 'links_to', source_id: 'A', target_id: 'C', evidence: { line_number: 8, line: 'A links C.' }, validator: { status: 'FAIL', reason: 'Unsupported relation.' } }], receipt: { receipt_id: 'proposal-receipt' }, trace: { trace_id: 'proposal-trace' } }
const approval = { accepted_ids: ['rel-01'], graph_fingerprint: 'graph-fp-1', receipt: { receipt_id: 'approval-receipt' }, trace: { trace_id: 'approval-trace' } }
const queryResult = { query: 'How is A related to B?', paths: [{ nodes: ['A', 'B'] }], inferred: [{ rule: 'transitive_path' }], contradictions: [], evidence_refs: [{ source_path: 'docs/map.md', source_sha256: 'a'.repeat(64), line_number: 7, line: 'A depends on B.', proposal_id: 'rel-01' }], graph_fingerprint: 'graph-fp-1', receipt: { receipt_id: 'query-receipt' }, trace: { trace_id: 'query-trace' } }
const response = (body, status = 200) => ({ ok: status >= 200 && status < 300, status, json: async () => body })
function fillSource() { fireEvent.change(screen.getByLabelText('Relation source file path'), { target: { value: 'docs/map.md' } }) }
function stubFetch(run) { const previous = globalThis.fetch; const calls = []; globalThis.fetch = async (url, init = {}) => { calls.push({ url: String(url), init }); return run(url, init) }; return { calls, restore: () => { globalThis.fetch = previous } } }
async function propose() { fillSource(); fireEvent.click(screen.getByRole('button', { name: 'Read source and propose relations' })); return Promise.race([screen.findByRole('region', { name: 'Relation proposal review' }), screen.findByRole('alert')]) }

afterEach(() => cleanup())
after(async () => { await server.close(); dom.window.close() })

describe('Local graph proposal and review UI', () => {
  it('does not read automatically and requires explicit source selection and submission', () => {
    const stub = stubFetch(async () => response(proposal))
    try { render(React.createElement(OntologyReview)); assert.equal(stub.calls.length, 0); assert.equal(screen.getByRole('button', { name: 'Read source and propose relations' }).disabled, true); assert.equal(screen.queryByRole('button', { name: 'Approve selected exact proposal IDs' }), null) } finally { stub.restore() }
  })
  it('renders exact evidence and validator state and does not auto-approve proposals', async () => {
    const stub = stubFetch(async () => response(proposal))
    try {
      render(React.createElement(OntologyReview)); await propose()
      assert.deepEqual(JSON.parse(stub.calls[0].init.body), { path: 'docs/map.md' })
      assert.equal(stub.calls[0].url, '/api/ontology/proposals')
      assert.ok(screen.getByText('a'.repeat(64))); assert.ok(screen.getByText(/line 7: A depends on B\./)); assert.ok(screen.getByText('PASS')); assert.ok(screen.getByText(/Unsupported relation/))
      assert.equal(screen.getByRole('button', { name: 'Approve selected exact proposal IDs' }).disabled, true)
      assert.equal(screen.getByLabelText('Select proposal rel-invalid').disabled, true)
      assert.equal(stub.calls.length, 1)
    } finally { stub.restore() }
  })
  it('sends only the explicitly selected exact proposal ID, then renders accepted receipt and query evidence', async () => {
    const stub = stubFetch(async (url) => url.includes('/approve') ? response(approval) : url.endsWith('/query') ? response(queryResult) : response(proposal))
    try {
      render(React.createElement(OntologyReview)); await propose()
      fireEvent.click(screen.getByLabelText('Select proposal rel-01'))
      fireEvent.click(screen.getByRole('button', { name: 'Approve selected exact proposal IDs' }))
      assert.equal(stub.calls[1].url, '/api/ontology/proposals/batch-01/approve')
      assert.deepEqual(JSON.parse(stub.calls[1].init.body), { proposal_ids: ['rel-01'] })
      assert.ok(await screen.findByRole('region', { name: 'Accepted graph state' })); assert.match(screen.getByRole('region', { name: 'Accepted graph state' }).textContent, /approval-receipt/); assert.ok(screen.getByText('graph-fp-1'))
      fireEvent.change(screen.getByLabelText('Graph question'), { target: { value: 'How is A related to B?' } })
      fireEvent.click(screen.getByRole('button', { name: 'Query graph' }))
      assert.ok(await screen.findByRole('region', { name: 'Graph query result' })); const resultText = screen.getByRole('region', { name: 'Graph query result' }).textContent; assert.match(resultText, /query-receipt/); assert.match(resultText, /query-trace/); assert.match(resultText, /docs\/map\.md/); assert.match(resultText, /transitive_path/)
    } finally { stub.restore() }
  })
  it('shows empty proposal response and rejects incomplete records without synthesizing accepted state', async () => {
    const stub = stubFetch(async () => response({ ...proposal, relations: [] }))
    try { render(React.createElement(OntologyReview)); await propose(); assert.match(screen.getByRole('status').textContent, /no relation proposals/i); assert.equal(screen.getByRole('button', { name: 'Approve selected exact proposal IDs' }).disabled, true) } finally { stub.restore() }
    cleanup()
    const incomplete = stubFetch(async () => response({ proposal_id: 'batch' }))
    try { render(React.createElement(OntologyReview)); await propose(); assert.match(screen.getByRole('alert').textContent, /incomplete proposal record/i); assert.equal(screen.queryByRole('region', { name: 'Relation proposal review' }), null) } finally { incomplete.restore() }
  })
  it('does not claim acceptance when returned IDs differ from the exact selection', async () => {
    const stub = stubFetch(async (url) => url.includes('/approve') ? response({ ...approval, accepted_ids: ['rel-other'] }) : response(proposal))
    try { render(React.createElement(OntologyReview)); await propose(); fireEvent.click(screen.getByLabelText('Select proposal rel-01')); fireEvent.click(screen.getByRole('button', { name: 'Approve selected exact proposal IDs' })); assert.match((await screen.findByRole('alert')).textContent, /did not match the exact IDs selected/i); assert.equal(screen.queryByRole('region', { name: 'Accepted graph state' }), null) } finally { stub.restore() }
  })
  it('reports unsupported and service errors without success state', async () => {
    for (const [status, expected] of [[404, /not supported by this backend/i], [503, /graph store unavailable/i]]) {
      const stub = stubFetch(async () => response({ detail: status === 404 ? 'missing' : { message: 'graph store unavailable' } }, status))
      try { render(React.createElement(OntologyReview)); fillSource(); fireEvent.click(screen.getByRole('button', { name: 'Read source and propose relations' })); assert.match((await screen.findByRole('alert')).textContent, expected); assert.equal(screen.queryByRole('region', { name: 'Relation proposal review' }), null) } finally { stub.restore(); cleanup() }
    }
  })
})
