import './CapabilityManager.css'
import { useCallback, useEffect, useState } from 'react'

export type Capability = {
  id: string
  name: string
  provider: string
  effect: string
  status: string
  integration: string
  summary: string
  limits: Record<string, unknown>
  source_fingerprints: Record<string, string | null>
  source_available: boolean
  fingerprint: string
}

export type CapabilityProposal = {
  id: string
  capability_id: string
  capability_fingerprint: string
  effect: string
  summary: string
  requested_scope: string
  conversation_id: string | null
  status: 'PENDING_REVIEW' | 'CANCELLED' | 'EXPIRED'
  revision: number
  created_at: string
  expires_at: string
  updated_at: string
}

export async function capabilityResponseError(response: Response): Promise<string> {
  try {
    const body = await response.json()
    const detail = body?.detail
    if (typeof detail === 'string') return detail
    if (typeof detail?.message === 'string') return detail.message
  } catch { /* use the status when the response has no JSON error */ }
  return `Request failed (${response.status}).`
}

export default function CapabilityManager() {
  const [capabilities, setCapabilities] = useState<Capability[]>([])
  const [proposals, setProposals] = useState<CapabilityProposal[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [canceling, setCanceling] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [catalogResponse, proposalResponse] = await Promise.all([
        fetch('/api/capabilities'),
        fetch('/api/capabilities/proposals?status=all&limit=100'),
      ])
      if (!catalogResponse.ok) throw new Error(await capabilityResponseError(catalogResponse))
      if (!proposalResponse.ok) throw new Error(await capabilityResponseError(proposalResponse))
      const catalog = await catalogResponse.json()
      const proposalData = await proposalResponse.json()
      setCapabilities(Array.isArray(catalog.capabilities) ? catalog.capabilities : [])
      setProposals(Array.isArray(proposalData.proposals) ? proposalData.proposals : [])
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Capability data could not be loaded.')
    } finally { setLoading(false) }
  }, [])

  useEffect(() => { void refresh() }, [refresh])

  const cancelProposal = async (proposal: CapabilityProposal) => {
    setCanceling(proposal.id)
    setError('')
    try {
      const response = await fetch(`/api/capabilities/proposals/${encodeURIComponent(proposal.id)}/cancel`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ revision: proposal.revision }),
      })
      if (!response.ok) throw new Error(await capabilityResponseError(response))
      const result = await response.json()
      await refresh()
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Proposal could not be cancelled.')
      await refresh()
    } finally { setCanceling(null) }
  }

  return (
    <section className="capability-manager" aria-label="Capabilities">
      {loading && <p className="capability-state" role="status">Loading capability catalog and proposals…</p>}
      {error && <p className="capability-error" role="alert">{error}</p>}
      {!loading && !error && capabilities.length === 0 && <p className="capability-state">No capability records were returned by the backend.</p>}
      {!loading && !error && capabilities.length > 0 && <div className="capability-grid">
        {capabilities.map((capability) => <article className="capability-card" key={capability.id}>
          <div className="capability-card-heading"><div><h3>{capability.name}</h3><code>{capability.id}</code></div><span className={`capability-status status-${capability.status.toLowerCase()}`}>{capability.status}</span></div>
          <p>{capability.summary}</p>
          <dl><div><dt>Effect</dt><dd>{capability.effect}</dd></div><div><dt>Provider</dt><dd>{capability.provider}</dd></div><div><dt>Integration</dt><dd>{capability.integration}</dd></div><div><dt>Source check</dt><dd>{capability.source_available ? 'Available' : 'Missing source'}</dd></div></dl>
          <details><summary>Limits and source fingerprints</summary><pre>{JSON.stringify({ limits: capability.limits, source_fingerprints: capability.source_fingerprints }, null, 2)}</pre></details>
        </article>)}
      </div>}
      <section className={`capability-proposals ${!loading && !error && proposals.length === 0 ? 'is-empty' : ''}`} aria-labelledby="capability-proposals-title">
        <div className="capability-section-heading">
          <div className="capability-section-title"><h3 id="capability-proposals-title">Proposals</h3><span>{loading ? '—' : proposals.length}</span></div>
          {!loading && !error && proposals.length === 0 && <p className="capability-empty-proposals">No saved proposals. <span>Ask the chat to prepare one for review.</span></p>}
        </div>
        <div className="capability-proposal-list">{proposals.map((proposal) => <article className="capability-proposal" key={proposal.id}>
          <div className="capability-card-heading"><div><h4>{capabilities.find((item) => item.id === proposal.capability_id)?.name ?? proposal.capability_id}</h4><code>{proposal.id}</code></div><span className="capability-status">{proposal.status}</span></div>
          <p>{proposal.summary}</p><p><strong>Requested scope:</strong> {proposal.requested_scope}</p>
          <p className="capability-proposal-meta">Effect: {proposal.effect} · Revision {proposal.revision} · Expires {new Date(proposal.expires_at).toLocaleString()}</p>
          {proposal.conversation_id && <p className="capability-proposal-meta">Conversation: <code>{proposal.conversation_id}</code></p>}
          {proposal.status === 'PENDING_REVIEW' && <button type="button" className="secondary-action" disabled={canceling === proposal.id} onClick={() => void cancelProposal(proposal)}>{canceling === proposal.id ? 'Cancelling…' : 'Cancel proposal'}</button>}
        </article>)}</div>
      </section>
      <p className="capability-footer">A proposal records a request for review only. It grants no permission, creates no job, and does not execute code.</p>
    </section>
  )
}
