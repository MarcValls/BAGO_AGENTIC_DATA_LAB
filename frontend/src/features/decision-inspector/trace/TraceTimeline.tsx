import type { TraceTimeline as TraceTimelineData, TraceTimelineEvent } from '../../../contracts/trace/trace'
import { InspectorStateView, type InspectorState } from '../shared/InspectorState'
import './TraceTimeline.css'

export interface TraceTimelineProps {
  timeline?: TraceTimelineData | null
  state?: InspectorState
  onClaimNavigate?: (claimId: string) => void
  onActionNavigate?: (actionId: string) => void
}

function Payload({ event }: { event: TraceTimelineEvent }) {
  const values = Object.entries(event.attributes)
  const renderValue = (value: unknown) => {
    if (value === null || typeof value !== 'object') return String(value)
    return JSON.stringify(value, null, 2)
  }
  return <details className="decision-trace__payload">
    <summary>Inspect tool inputs and outputs (source attributes)</summary>
    {values.length === 0 ? <p>Payload not provided by the source.</p> : <dl>
      {values.map(([key, value]) => <div className="decision-trace__attribute" key={key}>
        <dt>{key}</dt><dd><pre>{renderValue(value)}</pre></dd>
      </div>)}
    </dl>}
    <p className="decision-trace__redaction-note">Redaction markers are shown as received; the inspector cannot verify upstream redaction.</p>
  </details>
}

function Correlation({ event, onClaimNavigate, onActionNavigate }: Pick<TraceTimelineProps, 'onClaimNavigate' | 'onActionNavigate'> & { event: TraceTimelineEvent }) {
  const { correlation } = event
  return <div className="decision-trace__correlation" aria-label="Explicit correlation identifiers">
    <span>Run: <code>{correlation.runId || 'Not provided'}</code></span>
    {correlation.agentId && <span>Agent: <code>{correlation.agentId}</code></span>}
    {correlation.toolCallId && <span>Tool call: <code>{correlation.toolCallId}</code></span>}
    {correlation.claimState === 'linked' && correlation.claimId
      ? <button type="button" onClick={() => onClaimNavigate?.(correlation.claimId!)} disabled={!onClaimNavigate}>Claim: {correlation.claimId}</button>
      : <span>Claim correlation unavailable</span>}
    {correlation.actionState === 'linked' && correlation.actionId
      ? <button type="button" onClick={() => onActionNavigate?.(correlation.actionId!)} disabled={!onActionNavigate}>Action: {correlation.actionId}</button>
      : <span>Action correlation unavailable</span>}
  </div>
}

export function TraceTimeline({ timeline, state = { status: 'ready' }, onClaimNavigate, onActionNavigate }: TraceTimelineProps) {
  if (state.status !== 'ready') return <section className="decision-trace" aria-labelledby="decision-trace-title"><h2 id="decision-trace-title">Trace timeline</h2><InspectorStateView state={state} /></section>
  if (!timeline) return <section className="decision-trace" aria-labelledby="decision-trace-title"><h2 id="decision-trace-title">Trace timeline</h2><InspectorStateView state={{ status: 'unknown', message: 'Trace data was not provided by the source.' }} /></section>
  if (timeline.events.length === 0) return <section className="decision-trace" aria-labelledby="decision-trace-title"><h2 id="decision-trace-title">Trace timeline</h2><InspectorStateView state={{ status: 'empty', message: 'This run has no trace events.' }} /></section>

  return <section className="decision-trace" aria-labelledby="decision-trace-title">
    <header className="decision-trace__header">
      <div><h2 id="decision-trace-title">Trace timeline</h2><p>Local trace <code>{timeline.traceId}</code> · Run <code>{timeline.runId}</code></p></div>
      <p className="decision-trace__jaeger" role="status">Jaeger correlation unavailable. Jaeger is a projection and is not execution authority.</p>
    </header>
    <p className="decision-trace__model">Chronology: source sequence ({timeline.chronology}). Causality: explicit parent event ({timeline.causality}). Sequence order does not imply causation.</p>
    {timeline.gaps.length > 0 && <aside className="decision-trace__gaps" aria-label="Trace gaps">
      <h3>Trace gaps ({timeline.gaps.length})</h3>
      <ul>{timeline.gaps.map((gap, index) => <li key={`${gap.kind}-${gap.eventId || 'trace'}-${index}`}><strong>{gap.kind.replace(/_/g, ' ')}</strong>: {gap.detail}</li>)}</ul>
    </aside>}
    <ol className="decision-trace__events" aria-label="Trace events in sequence order">
      {timeline.events.map(event => <li key={`${event.eventId}-${event.sequence}`} className="decision-trace__event">
        <article aria-labelledby={`trace-event-${event.sequence}`}>
          <header><span className="decision-trace__sequence">Sequence {event.sequence}</span><h3 id={`trace-event-${event.sequence}`}>{event.name || 'Unnamed event'}</h3><span className={`decision-trace__status decision-trace__status--${event.status.toLowerCase()}`}>Status: {event.status}</span></header>
          <dl className="decision-trace__facts">
            <div><dt>Event ID</dt><dd><code>{event.eventId}</code></dd></div>
            <div><dt>Kind</dt><dd>{event.kind || 'Not provided'}</dd></div>
            <div><dt>Causal parent</dt><dd>{event.parentState === 'root' ? 'Root event (no parent supplied)' : event.parentState === 'resolved' ? <code>{event.parentEventId}</code> : `Parent unavailable: ${event.parentEventId || 'not provided'}`}</dd></div>
            <div><dt>Evidence references</dt><dd>{event.evidenceRefs.length ? event.evidenceRefs.map(ref => <code key={ref}>{ref} </code>) : 'No evidence references linked'}</dd></div>
          </dl>
          <Correlation event={event} onClaimNavigate={onClaimNavigate} onActionNavigate={onActionNavigate} />
          <Payload event={event} />
        </article>
      </li>)}
    </ol>
  </section>
}
