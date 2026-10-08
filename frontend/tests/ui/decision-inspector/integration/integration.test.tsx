import { strict as assert } from 'node:assert'
import { test } from 'node:test'
import { renderToString } from 'react-dom/server'
import { decisionInspectorModel, DecisionInspector, type DecisionInspectorArtifacts } from '../../../../src/features/decision-inspector/integration/DecisionInspector'

const artifacts: DecisionInspectorArtifacts = {
  summary: { status: 'PASS' },
  agent_run: {
    run_id: 'run-demo-17',
    status: 'COMPLETED',
    query: 'What source supports this decision?',
    answer: 'The source says the operation completed.',
    citations: ['policy.md#revision=2'],
    retrieval: { hits: [{ chunk_id: 'chunk-7', document_id: 'policy', evidence: { citation: 'policy.md#revision=2', source_uri: 'policy.md', revision: '2' } }] },
    proposals: [{ proposal_id: 'action-3', request_id: 'request-3', tool_name: 'lookup', decision: 'REQUIRE_HUMAN' }],
    decision_receipts: [],
    mcp_receipts: [],
  },
  receipts: {},
  trace: {
    trace_id: 'trace-demo-17',
    run_id: 'run-demo-17',
    events: [{ event_id: 'event-1', trace_id: 'trace-demo-17', sequence: 0, name: 'agent.run', kind: 'workflow', status: 'SUCCESS', attributes: {}, evidence_refs: [] }],
  },
  evaluation: {},
}

test('maps source identifiers, retrieval evidence and trace without manufacturing claim links', () => {
  const model = decisionInspectorModel(artifacts)
  assert.equal(model.conclusion?.id, 'run-demo-17')
  assert.equal(model.conclusion?.claims.length, 0)
  assert.equal(model.evidence[0]?.artifactRef, 'policy.md#revision=2')
  assert.equal(model.evidence[0]?.snapshot?.revision, '2')
  assert.equal(model.evidence[0]?.freshness, 'unknown')
  assert.equal(model.timeline?.traceId, 'trace-demo-17')
  assert.equal(model.timeline?.jaegerCorrelation, 'unavailable')
  assert.equal(model.actions.actions[0]?.id, 'action-3')
})

test('does not create a stable conclusion identity without a source run id', () => {
  const model = decisionInspectorModel({ ...artifacts, agent_run: { answer: 'An answer without source identity.' } })
  assert.equal(model.conclusion, undefined)
})

test('rejects a foreign-run receipt even when receipt and request identifiers collide', () => {
  const model = decisionInspectorModel({ ...artifacts, agent_run: {
    run_id: 'run-demo-17',
    proposals: [{ proposal_id: 'action-3', request_id: 'request-collision', receipt_id: 'receipt-collision', called: true, outcome: 'SUCCESS' }],
    decision_receipts: [{ run_id: 'run-foreign-99', receipt_id: 'receipt-collision', request_id: 'request-collision', execution_outcome: 'SUCCESS' }],
  } })
  const action = model.actions.actions[0]
  assert.equal(action?.receiptLink.state, 'missing')
  assert.equal(action?.receiptLink.receipt, undefined)
  assert.equal(action?.execution.state, 'unverified')
})

test('does not associate a receipt without explicit source run identity', () => {
  const model = decisionInspectorModel({ ...artifacts, agent_run: {
    run_id: 'run-demo-17',
    proposals: [{ proposal_id: 'action-3', request_id: 'request-collision', receipt_id: 'receipt-collision', called: true, outcome: 'SUCCESS' }],
    mcp_receipts: [{ receipt_id: 'receipt-collision', request_id: 'request-collision', execution_outcome: 'SUCCESS' }],
    provider_receipt: { receipt_id: 'receipt-collision', request_id: 'request-collision', execution_outcome: 'SUCCESS' },
  } })
  const action = model.actions.actions[0]
  assert.equal(action?.receiptLink.state, 'missing')
  assert.equal(action?.receiptLink.receipt, undefined)
  assert.equal(action?.execution.state, 'unverified')
})

test('renders the integrated inspector with readable navigation and source answer', () => {
  const html = renderToString(<DecisionInspector artifacts={artifacts} />)
  assert.match(html, /Decision Inspector/)
  assert.match(html, /What source supports this decision\?/)
  assert.match(html, /The source says the operation completed\./)
  assert.match(html, /aria-label="Inspector views"/)
  assert.match(html, /Evidence/)
  assert.match(html, /Trace/)
  assert.match(html, /Actions/)
})
