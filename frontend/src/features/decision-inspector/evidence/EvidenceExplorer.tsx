import { useMemo, useState } from 'react'
import { assessEvidenceFreshness, type DecisionConclusion, type DecisionClaim, type DecisionEvidence, type ExpectedEvidenceSnapshot, type EvidenceFreshness } from '../../../contracts/decision/evidence'
import { EvidenceSupportStatus, InspectorStateView, freshnessLabel, type EvidenceSupport, type InspectorState } from '../shared/InspectorState'
import './EvidenceExplorer.css'

export interface EvidenceExplorerProps {
  conclusion: DecisionConclusion
  expectedSnapshot?: ExpectedEvidenceSnapshot
  state?: InspectorState
  initialClaimId?: string
  initialEvidenceId?: string
}

const valueOrMissing = (value: string | undefined): string => value || 'Not provided'

function claimSupport(claim: DecisionClaim, evidenceById: Map<string, DecisionEvidence>): EvidenceSupport {
  if (claim.evidence.length === 0) return 'unsupported'
  const links = claim.evidence.map(link => ({ link, evidence: evidenceById.get(link.evidenceId) }))
  if (links.some(item => !item.evidence)) return 'missing'
  if (links.some(item => item.link.relation === 'contradicts')) return 'contradictory'
  if (links.some(item => item.link.relation === 'supports')) return 'supported'
  return 'unknown'
}

function ClaimRow({ claim, selected, support, onSelect }: {
  claim: DecisionClaim
  selected: boolean
  support: EvidenceSupport
  onSelect: () => void
}) {
  return <li className="evidence-explorer__claim">
    <button type="button" className="evidence-explorer__claim-button" aria-pressed={selected} onClick={onSelect}>
      <span className="evidence-explorer__claim-text">{claim.text || `Claim ${claim.id}`}</span>
      <EvidenceSupportStatus status={support} />
    </button>
    {claim.confidence === undefined
      ? <p className="evidence-explorer__metadata">Confidence not provided</p>
      : <p className="evidence-explorer__metadata">Confidence provided: {claim.confidence}</p>}
  </li>
}

function EvidenceDetails({ evidence, relation, claimId, freshness }: { evidence: DecisionEvidence; relation: string; claimId: string; freshness: EvidenceFreshness }) {
  return <article className="evidence-explorer__evidence-card" aria-labelledby="evidence-detail-title">
    <h4 id="evidence-detail-title">Evidence {valueOrMissing(evidence.id)}</h4>
    <p className="evidence-explorer__relation">Claim {claimId} relation: <strong>{relation.replace('_', ' ')}</strong></p>
    <p>{evidence.excerpt || 'No excerpt was provided.'}</p>
    <dl className="evidence-explorer__provenance">
      <div><dt>Artifact reference</dt><dd><code>{valueOrMissing(evidence.artifactRef)}</code></dd></div>
      <div><dt>Source identity</dt><dd><code>{valueOrMissing(evidence.sourceIdentity)}</code></dd></div>
      <div><dt>Snapshot source URI</dt><dd><code>{valueOrMissing(evidence.snapshot?.sourceUri)}</code></dd></div>
      <div><dt>Snapshot revision</dt><dd><code>{valueOrMissing(evidence.snapshot?.revision)}</code></dd></div>
      <div><dt>Document ID</dt><dd><code>{valueOrMissing(evidence.snapshot?.documentId)}</code></dd></div>
      <div><dt>Chunk ID</dt><dd><code>{valueOrMissing(evidence.snapshot?.chunkId)}</code></dd></div>
      <div><dt>Content fingerprint</dt><dd><code>{valueOrMissing(evidence.contentFingerprint)}</code></dd></div>
      <div><dt>Freshness</dt><dd>{freshnessLabel(freshness)}</dd></div>
    </dl>
  </article>
}

export function EvidenceExplorer({ conclusion, expectedSnapshot, state = { status: 'ready' }, initialClaimId, initialEvidenceId }: EvidenceExplorerProps) {
  const [claimId, setClaimId] = useState<string | undefined>(initialClaimId)
  const [evidenceId, setEvidenceId] = useState<string | undefined>(initialEvidenceId)
  const evidenceById = useMemo(() => new Map(conclusion.evidence.map(item => [item.id, item])), [conclusion.evidence])
  const selectedClaim = conclusion.claims.find(claim => claim.id === claimId)
  const selectedLink = selectedClaim?.evidence.find(link => link.evidenceId === evidenceId) ?? selectedClaim?.evidence[0]
  const selectedEvidence = selectedLink ? evidenceById.get(selectedLink.evidenceId) : undefined
  const selectedFreshness = selectedEvidence && (expectedSnapshot
    ? assessEvidenceFreshness(selectedEvidence.snapshot, expectedSnapshot)
    : selectedEvidence.freshness)
  const noClaims = conclusion.claims.length === 0

  return <section className="evidence-explorer" aria-labelledby="evidence-explorer-title">
    <header className="evidence-explorer__header">
      <h2 id="evidence-explorer-title">Claims and evidence</h2>
      <p>Conclusion: {conclusion.text || 'Not provided'}</p>
      <p className="evidence-explorer__metadata">Run ID: <code>{valueOrMissing(conclusion.runId)}</code> · Conclusion ID: <code>{conclusion.id || 'Not provided'}</code></p>
    </header>

    <InspectorStateView state={state}>
      {noClaims ? <section className="evidence-explorer__empty" aria-label="Claims unavailable">
        <h3>Claims not provided</h3>
        <p>The source did not provide a structured claim list. Citations are not converted into claims.</p>
      </section> : <div className="evidence-explorer__layout">
        <section aria-labelledby="claim-list-title">
          <h3 id="claim-list-title">Claims</h3>
          <ul className="evidence-explorer__claim-list">
            {conclusion.claims.map(claim => <ClaimRow
              key={claim.id}
              claim={claim}
              selected={selectedClaim?.id === claim.id}
              support={claimSupport(claim, evidenceById)}
              onSelect={() => { setClaimId(claim.id); setEvidenceId(undefined) }}
            />)}
          </ul>
        </section>

        {selectedClaim ? <section aria-labelledby="evidence-list-title">
          <h3 id="evidence-list-title">Evidence for selected claim</h3>
          <p className="evidence-explorer__metadata">Claim ID: <code>{selectedClaim.id}</code></p>
          {selectedClaim.evidence.length === 0 ? <div className="evidence-explorer__empty">
            <EvidenceSupportStatus status="unsupported" />
            <p>No supporting evidence linked to this claim.</p>
          </div> : <>
          {selectedClaim.evidence.every(link => link.relation === 'context_only' || link.relation === 'insufficient') && <p className="evidence-explorer__metadata">Linked records are context-only or marked insufficient; no explicit supporting relation was provided.</p>}
          <ul className="evidence-explorer__evidence-list">
            {selectedClaim.evidence.map((link, index) => {
              const evidence = evidenceById.get(link.evidenceId)
              return <li key={`${link.evidenceId}-${index}`}>
                {evidence ? <button type="button" className="evidence-explorer__evidence-button" aria-pressed={selectedLink === link} onClick={() => setEvidenceId(link.evidenceId)}>
                  <span>Evidence reference <code>{link.evidenceId}</code></span>
                  <span>Relation: {link.relation.replace('_', ' ')}</span>
                  <span>Freshness: {freshnessLabel(expectedSnapshot ? assessEvidenceFreshness(evidence.snapshot, expectedSnapshot) : evidence.freshness)}</span>
                </button> : <div className="evidence-explorer__missing" role="status">
                  <EvidenceSupportStatus status="missing" />
                  <p>Referenced evidence <code>{link.evidenceId || 'Not provided'}</code> is unavailable in the supplied evidence inventory.</p>
                  <p>Relation: {link.relation.replace('_', ' ')}</p>
                </div>}
              </li>
            })}
          </ul>
          {selectedEvidence && selectedLink && selectedFreshness && <EvidenceDetails evidence={selectedEvidence} relation={selectedLink.relation} claimId={selectedClaim.id} freshness={selectedFreshness} />}
          {selectedClaim.evidence.some(link => {
            const item = evidenceById.get(link.evidenceId)
            return item && (expectedSnapshot ? assessEvidenceFreshness(item.snapshot, expectedSnapshot) : item.freshness) === 'stale'
          }) && <p className="evidence-explorer__stale-note" role="status">At least one linked evidence snapshot is stale; it remains visible with its supplied identity.</p>}
          </>}
        </section> : <section className="evidence-explorer__empty" aria-label="Claim selection unavailable">
          <h3>Select a claim</h3>
          <p>No claim is selected. Choose a source-provided claim to inspect its evidence.</p>
        </section>}
      </div>}
    </InspectorStateView>
  </section>
}
