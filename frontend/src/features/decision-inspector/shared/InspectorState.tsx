import type { ReactNode } from 'react'
import './InspectorState.css'

export type InspectorState =
  | { status: 'loading'; message?: string }
  | { status: 'empty'; message?: string }
  | { status: 'error'; message: string; onRetry?: () => void }
  | { status: 'unsupported'; message?: string }
  | { status: 'unknown'; message?: string }
  | { status: 'ready' }

const defaultMessages: Record<Exclude<InspectorState['status'], 'ready'>, string> = {
  loading: 'Loading run artifacts',
  empty: 'No artifacts are available for this run.',
  error: 'The requested resource could not be loaded.',
  unsupported: 'This data type is not supported by the current inspector.',
  unknown: 'The source did not provide enough information to determine this state.',
}

export function InspectorStateView({ state, children }: { state: InspectorState; children?: ReactNode }) {
  if (state.status === 'ready') return <>{children}</>

  const message = state.status === 'error' ? state.message : state.message || defaultMessages[state.status]
  const liveRole = state.status === 'error' ? 'alert' : 'status'
  return (
    <section className={`decision-inspector-state decision-inspector-state--${state.status}`} role={liveRole} aria-live={state.status === 'error' ? 'assertive' : 'polite'}>
      <h2>{state.status === 'loading' ? 'Loading' : state.status === 'empty' ? 'Nothing to inspect' : state.status === 'error' ? 'Unable to load' : state.status === 'unsupported' ? 'Unsupported data' : 'State unknown'}</h2>
      <p>{message}</p>
      {state.status === 'error' && state.onRetry && <button type="button" onClick={state.onRetry}>Retry</button>}
    </section>
  )
}

export type EvidenceSupport = 'supported' | 'unsupported' | 'missing' | 'stale' | 'contradictory' | 'unknown'

const supportLabels: Record<EvidenceSupport, string> = {
  supported: 'Supported by linked evidence',
  unsupported: 'No supporting evidence linked',
  missing: 'Referenced evidence is unavailable',
  stale: 'Evidence is stale',
  contradictory: 'Conflicting evidence is reported',
  unknown: 'Evidence support is unknown',
}

export function EvidenceSupportStatus({ status }: { status: EvidenceSupport }) {
  return <span className={`decision-inspector-support decision-inspector-support--${status}`}>{supportLabels[status]}</span>
}

export const freshnessLabel = (freshness: 'current' | 'stale' | 'unknown'): string => ({
  current: 'Current',
  stale: 'Stale',
  unknown: 'Freshness not established',
}[freshness])
