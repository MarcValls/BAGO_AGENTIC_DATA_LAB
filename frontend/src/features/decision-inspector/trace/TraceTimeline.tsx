import {agentStateLabel} from '../../../components/AgentTaskForm'
import {useI18n, t, formatDate, formatNumber, apiError, errorMessage} from '../../../i18n'
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
  useI18n()
  const values = Object.entries(event.attributes)
  const renderValue = (value: unknown) => {
    if (value === null || typeof value !== 'object') return String(value)
    return JSON.stringify(value, null, 2)
  }
  return <details className="decision-trace__payload">
    <summary>{t('agents.TraceTimeline.inspect_supplied_event_attributes')}</summary>
    {values.length === 0 ? <p>{t('agents.TraceTimeline.event_attributes_not_provided_by_the_source')}</p> : <dl>
      {values.map(([key, value]) => <div className="decision-trace__attribute" key={key}>
        <dt>{key}</dt><dd><pre>{renderValue(value)}</pre></dd>
      </div>)}
    </dl>}
    <p className="decision-trace__redaction-note">{t('agents.TraceTimeline.redaction_markers_are_shown_as_received_the_inspector_cannot_verify_up')}</p>
  </details>
}

function Correlation({ event, onClaimNavigate, onActionNavigate }: Pick<TraceTimelineProps, 'onClaimNavigate' | 'onActionNavigate'> & { event: EventData | LegacyTimelineData['events'][number] }) {
  useI18n()
  const ids = eventCorrelations(event)
  const supplied = [
    [t('agents.AgentEvaluationLab.agent'), ids.agentId], [t('agents.TraceTimeline.tool_call'), ids.toolCallId], [t('agents.TraceTimeline.proposal'), 'proposalId' in ids ? ids.proposalId : undefined],
    [t('agents.TraceTimeline.request'), 'requestId' in ids ? ids.requestId : undefined], [t('agents.EvidenceExplorer.claim'), ids.claimId], [t('agents.DecisionInspector.action'), ids.actionId],
    [t('agents.ActionReview.execution'), 'executionId' in ids ? ids.executionId : undefined], [t('agents.TraceTimeline.execution_request'), 'executionRequestId' in ids ? ids.executionRequestId : undefined],
    [t('agents.TraceTimeline.permit'), 'permitId' in ids ? ids.permitId : undefined], [t('agents.ActionReview.receipt'), 'receiptId' in ids ? ids.receiptId : undefined],
  ] as const
  const visible = supplied.filter(([, id]) => Boolean(id))

  return <section className="decision-trace__correlation" aria-label={t('agents.TraceTimeline.source_supplied_correlation_identifiers')}>
    <h4>{t('agents.TraceTimeline.correlation_identifiers')}</h4>
    {visible.length > 0 ? <dl>
      {visible.map(([label, id]) => <div key={label}>
        <dt>{label}</dt><dd>{id ? label === t('agents.EvidenceExplorer.claim') && onClaimNavigate
          ? <button type="button" onClick={() => onClaimNavigate(id)}>{t('agents.TraceTimeline.claim')} <code>{id}</code></button>
          : label === t('agents.DecisionInspector.action') && onActionNavigate
            ? <button type="button" onClick={() => onActionNavigate(id)}>{t('agents.TraceTimeline.action')} <code>{id}</code></button>
            : <code>{id}</code>
          : t('agents.TraceTimeline.correlation_unavailable')}</dd>
      </div>)}
    </dl> : <p>{t('agents.TraceTimeline.no_optional_correlation_identifiers_were_supplied')}</p>}
    {!ids.claimId && <p>{t('agents.TraceTimeline.claim_correlation_unavailable')}</p>}
    {!ids.actionId && <p>{t('agents.TraceTimeline.action_correlation_unavailable')}</p>}
    <p>{t('agents.TraceTimeline.identifiers_are_copied_from_the_source_event_correlation_does_not_esta')}</p>
  </section>
}

export function TraceTimeline({ timeline, state = { status: 'ready' }, onClaimNavigate, onActionNavigate }: TraceTimelineProps) {
  useI18n()
  if (state.status !== 'ready') return <section className="decision-trace" aria-labelledby="decision-trace-title"><h2 id="decision-trace-title">{t('agents.TraceTimeline.trace_timeline')}</h2><InspectorStateView state={state} /></section>
  if (!timeline) return <section className="decision-trace" aria-labelledby="decision-trace-title"><h2 id="decision-trace-title">{t('agents.TraceTimeline.trace_timeline')}</h2><InspectorStateView state={{ status: 'unknown', message: t('agents.TraceTimeline.trace_data_was_not_provided_by_the_source') }} /></section>
  if (timeline.events.length === 0) return <section className="decision-trace" aria-labelledby="decision-trace-title"><h2 id="decision-trace-title">{t('agents.TraceTimeline.trace_timeline')}</h2><InspectorStateView state={{ status: 'empty', message: t('agents.TraceTimeline.this_run_has_no_trace_events') }} /></section>

  return <section className="decision-trace" aria-labelledby="decision-trace-title">
    <header className="decision-trace__header">
      <div><h2 id="decision-trace-title">{t('agents.TraceTimeline.trace_timeline')}</h2><p>{t('agents.TraceTimeline.supplied_trace')} <code>{timeline.traceId}</code> {t('agents.TraceTimeline.run')} <code>{timeline.runId}</code></p></div>
      <p className="decision-trace__authority" role="note">{t('agents.TraceTimeline.trace_data_is_an_observation_it_does_not_establish_ber_authorization_o')}</p>
    </header>
    <p className="decision-trace__model">{t('agents.TraceTimeline.chronology_supplied_sequence_causality_explicit_parent_event_sequence_')}</p>
    {timeline.gaps.length > 0 && <aside className="decision-trace__gaps" aria-label={t('agents.TraceTimeline.trace_gaps')}>
      <h3>{t('agents.trace.gapsCount',{count:formatNumber(timeline.gaps.length)})}</h3>
      <ul>{timeline.gaps.map((gap, index) => <li key={`${gap.kind}-${gap.eventId || 'trace'}-${index}`}><strong>{agentStateLabel(gap.kind)}</strong>: {gap.detail}</li>)}</ul>
    </aside>}
    <ol className="decision-trace__events" aria-label={t('agents.TraceTimeline.trace_events_in_supplied_sequence_order')}>
      {timeline.events.map(event => <li key={`${event.eventId}-${event.sequence}`} className="decision-trace__event">
        <article aria-labelledby={`trace-event-${event.sequence}-${event.eventId}`}>
          <header><span className="decision-trace__sequence">{t('agents.TraceTimeline.sequence')} {event.sequence}</span><h3 id={`trace-event-${event.sequence}-${event.eventId}`}>{event.name || t('agents.TraceTimeline.unnamed_event')}</h3><span className="decision-trace__status">{t('agents.AgentRunner.status')} {event.status || t('agents.AgentRunner.not_provided')}</span></header>
          <dl className="decision-trace__facts">
            <div><dt>{t('agents.TraceTimeline.event_id')}</dt><dd><code>{event.eventId || t('agents.AgentRunner.not_provided')}</code></dd></div>
            <div><dt>{t('agents.TraceTimeline.event_trace_id')}</dt><dd><code>{event.traceId || t('agents.AgentRunner.not_provided')}</code></dd></div>
            <div><dt>{t('agents.TraceTimeline.kind')}</dt><dd>{event.kind || t('agents.AgentRunner.not_provided')}</dd></div>
            <div><dt>{t('agents.TraceTimeline.declared_causal_parent')}</dt><dd>{event.parentState === 'root' ? t('agents.TraceTimeline.root_event_no_parent_supplied') : event.parentState === 'resolved' ? <code>{event.parentEventId}</code> : t('agents.TraceTimeline.parent_unavailable_p0', {p0: event.parentEventId || t('agents.TraceTimeline.not_provided')})}</dd></div>
            <div><dt>{t('agents.DecisionInspector.evidence_references')}</dt><dd>{event.evidenceRefs.length ? event.evidenceRefs.map((ref, index) => <code key={`${ref}-${index}`}>{ref} </code>) : t('agents.TraceTimeline.no_evidence_references_linked')}</dd></div>
          </dl>
          <Correlation event={event} onClaimNavigate={onClaimNavigate} onActionNavigate={onActionNavigate} />
          <Payload event={event} />
        </article>
      </li>)}
    </ol>
  </section>
}
