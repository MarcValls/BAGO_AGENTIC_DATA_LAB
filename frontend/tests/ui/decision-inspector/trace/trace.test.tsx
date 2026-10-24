import {setLocale,t} from '../../../../src/i18n'
import {beforeEach as beforeLocaleExpectation} from 'vitest'
beforeLocaleExpectation(() => setLocale('en'))
// @vitest-environment jsdom
import { strict as assert } from 'node:assert'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, it as test, vi } from 'vitest'
import { localTraceToTimeline } from '../../../../../src/adapters/trace/localTraceAdapter'
import { TraceTimeline } from '../../../../src/features/decision-inspector/trace/TraceTimeline'

afterEach(cleanup)

const timeline = localTraceToTimeline({
  trace_id: 'trace-ber-1', run_id: 'run-1',
  events: [
    {
      event_id: 'tool-event', trace_id: 'trace-ber-1', sequence: 4,
      name: 'filesystem.write', kind: 'tool', status: 'DENY', parent_event_id: 'missing-parent',
      attributes: {
        tool_call_id: 'call-1', proposal_id: 'proposal-1', request_id: 'request-1',
        claim_id: 'claim-2', action_id: 'action-4', execution_id: 'exec-3',
        execution_request_id: 'exec-request-3', permit_id: 'permit-7', receipt_id: 'receipt-9',
        input: '[REDACTED]', output: 'denied',
      },
      evidence_refs: ['receipt://evidence-only'],
    },
    {
      event_id: 'root', trace_id: 'trace-ber-1', sequence: 1,
      name: 'agent.start', kind: 'agent', status: 'COMPLETED', attributes: {}, evidence_refs: [],
    },
  ],
})

test('renders sequence chronology separately from parent causality and keeps gaps and failure visible', () => {
  render(<TraceTimeline timeline={timeline} />)
  assert.match(screen.getByText(/Chronology: supplied sequence/).textContent ?? '', /Causality: explicit parent event/)
  assert.equal(screen.getByText('Sequence 1').textContent, 'Sequence 1')
  assert.equal(screen.getByText('Sequence 4').textContent, 'Sequence 4')
  assert.ok(screen.getByText('Sequence gap (sequence_gap)'))
  assert.ok(screen.getByText('Missing parent (missing_parent)'))
  assert.ok(screen.getByText('Parent unavailable: missing-parent'))
  assert.ok(screen.getByText('Status: DENY'))
  assert.ok(screen.getByText(/receipt:\/\/evidence-only/))
})

test('shows distinct explicit correlation IDs and navigates only supplied claim/action identities', () => {
  const onClaimNavigate = vi.fn()
  const onActionNavigate = vi.fn()
  render(<TraceTimeline timeline={timeline} onClaimNavigate={onClaimNavigate} onActionNavigate={onActionNavigate} />)

  for (const id of ['call-1', 'proposal-1', 'request-1', 'claim-2', 'action-4', 'exec-3', 'exec-request-3', 'permit-7', 'receipt-9']) {
    assert.ok(screen.getAllByText(id).length > 0, `expected explicit ID ${id}`)
  }
  fireEvent.click(screen.getByRole('button', { name: /Claim: claim-2/ }))
  fireEvent.click(screen.getByRole('button', { name: /Action: action-4/ }))
  assert.deepEqual(onClaimNavigate.mock.calls, [['claim-2']])
  assert.deepEqual(onActionNavigate.mock.calls, [['action-4']])
  assert.equal(screen.getAllByText(/Correlation does not establish authorization or execution/).length, 2)
})

test('preserves redaction and does not parse evidence references into receipt IDs', () => {
  const eventWithoutReceipt = localTraceToTimeline({
    trace_id: 'trace-2', run_id: 'run-2',
    events: [{ event_id: 'e1', trace_id: 'trace-2', sequence: 0, name: 'tool', kind: 'tool', status: 'ERROR', attributes: { input: '[REDACTED]' }, evidence_refs: ['receipt://r-from-ref'] }],
  })
  render(<TraceTimeline timeline={eventWithoutReceipt} />)
  fireEvent.click(screen.getByText(t('agents.TraceTimeline.inspect_supplied_event_attributes')))
  assert.ok(screen.getByText('[REDACTED]'))
  assert.ok(screen.getByText(t('agents.TraceTimeline.redaction_markers_are_shown_as_received_the_inspector_cannot_verify_up')))
  assert.ok(screen.queryByText('r-from-ref') === null)
  assert.ok(screen.getByText(t('agents.TraceTimeline.claim_correlation_unavailable')))
  assert.ok(screen.getByText(t('agents.TraceTimeline.action_correlation_unavailable')))
})

test('distinguishes missing, empty, loading, error, unsupported and normal trace states', () => {
  const states = [
    { state: { status: 'loading' as const }, label: 'Loading' },
    { state: { status: 'error' as const, message: 'Trace service failed' }, label: 'Trace service failed' },
    { state: { status: 'unsupported' as const, message: 'Unsupported trace version' }, label: 'Unsupported trace version' },
  ]
  for (const entry of states) {
    const { unmount } = render(<TraceTimeline state={entry.state} />)
    assert.ok(screen.getByText(entry.label))
    unmount()
  }

  const { unmount } = render(<TraceTimeline />)
  assert.ok(screen.getByText(t('agents.TraceTimeline.trace_data_was_not_provided_by_the_source')))
  unmount()
  const empty = localTraceToTimeline({ trace_id: 'empty', run_id: 'run-empty', events: [] })
  render(<TraceTimeline timeline={empty} />)
  assert.ok(screen.getByText(t('agents.TraceTimeline.this_run_has_no_trace_events')))
})
