import {useI18n, t, formatDate, formatNumber, apiError, errorMessage} from '../../../i18n'
import './DecisionInspector.css'
import { useMemo, useState } from 'react'
import { actionBundleFromAgentRun } from '../../../adapters/action/agentRun'
import { localTraceToTimeline } from '../../../adapters/trace/localTraceAdapter'
import { evidenceFromRetrievalHit, type DecisionConclusion, type DecisionEvidence } from '../../../contracts/decision/evidence'
import type { ActionInspectionBundle } from '../../../contracts/action/action'
import type { TraceSource, TraceTimeline } from '../../../contracts/trace/trace'
import { ActionReview } from '../actions/ActionReview'
import { EvidenceExplorer } from '../evidence/EvidenceExplorer'
import { InspectorShell, type InspectorSection } from '../shell/InspectorShell'
import { TraceTimeline as TraceTimelineView } from '../trace/TraceTimeline'

export interface DecisionInspectorArtifacts {
  summary: Record<string, unknown>
  agent_run: Record<string, unknown>
  receipts: Record<string, unknown>
  trace: TraceSource
  evaluation: Record<string, unknown>
}

export interface DecisionInspectorModel {
  conclusion?: DecisionConclusion
  evidence: DecisionEvidence[]
  timeline?: TraceTimeline
  traceBindingIssue?: { kind: 'run_id_missing' | 'run_id_mismatch'; expectedRunId?: string; actualRunId: string }
  actions: ActionInspectionBundle
}

function record(value: unknown): Record<string, unknown> | undefined {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : undefined
}

function text(value: unknown): string | undefined {
  return typeof value === 'string' && value.trim() ? value : undefined
}

/** Receipt association requires source identity, even when receipt arrays are nested in a run. */
function runBoundActionSource(run: Record<string, unknown>): Parameters<typeof actionBundleFromAgentRun>[0] {
  const runId = text(run.run_id)
  const receiptsForThisRun = (value: unknown) => {
    if (!runId || !Array.isArray(value)) return []
    return value.filter(item => {
      const receipt = record(item)
      return receipt !== undefined && text(receipt.run_id) === runId
    })
  }
  const providerReceipt = record(run.provider_receipt)

  return {
    ...run,
    decision_receipts: receiptsForThisRun(run.decision_receipts),
    mcp_receipts: receiptsForThisRun(run.mcp_receipts),
    provider_receipt: runId && providerReceipt && text(providerReceipt.run_id) === runId ? providerReceipt : undefined,
  } as Parameters<typeof actionBundleFromAgentRun>[0]
}

/** Maps only source-supplied identities and values; it never decomposes answer text into claims. */
export function decisionInspectorModel(artifacts: DecisionInspectorArtifacts): DecisionInspectorModel {
  const run = artifacts.agent_run
  const runId = text(run.run_id)
  const retrieval = record(run.retrieval)
  const hits = Array.isArray(retrieval?.hits) ? retrieval.hits.map(record).filter((item): item is Record<string, unknown> => Boolean(item)) : []
  const evidenceById = new Map<string, DecisionEvidence>()

  for (const hit of hits) {
    const rawEvidence = record(hit.evidence)
    const mapped = evidenceFromRetrievalHit({
      ...(rawEvidence ? { evidence: rawEvidence as { citation?: string; chunk_id?: string; document_id?: string; source_uri?: string; revision?: string } } : {}),
      ...(text(hit.chunk_id) ? { chunk_id: text(hit.chunk_id) } : {}),
      ...(text(hit.document_id) ? { document_id: text(hit.document_id) } : {}),
    })
    if (mapped.id) evidenceById.set(mapped.id, mapped)
  }

  const citations = Array.isArray(run.citations) ? run.citations.filter((item): item is string => typeof item === 'string') : []
  for (const citation of citations) {
    if (citation.trim() && !evidenceById.has(citation)) {
      evidenceById.set(citation, { id: citation, artifactRef: citation, freshness: 'unknown' })
    }
  }

  const evidence = [...evidenceById.values()]
  const conclusion = runId ? {
    schema: 'decision-conclusion/v1' as const,
    id: runId,
    runId,
    text: text(run.answer) ?? '',
    claims: [],
    evidence,
  } : undefined
  const trace = artifacts.trace
  const validTraceEnvelope = trace && typeof trace.trace_id === 'string' && typeof trace.run_id === 'string' && Array.isArray(trace.events)
  const traceBindingIssue = validTraceEnvelope && !runId
    ? { kind: 'run_id_missing' as const, actualRunId: trace.run_id }
    : validTraceEnvelope && trace.run_id !== runId
      ? { kind: 'run_id_mismatch' as const, expectedRunId: runId, actualRunId: trace.run_id }
    : undefined
  const timeline = validTraceEnvelope && runId && !traceBindingIssue
    ? localTraceToTimeline(trace)
    : undefined

  return {
    conclusion,
    evidence,
    timeline,
    traceBindingIssue,
    actions: actionBundleFromAgentRun(runBoundActionSource(run)),
  }
}

type InspectorView = 'overview' | 'trace' | 'actions'

const views: Array<{ id: InspectorView; label: string }> = [
  { id: 'overview', get label() { return t('agents.DecisionInspector.decision') } },
  { id: 'trace', get label() { return t('agents.DecisionInspector.trace') } },
  { id: 'actions', get label() { return t('agents.DecisionInspector.actions') } },
]

function EvidenceInventory({ evidence }: { evidence: DecisionEvidence[] }) {
  useI18n()
  if (evidence.length === 0) return <p role="status">{t('agents.DecisionInspector.no_citation_or_retrieval_evidence_was_provided_by_this_run')}</p>
  return <section className="decision-inspector__inventory" aria-label={t('agents.DecisionInspector.retrieved_evidence_references')}>
    <p>{t('agents.DecisionInspector.these_references_were_retrieved_for_the_run_the_source_did_not_provide')}</p>
    <ul>{evidence.map((item, index) => <li key={`${item.id}-${index}`}>
      <h3>{t('agents.inspector.referenceNumber',{count:formatNumber(index+1)})}</h3>
      <p><code>{item.artifactRef || item.id || t('agents.DecisionInspector.reference_not_provided')}</code></p>
      <dl>
        <div><dt>{t('agents.DecisionInspector.source')}</dt><dd><code>{item.sourceIdentity || item.snapshot?.sourceUri || t('agents.AgentRunner.not_provided')}</code></dd></div>
        <div><dt>{t('agents.DecisionInspector.revision')}</dt><dd>{item.snapshot?.revision || t('agents.AgentRunner.not_provided')}</dd></div>
        <div><dt>{t('agents.EvidenceExplorer.freshness')}</dt><dd>{item.freshness === 'unknown' ? t('agents.ActionReview.not_established') : item.freshness}</dd></div>
        <div><dt>{t('agents.DecisionInspector.claim_relation')}</dt><dd>{t('agents.AgentRunner.not_provided')}</dd></div>
      </dl>
    </li>)}</ul>
  </section>
}

export function DecisionInspector({ artifacts, embedded = false }: { artifacts: DecisionInspectorArtifacts; embedded?: boolean }) {
  useI18n()
  const [view, setView] = useState<InspectorView>('overview')
  const [section, setSection] = useState<InspectorSection>('conclusion')
  const [claimId, setClaimId] = useState<string | undefined>()
  const [actionId, setActionId] = useState<string | undefined>()
  const model = useMemo(() => decisionInspectorModel(artifacts), [artifacts])
  const runId = model.conclusion?.runId || t('agents.AgentRunner.not_provided')
  const selectedAction = actionId ? model.actions.actions.find(action => action.id === actionId) : undefined
  const actionBundle = selectedAction ? { ...model.actions, actions: [selectedAction] } : model.actions
  const runStatus = text(artifacts.agent_run.status) || t('agents.AgentRunner.not_provided')

  const conclusion = model.conclusion ? <>
    <section className="decision-inspector__summary" aria-label={t('agents.DecisionInspector.agent_conclusion')}>
      <p className="decision-inspector__eyebrow">{t('agents.DecisionInspector.agent_conclusion')}</p>
      <h2>{text(artifacts.agent_run.query) || t('agents.DecisionInspector.query_not_provided')}</h2>
      <p className="decision-inspector__answer">{model.conclusion.text || t('agents.DecisionInspector.conclusion_text_not_provided')}</p>
    </section>
    <div className="decision-inspector__summary-grid">
      <div><span>{t('agents.DecisionInspector.evidence_references')}</span><strong>{model.evidence.length}</strong></div>
      <div><span>{t('agents.DecisionInspector.structured_claims')}</span><strong>{model.conclusion.claims.length ? model.conclusion.claims.length : t('agents.AgentRunner.not_provided')}</strong></div>
      <div><span>{t('agents.DecisionInspector.trace_events')}</span><strong>{model.timeline?.events.length ?? t('agents.AgentRunner.not_provided')}</strong></div>
      <div><span>{t('agents.ActionReview.proposed_actions')}</span><strong>{model.actions.actions.length}</strong></div>
    </div>
    <InspectorShell
      embedded
      key={section}
      conclusions={[model.conclusion]}
      selectedConclusionId={model.conclusion.id}
      initialSection={section}
      sections={{
        conclusion: <div className="decision-inspector__answer-detail"><h3>{t('agents.DecisionInspector.conclusion_source')}</h3><p>{t('agents.DecisionInspector.the_answer_above_is_the_source_supplied_by_this_run')}</p><p>{t('agents.DecisionInspector.claims_are_not_derived_from_answer_text_or_citations')}</p></div>,
        claims: <EvidenceExplorer key={`claims-${claimId || 'none'}`} conclusion={model.conclusion} initialClaimId={claimId} />,
        evidence: <EvidenceInventory evidence={model.evidence} />,
        provenance: <EvidenceExplorer key={`provenance-${claimId || 'none'}`} conclusion={model.conclusion} initialClaimId={claimId} />,
      }}
    />
  </> : <section className="decision-inspector__empty" role="status"><h2>{t('agents.DecisionInspector.run_identity_unavailable')}</h2><p>{t('agents.DecisionInspector.the_source_did_not_provide_a_run_id_so_the_inspector_cannot_create_a_s')}</p></section>

  return <section className="decision-inspector-page" aria-label={t('agents.DecisionInspector.bago_decision_inspector')}>
    {!embedded&&<header className="decision-inspector-page__header">
      <div><p className="decision-inspector__eyebrow">{t('agents.DecisionInspector.governed_agent_run')}</p><h1>{t('agents.DecisionInspector.decision_inspector')}</h1><p>{t('agents.DecisionInspector.follow_the_source_conclusion_through_evidence_trace_actions_and_receip')}</p></div>
      <span className="decision-inspector-page__status">{runStatus}</span>
    </header>}
    {embedded&&<p className="decision-inspector-page__status">{runStatus}</p>}
    <details className="decision-inspector-page__identity"><summary>{t('agents.aux.context.technical')}</summary><dl><dt>{t('agents.ActionReview.run_id')}</dt><dd><code>{runId}</code></dd></dl></details>
    <nav className="decision-inspector-page__nav" aria-label={t('agents.DecisionInspector.inspector_views')}>
      {views.map(item => <button key={item.id} type="button" aria-current={view === item.id ? 'page' : undefined} onClick={() => { setView(item.id); setActionId(undefined) }}>{item.label}</button>)}
    </nav>
    {model.traceBindingIssue && <p role="status">{model.traceBindingIssue.kind === 'run_id_missing'
      ? t('agents.DecisionInspector.trace_run_p0_cannot_be_bound_because_the_selected_run_has_no_run_id_it', {p0: model.traceBindingIssue.actualRunId})
      : t('agents.DecisionInspector.trace_run_p0_does_not_match_selected_run_p1_its_correlations_are_hidde', {p0: model.traceBindingIssue.actualRunId, p1: model.traceBindingIssue.expectedRunId})}</p>}
    {view === 'overview' && conclusion}
    {view === 'trace' && <TraceTimelineView
      timeline={model.timeline}
      state={model.timeline ? { status: 'ready' } : model.traceBindingIssue?.kind === 'run_id_missing'
        ? { status: 'unverified', message: t('agents.DecisionInspector.trace_run_p0_cannot_be_bound_because_the_selected_run_has_no_run_id', {p0: model.traceBindingIssue.actualRunId}) }
        : model.traceBindingIssue
          ? { status: 'stale', message: t('agents.DecisionInspector.trace_run_p0_does_not_match_selected_run_p1', {p0: model.traceBindingIssue.actualRunId, p1: model.traceBindingIssue.expectedRunId}) }
        : { status: 'unknown', message: t('agents.DecisionInspector.the_source_did_not_provide_a_trace_for_this_run') }}
      onClaimNavigate={id => { setClaimId(id); setSection('claims'); setView('overview') }}
      onActionNavigate={id => { setActionId(id); setView('actions') }}
    />}
    {view === 'actions' && <>
      {actionId && !selectedAction && <p role="status">{t('agents.DecisionInspector.action')} {actionId} {t('agents.DecisionInspector.was_referenced_by_the_trace_but_was_not_included_in_the_supplied_actio')}</p>}
      <ActionReview bundle={actionBundle} />
    </>}
  </section>
}
