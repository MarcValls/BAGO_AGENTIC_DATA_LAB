import { strict as assert } from 'node:assert'
import { test } from 'node:test'
import { renderToStaticMarkup } from 'react-dom/server'
import type { ActionInspectionBundle } from '../../../../src/contracts/action/action'
import { actionBundleFromAgentRun } from '../../../../src/adapters/action/agentRun'
import { ActionReview } from '../../../../src/features/decision-inspector/actions/ActionReview'

const bundle = actionBundleFromAgentRun({
  run_id: 'run-action-42',
  proposals: [
    { proposal_id: 'proposal-approved', request_id: 'req-ok', tool_name: 'read_file', effect_type: 'READ', decision: 'ALLOW', called: true, outcome: 'SUCCESS', receipt_id: 'receipt-ok', arguments: { path: 'report.txt' } },
    { proposal_id: 'proposal-denied', request_id: 'req-deny', tool_name: 'delete_file', effect_type: 'DELETE', decision: 'DENY', called: false, rationale: 'Policy denied request.' },
  ],
  decision_receipts: [{ receipt_id: 'receipt-ok', request_id: 'req-ok', permit_id: 'permit-1', execution_outcome: 'SUCCESS', evidence_refs: ['event-9'] }],
})

test('renders source-backed proposal lifecycle and matching receipt as distinct states', () => {
  const html = renderToStaticMarkup(<ActionReview bundle={bundle} />)
  for (const text of ['Proposed actions', 'run-action-42', 'proposal-approved', 'Proposed intent', 'Authorization', 'Authorized by recorded decision', 'Execution', 'succeeded', 'Matched receipt', 'receipt-ok', 'event-9', 'Inspect supplied arguments']) assert.ok(html.includes(text), `expected ${text}`)
  assert.match(html, /disabled[^>]*>Approve proposal/)
  assert.match(html, /No approval, rejection, or execution was submitted/)
})

test('shows denied authorization and declared but unavailable receipt without implying execution', () => {
  const html = renderToStaticMarkup(<ActionReview bundle={bundle} />)
  assert.match(html, /Rejected by recorded decision/)
  assert.match(html, /Receipt link unknown/)
  assert.match(html, /Call recorded: no/)
  assert.doesNotMatch(html, /Execution: succeeded/)
})

test('missing and mismatched receipts are explicit and success without a match stays unverified', () => {
  const missing = actionBundleFromAgentRun({ run_id: 'r', proposals: [{ proposal_id: 'p', request_id: 'q', decision: 'ALLOW', called: true, outcome: 'SUCCESS', receipt_id: 'declared' }] })
  const missingHtml = renderToStaticMarkup(<ActionReview bundle={missing} />)
  assert.match(missingHtml, /Receipt declared but unavailable/)
  assert.match(missingHtml, /The source reports success, but it is unverified/)
  const mismatch = actionBundleFromAgentRun({ run_id: 'r', proposals: [{ proposal_id: 'p', request_id: 'q', permit_id: 'permit-1', decision: 'ALLOW', called: true, outcome: 'SUCCESS' }], mcp_receipts: [{ receipt_id: 'other', request_id: 'q', permit_id: 'permit-2', execution_outcome: 'SUCCESS' }] })
  assert.match(renderToStaticMarkup(<ActionReview bundle={mismatch} />), /Receipt mismatch/)
})

test('loading, empty, error, unsupported and unknown states remain visible', () => {
  const html = [
    renderToStaticMarkup(<ActionReview state={{ status: 'loading' }} />),
    renderToStaticMarkup(<ActionReview bundle={{ schema: 'governed-action-bundle/v1', actions: [] }} />),
    renderToStaticMarkup(<ActionReview state={{ status: 'error', message: 'Action source failed' }} />),
    renderToStaticMarkup(<ActionReview bundle={{ schema: 'unsupported' as ActionInspectionBundle['schema'], actions: [] }} />),
    renderToStaticMarkup(<ActionReview />),
  ].join('\n')
  for (const text of ['Loading run artifacts', 'This run has no proposed actions', 'Action source failed', 'unsupported', 'Action proposal data was not provided']) assert.ok(html.includes(text), `expected ${text}`)
})

