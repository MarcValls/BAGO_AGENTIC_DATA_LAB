import { strict as assert } from 'node:assert'
import { test } from 'node:test'
import { renderToStaticMarkup } from 'react-dom/server'
import { localTraceToTimeline } from '../../../../src/adapters/trace/localTraceAdapter'
import { TraceTimeline } from '../../../../src/features/decision-inspector/trace/TraceTimeline'

const trace = localTraceToTimeline({
  trace_id: 'trace-1', run_id: 'run-1',
  events: [
    { event_id: 'child', trace_id: 'trace-1', sequence: 3, name: 'tool.call', kind: 'tool', status: 'DENY', parent_event_id: 'parent', attributes: { request_id: 'req-7', input: '[REDACTED]', output: 'denied' } },
    { event_id: 'root', trace_id: 'trace-1', sequence: 1, name: 'agent.start', kind: 'agent', status: 'OK', attributes: { claim_id: 'claim-2', action_id: 'action-4' } },
  ],
})

test('timeline separates sequence chronology and explicit parent causality; gaps and denied status stay visible', () => {
  const html = renderToStaticMarkup(<TraceTimeline timeline={trace} onClaimNavigate={() => undefined} onActionNavigate={() => undefined} />)
  assert.match(html, /Chronology: source sequence/)
  assert.match(html, /Causality: explicit parent event/)
  assert.match(html, /Sequence 1[\s\S]*Sequence 3/)
  assert.match(html, /sequence gap/)
  assert.match(html, /Status: DENY/)
  assert.match(html, /Parent unavailable: parent/)
})

test('only supplied claim/action identifiers become navigation controls and redaction is preserved', () => {
  const html = renderToStaticMarkup(<TraceTimeline timeline={trace} onClaimNavigate={() => undefined} onActionNavigate={() => undefined} />)
  assert.match(html, /Claim: claim-2/)
  assert.match(html, /Action: action-4/)
  assert.match(html, /Claim correlation unavailable/)
  assert.match(html, /Action correlation unavailable/)
  assert.match(html, /\[REDACTED\]/)
  assert.match(html, /cannot verify upstream redaction/)
  assert.match(html, /Jaeger correlation unavailable/)
  assert.doesNotMatch(html, /href=.*jaeger/i)
})

test('missing trace and empty event set are distinct explicit states', () => {
  const missing = renderToStaticMarkup(<TraceTimeline />)
  assert.match(missing, /Trace data was not provided by the source/)
  const empty = localTraceToTimeline({ trace_id: 'trace-empty', run_id: 'run-empty', events: [] })
  const html = renderToStaticMarkup(<TraceTimeline timeline={empty} />)
  assert.match(html, /This run has no trace events/)
})

test('loading and error states render through shared state primitives', () => {
  const loading = renderToStaticMarkup(<TraceTimeline state={{ status: 'loading' }} />)
  const error = renderToStaticMarkup(<TraceTimeline state={{ status: 'error', message: 'Trace service failed' }} />)
  assert.match(loading, /Loading run artifacts/)
  assert.match(error, /Trace service failed/)
})
