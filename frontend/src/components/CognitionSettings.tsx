import {useI18n,t,localMessage,errorMessage,apiError,formatDate,formatNumber} from '../i18n'
import './CognitionSettings.css'
import { useEffect, useState } from 'react'
import ProjectContextDocument from './ProjectContextDocument'
import type { ContextLocation } from './ProjectContextDocument'

export type CognitiveMode = 'baseline' | 'bago5'
const MODE_KEY = 'adl.chat.cognitive-mode.v1'
const PROJECT_DOCUMENT_LABELS: Record<string, string> = {
  get 'conversations'(){return t('agents.aux.context.conversations')},
  get 'cognition-traces'(){return t('agents.aux.context.cognition-traces')},
  get 'project-context'(){return t('agents.aux.CognitionSettings.contexto_del_proyecto')},
  get 'project-state'(){return t('agents.aux.CognitionSettings.estado_del_proyecto')},
  get 'active-handoff'(){return t('agents.aux.CognitionSettings.continuidad')},
}

export function readCognitiveMode(): CognitiveMode {
  try { return localStorage.getItem(MODE_KEY) === 'bago5' ? 'bago5' : 'baseline' }
  catch { return 'baseline' }
}

type ContextMetadata = {
  workspace_root: string
  cognition: { profile: string; capacity: number; max_hops: number; max_expansions: number }
  paths: ContextLocation[]
  memory: { kind: string; state: string; description: string }
}

export default function CognitionSettings({ mode, onModeChange, workspaceOnly = false, showWorkspaceLocations = true }: {
  mode: CognitiveMode
  onModeChange: (mode: CognitiveMode) => void
  workspaceOnly?: boolean
  showWorkspaceLocations?: boolean
}) {
  useI18n()

  const [metadata, setMetadata] = useState<ContextMetadata | null>(null)
  const [error, setError] = useState<any>('')
  const [loading, setLoading] = useState(true)
  const [modeNotice, setModeNotice] = useState<any>('')
  const [pathDraft, setPathDraft] = useState('')
  const [workspaceBusy, setWorkspaceBusy] = useState(false)
  const [workspaceNotice, setWorkspaceNotice] = useState<any>('')
  const [workspaceError, setWorkspaceError] = useState<any>('')
  const [request, setRequest] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    setError('')
    void fetch('/api/chat/context', { signal: controller.signal }).then(async (response) => {
      if (!response.ok) throw apiError(await response.json().catch(() => null),response.status,'agents')
      const data = await response.json() as ContextMetadata
      if (typeof data.workspace_root !== 'string' || !Array.isArray(data.paths) || !data.cognition || !data.memory) throw localMessage("core.CognitionSettings.context_metadata_is_incomplete_bf2ff3")
      setMetadata(data)
      setPathDraft(data.workspace_root)
    }).catch((cause: unknown) => {
      if (!controller.signal.aborted) setError(cause instanceof Error ? cause : localMessage('agents.aux.CognitionSettings.context_locations_are_unavailable'))
    }).finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [request])

  const changeMode = (next: CognitiveMode) => {
    onModeChange(next)
    setModeNotice(localMessage(next === 'bago5' ? 'agents.aux.modeBagoApplies' : 'agents.aux.modeBaselineApplies'))
    try { localStorage.setItem(MODE_KEY, next) } catch { setModeNotice(localMessage('agents.aux.CognitionSettings.the_mode_applies_until_this_page_is_reloaded')) }
  }

  const applyWorkspace = async (endpoint: '/api/workspace/select' | '/api/workspace/browse') => {
    setWorkspaceBusy(true)
    setWorkspaceError('')
    setWorkspaceNotice('')
    try {
      const response = await fetch(endpoint, endpoint.endsWith('/select') ? {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ path: pathDraft }),
      } : { method: 'POST' })
      const body = await response.json() as { workspace_root?: string; cancelled?: boolean; detail?: { message?: string } }
      if (!response.ok) throw apiError(body,response.status,'agents')
      if (body.cancelled) { setWorkspaceNotice(localMessage('agents.aux.CognitionSettings.seleccion_cancelada')); return }
      if (!body.workspace_root) throw localMessage("core.CognitionSettings.the_selected_folder_was_not_returned_by_3bac17")
      setPathDraft(body.workspace_root)
      setMetadata(null)
      setWorkspaceNotice(localMessage('agents.aux.CognitionSettings.carpeta_seleccionada'))
      setRequest((value) => value + 1)
    } catch (cause) {
      setWorkspaceError(cause instanceof Error ? cause : localMessage('agents.aux.CognitionSettings.the_workspace_folder_could_not_be_selected'))
    } finally { setWorkspaceBusy(false) }
  }

  const location = (id: string) => metadata?.paths.find((item) => item.id === id)
  const renderLocation = (item: ContextLocation | undefined) => item && (['project-context', 'project-state', 'active-handoff'].includes(item.id)
    ? <ProjectContextDocument key={`${metadata?.workspace_root}:${item.id}`} item={{ ...item, label: PROJECT_DOCUMENT_LABELS[item.id] }} workspaceRoot={metadata!.workspace_root} />
    : <div className={`workspace-source ${item.state}`} key={item.id}>
    <div><strong>{PROJECT_DOCUMENT_LABELS[item.id] || t('agents.aux.context.unknown',{id:item.id})}</strong><span>{item.state === 'present' ? t("core.CognitionSettings.available_e67444") : t("core.CognitionSettings.not_found_e3ebaa")}</span></div>
    <p>{contextPurpose(item.id)}</p><details><summary>{t('agents.aux.context.technical')}</summary><pre>{JSON.stringify({id:item.id,label:item.label,purpose:item.purpose},null,2)}</pre></details>
    <code title={item.path}>{item.path}</code>
  </div>)

  return <div className={`cognition-settings${workspaceOnly ? ' workspace-settings' : ''}`}>
    {!workspaceOnly && <header><h3>{t("core.CognitionSettings.cognition_context_9f7f54")}</h3><p>{t("core.CognitionSettings.choose_how_the_assistant_handles_new_messages_537723")}</p></header>}
    {workspaceOnly && <header className="workspace-heading"><h3>{t("core.CognitionSettings.workspace_87bb59")}</h3></header>}
    {!workspaceOnly && <fieldset className="cognition-mode"><legend>{t("core.CognitionSettings.chat_cognition_mode_0fa5af")}</legend>
      <label><input type="radio" name="cognitive-mode" value="baseline" checked={mode === 'baseline'} onChange={() => changeMode('baseline')} /><span><strong>{t("core.CognitionSettings.baseline_cc9ea7")}</strong><small>{t("core.CognitionSettings.use_the_normal_assistant_or_agent_prompt_c5c67e")}</small></span></label>
      <label><input type="radio" name="cognitive-mode" value="bago5" checked={mode === 'bago5'} onChange={() => changeMode('bago5')} /><span><strong>{t("core.CognitionSettings.bago5_experimental_e39938")}</strong><small>{t("core.CognitionSettings.add_bounded_cognitive_focus_to_the_model_6cb533")}</small></span></label>
    </fieldset>}
    {!workspaceOnly && modeNotice && <p className="cognition-status" role="status">{errorMessage(modeNotice)}</p>}
    {workspaceOnly && <section className="workspace-picker" aria-label={t("core.CognitionSettings.project_folder_60c6cd")}>
      <label htmlFor="workspace-path">{t("core.CognitionSettings.project_folder_60c6cd")}</label>
      <div className="workspace-path-row"><input id="workspace-path" value={pathDraft} onChange={(event) => { setPathDraft(event.target.value); setWorkspaceNotice('') }} onKeyDown={(event) => { if (event.key === 'Enter' && !workspaceBusy && pathDraft.trim()) void applyWorkspace('/api/workspace/select') }} placeholder={t("core.CognitionSettings.select_a_folder_ea37f6")} disabled={workspaceBusy} />
        <button type="button" className="workspace-browse" onClick={() => void applyWorkspace('/api/workspace/browse')} disabled={workspaceBusy}>{workspaceBusy ? t("core.CognitionSettings.waiting_a7f426") : t("core.CognitionSettings.browse_4ebca1")}</button>
        <button type="button" onClick={() => void applyWorkspace('/api/workspace/select')} disabled={workspaceBusy || !pathDraft.trim()}>{t("core.CognitionSettings.use_folder_bf3210")}</button>
      </div>
      {workspaceNotice && <p className="cognition-status" role="status">{errorMessage(workspaceNotice)}</p>}
      {workspaceError && <p className="context-path-error" role="alert">{errorMessage(workspaceError)}</p>}
    </section>}
    {showWorkspaceLocations && (workspaceOnly ? <section className="context-locations workspace-context">
      {loading && <p role="status">{t("core.CognitionSettings.loading_205443")}</p>}
      {error && <div role="alert"><p>{errorMessage(error)}</p><button type="button" onClick={() => setRequest((value) => value + 1)}>{t("core.CognitionSettings.retry_a9254c")}</button></div>}
      {metadata && <>
        <h4 className="workspace-section-title">{t("core.CognitionSettings.project_files_f6105a")}</h4>
        <div className="workspace-sources">{renderLocation(location('project-context'))}{renderLocation(location('project-state'))}{renderLocation(location('active-handoff'))}</div>
        <section className="workspace-memory" aria-labelledby="workspace-memory-title">
          <h4 id="workspace-memory-title" className="workspace-section-title">{t("core.CognitionSettings.memory_031633")}</h4>
          <dl><div><dt>{t("core.CognitionSettings.general_c910d4")}</dt><dd className="unavailable">{t("core.CognitionSettings.not_connected_48e643")}</dd></div><div><dt>{t("core.CognitionSettings.conversation_2f2f74")}</dt><dd className={metadata.memory.state === 'present' ? 'available' : 'unavailable'}>{metadata.memory.state === 'present' ? t("core.CognitionSettings.available_f4e4f6") : t("core.CognitionSettings.unavailable_b781f6")}</dd></div></dl>
        </section>
      </>}
    </section> : <details className="context-locations cognition-context" open>
      <summary id="context-locations-title"><strong>{t("core.CognitionSettings.context_and_workspace_ed6f02")}</strong><span>{metadata ? t('agents.aux.CognitionSettings.p0_project_sources',{p0:metadata.paths.length}) : t("core.CognitionSettings.loading_project_scope_9f0343")}</span></summary>
      <div className="context-locations-content">
        {loading && <p role="status">{t("core.CognitionSettings.loading_context_sources_4b187f")}</p>}
        {error && <div role="alert"><p>{errorMessage(error)}</p><button type="button" onClick={() => setRequest((value) => value + 1)}>{t("core.CognitionSettings.retry_942087")}</button></div>}
        {metadata && <>
          <p className="cognition-context-intro">{t("core.CognitionSettings.live_scope_and_context_metadata_used_by_b3daa3")}</p>
          <dl className="context-summary cognition-context-summary">
            <div><dt>{t("core.CognitionSettings.active_workspace_68971a")}</dt><dd><code title={metadata.workspace_root}>{metadata.workspace_root}</code></dd></div>
            <div><dt>{t("core.CognitionSettings.cognition_profile_2ecb9f")}</dt><dd>{metadata.cognition.profile}</dd></div>
            <div><dt>{t("core.CognitionSettings.focus_capacity_922ae3")}</dt><dd>{t('agents.aux.focusCapacity',{capacity:formatNumber(metadata.cognition.capacity),hops:formatNumber(metadata.cognition.max_hops),expansions:formatNumber(metadata.cognition.max_expansions)})}</dd></div>
            <div><dt>{t("core.CognitionSettings.conversation_memory_230741")}</dt><dd>{metadata.memory.kind === 'conversation_history' ? t('agents.aux.context.memoryKind') : metadata.memory.kind} · {observedStateLabel(metadata.memory.state)}<small>{metadata.memory.kind === 'conversation_history' ? t('agents.aux.context.memoryDescription') : metadata.memory.description}</small></dd></div>
          </dl>
          <div className="context-sources-heading"><h4>{t("core.CognitionSettings.project_context_sources_bd2939")}</h4><span>{t("core.CognitionSettings.expand_a_file_to_read_it_228fd5")}</span></div>
          <div className="context-source-grid">{metadata.paths.map((item) => renderLocation(item))}</div>
        </>}
      </div>
    </details>)}
  </div>
}

/** Presentation only: preserve the exact observed protocol value alongside its label. */
function observedStateLabel(value: string): string {
  const labels: Record<string, () => string> = {
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

function contextPurpose(id: string): string {
  switch(id) {
    case 'project-context': return t('agents.aux.context.project-context.purpose')
    case 'project-state': return t('agents.aux.context.project-state.purpose')
    case 'active-handoff': return t('agents.aux.context.active-handoff.purpose')
    case 'conversations': return t('agents.aux.context.conversations.purpose')
    case 'cognition-traces': return t('agents.aux.context.cognition-traces.purpose')
    default: return t('agents.aux.context.unknown',{id})
  }
}
