import {useI18n,t,localMessage,errorMessage,apiError,formatDate,formatNumber} from '../i18n'
import type {TranslationKey} from '../i18n'
import './CapabilityManager.css'
import { useCallback, useEffect, useId, useRef, useState } from 'react'
import type { KeyboardEvent } from 'react'

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

type CapabilityGroup = {id: string; title: TranslationKey; description: TranslationKey; capabilityIds: string[]}

const CAPABILITY_GROUPS: CapabilityGroup[] = [
  {id:'documents',title:'commerce.capability_ui.group_documents',description:'commerce.capability_ui.group_documents_help',capabilityIds:['document_inventory','document_extract','document_relate','document_plan_rename','document_export']},
  {id:'workspace',title:'commerce.capability_ui.group_workspace',description:'commerce.capability_ui.group_workspace_help',capabilityIds:['workspace.read_text','workspace.scan_duplicates','filesystem_inventory','filesystem_plan']},
  {id:'agents',title:'commerce.capability_ui.group_agents',description:'commerce.capability_ui.group_agents_help',capabilityIds:['agent.run','agent.evaluate']},
  {id:'development',title:'capability.tabs.group_development',description:'commerce.capability_ui.group_development_help',capabilityIds:['development_read','development_inspect','development_prepare','development_revise','development_check','development_review']},
  {id:'delivery',title:'commerce.capability_ui.group_delivery',description:'commerce.capability_ui.group_delivery_help',capabilityIds:['delivery_review','delivery_revalidate','delivery_prepare_draft']},
  {id:'connections',title:'commerce.capability_ui.group_connections',description:'commerce.capability_ui.group_connections_help',capabilityIds:['mcp.execute','sandbox.execute']},
]

export type CapabilityDestination = 'connections' | 'builder' | 'workspace' | 'evaluation_lab'
export type CapabilityChatRequest = {capabilityId: string; prompt: string}
type CapabilityManagerProps = {
  onPrepareChat?: (request: CapabilityChatRequest) => void
  onNavigate?: (destination: CapabilityDestination) => void
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
  return t('agents.aux.DirectoryScanRun.request_failed_p0',{p0:response.status})
}

async function capabilityError(response: Response): Promise<Error> {
  return apiError(await response.json().catch(() => null),response.status,'agents')
}

export default function CapabilityManager({onPrepareChat, onNavigate}: CapabilityManagerProps = {}) {
  useI18n()

  const [capabilities, setCapabilities] = useState<Capability[]>([])
  const [proposals, setProposals] = useState<CapabilityProposal[]>([])
  const [activeGroupId, setActiveGroupId] = useState('all')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<any>('')
  const [canceling, setCanceling] = useState<string | null>(null)
  const idPrefix = useId().replace(/:/g, '')
  const tabRefs = useRef<Record<string, HTMLButtonElement | null>>({})
  const capabilityGroups = capabilityGroupsFor(capabilities)
  const activeGroup = capabilityGroups.find((group) => group.id === activeGroupId) ?? capabilityGroups[0]
  const groupCapabilities = activeGroup?.id === 'all' ? capabilities : activeGroup ? capabilities.filter((capability) => activeGroup.capabilityIds.includes(capability.id)) : []
  const tabId = (groupId: string) => `capability-tab-${idPrefix}-${groupId}`
  const panelId = `capability-panel-${idPrefix}`

  const activateGroup = (groupId: string, moveFocus = false) => {
    setActiveGroupId(groupId)
    if (moveFocus) tabRefs.current[groupId]?.focus()
  }

  const onTabKeyDown = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    let nextIndex: number | undefined
    if (event.key === 'ArrowRight') nextIndex = (index + 1) % capabilityGroups.length
    else if (event.key === 'ArrowLeft') nextIndex = (index - 1 + capabilityGroups.length) % capabilityGroups.length
    else if (event.key === 'Home') nextIndex = 0
    else if (event.key === 'End') nextIndex = capabilityGroups.length - 1
    if (nextIndex === undefined) return
    event.preventDefault()
    activateGroup(capabilityGroups[nextIndex].id, true)
  }

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
      if (!Array.isArray(catalog.capabilities) || catalog.capabilities.some((item: unknown) => !item || typeof item !== 'object' || typeof (item as Capability).id !== 'string' || typeof (item as Capability).status !== 'string' || typeof (item as Capability).effect !== 'string')) throw localMessage('commerce.capability_ui.bad_catalog')
      setCapabilities(catalog.capabilities)
      setActiveGroupId('all')
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

  return (
    <section className="capability-manager" aria-label={t("core.CapabilityManager.capabilities_9460f1")}>
      <header><h2>{t('commerce.capability_ui.heading')}</h2><p>{t('commerce.capability_ui.prepare_notice')}</p></header>
      {loading && <p className="capability-state" role="status">{t("core.CapabilityManager.loading_capability_catalog_and_proposals_8fb43b")}</p>}
      {error && <div className="capability-error" role="alert"><p>{errorMessage(error)}</p><button type="button" onClick={()=>void refresh()}>{t('commerce.capability_ui.retry')}</button></div>}
      {!loading && !error && capabilities.length === 0 && <p className="capability-state">{t("core.CapabilityManager.no_capability_records_were_returned_by_the_199420")}</p>}
      {!loading && !error && capabilities.length > 0 && <p className="capability-catalog-notice">{t('commerce.capability_ui.source_notice')}</p>}
      {!loading && !error && capabilities.length > 0 && <>
        <details className="capability-quick-menu">
          <summary>{t('commerce.capability_ui.quick_options')}</summary>
          <p>{t('commerce.capability_ui.quick_options_help')}</p>
          <nav aria-label={t('commerce.capability_ui.quick_options')}>
            {capabilityGroups.map((group) => <button type="button" key={group.id} aria-controls={panelId} aria-pressed={activeGroup?.id === group.id} onClick={() => activateGroup(group.id)}>{t(group.title)}</button>)}
          </nav>
        </details>
        <div className="capability-tabs" role="tablist" aria-label={t('core.CapabilityManager.capabilities_9460f1')}>
          {capabilityGroups.map((group, index) => {
            const count = group.id === 'all' ? capabilities.length : capabilities.filter((capability) => group.capabilityIds.includes(capability.id)).length
            const selected = activeGroup?.id === group.id
            return <button
              key={group.id}
              ref={(element) => { tabRefs.current[group.id] = element }}
              id={tabId(group.id)}
              type="button"
              role="tab"
              aria-selected={selected}
              aria-controls={panelId}
              aria-label={`${t(group.title)} (${count})`}
              tabIndex={selected ? 0 : -1}
              onClick={() => activateGroup(group.id)}
              onKeyDown={(event) => onTabKeyDown(event, index)}
            >
              <span>{t(group.title)}</span><span className="capability-tab-count" aria-hidden="true">{count}</span>
            </button>
          })}
        </div>
        {activeGroup && <section className="capability-group-panel" role="tabpanel" id={panelId} aria-labelledby={tabId(activeGroup.id)} tabIndex={0}>
          <p className="capability-group-help">{t(activeGroup.description)}</p>
          {groupCapabilities.length === 0
            ? <p className="capability-empty-category">{t('capability.tabs.empty_category', {category:t(activeGroup.title)})}</p>
            : <ul className="capability-list">
        {groupCapabilities.map((capability) => <li key={capability.id}><article className="capability-card">
          <div className="capability-card-heading"><div><h3>{capabilityPresentation(capability.id).name}</h3><code>{capability.id}</code></div><span className={`capability-status status-${capability.status.toLowerCase()}`}>{observedStateLabel(capability.status)}</span></div>
          <p className="capability-card-summary">{capabilityPresentation(capability.id).summary}</p>
          <dl className="capability-metadata" aria-label={t('commerce.capability_ui.metadata')}>
            <div className="metadata-effect"><dt>{t("core.CapabilityManager.effect_2252d5")}</dt><dd>{observedStateLabel(capability.effect)}</dd></div>
            <div className="metadata-provider"><dt>{t("core.CapabilityManager.provider_472590")}</dt><dd>{capabilityPresentation(capability.id).provider}</dd></div>
            <div className={`metadata-integration status-${String(capability.integration ?? 'UNKNOWN').toLowerCase()}`}><dt>{t("core.CapabilityManager.integration_9a42d4")}</dt><dd>{observedStateLabel(capability.integration ?? 'UNKNOWN')}</dd></div>
          </dl>
          <p className={`capability-requirement ${capability.status === 'AVAILABLE' ? 'requirement-ready' : 'requirement-review'}`}><strong>{t('commerce.capability_ui.requirements')}: </strong>{capabilityAction(capability.id) ? t(capabilityAction(capability.id)!.requirement) : t('commerce.capability_ui.unsupported')}</p>
          <div className="capability-card-actions">
            {capabilityAction(capability.id) ? <>
              {capability.status === 'AVAILABLE' && capabilityAction(capability.id)!.prompt ? <button type="button" className="primary-action" disabled={!onPrepareChat} onClick={()=>onPrepareChat?.({capabilityId:capability.id,prompt:t(capabilityAction(capability.id)!.prompt!)})}>{t('commerce.capability_ui.prepare')}</button> : <span className="capability-action-state">{capability.status === 'UNAVAILABLE' ? t('commerce.capability_ui.unavailable') : t('commerce.capability_ui.unsupported')}</span>}
              {!onPrepareChat && capability.status === 'AVAILABLE' && capabilityAction(capability.id)!.prompt && <span className="capability-action-state">{t('commerce.capability_ui.no_bridge')}</span>}
              {capabilityAction(capability.id)!.destination && onNavigate && <button type="button" className="secondary-action" onClick={()=>onNavigate(capabilityAction(capability.id)!.destination!)}>{t(capabilityAction(capability.id)!.configuration)}</button>}
            </> : <span className="capability-action-state">{t('commerce.capability_ui.unsupported')}</span>}
            <details className="capability-card-details"><summary>{t('commerce.capability_ui.details')}</summary>
              <details><summary>{t('agents.aux.context.technical')}</summary><pre>{JSON.stringify({id:capability.id,name:capability.name,summary:capability.summary,provider:capability.provider,effect:capability.effect,integration:capability.integration,status:capability.status},null,2)}</pre></details>
              <details><summary>{t("core.CapabilityManager.limits_and_source_fingerprints_e6e898")}</summary><pre>{JSON.stringify({ limits: capability.limits, source_fingerprints: capability.source_fingerprints }, null, 2)}</pre></details>
            </details>
          </div>

        </article></li>)}
          </ul>}
        </section>}
      </>}
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
      <p className="capability-footer">{t("core.CapabilityManager.a_proposal_records_a_request_for_review_e95b81")}</p>
    </section>
  )
}

function capabilityGroupsFor(capabilities: Capability[]): CapabilityGroup[] {
  const unknownIds = capabilities.map((item) => item.id).filter((id) => !CAPABILITY_GROUPS.some((group) => group.capabilityIds.includes(id)))
  return [
    {id:'all', title:'capability.tabs.all', description:'capability.tabs.all_help', capabilityIds:capabilities.map((item) => item.id)},
    ...CAPABILITY_GROUPS,
    {id:'uncategorized', title:'capability.tabs.uncategorized', description:'capability.tabs.uncategorized_help', capabilityIds:unknownIds},
  ]
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
    case 'document_inventory': return {name:t('commerce.capability_ui.document_inventory.name'),provider:t('commerce.capability_ui.provider_local'),summary:t('commerce.capability_ui.document_inventory.summary')}
    case 'document_extract': return {name:t('commerce.capability_ui.document_extract.name'),provider:t('commerce.capability_ui.provider_local'),summary:t('commerce.capability_ui.document_extract.summary')}
    case 'document_relate': return {name:t('commerce.capability_ui.document_relate.name'),provider:t('commerce.capability_ui.provider_local'),summary:t('commerce.capability_ui.document_relate.summary')}
    case 'document_plan_rename': return {name:t('commerce.capability_ui.document_plan_rename.name'),provider:t('commerce.capability_ui.provider_local'),summary:t('commerce.capability_ui.document_plan_rename.summary')}
    case 'document_export': return {name:t('commerce.capability_ui.document_export.name'),provider:t('commerce.capability_ui.provider_local'),summary:t('commerce.capability_ui.document_export.summary')}
    case 'filesystem_inventory': return {name:t('commerce.capability_ui.filesystem_inventory.name'),provider:t('commerce.capability_ui.provider_local'),summary:t('commerce.capability_ui.filesystem_inventory.summary')}
    case 'filesystem_plan': return {name:t('commerce.capability_ui.filesystem_plan.name'),provider:t('commerce.capability_ui.provider_local'),summary:t('commerce.capability_ui.filesystem_plan.summary')}
    case 'delivery_review': return {name:t('commerce.capability_ui.delivery_review.name'),provider:t('commerce.capability_ui.provider_local'),summary:t('commerce.capability_ui.delivery_review.summary')}
    case 'delivery_revalidate': return {name:t('commerce.capability_ui.delivery_revalidate.name'),provider:t('commerce.capability_ui.provider_local'),summary:t('commerce.capability_ui.delivery_revalidate.summary')}
    case 'delivery_prepare_draft': return {name:t('commerce.capability_ui.delivery_prepare_draft.name'),provider:t('commerce.capability_ui.provider_local'),summary:t('commerce.capability_ui.delivery_prepare_draft.summary')}
    case 'development_check': return {name:t('commerce.capability_ui.development_check.name'),provider:t('commerce.capability_ui.provider_development'),summary:t('commerce.capability_ui.development_check.summary')}
    case 'development_inspect': return {name:t('commerce.capability_ui.development_inspect.name'),provider:t('commerce.capability_ui.provider_development'),summary:t('commerce.capability_ui.development_inspect.summary')}
    case 'development_prepare': return {name:t('commerce.capability_ui.development_prepare.name'),provider:t('commerce.capability_ui.provider_development'),summary:t('commerce.capability_ui.development_prepare.summary')}
    case 'development_read': return {name:t('commerce.capability_ui.development_read.name'),provider:t('commerce.capability_ui.provider_development'),summary:t('commerce.capability_ui.development_read.summary')}
    case 'development_review': return {name:t('commerce.capability_ui.development_review.name'),provider:t('commerce.capability_ui.provider_development'),summary:t('commerce.capability_ui.development_review.summary')}
    case 'development_revise': return {name:t('commerce.capability_ui.development_revise.name'),provider:t('commerce.capability_ui.provider_development'),summary:t('commerce.capability_ui.development_revise.summary')}
    default: return {name:t('agents.aux.capability.unknownName',{id}),provider:t('agents.aux.capability.unknownProvider'),summary:t('agents.aux.capability.unknownSummary')}
  }
}

type CapabilityAction = {requirement: TranslationKey; prompt?: TranslationKey; destination?: CapabilityDestination; configuration: TranslationKey}
function capabilityAction(id: string): CapabilityAction | undefined {
  const prefix = 'commerce.capability_ui.'
  const configuration: TranslationKey = 'commerce.capability_ui.configure_agents'
  if (id === 'workspace.read_text' || id === 'workspace.scan_duplicates') return {requirement:'commerce.capability_ui.req_workspace',prompt:(prefix+id+'.prompt') as TranslationKey,destination:'workspace',configuration:'commerce.capability_ui.configure_workspace'}
  if (id === 'agent.evaluate') return {requirement:'commerce.capability_ui.req_evaluate',prompt:'commerce.capability_ui.agent.evaluate.prompt',destination:'evaluation_lab',configuration:'commerce.capability_ui.configure_evaluation'}
  if (id === 'mcp.execute') return {requirement:'commerce.capability_ui.req_mcp',destination:'connections',configuration:'commerce.capability_ui.connections'}
  if (id === 'sandbox.execute') return {requirement:'commerce.capability_ui.req_sandbox',configuration}
  if (id === 'agent.run') return {requirement:'commerce.capability_ui.req_agent',destination:'builder',configuration}
  const known = new Set(['document_inventory','document_extract','document_relate','document_plan_rename','document_export','filesystem_inventory','filesystem_plan','delivery_review','delivery_revalidate','delivery_prepare_draft','development_check','development_inspect','development_prepare','development_read','development_review','development_revise'])
  if (!known.has(id)) return undefined
  const requirement: TranslationKey = id.startsWith('document_') ? 'commerce.capability_ui.req_document' : id.startsWith('filesystem_') ? 'commerce.capability_ui.req_filesystem' : id.startsWith('delivery_') ? 'commerce.capability_ui.req_delivery' : 'commerce.capability_ui.req_development'
  return {requirement,prompt:(prefix+id+'.prompt') as TranslationKey,destination:'builder',configuration}
}
