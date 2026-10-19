// @vitest-environment jsdom
import { strict as assert } from 'node:assert'
import { fireEvent, render, screen } from '@testing-library/react'
import { it as test, vi } from 'vitest'
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

test('empty, loading, error, unsupported, partial, stale, unverified and unknown states have textual announcements', () => {
  const states = [
    { status: 'loading' as const }, { status: 'empty' as const },
    { status: 'error' as const, message: 'Request failed' },
    { status: 'unsupported' as const },
    { status: 'partial' as const, message: 'Evidence is unavailable.' },
    { status: 'stale' as const, message: 'Snapshot identity changed.' },
    { status: 'unverified' as const, message: 'Receipt identity was not provided.' },
    { status: 'unknown' as const },
  ]
  for (const state of states) {
    const html = renderToStaticMarkup(<InspectorStateView state={state} />)
    assert.match(html, /role="(status|alert)"/)
    assert.match(html, /<p>/)
  }
})

test('shell exposes native keyboard-operable navigation without adding effect controls', () => {
  const html = renderToStaticMarkup(<InspectorShell conclusions={[conclusion]} selectedConclusionId="c-1" />)
  assert.match(html, /aria-label="Select a conclusion"/)
  assert.match(html, /aria-label="Conclusion details"/)
  assert.match(html, /aria-current="true"/)
  assert.match(html, /aria-pressed="true"/)
  assert.doesNotMatch(html, /Approve|Execute|Delete|Retry/)
})

test('user can select a supplied conclusion and navigate its sections', () => {
  const second: DecisionConclusion = { ...conclusion, id: 'c-2', runId: 'run-2', text: 'Second supplied conclusion' }
  const onConclusionSelect = vi.fn()
  render(<InspectorShell conclusions={[conclusion, second]} onConclusionSelect={onConclusionSelect} />)

  fireEvent.click(screen.getByRole('button', { name: 'Source-provided answer' }))
  assert.equal(onConclusionSelect.mock.calls[0]?.[0], 'c-1')
  assert.equal(screen.getByRole('button', { name: 'Source-provided answer' }).getAttribute('aria-current'), 'true')
  fireEvent.click(screen.getByRole('button', { name: 'Evidence' }))
  assert.ok(screen.getByRole('heading', { name: 'Evidence' }))
  assert.match(screen.getByLabelText('Current location').textContent ?? '', /Evidence/)
})

test('unsupported claims never receive a supported presentation by default', () => {
  const html = renderToStaticMarkup(<EvidenceSupportStatus status="unsupported" />)
  assert.match(html, /No supporting evidence linked/)
  assert.doesNotMatch(html, /Supported by linked evidence/)
})
