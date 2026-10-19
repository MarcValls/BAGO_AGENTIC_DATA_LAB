import './TraceTimeline.css'
import type { InspectorState } from '../shared/InspectorState'
import { InspectorStateView } from '../shared/InspectorState'

/** Structural UI shape of the frozen src/contracts/trace/trace.ts contract. */
export interface TraceTimelineData {
  traceId: string
  runId: string
  chronology: 'sequence'
  causality: 'parent_event_id'
  gaps: Array<{ kind: string; eventId?: string; detail: string }>
  events: Array<{
    eventId: string
    traceId: string
    sequence: number
    name: string
    kind: string
    status: string
    parentEventId?: string
    parentState: 'root' | 'resolved' | 'missing'
    runId: string
    correlations: {
      agentId?: string
      toolCallId?: string
      proposalId?: string
      requestId?: string
      claimId?: string
      actionId?: string
      executionId?: string
      executionRequestId?: string
      permitId?: string
      receiptId?: string
    }
    attributes: Record<string, unknown>
    evidenceRefs: string[]
  }>
}

/** Temporary structural adapter for the earlier frontend projection during integration. */
interface LegacyTimelineData {
  traceId: string
  runId: string
  chronology: 'sequence'
  causality: 'parent_event_id'
  jaegerCorrelation?: 'available' | 'unavailable'
  gaps: Array<{ kind: string; eventId?: string; detail: string }>
  events: Array<{
    eventId: string
    traceId: string
    sequence: number
    name: string
    kind: string
    status: string
    parentEventId?: string
    parentState: 'root' | 'resolved' | 'missing'
    correlation: { runId: string; agentId?: string; toolCallId?: string; claimId?: string; actionId?: string; claimState: 'linked' | 'missing'; actionState: 'linked' | 'missing' }
    attributes: Record<string, unknown>
    evidenceRefs: string[]
  }>
}

type TimelineData = TraceTimelineData | LegacyTimelineData
type EventData = TraceTimelineData['events'][number]

export interface TraceTimelineProps {
  timeline?: TimelineData | null
  state?: InspectorState
  onClaimNavigate?: (claimId: string) => void
  onActionNavigate?: (actionId: string) => void
}

function eventCorrelations(event: EventData | LegacyTimelineData['events'][number]) {
  if ('correlations' in event) return event.correlations
  const { correlation } = event
  return {
    ...(correlation.agentId ? { agentId: correlation.agentId } : {}),
    // The legacy projector overloaded request/proposal IDs as toolCallId. Do not
    // display that value as a tool call until the canonical W04 projection feeds it.
    ...(correlation.claimId ? { claimId: correlation.claimId } : {}),
    ...(correlation.actionId ? { actionId: correlation.actionId } : {}),
  }
}

function Payload({ event }: { event: EventData | LegacyTimelineData['events'][number] }) {
  const values = Object.entries(event.attributes)
  const renderValue = (value: unknown) => {
    if (value === null || typeof value !== 'object') return String(value)
    return JSON.stringify(value, null, 2)
  }
  return <details className="decision-trace__payload">
    <summary>Inspect supplied event attributes</summary>
    {values.length === 0 ? <p>Event attributes not provided by the source.</p> : <dl>
      {values.map(([key, value]) => <div className="decision-trace__attribute" key={key}>
        <dt>{key}</dt><dd><pre>{renderValue(value)}</pre></dd>
      </div>)}
    </dl>}
    <p className="decision-trace__redaction-note">Redaction markers are shown as received; the inspector cannot verify upstream redaction.</p>
  </details>
}

function Correlation({ event, onClaimNavigate, onActionNavigate }: Pick<TraceTimelineProps, 'onClaimNavigate' | 'onActionNavigate'> & { event: EventData | LegacyTimelineData['events'][number] }) {
  const ids = eventCorrelations(event)
  const supplied = [
    ['Agent', ids.agentId], ['Tool call', ids.toolCallId], ['Proposal', 'proposalId' in ids ? ids.proposalId : undefined],
    ['Request', 'requestId' in ids ? ids.requestId : undefined], ['Claim', ids.claimId], ['Action', ids.actionId],
    ['Execution', 'executionId' in ids ? ids.executionId : undefined], ['Execution request', 'executionRequestId' in ids ? ids.executionRequestId : undefined],
    ['Permit', 'permitId' in ids ? ids.permitId : undefined], ['Receipt', 'receiptId' in ids ? ids.receiptId : undefined],
  ] as const
  const visible = supplied.filter(([, id]) => Boolean(id))

  return <section className="decision-trace__correlation" aria-label="Source-supplied correlation identifiers">
    <h4>Correlation identifiers</h4>
    {visible.length > 0 ? <dl>
      {visible.map(([label, id]) => <div key={label}>
        <dt>{label}</dt><dd>{id ? label === 'Claim' && onClaimNavigate
          ? <button type="button" onClick={() => onClaimNavigate(id)}>Claim: <code>{id}</code></button>
          : label === 'Action' && onActionNavigate
            ? <button type="button" onClick={() => onActionNavigate(id)}>Action: <code>{id}</code></button>
            : <code>{id}</code>
          : 'Correlation unavailable'}</dd>
      </div>)}
    </dl> : <p>No optional correlation identifiers were supplied.</p>}
    {!ids.claimId && <p>Claim correlation unavailable.</p>}
    {!ids.actionId && <p>Action correlation unavailable.</p>}
    <p>Identifiers are copied from the source event. Correlation does not establish authorization or execution.</p>
  </section>
}

export function TraceTimeline({ timeline, state = { status: 'ready' }, onClaimNavigate, onActionNavigate }: TraceTimelineProps) {
  if (state.status !== 'ready') return <section className="decision-trace" aria-labelledby="decision-trace-title"><h2 id="decision-trace-title">Trace timeline</h2><InspectorStateView state={state} /></section>
  if (!timeline) return <section className="decision-trace" aria-labelledby="decision-trace-title"><h2 id="decision-trace-title">Trace timeline</h2><InspectorStateView state={{ status: 'unknown', message: 'Trace data was not provided by the source.' }} /></section>
  if (timeline.events.length === 0) return <section className="decision-trace" aria-labelledby="decision-trace-title"><h2 id="decision-trace-title">Trace timeline</h2><InspectorStateView state={{ status: 'empty', message: 'This run has no trace events.' }} /></section>

  return <section className="decision-trace" aria-labelledby="decision-trace-title">
    <header className="decision-trace__header">
      <div><h2 id="decision-trace-title">Trace timeline</h2><p>Supplied trace <code>{timeline.traceId}</code> · Run <code>{timeline.runId}</code></p></div>
      <p className="decision-trace__authority" role="note">Trace data is an observation. It does not establish BER authorization or execution.</p>
    </header>
    <p className="decision-trace__model">Chronology: supplied sequence. Causality: explicit parent event. Sequence order does not imply causation.</p>
    {timeline.gaps.length > 0 && <aside className="decision-trace__gaps" aria-label="Trace gaps">
      <h3>Trace gaps ({timeline.gaps.length})</h3>
      <ul>{timeline.gaps.map((gap, index) => <li key={`${gap.kind}-${gap.eventId || 'trace'}-${index}`}><strong>{gap.kind.replace(/_/g, ' ')}</strong>: {gap.detail}</li>)}</ul>
    </aside>}
    <ol className="decision-trace__events" aria-label="Trace events in supplied sequence order">
      {timeline.events.map(event => <li key={`${event.eventId}-${event.sequence}`} className="decision-trace__event">
        <article aria-labelledby={`trace-event-${event.sequence}-${event.eventId}`}>
          <header><span className="decision-trace__sequence">Sequence {event.sequence}</span><h3 id={`trace-event-${event.sequence}-${event.eventId}`}>{event.name || 'Unnamed event'}</h3><span className="decision-trace__status">Status: {event.status || 'Not provided'}</span></header>
          <dl className="decision-trace__facts">
            <div><dt>Event ID</dt><dd><code>{event.eventId || 'Not provided'}</code></dd></div>
            <div><dt>Event trace ID</dt><dd><code>{event.traceId || 'Not provided'}</code></dd></div>
            <div><dt>Kind</dt><dd>{event.kind || 'Not provided'}</dd></div>
            <div><dt>Declared causal parent</dt><dd>{event.parentState === 'root' ? 'Root event (no parent supplied)' : event.parentState === 'resolved' ? <code>{event.parentEventId}</code> : `Parent unavailable: ${event.parentEventId || 'not provided'}`}</dd></div>
            <div><dt>Evidence references</dt><dd>{event.evidenceRefs.length ? event.evidenceRefs.map((ref, index) => <code key={`${ref}-${index}`}>{ref} </code>) : 'No evidence references linked'}</dd></div>
          </dl>
          <Correlation event={event} onClaimNavigate={onClaimNavigate} onActionNavigate={onActionNavigate} />
          <Payload event={event} />
        </article>
      </li>)}
    </ol>
  </section>
}
