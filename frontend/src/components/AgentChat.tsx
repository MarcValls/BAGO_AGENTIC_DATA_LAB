import {t, useI18n, formatDate, formatNumber, apiError, errorMessage, localMessage} from '../i18n'
import './AgentChat.css'
import './ChatMessage.css'
import './WindowsSurface.css'
import type {InspectionSelection} from '../types/inspection'
import { FormEvent, useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import type { UIEvent } from 'react'
import { createPortal } from 'react-dom'
import { Capability, CapabilityProposal, capabilityResponseError } from './CapabilityManager'
import AgentBuilder from './AgentBuilder'
import WorkspaceManager, { type WorkspaceProposal } from './WorkspaceManager'
import WorkspaceWriteReview,{isWriteProposalSummary,type WriteProposalSummary} from './WorkspaceWriteReview'
import DirectoryScanRun, { type ScanOutcome, type ScanReceipt, type ScanReport, type ScanTrace } from './DirectoryScanRun'
import JobHistory from './JobHistory'
import Communications from './Communications'
import type { Draft as CommunicationDraft } from '../types/communications'
import ChatTools from './ChatTools'
import WindowPanel from './WindowPanel'
import TabStrip from './TabStrip'
import AssistantMarkdown from './AssistantMarkdown'

type AgentConfig = {
  name: string
  description: string
  type: 'rag' | 'tool' | 'multi-agent'
  system_prompt: string
  provider_id?: 'ollama-cloud' | 'openai-platform' | 'github-copilot' | null
  model_id?: string | null
  tools: string[]
  retrieval_config?: { mode: 'hybrid' | 'semantic' | 'lexical'; top_k: number } | null
  sandbox_profile?: string | null
}

type Agent = { id: string; config: AgentConfig; created_at: string }
type ChatProvider = { provider_id: string; label: string; model_id: string; display_name?: string; state: string; chat_enabled?: boolean; orchestrator_enabled?: boolean }
type ChatProviderSelection = { provider_id: string; model_id: string; label?: string; state?: string }
type MessageTrace = { localId: string; state: string; jaegerId?: string; jaegerUrl?: string }
function safePublicLink(value: string): string | undefined {try {const url = new URL(value);return url.protocol === 'https:' && !url.username && !url.password && !url.port ? url.href : undefined} catch {return undefined}}

type WorkspaceSource = { source_type?: 'public_web'; requested_url?: string; final_url?: string; captured_at?: string; raw_sha256?: string; text_sha256?: string; snapshot_id?: string; snapshot_manifest_sha256?: string; path: string; start_line: number; end_line: number; file_sha256?: string; content_sha256?: string }
type WorkspaceReadEvent = { decision: 'ALLOW' | 'DENY' | 'FAIL'; kind?: string; path: string | null; reason_code?: string; file_sha256?: string; content_sha256?: string; files_scanned?: number; files_skipped?: number; bytes_scanned?: number; lines_scanned?: number; finding_count?: number; truncated?: boolean; manifest_sha256?: string }
type CognitiveTrace = { mode: 'baseline' | 'bago5'; enabled: boolean; profile?: string | null; method?: string; focus: Array<{ id: string; kind: string; label: string; score: number }>; capacity?: number; max_hops?: number; trace_id?: string; trace_state?: string }
type Message = { uiContent?:Error; workspaceWriteProposal?:WriteProposalSummary; workspaceWriteProposalError?:string; status?: string; workspaceProposal?: WorkspaceProposal; communicationDraft?: CommunicationDraft; communicationDraftId?: string; id: string; role: 'user' | 'assistant'; content: string; trace?: MessageTrace; cognitiveTrace?: CognitiveTrace; sources?: WorkspaceSource[]; readEvents?: WorkspaceReadEvent[]; agentBuilderDraft?: AgentConfig; inlineJobHistory?: boolean; inlineDirectoryScan?: boolean; scanOutcome?: ScanOutcome; pendingNavigation?: ExistingView; navigationDecision?: 'accepted' | 'declined' }
type ConversationSummary = { id: string; owner_kind: 'assistant' | 'agent'; owner_id: string; title: string; status: 'active' | 'archived' | 'deleted'; updated_at: string; revision: number }
type StoredConversation = ConversationSummary & { messages: Array<{ id: string; role: 'user' | 'assistant'; content: string; status?: string; references?: { workspace_write_proposal?:unknown; workspace_proposal?: WorkspaceProposal; communication_draft_id?: string; communication_draft?: CommunicationDraft; trace?: { trace_id?: string; trace_state?: string; jaeger_trace_id?: string; jaeger_url?: string } & Partial<ScanTrace>; cognitive_trace?: CognitiveTrace; sources?: WorkspaceSource[]; read_events?: Array<WorkspaceReadEvent & Partial<ScanReceipt>>; scan_result?: ScanReport; control_capability?: string } }> }
type LibraryMode = 'active' | 'archived' | 'deleted'
type ControlOperation = 'chat' | 'help' | 'list_agents' | 'draft_agent' | 'navigate' | 'list_capabilities' | 'propose_capability'
type ExistingView = 'communications' | 'whatsapp_settings' | 'inspector' | 'builder' | 'chat' | 'workspace' | 'runner' | 'control' | 'jobs' | 'traces' | 'summary' | 'retrieval' | 'authorization' | 'evaluation' | 'evaluation_lab' | 'provider_settings' | 'cognition_settings' | 'capabilities'
type CapabilityDraft = { capabilities: Capability[]; capabilityId: string; summary: string; requestedScope: string; conversationId: string | null }

function CognitiveContextPanel({ trace }: { trace: CognitiveTrace }) {
  useI18n()

  const experimental = trace.mode === 'bago5'
  return <section className={`message-cognition${experimental ? ' message-cognition-bago5' : ''}`} aria-label={t('commerce.model_prompt_mode_and_cognitive_context')}>
    <div className="message-cognition-heading"><strong>{experimental ? t('commerce.bago5_cognitive_focus') : t('commerce.baseline_prompt')}</strong><span>{experimental ? t('commerce.experimental') : t('commerce.comparison')}</span></div>
    {experimental ? <>
      <ul>{trace.focus.map((item) => <li key={item.id}><span>{item.label}</span><code>{formatNumber(item.score,{minimumFractionDigits:3,maximumFractionDigits:3})}</code></li>)}</ul>
      <small>{t('commerce.focus_dimensions',{profile:trace.profile??'—',method:trace.method??'—',capacity:typeof trace.capacity==='number'?formatNumber(trace.capacity):t('commerce.unavailable'),hops:typeof trace.max_hops==='number'?formatNumber(trace.max_hops):t('commerce.unavailable')})}</small>
    </> : null}
    {trace.trace_id && <small>{t('commerce.local_focus_trace')} {trace.trace_id} · {humanState(trace.trace_state)}</small>}
  </section>
}


/** Human label plus original protocol code; unknown values never imply success. */
function humanState(value:string|undefined){
 const keys={"ALLOW":"commerce.state_allow","DENY":"commerce.state_deny","FAIL":"commerce.state_fail","FAILED":"commerce.trace_failed","PENDING_REVIEW":"commerce.state_pending_review","CANCELLED":"commerce.cancelled","EXPIRED":"commerce.state_expired","APPROVED":"commerce.state_approved","REJECTED":"commerce.state_rejected","ENABLED":"commerce.state_enabled","DISABLED":"commerce.state_disabled","REGISTERED":"commerce.state_registered","UNREGISTERED":"commerce.state_unregistered","AVAILABLE":"commerce.state_available","UNAVAILABLE":"commerce.state_not_available","recorded":"commerce.trace_recorded","persisted":"commerce.state_persisted","exported":"commerce.state_exported","unavailable":"commerce.trace_unavailable","pending":"commerce.trace_pending","failed":"commerce.trace_failed","unknown":"commerce.unknown_state","not_registered":"commerce.state_not_registered","read":"commerce.effect_read","write":"commerce.effect_write","execute":"commerce.effect_execute","read_only":"commerce.effect_read_only","external":"commerce.effect_external","none":"commerce.effect_none","network":"commerce.effect_network"} as const
 const key=keys[value as keyof typeof keys]
 return key?t(key)+' ('+value+')':t('commerce.unknown_code',{code:value??'—'})
}

const scrollbarHideTimers = new WeakMap<HTMLElement, number>()

function revealScrollbarWhileScrolling(event: UIEvent<HTMLElement>) {
  const element = event.target as HTMLElement
  element.classList.add('is-scrolling')
  const existingTimer = scrollbarHideTimers.get(element)
  if (existingTimer !== undefined) window.clearTimeout(existingTimer)
  scrollbarHideTimers.set(element, window.setTimeout(() => {
    element.classList.remove('is-scrolling')
    scrollbarHideTimers.delete(element)
  }, 700))
}

interface AgentChatProps {
  onInspectionSelection?: (selection: InspectionSelection|null) => void
  onInspectExecution?: (selection: InspectionSelection) => void
  onNavigate: (view: ExistingView) => void
  onManageAgents?: () => void
  onOpenCommunication?: (id: string) => void
  onOpenProviderSettings: () => void
  onOpenCognitionSettings: () => void
  cognitiveMode: 'baseline' | 'bago5'
}

const idFor = () => `${Date.now()}-${Math.random().toString(16).slice(2)}`

const viewLabels: Record<ExistingView, string> = {
  get communications(){return t('commerce.communications')}, whatsapp_settings: 'WhatsApp',
  get inspector(){return t('commerce.decision_inspector')}, get builder(){return t('commerce.agent_builder')}, chat: 'Chat', get workspace(){return t('commerce.workspace')}, get runner(){return t('commerce.agent_runs')},
  control: 'Control', get jobs(){return t('commerce.job_history')}, get traces(){return t('commerce.trace')}, get summary(){return t('commerce.summary')}, get retrieval(){return t('commerce.retrieval')},
  get authorization(){return t('commerce.authorization')}, get evaluation(){return t('commerce.evaluation')}, get evaluation_lab(){return t('commerce.agent_evaluation_lab')},
  get provider_settings(){return t('commerce.providers_and_models')}, get cognition_settings(){return t('commerce.cognition_and_context')}, get capabilities(){return t('commerce.capabilities')},
}

async function responseError(response: Response): Promise<Error> {
 let body:unknown=null
 try {body=await response.json()}catch { /* retain HTTP status */ }
 return apiError(body,response.status,'commerce')
}

function inferIntent(message: string, cognitiveMode: 'baseline' | 'bago5'): { operation: ControlOperation; view?: ExistingView } {
  const text = message.toLocaleLowerCase()
  const capabilityIdMentioned = /\b(?:workspace\.read_text|mcp\.execute|sandbox\.execute|agent\.run)\b/.test(text)
  if (/\b(propuesta|proponer|propose|proposal)\b/.test(text) && (/\b(capacidad|capability|acceso|access|habilitar|enable|registrar|register)\b/.test(text) || capabilityIdMentioned)) return { operation: 'propose_capability' }
  if ((/\b(capacidades|capabilities|capability catalog)\b/.test(text) && /\b(lista|listar|list|show|muestra|mostrar|consulta|consultar|describe|describir|qu[eé]|cu[aá]les|which|status|estado)\b/.test(text)) || (capabilityIdMentioned && /\b(estado|status|lista|listar|mostrar|show|describe|qu[eé])\b/.test(text))) return { operation: 'list_capabilities' }
  if (/^\s*(hola|buenas|hello|hi|hey)[!.\s]*$/.test(text) || /\b(qu[eé] puedes hacer|what can you do|capacidades del asistente|assistant capabilities)\b/.test(text) || /\b(puedes|can you|could you)\s+(crear|create|diseñar|design)\s+(un\s+|a\s+)?agentes?\s*[?!.]*$/.test(text) || /\b(no puedes|cannot|can't)\s+(crear|create)\s+agentes?\b/.test(text)) {
    return { operation: cognitiveMode === 'bago5' ? 'chat' : 'help' }
  }
  if (/\b(lista|listar|muestra|mostrar|qué|cu[aá]les)\b.*\b(agentes|agente)\b/.test(text) || /\b(agentes|agente)\b.*\b(lista|listar|hay|tengo)\b/.test(text)) {
    return { operation: 'list_agents' }
  }
  return { operation: 'chat' }
}

export default function AgentChat({ onInspectionSelection, onInspectExecution, onNavigate, onManageAgents, onOpenCommunication, onOpenProviderSettings, onOpenCognitionSettings, cognitiveMode }: AgentChatProps) {
  useI18n()

  const [agents, setAgents] = useState<Agent[]>([])
  const [agentsState, setAgentsState] = useState<'loading' | 'ready' | 'error'>('loading')
  const [inventoryWarning, setInventoryWarning] = useState<string|Error>('')
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [activeConversation, setActiveConversation] = useState<StoredConversation | null>(null)
  const [conversationList, setConversationList] = useState<ConversationSummary[]>([])
  const [conversationContextMenu, setConversationContextMenu] = useState<{ conversation: ConversationSummary; x: number; y: number } | null>(null)
  const [libraryMode, setLibraryMode] = useState<LibraryMode>('active')
  const [libraryError, setLibraryError] = useState<string|Error>('')
  const [permanentlyDeleting, setPermanentlyDeleting] = useState(false)
  const [loadingConversation, setLoadingConversation] = useState(false)
  const [creatingConversation, setCreatingConversation] = useState(false)
  const creatingConversationRef = useRef(false)
  const agentPanelRef = useRef<HTMLDetailsElement>(null)
  const [input, setInput] = useState('')
  const [messageCopyState, setMessageCopyState] = useState<{ id: string; state: 'copied' | 'failed' } | null>(null)
  const [messageContextMenu, setMessageContextMenu] = useState<{ id: string; agentId: string | null; latestUserId: string | undefined; conversationId: string | null; revision: number | null; x: number; y: number; origin: HTMLElement } | null>(null)
  const messageMenuRef = useRef<HTMLDivElement>(null)
  const [allowWorkspaceRead, setAllowWorkspaceRead] = useState(false)
  const [allowPublicWebRead, setAllowPublicWebRead] = useState(false)
  const [allowWorkspaceWriteProposals,setAllowWorkspaceWriteProposals]=useState(false)
  const [publicWebUrls, setPublicWebUrls] = useState('')
  const [workspaceReadPaths, setWorkspaceReadPaths] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState<string|Error>('')
  const [chatProviders, setChatProviders] = useState<ChatProvider[]>([])
  const [chatProviderSelection, setChatProviderSelection] = useState<ChatProviderSelection | null>(null)
  const [savingChatProvider, setSavingChatProvider] = useState(false)
  const [capabilityDraft, setCapabilityDraft] = useState<CapabilityDraft | null>(null)
  const [capabilityProposals, setCapabilityProposals] = useState<CapabilityProposal[]>([])
  const [capabilityBusy, setCapabilityBusy] = useState(false)
  const [agentPanelTarget, setAgentPanelTarget] = useState<HTMLDivElement | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const composerRef = useRef<HTMLTextAreaElement>(null)
  const contextMenuRef = useRef<HTMLDivElement>(null)
  const longPressTimerRef = useRef<number | null>(null)
  const longPressTriggeredRef = useRef(false)
  const agentRefreshAtRef = useRef(0)
  const agentRefreshInFlightRef = useRef<Promise<void> | null>(null)
  const agentsLoadedRef = useRef(false)

  const latestUserMessageId = [...messages].reverse().find((message) => message.role === 'user')?.id

  const copyMessage = async (message: Message) => {
    try {
      await navigator.clipboard.writeText(message.content)
      setMessageCopyState({ id: message.id, state: 'copied' })
    } catch {
      setMessageCopyState({ id: message.id, state: 'failed' })
    }
    window.setTimeout(() => setMessageCopyState((current) => current?.id === message.id ? null : current), 1800)
  }

  const editLatestMessage = (message: Message) => {
    setInput(message.content)
    composerRef.current?.focus()
    composerRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  }

  const canEditMessage = (message: Message) => message.role === 'user' && message.id === latestUserMessageId
  const messageEditDisabled = sending || Boolean(activeConversation && activeConversation.status !== 'active')
  const menuMessage = messageContextMenu && messageContextMenu.agentId === (selectedAgent?.id ?? null)
    && messageContextMenu.latestUserId === latestUserMessageId
    && messageContextMenu.conversationId === (activeConversation?.id ?? null)
    && messageContextMenu.revision === (activeConversation?.revision ?? null)
    ? messages.find(message => message.id === messageContextMenu.id && message.content) : undefined
  const closeMessageMenu = (restoreFocus = false) => {
    if (restoreFocus && messageContextMenu?.origin.isConnected) messageContextMenu.origin.focus()
    setMessageContextMenu(null)
  }
  const openMessageMenu = (message: Message, origin: HTMLElement, x: number, y: number) => {
    if (!message.content) return
    setConversationContextMenu(null)
    setMessageContextMenu({ id: message.id, agentId: selectedAgent?.id ?? null, latestUserId: latestUserMessageId, conversationId: activeConversation?.id ?? null,
      revision: activeConversation?.revision ?? null, x, y, origin })
  }
  useLayoutEffect(() => {
    const menu = messageMenuRef.current
    if (!messageContextMenu || !menuMessage || !menu) return
    const rect = menu.getBoundingClientRect()
    menu.style.left = `${Math.max(8, Math.min(messageContextMenu.x, window.innerWidth - rect.width - 8))}px`
    menu.style.top = `${Math.max(8, Math.min(messageContextMenu.y, window.innerHeight - rect.height - 8))}px`
    menu.querySelector<HTMLButtonElement>('button:not(:disabled)')?.focus()
  }, [messageContextMenu, menuMessage])
  useEffect(() => {
    if (!messageContextMenu) return
    if (!menuMessage) { setMessageContextMenu(null); return }
    const dismissOutside = (event: PointerEvent) => {
      if (event.target instanceof Node && messageMenuRef.current?.contains(event.target)) return
      setMessageContextMenu(null)
    }
    const dismiss = () => setMessageContextMenu(null)
    const dismissOnEscape = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return
      event.preventDefault()
      if (messageContextMenu.origin.isConnected) messageContextMenu.origin.focus()
      setMessageContextMenu(null)
    }
    document.addEventListener('pointerdown', dismissOutside)
    document.addEventListener('keydown', dismissOnEscape)
    window.addEventListener('resize', dismiss)
    window.addEventListener('blur', dismiss)
    document.addEventListener('scroll', dismiss, true)
    return () => {
      document.removeEventListener('pointerdown', dismissOutside)
      document.removeEventListener('keydown', dismissOnEscape)
      window.removeEventListener('resize', dismiss)
      window.removeEventListener('blur', dismiss)
      document.removeEventListener('scroll', dismiss, true)
    }
  }, [messageContextMenu, menuMessage])

  useEffect(() => {
    let active = true
    const load = () => { void Promise.all([
      fetch('/api/providers/chat-models').then(async response => {
        if (!response.ok) throw await responseError(response)
        return response.json() as Promise<{ models?: ChatProvider[] }>
      }),
      fetch('/api/providers/selection').then(async response => response.ok ? response.json() as Promise<ChatProviderSelection> : null),
    ]).then(([available, selected]) => {
      if (!active) return
      const usable = (available.models ?? []).filter(provider => ['ready', 'configured_unverified'].includes(provider.state) && provider.model_id && (provider.orchestrator_enabled ?? provider.chat_enabled) !== false)
      setChatProviders(usable)
      setChatProviderSelection(selected)
    }).catch(cause => {
      if (active) setError(cause instanceof Error ? cause : "commerce.could_not_load_orchestrator_models")
    })
    }
    load()
    window.addEventListener('adl-model-policy-changed', load)
    return () => { active = false; window.removeEventListener('adl-model-policy-changed', load) }
  }, [])

  const changeChatProvider = async (value: string) => {
    const [provider_id, model_id] = value.split('|')
    if (!provider_id || !model_id) return
    setSavingChatProvider(true); setError('')
    try {
      const response = await fetch('/api/providers/selection', {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider_id, model_id }),
      })
      if (!response.ok) throw await responseError(response)
      setChatProviderSelection(await response.json() as ChatProviderSelection)
    } catch (cause) {
      setError(cause instanceof Error ? cause : "commerce.could_not_change_the_orchestrator_model")
    } finally { setSavingChatProvider(false) }
  }

  const refreshAgents = useCallback(async ({ background = false }: { background?: boolean } = {}) => {
    const inFlight = agentRefreshInFlightRef.current
    if (inFlight) return inFlight
    if (!background) setAgentsState('loading')
    agentRefreshAtRef.current = Date.now()
    const request = (async () => {
      try {
        const response = await fetch('/api/agents/list')
        if (!response.ok) throw await responseError(response)
        const data = await response.json()
        const nextAgents = Array.isArray(data.agents) ? data.agents as Agent[] : []
        setAgents(nextAgents)
        setSelectedAgent((current) => current ? nextAgents.find((agent) => agent.id === current.id) ?? current : null)
        agentsLoadedRef.current = true
        setInventoryWarning(data.warning_count
          ? localMessage('commerce.agent_records_skipped',{get count(){return formatNumber(data.warning_count)}})
          : '')
        setAgentsState('ready')
      } catch (cause) {
        if (background && agentsLoadedRef.current) {
          setInventoryWarning("commerce.could_not_refresh_the_agent_list_showing_the_last_loaded_list")
        } else {
          setAgentsState('error')
          setError(cause instanceof Error ? cause : "commerce.agent_inventory_could_not_be_loaded")
        }
      }
    })()
    agentRefreshInFlightRef.current = request
    try {
      await request
    } finally {
      if (agentRefreshInFlightRef.current === request) agentRefreshInFlightRef.current = null
    }
  }, [])

  const ownerKind = selectedAgent ? 'agent' : 'assistant'
  const ownerId = selectedAgent?.id ?? 'app-assistant'

  useEffect(() => {onInspectionSelection?.(activeConversation ? {conversationId:activeConversation.id,revision:activeConversation.revision} : null)}, [activeConversation?.id, activeConversation?.revision, onInspectionSelection])

  const conversationLoadGeneration = useRef(0)
  const conversationScope = `${ownerKind}:${ownerId}:${libraryMode}`
  const conversationScopeRef = useRef(conversationScope)
  conversationScopeRef.current = conversationScope
  const matchesOwner = (conversation: ConversationSummary) => conversation.owner_kind === ownerKind && conversation.owner_id === ownerId
  const clearInspectionSelection = () => {setActiveConversation(null);setMessages([]);onInspectionSelection?.(null)}

  useEffect(() => {setAllowPublicWebRead(false);setAllowWorkspaceWriteProposals(false);setPublicWebUrls('')}, [activeConversation?.id, ownerId])

  const applyConversation = (conversation: StoredConversation) => {
    const inlineAgentDrafts = new Map(messages.filter((message) => message.agentBuilderDraft).map((message) => [message.id, message.agentBuilderDraft as AgentConfig]))
    const inlineJobHistoryIds = new Set(messages.filter((message) => message.inlineJobHistory).map((message) => message.id))
    const inlineDirectoryScanIds = new Set(messages.filter((message) => message.inlineDirectoryScan).map((message) => message.id))
    const pendingNavigations = new Map(messages.filter((message) => message.pendingNavigation).map((message) => [message.id, { view: message.pendingNavigation as ExistingView, decision: message.navigationDecision }]))
    setActiveConversation(conversation)
    setMessages(conversation.messages.map((message) => {
      const writeProposal=message.references?.workspace_write_proposal
      const validWriteProposal=message.role==='assistant'&&isWriteProposalSummary(writeProposal,{ownerKind:conversation.owner_kind,ownerId:conversation.owner_id,conversationId:conversation.id,conversationRevision:conversation.revision})
      const trace = message.references?.trace
      const scanReceipt = message.references?.read_events?.find((event) => event.kind === 'directory_code_scan')
      const scanTrace = message.references?.trace
      const scanOutcome = message.references?.scan_result && scanReceipt && scanTrace?.trace_id && scanTrace.trace_state
        ? { result: message.references.scan_result, receipt: scanReceipt as ScanReceipt, trace: { trace_id: scanTrace.trace_id, trace_state: scanTrace.trace_state }, conversation_id: conversation.id }
        : undefined
      return {
        id: message.id,
        role: message.role,
        content: message.content,
        status: message.status,
        ...(writeProposal!==undefined ? validWriteProposal ? {workspaceWriteProposal:writeProposal} : {workspaceWriteProposalError:'commerce.the_file_proposal_does_not_belong_to_the_current_agent_or_conversation'} : {}),
        ...(message.references?.communication_draft_id ? { communicationDraftId: message.references.communication_draft_id } : {}),
        ...(message.references?.communication_draft ? { communicationDraft: message.references.communication_draft } : {}),
        ...(inlineAgentDrafts.has(message.id) ? { agentBuilderDraft: inlineAgentDrafts.get(message.id) } : {}),
        ...(inlineJobHistoryIds.has(message.id) ? { inlineJobHistory: true } : {}),
        ...(message.references?.workspace_proposal ? { workspaceProposal: message.references.workspace_proposal } : {}),
        ...(message.references?.control_capability === 'workspace.scan_duplicates' || inlineDirectoryScanIds.has(message.id) ? { inlineDirectoryScan: true } : {}),
        ...(scanOutcome ? { scanOutcome } : {}),
        ...(pendingNavigations.has(message.id) ? { pendingNavigation: pendingNavigations.get(message.id)?.view, navigationDecision: pendingNavigations.get(message.id)?.decision } : {}),
        ...(!scanOutcome && trace?.trace_id ? { trace: { localId: trace.trace_id, state: trace.trace_state || 'unknown', jaegerId: trace.jaeger_trace_id, jaegerUrl: trace.jaeger_url } } : {}),
        ...(message.references?.cognitive_trace ? { cognitiveTrace: message.references.cognitive_trace } : {}),
        ...(message.references?.sources?.length ? { sources: message.references.sources } : {}),
        ...(!scanOutcome && Array.isArray((message.references as any)?.read_events) ? { readEvents: (message.references as any).read_events } : {}),
      }
    }))
  }

  const refreshConversationList = async () => {
    const generation = ++conversationLoadGeneration.current
    const scope = conversationScopeRef.current
    const current = () => generation === conversationLoadGeneration.current && scope === conversationScopeRef.current
    setLibraryError('')
    try {
      const query = new URLSearchParams({ owner_kind: ownerKind, owner_id: ownerId, status: libraryMode })
      const response = await fetch(`/api/conversations?${query}`)
      if (!response.ok) throw await responseError(response)
      const data = await response.json()
      if (!current()) return
      const conversations = Array.isArray(data.conversations) ? data.conversations as ConversationSummary[] : []
      setConversationList(conversations)
      if (!activeConversation || activeConversation.owner_kind !== ownerKind || activeConversation.owner_id !== ownerId || activeConversation.status !== libraryMode) {
        if (libraryMode === 'deleted' && conversations.length) {
          setActiveConversation({ ...conversations[0], messages: [] })
          setMessages([])
        } else if (conversations.length) {
          const latest = await fetch(`/api/conversations/${encodeURIComponent(conversations[0].id)}`)
          if (latest.ok) {const detail = await latest.json() as StoredConversation;if (current() && detail.id === conversations[0].id && matchesOwner(detail)) applyConversation(detail)}
          else { setActiveConversation(null); setMessages([]) }
        } else {
          setActiveConversation(null)
          setMessages([])
        }
      }
    } catch (cause) {
      if (!current()) return
      setLibraryError(cause instanceof Error ? cause : "commerce.conversation_library_could_not_be_loaded")
    }
  }

  useEffect(() => { void refreshAgents() }, [refreshAgents])
  useEffect(() => {
    const refreshIfStale = () => {
      if (document.visibilityState !== 'visible' || Date.now() - agentRefreshAtRef.current < 30_000) return
      void refreshAgents({ background: true })
    }
    document.addEventListener('visibilitychange', refreshIfStale)
    window.addEventListener('focus', refreshIfStale)
    return () => {
      document.removeEventListener('visibilitychange', refreshIfStale)
      window.removeEventListener('focus', refreshIfStale)
    }
  }, [refreshAgents])
  useEffect(() => {clearInspectionSelection(); void refreshConversationList();return () => {conversationLoadGeneration.current++}}, [ownerKind, ownerId, libraryMode])
  useEffect(() => { void refreshConversationProposals(activeConversation?.id ?? null) }, [activeConversation?.id])
  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])
  useEffect(() => {
    if (!conversationContextMenu) return
    contextMenuRef.current?.querySelector<HTMLButtonElement>('button')?.focus()
    const dismiss = (event: PointerEvent) => {
      if (event.target instanceof Element && event.target.closest('[data-conversation-context-menu]')) return
      setConversationContextMenu(null)
    }
    const dismissOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setConversationContextMenu(null)
    }
    document.addEventListener('pointerdown', dismiss)
    document.addEventListener('keydown', dismissOnEscape)
    return () => {
      document.removeEventListener('pointerdown', dismiss)
      document.removeEventListener('keydown', dismissOnEscape)
    }
  }, [conversationContextMenu])
  useEffect(() => () => {
    if (longPressTimerRef.current !== null) window.clearTimeout(longPressTimerRef.current)
  }, [])

  const startConversation = async () => {
    if (creatingConversationRef.current) return
    creatingConversationRef.current = true
    setCreatingConversation(true)
    const generation = ++conversationLoadGeneration.current
    const scope = conversationScopeRef.current
    const current = () => generation === conversationLoadGeneration.current && scope === conversationScopeRef.current
    setLibraryError('')
    try {
      const response = await fetch('/api/conversations', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ owner_kind: ownerKind, owner_id: ownerId }),
      })
      if (!current()) return
      if (!response.ok) throw await responseError(response)
      const conversation = await response.json() as ConversationSummary
      if (!current()) return
      const detail = await fetch(`/api/conversations/${encodeURIComponent(conversation.id)}`)
      if (!detail.ok) throw await responseError(detail)
      const loaded = await detail.json() as StoredConversation
      if (!current()) return
      if (loaded.id !== conversation.id || !matchesOwner(loaded) || loaded.status !== 'active') throw new Error("commerce.conversation_response_identity_mismatch")
      const query = new URLSearchParams({ owner_kind: ownerKind, owner_id: ownerId, status: 'active' })
      const list = await fetch(`/api/conversations?${query}`)
      const listed = list.ok ? (await list.json()).conversations : null
      if (!current()) return
      applyConversation(loaded)
      if (Array.isArray(listed)) setConversationList(listed)
      setLibraryMode('active')
      setInput('')
      if (agentPanelRef.current) agentPanelRef.current.open = false
      composerRef.current?.focus()
    } catch (cause) {
      if (current()) setLibraryError(cause instanceof Error ? cause : "commerce.a_new_conversation_could_not_be_created")
    } finally {
      creatingConversationRef.current = false
      setCreatingConversation(false)
    }
  }

  const openConversation = async (conversationId: string) => {
    const generation = ++conversationLoadGeneration.current
    const scope = conversationScopeRef.current
    clearInspectionSelection()
    setLoadingConversation(true)
    setLibraryError('')
    try {
      const response = await fetch(`/api/conversations/${encodeURIComponent(conversationId)}`)
      if (!response.ok) throw await responseError(response)
      const loaded = await response.json() as StoredConversation
      if (generation !== conversationLoadGeneration.current || scope !== conversationScopeRef.current) return
      if (loaded.id !== conversationId || !matchesOwner(loaded)) throw new Error("commerce.conversation_response_identity_mismatch")
      applyConversation(loaded)
    } catch (cause) {
      if (generation !== conversationLoadGeneration.current || scope !== conversationScopeRef.current) return
      setLibraryError(cause instanceof Error ? cause : "commerce.conversation_could_not_be_opened")
    } finally { if (generation === conversationLoadGeneration.current) setLoadingConversation(false) }
  }

  const manageConversation = async (action: 'rename' | 'archive' | 'delete' | 'restore', target: ConversationSummary | StoredConversation | null = activeConversation) => {
    if (!target) return
    const title = action === 'rename' ? window.prompt(t('commerce.conversation_title'), target.title) : null
    if (action === 'rename' && title === null) return
    const route = action === 'rename' ? `/api/conversations/${target.id}` : `/api/conversations/${target.id}/${action}`
    const method = action === 'rename' ? 'PATCH' : 'POST'
    const body = action === 'rename' ? { revision: target.revision, title } : { revision: target.revision }
    try {
      const response = await fetch(route, { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
      if (!response.ok) throw await responseError(response)
      if (action === 'delete') {
        if (activeConversation?.id === target.id) { setActiveConversation(null); setMessages([]) }
        setLibraryMode('deleted')
      } else {
        const updated = await response.json() as StoredConversation
        if (activeConversation?.id === target.id) applyConversation(updated)
        if (action === 'archive') setLibraryMode('archived')
        if (action === 'restore') setLibraryMode('active')
      }
      await refreshConversationList()
    } catch (cause) {
      setLibraryError(cause instanceof Error ? cause : "commerce.conversation_could_not_be_updated")
      if (cause instanceof Error && cause.message.includes('changed elsewhere')) await refreshConversationList()
    }
  }

  const showConversationContextMenu = (conversation: ConversationSummary, x: number, y: number) => {
    const menuWidth = 184
    const menuHeight = conversation.status === 'active' ? 132 : 104
    setConversationContextMenu({
      conversation,
      x: Math.max(8, Math.min(x, window.innerWidth - menuWidth - 8)),
      y: Math.max(8, Math.min(y, window.innerHeight - menuHeight - 8)),
    })
  }

  const permanentlyDeleteConversation = async (target: ConversationSummary | null = activeConversation) => {
    if (!target || target.status !== 'deleted' || permanentlyDeleting) return
    if (!window.confirm(t('commerce.permanently_delete_conversation',{title:target.title}))) return
    setPermanentlyDeleting(true)
    setLibraryError('')
    try {
      const response = await fetch(`/api/conversations/${encodeURIComponent(target.id)}`, {
        method: 'DELETE', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ expected_revision: target.revision, confirmed: true }),
      })
      if (!response.ok) throw await responseError(response)
      if (activeConversation?.id === target.id) { setActiveConversation(null); setMessages([]) }
      setConversationContextMenu(null)
      await refreshConversationList()
    } catch (cause) {
      setLibraryError(cause instanceof Error ? cause : "commerce.could_not_permanently_delete_the_conversation")
    } finally { setPermanentlyDeleting(false) }
  }

  const cancelConversationLongPress = () => {
    if (longPressTimerRef.current !== null) window.clearTimeout(longPressTimerRef.current)
    longPressTimerRef.current = null
  }

  async function refreshConversationProposals(conversationId: string | null) {
    if (!conversationId) { setCapabilityProposals([]); return }
    try {
      const response = await fetch('/api/capabilities/proposals?status=all&limit=100')
      if (!response.ok) throw await responseError(response)
      const data = await response.json()
      setCapabilityProposals((Array.isArray(data.proposals) ? data.proposals : []).filter((item: CapabilityProposal) => item.conversation_id === conversationId))
    } catch (cause) {
      setError(cause instanceof Error ? cause : "commerce.capability_proposals_could_not_be_loaded")
    }
  }

  async function beginCapabilityRequest(content: string, operation: 'list_capabilities' | 'propose_capability', conversationId: string | null) {
    setCapabilityBusy(true)
    setCapabilityDraft(null)
    setError('')
    try {
      const response = await fetch('/api/capabilities')
      if (!response.ok) throw await responseError(response)
      const catalog = await response.json()
      const capabilities = Array.isArray(catalog.capabilities) ? catalog.capabilities as Capability[] : []
      setMessages((previous) => [...previous, { id: idFor(), role: 'user', content }])
      if (operation === 'list_capabilities') {
        const summary = capabilities.length
          ? capabilities.map((item) => `${item.id}: ${humanState(item.status)} (${humanState(item.effect)}) — ${item.name}`).join('\n')
          : t('commerce.the_backend_returned_no_capability_records')
        setMessages((previous) => [...previous, { id: idFor(), role: 'assistant', content: `${summary}\n\n${catalog.authority_notice || t('commerce.catalog_status_does_not_grant_permission_or_enable_execution')}`, uiContent:localMessage('commerce.catalog_local_message',{get records(){return capabilities.length?summary:t('commerce.the_backend_returned_no_capability_records')},get notice(){return catalog.authority_notice||t('commerce.catalog_status_does_not_grant_permission_or_enable_execution')}}) }])
        return
      }
      const lower = content.toLocaleLowerCase()
      const exactMatches = capabilities.filter((item) => lower.includes(item.id.toLocaleLowerCase()) || lower.includes(item.name.toLocaleLowerCase()))
      const capabilityId = exactMatches.length === 1 ? exactMatches[0].id : ''
      const summary = content.trim().slice(0, 500)
      setCapabilityDraft({ capabilities, capabilityId, summary, requestedScope: '', conversationId })
      setMessages((previous) => [...previous, { id: idFor(), role: 'assistant', content: exactMatches.length === 1
        ? t('commerce.exact_capability',{id:exactMatches[0].id})
        : t('commerce.i_could_not_select_one_exact_catalog_entry_from_that_request_choose_the_intended_capability_below_no_fuzzy_sel') }])
    } catch (cause) {
      setError(cause instanceof Error ? cause : "commerce.capability_catalog_could_not_be_loaded")
    } finally { setCapabilityBusy(false) }
  }

  async function saveCapabilityProposal() {
    if (!capabilityDraft || capabilityBusy || !capabilityDraft.capabilityId || !capabilityDraft.summary.trim() || !capabilityDraft.requestedScope.trim()) return
    setCapabilityBusy(true)
    setError('')
    try {
      const response = await fetch('/api/capabilities/proposals', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ capability_id: capabilityDraft.capabilityId, summary: capabilityDraft.summary, requested_scope: capabilityDraft.requestedScope, ...(capabilityDraft.conversationId ? { conversation_id: capabilityDraft.conversationId } : {}) }),
      })
      if (!response.ok) throw await responseError(response)
      const result = await response.json()
      const saved = result.proposal as CapabilityProposal
      setCapabilityProposals((previous) => [saved, ...previous.filter((item) => item.id !== saved.id)])
      setMessages((previous) => [...previous, { id: idFor(), role: 'assistant', content: t('commerce.proposal_saved',{notice:result.authority_notice || t('commerce.proposal_saved_for_review_only_no_permission_job_or_execution_was_created'),id:saved.id}), uiContent:localMessage('commerce.proposal_saved',{get notice(){return result.authority_notice||t('commerce.proposal_saved_for_review_only_no_permission_job_or_execution_was_created')},id:saved.id}) }])
      setCapabilityDraft(null)
    } catch (cause) {
      setError(cause instanceof Error ? cause : "commerce.capability_proposal_could_not_be_saved")
    } finally { setCapabilityBusy(false) }
  }

  async function cancelChatProposal(proposal: CapabilityProposal) {
    setCapabilityBusy(true)
    setError('')
    try {
      const response = await fetch(`/api/capabilities/proposals/${encodeURIComponent(proposal.id)}/cancel`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ revision: proposal.revision }) })
      if (!response.ok) throw await responseError(response)
      const result = await response.json()
      setCapabilityProposals((previous) => previous.map((item) => item.id === proposal.id ? result.proposal : item))
      setMessages((previous) => [...previous, { id: idFor(), role: 'assistant', content: result.authority_notice }])
    } catch (cause) {
      setError(cause instanceof Error ? cause : "commerce.capability_proposal_could_not_be_cancelled")
      await refreshConversationProposals(activeConversation?.id ?? null)
    } finally { setCapabilityBusy(false) }
  }

  const sendMessage = async (event?: FormEvent) => {
    event?.preventDefault()
    const content = input.trim()
    if (!content || sending) return
    setInput('')
    setError('')
    setLibraryError('')
    const readFilesForThisMessage = allowWorkspaceRead
    const readWebForThisMessage = allowPublicWebRead
    const proposeFilesForThisMessage=Boolean(selectedAgent)&&allowWorkspaceWriteProposals
    const urlsForThisMessage = publicWebUrls
    setAllowWorkspaceRead(false)
    setAllowPublicWebRead(false)
    setAllowWorkspaceWriteProposals(false)
    setSending(true)
    const generation = conversationLoadGeneration.current
    const scope = conversationScopeRef.current
    const current = () => generation === conversationLoadGeneration.current && scope === conversationScopeRef.current
    let attemptedConversation: StoredConversation | null = null
    let failedDetail: any = null
    try {
      let conversation = activeConversation
      if (!conversation || conversation.owner_kind !== ownerKind || conversation.owner_id !== ownerId || conversation.status !== 'active') {
        const createResponse = await fetch('/api/conversations', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ owner_kind: ownerKind, owner_id: ownerId }),
        })
        if (!createResponse.ok) throw await responseError(createResponse)
        const summary = await createResponse.json() as ConversationSummary
        conversation = { ...summary, messages: [] }
        if (!current() || !matchesOwner(conversation)) return
        setActiveConversation(conversation)
      }
      attemptedConversation = conversation
      const localCapabilityIntent = !selectedAgent ? inferIntent(content, cognitiveMode) : null
      if (localCapabilityIntent?.operation === 'list_capabilities' || localCapabilityIntent?.operation === 'propose_capability') {
        await beginCapabilityRequest(content, localCapabilityIntent.operation, conversation.id)
        return
      }
      setMessages((previous) => [...previous, { id: idFor(), role: 'user', content }])
      let workspaceReadAuthorizationId: string | undefined
      if (readFilesForThisMessage) {
        const paths = workspaceReadPaths.split(/\r?\n/).map((path) => path.trim()).filter(Boolean)
        if (!paths.length) throw new Error("commerce.enter_the_exact_project_relative_file_paths_to_authorize_one_per_line")
        const authorizationResponse = await fetch('/api/workspace-read/authorizations', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ owner_kind: ownerKind, owner_id: ownerId, conversation_id: conversation.id, revision: conversation.revision, paths }),
        })
        if (!authorizationResponse.ok) throw await responseError(authorizationResponse)
        const authorization = await authorizationResponse.json()
        workspaceReadAuthorizationId = authorization.authorization_id
      }
      let webReadAuthorizationId: string | undefined
      if (readWebForThisMessage) {
        const urls = [...new Set(urlsForThisMessage.split(/\r?\n/).map(value => value.trim()).filter(Boolean))]
        if (!urls.length || urls.length > 8) throw new Error("commerce.enter_1_to_8_public_https_urls_one_per_line")
        const origins = [...new Set(urls.map(value => {
          let url: URL
          try {url = new URL(value)} catch {throw new Error("commerce.the_web_reading_url_is_invalid")}
          if (url.protocol !== 'https:' || url.username || url.password || url.port) throw new Error("commerce.web_reading_requires_https_without_credentials_or_alternate_ports")
          return url.origin
        }))]
        const authorizationResponse = await fetch('/api/web-read/authorizations', {
          method: 'POST', headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({owner_kind: ownerKind, owner_id: ownerId, conversation_id: conversation.id, revision: conversation.revision, urls}),
        })
        if (!authorizationResponse.ok) throw await responseError(authorizationResponse)
        const authorization = await authorizationResponse.json()
        if (typeof authorization.authorization_id !== 'string' || !authorization.authorization_id.trim() || !Array.isArray(authorization.allowed_origins) || authorization.allowed_origins.length !== origins.length || !origins.every(origin => authorization.allowed_origins.includes(origin))) throw new Error("commerce.the_server_did_not_confirm_the_requested_web_scope_the_turn_was_not_sent")
        webReadAuthorizationId = authorization.authorization_id
      }
      if (!current()) return
      let response: Response
      let data: any
      let intent: ReturnType<typeof inferIntent> | null = null
      if (selectedAgent) {
        response = await fetch(`/api/agents/${encodeURIComponent(selectedAgent.id)}/chat`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: content, conversation_id: conversation.id, revision: conversation.revision, cognitive_mode: cognitiveMode, ...(proposeFilesForThisMessage?{allow_workspace_write_proposals:true}:{}), ...(workspaceReadAuthorizationId ? { workspace_read_authorization_id: workspaceReadAuthorizationId } : {}), ...(webReadAuthorizationId ? {web_read_authorization_id: webReadAuthorizationId} : {}) }),
        })
      } else {
        intent = localCapabilityIntent ?? inferIntent(content, cognitiveMode)
        response = await fetch('/api/chat/control', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ operation: intent.operation, message: content, conversation_id: conversation.id, revision: conversation.revision, ...(intent.operation === 'chat' ? { cognitive_mode: cognitiveMode } : {}), ...(workspaceReadAuthorizationId ? { workspace_read_authorization_id: workspaceReadAuthorizationId } : {}), ...(webReadAuthorizationId ? {web_read_authorization_id: webReadAuthorizationId} : {}), ...(intent.view ? { view: intent.view } : {}) }),
        })
      }
      if (!current()) return
      if (!response.ok) {
        let body: any = null
        try { body = await response.json() } catch { /* preserve the HTTP error */ }
        failedDetail = body?.detail
        throw apiError(body,response.status,'commerce')
      }
      data = await response.json()
      if (!current()) return
      if (selectedAgent) {
        const provider = selectedAgent.config.provider_id || 'ollama-cloud'
        const expectedSource = provider === 'ollama-cloud' ? 'ollama' : provider
        if (data.source !== expectedSource || typeof data.assistant_message !== 'string') throw new Error("commerce.the_server_did_not_confirm_a_response_from_the_selected_provider")
      }
      if (Array.isArray(data.read_events) && data.read_events.length) {
        setMessages((previous) => [...previous, { id: idFor(), role: 'assistant', content: '', readEvents: data.read_events }])
      }
      if (!data.conversation || data.conversation.id !== conversation.id || !matchesOwner(data.conversation) || !Array.isArray(data.conversation.messages)) throw new Error("commerce.the_server_did_not_return_the_saved_conversation")
      applyConversation(data.conversation as StoredConversation)
      if (data.communication_draft) {
        const lastAssistant = [...data.conversation.messages].reverse().find((message: Message) => message.role === 'assistant')
        if (!lastAssistant || typeof data.communication_draft.id !== 'string') throw new Error("commerce.the_draft_has_no_valid_conversation_reference")
        setMessages(previous => previous.map(message => message.id === lastAssistant.id ? { ...message, communicationDraft: data.communication_draft, communicationDraftId: data.communication_draft.id } : message))
      }
      if (data.communication_draft) { /* Editing prepares a draft; the separate review authorizes effects. */ } else if (data.operation === 'list_agents') {
        setAgents(Array.isArray(data.agents) ? data.agents : [])
        setInventoryWarning(data.warning_count ? localMessage('commerce.agent_records_skipped',{count:data.warning_count}) : '')
      } else if (data.operation === 'draft_agent') {
        if (!data.agent_draft || data.created !== false) throw new Error("commerce.the_server_returned_an_invalid_or_already_created_proposal")
        const proposedDraft = data.agent_draft as AgentConfig
        const assistantMessages = (data.conversation as StoredConversation).messages.filter((message) => message.role === 'assistant')
        const assistantMessageId = assistantMessages[assistantMessages.length - 1]?.id
        if (!assistantMessageId) throw new Error("commerce.the_agent_proposal_has_no_matching_assistant_message")
        setMessages((previous) => previous.map((message) => message.id === assistantMessageId
          ? { ...message, agentBuilderDraft: proposedDraft }
          : message))
      } else if (data.operation === 'job_history') {
        const assistantMessages = (data.conversation as StoredConversation).messages.filter((message) => message.role === 'assistant')
        const assistantMessageId = assistantMessages[assistantMessages.length - 1]?.id
        if (!assistantMessageId) throw new Error("commerce.the_job_history_request_has_no_matching_assistant_message")
        setMessages((previous) => previous.map((message) => message.id === assistantMessageId
          ? { ...message, inlineJobHistory: true }
          : message))
      } else if (data.operation === 'workspace_action') {
        if (!data.workspace_proposal) throw new Error("commerce.missing_workspace_proposal")
      } else if (data.operation === 'workspace_scan') {
        const assistantMessages = (data.conversation as StoredConversation).messages.filter((message) => message.role === 'assistant')
        const assistantMessageId = assistantMessages[assistantMessages.length - 1]?.id
        if (!assistantMessageId) throw new Error("commerce.the_code_scan_request_has_no_matching_assistant_message")
        setMessages((previous) => previous.map((message) => message.id === assistantMessageId
          ? { ...message, inlineDirectoryScan: true }
          : message))
      } else if (data.operation === 'confirm_navigation') {
        const view = data.navigation?.view as ExistingView | undefined
        if (!view || !(view in viewLabels)) throw new Error("commerce.the_server_did_not_identify_a_valid_destination_view")
        const assistantMessages = (data.conversation as StoredConversation).messages.filter((message) => message.role === 'assistant')
        const assistantMessageId = assistantMessages[assistantMessages.length - 1]?.id
        if (!assistantMessageId) throw new Error("commerce.the_navigation_confirmation_has_no_matching_assistant_message")
        setMessages((previous) => previous.map((message) => message.id === assistantMessageId ? { ...message, pendingNavigation: view } : message))
      } else if (!selectedAgent && !['chat', 'help'].includes(data.operation)) {
        throw new Error("commerce.the_server_returned_an_unsupported_chat_operation")
      }
      const query = new URLSearchParams({ owner_kind: ownerKind, owner_id: ownerId, status: libraryMode })
      const listResponse = await fetch(`/api/conversations?${query}`)
      if (listResponse.ok) {
        const list = await listResponse.json()
        if (current()) setConversationList(list.conversations || [])
      }
    } catch (cause) {
      if (!current()) return
      // A failed response is still a failure. Restore only evidence bound to this
      // exact attempt, without clearing the current messages or the original error.
      setError(cause instanceof Error ? cause : "commerce.the_request_could_not_be_completed")
      if (attemptedConversation && failedDetail?.execution_state === 'FAILED'
        && failedDetail.conversation_id === attemptedConversation.id
        && failedDetail.evidence_persistence?.conversation === 'persisted'
        && Number.isInteger(failedDetail.revision) && failedDetail.revision > attemptedConversation.revision) {
        try {
          const saved = await fetch(`/api/conversations/${encodeURIComponent(attemptedConversation.id)}`)
          if (!saved.ok || !current()) return
          const loaded = await saved.json() as StoredConversation
          const lastMessage = loaded.messages?.[loaded.messages.length - 1]
          const expectedTrace = failedDetail.trace?.trace_id
          if (current() && loaded.id === attemptedConversation.id && matchesOwner(loaded)
            && loaded.revision === failedDetail.revision && loaded.status === 'active'
            && lastMessage?.role === 'assistant' && lastMessage.status === 'failed'
            && (!expectedTrace || lastMessage.references?.trace?.trace_id === expectedTrace)) {
            applyConversation(loaded)
          }
        } catch { /* The provider failure remains visible if evidence cannot be restored. */ }
      }
    } finally {
      setSending(false)
    }
  }

  const openControlChat = () => { setSelectedAgent(null); setAllowWorkspaceRead(false); setWorkspaceReadPaths(''); setCapabilityDraft(null); setCapabilityProposals([]); setError('') }
  const selectAgent = (agent: Agent) => { setSelectedAgent(agent); setAllowWorkspaceRead(false); setWorkspaceReadPaths(''); setCapabilityDraft(null); setCapabilityProposals([]); setError('') }
  const latestDirectoryScanPromptId = [...messages].reverse().find((message) => message.inlineDirectoryScan)?.id

  return (
    <section className="control-chat" aria-label={t('commerce.agent_and_application_chat')} onScrollCapture={revealScrollbarWhileScrolling}>
      {agentPanelTarget && createPortal(
        <details className="chat-agent-panel" ref={agentPanelRef}>
          <summary>{t('commerce.conversations_and_agents')} <span>{agentsState === 'ready' ? agents.length : '—'}</span></summary>
          <aside className="control-chat-sidebar" aria-label={t('commerce.orchestrator_conversations_and_agents')}>
            <section className="chat-sidebar-pane conversation-library" aria-label={t('commerce.conversation_library')}>
              {selectedAgent && <div className="conversation-library-heading"><strong>{t('commerce.chat_title_named',{name:selectedAgent.config.name})}</strong></div>}
              <TabStrip<LibraryMode> label={t('commerce.conversation_status')} value={libraryMode} onChange={setLibraryMode} items={[{ id: 'active', label: t('commerce.recent') }, { id: 'archived', label: t('commerce.archived') }, { id: 'deleted', label: t('commerce.trash') }]} />
              {loadingConversation && <p className="muted-state" role="status">{t('commerce.opening_conversation')}</p>}
              {libraryError && <p className="inline-error" role="alert">{errorMessage(libraryError)}</p>}
              {conversationList.length === 0 && !libraryError && <p className="muted-state">{t(libraryMode==='active'?'commerce.empty_library_active':libraryMode==='archived'?'commerce.empty_library_archived':'commerce.empty_library_deleted',{owner:selectedAgent?t('commerce.for_this_agent'):t('commerce.with_the_orchestrator')})}</p>}
              <div className="conversation-library-list">{conversationList.map((conversation) => <button
                key={conversation.id}
                type="button"
                className={`conversation-library-item ${activeConversation?.id === conversation.id ? 'selected' : ''}`}
                onClick={(event) => {
                  if (longPressTriggeredRef.current) { event.preventDefault(); longPressTriggeredRef.current = false; return }
                  setConversationContextMenu(null)
                  if (conversation.status === 'deleted') { setActiveConversation({ ...conversation, messages: [] }); setMessages([]) }
                  else void openConversation(conversation.id)
                }}
                onContextMenu={(event) => { event.preventDefault(); cancelConversationLongPress(); showConversationContextMenu(conversation, event.clientX, event.clientY) }}
                onPointerDown={(event) => {
                  if (event.pointerType !== 'touch') return
                  cancelConversationLongPress()
                  longPressTriggeredRef.current = false
                  const { clientX, clientY } = event
                  longPressTimerRef.current = window.setTimeout(() => {
                    longPressTriggeredRef.current = true
                    showConversationContextMenu(conversation, clientX, clientY)
                  }, 550)
                }}
                onPointerUp={cancelConversationLongPress}
                onPointerCancel={cancelConversationLongPress}
                onPointerLeave={cancelConversationLongPress}
                onKeyDown={(event) => {
                  if (event.key !== 'ContextMenu' && !(event.shiftKey && event.key === 'F10')) return
                  event.preventDefault()
                  const bounds = event.currentTarget.getBoundingClientRect()
                  showConversationContextMenu(conversation, bounds.left, bounds.bottom)
                }}
              ><strong>{conversation.title}</strong><span>{formatDate(conversation.updated_at)}</span></button>)}</div>
              <div className="conversation-library-footer"><button className="conversation-library-new" type="button" disabled={creatingConversation} onClick={() => void startConversation()}>{t('commerce.new')}</button>
                {libraryMode === 'deleted' && activeConversation?.status === 'deleted' && <button type="button" disabled={permanentlyDeleting} onClick={() => void permanentlyDeleteConversation()}>{permanentlyDeleting ? t('commerce.deleting') : t('commerce.permanently_delete')}</button>}
              </div>
              {conversationContextMenu && <div
                ref={contextMenuRef}
                className="conversation-context-menu"
                data-conversation-context-menu
                role="menu"
                aria-label={t('commerce.conversation_actions',{title:conversationContextMenu.conversation.title})}
                style={{ left: conversationContextMenu.x, top: conversationContextMenu.y }}
                onKeyDown={(event) => {
                  if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') return
                  event.preventDefault()
                  const items = Array.from(event.currentTarget.querySelectorAll<HTMLButtonElement>('button'))
                  const currentIndex = items.indexOf(document.activeElement as HTMLButtonElement)
                  const direction = event.key === 'ArrowDown' ? 1 : -1
                  items[(currentIndex + direction + items.length) % items.length]?.focus()
                }}
              >
                {conversationContextMenu.conversation.status !== 'deleted' && <button type="button" role="menuitem" onClick={() => { const { conversation } = conversationContextMenu; setConversationContextMenu(null); void manageConversation('rename', conversation) }}>{t('commerce.rename')}</button>}
                {conversationContextMenu.conversation.status === 'active' && <button type="button" role="menuitem" onClick={() => { const { conversation } = conversationContextMenu; setConversationContextMenu(null); void manageConversation('archive', conversation) }}>{t('commerce.archive')}</button>}
                {conversationContextMenu.conversation.status !== 'deleted' && <button type="button" role="menuitem" onClick={() => { const { conversation } = conversationContextMenu; setConversationContextMenu(null); void manageConversation('delete', conversation) }}>{t('commerce.move_to_trash')}</button>}
                {conversationContextMenu.conversation.status !== 'active' && <button type="button" role="menuitem" onClick={() => { const { conversation } = conversationContextMenu; setConversationContextMenu(null); void manageConversation('restore', conversation) }}>{t('commerce.restore')}</button>}
                {conversationContextMenu.conversation.status === 'deleted' && <button type="button" role="menuitem" disabled={permanentlyDeleting} onClick={() => { const { conversation } = conversationContextMenu; setConversationContextMenu(null); void permanentlyDeleteConversation(conversation) }}>{t('commerce.permanently_delete')}</button>}
              </div>}
            </section>
            <section className="chat-sidebar-pane chat-sidebar-agents" aria-labelledby="chat-agents-title">
              <div className="chat-sidebar-heading"><div><h2 id="chat-agents-title">{t('commerce.agents')}</h2></div>{onManageAgents && <button type="button" className="secondary-action" onClick={onManageAgents}>{t('commerce.manage_agents')}</button>}</div>
              <section className="conversation-agent-activity" aria-label={t('commerce.agents_participating_in_the_selected_conversation')}>
                <strong>{t('commerce.agents_in_this_chat')}</strong>
                <p>{!selectedAgent && activeConversation?.owner_kind === 'assistant'
                  ? t('commerce.no_agent_tasks_are_linked_to_this_conversation_yet')
                  : t('commerce.select_an_orchestrator_conversation_to_see_its_linked_agent_tasks')}</p>
              </section>
              <button type="button" className={`control-agent-option ${selectedAgent === null ? 'selected' : ''}`} onClick={openControlChat}><strong>{t('commerce.app_assistant')}</strong></button>
              <div className="agent-list-label"><span>{t('commerce.available_agents')}</span><span>{agentsState === 'ready' ? agents.length : '—'}</span></div>
              {agentsState === 'loading' && <p className="muted-state" role="status">{t('commerce.loading_agents')}</p>}
              {agentsState === 'error' && <p className="inline-error">{t('commerce.agent_inventory_unavailable')}</p>}
              {agentsState === 'ready' && agents.length === 0 && <p className="muted-state">{t('commerce.no_agents_created_yet_ask_the_app_assistant_to_create_one')}</p>}
              <div className="control-agent-list">{agents.map((agent) => <button key={agent.id} type="button" className={`control-agent-option ${selectedAgent?.id === agent.id ? 'selected' : ''}`} onClick={() => selectAgent(agent)}><strong>{agent.config.name}</strong><span>{{rag:t('commerce.agent_rag'),tool:t('commerce.agent_tool'),'multi-agent':t('commerce.agent_multi')}[agent.config.type]??t('commerce.unrecognized_state')} · {agent.config.model_id || t('commerce.no_model_assigned')}</span><span>{agent.config.description}</span></button>)}</div>
              {inventoryWarning && <p className="warning-state" role="status">{errorMessage(inventoryWarning)}</p>}
            </section>
          </aside>
        </details>,
        agentPanelTarget,
      )}
      <WindowPanel
        title={selectedAgent?.config.name ?? activeConversation?.title ?? t('commerce.how_can_i_help')}
        className="control-chat-main control-chat-window"
        hideTitlebar
      >
        <div className="chat-mode-header">
          <ChatTools conversationId={activeConversation?.id} onOpenCommunication={onOpenCommunication} />
          <button type="button" onClick={onOpenCognitionSettings} aria-label={t('commerce.open_cognition_and_context_settings')}>{t('commerce.cognition')} {cognitiveMode === 'bago5' ? t('commerce.bago5_experimental') : t('commerce.baseline')} <span aria-hidden="true">↗</span></button>
        </div>
        <div className="control-chat-messages" aria-live="polite">
          {messages.length === 0 && <div className="chat-welcome"><div className="welcome-mark" aria-hidden="true">✳</div><h3>{selectedAgent ? t('commerce.chat_with',{name:selectedAgent.config.name}) : t('commerce.your_workspace_through_chat')}</h3>{!selectedAgent && <div className="prompt-suggestions"><button type="button" onClick={() => setInput('Lista mis agentes')}>{t('commerce.list_my_agents')}</button><button type="button" onClick={() => setInput('Quiero crear un agente para…')}>{t('commerce.create_an_agent')}</button><button type="button" onClick={() => setInput('Abre el Decision Inspector')}>{t('commerce.open_the_inspector')}</button></div>}</div>}
          {messages.map((message) => <article key={message.id} className={`control-message control-message-${message.role}`} tabIndex={0} aria-labelledby={`message-author-${message.id}`} onContextMenu={event => {
            if ((event.target as HTMLElement).closest('input,textarea,[contenteditable="true"]') || !message.content) return
            event.preventDefault(); openMessageMenu(message, event.currentTarget, event.clientX, event.clientY)
          }} onKeyDown={event => {
            if (event.key !== 'ContextMenu' && !(event.key === 'F10' && event.shiftKey)) return
            if ((event.target as HTMLElement).closest('input,textarea,[contenteditable="true"]') || !message.content) return
            event.preventDefault(); const rect = event.currentTarget.getBoundingClientRect()
            openMessageMenu(message, event.currentTarget, rect.left + 16, rect.top + 36)
          }}><div className="control-message-heading"><span id={`message-author-${message.id}`} className="message-speaker">{message.role === 'user' ? t('commerce.you') : selectedAgent?.config.name ?? t('commerce.assistant')}</span>{message.content && <div className="control-message-actions"><button type="button" className="message-action" onClick={() => void copyMessage(message)}>{messageCopyState?.id === message.id ? messageCopyState.state === 'copied' ? t('commerce.copied') : t('commerce.copy_failed') : message.role === 'user' ? t('commerce.copy_message') : t('commerce.copy_response')}</button>{canEditMessage(message) && <button type="button" className="message-action" onClick={() => editLatestMessage(message)} disabled={messageEditDisabled}>{t('commerce.edit')}</button>}</div>}</div>{message.status === 'failed' && <p role="status">{t('commerce.failed_response_no_response_was_received_from_the_provider')}</p>}{message.content && <div className="control-message-content">{message.role === 'assistant' ? <AssistantMarkdown content={message.uiContent?errorMessage(message.uiContent):message.content} /> : message.content}</div>}{(message.communicationDraftId || message.communicationDraft) && <Communications key={`communication-${message.id}`} inline initialDraft={message.communicationDraft} draftId={message.communicationDraftId} conversationId={activeConversation?.id} onOpenFull={onOpenCommunication} />}{message.agentBuilderDraft && <AgentBuilder key={message.id} inline initialAgent={message.agentBuilderDraft} onAgentCreated={() => void refreshAgents()} />}{message.inlineJobHistory && <JobHistory key={message.id} inline />}{message.workspaceProposal && <WorkspaceManager inline proposal={message.workspaceProposal} />}{message.workspaceWriteProposalError&&<p role="alert">{errorMessage(message.workspaceWriteProposalError)}</p>}{message.workspaceWriteProposal&&activeConversation&&<WorkspaceWriteReview proposal={message.workspaceWriteProposal} ownerKind={ownerKind} ownerId={ownerId} conversationId={activeConversation.id} conversationRevision={activeConversation.revision} />}{message.inlineDirectoryScan && message.id === latestDirectoryScanPromptId && !selectedAgent && activeConversation?.owner_kind === 'assistant' && <DirectoryScanRun key={`scan-form-${message.id}`} conversationId={activeConversation.id} revision={activeConversation.revision} disabled={activeConversation.status !== 'active'} showForm onConversationUpdate={(conversation) => applyConversation(conversation as StoredConversation)} />}{message.scanOutcome && activeConversation?.owner_kind === 'assistant' && <DirectoryScanRun key={`scan-results-${message.id}`} conversationId={activeConversation.id} revision={activeConversation.revision} showForm={false} initialOutcome={message.scanOutcome} onConversationUpdate={(conversation) => applyConversation(conversation as StoredConversation)} />}{message.scanOutcome && activeConversation && onInspectExecution && <button type="button" onClick={() => onInspectExecution({conversationId:activeConversation.id,revision:activeConversation.revision,traceId:message.scanOutcome!.trace.trace_id})}>{t('commerce.inspect_scan_execution')}</button>}{message.pendingNavigation && <section className="chat-navigation-confirmation" aria-label={t('commerce.confirm_screen_change')}><p>{t('commerce.switch_screen',{view:viewLabels[message.pendingNavigation]})}</p>{message.navigationDecision === 'accepted' ? <span role="status">{t('commerce.switching_screen')}</span> : message.navigationDecision === 'declined' ? <span role="status">{t('commerce.staying_in_chat')}</span> : <div className="draft-actions"><button type="button" className="secondary-action" onClick={() => setMessages((previous) => previous.map((item) => item.id === message.id ? { ...item, navigationDecision: 'declined' } : item))}>{t('commerce.stay_in_chat')}</button><button type="button" className="primary-action" onClick={() => { setMessages((previous) => previous.map((item) => item.id === message.id ? { ...item, navigationDecision: 'accepted' } : item)); onNavigate(message.pendingNavigation as ExistingView) }}>{t('commerce.yes_switch_screen')}</button></div>}</section>}{message.cognitiveTrace && <details><summary>{t('commerce.response_context')}</summary><CognitiveContextPanel trace={message.cognitiveTrace} /></details>}{message.sources?.some(source => source.source_type !== 'public_web') ? <details className="message-sources" aria-label={t('commerce.project_files_read')}><summary>{t('commerce.files_count',{count:formatNumber(message.sources.filter(source => source.source_type !== 'public_web').length)})}</summary><ul>{message.sources.filter(source => source.source_type !== 'public_web').map(source => <li key={`${source.path}:${source.start_line}-${source.end_line}`}><code>{source.path}:{source.start_line}-{source.end_line}</code>{source.content_sha256 && <small> SHA-256 {source.content_sha256}</small>}</li>)}</ul></details> : null}{message.sources?.some(source => source.source_type === 'public_web') ? <details className="message-sources" aria-label={t('commerce.public_web_sources_read')}><summary>{t('commerce.web_count',{count:formatNumber(message.sources.filter(source => source.source_type === 'public_web').length)})}</summary><ul>{message.sources.filter(source => source.source_type === 'public_web').map(source => <li key={`${source.snapshot_id ?? source.path}:${source.start_line}-${source.end_line}`}><code>{source.path}:{source.start_line}-{source.end_line}</code>{safePublicLink(source.final_url ?? source.path) ? <a href={safePublicLink(source.final_url ?? source.path)} target="_blank" rel="noreferrer">{t('commerce.open_public_url')}</a> : <span>{t('commerce.url_cannot_be_opened')}</span>}<small>{t('commerce.captured_utc')} {source.captured_at ?? t('commerce.not_recorded')} {t('commerce.text_sha_256')} {source.text_sha256 ?? source.content_sha256 ?? t('commerce.not_recorded_124')} {t('commerce.raw_hash')} {source.raw_sha256 ?? t('commerce.not_recorded_124')}</small>{source.requested_url && <small>{t('commerce.requested')} {source.requested_url}</small>}{source.snapshot_id && <code>{t('commerce.snapshot_label')} {source.snapshot_id}</code>}{source.snapshot_manifest_sha256 && <code>{t('commerce.manifest_sha_256')} {source.snapshot_manifest_sha256}</code>}</li>)}</ul></details> : null}{message.readEvents?.length ? <details className="message-sources" aria-label={t('commerce.read_only_analysis_evidence')}><summary>{t('commerce.reads')} {message.readEvents.some(event => event.decision !== 'ALLOW') ? message.readEvents.filter(event => event.decision !== 'ALLOW').map(event => `${humanState(event.decision)}${event.reason_code ? `: ${event.reason_code}` : ''}`).join(' · ') : t('commerce.no_issues_recorded')}</summary><ul>{message.readEvents.map((event, index) => <li key={`${event.path}:${index}`}><code>{event.decision} {event.path || t('commerce.unresolved_path')} {event.reason_code ? `· ${event.reason_code}` : ''}</code>{event.kind === 'public_web_read' && <small> {t('commerce.public_web_read')} {event.decision}</small>}{event.kind === 'directory_code_scan' && <small>{t('commerce.scan_counts',{files:formatNumber(event.files_scanned??0),lines:formatNumber(event.lines_scanned??0),findings:formatNumber(event.finding_count??0),capped:event.truncated?t('commerce.capped'):'',hash:event.manifest_sha256??t('commerce.unavailable')})}</small>}</li>)}</ul></details> : null}{message.trace && <div className="message-trace" aria-label={t('commerce.execution_trace_evidence')}>{activeConversation && onInspectExecution && <button type="button" onClick={() => onInspectExecution({conversationId:activeConversation.id,revision:activeConversation.revision,traceId:message.trace!.localId})}>{t('commerce.inspect_execution')}</button>}<details><summary>{t('commerce.trace_details')} {humanState(message.trace.state)}</summary><code>Local: {message.trace.localId}</code>{message.trace.jaegerId && <code>Jaeger: {message.trace.jaegerId}</code>}{message.trace.jaegerUrl && <a href={message.trace.jaegerUrl} target="_blank" rel="noreferrer">{t('commerce.open_in_jaeger')}</a>}</details></div>}</article>)}
          {capabilityDraft && <section className="capability-chat-card" aria-labelledby="capability-draft-title"><div className="draft-heading"><div><p className="section-eyebrow">{t('commerce.proposal_review')}</p><h3 id="capability-draft-title">{t('commerce.review_before_saving')}</h3></div><span className="draft-status">{t('commerce.not_saved')}</span></div><label>{t('commerce.capability')}<select value={capabilityDraft.capabilityId} onChange={(event) => setCapabilityDraft({ ...capabilityDraft, capabilityId: event.target.value })} disabled={capabilityBusy}><option value="">{t('commerce.choose_a_catalog_entry')}</option>{capabilityDraft.capabilities.map((item) => <option key={item.id} value={item.id}>{item.id} · {item.status} · {item.effect}</option>)}</select></label>{capabilityDraft.capabilityId && <p className="capability-chat-selected">{capabilityDraft.capabilities.find((item) => item.id === capabilityDraft.capabilityId)?.summary}</p>}<label>{t('commerce.request_summary')}<input value={capabilityDraft.summary} maxLength={500} onChange={(event) => setCapabilityDraft({ ...capabilityDraft, summary: event.target.value })} disabled={capabilityBusy} /></label><label>{t('commerce.requested_scope')}<textarea value={capabilityDraft.requestedScope} maxLength={1000} rows={3} onChange={(event) => setCapabilityDraft({ ...capabilityDraft, requestedScope: event.target.value })} disabled={capabilityBusy} /></label><div className="draft-actions"><button type="button" className="secondary-action" onClick={() => setCapabilityDraft(null)} disabled={capabilityBusy}>{t('commerce.discard')}</button><button type="button" className="primary-action" onClick={() => void saveCapabilityProposal()} disabled={capabilityBusy || !capabilityDraft.capabilityId || !capabilityDraft.summary.trim() || !capabilityDraft.requestedScope.trim()}>{capabilityBusy ? t('commerce.saving') : t('commerce.save_proposal')}</button></div></section>}
          {capabilityProposals.map((proposal) => <article className="capability-chat-saved" key={proposal.id}><div><strong>{proposal.capability_id}</strong><span>{humanState(proposal.status)} {t('commerce.revision')} {proposal.revision}</span></div><p>{proposal.summary}</p><p><strong>{t('commerce.requested_scope_148')}</strong> {proposal.requested_scope}</p><code>{proposal.id}</code>{proposal.status === 'PENDING_REVIEW' && <button type="button" className="secondary-action" onClick={() => void cancelChatProposal(proposal)} disabled={capabilityBusy}>{t('commerce.cancel_proposal')}</button>}</article>)}
          {error && <p className="chat-error" role="alert">{errorMessage(error)}{errorMessage(error).toLowerCase().includes('ollama') || errorMessage(error).toLowerCase().includes('provider') ? <button type="button" onClick={onOpenProviderSettings}>{t('commerce.open_provider_settings')}</button> : null}</p>}
          {sending && <p className="muted-state" role="status">{t('commerce.waiting_for_the_provider_response')}</p>}
          <div ref={messagesEndRef} />
        </div>
        <form className="control-chat-composer" onSubmit={(event) => void sendMessage(event)}><label className="visually-hidden" htmlFor="control-chat-input">{t('commerce.message_the_assistant_or_selected_agent')}</label><div className="chat-composer-input"><textarea ref={composerRef} id="control-chat-input" rows={2} value={input} onChange={(event) => setInput(event.target.value)} onKeyDown={(event) => {
          if (event.key !== 'Enter' || event.shiftKey || event.nativeEvent.isComposing || event.repeat) return
          event.preventDefault()
          void sendMessage()
        }} placeholder={activeConversation?.status && activeConversation.status !== 'active' ? t('commerce.restore_or_start_a_new_conversation') : selectedAgent ? t('commerce.message_agent',{name:selectedAgent.config.name}) : t('commerce.message_the_assistant')} disabled={sending || Boolean(activeConversation && activeConversation.status !== 'active')} />
            <button className="primary-action" type="submit" disabled={sending || !input.trim() || Boolean(activeConversation && activeConversation.status !== 'active')}>{sending ? 'Sending.' : t('commerce.send')}</button>
          </div>
          <div className="chat-composer-actions">
            {selectedAgent&&<label className="workspace-read-toggle"><input type="checkbox" checked={allowWorkspaceWriteProposals} onChange={event=>setAllowWorkspaceWriteProposals(event.target.checked)} disabled={sending||Boolean(activeConversation&&activeConversation.status!=='active')}/><span>{t('commerce.propose_files')}</span></label>}
            <label className="workspace-read-toggle"><input type="checkbox" checked={allowPublicWebRead} onChange={event => setAllowPublicWebRead(event.target.checked)} disabled={sending || Boolean(activeConversation && activeConversation.status !== 'active')} /><span>{t('commerce.allow_public_web_reading')}</span></label>
            <label className="workspace-read-toggle"><input type="checkbox" checked={allowWorkspaceRead} onChange={(event) => setAllowWorkspaceRead(event.target.checked)} disabled={sending || Boolean(activeConversation && activeConversation.status !== 'active')} /><span>{t('commerce.allow_project_file_reads')}</span></label>
            {!selectedAgent && <label className="chat-provider-picker"><span className="visually-hidden">{t('commerce.orchestrator_model')}</span><select aria-label={t('commerce.orchestrator_model')} value={chatProviderSelection ? `${chatProviderSelection.provider_id}|${chatProviderSelection.model_id}` : ''} onChange={event => void changeChatProvider(event.target.value)} disabled={savingChatProvider || chatProviders.length === 0}><option value="" disabled>{chatProviders.length ? t('commerce.select_a_model') : t('commerce.configure_a_provider')}</option>{chatProviders.map(provider => <option key={`${provider.provider_id}|${provider.model_id}`} value={`${provider.provider_id}|${provider.model_id}`}>{provider.label} · {provider.display_name ?? provider.model_id}{provider.state === 'configured_unverified' ? t('commerce.unverified') : ''}</option>)}</select></label>}
          </div>
          {allowPublicWebRead && <section aria-label={t('commerce.public_web_reading_scope')}><label className="workspace-read-paths">{t('commerce.entry_https_urls_one_per_line')}<textarea rows={3} value={publicWebUrls} onChange={event => setPublicWebUrls(event.target.value)} placeholder="https://www.ejemplo.com/" maxLength={16384} disabled={sending} /></label><p>{t('commerce.this_turn_only_public_pages_from_these_origins')}</p><ul aria-label={t('commerce.requested_web_origins')}>{[...new Set(publicWebUrls.split(/\r?\n/).map(value => {try {return new URL(value.trim()).origin} catch {return value.trim() ? t('commerce.invalid_url',{url:value.trim()}) : ''}}).filter(Boolean))].map(origin => <li key={origin}><code>{origin}</code></li>)}</ul></section>}
          {allowWorkspaceRead && <label className="workspace-read-paths">{t('commerce.project_relative_paths')}<textarea rows={3} value={workspaceReadPaths} onChange={(event) => setWorkspaceReadPaths(event.target.value)} placeholder={'src/api/server.py\nsrc/agent_tools/workspace_read.py'} disabled={sending} /></label>}
        </form>
        <div className="chat-agent-panel-slot" ref={setAgentPanelTarget} />
      </WindowPanel>
      {menuMessage && messageContextMenu && createPortal(<div ref={messageMenuRef} className="chat-message-context-menu" role="menu" aria-labelledby={`message-author-${menuMessage.id}`} style={{ left: messageContextMenu.x, top: messageContextMenu.y }} onKeyDown={event => {
        if (event.key === 'Tab') { closeMessageMenu(true); return }
        const buttons = Array.from(event.currentTarget.querySelectorAll<HTMLButtonElement>('button:not(:disabled)'))
        if (!['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key) || !buttons.length) return
        event.preventDefault()
        const current = buttons.indexOf(document.activeElement as HTMLButtonElement)
        const next = event.key === 'Home' ? 0 : event.key === 'End' ? buttons.length - 1
          : (current + (event.key === 'ArrowUp' ? -1 : 1) + buttons.length) % buttons.length
        buttons[next].focus()
      }}>
        <div className="chat-message-context-author" aria-hidden="true">{menuMessage.role === 'user' ? t('commerce.you') : selectedAgent?.config.name ?? t('commerce.assistant')}</div>
        <button type="button" role="menuitem" tabIndex={-1} onClick={() => { void copyMessage(menuMessage); closeMessageMenu(true) }}>{menuMessage.role === 'user' ? t('commerce.copy_message') : t('commerce.copy_response')}</button>
        {canEditMessage(menuMessage) && <button type="button" role="menuitem" tabIndex={-1} disabled={messageEditDisabled} onClick={() => { closeMessageMenu(); editLatestMessage(menuMessage) }}>{t('commerce.edit')}</button>}
      </div>, document.body)}
    </section>
  )
}
