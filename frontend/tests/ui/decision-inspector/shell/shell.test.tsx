import { strict as assert } from 'node:assert'
import { test } from 'node:test'
import { renderToStaticMarkup } from 'react-dom/server'
import { InspectorShell, selectConclusion } from '../../../../src/features/decision-inspector/shell/InspectorShell'
import { EvidenceSupportStatus, InspectorStateView } from '../../../../src/features/decision-inspector/shared/InspectorState'
import type { DecisionConclusion } from '../../../../src/contracts/decision/evidence'

const conclusion: DecisionConclusion = { schema: 'decision-conclusion/v1', id: 'c-1', runId: 'run-1', text: 'Source-provided answer', claims: [], evidence: [] }

test('selection resolves only an explicitly supplied conclusion identity', () => {
  assert.equal(selectConclusion([conclusion], 'c-1'), conclusion)
  assert.equal(selectConclusion([conclusion], 'absent'), undefined)
  assert.equal(selectConclusion([conclusion], null), undefined)
})

test('shell renders source-backed selection, identity and explicit missing section state', () => {
  const html = renderToStaticMarkup(<InspectorShell conclusions={[conclusion]} selectedConclusionId="c-1" initialSection="evidence" />)
  assert.match(html, /Decision Inspector/)
  assert.match(html, /Run ID:/)
  assert.match(html, /run-1/)
  assert.match(html, /Evidence data not provided/)
  assert.match(html, /aria-label="Select a conclusion"/)
})

test('empty, loading, error, unsupported and unknown states have textual announcements', () => {
  const states = [
    { status: 'loading' as const }, { status: 'empty' as const },
    { status: 'error' as const, message: 'Request failed' },
    { status: 'unsupported' as const }, { status: 'unknown' as const },
  ]
  for (const state of states) {
    const html = renderToStaticMarkup(<InspectorStateView state={state} />)
    assert.match(html, /role="(status|alert)"/)
    assert.match(html, /<p>/)
  }
})

test('unsupported claims never receive a supported presentation by default', () => {
  const html = renderToStaticMarkup(<EvidenceSupportStatus status="unsupported" />)
  assert.match(html, /No supporting evidence linked/)
  assert.doesNotMatch(html, /Supported by linked evidence/)
})
