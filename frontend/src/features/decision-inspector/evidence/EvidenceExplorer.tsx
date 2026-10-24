import {agentStateLabel} from '../../../components/AgentTaskForm'
import {useI18n, t, formatDate, formatNumber, apiError, errorMessage} from '../../../i18n'
import './EvidenceExplorer.css'
import { useMemo, useState } from 'react'
import { assessEvidenceFreshness, type DecisionConclusion, type DecisionClaim, type DecisionEvidence, type ExpectedEvidenceSnapshot, type EvidenceFreshness } from '../../../contracts/decision/evidence'
import { EvidenceSupportStatus, InspectorStateView, freshnessLabel, type EvidenceSupport, type InspectorState } from '../shared/InspectorState'

export interface EvidenceExplorerProps {
  conclusion: DecisionConclusion
  expectedSnapshot?: ExpectedEvidenceSnapshot
  state?: InspectorState
  initialClaimId?: string
  initialEvidenceId?: string
}

const valueOrMissing = (value: string | undefined): string => value || t('agents.AgentRunner.not_provided')

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
  useI18n()
  return <li className="evidence-explorer__claim">
    <button type="button" className="evidence-explorer__claim-button" aria-pressed={selected} onClick={onSelect}>
      <span className="evidence-explorer__claim-text">{claim.text || t('agents.EvidenceExplorer.claim_p0', {p0: claim.id})}</span>
      <EvidenceSupportStatus status={support} />
    </button>
    {claim.confidence === undefined
      ? <p className="evidence-explorer__metadata">{t('agents.EvidenceExplorer.confidence_not_provided')}</p>
      : <p className="evidence-explorer__metadata">{t('agents.EvidenceExplorer.confidence_provided')} {claim.confidence}</p>}
  </li>
}

function EvidenceDetails({ evidence, relation, claimId, freshness }: { evidence: DecisionEvidence; relation: string; claimId: string; freshness: EvidenceFreshness }) {
  useI18n()
  return <article className="evidence-explorer__evidence-card" aria-labelledby="evidence-detail-title">
    <h4 id="evidence-detail-title">{t('agents.EvidenceExplorer.evidence')} {valueOrMissing(evidence.id)}</h4>
    <p className="evidence-explorer__relation">{t('agents.EvidenceExplorer.claim')} {claimId} {t('agents.EvidenceExplorer.relation')} <strong>{agentStateLabel(relation)}</strong></p>
    <p>{evidence.excerpt || t('agents.EvidenceExplorer.no_excerpt_was_provided')}</p>
    <dl className="evidence-explorer__provenance">
      <div><dt>{t('agents.EvidenceExplorer.artifact_reference')}</dt><dd><code>{valueOrMissing(evidence.artifactRef)}</code></dd></div>
      <div><dt>{t('agents.EvidenceExplorer.source_identity')}</dt><dd><code>{valueOrMissing(evidence.sourceIdentity)}</code></dd></div>
      <div><dt>{t('agents.EvidenceExplorer.snapshot_source_uri')}</dt><dd><code>{valueOrMissing(evidence.snapshot?.sourceUri)}</code></dd></div>
      <div><dt>{t('agents.EvidenceExplorer.snapshot_revision')}</dt><dd><code>{valueOrMissing(evidence.snapshot?.revision)}</code></dd></div>
      <div><dt>{t('agents.EvidenceExplorer.document_id')}</dt><dd><code>{valueOrMissing(evidence.snapshot?.documentId)}</code></dd></div>
      <div><dt>{t('agents.EvidenceExplorer.chunk_id')}</dt><dd><code>{valueOrMissing(evidence.snapshot?.chunkId)}</code></dd></div>
      <div><dt>{t('agents.EvidenceExplorer.content_fingerprint')}</dt><dd><code>{valueOrMissing(evidence.contentFingerprint)}</code></dd></div>
      <div><dt>{t('agents.EvidenceExplorer.freshness')}</dt><dd>{freshnessLabel(freshness)}</dd></div>
    </dl>
  </article>
}

function UnlinkedEvidenceInventory({ evidence, linkedIds }: { evidence: DecisionEvidence[]; linkedIds: Set<string> }) {
  useI18n()
  const unlinked = evidence.filter(item => !linkedIds.has(item.id))
  return <section className="evidence-explorer__unlinked" aria-label={t('agents.EvidenceExplorer.unlinked_evidence_references')}>
    <h3>{t('agents.EvidenceExplorer.evidence_without_a_claim_link')}</h3>
    {unlinked.length === 0 ? <p role="status">{t('agents.EvidenceExplorer.no_unlinked_evidence_references_were_supplied')}</p> : <>
      <p>{t('agents.EvidenceExplorer.these_source_provided_references_are_retained_but_the_source_supplied_')}</p>
      <ul className="evidence-explorer__unlinked-list">{unlinked.map((item, index) => <li key={`${item.id}-${index}`}>
        <h4>{t('agents.EvidenceExplorer.evidence_reference')} {valueOrMissing(item.id)}</h4>
        <dl className="evidence-explorer__provenance">
          <div><dt>{t('agents.EvidenceExplorer.artifact_reference')}</dt><dd><code>{valueOrMissing(item.artifactRef || item.id)}</code></dd></div>
          <div><dt>{t('agents.EvidenceExplorer.source_identity')}</dt><dd><code>{valueOrMissing(item.sourceIdentity)}</code></dd></div>
          <div><dt>{t('agents.EvidenceExplorer.snapshot_revision')}</dt><dd>{valueOrMissing(item.snapshot?.revision)}</dd></div>
          <div><dt>{t('agents.EvidenceExplorer.freshness')}</dt><dd>{freshnessLabel(item.freshness)}</dd></div>
        </dl>
        <p>{t('agents.EvidenceExplorer.claim_relation_not_provided')}</p>
      </li>)}</ul>
    </>}
  </section>
}

export function EvidenceExplorer({ conclusion, expectedSnapshot, state = { status: 'ready' }, initialClaimId, initialEvidenceId }: EvidenceExplorerProps) {
  useI18n()
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
  const linkedEvidenceIds = new Set(conclusion.claims.flatMap(claim => claim.evidence.map(link => link.evidenceId)))

  return <section className="evidence-explorer" aria-labelledby="evidence-explorer-title">
    <header className="evidence-explorer__header">
      <h2 id="evidence-explorer-title">{t('agents.EvidenceExplorer.claims_and_evidence')}</h2>
      <p>{t('agents.EvidenceExplorer.conclusion')} {conclusion.text || t('agents.AgentRunner.not_provided')}</p>
      <p className="evidence-explorer__metadata">{t('agents.ActionReview.run_id')} <code>{valueOrMissing(conclusion.runId)}</code> {t('agents.EvidenceExplorer.conclusion_id')} <code>{conclusion.id || t('agents.AgentRunner.not_provided')}</code></p>
    </header>

    <InspectorStateView state={state}>
      {noClaims ? <>
        <section className="evidence-explorer__empty" aria-label={t('agents.EvidenceExplorer.claims_unavailable')}>
          <h3>{t('agents.EvidenceExplorer.claims_not_provided')}</h3>
          <p>{t('agents.EvidenceExplorer.the_source_did_not_provide_a_structured_claim_list_citations_are_not_c')}</p>
        </section>
        <UnlinkedEvidenceInventory evidence={conclusion.evidence} linkedIds={linkedEvidenceIds} />
      </> : <>
      <div className="evidence-explorer__layout">
        <section aria-labelledby="claim-list-title">
          <h3 id="claim-list-title">{t('agents.EvidenceExplorer.claims')}</h3>
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
          <h3 id="evidence-list-title">{t('agents.EvidenceExplorer.evidence_for_selected_claim')}</h3>
          <p className="evidence-explorer__metadata">{t('agents.EvidenceExplorer.claim_id')} <code>{selectedClaim.id}</code></p>
          {selectedClaim.evidence.length === 0 ? <div className="evidence-explorer__empty">
            <EvidenceSupportStatus status="unsupported" />
            <p>{t('agents.EvidenceExplorer.no_supporting_evidence_linked_to_this_claim')}</p>
          </div> : <>
          {selectedClaim.evidence.every(link => link.relation === 'context_only' || link.relation === 'insufficient') && <p className="evidence-explorer__metadata">{t('agents.EvidenceExplorer.linked_records_are_context_only_or_marked_insufficient_no_explicit_sup')}</p>}
          <ul className="evidence-explorer__evidence-list">
            {selectedClaim.evidence.map((link, index) => {
              const evidence = evidenceById.get(link.evidenceId)
              return <li key={`${link.evidenceId}-${index}`}>
                {evidence ? <button type="button" className="evidence-explorer__evidence-button" aria-pressed={selectedLink === link} onClick={() => setEvidenceId(link.evidenceId)}>
                  <span>{t('agents.EvidenceExplorer.evidence_reference')} <code>{link.evidenceId}</code></span>
                  <span>{t('agents.EvidenceExplorer.relation_2')} {agentStateLabel(link.relation)}</span>
                  <span>{t('agents.EvidenceExplorer.freshness_2')} {freshnessLabel(expectedSnapshot ? assessEvidenceFreshness(evidence.snapshot, expectedSnapshot) : evidence.freshness)}</span>
                </button> : <div className="evidence-explorer__missing" role="status">
                  <EvidenceSupportStatus status="missing" />
                  <p>{t('agents.EvidenceExplorer.referenced_evidence')} <code>{link.evidenceId || t('agents.AgentRunner.not_provided')}</code> {t('agents.EvidenceExplorer.is_unavailable_in_the_supplied_evidence_inventory')}</p>
                  <p>{t('agents.EvidenceExplorer.relation_2')} {agentStateLabel(link.relation)}</p>
                </div>}
              </li>
            })}
          </ul>
          {selectedEvidence && selectedLink && selectedFreshness && <EvidenceDetails evidence={selectedEvidence} relation={selectedLink.relation} claimId={selectedClaim.id} freshness={selectedFreshness} />}
          {selectedClaim.evidence.some(link => {
            const item = evidenceById.get(link.evidenceId)
            return item && (expectedSnapshot ? assessEvidenceFreshness(item.snapshot, expectedSnapshot) : item.freshness) === 'stale'
          }) && <p className="evidence-explorer__stale-note" role="status">{t('agents.EvidenceExplorer.at_least_one_linked_evidence_snapshot_is_stale_it_remains_visible_with')}</p>}
          </>}
        </section> : <section className="evidence-explorer__empty" aria-label={t('agents.EvidenceExplorer.claim_selection_unavailable')}>
          <h3>{t('agents.EvidenceExplorer.select_a_claim')}</h3>
          <p>{t('agents.EvidenceExplorer.no_claim_is_selected_choose_a_source_provided_claim_to_inspect_its_evi')}</p>
        </section>}
      </div>
      <UnlinkedEvidenceInventory evidence={conclusion.evidence} linkedIds={linkedEvidenceIds} />
      </>}
    </InspectorStateView>
  </section>
}
