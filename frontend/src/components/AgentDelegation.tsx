import { useEffect, useState } from 'react'
import './AgentDelegation.css'

export type AgentDelegationProposal = {
  proposal_id: string
  state: 'PROPOSED' | 'RUNNING' | 'PASSED' | 'FAILED' | 'INCONCLUSIVE' | 'EXPIRED' | 'STALE' | 'OUT_OF_SCOPE' | 'NEEDS_AUTHORIZATION' | 'NEEDS_REVIEW'
  parent_conversation_id: string
  parent_revision: number
  agent_id: string
  agent_name: string
  agent_config_sha256: string
  provider_id: string
  model_id: string
  assigned_tools: string[]
  task: string
  task_sha256: string
  proposal_sha256: string
  expires_at: number
  child_conversation_id?: string | null
  child_revision?: number | null
  child_trace_id?: string | null
  child_trace_sha256?: string | null
  child_trace_state?: string | null
  receipt_id?: string | null
  receipt_sha256?: string | null
  error_code?: string | null
  assistant_message?: string | null
  tools_executed?: boolean
  target_written?: boolean
  orchestration_status?: 'COMPLETED' | 'OUT_OF_SCOPE' | 'NEEDS_AUTHORIZATION' | 'NEEDS_REVIEW'
}

type FolderListing = { roots: Array<{ path: string; name: string }>; directories: Array<{ path: string; name: string }>; path?: string; parent?: string | null; output_directory?: string }
type ReviewContext = { runs: Array<{ work_id: string; owner_id: string; producer_name?: string; conversation_id: string; source_root: string; candidate_id: string; scope_sha256: string; artifacts: Array<{ path: string; sha256: string }>; business_acceptance: string }>; contacts: Array<{ id: string; name: string; phone: string }> }
type StoredConversation = { id: string; owner_kind: 'assistant' | 'agent'; owner_id: string; status: string; revision: number; messages: unknown[] }
type Props = {
  proposal: AgentDelegationProposal
  parentConversationId: string
  parentRevision: number
  disabled?: boolean
  onConversationUpdate: (conversation: StoredConversation) => void
  onOpenChild?: (identity: { agentId: string; conversationId: string }) => void
  onInspectChild?: (identity: { conversationId: string; revision: number; traceId: string }) => void
}

const terminal = new Set<AgentDelegationProposal['state']>(['PASSED', 'FAILED', 'INCONCLUSIVE', 'EXPIRED', 'STALE', 'OUT_OF_SCOPE', 'NEEDS_AUTHORIZATION', 'NEEDS_REVIEW'])
const validStates = new Set<AgentDelegationProposal['state']>(['PROPOSED', 'RUNNING', ...terminal])
const hash = /^[a-f0-9]{64}$/i
const allowedHandlers = new Set(['document_inventory', 'document_extract', 'document_relate', 'document_export', 'document_plan_rename', 'filesystem_inventory', 'filesystem_plan', 'delivery_review', 'delivery_revalidate', 'delivery_prepare_draft'])

async function readError(response: Response) {
  try {
    const body = await response.json()
    return typeof body?.detail === 'string' ? body.detail : `HTTP ${response.status}`
  } catch { return `HTTP ${response.status}` }
}

export default function AgentDelegation({ proposal, parentConversationId, parentRevision, disabled = false, onConversationUpdate, onOpenChild, onInspectChild }: Props) {
  const english = document.documentElement.lang?.toLowerCase().startsWith('en') ?? false
  const [current, setCurrent] = useState(proposal)
  const [allowTools, setAllowTools] = useState(false)
  const [allowExport, setAllowExport] = useState(false)
  const [allowDraft, setAllowDraft] = useState(false)
  const [folders, setFolders] = useState<FolderListing | null>(null)
  const [folder, setFolder] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [outputDirectory, setOutputDirectory] = useState('')
  const [reviewContext, setReviewContext] = useState<ReviewContext>({ runs: [], contacts: [] })
  const [reviewWork, setReviewWork] = useState('')
  const [reviewContact, setReviewContact] = useState('')
  const [contextError, setContextError] = useState(false)
  const [confirmed, setConfirmed] = useState(false)
  const identityKey = `${proposal.proposal_id}|${parentConversationId}|${proposal.agent_id}|${proposal.proposal_sha256}`
  const proposalStateKey = JSON.stringify(proposal)

  useEffect(() => {
    setCurrent(proposal)
    setAllowTools(false); setAllowExport(false); setAllowDraft(false)
    setFolder(''); setFolders(null); setOutputDirectory(''); setError(''); setNotice('')
    setReviewContext({ runs: [], contacts: [] }); setReviewWork(''); setReviewContact(''); setContextError(false); setConfirmed(false)
  }, [identityKey, proposalStateKey])

  useEffect(() => {
    if (!current.assigned_tools.some(tool => tool.startsWith('delivery_'))) return
    const controller = new AbortController()
    void fetch(`/api/agent-tools/context?owner_id=${encodeURIComponent(current.agent_id)}`, { signal: controller.signal }).then(async response => {
      if (!response.ok) throw new Error('context unavailable')
      const value = await response.json()
      if (!Array.isArray(value.runs) || !Array.isArray(value.contacts)) throw new Error('context invalid')
      setReviewContext(value); setContextError(false)
    }).catch(() => { if (!controller.signal.aborted) setContextError(true) })
    return () => controller.abort()
  }, [current.agent_id, current.assigned_tools.join('|')])

  const lang = {
    heading: english ? 'Saved agent delegation' : 'Delegación a agente guardado',
    review: english ? 'Review permissions' : 'Revisar permisos',
    task: english ? 'Task' : 'Tarea',
    tools: english ? 'Allow assigned tools' : 'Permitir herramientas asignadas',
    export: english ? 'Allow export to the selected output folder' : 'Permitir exportar a la carpeta de salida elegida',
    draft: english ? 'Allow preparing a draft (never send)' : 'Permitir preparar un borrador (nunca enviar)',
    folder: english ? 'Execution folder' : 'Carpeta de trabajo',
    choose: english ? 'Choose folder' : 'Elegir carpeta',
    use: english ? 'Use this folder' : 'Usar esta carpeta',
    parent: english ? 'Parent folder' : 'Carpeta superior',
    run: english ? 'Run task' : 'Ejecutar tarea',
    refresh: english ? 'Refresh status' : 'Actualizar estado',
    loading: english ? 'Loading…' : 'Cargando…',
    answer: english ? 'Agent result' : 'Resultado del agente',
    receipt: english ? 'Execution receipt' : 'Recibo de ejecución',
    trace: english ? 'Child trace' : 'Traza hija',
    noInherit: english ? 'Parent permissions and history are not copied to the delegated conversation.' : 'Los permisos y el historial principales no se copian a la conversación delegada.',
    notExecuted: english ? 'Proposal only. No child turn has run.' : 'Solo propuesta. Aún no se ha ejecutado ningún turno hijo.',
    openChild: english ? 'Open child conversation' : 'Abrir conversación hija',
    inspect: english ? 'Inspect child trace' : 'Inspeccionar traza hija',
    chooseFirst: english ? 'Choose an allowed folder before enabling tools.' : 'Elige una carpeta permitida antes de habilitar herramientas.',
    expired: english ? 'This proposal has expired.' : 'La propuesta ha caducado.',
    confirm: english ? 'I reviewed the agent, task, and selected permissions.' : 'He revisado el agente, la tarea y los permisos elegidos.',
    work: english ? 'Delivery review work' : 'Trabajo para revisar',
    chooseWork: english ? 'Choose a saved result' : 'Elegir un resultado guardado',
    contact: english ? 'Contact for draft context' : 'Contacto para el contexto del borrador',
    chooseContact: english ? 'Choose a contact' : 'Elegir un contacto',
    contextUnavailable: english ? 'Delivery review context could not be loaded.' : 'No se pudo cargar el contexto de revisión de entrega.',
    assigned: english ? 'Assigned tool handlers' : 'Herramientas asignadas',
    identity: english ? 'Proposal and profile identity' : 'Identidad de propuesta y perfil',
  }
  const labels: Record<AgentDelegationProposal['state'], string> = {
    PROPOSED: english ? 'Proposed' : 'Propuesta', RUNNING: english ? 'Running' : 'En curso', PASSED: english ? 'Returned with receipt' : 'Respuesta recibida con recibo',
    FAILED: english ? 'Failed' : 'Falló', INCONCLUSIVE: english ? 'Inconclusive' : 'Inconcluso', EXPIRED: english ? 'Expired' : 'Caducada', STALE: english ? 'Stale' : 'Desactualizada',
    OUT_OF_SCOPE: english ? 'Returned: outside scope' : 'Devuelta: fuera de alcance',
    NEEDS_AUTHORIZATION: english ? 'Waiting for additional permission' : 'Pendiente de permiso adicional',
    NEEDS_REVIEW: english ? 'Needs human review' : 'Requiere revisión humana',
  }

  async function browse(path?: string) {
    setBusy(true); setError('')
    try {
      const response = await fetch('/api/document-tools/folders' + (path ? `?path=${encodeURIComponent(path)}` : ''))
      if (!response.ok) throw new Error(await readError(response))
      const data = await response.json() as FolderListing
      if (!Array.isArray(data.roots) || !Array.isArray(data.directories)) throw new Error('Invalid folder response')
      setFolders(data); setOutputDirectory(data.output_directory || '')
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Folder lookup failed') }
    finally { setBusy(false) }
  }

  async function requestStatus() {
    setBusy(true); setError(''); setNotice('')
    try {
      const response = await fetch(`/api/agent-delegations/${encodeURIComponent(current.proposal_id)}?parent_conversation_id=${encodeURIComponent(parentConversationId)}`)
      if (!response.ok) throw new Error(await readError(response))
      const data = await response.json()
      const next = data?.agent_delegation as AgentDelegationProposal | undefined
      if (!next || !validStates.has(next.state) || next.proposal_id !== current.proposal_id || next.parent_conversation_id !== parentConversationId || next.agent_id !== current.agent_id) throw new Error('Delegation identity mismatch')
      setCurrent(next); setNotice(labels[next.state])
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Status could not be checked') }
    finally { setBusy(false) }
  }

  async function execute(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (busy || disabled || !confirmed || current.state !== 'PROPOSED' || current.parent_conversation_id !== parentConversationId || current.parent_revision !== parentRevision) return
    if (!hash.test(current.proposal_sha256) || (allowTools && !folder)) { setError(allowTools && !folder ? lang.chooseFirst : 'Proposal binding is invalid'); return }
    setBusy(true); setError(''); setNotice('')
    try {
      const response = await fetch(`/api/agent-delegations/${encodeURIComponent(current.proposal_id)}/execute`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          parent_conversation_id: parentConversationId, parent_revision: parentRevision, proposal_sha256: current.proposal_sha256, confirm: true,
          scope: { allow_tools: allowTools, root: allowTools ? folder : null, allow_export: allowExport, expected_output_directory: allowExport ? outputDirectory || null : null,
            review_work_id: reviewWork || null, review_candidate_id: reviewContext.runs.find(run => run.work_id === reviewWork)?.candidate_id ?? null,
            review_scope_sha256: reviewContext.runs.find(run => run.work_id === reviewWork)?.scope_sha256 ?? null, contact_id: reviewContact || null, allow_draft: allowDraft },
        }),
      })
      if (!response.ok) throw new Error(await readError(response))
      const data = await response.json()
      const next = data?.agent_delegation as AgentDelegationProposal | undefined
      const parent = data?.conversation as StoredConversation | undefined
      const child = data?.child_conversation as StoredConversation | null | undefined
      if (!next || !validStates.has(next.state) || next.proposal_id !== current.proposal_id || next.parent_conversation_id !== parentConversationId || next.agent_id !== current.agent_id || !terminal.has(next.state) && next.state !== 'RUNNING') throw new Error('Delegation response identity mismatch')
      if (!parent || parent.id !== parentConversationId || parent.owner_kind !== 'assistant' || parent.owner_id !== 'app-assistant' || !Array.isArray(parent.messages)) throw new Error('Parent conversation identity mismatch')
      if (child && (child.id !== next.child_conversation_id || child.owner_kind !== 'agent' || child.owner_id !== current.agent_id)) throw new Error('Child conversation identity mismatch')
      onConversationUpdate(parent); setCurrent(next); setNotice(labels[next.state])
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Execution response could not be verified') }
    finally { setBusy(false) }
  }

  const hasDeliveryTool = current.assigned_tools.some(tool => tool.startsWith('delivery_'))
  const hasAllowedTool = current.assigned_tools.some(tool => allowedHandlers.has(tool) || tool.startsWith('development_'))
  const hasExportTool = current.assigned_tools.includes('document_export')
  const hasDraftTool = current.assigned_tools.includes('delivery_prepare_draft')
  const expired = current.state === 'PROPOSED' && current.expires_at * 1000 <= Date.now()
  const canReview = current.state === 'PROPOSED' && !expired && !disabled && !busy && current.parent_conversation_id === parentConversationId && current.parent_revision === parentRevision
  const canExecute = canReview && confirmed
  const invalid = current.state === 'PROPOSED' && (current.parent_conversation_id !== parentConversationId || current.parent_revision !== parentRevision)
  return <section className="agent-delegation" aria-label={lang.heading} data-proposal-id={current.proposal_id}>
    <header className="agent-delegation-heading"><strong>{lang.heading}</strong><span data-state={current.state}>{labels[current.state]}</span></header>
    <dl className="agent-delegation-identity"><div><dt>{english ? 'Saved agent' : 'Agente guardado'}</dt><dd>{current.agent_name}</dd></div><div><dt>{english ? 'Provider / model' : 'Proveedor / modelo'}</dt><dd>{current.provider_id} / {current.model_id}</dd></div></dl>
    <p className="agent-delegation-task-label">{lang.task}</p><p className="agent-delegation-task">{current.task}</p>
    {current.assigned_tools.length > 0 && <details className="agent-delegation-assigned"><summary>{lang.assigned} ({current.assigned_tools.length})</summary><ul>{current.assigned_tools.map(tool => <li key={tool}><code>{tool}</code></li>)}</ul></details>}
    <p className="agent-delegation-note">{lang.noInherit}</p>
    {current.state === 'PROPOSED' && <form onSubmit={(event) => void execute(event)}>
      <fieldset disabled={!canReview}><legend>{lang.review}</legend>
        <label className="agent-delegation-consent"><input type="checkbox" checked={allowTools} disabled={!hasAllowedTool} onChange={event => { setAllowTools(event.target.checked); setAllowExport(false); setAllowDraft(false); setFolder(''); setReviewWork(''); setReviewContact(''); setConfirmed(false) }} />{lang.tools}</label>
        {allowTools && <div className="agent-delegation-folders"><button type="button" onClick={() => void browse()} disabled={busy}>{lang.choose}</button>{error && <p role="alert">{error}</p>}
          {folders && <div>{folders.roots.map(item => <button type="button" key={item.path} onClick={() => void browse(item.path)} disabled={busy}>{item.name}</button>)}
            {folders.parent && <button type="button" onClick={() => void browse(folders.parent!)} disabled={busy}>{lang.parent}</button>}
            {folders.directories.map(item => <button type="button" key={item.path} onClick={() => void browse(item.path)} disabled={busy}>{item.name}</button>)}
            {folders.path && <><code>{folders.path}</code><button type="button" onClick={() => { setFolder(folders.path!); setAllowExport(false); setAllowDraft(false); setConfirmed(false) }} disabled={busy}>{lang.use}</button></>}
          </div>}{folder && <p><strong>{lang.folder}:</strong> <code>{folder}</code></p>}</div>}
        {hasDeliveryTool && <section className="agent-delegation-review" aria-label={english ? 'Delivery review context' : 'Contexto de revisión de entrega'}>
          {contextError && <p role="alert">{lang.contextUnavailable}</p>}
          <label>{lang.work}<select value={reviewWork} onChange={event => { setReviewWork(event.target.value); setAllowDraft(false); setConfirmed(false) }} disabled={!allowTools || busy}><option value="">{lang.chooseWork}</option>{reviewContext.runs.map(run => <option key={run.work_id} value={run.work_id}>{run.producer_name || run.owner_id} · {run.artifacts.map(artifact => artifact.path.split('/').pop()).join(', ')}</option>)}</select></label>
          <label>{lang.contact}<select value={reviewContact} onChange={event => { setReviewContact(event.target.value); setAllowDraft(false); setConfirmed(false) }} disabled={!allowTools || busy}><option value="">{lang.chooseContact}</option>{reviewContext.contacts.map(contact => <option key={contact.id} value={contact.id}>{contact.name} · {contact.phone}</option>)}</select></label>
        </section>}
        {hasExportTool && <label className="agent-delegation-consent"><input type="checkbox" checked={allowExport} onChange={event => { setAllowExport(event.target.checked); setConfirmed(false) }} disabled={!allowTools || !folder || !outputDirectory} />{lang.export}{outputDirectory && <code>{outputDirectory}</code>}</label>}
        {hasDraftTool && <label className="agent-delegation-consent"><input type="checkbox" checked={allowDraft} onChange={event => { setAllowDraft(event.target.checked); setConfirmed(false) }} disabled={!allowTools || !reviewWork || !reviewContact} />{lang.draft}</label>}
        <label className="agent-delegation-confirm"><input type="checkbox" required checked={confirmed} onChange={event => setConfirmed(event.target.checked)} />{lang.confirm}</label>
        <button type="submit" disabled={!canExecute}>{busy ? lang.loading : lang.run}</button>
      </fieldset>
    </form>}
    {current.state === 'PROPOSED' && <p className="agent-delegation-note">{lang.notExecuted}</p>}
    {invalid && <p role="alert">{english ? 'This proposal does not match the active parent conversation revision.' : 'La propuesta no corresponde a la revisión activa de la conversación principal.'}</p>}
    {expired && <p role="status">{lang.expired}</p>}
    {(current.state !== 'PROPOSED' || expired) && <button type="button" onClick={() => void requestStatus()} disabled={busy}>{busy ? lang.loading : lang.refresh}</button>}
    {notice && <p role="status">{notice}</p>}
    {error && <p role="alert">{error}</p>}
    {current.assistant_message && <section className="agent-delegation-answer"><h4>{lang.answer}</h4><p>{current.assistant_message}</p></section>}
    <dl className="agent-delegation-evidence">
      {current.receipt_id && <div><dt>{lang.receipt}</dt><dd><code>{current.receipt_id}</code>{current.receipt_sha256 && <small>SHA-256 <code>{current.receipt_sha256}</code></small>}</dd></div>}
      {current.child_trace_id && <div><dt>{lang.trace}</dt><dd><code>{current.child_trace_id}</code>{current.child_trace_state && <span>{current.child_trace_state}</span>}{current.child_trace_sha256 && <small>SHA-256 <code>{current.child_trace_sha256}</code></small>}</dd></div>}
    </dl>
    <details className="agent-delegation-identifiers"><summary>{lang.identity}</summary><dl><div><dt>Proposal</dt><dd><code>{current.proposal_id}</code></dd></div><div><dt>Proposal SHA-256</dt><dd><code>{current.proposal_sha256}</code></dd></div><div><dt>Agent config SHA-256</dt><dd><code>{current.agent_config_sha256}</code></dd></div><div><dt>Task SHA-256</dt><dd><code>{current.task_sha256}</code></dd></div></dl></details>
    {current.child_conversation_id && <div className="agent-delegation-links">
      {onOpenChild && <button type="button" onClick={() => onOpenChild({ agentId: current.agent_id, conversationId: current.child_conversation_id! })}>{lang.openChild}</button>}
      {onInspectChild && current.child_trace_id && Number.isInteger(current.child_revision) && <button type="button" onClick={() => onInspectChild({ conversationId: current.child_conversation_id!, revision: current.child_revision!, traceId: current.child_trace_id! })}>{lang.inspect}</button>}
    </div>}
  </section>
}
