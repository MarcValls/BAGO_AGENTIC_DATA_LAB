import {setLocale,t} from '../../../../src/i18n'
import {beforeEach as beforeLocaleExpectation} from 'vitest'
beforeLocaleExpectation(() => setLocale('en'))
import { expect, test } from 'vitest'
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

test('renders proposal, approval, execution and receipt as distinct states without action controls', () => {
  const html = renderToStaticMarkup(<ActionReview bundle={bundle} />)
  for (const text of ['Proposed actions', 'run-action-42', 'proposal-approved', 'Proposed intent', 'Authorization decision', 'Authorized by recorded decision', 'Approval state', 'Execution', 'succeeded', 'Matched receipt', 'receipt-ok', 'event-9', 'Arguments were supplied but are hidden', 'does not grant BAGO authority']) expect(html, `expected ${text}`).toContain(text)
  expect(html).not.toMatch(/<button[^>]*>(Approve|Reject|Request evidence)/)
  expect(html).not.toContain('report.txt')
})

test('shows denied authorization and declared but unavailable receipt without implying execution', () => {
  const html = renderToStaticMarkup(<ActionReview bundle={bundle} />)
  expect(html).toMatch(/Rejected by recorded decision/)
  expect(html).toMatch(/Receipt declared but unavailable/)
  expect(html).toMatch(/Call recorded: no/)
  expect(html).not.toMatch(/Execution: succeeded/)
})

test('missing and mismatched receipts are explicit and success without a match stays unverified', () => {
  const missing = actionBundleFromAgentRun({ run_id: 'r', proposals: [{ proposal_id: 'p', request_id: 'q', decision: 'ALLOW', called: true, outcome: 'SUCCESS', receipt_id: 'declared' }] })
  const missingHtml = renderToStaticMarkup(<ActionReview bundle={missing} />)
  expect(missingHtml).toMatch(/Receipt declared but unavailable/)
  expect(missingHtml).toMatch(/The source reports success, but it is unverified/)
  const mismatch = actionBundleFromAgentRun({ run_id: 'r', proposals: [{ proposal_id: 'p', request_id: 'q', permit_id: 'permit-1', decision: 'ALLOW', called: true, outcome: 'SUCCESS' }], mcp_receipts: [{ receipt_id: 'other', request_id: 'q', permit_id: 'permit-2', execution_outcome: 'SUCCESS' }] })
  expect(renderToStaticMarkup(<ActionReview bundle={mismatch} />)).toMatch(/Receipt mismatch/)
})

test('UI rejects a claimed receipt match without exact request and permit identity', () => {
  const unsafe = {
    schema: 'governed-action-bundle/v1' as const,
    actions: [{
      schema: 'governed-action/v1' as const,
      id: 'p',
      proposalState: 'proposed' as const,
      runId: 'r',
      requestId: 'request-1',
      effectType: 'WRITE',
      risk: 'mutating' as const,
      approval: 'unknown' as const,
      capability: { state: 'unknown' as const },
      eligibility: { state: 'unknown' as const },
      authorization: { state: 'authorized' as const, permitValidity: 'valid' as const, permitId: 'permit-1' },
      availability: { state: 'unknown' as const },
      execution: { state: 'succeeded' as const, called: true, outcome: 'SUCCESS' },
      receiptLink: { state: 'matched' as const, receiptId: 'receipt-1', receipt: { id: 'receipt-1', requestId: 'request-other', permitId: 'permit-other', outcome: 'SUCCESS', evidenceRefs: [], source: 'adl-agent-run' } },
    }],
  } satisfies ActionInspectionBundle
  const html = renderToStaticMarkup(<ActionReview bundle={unsafe} />)
  expect(html).toMatch(/Receipt mismatch/)
  expect(html).toMatch(/Execution<\/strong><span>Unverified \(unverified\)/)
  expect(html).toMatch(/identity-matched receipt is unavailable/)
})

test('loading, empty, error, unsupported and unknown states remain visible', () => {
  const html = [
    renderToStaticMarkup(<ActionReview state={{ status: 'loading' }} />),
    renderToStaticMarkup(<ActionReview bundle={{ schema: 'governed-action-bundle/v1', actions: [] }} />),
    renderToStaticMarkup(<ActionReview state={{ status: 'error', message: 'Action source failed' }} />),
    renderToStaticMarkup(<ActionReview bundle={{ schema: 'unsupported' as ActionInspectionBundle['schema'], actions: [] }} />),
    renderToStaticMarkup(<ActionReview />),
  ].join('\n')
  for (const text of ['Loading run artifacts', 'This run has no proposed actions', 'Action source failed', 'unsupported', 'Action proposal data was not provided']) expect(html, `expected ${text}`).toContain(text)
})

