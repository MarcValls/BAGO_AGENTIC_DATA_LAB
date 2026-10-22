import './CapabilityManager.css'
import { useCallback, useEffect, useState } from 'react'
import ExternalConnections from './ExternalConnections'

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

type McpReceipt = Record<string, unknown> & { receipt_id?: string }
type McpFixtureResult = {
  run_id: string
  status: string
  transport: string
  source_kind: string
  server: string
  discovered: Array<{ name: string; fingerprint: string }>
  registered: Array<{ name: string; effect_type: string }>
  read_call: { receipt_id: string; decision: string; actual_effect: { called: boolean }; receipt?: McpReceipt }
  write_call: { receipt_id: string; decision: string; actual_effect: { called: boolean }; receipt?: McpReceipt }
  trace: { trace_id: string; events: unknown[] }
  evidence: { path: string; sha256: string }
}

function hasMcpFixtureResult(value: unknown): value is McpFixtureResult {
  if (!value || typeof value !== 'object') return false
  const result = value as Partial<McpFixtureResult>
  return typeof result.run_id === 'string' && result.status === 'completed'
    && result.transport === 'stdio' && result.source_kind === 'repository_local_fixture'
    && result.server === 'bago-local-demo'
    && Array.isArray(result.discovered) && result.discovered.every((tool) => typeof tool?.name === 'string' && typeof tool?.fingerprint === 'string')
    && Array.isArray(result.registered) && result.registered.every((tool) => typeof tool?.name === 'string' && typeof tool?.effect_type === 'string')
    && typeof result.read_call?.receipt_id === 'string' && typeof result.read_call?.decision === 'string'
    && typeof result.read_call?.actual_effect?.called === 'boolean'
    && typeof result.write_call?.receipt_id === 'string' && typeof result.write_call?.decision === 'string'
    && typeof result.write_call?.actual_effect?.called === 'boolean'
    && typeof result.trace?.trace_id === 'string'
    && typeof result.evidence?.path === 'string' && typeof result.evidence?.sha256 === 'string'
    && /^[a-f0-9]{64}$/i.test(result.evidence.sha256)
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
  const [mcpRunning, setMcpRunning] = useState(false)
  const [mcpError, setMcpError] = useState('')
  const [mcpResult, setMcpResult] = useState<McpFixtureResult | null>(null)

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

  const runMcpFixture = async () => {
    setMcpRunning(true)
    setMcpError('')
    setMcpResult(null)
    try {
      const response = await fetch('/api/demo/mcp-governance', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({}),
      })
      if (!response.ok) throw new Error(await capabilityResponseError(response))
      const body: unknown = await response.json()
      if (!hasMcpFixtureResult(body)) throw new Error('The local MCP fixture returned an incomplete result; no success is shown.')
      setMcpResult(body)
    } catch (cause) {
      setMcpError(cause instanceof Error ? cause.message : 'The local MCP fixture could not be run.')
    } finally { setMcpRunning(false) }
  }

  return (
    <section className="capability-manager" aria-label="Capabilities">
      <ExternalConnections />
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
      <section className="mcp-governance" aria-labelledby="mcp-governance-title">
        <div className="mcp-governance__header">
          <div><p className="section-eyebrow">Governed tool access</p><h3 id="mcp-governance-title">Local MCP fixture</h3></div>
          <button type="button" className="secondary-action" onClick={() => void runMcpFixture()} disabled={mcpRunning}>
            {mcpRunning ? 'Running local fixture…' : 'Run local MCP fixture'}
          </button>
        </div>
        <p className="mcp-governance__notice">Esta demo inicia únicamente el servidor stdio local del repositorio. Configura Docker MCP, servidores MCP HTTP y APIs en Conexiones externas.</p>
        {mcpRunning && <p className="capability-state" role="status" aria-live="polite">Running the local MCP fixture and recording its observed calls…</p>}
        {mcpError && <p className="capability-error" role="alert">Local MCP fixture failed: {mcpError}</p>}
        {mcpResult && <div className="mcp-governance__result" role="region" aria-label="Local MCP fixture result">
          {mcpResult.read_call.decision === 'ALLOW' && mcpResult.read_call.actual_effect.called && mcpResult.write_call.decision === 'REQUIRE_HUMAN' && !mcpResult.write_call.actual_effect.called
            ? <p className="mcp-governance__success" role="status">Local fixture completed. The READ call reached MCP; the WRITE call was denied before transport.</p>
            : <p className="capability-error" role="alert">The fixture returned, but its allow/deny transport boundary is unexpected. Review the receipts; required policy is not demonstrated.</p>}
          <dl className="mcp-governance__meta">
            <div><dt>Run ID</dt><dd><code>{mcpResult.run_id}</code></dd></div>
            <div><dt>Transport</dt><dd>{mcpResult.transport}</dd></div>
            <div><dt>Fixture source</dt><dd>{mcpResult.source_kind}</dd></div>
            <div><dt>Server</dt><dd>{mcpResult.server}</dd></div>
            <div><dt>Trace ID</dt><dd><code>{mcpResult.trace.trace_id}</code></dd></div>
            <div><dt>Evidence path</dt><dd><code>{mcpResult.evidence.path}</code></dd></div>
            <div><dt>Evidence SHA-256</dt><dd><code>{mcpResult.evidence.sha256}</code></dd></div>
          </dl>
          <h4>Discovered tools</h4>
          {mcpResult.discovered.length === 0 ? <p>No tools were discovered.</p> : <ul className="mcp-governance__tools">{mcpResult.discovered.map((tool) => {
            const registration = mcpResult.registered.find((item) => item.name === tool.name)
            return <li key={`${tool.name}:${tool.fingerprint}`}><strong>{tool.name}</strong><span>Effect: {registration?.effect_type ?? 'Unknown or unregistered'}</span><code>Fingerprint: {tool.fingerprint}</code></li>
          })}</ul>}
          <div className="mcp-governance__calls">
            <article className="mcp-governance__call"><h4>READ: {mcpResult.read_call.decision}</h4><p>Actual MCP transport call: <strong>{mcpResult.read_call.actual_effect.called ? 'called' : 'not called'}</strong></p><p>Receipt ID: <code>{mcpResult.read_call.receipt_id}</code></p><details><summary>Inspect READ receipt</summary><pre>{JSON.stringify(mcpResult.read_call.receipt ?? mcpResult.read_call, null, 2)}</pre></details></article>
            <article className="mcp-governance__call"><h4>WRITE: {mcpResult.write_call.decision}</h4><p>Actual MCP transport call: <strong>{mcpResult.write_call.actual_effect.called ? 'called' : 'not called'}</strong></p><p>Receipt ID: <code>{mcpResult.write_call.receipt_id}</code></p><details><summary>Inspect WRITE receipt</summary><pre>{JSON.stringify(mcpResult.write_call.receipt ?? mcpResult.write_call, null, 2)}</pre></details></article>
          </div>
          <details><summary>Inspect trace events</summary><pre>{JSON.stringify(mcpResult.trace.events, null, 2)}</pre></details>
        </div>}
      </section>
      <p className="capability-footer">A proposal records a request for review only. It grants no permission, creates no job, and does not execute code.</p>
    </section>
  )
}
