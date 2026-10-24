import {agentStateLabel} from '../../../components/AgentTaskForm'
import {useI18n, t, formatDate, formatNumber, apiError, errorMessage} from '../../../i18n'
import './ActionReview.css'
import type { ActionInspectionBundle, ProposedAction } from '../../../contracts/action/action'
import { validateActionBundle } from '../../../contracts/action/action'
import { InspectorStateView, type InspectorState } from '../shared/InspectorState'

export interface ActionReviewProps {
  bundle?: ActionInspectionBundle
  state?: InspectorState
}

const authorizationLabel: Record<ProposedAction['authorization']['state'], string> = {
  get authorized() { return t('agents.ActionReview.authorized_by_recorded_decision') },
  get rejected() { return t('agents.ActionReview.rejected_by_recorded_decision') },
  get requires_approval() { return t('agents.ActionReview.human_approval_required') },
  get expired() { return t('agents.ActionReview.authorization_expired') },
  get revoked() { return t('agents.ActionReview.authorization_revoked') },
  get unknown() { return t('agents.ActionReview.authorization_state_unknown') },
}

const receiptLabel: Record<ProposedAction['receiptLink']['state'], string> = {
  get matched() { return t('agents.ActionReview.matched_receipt') },
  get missing() { return t('agents.ActionReview.receipt_declared_but_unavailable') },
  get mismatch() { return t('agents.ActionReview.receipt_mismatch') },
  get unknown() { return t('agents.ActionReview.receipt_link_unknown') },
}

function display(value: string | undefined): string {
  return value || t('agents.AgentRunner.not_provided')
}

function readable(value: string | undefined): string {
  return value ? value.replace(/_/g, ' ') : t('agents.ActionReview.unknown')
}

/** Defend the display boundary as well as the upstream adapter's receipt link. */
function receiptState(action: ProposedAction): ProposedAction['receiptLink']['state'] {
  const { state, receiptId, receipt } = action.receiptLink
  if (state !== 'matched') return state
  if (!receipt || !receiptId || receiptId !== receipt.id || !action.requestId || !receipt.requestId || action.requestId !== receipt.requestId) return 'mismatch'
  if (action.authorization.permitId && action.authorization.permitId !== receipt.permitId) return 'mismatch'
  const effectType = (receipt as typeof receipt & { effectType?: string }).effectType
  if (action.effectType && effectType && action.effectType !== effectType) return 'mismatch'
  return 'matched'
}

function executionState(action: ProposedAction, linkedReceipt: ProposedAction['receiptLink']['state']): string {
  if (action.execution.state === 'succeeded' && linkedReceipt !== 'matched') return 'unverified'
  return action.execution.state
}

function ReceiptDetails({ action }: { action: ProposedAction }) {
  useI18n()
  const link = action.receiptLink
  const state = receiptState(action)
  return (
    <section className={`action-review__receipt action-review__receipt--${state}`} aria-label={t('agents.ActionReview.execution_receipt')}>
      <h4>{t('agents.ActionReview.receipt')}</h4>
      <p><strong>{receiptLabel[state]}</strong></p>
      {link.receiptId && <p>{t('agents.ActionReview.receipt_id')} <code>{link.receiptId}</code></p>}
      {state === 'missing' && <p>{t('agents.ActionReview.the_source_declares_a_receipt_but_no_matching_receipt_record_was_provi')}</p>}
      {state === 'mismatch' && <p>{t('agents.ActionReview.the_available_receipt_does_not_match_the_proposal_identifiers_its_outc')}</p>}
      {state === 'unknown' && <p>{t('agents.ActionReview.no_receipt_relationship_was_established_from_the_supplied_source_data')}</p>}
      {link.receipt && <>
        {'source' in link.receipt && <p>{t('agents.ActionReview.receipt_source')} {String(link.receipt.source)}</p>}
        <p>{t('agents.ActionReview.receipt_outcome')} {display(link.receipt.outcome)}</p>
        <p>{t('agents.ActionReview.request_id')} <code>{display(link.receipt.requestId)}</code></p>
        <p>{t('agents.ActionReview.permit_id')} <code>{display(link.receipt.permitId)}</code></p>
        {link.receipt.error && <p>{t('agents.ActionReview.receipt_error')} {link.receipt.error}</p>}
        {link.receipt.evidenceRefs.length > 0
          ? <ul aria-label={t('agents.ActionReview.receipt_evidence_references')}>{link.receipt.evidenceRefs.map((ref, index) => <li key={`${ref}-${index}`}><code>{ref}</code></li>)}</ul>
          : <p>{t('agents.ActionReview.receipt_evidence_references_none_provided')}</p>}
      </>}
      {executionState(action, state) === 'unverified' && <p role="status">{t('agents.ActionReview.the_source_reports_success_but_it_is_unverified_because_an_identity_ma')}</p>}
    </section>
  )
}

function ActionCard({ action, index }: { action: ProposedAction; index: number }) {
  useI18n()
  const title = action.id ? t('agents.ActionReview.action_p0', {p0: action.id}) : t('agents.ActionReview.proposed_action_p0_identifier_not_provided', {p0: index + 1})
  const linkedReceipt = receiptState(action)
  return (
    <article className="action-review__card" aria-labelledby={`action-title-${index}`}>
      <header>
        <h3 id={`action-title-${index}`}>{title}</h3>
        <p className="action-review__proposal-state">{t('agents.ActionReview.proposed_intent_display_only')}</p>
      </header>
      <dl className="action-review__facts">
        <div><dt>{t('agents.AgentRunner.run_id')}</dt><dd><code>{display(action.runId)}</code></dd></div>
        <div><dt>{t('agents.AgentRunner.request_id')}</dt><dd><code>{display(action.requestId)}</code></dd></div>
        <div><dt>{t('agents.ActionReview.tool')}</dt><dd>{display(action.toolName)}</dd></div>
        <div><dt>{t('agents.ActionReview.transport')}</dt><dd>{display(action.transport)}</dd></div>
        <div><dt>{t('agents.ActionReview.effect_type')}</dt><dd>{display(action.effectType)} {t('agents.ActionReview.risk')} {agentStateLabel(action.risk)}</dd></div>
        <div><dt>{t('agents.ActionReview.proposal_reason')}</dt><dd>{display(action.proposalReason)}</dd></div>
        <div><dt>{t('agents.ActionReview.approval_state')}</dt><dd>{action.approval === 'required' ? t('agents.ActionReview.required_by_recorded_decision') : action.approval === 'not_required' ? t('agents.ActionReview.not_required_by_recorded_decision') : t('agents.ActionReview.not_established')}</dd></div>
      </dl>
      {action.arguments && <p className="action-review__arguments-note">{t('agents.ActionReview.arguments_were_supplied_but_are_hidden_here_unless_a_source_provides_a')}</p>}

      <section className="action-review__ladder" aria-label={t('agents.ActionReview.authorization_and_execution_lifecycle')}>
        <h4>{t('agents.ActionReview.action_lifecycle')}</h4>
        <ol>
          <li><strong>{t('agents.ActionReview.capability')}</strong><span>{agentStateLabel(action.capability.state)}{action.capability.name ? ` · ${action.capability.name}` : ''}</span></li>
          <li><strong>{t('agents.ActionReview.eligibility')}</strong><span>{agentStateLabel(action.eligibility.state)}{action.eligibility.reason ? ` · ${action.eligibility.reason}` : ''}</span></li>
          <li><strong>{t('agents.ActionReview.authorization_decision')}</strong><span>{authorizationLabel[action.authorization.state] ?? t('agents.ActionReview.authorization_state_unknown')}</span>
            <span>{t('agents.ActionReview.permit_validity')} {agentStateLabel(action.authorization.permitValidity || 'unknown')}</span>
            <span>{t('agents.ActionReview.permit_id')} <code>{display(action.authorization.permitId)}</code></span>
            {action.authorization.actor && <span>{t('agents.ActionReview.actor')} {action.authorization.actor}</span>}
            {action.authorization.reason && <span>{t('agents.ActionReview.reason')} {action.authorization.reason}</span>}
          </li>
          <li><strong>{t('agents.ActionReview.availability')}</strong><span>{agentStateLabel(action.availability.state)}{action.availability.reason ? ` · ${action.availability.reason}` : ''}</span></li>
          <li><strong>{t('agents.ActionReview.execution')}</strong><span>{agentStateLabel(executionState(action, linkedReceipt))}</span>
            <span>{t('agents.ActionReview.call_recorded')} {action.execution.called === undefined ? t('agents.InspectorState.state_unknown') : action.execution.called ? t('agents.boolean.yes') : t('agents.boolean.no')}</span>
            <span>{t('agents.ActionReview.outcome')} {display(action.execution.outcome)}</span>
            {action.execution.error && <span>{t('agents.ActionReview.error')} {action.execution.error}</span>}
          </li>
        </ol>
      </section>

      <ReceiptDetails action={action} />

    </article>
  )
}

export function ActionReview({ bundle, state = { status: 'ready' } }: ActionReviewProps) {
  useI18n()
  if (state.status !== 'ready') return <section className="action-review"><h2>{t('agents.ActionReview.proposed_actions')}</h2><InspectorStateView state={state} /></section>
  if (!bundle) return <section className="action-review"><h2>{t('agents.ActionReview.proposed_actions')}</h2><InspectorStateView state={{ status: 'unknown', message: t('agents.ActionReview.action_proposal_data_was_not_provided_by_the_source') }} /></section>
  const errors = validateActionBundle(bundle).filter(error => !(
    error.includes('receipt') || error.includes('reports success without a matched receipt')
  ))
  if (errors.length > 0) return <section className="action-review"><h2>{t('agents.ActionReview.proposed_actions')}</h2><InspectorStateView state={{ status: 'unsupported', message: t('agents.ActionReview.action_data_is_invalid_or_unsupported_p0', {p0: errors.join('; ')}) }} /></section>
  if (bundle.actions.length === 0) return <section className="action-review"><h2>{t('agents.ActionReview.proposed_actions')}</h2><InspectorStateView state={{ status: 'empty', message: t('agents.ActionReview.this_run_has_no_proposed_actions') }} /></section>

  return <section className="action-review" aria-labelledby="action-review-title">
    <header className="action-review__header">
      <div><h2 id="action-review-title">{t('agents.ActionReview.proposed_actions')}</h2><p>{t('agents.ActionReview.inspection_only_a_recorded_authorization_decision_does_not_prove_execu')}</p></div>
      {bundle.runId && <p>{t('agents.ActionReview.run_id')} <code>{bundle.runId}</code></p>}
    </header>
    <div className="action-review__list">{bundle.actions.map((action, index) => <ActionCard key={action.id ?? `${action.requestId ?? 'unknown'}-${index}`} action={action} index={index} />)}</div>
  </section>
}
