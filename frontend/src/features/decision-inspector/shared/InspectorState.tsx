import {useI18n, t, formatDate, formatNumber, apiError, errorMessage} from '../../../i18n'
import './InspectorState.css'
import type { ReactNode } from 'react'

export type InspectorState =
  | { status: 'loading'; message?: string }
  | { status: 'empty'; message?: string }
  | { status: 'error'; message: string; onRetry?: () => void }
  | { status: 'unsupported'; message?: string }
  | { status: 'partial'; message: string }
  | { status: 'stale'; message: string }
  | { status: 'unverified'; message: string }
  | { status: 'unknown'; message?: string }
  | { status: 'ready' }

const defaultMessages: Record<Exclude<InspectorState['status'], 'ready'>, string> = {
  get loading() { return t('agents.InspectorState.loading_run_artifacts') },
  get empty() { return t('agents.InspectorState.no_artifacts_are_available_for_this_run') },
  get error() { return t('agents.InspectorState.the_requested_resource_could_not_be_loaded') },
  get unsupported() { return t('agents.InspectorState.this_data_type_is_not_supported_by_the_current_inspector') },
  get partial() { return t('agents.InspectorState.some_source_data_was_not_provided_or_is_unavailable') },
  get stale() { return t('agents.InspectorState.the_supplied_source_identity_does_not_match_the_expected_identity') },
  get unverified() { return t('agents.InspectorState.the_source_did_not_provide_enough_matching_identity_to_verify_this_res') },
  get unknown() { return t('agents.InspectorState.the_source_did_not_provide_enough_information_to_determine_this_state') },
}

const stateHeadings: Record<Exclude<InspectorState['status'], 'ready'>, string> = {
  get loading() { return t('agents.InspectorState.loading') },
  get empty() { return t('agents.InspectorState.nothing_to_inspect') },
  get error() { return t('agents.InspectorState.unable_to_load') },
  get unsupported() { return t('agents.InspectorState.unsupported_data') },
  get partial() { return t('agents.InspectorState.partial_data') },
  get stale() { return t('agents.InspectorState.stale_data') },
  get unverified() { return t('agents.InspectorState.unverified') },
  get unknown() { return t('agents.InspectorState.state_unknown') },
}

export function InspectorStateView({ state, children }: { state: InspectorState; children?: ReactNode }) {
  useI18n()
  if (state.status === 'ready') return <>{children}</>

  const message = state.status === 'error' ? state.message : state.message || defaultMessages[state.status]
  const liveRole = state.status === 'error' ? 'alert' : 'status'
  return (
    <section className={`decision-inspector-state decision-inspector-state--${state.status}`} role={liveRole} aria-live={state.status === 'error' ? 'assertive' : 'polite'}>
      <h2>{stateHeadings[state.status]}</h2>
      <p>{message}</p>
      {state.status === 'error' && state.onRetry && <button type="button" onClick={state.onRetry}>{t('agents.AgentEvaluationLab.retry')}</button>}
    </section>
  )
}

export type EvidenceSupport = 'supported' | 'unsupported' | 'missing' | 'stale' | 'contradictory' | 'unknown'

const supportLabels: Record<EvidenceSupport, string> = {
  get supported() { return t('agents.InspectorState.supported_by_linked_evidence') },
  get unsupported() { return t('agents.InspectorState.no_supporting_evidence_linked') },
  get missing() { return t('agents.InspectorState.referenced_evidence_is_unavailable') },
  get stale() { return t('agents.InspectorState.evidence_is_stale') },
  get contradictory() { return t('agents.InspectorState.conflicting_evidence_is_reported') },
  get unknown() { return t('agents.InspectorState.evidence_support_is_unknown') },
}

export function EvidenceSupportStatus({ status }: { status: EvidenceSupport }) {
  useI18n()
  return <span className={`decision-inspector-support decision-inspector-support--${status}`}>{supportLabels[status]}</span>
}

export const freshnessLabel = (freshness: 'current' | 'stale' | 'unknown'): string => ({
  current: t('agents.InspectorState.current'),
  stale: t('agents.InspectorState.stale'),
  unknown: t('agents.InspectorState.freshness_not_established'),
}[freshness])
