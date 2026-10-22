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
const { default: KnowledgeIngest } = await server.ssrLoadModule('/src/components/KnowledgeIngest.tsx')

const answer = {
  run_id: 'rag_run_01', status: 'answered',
  ingestion: { receipt_id: 'ingest_receipt_01', source_id: 'source_01', source_path: 'docs/guide.md', source_sha256: 'a'.repeat(64), source_revision: 'rev_2', index_fingerprint: 'index_sha256_01', chunk_count: 2, idempotent: false },
  retrieval: { query: 'What is the procedure?', index_fingerprint: 'index_sha256_01', eligible_count: 1, filtered_count: 1, hits: [{ rank: 1, chunk_id: 'chunk_01', document_id: 'doc_01', score: 0.9, evidence: { chunk_id: 'chunk_01', document_id: 'doc_01', source_uri: 'docs/guide.md', revision: 'rev_2', citation: 'The procedure has two steps.' } }], citations: [] },
  generation: { provider_id: 'ollama', model_id: 'test-model', answer: 'The procedure has two steps.' },
  trace: { trace_id: 'trace_rag_01', path: '.bago/traces/rag/trace_rag_01.json', sha256: 'b'.repeat(64) },
}
const response = (body, status = 200) => ({ ok: status >= 200 && status < 300, status, json: async () => body })
function fillForm() {
  fireEvent.change(screen.getByLabelText('Project-relative file path'), { target: { value: 'docs/guide.md' } })
  fireEvent.change(screen.getByLabelText('Question'), { target: { value: 'What is the procedure?' } })
}
function stubFetch(run) {
  const previous = globalThis.fetch
  const calls = []
  globalThis.fetch = async (url, init = {}) => { calls.push({ url: String(url), init }); return run(url, init) }
  return { calls, restore: () => { globalThis.fetch = previous } }
}

afterEach(() => cleanup())
after(async () => { await server.close(); dom.window.close() })

describe('Grounded local source route', () => {
  it('does not read/index before explicit submission and declares authority as user input', () => {
    const stub = stubFetch(async () => response(answer))
    try {
      render(React.createElement(KnowledgeIngest))
      assert.equal(stub.calls.length, 0)
      assert.match(document.querySelector('.knowledge-authority-note').textContent, /not independently checked/i)
      assert.equal(screen.getByLabelText('Declared source authority').value, 'PROPOSED')
    } finally { stub.restore() }
  })

  it('shows accessible loading, sends exactly the four contract fields and renders backend evidence verbatim', async () => {
    let release
    const stub = stubFetch(() => new Promise((resolve) => { release = resolve }))
    try {
      render(React.createElement(KnowledgeIngest))
      fillForm()
      fireEvent.change(screen.getByLabelText('Declared source authority'), { target: { value: 'VERIFIED' } })
      fireEvent.change(screen.getByLabelText('Minimum retrieval authority'), { target: { value: 'VERIFIED' } })
      fireEvent.click(screen.getByRole('button', { name: 'Index source and answer' }))
      assert.ok(await screen.findByRole('status'))
      const request = stub.calls[0]
      assert.equal(request.url, '/api/knowledge/ingest-and-answer')
      assert.equal(request.init.method, 'POST')
      assert.deepEqual(JSON.parse(request.init.body), { path: 'docs/guide.md', question: 'What is the procedure?', source_authority: 'VERIFIED', minimum_authority: 'VERIFIED' })
      await act(async () => release(response(answer)))
      assert.ok(await screen.findByRole('region', { name: 'Grounded retrieval result' }))
      assert.equal(screen.getAllByText('The procedure has two steps.').length, 2)
      assert.equal(screen.getAllByText('a'.repeat(64)).length, 2)
      assert.equal(screen.getAllByText('ingest_receipt_01').length, 2)
      assert.ok(screen.getByText('trace_rag_01'))
      assert.ok(screen.getByText('b'.repeat(64)))
    } finally { stub.restore() }
  })

  it('states no evidence without rendering an answer, and displays the receipt/trace if returned', async () => {
    const empty = { ...answer, status: 'no_evidence', generation: null, retrieval: { ...answer.retrieval, eligible_count: 0, filtered_count: 1, hits: [] } }
    const stub = stubFetch(async () => response(empty))
    try {
      render(React.createElement(KnowledgeIngest)); fillForm()
      fireEvent.click(screen.getByRole('button', { name: 'Index source and answer' }))
      assert.ok(await screen.findByRole('heading', { name: 'No eligible evidence' }))
      assert.equal(screen.queryByText('The procedure has two steps.'), null)
      assert.ok(screen.getByText('trace_rag_01'))
    } finally { stub.restore() }
  })

  it('reports unsupported and request errors without presenting a success result', async () => {
    const stub = stubFetch(async () => response({}, 404))
    try {
      render(React.createElement(KnowledgeIngest)); fillForm()
      fireEvent.click(screen.getByRole('button', { name: 'Index source and answer' }))
      assert.match((await screen.findByRole('alert')).textContent, /not supported by this backend/i)
      assert.equal(screen.queryByRole('region', { name: 'Grounded retrieval result' }), null)
    } finally { stub.restore() }

    cleanup()
    const failed = stubFetch(async () => response({ detail: { message: 'Model unavailable.' } }, 503))
    try {
      render(React.createElement(KnowledgeIngest)); fillForm()
      fireEvent.click(screen.getByRole('button', { name: 'Index source and answer' }))
      assert.match((await screen.findByRole('alert')).textContent, /Model unavailable/)
      assert.equal(screen.queryByRole('region', { name: 'Grounded retrieval result' }), null)
    } finally { failed.restore() }
  })

  it('rejects incomplete backend records instead of inventing citations or receipts', async () => {
    const stub = stubFetch(async () => response({ run_id: 'incomplete', status: 'answered', generation: { answer: 'unbound text' } }))
    try {
      render(React.createElement(KnowledgeIngest)); fillForm()
      fireEvent.click(screen.getByRole('button', { name: 'Index source and answer' }))
      assert.match((await screen.findByRole('alert')).textContent, /incomplete run record/i)
      assert.equal(screen.queryByText('unbound text'), null)
    } finally { stub.restore() }
  })
})
