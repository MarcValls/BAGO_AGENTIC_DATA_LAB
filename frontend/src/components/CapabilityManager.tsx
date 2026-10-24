import {useI18n,t,localMessage,errorMessage,apiError,formatDate,formatNumber} from '../i18n'
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
  return t('agents.aux.DirectoryScanRun.request_failed_p0',{p0:response.status})
}

async function capabilityError(response: Response): Promise<Error> {
  return apiError(await response.json().catch(() => null),response.status,'agents')
}

export default function CapabilityManager() {
  useI18n()

  const [capabilities, setCapabilities] = useState<Capability[]>([])
  const [proposals, setProposals] = useState<CapabilityProposal[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<any>('')
  const [canceling, setCanceling] = useState<string | null>(null)
  const [mcpRunning, setMcpRunning] = useState(false)
  const [mcpError, setMcpError] = useState<any>('')
  const [mcpResult, setMcpResult] = useState<McpFixtureResult | null>(null)

  const refresh = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [catalogResponse, proposalResponse] = await Promise.all([
        fetch('/api/capabilities'),
        fetch('/api/capabilities/proposals?status=all&limit=100'),
      ])
      if (!catalogResponse.ok) throw await capabilityError(catalogResponse)
      if (!proposalResponse.ok) throw await capabilityError(proposalResponse)
      const catalog = await catalogResponse.json()
      const proposalData = await proposalResponse.json()
      setCapabilities(Array.isArray(catalog.capabilities) ? catalog.capabilities : [])
      setProposals(Array.isArray(proposalData.proposals) ? proposalData.proposals : [])
    } catch (cause) {
      setError(cause instanceof Error ? cause : localMessage('agents.aux.CapabilityManager.capability_data_could_not_be_loaded'))
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
      if (!response.ok) throw await capabilityError(response)
      const result = await response.json()
      await refresh()
    } catch (cause) {
      setError(cause instanceof Error ? cause : localMessage('agents.aux.CapabilityManager.proposal_could_not_be_cancelled'))
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
      if (!response.ok) throw await capabilityError(response)
      const body: unknown = await response.json()
      if (!hasMcpFixtureResult(body)) throw localMessage("core.CapabilityManager.the_local_mcp_fixture_returned_an_incomplete_0f0575")
      setMcpResult(body)
    } catch (cause) {
      setMcpError(cause instanceof Error ? cause : localMessage('agents.aux.CapabilityManager.the_local_mcp_fixture_could_not_be_run'))
    } finally { setMcpRunning(false) }
  }

  return (
    <section className="capability-manager" aria-label={t("core.CapabilityManager.capabilities_9460f1")}>
      <ExternalConnections />
      {loading && <p className="capability-state" role="status">{t("core.CapabilityManager.loading_capability_catalog_and_proposals_8fb43b")}</p>}
      {error && <p className="capability-error" role="alert">{errorMessage(error)}</p>}
      {!loading && !error && capabilities.length === 0 && <p className="capability-state">{t("core.CapabilityManager.no_capability_records_were_returned_by_the_199420")}</p>}
      {!loading && !error && capabilities.length > 0 && <div className="capability-grid">
        {capabilities.map((capability) => <article className="capability-card" key={capability.id}>
          <div className="capability-card-heading"><div><h3>{capabilityPresentation(capability.id).name}</h3><code>{capability.id}</code></div><span className={`capability-status status-${capability.status.toLowerCase()}`}>{observedStateLabel(capability.status)}</span></div>
          <p>{capabilityPresentation(capability.id).summary}</p><details><summary>{t('agents.aux.context.technical')}</summary><pre>{JSON.stringify({id:capability.id,name:capability.name,summary:capability.summary,provider:capability.provider,effect:capability.effect,integration:capability.integration,status:capability.status},null,2)}</pre></details>
          <dl><div><dt>{t("core.CapabilityManager.effect_2252d5")}</dt><dd>{observedStateLabel(capability.effect)}</dd></div><div><dt>{t("core.CapabilityManager.provider_472590")}</dt><dd>{capabilityPresentation(capability.id).provider}</dd></div><div><dt>{t("core.CapabilityManager.integration_9a42d4")}</dt><dd>{observedStateLabel(capability.integration)}</dd></div><div><dt>{t("core.CapabilityManager.source_check_2e0156")}</dt><dd>{capability.source_available ? t("core.CapabilityManager.available_e67444") : t("core.CapabilityManager.missing_source_9800f9")}</dd></div></dl>
          <details><summary>{t("core.CapabilityManager.limits_and_source_fingerprints_e6e898")}</summary><pre>{JSON.stringify({ limits: capability.limits, source_fingerprints: capability.source_fingerprints }, null, 2)}</pre></details>
        </article>)}
      </div>}
      <section className={`capability-proposals ${!loading && !error && proposals.length === 0 ? 'is-empty' : ''}`} aria-labelledby="capability-proposals-title">
        <div className="capability-section-heading">
          <div className="capability-section-title"><h3 id="capability-proposals-title">{t("core.CapabilityManager.proposals_834cfc")}</h3><span>{loading ? '—' : proposals.length}</span></div>
          {!loading && !error && proposals.length === 0 && <p className="capability-empty-proposals">{t("core.CapabilityManager.no_saved_proposals_bf4879")}{' '}<span>{t("core.CapabilityManager.ask_the_chat_to_prepare_one_for_508f7b")}</span></p>}
        </div>
        <div className="capability-proposal-list">{proposals.map((proposal) => <article className="capability-proposal" key={proposal.id}>
          <div className="capability-card-heading"><div><h4>{capabilityPresentation(proposal.capability_id).name}</h4><code>{proposal.id}</code></div><span className="capability-status">{observedStateLabel(proposal.status)}</span></div>
          <p>{proposal.summary}</p><p><strong>{t("core.CapabilityManager.requested_scope_276692")}</strong> {proposal.requested_scope}</p>
          <p className="capability-proposal-meta">{t("core.CapabilityManager.effect_6f84a2")}{' '}{proposal.effect}{' '}{t("core.CapabilityManager.revision_8d8560")}{' '}{proposal.revision}{' '}{t("core.CapabilityManager.expires_f87160")}{' '}{formatDate(proposal.expires_at)}</p>
          {proposal.conversation_id && <p className="capability-proposal-meta">{t("core.CapabilityManager.conversation_343a88")}{' '}<code>{proposal.conversation_id}</code></p>}
          {proposal.status === 'PENDING_REVIEW' && <button type="button" className="secondary-action" disabled={canceling === proposal.id} onClick={() => void cancelProposal(proposal)}>{canceling === proposal.id ? t("core.CapabilityManager.cancelling_91b104") : t("core.CapabilityManager.cancel_proposal_15fe06")}</button>}
        </article>)}</div>
      </section>
      <section className="mcp-governance" aria-labelledby="mcp-governance-title">
        <div className="mcp-governance__header">
          <div><p className="section-eyebrow">{t("core.CapabilityManager.governed_tool_access_9848ce")}</p><h3 id="mcp-governance-title">{t("core.CapabilityManager.local_mcp_fixture_467351")}</h3></div>
          <button type="button" className="secondary-action" onClick={() => void runMcpFixture()} disabled={mcpRunning}>
            {mcpRunning ? t("core.CapabilityManager.running_local_fixture_225d0c") : t("core.CapabilityManager.run_local_mcp_fixture_01ede0")}
          </button>
        </div>
        <p className="mcp-governance__notice">{t("core.CapabilityManager.this_demonstration_starts_only_the_repository_local_98d489")}</p>
        {mcpRunning && <p className="capability-state" role="status" aria-live="polite">{t("core.CapabilityManager.running_the_local_mcp_fixture_and_recording_8004c8")}</p>}
        {mcpError && <p className="capability-error" role="alert">{t("core.CapabilityManager.local_mcp_fixture_failed_505b55")}{' '}{errorMessage(mcpError)}</p>}
        {mcpResult && <div className="mcp-governance__result" role="region" aria-label={t("core.CapabilityManager.local_mcp_fixture_result_b1ed4d")}>
          {mcpResult.read_call.decision === 'ALLOW' && mcpResult.read_call.actual_effect.called && mcpResult.write_call.decision === 'REQUIRE_HUMAN' && !mcpResult.write_call.actual_effect.called
            ? <p className="mcp-governance__success" role="status">{t("core.CapabilityManager.local_fixture_completed_the_read_call_reached_306cc9")}</p>
            : <p className="capability-error" role="alert">{t("core.CapabilityManager.the_fixture_returned_but_its_allow_deny_ff8f0a")}</p>}
          <dl className="mcp-governance__meta">
            <div><dt>{t("core.CapabilityManager.run_id_26d3e7")}</dt><dd><code>{mcpResult.run_id}</code></dd></div>
            <div><dt>{t("core.CapabilityManager.transport_aaead4")}</dt><dd>{mcpResult.transport}</dd></div>
            <div><dt>{t("core.CapabilityManager.fixture_source_a67722")}</dt><dd>{mcpResult.source_kind}</dd></div>
            <div><dt>{t("core.CapabilityManager.server_aef7de")}</dt><dd>{mcpResult.server}</dd></div>
            <div><dt>{t("core.CapabilityManager.trace_id_c4cbbc")}</dt><dd><code>{mcpResult.trace.trace_id}</code></dd></div>
            <div><dt>{t("core.CapabilityManager.evidence_path_9aa7c3")}</dt><dd><code>{mcpResult.evidence.path}</code></dd></div>
            <div><dt>{t("core.CapabilityManager.evidence_sha_256_5f35a7")}</dt><dd><code>{mcpResult.evidence.sha256}</code></dd></div>
          </dl>
          <h4>{t("core.CapabilityManager.discovered_tools_34bd08")}</h4>
          {mcpResult.discovered.length === 0 ? <p>{t("core.CapabilityManager.no_tools_were_discovered_d5107c")}</p> : <ul className="mcp-governance__tools">{mcpResult.discovered.map((tool) => {
            const registration = mcpResult.registered.find((item) => item.name === tool.name)
            return <li key={`${tool.name}:${tool.fingerprint}`}><strong>{tool.name}</strong><span>{t("core.CapabilityManager.effect_6f84a2")}{' '}{registration?.effect_type ?? t('agents.aux.CapabilityManager.unknown_or_unregistered')}</span><code>{t("core.CapabilityManager.fingerprint_500d5b")}{' '}{tool.fingerprint}</code></li>
          })}</ul>}
          <div className="mcp-governance__calls">
            <article className="mcp-governance__call"><h4>{t("core.CapabilityManager.read_0ef7bb")}{' '}{observedStateLabel(mcpResult.read_call.decision)}</h4><p>{t("core.CapabilityManager.actual_mcp_transport_call_ace798")}{' '}<strong>{mcpResult.read_call.actual_effect.called ? t("core.CapabilityManager.called_8c90cb") : t("core.CapabilityManager.not_called_57404b")}</strong></p><p>{t("core.CapabilityManager.receipt_id_9ba800")}{' '}<code>{mcpResult.read_call.receipt_id}</code></p><details><summary>{t("core.CapabilityManager.inspect_read_receipt_d2044f")}</summary><pre>{JSON.stringify(mcpResult.read_call.receipt ?? mcpResult.read_call, null, 2)}</pre></details></article>
            <article className="mcp-governance__call"><h4>{t("core.CapabilityManager.write_e800c6")}{' '}{observedStateLabel(mcpResult.write_call.decision)}</h4><p>{t("core.CapabilityManager.actual_mcp_transport_call_ace798")}{' '}<strong>{mcpResult.write_call.actual_effect.called ? t("core.CapabilityManager.called_8c90cb") : t("core.CapabilityManager.not_called_57404b")}</strong></p><p>{t("core.CapabilityManager.receipt_id_9ba800")}{' '}<code>{mcpResult.write_call.receipt_id}</code></p><details><summary>{t("core.CapabilityManager.inspect_write_receipt_4a2084")}</summary><pre>{JSON.stringify(mcpResult.write_call.receipt ?? mcpResult.write_call, null, 2)}</pre></details></article>
          </div>
          <details><summary>{t("core.CapabilityManager.inspect_trace_events_54a42b")}</summary><pre>{JSON.stringify(mcpResult.trace.events, null, 2)}</pre></details>
        </div>}
      </section>
      <p className="capability-footer">{t("core.CapabilityManager.a_proposal_records_a_request_for_review_e95b81")}</p>
    </section>
  )
}

/** Presentation only: preserve the exact observed protocol value alongside its label. */
function observedStateLabel(value: string): string {
  const labels: Record<string, () => string> = {
    'EXECUTE':()=>t('agents.aux.state.EXECUTE'),
    'EXTERNAL_ACTION':()=>t('agents.aux.state.EXTERNAL_ACTION'),
    'MODEL_INFERENCE':()=>t('agents.aux.state.MODEL_INFERENCE'),
    'READ':()=>t('agents.aux.state.READ'),
    'FAIL_CLOSED':()=>t('agents.aux.state.FAIL_CLOSED'),
    'MODULE_PRESENT_NOT_CONNECTED':()=>t('agents.aux.state.MODULE_PRESENT_NOT_CONNECTED'),
    'CONNECTED':()=>t('agents.aux.state.CONNECTED'),
"running":()=>t('agents.aux.state.running'),
"success":()=>t('agents.aux.state.success'),
"failed":()=>t('agents.aux.state.failed'),
"timeout":()=>t('agents.aux.state.timeout'),
"demo":()=>t('agents.aux.state.demo'),
"agent":()=>t('agents.aux.state.agent'),
"PROPOSED":()=>t('agents.aux.state.PROPOSED'),
"VERIFIED":()=>t('agents.aux.state.VERIFIED'),
"PENDING_REVIEW":()=>t('agents.aux.state.PENDING_REVIEW'),
"CANCELLED":()=>t('agents.aux.state.CANCELLED'),
"EXPIRED":()=>t('agents.aux.state.EXPIRED'),
"AVAILABLE":()=>t('agents.aux.state.AVAILABLE'),
"UNAVAILABLE":()=>t('agents.aux.state.UNAVAILABLE'),
"READY":()=>t('agents.aux.state.READY'),
"NOT_READY":()=>t('agents.aux.state.NOT_READY'),
"AWAITING_APPROVAL":()=>t('agents.aux.state.AWAITING_APPROVAL'),
"APPROVED":()=>t('agents.aux.state.APPROVED'),
"REJECTED":()=>t('agents.aux.state.REJECTED'),
"SUCCEEDED":()=>t('agents.aux.state.SUCCEEDED'),
"FAILED":()=>t('agents.aux.state.FAILED'),
"REVOKED":()=>t('agents.aux.state.REVOKED'),
"UNKNOWN":()=>t('agents.aux.state.UNKNOWN'),
"PASS":()=>t('agents.aux.state.PASS'),
"FAIL":()=>t('agents.aux.state.FAIL'),
"ERROR":()=>t('agents.aux.state.ERROR'),
"healthy":()=>t('agents.aux.state.healthy'),
"unavailable":()=>t('agents.aux.state.unavailable'),
"ALLOW":()=>t('agents.aux.state.ALLOW'),
"DENY":()=>t('agents.aux.state.DENY'),
"REQUIRE_HUMAN":()=>t('agents.aux.state.REQUIRE_HUMAN'),
"SUCCESS":()=>t('agents.aux.state.SUCCESS'),
"DENIED":()=>t('agents.aux.state.DENIED'),
"configured":()=>t('agents.aux.state.configured'),
"connected":()=>t('agents.aux.state.connected'),
"present":()=>t('agents.aux.state.present'),
"absent":()=>t('agents.aux.state.absent')
  }
  return Object.prototype.hasOwnProperty.call(labels,value) ? `${labels[value]()} (${value})` : t('agents.aux.state.unknownCode',{value})
}

function capabilityPresentation(id: string) {
  switch(id) {
    case 'workspace.read_text': return {name:t('agents.aux.capability.workspace.read_text.name'),provider:t('agents.aux.capability.workspace.read_text.provider'),summary:t('agents.aux.capability.workspace.read_text.summary')}
    case 'workspace.scan_duplicates': return {name:t('agents.aux.capability.workspace.scan_duplicates.name'),provider:t('agents.aux.capability.workspace.scan_duplicates.provider'),summary:t('agents.aux.capability.workspace.scan_duplicates.summary')}
    case 'agent.evaluate': return {name:t('agents.aux.capability.agent.evaluate.name'),provider:t('agents.aux.capability.agent.evaluate.provider'),summary:t('agents.aux.capability.agent.evaluate.summary')}
    case 'mcp.execute': return {name:t('agents.aux.capability.mcp.execute.name'),provider:t('agents.aux.capability.mcp.execute.provider'),summary:t('agents.aux.capability.mcp.execute.summary')}
    case 'sandbox.execute': return {name:t('agents.aux.capability.sandbox.execute.name'),provider:t('agents.aux.capability.sandbox.execute.provider'),summary:t('agents.aux.capability.sandbox.execute.summary')}
    case 'agent.run': return {name:t('agents.aux.capability.agent.run.name'),provider:t('agents.aux.capability.agent.run.provider'),summary:t('agents.aux.capability.agent.run.summary')}
    default: return {name:t('agents.aux.capability.unknownName',{id}),provider:t('agents.aux.capability.unknownProvider'),summary:t('agents.aux.capability.unknownSummary')}
  }
}
