import { useMemo, useState } from 'react'
import { actionBundleFromAgentRun } from '../../../adapters/action/agentRun'
import { localTraceToTimeline } from '../../../adapters/trace/localTraceAdapter'
import { evidenceFromRetrievalHit, type DecisionConclusion, type DecisionEvidence } from '../../../contracts/decision/evidence'
import type { ActionInspectionBundle } from '../../../contracts/action/action'
import type { LocalTraceRecord, TraceTimeline } from '../../../contracts/trace/trace'
import { ActionReview } from '../actions/ActionReview'
import { EvidenceExplorer } from '../evidence/EvidenceExplorer'
import { InspectorShell, type InspectorSection } from '../shell/InspectorShell'
import { TraceTimeline as TraceTimelineView } from '../trace/TraceTimeline'
import './DecisionInspector.css'

export interface DecisionInspectorArtifacts {
  summary: Record<string, unknown>
  agent_run: Record<string, unknown>
  receipts: Record<string, unknown>
  trace: LocalTraceRecord
  evaluation: Record<string, unknown>
}

export interface DecisionInspectorModel {
  conclusion?: DecisionConclusion
  evidence: DecisionEvidence[]
  timeline?: TraceTimeline
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
  const trace = record(artifacts.trace)
  const timeline = trace && typeof trace.trace_id === 'string' && typeof trace.run_id === 'string' && Array.isArray(trace.events)
    ? localTraceToTimeline(trace as unknown as LocalTraceRecord)
    : undefined

  return {
    conclusion,
    evidence,
    timeline,
    actions: actionBundleFromAgentRun(runBoundActionSource(run)),
  }
}

type InspectorView = 'overview' | 'trace' | 'actions'

const views: Array<{ id: InspectorView; label: string }> = [
  { id: 'overview', label: 'Decision' },
  { id: 'trace', label: 'Trace' },
  { id: 'actions', label: 'Actions' },
]

function EvidenceInventory({ evidence }: { evidence: DecisionEvidence[] }) {
  if (evidence.length === 0) return <p role="status">No citation or retrieval evidence was provided by this run.</p>
  return <section className="decision-inspector__inventory" aria-label="Retrieved evidence references">
    <p>These references were retrieved for the run. The source did not provide structured claim links, so support is not inferred.</p>
    <ul>{evidence.map((item, index) => <li key={`${item.id}-${index}`}>
      <h3>Reference {index + 1}</h3>
      <p><code>{item.artifactRef || item.id || 'Reference not provided'}</code></p>
      <dl>
        <div><dt>Source</dt><dd><code>{item.sourceIdentity || item.snapshot?.sourceUri || 'Not provided'}</code></dd></div>
        <div><dt>Revision</dt><dd>{item.snapshot?.revision || 'Not provided'}</dd></div>
        <div><dt>Freshness</dt><dd>{item.freshness === 'unknown' ? 'Not established' : item.freshness}</dd></div>
        <div><dt>Claim relation</dt><dd>Not provided</dd></div>
      </dl>
    </li>)}</ul>
  </section>
}

export function DecisionInspector({ artifacts }: { artifacts: DecisionInspectorArtifacts }) {
  const [view, setView] = useState<InspectorView>('overview')
  const [section, setSection] = useState<InspectorSection>('conclusion')
  const [claimId, setClaimId] = useState<string | undefined>()
  const [actionId, setActionId] = useState<string | undefined>()
  const model = useMemo(() => decisionInspectorModel(artifacts), [artifacts])
  const runId = model.conclusion?.runId || 'Not provided'
  const selectedAction = actionId ? model.actions.actions.find(action => action.id === actionId) : undefined
  const actionBundle = selectedAction ? { ...model.actions, actions: [selectedAction] } : model.actions
  const runStatus = text(artifacts.agent_run.status) || 'Not provided'

  const conclusion = model.conclusion ? <>
    <section className="decision-inspector__summary" aria-label="Agent conclusion">
      <p className="decision-inspector__eyebrow">Source supplied conclusion · run {runId}</p>
      <h2>{text(artifacts.agent_run.query) || 'Query not provided'}</h2>
      <p className="decision-inspector__answer">{model.conclusion.text || 'Conclusion text not provided.'}</p>
    </section>
    <div className="decision-inspector__summary-grid">
      <div><span>Evidence references</span><strong>{model.evidence.length}</strong></div>
      <div><span>Structured claims</span><strong>{model.conclusion.claims.length ? model.conclusion.claims.length : 'Not provided'}</strong></div>
      <div><span>Trace events</span><strong>{model.timeline?.events.length ?? 'Not provided'}</strong></div>
      <div><span>Proposed actions</span><strong>{model.actions.actions.length}</strong></div>
    </div>
    <InspectorShell
      key={section}
      conclusions={[model.conclusion]}
      selectedConclusionId={model.conclusion.id}
      initialSection={section}
      sections={{
        conclusion: <div className="decision-inspector__answer-detail"><h3>Conclusion source</h3><p>The answer above is the source supplied by this run.</p><p>Claims are not derived from answer text or citations.</p></div>,
        claims: <EvidenceExplorer key={`claims-${claimId || 'none'}`} conclusion={model.conclusion} initialClaimId={claimId} />,
        evidence: <EvidenceInventory evidence={model.evidence} />,
        provenance: <EvidenceExplorer key={`provenance-${claimId || 'none'}`} conclusion={model.conclusion} initialClaimId={claimId} />,
      }}
    />
  </> : <section className="decision-inspector__empty" role="status"><h2>Run identity unavailable</h2><p>The source did not provide a run ID, so the inspector cannot create a stable conclusion identity.</p></section>

  return <section className="decision-inspector-page" aria-label="BAGO decision inspector">
    <header className="decision-inspector-page__header">
      <div><p className="decision-inspector__eyebrow">Governed agent run</p><h1>Decision Inspector</h1><p>Follow the source conclusion through evidence, trace, actions and receipts.</p><code>Run ID: {runId}</code></div>
      <span className="decision-inspector-page__status">{runStatus}</span>
    </header>
    <nav className="decision-inspector-page__nav" aria-label="Inspector views">
      {views.map(item => <button key={item.id} type="button" aria-current={view === item.id ? 'page' : undefined} onClick={() => { setView(item.id); setActionId(undefined) }}>{item.label}</button>)}
    </nav>
    {view === 'overview' && conclusion}
    {view === 'trace' && <TraceTimelineView
      timeline={model.timeline}
      state={model.timeline ? { status: 'ready' } : { status: 'unknown', message: 'The source did not provide a trace for this run.' }}
      onClaimNavigate={id => { setClaimId(id); setSection('claims'); setView('overview') }}
      onActionNavigate={id => { setActionId(id); setView('actions') }}
    />}
    {view === 'actions' && <>
      {actionId && !selectedAction && <p role="status">Action {actionId} was referenced by the trace but was not included in the supplied action data.</p>}
      <ActionReview bundle={actionBundle} />
    </>}
  </section>
}
