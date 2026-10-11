import type { ActionInspectionBundle, ProposedAction } from '../../../contracts/action/action'
import { validateActionBundle } from '../../../contracts/action/action'
import { InspectorStateView, type InspectorState } from '../shared/InspectorState'
import './ActionReview.css'

export interface ActionReviewProps {
  bundle?: ActionInspectionBundle
  state?: InspectorState
}

const authorizationLabel: Record<ProposedAction['authorization']['state'], string> = {
  authorized: 'Authorized by recorded decision',
  rejected: 'Rejected by recorded decision',
  requires_approval: 'Human approval required',
  unknown: 'Authorization state unknown',
}

const receiptLabel: Record<ProposedAction['receiptLink']['state'], string> = {
  matched: 'Matched receipt',
  missing: 'Receipt declared but unavailable',
  mismatch: 'Receipt mismatch',
  unknown: 'Receipt link unknown',
}

function display(value: string | undefined): string {
  return value || 'Not provided'
}

function ReceiptDetails({ action }: { action: ProposedAction }) {
  const link = action.receiptLink
  return (
    <section className={`action-review__receipt action-review__receipt--${link.state}`} aria-label="Execution receipt">
      <h4>Receipt</h4>
      <p><strong>{receiptLabel[link.state]}</strong></p>
      {link.receiptId && <p>Receipt ID: <code>{link.receiptId}</code></p>}
      {link.state === 'missing' && <p>The source declares a receipt, but no matching receipt record was provided.</p>}
      {link.state === 'mismatch' && <p>The available receipt does not match the proposal identifiers. Its outcome is not accepted as this action's receipt.</p>}
      {link.state === 'unknown' && <p>No receipt relationship was established from the supplied source data.</p>}
      {link.receipt && <>
        <p>Receipt outcome: {display(link.receipt.outcome)}</p>
        <p>Request ID: <code>{display(link.receipt.requestId)}</code></p>
        <p>Permit ID: <code>{display(link.receipt.permitId)}</code></p>
        {link.receipt.error && <p>Receipt error: {link.receipt.error}</p>}
        {link.receipt.evidenceRefs.length > 0
          ? <ul aria-label="Receipt evidence references">{link.receipt.evidenceRefs.map((ref, index) => <li key={`${ref}-${index}`}><code>{ref}</code></li>)}</ul>
          : <p>Receipt evidence references: none provided.</p>}
      </>}
      {action.execution.state === 'unverified' && <p role="alert">The source reports success, but it is unverified because a matching receipt is unavailable.</p>}
    </section>
  )
}

function ActionCard({ action, index }: { action: ProposedAction; index: number }) {
  const title = action.id ? `Action ${action.id}` : `Proposed action ${index + 1} (identifier not provided)`
  return (
    <article className="action-review__card" aria-labelledby={`action-title-${index}`}>
      <header>
        <h3 id={`action-title-${index}`}>{title}</h3>
        <p className="action-review__proposal-state">Proposed intent · display only</p>
      </header>
      <dl className="action-review__facts">
        <div><dt>Run ID</dt><dd><code>{display(action.runId)}</code></dd></div>
        <div><dt>Request ID</dt><dd><code>{display(action.requestId)}</code></dd></div>
        <div><dt>Tool</dt><dd>{display(action.toolName)}</dd></div>
        <div><dt>Transport</dt><dd>{display(action.transport)}</dd></div>
        <div><dt>Effect type</dt><dd>{display(action.effectType)} · risk: {action.risk.replace('_', ' ')}</dd></div>
        <div><dt>Proposal reason</dt><dd>{display(action.proposalReason)}</dd></div>
      </dl>
      {action.arguments && <details>
        <summary>Inspect supplied arguments</summary>
        <pre>{JSON.stringify(action.arguments, null, 2)}</pre>
      </details>}

      <section className="action-review__ladder" aria-label="Authorization and execution lifecycle">
        <h4>Authorization ladder</h4>
        <ol>
          <li><strong>Capability</strong><span>{action.capability.state}{action.capability.name ? ` · ${action.capability.name}` : ''}</span></li>
          <li><strong>Eligibility</strong><span>{action.eligibility.state}{action.eligibility.reason ? ` · ${action.eligibility.reason}` : ''}</span></li>
          <li><strong>Authorization</strong><span>{authorizationLabel[action.authorization.state]}</span>
            <span>Permit validity: {action.authorization.permitValidity.replace('_', ' ')}</span>
            <span>Permit ID: <code>{display(action.authorization.permitId)}</code></span>
            {action.authorization.actor && <span>Actor: {action.authorization.actor}</span>}
            {action.authorization.reason && <span>Reason: {action.authorization.reason}</span>}
          </li>
          <li><strong>Availability</strong><span>{action.availability.state}{action.availability.reason ? ` · ${action.availability.reason}` : ''}</span></li>
          <li><strong>Execution</strong><span>{action.execution.state.replace('_', ' ')}</span>
            <span>Call recorded: {action.execution.called === undefined ? 'unknown' : action.execution.called ? 'yes' : 'no'}</span>
            <span>Outcome: {display(action.execution.outcome)}</span>
            {action.execution.error && <span>Error: {action.execution.error}</span>}
          </li>
        </ol>
      </section>

      <ReceiptDetails action={action} />

      <section className="action-review__controls" aria-label="Review controls">
        <p>Review controls are unavailable in this read-only inspector. No approval, rejection, or execution was submitted.</p>
        <div>
          <button type="button" disabled aria-describedby={`review-note-${index}`}>Approve proposal</button>
          <button type="button" disabled aria-describedby={`review-note-${index}`}>Reject proposal</button>
          <button type="button" disabled aria-describedby={`review-note-${index}`}>Request evidence</button>
        </div>
        <span id={`review-note-${index}`} className="action-review__sr-only">These controls do not submit a decision or execute the proposed action.</span>
      </section>
    </article>
  )
}

export function ActionReview({ bundle, state = { status: 'ready' } }: ActionReviewProps) {
  if (state.status !== 'ready') return <section className="action-review"><h2>Proposed actions</h2><InspectorStateView state={state} /></section>
  if (!bundle) return <section className="action-review"><h2>Proposed actions</h2><InspectorStateView state={{ status: 'unknown', message: 'Action proposal data was not provided by the source.' }} /></section>
  const errors = validateActionBundle(bundle)
  if (errors.length > 0) return <section className="action-review"><h2>Proposed actions</h2><InspectorStateView state={{ status: 'unsupported', message: `Action data is invalid or unsupported: ${errors.join('; ')}` }} /></section>
  if (bundle.actions.length === 0) return <section className="action-review"><h2>Proposed actions</h2><InspectorStateView state={{ status: 'empty', message: 'This run has no proposed actions.' }} /></section>

  return <section className="action-review" aria-labelledby="action-review-title">
    <header className="action-review__header">
      <div><h2 id="action-review-title">Proposed actions</h2><p>Inspection only; proposal, authorization, execution, and receipt are separate states.</p></div>
      {bundle.runId && <p>Run ID: <code>{bundle.runId}</code></p>}
    </header>
    <div className="action-review__list">{bundle.actions.map((action, index) => <ActionCard key={action.id ?? `${action.requestId ?? 'unknown'}-${index}`} action={action} index={index} />)}</div>
  </section>
}
