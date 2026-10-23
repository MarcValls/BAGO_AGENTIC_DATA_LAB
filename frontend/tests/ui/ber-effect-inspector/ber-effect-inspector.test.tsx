import {setLocale,t} from '../../../src/i18n'
import {beforeEach as beforeLocaleExpectation} from 'vitest'
beforeLocaleExpectation(() => setLocale('en'))
// @vitest-environment jsdom
import { strict as assert } from 'node:assert'
import { test } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { BerEffectRecordInspector, validateBerEffectRecord } from '../../../src/features/ber-effect-inspector/BerEffectRecordInspector'

const record = {
  schema: 'bago.ber.effect-demo.v1',
  status: 'PASS',
  ber: {
    version: '0.1.0',
    protocol_version: 'bago.ber.ipc/v1',
    source_commit: '5fb6f2f0c57f29de1b42bbb2efb4a57c86aa032d',
    artifact_sha256: 'c81ef7f05a3051df8ecbc1a150500ea16ea872fc459fa45881488c91e83843d3',
  },
  prepared: { effect_id: 'filesystem.write', request_id: 'request-1', approval_required: true },
  approval: { state: 'approved', request_id: 'request-1', effect_id: 'filesystem.write', decision_id: 'decision-1', proof_id: 'proof-1' },
  execution: {
    ber_execution_id: 'ber-exec-1',
    request_id: 'request-1',
    effect_id: 'filesystem.write',
    receipt_id: 'receipt-1',
    authorization: { state: 'consumed', decision_id: 'decision-1', proof_id: 'proof-1', permit_id: 'permit-1' },
    result: { ok: true, executed: true, receipt_id: 'receipt-1', content: 'MUST NOT RENDER' },
  },
  trace: {
    trace_id: 'trace-1',
    run_id: 'ber-exec-1',
    events: [
      { event_id: 'event-1', trace_id: 'trace-1', name: 'ber.effect', status: 'SUCCESS', attributes: { effect_id: 'filesystem.write', request_id: 'request-1' } },
      { event_id: 'event-2', trace_id: 'trace-1', name: 'ber.receipt', status: 'SUCCESS', attributes: { receipt_id: 'receipt-1', request_id: 'request-1' } },
    ],
  },
  evaluation: { status: 'PASS', evidence_refs: ['ber://receipt/receipt-1'] },
}

test('accepts a pinned BER record only when execution, approval, receipt, trace and evaluation correlate', () => {
  const validated = validateBerEffectRecord(record)
  assert.equal(validated.execution.ber_execution_id, validated.trace.run_id)
  assert.equal(validated.events[0]?.trace_id, validated.trace.trace_id)
  assert.equal(validated.evaluation.status, 'PASS')
})

test('rejects unpinned, foreign, mismatched and unsupported BER records', () => {
  const mutations: Array<[string, (copy: typeof record) => void]> = [
    ['source commit', copy => { copy.ber.source_commit = 'foreign' }],
    ['request ID', copy => { copy.execution.request_id = 'foreign' }],
    ['receipt ID', copy => { copy.execution.result.receipt_id = 'foreign' }],
    ['execution effect', copy => { copy.execution.effect_id = 'filesystem.delete' }],
    ['LocalTrace run ID', copy => { copy.trace.run_id = 'foreign' }],
    ['unsupported effect', copy => { copy.prepared.effect_id = 'filesystem.delete' }],
    ['approval decision', copy => { copy.execution.authorization.decision_id = 'foreign' }],
  ]
  for (const [label, mutate] of mutations) {
    const copy = structuredClone(record)
    mutate(copy)
    assert.throws(() => validateBerEffectRecord(copy), Error, label)
  }
})

test('shows an explicit approval link requirement for mutating effects', () => {
  const copy = structuredClone(record)
  copy.approval = null
  assert.throws(() => validateBerEffectRecord(copy), /matching BAGO approval/)
})

test('imports the selected JSON and renders receipt/trace metadata without effect output', async () => {
  render(<BerEffectRecordInspector />)
  const file = new File([JSON.stringify(record)], 'ber-effect.json', { type: 'application/json' })
  Object.defineProperty(file, 'text', { value: async () => JSON.stringify(record) })
  fireEvent.change(screen.getByLabelText(t('agents.BerEffectRecordInspector.choose_ber_effect_json')), { target: { files: [file] } })

  assert.ok(await screen.findByText('ber-effect.json'))
  assert.ok(screen.getByText('receipt-1'))
  assert.ok(screen.getByText('trace-1'))
  assert.equal(screen.queryByText('MUST NOT RENDER'), null)
})
