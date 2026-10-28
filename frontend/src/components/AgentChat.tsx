import {t, useI18n, getLocale, formatDate, formatNumber, apiError, errorMessage, localMessage} from '../i18n'
import {PROVIDER_RESPONSE_OBSERVED_EVENT, readProviderResponseObservation} from '../contracts/provider-response-observation'
import './AgentChat.css'
import './AgentChatOverrides.css'
import './ChatMessage.css'
import './WindowsSurface.css'
import type {InspectionSelection} from '../types/inspection'
import { FormEvent, useCallback, useEffect, useId, useLayoutEffect, useMemo, useRef, useState, type KeyboardEvent as ReactKeyboardEvent, type MouseEvent as ReactMouseEvent, type PointerEvent as ReactPointerEvent } from 'react'
import type { UIEvent } from 'react'
import { createPortal } from 'react-dom'
import { Capability, CapabilityProposal, capabilityResponseError } from './CapabilityManager'
import AgentBuilder from './AgentBuilder'
import DevelopmentPanel from './DevelopmentPanel'
import ProjectPermissions from './ProjectPermissions'
import HumanCorrectionReview, {type HumanCorrectionSource, type PreparedHumanCorrection} from './HumanCorrectionReview'
import AgentServiceReview,{type FilesystemProposal} from './AgentServiceReview'
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
import AgentDelegation, { type AgentDelegationProposal } from './AgentDelegation'

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

type WorkspaceSource = { source_type?: 'public_web' | 'document'; locations?:Array<Record<string,unknown>>; requested_url?: string; final_url?: string; captured_at?: string; raw_sha256?: string; text_sha256?: string; snapshot_id?: string; snapshot_manifest_sha256?: string; path: string; start_line: number; end_line: number; file_sha256?: string; content_sha256?: string }
type WorkspaceReadEvent = { filesystem_proposal?:FilesystemProposal; delivery_review?:{review_id:string;decision:string;errors:string[];missing:string[];pending:string[];send_executed:boolean}; production?:{work_id:string}; tool_name?:string; receipt_id?:string; executed?:boolean; outcome?:string; next_cursor?:string|null; corpus_coverage?:{total:number;offset:number;batch_selected:number;complete:boolean}; output?:{download_url?:string;sha256?:string;path?:string}; decision: 'ALLOW' | 'DENY' | 'FAIL'; kind?: string; path: string | null; reason_code?: string; file_sha256?: string; content_sha256?: string; files_scanned?: number; files_skipped?: number; bytes_scanned?: number; lines_scanned?: number; finding_count?: number; truncated?: boolean; manifest_sha256?: string }
type CognitiveTrace = { mode: 'baseline' | 'bago5'; enabled: boolean; profile?: string | null; method?: string; focus: Array<{ id: string; kind: string; label: string; score: number }>; capacity?: number; max_hops?: number; trace_id?: string; trace_state?: string }
type Message = { uiContent?:Error; workspaceWriteProposal?:WriteProposalSummary; workspaceWriteProposalError?:string; status?: string; workspaceProposal?: WorkspaceProposal; communicationDraft?: CommunicationDraft; communicationDraftId?: string; agentDelegation?: AgentDelegationProposal; id: string; role: 'user' | 'assistant'; content: string; trace?: MessageTrace; cognitiveTrace?: CognitiveTrace; sources?: WorkspaceSource[]; readEvents?: WorkspaceReadEvent[]; agentBuilderDraft?: AgentConfig; inlineJobHistory?: boolean; inlineDirectoryScan?: boolean; scanOutcome?: ScanOutcome; pendingNavigation?: ExistingView; navigationDecision?: 'accepted' | 'declined' }
type ConversationSummary = { id: string; owner_kind: 'assistant' | 'agent'; owner_id: string; title: string; status: 'active' | 'archived' | 'deleted'; labels?: string[]; created_at?: string; updated_at: string; revision: number }
type StoredConversation = ConversationSummary & { messages: Array<{ id: string; role: 'user' | 'assistant'; content: string; status?: string; references?: { agent_delegation?: AgentDelegationProposal; workspace_write_proposal?:unknown; workspace_proposal?: WorkspaceProposal; communication_draft_id?: string; communication_draft?: CommunicationDraft; trace?: { trace_id?: string; trace_state?: string; jaeger_trace_id?: string; jaeger_url?: string } & Partial<ScanTrace>; cognitive_trace?: CognitiveTrace; sources?: WorkspaceSource[]; read_events?: Array<WorkspaceReadEvent & Partial<ScanReceipt>>; scan_result?: ScanReport; control_capability?: string } }> }
type LibraryMode = 'active' | 'archived' | 'deleted'
type ConversationSortKey = 'labels' | 'title' | 'created_at' | 'updated_at'
type ConversationSort = { key: ConversationSortKey; direction: 'asc' | 'desc' }
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

export type PreparedChatPrompt = {id:string; text:string; capabilityId?:'workspace.scan_duplicates'}

interface AgentChatProps {
  hidden?: boolean
  preparedPrompt?: PreparedChatPrompt|null
  onPreparedPromptHandled?: (id:string)=>void
  /** Explicit selection is the product policy; latest retains reusable embedding compatibility. */
  historySelection?: 'latest' | 'explicit'
  /** Changes when the bound project folder changes; history is reloaded in its own scope. */
  workspaceScopeVersion?: number
  onInspectionSelection?: (selection: InspectionSelection|null) => void
  onInspectExecution?: (selection: InspectionSelection) => void
  onNavigate: (view: ExistingView) => void
  onManageAgents?: () => void
  onOpenCommunication?: (id: string) => void
  onOpenProviderSettings: () => void
  onOpenCognitionSettings: () => void
  cognitiveMode: 'baseline' | 'bago5'
}

// A dated activity requires a complete source timestamp with an explicit zone.
function conversationActivity(value: unknown): number {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/.test(value)) return NaN
  return Date.parse(value)
}

export type HumanCorrectionContext = {
  ownerKind: HumanCorrectionSource['ownerKind']; ownerId: string
  conversation: Pick<StoredConversation,'id'|'revision'|'status'|'owner_kind'|'owner_id'>|null
  messages: Array<Pick<Message,'id'|'role'|'content'|'uiContent'>>
}
export function isHumanCorrectionSourceCurrent(source: HumanCorrectionSource, context: HumanCorrectionContext): boolean {
  const original=context.messages.find(message=>message.id===source.messageId&&message.role==='assistant')
  return context.ownerKind===source.ownerKind && context.ownerId===source.ownerId
    && context.conversation?.owner_kind===context.ownerKind && context.conversation.owner_id===context.ownerId
    && context.conversation.id===source.conversationId && context.conversation.revision===source.revision
    && context.conversation.status==='active' && Boolean(original && (original.uiContent?errorMessage(original.uiContent):original.content)===source.content)
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
  // Local shortcuts consume the whole message. Mentions inside a mission,
  // quoted commands and negations belong to the ordinary model route.
  // Normalize only this matching copy; sendMessage retains the user's text.
  const text = message.trim().toLocaleLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    .replace(/^[¿¡]\s*/, '').replace(/[?!.]+$/, '').trim().replace(/\s+/g, ' ')
  const capabilityId = '(?:workspace\\.read_text|mcp\\.execute|sandbox\\.execute|agent\\.run)'
  const proposalCommand = /^(?:(?:quiero )?proponer(?: una)? capacidad|propuesta de capacidad|propose(?: a)? capability|capability proposal)$/
  const targetedProposal = new RegExp(`^(?:(?:quiero )?proponer(?: una)? capacidad|propuesta de capacidad|propose(?: a)? capability|capability proposal) ${capabilityId}$`)
  const accessProposal = new RegExp(`^(?:proponer acceso a|propuesta de acceso a|propose access to|proposal for access to) ${capabilityId}$`)
  if (proposalCommand.test(text) || targetedProposal.test(text) || accessProposal.test(text)) return { operation: 'propose_capability' }
  const capabilityList = /^(?:(?:lista|listar|muestra|mostrar|consulta|consultar|describe|describir)(?: las| mis)? capacidades|(?:consulta|consultar|muestra|mostrar)(?: el)? catalogo de capacidades|(?:que|cuales)(?: son)?(?: las| mis)? capacidades(?: hay| tengo| estan disponibles)?|(?:list|show|describe)(?: the| my)? (?:capabilities|capability catalog)|(?:which|what) capabilities(?: are available| do i have)?|(?:estado de las capacidades|status of capabilities|capability status))$/
  const capabilityStatus = new RegExp(`^(?:(?:estado de|status of|lista|listar|list|describe|describir|muestra|mostrar|show|que es|what is) ${capabilityId}|${capabilityId} (?:estado|status))$`)
  if (capabilityList.test(text) || capabilityStatus.test(text)) return { operation: 'list_capabilities' }
  if (/^(?:hola|buenas|hello|hi|hey|que puedes hacer|what can you do|capacidades del asistente|assistant capabilities|puedes (?:crear|disenar)(?: un)? agentes?|(?:can you|could you) (?:create|design)(?: an?)? agents?)$/.test(text)) {
    return { operation: cognitiveMode === 'bago5' ? 'chat' : 'help' }
  }
  if (/^(?:(?:lista|listar|muestra|mostrar|consulta|consultar)(?: mis| los)? agentes|(?:que|cuales)(?: son)?(?: mis| los)? agentes(?: hay| tengo)?|(?:list|show)(?: my| the)? agents|(?:which|what) agents(?: do i have| are available)?)$/.test(text)) {
    return { operation: 'list_agents' }
  }
  return { operation: 'chat' }
}

export default function AgentChat({ onInspectionSelection, onInspectExecution, onNavigate, onManageAgents, onOpenCommunication, onOpenProviderSettings, onOpenCognitionSettings, cognitiveMode, historySelection = 'latest', workspaceScopeVersion = 0, hidden = false, preparedPrompt, onPreparedPromptHandled }: AgentChatProps) {
  useI18n()
  const english = getLocale() === 'en'
  const [reviewContext,setReviewContext]=useState<{runs:Array<{work_id:string;owner_id:string;producer_name?:string;conversation_id:string;source_root:string;candidate_id:string;scope_sha256:string;artifacts:Array<{path:string;sha256:string}>;business_acceptance:string}>;contacts:Array<{id:string;name:string;phone:string}>}>({runs:[],contacts:[]})
  const [reviewWork,setReviewWork]=useState(''),[reviewContact,setReviewContact]=useState(''),[draftConsent,setDraftConsent]=useState(false),[reviewContextError,setReviewContextError]=useState(false)
  const [documentRoot, setDocumentRoot] = useState('')
  const [documentConsent, setDocumentConsent] = useState(false)
  const [documentOutputConsent, setDocumentOutputConsent] = useState(false)
  const [documentOutputDirectory, setDocumentOutputDirectory] = useState('')
  const [documentFolders, setDocumentFolders] = useState<{roots:Array<{path:string;name:string}>;path?:string;parent?:string|null;directories:Array<{path:string;name:string}>}|null>(null)
  const [documentBrowseError, setDocumentBrowseError] = useState('')
  const [documentBrowseBusy, setDocumentBrowseBusy] = useState(false)
  const browseRequest = useRef(0)
  async function browseDocuments(path?:string) {
    const requestId = ++browseRequest.current
    setDocumentBrowseBusy(true);setDocumentBrowseError('')
    try {
      const response = await fetch('/api/document-tools/folders'+(path?'?path='+encodeURIComponent(path):''))
      if (!response.ok) throw new Error('folder_unavailable')
      const result = await response.json()
      if (!Array.isArray(result.roots) || !Array.isArray(result.directories)) throw new Error('folder_invalid')
      if (requestId === browseRequest.current) {setDocumentFolders(result);setDocumentOutputDirectory(result.output_directory || '')}
    } catch {
      if (requestId === browseRequest.current) setDocumentBrowseError(t('agentTools.folderUnavailable'))
    } finally {if (requestId === browseRequest.current) setDocumentBrowseBusy(false)}
  }

  const [agents, setAgents] = useState<Agent[]>([])
  const [agentsState, setAgentsState] = useState<'loading' | 'ready' | 'error'>('loading')
  const [inventoryWarning, setInventoryWarning] = useState<string|Error>('')
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [activeConversation, setActiveConversation] = useState<StoredConversation | null>(null)
  const [conversationList, setConversationList] = useState<ConversationSummary[]>([])
  const [conversationContextMenu, setConversationContextMenu] = useState<{ conversation: ConversationSummary; x: number; y: number } | null>(null)
  const conversationActionTriggerRef = useRef<HTMLButtonElement | null>(null)
  const [libraryMode, setLibraryMode] = useState<LibraryMode>('active')
  const [conversationSort, setConversationSort] = useState<ConversationSort>({key: 'updated_at', direction: 'desc'})
  const [agentPanelOpen, setAgentPanelOpen] = useState(false)
  const agentPanelContentId = useId()
  const [libraryError, setLibraryError] = useState<string|Error>('')
  const [permanentlyDeleting, setPermanentlyDeleting] = useState(false)
  const [activeProject, setActiveProject] = useState<{project_id:string|null;title:string;scope:string;root:string|null}|null>(null)
  const [developmentPanelTarget, setDevelopmentPanelTarget] = useState<HTMLDivElement | null>(null)
  const [projectPanelExpanded, setProjectPanelExpanded] = useState(false)
  const [loadingConversation, setLoadingConversation] = useState(false)
  const [creatingConversation, setCreatingConversation] = useState(false)
  const creatingConversationRef = useRef(false)
  const agentPanelRef = useRef<HTMLDetailsElement>(null)
  // Route identity belongs to one exact, untouched catalog draft, not its wording.
  const preparedCapabilityRef=useRef<{id:'workspace.scan_duplicates';text:string}|null>(null)
  const [input, setInputState] = useState('')
  const setInput=useCallback((value:string|((previous:string)=>string))=>{preparedCapabilityRef.current=null;setInputState(value)},[])
  const [humanCorrection, setHumanCorrection] = useState<{source: HumanCorrectionSource; origin: HTMLElement}|null>(null)
  const correctionReturnFocus = useRef<HTMLElement|null>(null)
  useEffect(()=>{if(!humanCorrection && correctionReturnFocus.current){const origin=correctionReturnFocus.current;correctionReturnFocus.current=null;if(origin.isConnected)origin.focus();else composerRef.current?.focus()}},[humanCorrection])
  const [messageCopyState, setMessageCopyState] = useState<{ id: string; state: 'copied' | 'failed' } | null>(null)
  const [messageContextMenu, setMessageContextMenu] = useState<{ id: string; agentId: string | null; latestUserId: string | undefined; conversationId: string | null; revision: number | null; x: number; y: number; origin: HTMLElement } | null>(null)
  useEffect(()=>{if(hidden){setMessageContextMenu(null);setConversationContextMenu(null)}},[hidden])
  const messageMenuRef = useRef<HTMLDivElement>(null)
  const [allowPublicWebRead, setAllowPublicWebRead] = useState(false)
  const [publicWebUrls, setPublicWebUrls] = useState('')
  async function loadReviewContext(signal?:AbortSignal){
    if(!selectedAgent?.config.tools?.some(tool=>tool.startsWith('delivery_')))return
    try{
      const response=await fetch('/api/agent-tools/context?owner_id='+encodeURIComponent(selectedAgent.id),{signal})
      if(!response.ok)throw new Error('context_unavailable')
      const value=await response.json()
      if(!Array.isArray(value.runs)||!Array.isArray(value.contacts))throw new Error('context_invalid')
      if(!signal?.aborted){setReviewContext(value);setReviewContextError(false)}
    }catch{if(!signal?.aborted)setReviewContextError(true)}
  }
  useEffect(()=>{
    const controller=new AbortController()
    setReviewContext({runs:[],contacts:[]});setReviewWork('');setReviewContact('');setDraftConsent(false)
    void loadReviewContext(controller.signal)
    return()=>controller.abort()
  },[selectedAgent?.id])
  useEffect(() => {
    ++browseRequest.current
    setDocumentConsent(false);setDocumentOutputConsent(false);setDocumentRoot('');setDocumentFolders(null);setDocumentBrowseBusy(false);setDocumentOutputDirectory('')
  }, [selectedAgent?.id])
  const [sending, setSending] = useState(false)
  const [error, setError] = useState<string|Error>('')
  const [chatProviders, setChatProviders] = useState<ChatProvider[]>([])
  const [chatProviderSelection, setChatProviderSelection] = useState<ChatProviderSelection | null>(null)
  const [savingChatProvider, setSavingChatProvider] = useState(false)
  const [chatProviderSelectionFailed, setChatProviderSelectionFailed] = useState(false)
  // Synchronous guard: a same-tick submit must not outrun React's disabled render.
  const chatProviderMutation = useRef({generation:0,pending:false,failed:false})
  const chatDispatchPending = useRef(false)
  const orchestratorSelectionBlocked = !selectedAgent && (savingChatProvider || chatProviderSelectionFailed)
  const [capabilityDraft, setCapabilityDraft] = useState<CapabilityDraft | null>(null)
  const [capabilityProposals, setCapabilityProposals] = useState<CapabilityProposal[]>([])
  const [capabilityBusy, setCapabilityBusy] = useState(false)
  const [agentPanelTarget, setAgentPanelTarget] = useState<HTMLDivElement | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const messagesContainerRef = useRef<HTMLDivElement>(null)
  const conversationScrollTimerRef = useRef<number | null>(null)
  const [showConversationScrollControls, setShowConversationScrollControls] = useState(false)
  const composerRef = useRef<HTMLTextAreaElement>(null)
  const handledPreparedPrompt=useRef<string|null>(null)
  const [preparedPromptReview,setPreparedPromptReview]=useState<PreparedChatPrompt|null>(null)
  const [preparedPromptNotice,setPreparedPromptNotice]=useState(false)
  useEffect(()=>{
    if(hidden || !preparedPrompt || preparedPrompt.id===handledPreparedPrompt.current)return
    handledPreparedPrompt.current=preparedPrompt.id
    setPreparedPromptNotice(false)
    if(input.length===0 && !selectedAgent && !sending && !humanCorrection){
      setInput(preparedPrompt.text)
      preparedCapabilityRef.current=preparedPrompt.capabilityId==='workspace.scan_duplicates'?{id:preparedPrompt.capabilityId,text:preparedPrompt.text}:null
      setPreparedPromptReview(null);setPreparedPromptNotice(true)
      onPreparedPromptHandled?.(preparedPrompt.id)
      composerRef.current?.focus()
    }else setPreparedPromptReview(preparedPrompt)
  },[hidden,preparedPrompt,input,selectedAgent,sending,humanCorrection,onPreparedPromptHandled])

  const contextMenuRef = useRef<HTMLDivElement>(null)
  const longPressTimerRef = useRef<number | null>(null)
  const longPressTriggeredRef = useRef(false)
  const agentRefreshAtRef = useRef(0)
  const agentRefreshInFlightRef = useRef<Promise<void> | null>(null)
  const agentsLoadedRef = useRef(false)

  const latestUserMessageId = [...messages].reverse().find((message) => message.role === 'user')?.id
  const conversationAgents = useMemo(() => {
    const participants = new Map<string, { id: string; name: string; model: string }>()
    if (selectedAgent && activeConversation?.owner_kind === 'agent' && activeConversation.owner_id === selectedAgent.id) participants.set(selectedAgent.id, {
      id: selectedAgent.id,
      name: selectedAgent.config.name,
      model: selectedAgent.config.model_id || t('commerce.no_model_assigned'),
    })
    for (const message of messages) {
      const delegation = message.agentDelegation
      if (!delegation?.child_conversation_id || !['RUNNING', 'PASSED', 'FAILED', 'INCONCLUSIVE', 'OUT_OF_SCOPE', 'NEEDS_AUTHORIZATION', 'NEEDS_REVIEW'].includes(delegation.state)) continue
      participants.set(delegation.agent_id, { id: delegation.agent_id, name: delegation.agent_name, model: delegation.model_id })
    }
    return [...participants.values()]
  }, [activeConversation, messages, selectedAgent])

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
    let loadSequence = 0
    const load = () => {
      const sequence = ++loadSequence
      const selectionGeneration = chatProviderMutation.current.generation
      void Promise.all([
      fetch('/api/providers/chat-models').then(async response => {
        if (!response.ok) throw await responseError(response)
        return response.json() as Promise<{ models?: ChatProvider[] }>
      }),
      fetch('/api/providers/selection').then(async response => response.ok ? response.json() as Promise<ChatProviderSelection> : null),
    ]).then(([available, selected]) => {
      if (!active || sequence !== loadSequence) return
      const usable = (available.models ?? []).filter(provider => ['ready', 'configured_unverified'].includes(provider.state) && provider.model_id && (provider.orchestrator_enabled ?? provider.chat_enabled) !== false)
      setChatProviders(usable)
      const mutation = chatProviderMutation.current
      if (selectionGeneration === mutation.generation && !mutation.pending && !mutation.failed && !chatDispatchPending.current) setChatProviderSelection(selected)
    }).catch(cause => {
      if (active && sequence === loadSequence && selectionGeneration === chatProviderMutation.current.generation && !chatProviderMutation.current.pending && !chatProviderMutation.current.failed) setError(cause instanceof Error ? cause : "commerce.could_not_load_orchestrator_models")
    })
    }
    load()
    window.addEventListener('adl-model-policy-changed', load)
    return () => { active = false; chatProviderMutation.current.generation++; window.removeEventListener('adl-model-policy-changed', load) }
  }, [])

  const changeChatProvider = async (value: string) => {
    if (chatDispatchPending.current || chatProviderMutation.current.pending) return
    const [provider_id, model_id] = value.split('|')
    if (!provider_id || !model_id) return
    const generation = chatProviderMutation.current.generation + 1
    chatProviderMutation.current = {generation,pending:true,failed:false}
    setSavingChatProvider(true); setError('')
    try {
      const response = await fetch('/api/providers/selection', {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider_id, model_id }),
      })
      if (!response.ok) throw await responseError(response)
      const saved = await response.json() as ChatProviderSelection
      if (generation !== chatProviderMutation.current.generation) return
      if (saved?.provider_id !== provider_id || saved?.model_id !== model_id) throw new Error("commerce.could_not_change_the_orchestrator_model")
      chatProviderMutation.current = {generation,pending:false,failed:false}
      setChatProviderSelection(saved)
      setChatProviderSelectionFailed(false)
    } catch (cause) {
      if (generation !== chatProviderMutation.current.generation) return
      chatProviderMutation.current = {generation,pending:false,failed:true}
      setChatProviderSelectionFailed(true)
      setError(cause instanceof Error ? cause : "commerce.could_not_change_the_orchestrator_model")
    } finally { if (generation === chatProviderMutation.current.generation) setSavingChatProvider(false) }
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
  const conversationScope = `${ownerKind}:${ownerId}:${libraryMode}:${workspaceScopeVersion}`
  const conversationScopeRef = useRef(conversationScope)
  conversationScopeRef.current = conversationScope
  const matchesOwner = (conversation: ConversationSummary) => conversation.owner_kind === ownerKind && conversation.owner_id === ownerId
  const correctionContext = useRef<HumanCorrectionContext>({ownerKind,ownerId,conversation:activeConversation,messages})
  correctionContext.current = {ownerKind,ownerId,conversation:activeConversation,messages}
  function correctionSourceCurrent(source: HumanCorrectionSource) {
    return isHumanCorrectionSourceCurrent(source,correctionContext.current)
  }
  function openHumanCorrection(message: Message, origin: HTMLElement) {
    if(humanCorrection || sending || !activeConversation || activeConversation.status!=='active' || !matchesOwner(activeConversation) || message.role!=='assistant' || !message.content)return
    setHumanCorrection({source:{ownerKind,ownerId,conversationId:activeConversation.id,revision:activeConversation.revision,
      messageId:message.id,content:message.uiContent?errorMessage(message.uiContent):message.content,...(message.trace?.localId?{traceId:message.trace.localId}:{})},origin})
  }
  function closeHumanCorrection() {
    correctionReturnFocus.current=humanCorrection?.origin??null
    setHumanCorrection(null)
  }
  const correctionPermissions=`permisos READ/WRITE persistentes del proyecto, web pública ${allowPublicWebRead?'activada':'desactivada'}, carpeta ${documentConsent?'con permiso actual':'sin permiso actual'}`
  const correctionPermissionIdentity=JSON.stringify({projectId:activeProject?.project_id,projectRoot:activeProject?.root,providerId:selectedAgent?.config.provider_id??chatProviderSelection?.provider_id,modelId:selectedAgent?.config.model_id??chatProviderSelection?.model_id,savingChatProvider,chatProviderSelectionFailed,cognitiveMode,allowPublicWebRead,publicWebUrls,documentRoot,documentConsent,documentOutputConsent,documentOutputDirectory,reviewWork,reviewContact,draftConsent})

  const clearInspectionSelection = () => {setActiveConversation(null);setMessages([]);onInspectionSelection?.(null)}

  useEffect(() => {setAllowPublicWebRead(false);setPublicWebUrls('');setDocumentConsent(false);setDocumentOutputConsent(false);setDraftConsent(false)}, [activeConversation?.id, ownerId])

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
        ...(message.role === 'assistant' && message.references?.agent_delegation ? { agentDelegation: message.references.agent_delegation } : {}),
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
        if (historySelection === 'explicit') {
          setActiveConversation(null); setMessages([])
        } else if (libraryMode === 'deleted' && conversations.length) {
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
  useEffect(() => {
    clearInspectionSelection()
    setConversationList([])
    setActiveProject(null)
    void fetch('/api/project-folders/v1/active').then(async response => {
      if (!response.ok) throw await responseError(response)
      return response.json()
    }).then(value => {
      if (conversationScopeRef.current.endsWith(`:${workspaceScopeVersion}`)) {
        setActiveProject({project_id:typeof value.project_id==='string'?value.project_id:null,title:typeof value.title==='string'?value.title:'',scope:typeof value.scope==='string'?value.scope:'unknown',root:typeof value.root==='string'?value.root:null})
      }
    }).catch(() => { setActiveProject(null) })
    void refreshConversationList()
    return () => {conversationLoadGeneration.current++}
  }, [ownerKind, ownerId, libraryMode, historySelection, workspaceScopeVersion])
  useEffect(() => { void refreshConversationProposals(activeConversation?.id ?? null) }, [activeConversation?.id])
  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])
  useEffect(() => () => { if (conversationScrollTimerRef.current !== null) window.clearTimeout(conversationScrollTimerRef.current) }, [])
  const revealConversationScrollControls = () => {
    const element = messagesContainerRef.current
    if (!element || element.scrollHeight <= element.clientHeight + 4) return
    setShowConversationScrollControls(true)
    if (conversationScrollTimerRef.current !== null) window.clearTimeout(conversationScrollTimerRef.current)
    conversationScrollTimerRef.current = window.setTimeout(() => { setShowConversationScrollControls(false); conversationScrollTimerRef.current = null }, 3500)
  }
  const scrollConversation = (edge: 'start' | 'end') => {
    const element = messagesContainerRef.current
    if (!element) return
    element.scrollTo({top: edge === 'start' ? 0 : element.scrollHeight, behavior: 'smooth'})
    revealConversationScrollControls()
  }
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

  const openDelegatedChild = async (identity: { agentId: string; conversationId: string }) => {
    const agent = agents.find(item => item.id === identity.agentId)
    if (!agent) { setLibraryError('commerce.the_saved_agent_for_this_child_conversation_is_unavailable'); return }
    setSelectedAgent(agent)
    setLibraryMode('active')
    await new Promise(resolve => window.setTimeout(resolve, 0))
    try {
      const response = await fetch(`/api/conversations/${encodeURIComponent(identity.conversationId)}`)
      if (!response.ok) throw await responseError(response)
      const conversation = await response.json() as StoredConversation
      if (conversation.id !== identity.conversationId || conversation.owner_kind !== 'agent' || conversation.owner_id !== identity.agentId || conversation.status === 'deleted') throw new Error('commerce.conversation_response_identity_mismatch')
      applyConversation(conversation)
    } catch (cause) { setLibraryError(cause instanceof Error ? cause : 'commerce.conversation_could_not_be_opened') }
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

  const manageConversationLabels = async (target: ConversationSummary) => {
    const raw = window.prompt(t('commerce.labels_prompt'), (target.labels ?? []).join(', '))
    if (raw === null) return
    const labels = raw.split(',').map(label => label.trim()).filter(Boolean)
    try {
      const response = await fetch(`/api/conversations/${encodeURIComponent(target.id)}/labels`, {
        method: 'PATCH', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ revision: target.revision, labels }),
      })
      if (!response.ok) throw await responseError(response)
      const updated = await response.json() as StoredConversation
      if (activeConversation?.id === target.id) applyConversation(updated)
      await refreshConversationList()
    } catch (cause) {
      setLibraryError(cause instanceof Error ? cause : 'commerce.conversation_labels_could_not_be_updated')
      if (cause instanceof Error && cause.message.includes('changed elsewhere')) await refreshConversationList()
    }
  }

  const showConversationContextMenu = (conversation: ConversationSummary, x: number, y: number) => {
    const menuWidth = 184
    const menuHeight = conversation.status === 'deleted' ? 104 : 164
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

  const sendMessage = async (event?: FormEvent, correctionRequest?: PreparedHumanCorrection) => {
    event?.preventDefault()
    if (correctionRequest && (correctionRequest.source!==humanCorrection?.source || !correctionSourceCurrent(correctionRequest.source) || !/^[a-f0-9]{64}$/.test(correctionRequest.sourceSha256))) {
      setError(new Error('El contexto de la respuesta cambió. La corrección no se ha enviado.'));return
    }
    const content = correctionRequest ? correctionRequest.content : input.trim()
    if (!content || sending || chatDispatchPending.current || (!selectedAgent && (chatProviderMutation.current.pending || chatProviderMutation.current.failed))) return
    const explicitCapabilityId=!correctionRequest && !selectedAgent && preparedCapabilityRef.current?.id==='workspace.scan_duplicates' && preparedCapabilityRef.current.text===input ? preparedCapabilityRef.current.id : undefined
    chatDispatchPending.current = true
    if (!correctionRequest) setInput('')
    setError('')
    setLibraryError('')
    const readWebForThisMessage = allowPublicWebRead
    const documentRootForThisMessage = selectedAgent && documentConsent ? documentRoot : ''
    const outputDocumentsForThisMessage = documentOutputConsent
    const selectedReviewForThisMessage=reviewContext.runs.find(run=>run.work_id===reviewWork)
    const contactForThisMessage=reviewContact,draftForThisMessage=draftConsent
    setDraftConsent(false)
    setDocumentConsent(false);setDocumentOutputConsent(false)
    const urlsForThisMessage = publicWebUrls
    setAllowPublicWebRead(false)
    setSending(true)
    const generation = conversationLoadGeneration.current
    const scope = conversationScopeRef.current
    const current = () => generation === conversationLoadGeneration.current && scope === conversationScopeRef.current && (!correctionRequest || correctionSourceCurrent(correctionRequest.source))
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
      const localCapabilityIntent = !selectedAgent ? (correctionRequest || explicitCapabilityId ? {operation:'chat' as const} : inferIntent(content, cognitiveMode)) : null
      if (localCapabilityIntent?.operation === 'list_capabilities' || localCapabilityIntent?.operation === 'propose_capability') {
        await beginCapabilityRequest(content, localCapabilityIntent.operation, conversation.id)
        return
      }
      setMessages((previous) => [...previous, { id: idFor(), role: 'user', content }])
      let documentAuthorizationId: string | undefined
      if (documentRootForThisMessage && selectedAgent) {
        const authorizationResponse = await fetch('/api/document-tools/authorizations', {
          method:'POST',headers:{'Content-Type':'application/json'},
          body:JSON.stringify({owner_id:selectedAgent.id,conversation_id:conversation.id,revision:conversation.revision,
            root:documentRootForThisMessage,confirmed:true,allow_export:outputDocumentsForThisMessage,
            ...(outputDocumentsForThisMessage?{expected_output_directory:documentOutputDirectory}:{}),
            ...(selectedReviewForThisMessage?{review_work_id:selectedReviewForThisMessage.work_id,review_candidate_id:selectedReviewForThisMessage.candidate_id,review_scope_sha256:selectedReviewForThisMessage.scope_sha256}:{}),
            ...(contactForThisMessage?{contact_id:contactForThisMessage}:{}),allow_draft:draftForThisMessage}),
        })
        if (!authorizationResponse.ok) throw await responseError(authorizationResponse)
        const authorization = await authorizationResponse.json()
        if (authorization.root !== documentRootForThisMessage || typeof authorization.authorization_id !== 'string') throw new Error(t('agentTools.grantNotConfirmed'))
        documentAuthorizationId = authorization.authorization_id
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
          body: JSON.stringify({ message: content, conversation_id: conversation.id, revision: conversation.revision, cognitive_mode: cognitiveMode, ...(documentAuthorizationId?{document_authorization_id:documentAuthorizationId}:{}), ...(webReadAuthorizationId ? {web_read_authorization_id: webReadAuthorizationId} : {}) }),
        })
      } else {
        intent = localCapabilityIntent ?? inferIntent(content, cognitiveMode)
        response = await fetch('/api/chat/control', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ operation: intent.operation, message: content, conversation_id: conversation.id, revision: conversation.revision, ...(explicitCapabilityId ? {capability_id:explicitCapabilityId} : {}), ...(intent.operation === 'chat' ? { cognitive_mode: cognitiveMode } : {}), ...(webReadAuthorizationId ? {web_read_authorization_id: webReadAuthorizationId} : {}), ...(intent.view ? { view: intent.view } : {}) }),
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
        if (data.assistant_message.trim() && selectedAgent.config.model_id) window.dispatchEvent(new CustomEvent(PROVIDER_RESPONSE_OBSERVED_EVENT, {detail: {provider_id: provider, model_id: selectedAgent.config.model_id, observed_at: new Date().toISOString()}}))
      } else {
        const observation = readProviderResponseObservation(data.provider_response_observation)
        if (observation) window.dispatchEvent(new CustomEvent(PROVIDER_RESPONSE_OBSERVED_EVENT, {detail: observation}))
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
      } else if (!selectedAgent && !['chat', 'help', 'agent_delegation'].includes(data.operation)) {
        throw new Error("commerce.the_server_returned_an_unsupported_chat_operation")
      }
      const query = new URLSearchParams({ owner_kind: ownerKind, owner_id: ownerId, status: libraryMode })
      const listResponse = await fetch(`/api/conversations?${query}`)
      if (listResponse.ok) {
        const list = await listResponse.json()
        if (current()) setConversationList(list.conversations || [])
      }
      if(correctionRequest && generation===conversationLoadGeneration.current && scope===conversationScopeRef.current) closeHumanCorrection()
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
      chatDispatchPending.current = false
      setSending(false)
    }
  }

  const closeAgentPanel = () => {
    if (agentPanelRef.current) agentPanelRef.current.open = false
    setAgentPanelOpen(false)
    agentPanelRef.current?.querySelector<HTMLElement>(':scope > summary')?.focus()
  }
  const openControlChat = () => { setSelectedAgent(null); setCapabilityDraft(null); setCapabilityProposals([]); setError('') }
  const selectAgent = (agent: Agent) => { setSelectedAgent(agent); setCapabilityDraft(null); setCapabilityProposals([]); setError('') }
  const latestDirectoryScanPromptId = [...messages].reverse().find((message) => message.inlineDirectoryScan)?.id
  const latestDelegationMessageIds = new Set<string>()
  const seenDelegationProposalIds = new Set<string>()
  for (const message of [...messages].reverse()) {
    const proposalId = message.agentDelegation?.proposal_id
    if (proposalId && !seenDelegationProposalIds.has(proposalId)) {
      seenDelegationProposalIds.add(proposalId)
      latestDelegationMessageIds.add(message.id)
    }
  }

  const orderedConversationList = [...conversationList].sort((a,b)=>{
    let result = 0
    if (conversationSort.key === 'title') {
      result = a.title.localeCompare(b.title, getLocale(), {sensitivity: 'base', numeric: true})
    } else if (conversationSort.key === 'labels') {
      result = (a.labels ?? []).join(', ').localeCompare((b.labels ?? []).join(', '), getLocale(), {sensitivity: 'base', numeric: true})
    } else {
      const first = conversationActivity(a[conversationSort.key])
      const second = conversationActivity(b[conversationSort.key])
      if (Number.isFinite(first) && Number.isFinite(second)) result = first - second
      else if (Number.isFinite(first)) return -1
      else if (Number.isFinite(second)) return 1
    }
    if (result !== 0) return result * (conversationSort.direction === 'asc' ? 1 : -1)
    return a.id.localeCompare(b.id)
  })
  const conversationTitle = (conversation: ConversationSummary) => conversation.title === 'New conversation' ? t('commerce.new_conversation') : conversation.title
  const conversationTime = (value: string | undefined, label: 'commerce.created_date' | 'commerce.last_activity_date') => {
    if (!Number.isFinite(conversationActivity(value))) return <span>{t('commerce.timestamp_unavailable')}</span>
    return <time dateTime={value}>{t(label, {date: formatDate(value!)})}</time>
  }
  const selectConversation = (conversation: ConversationSummary) => {
    if (conversation.status === 'deleted') { setActiveConversation({ ...conversation, messages: [] }); setMessages([]) }
    else void openConversation(conversation.id)
  }
  const conversationSelectionEvents = (conversation: ConversationSummary) => ({
    onContextMenu: (event: ReactMouseEvent<HTMLButtonElement>) => { event.preventDefault(); cancelConversationLongPress(); conversationActionTriggerRef.current = event.currentTarget; showConversationContextMenu(conversation, event.clientX, event.clientY) },
    onPointerDown: (event: ReactPointerEvent<HTMLButtonElement>) => {
      if (event.pointerType !== 'touch') return
      cancelConversationLongPress()
      longPressTriggeredRef.current = false
      const {clientX, clientY} = event
      longPressTimerRef.current = window.setTimeout(() => { longPressTriggeredRef.current = true; showConversationContextMenu(conversation, clientX, clientY) }, 550)
    },
    onPointerUp: cancelConversationLongPress,
    onPointerCancel: cancelConversationLongPress,
    onPointerLeave: cancelConversationLongPress,
    onKeyDown: (event: ReactKeyboardEvent<HTMLButtonElement>) => {
      if (event.key !== 'ContextMenu' && !(event.shiftKey && event.key === 'F10')) return
      event.preventDefault()
      const bounds = event.currentTarget.getBoundingClientRect()
      conversationActionTriggerRef.current = event.currentTarget
      showConversationContextMenu(conversation, bounds.left, bounds.bottom)
    },
  })
  const renderConversationSelection = (conversation: ConversationSummary, compact: boolean) => <button
    key={conversation.id}
    type="button"
    className={`${compact ? 'conversation-library-item' : 'conversation-library-table-select'} ${activeConversation?.id === conversation.id ? 'selected' : ''}`}
    aria-pressed={activeConversation?.id === conversation.id}
    onClick={(event) => { if (longPressTriggeredRef.current) { event.preventDefault(); longPressTriggeredRef.current = false; return }; setConversationContextMenu(null); selectConversation(conversation) }}
    {...conversationSelectionEvents(conversation)}
  >
    <strong>{conversationTitle(conversation)}</strong>
    {compact && <span>{conversationTime(conversation.updated_at, 'commerce.last_activity_date')}</span>}
  </button>
  const renderConversationActions = (conversation: ConversationSummary) => <button
    type="button"
    className="conversation-row-actions-button"
    aria-label={t('commerce.conversation_actions', {title: conversationTitle(conversation)})}
    onClick={event => { event.stopPropagation(); conversationActionTriggerRef.current = event.currentTarget; const bounds = event.currentTarget.getBoundingClientRect(); showConversationContextMenu(conversation, bounds.left, bounds.bottom) }}
  ><span aria-hidden="true">⋯</span></button>
  const sortHeader = (key: ConversationSortKey, label: string) => {
    const selected = conversationSort.key === key
    const direction = selected ? conversationSort.direction : 'none'
    return <th scope="col" aria-sort={direction === 'asc' ? 'ascending' : direction === 'desc' ? 'descending' : 'none'}>
      <button type="button" onClick={() => setConversationSort(current => current.key === key ? {key, direction: current.direction === 'asc' ? 'desc' : 'asc'} : {key, direction: key === 'updated_at' ? 'desc' : 'asc'})}>
        {label}<span aria-hidden="true"> {selected ? conversationSort.direction === 'asc' ? '↑' : '↓' : '↕'}</span>
      </button>
    </th>
  }
  const conversationLibrary = (
    <section style={!selectedAgent ? {flex: '1 1 0', minHeight: 0, maxHeight: 'none', margin: 0} : undefined} className="chat-sidebar-pane conversation-library" aria-label={t('commerce.conversation_library')}>
              {selectedAgent && <div className="conversation-library-heading"><strong>{t('commerce.chat_title_named',{name:selectedAgent.config.name})}</strong></div>}
              {!selectedAgent && <div className="conversation-library-heading conversation-library-project"><strong>{t('commerce.project_chats')}</strong><span title={activeProject?.title||undefined}>{activeProject?.title||t('commerce.project_not_registered')}</span></div>}
              <TabStrip<LibraryMode> label={t('commerce.conversation_status')} value={libraryMode} onChange={setLibraryMode} items={[{ id: 'active', label: t('commerce.recent') }, { id: 'archived', label: t('commerce.archived') }, { id: 'deleted', label: t('commerce.trash') }]} />
              {loadingConversation && <p className="muted-state" role="status">{t('commerce.opening_conversation')}</p>}
              {libraryError && <p className="inline-error" role="alert">{errorMessage(libraryError)}</p>}
              {conversationList.length === 0 && !libraryError && <p className="muted-state">{t(libraryMode==='active'?'commerce.empty_library_active':libraryMode==='archived'?'commerce.empty_library_archived':'commerce.empty_library_deleted',{owner:selectedAgent?t('commerce.for_this_agent'):t('commerce.with_the_orchestrator')})}</p>}
              {(!projectPanelExpanded || Boolean(selectedAgent) || agentPanelOpen) && <div style={!selectedAgent ? {flex: '1 1 0', minHeight: 0, overflowY: 'auto'} : undefined} className="conversation-library-list">
                {orderedConversationList.map(conversation => <div className="conversation-compact-row" data-conversation-id={conversation.id} key={`compact-${conversation.id}`}>
                  {renderConversationSelection(conversation, true)}{renderConversationActions(conversation)}
                </div>)}
              </div>}
              {projectPanelExpanded && !selectedAgent && !agentPanelOpen && <div className="conversation-library-table-scroll" role="region" aria-label={t('commerce.conversation_library_table')} tabIndex={0}>
                <table className="conversation-library-table">
                  <caption className="visually-hidden">{t('commerce.conversation_library_table_caption')}</caption>
                  <thead><tr>
                    {sortHeader('title', t('commerce.conversation_name'))}
                    {sortHeader('labels', t('commerce.conversation_labels'))}
                    {sortHeader('created_at', t('commerce.conversation_created'))}
                    {sortHeader('updated_at', t('commerce.conversation_last_activity'))}
                    <th scope="col" aria-label={t('commerce.conversation_actions_heading')}></th>
                  </tr></thead>
                  <tbody>{orderedConversationList.map(conversation => <tr data-conversation-id={conversation.id} data-selected={activeConversation?.id === conversation.id} key={`table-${conversation.id}`}>
                    <td>{renderConversationSelection(conversation, false)}</td>
                      <td><div className="conversation-labels">{(conversation.labels ?? []).length > 0
                        ? (conversation.labels ?? []).map(label => <span className="conversation-label-chip" key={`${conversation.id}-${label}`}>{label}</span>)
                        : <span className="conversation-labels-empty">{t('commerce.no_labels')}</span>}</div></td>
                    <td>{conversationTime(conversation.created_at, 'commerce.created_date')}</td>
                    <td>{conversationTime(conversation.updated_at, 'commerce.last_activity_date')}</td>
                    <td>{renderConversationActions(conversation)}</td>
                  </tr>)}</tbody>
                </table>
              </div>}
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
                  if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); setConversationContextMenu(null); conversationActionTriggerRef.current?.focus(); return }
                  if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') return
                  event.preventDefault()
                  const items = Array.from(event.currentTarget.querySelectorAll<HTMLButtonElement>('button'))
                  const currentIndex = items.indexOf(document.activeElement as HTMLButtonElement)
                  const direction = event.key === 'ArrowDown' ? 1 : -1
                  items[(currentIndex + direction + items.length) % items.length]?.focus()
                }}
              >
                {conversationContextMenu.conversation.status !== 'deleted' && <button type="button" role="menuitem" onClick={() => { const { conversation } = conversationContextMenu; setConversationContextMenu(null); void manageConversationLabels(conversation) }}>{t('commerce.edit_labels')}</button>}
                {conversationContextMenu.conversation.status !== 'deleted' && <button type="button" role="menuitem" onClick={() => { const { conversation } = conversationContextMenu; setConversationContextMenu(null); void manageConversation('rename', conversation) }}>{t('commerce.rename')}</button>}
                {conversationContextMenu.conversation.status === 'active' && <button type="button" role="menuitem" onClick={() => { const { conversation } = conversationContextMenu; setConversationContextMenu(null); void manageConversation('archive', conversation) }}>{t('commerce.archive')}</button>}
                {conversationContextMenu.conversation.status !== 'deleted' && <button type="button" role="menuitem" onClick={() => { const { conversation } = conversationContextMenu; setConversationContextMenu(null); void manageConversation('delete', conversation) }}>{t('commerce.move_to_trash')}</button>}
                {conversationContextMenu.conversation.status !== 'active' && <button type="button" role="menuitem" onClick={() => { const { conversation } = conversationContextMenu; setConversationContextMenu(null); void manageConversation('restore', conversation) }}>{t('commerce.restore')}</button>}
                {conversationContextMenu.conversation.status === 'deleted' && <button type="button" role="menuitem" disabled={permanentlyDeleting} onClick={() => { const { conversation } = conversationContextMenu; setConversationContextMenu(null); void permanentlyDeleteConversation(conversation) }}>{t('commerce.permanently_delete')}</button>}
              </div>}
            </section>
  )
  return (
    <section hidden={hidden} style={hidden ? {display: 'none'} : undefined} className="control-chat" aria-label={t('commerce.agent_and_application_chat')} onScrollCapture={revealScrollbarWhileScrolling}>
      <div hidden={hidden || agentPanelOpen} className="development-panel-portal" ref={setDevelopmentPanelTarget} />
      {agentPanelTarget && createPortal(
        <details className="chat-agent-panel" ref={agentPanelRef} onToggle={event => setAgentPanelOpen(event.currentTarget.open)} onKeyDownCapture={event => {
          if (event.key !== 'Escape' || event.defaultPrevented || document.querySelector('dialog[open], [role="dialog"][aria-modal="true"], .chat-tools-menu[open], .conversation-context-menu')) return
          event.preventDefault(); event.stopPropagation(); closeAgentPanel()
        }}>
          <summary aria-expanded={agentPanelOpen} aria-controls={agentPanelContentId}>{t('commerce.conversations_and_agents')} <span>{conversationAgents.length}</span></summary>
          <aside id={agentPanelContentId} className="control-chat-sidebar" aria-label={t('commerce.orchestrator_conversations_and_agents')}>
            <div className="chat-agent-panel-close-row"><button type="button" aria-label={t('commerce.close_conversations_panel')} onClick={closeAgentPanel}>{t('commerce.close')} <span aria-hidden="true">×</span></button></div>
            {(selectedAgent || agentPanelOpen) && conversationLibrary}
            <section className="chat-sidebar-pane chat-sidebar-agents" aria-labelledby="chat-agents-title">
              <div className="chat-sidebar-heading"><div><h2 id="chat-agents-title">{t('commerce.agents')}</h2></div>{onManageAgents && <button type="button" className="secondary-action" onClick={onManageAgents}>{t('commerce.manage_agents')}</button>}</div>
              <section className="conversation-agent-activity" aria-label={t('commerce.agents_participating_in_the_selected_conversation')}>
                <strong>{t('commerce.agents_in_this_chat')}</strong>
                {conversationAgents.length === 0
                  ? <p>{t('commerce.no_agent_tasks_are_linked_to_this_conversation_yet')}</p>
                  : <div className="conversation-participant-list">{conversationAgents.map(agent => <article className="conversation-participant" key={agent.id}><strong>{agent.name}</strong><span>{agent.model}</span></article>)}</div>}
              </section>
              <button type="button" className={`control-agent-option ${selectedAgent === null ? 'selected' : ''}`} onClick={openControlChat}><strong>{t('commerce.app_assistant')}</strong></button>
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
        {preparedPromptReview && <section aria-label={t('commerce.capability_ui.review_title')} className="capability-chat-card">
          <h3>{t('commerce.capability_ui.review_title')}</h3><p>{t('commerce.capability_ui.review_preserve')}</p>
          {selectedAgent && <p>{t('commerce.capability_ui.review_agent')}</p>}
          <p style={{whiteSpace:'pre-wrap',overflowWrap:'anywhere'}}>{preparedPromptReview.text}</p>
          <button type="button" disabled={sending||Boolean(humanCorrection)} onClick={()=>{const request=preparedPromptReview;openControlChat();setInput(current=>current.length>0?current+'\n\n'+request.text:request.text);setPreparedPromptReview(null);setPreparedPromptNotice(true);onPreparedPromptHandled?.(request.id);composerRef.current?.focus()}}>{t('commerce.capability_ui.add_draft')}</button>
          <button type="button" onClick={()=>{onPreparedPromptHandled?.(preparedPromptReview.id);setPreparedPromptReview(null)}}>{t('commerce.capability_ui.discard')}</button>
        </section>}
        {preparedPromptNotice && <p role="status">{t('commerce.capability_ui.prepared_notice')}</p>}
        <div className="control-chat-transcript-frame">
        <div ref={messagesContainerRef} className="control-chat-messages" aria-live="polite" onScroll={revealConversationScrollControls}>
          {messages.length === 0 && <div className="chat-welcome"><div className="welcome-mark" aria-hidden="true">✳</div><h3>{selectedAgent ? t('commerce.chat_with',{name:selectedAgent.config.name}) : t('commerce.your_workspace_through_chat')}</h3>{!selectedAgent && <div className="prompt-suggestions"><button type="button" disabled={sending || orchestratorSelectionBlocked} onClick={() => {if (!chatProviderMutation.current.pending && !chatProviderMutation.current.failed) setInput('Lista mis agentes')}}>{t('commerce.list_my_agents')}</button><button type="button" disabled={sending || orchestratorSelectionBlocked} onClick={() => {if (!chatProviderMutation.current.pending && !chatProviderMutation.current.failed) setInput('Quiero crear un agente para…')}}>{t('commerce.create_an_agent')}</button><button type="button" disabled={sending || orchestratorSelectionBlocked} onClick={() => {if (!chatProviderMutation.current.pending && !chatProviderMutation.current.failed) setInput('Abre el Decision Inspector')}}>{t('commerce.open_the_inspector')}</button></div>}</div>}
          {messages.map((message) => <article key={message.id} className={`control-message control-message-${message.role}`} tabIndex={0} aria-labelledby={`message-author-${message.id}`} onContextMenu={event => {
            if ((event.target as HTMLElement).closest('input,textarea,[contenteditable="true"]') || !message.content) return
            event.preventDefault(); openMessageMenu(message, event.currentTarget, event.clientX, event.clientY)
          }} onKeyDown={event => {
            if (event.key !== 'ContextMenu' && !(event.key === 'F10' && event.shiftKey)) return
            if ((event.target as HTMLElement).closest('input,textarea,[contenteditable="true"]') || !message.content) return
            event.preventDefault(); const rect = event.currentTarget.getBoundingClientRect()
            openMessageMenu(message, event.currentTarget, rect.left + 16, rect.top + 36)
          }}><div className="control-message-heading"><span id={`message-author-${message.id}`} className="message-speaker">{message.role === 'user' ? t('commerce.you') : selectedAgent?.config.name ?? t('commerce.assistant')}</span>{message.content && <div className="control-message-actions"><button type="button" className="message-action" onClick={() => void copyMessage(message)}>{messageCopyState?.id === message.id ? messageCopyState.state === 'copied' ? t('commerce.copied') : t('commerce.copy_failed') : message.role === 'user' ? t('commerce.copy_message') : t('commerce.copy_response')}</button>{message.role==='assistant' && <button type="button" className="message-action" disabled={messageEditDisabled||Boolean(humanCorrection)||!activeConversation} onClick={event=>openHumanCorrection(message,event.currentTarget)}>Corregir interpretación</button>}{canEditMessage(message) && <button type="button" className="message-action" onClick={() => editLatestMessage(message)} disabled={messageEditDisabled}>{t('commerce.edit')}</button>}</div>}</div>{message.status === 'failed' && <p role="status">{t('commerce.failed_response_no_response_was_received_from_the_provider')}</p>}{message.content && <div className="control-message-content">{message.role === 'assistant' ? <AssistantMarkdown content={message.uiContent?errorMessage(message.uiContent):message.content} /> : message.content}</div>}{(message.communicationDraftId || message.communicationDraft) && <Communications key={`communication-${message.id}`} inline initialDraft={message.communicationDraft} draftId={message.communicationDraftId} conversationId={activeConversation?.id} onOpenFull={onOpenCommunication} />}{message.agentBuilderDraft && <AgentBuilder key={message.id} inline initialAgent={message.agentBuilderDraft} onAgentCreated={() => void refreshAgents()} />}{message.agentDelegation && latestDelegationMessageIds.has(message.id) && !selectedAgent && activeConversation?.owner_kind === 'assistant' && activeConversation.owner_id === 'app-assistant' && <AgentDelegation key={`delegation-${message.agentDelegation.proposal_id}`} proposal={message.agentDelegation} parentConversationId={activeConversation.id} parentRevision={activeConversation.revision} disabled={activeConversation.status !== 'active' || sending} onConversationUpdate={(conversation) => { if (conversation.id === activeConversation.id && conversation.owner_kind === 'assistant' && conversation.owner_id === 'app-assistant') applyConversation(conversation as StoredConversation) }} onOpenChild={identity => void openDelegatedChild(identity)} onInspectChild={onInspectExecution ? identity => onInspectExecution({conversationId:identity.conversationId,revision:identity.revision,traceId:identity.traceId}) : undefined} />}{message.inlineJobHistory && <JobHistory key={message.id} inline />}{message.workspaceProposal && <WorkspaceManager inline proposal={message.workspaceProposal} />}{message.workspaceWriteProposalError&&<p role="alert">{errorMessage(message.workspaceWriteProposalError)}</p>}{message.workspaceWriteProposal&&activeConversation&&<WorkspaceWriteReview proposal={message.workspaceWriteProposal} ownerKind={ownerKind} ownerId={ownerId} conversationId={activeConversation.id} conversationRevision={activeConversation.revision} />}{message.inlineDirectoryScan && message.id === latestDirectoryScanPromptId && !selectedAgent && activeConversation?.owner_kind === 'assistant' && <DirectoryScanRun key={`scan-form-${message.id}`} conversationId={activeConversation.id} revision={activeConversation.revision} disabled={activeConversation.status !== 'active'} showForm onConversationUpdate={(conversation) => applyConversation(conversation as StoredConversation)} />}{message.scanOutcome && activeConversation?.owner_kind === 'assistant' && <DirectoryScanRun key={`scan-results-${message.id}`} conversationId={activeConversation.id} revision={activeConversation.revision} showForm={false} initialOutcome={message.scanOutcome} onConversationUpdate={(conversation) => applyConversation(conversation as StoredConversation)} />}{message.scanOutcome && activeConversation && onInspectExecution && <button type="button" onClick={() => onInspectExecution({conversationId:activeConversation.id,revision:activeConversation.revision,traceId:message.scanOutcome!.trace.trace_id})}>{t('commerce.inspect_scan_execution')}</button>}{message.pendingNavigation && <section className="chat-navigation-confirmation" aria-label={t('commerce.confirm_screen_change')}><p>{t('commerce.switch_screen',{view:viewLabels[message.pendingNavigation]})}</p>{message.navigationDecision === 'accepted' ? <span role="status">{t('commerce.switching_screen')}</span> : message.navigationDecision === 'declined' ? <span role="status">{t('commerce.staying_in_chat')}</span> : <div className="draft-actions"><button type="button" className="secondary-action" onClick={() => setMessages((previous) => previous.map((item) => item.id === message.id ? { ...item, navigationDecision: 'declined' } : item))}>{t('commerce.stay_in_chat')}</button><button type="button" className="primary-action" onClick={() => { setMessages((previous) => previous.map((item) => item.id === message.id ? { ...item, navigationDecision: 'accepted' } : item)); onNavigate(message.pendingNavigation as ExistingView) }}>{t('commerce.yes_switch_screen')}</button></div>}</section>}{message.cognitiveTrace && <details><summary>{t('commerce.response_context')}</summary><CognitiveContextPanel trace={message.cognitiveTrace} /></details>}{message.sources?.some(source => source.source_type !== 'public_web') ? <details className="message-sources" aria-label={t('commerce.project_files_read')}><summary>{t('commerce.files_count',{count:formatNumber(message.sources.filter(source => source.source_type !== 'public_web').length)})}</summary><ul>{message.sources.filter(source => source.source_type !== 'public_web').map(source => <li key={`${source.path}:${source.start_line}-${source.end_line}`}><code>{source.path}{source.source_type === 'document' ? ' · '+JSON.stringify(source.locations?.slice(0,3) || []) : `:${source.start_line}-${source.end_line}`}</code>{source.content_sha256 && <small> SHA-256 {source.content_sha256}</small>}</li>)}</ul></details> : null}{message.sources?.some(source => source.source_type === 'public_web') ? <details className="message-sources" aria-label={t('commerce.public_web_sources_read')}><summary>{t('commerce.web_count',{count:formatNumber(message.sources.filter(source => source.source_type === 'public_web').length)})}</summary><ul>{message.sources.filter(source => source.source_type === 'public_web').map(source => <li key={`${source.snapshot_id ?? source.path}:${source.start_line}-${source.end_line}`}><code>{source.path}{source.source_type === 'document' ? ' · '+JSON.stringify(source.locations?.slice(0,3) || []) : `:${source.start_line}-${source.end_line}`}</code>{safePublicLink(source.final_url ?? source.path) ? <a href={safePublicLink(source.final_url ?? source.path)} target="_blank" rel="noreferrer">{t('commerce.open_public_url')}</a> : <span>{t('commerce.url_cannot_be_opened')}</span>}<small>{t('commerce.captured_utc')} {source.captured_at ?? t('commerce.not_recorded')} {t('commerce.text_sha_256')} {source.text_sha256 ?? source.content_sha256 ?? t('commerce.not_recorded_124')} {t('commerce.raw_hash')} {source.raw_sha256 ?? t('commerce.not_recorded_124')}</small>{source.requested_url && <small>{t('commerce.requested')} {source.requested_url}</small>}{source.snapshot_id && <code>{t('commerce.snapshot_label')} {source.snapshot_id}</code>}{source.snapshot_manifest_sha256 && <code>{t('commerce.manifest_sha_256')} {source.snapshot_manifest_sha256}</code>}</li>)}</ul></details> : null}{message.readEvents?.length ? <details className="message-sources" aria-label={t('commerce.read_only_analysis_evidence')}><summary>{t('commerce.reads')} {message.readEvents.some(event => event.decision !== 'ALLOW') ? message.readEvents.filter(event => event.decision !== 'ALLOW').map(event => `${humanState(event.decision)}${event.reason_code ? `: ${event.reason_code}` : ''}`).join(' · ') : t('commerce.no_issues_recorded')}</summary><ul>{message.readEvents.map((event, index) => <li key={`${event.path}:${index}`}><code>{event.decision} {event.path || t('commerce.unresolved_path')} {event.reason_code ? `· ${event.reason_code}` : ''}</code>{event.kind === 'document_tool' && <section aria-label={t('agentTools.receipt')}><p>{event.tool_name} · {event.executed ? (t('agentTools.executed')) : (t('agentTools.notExecuted'))} · {event.outcome || event.reason_code}</p>{event.corpus_coverage && <p>{t('agentTools.inventoryBatch')} {event.corpus_coverage.offset+event.corpus_coverage.batch_selected} / {event.corpus_coverage.total} · {event.corpus_coverage.complete ? (t('agentTools.complete')) : (t('agentTools.pendingBatches'))}</p>}{event.next_cursor && <button type="button" onClick={()=>{setInput(t('agentTools.continueInventory',{cursor:event.next_cursor}));composerRef.current?.focus()}}>{t('agentTools.nextBatch')}</button>}{event.output?.download_url?.startsWith('/api/document-tools/reports/') && <a href={event.output.download_url} download>{t('agentTools.downloadReport')}</a>}<small>{event.receipt_id}</small></section>}{event.kind === 'public_web_read' && <small> {t('commerce.public_web_read')} {event.decision}</small>}{event.kind === 'directory_code_scan' && <small>{t('commerce.scan_counts',{files:formatNumber(event.files_scanned??0),lines:formatNumber(event.lines_scanned??0),findings:formatNumber(event.finding_count??0),capped:event.truncated?t('commerce.capped'):'',hash:event.manifest_sha256??t('commerce.unavailable')})}</small>}</li>)}</ul></details> : null}{message.readEvents?.filter(event=>event.filesystem_proposal).map(event=><AgentServiceReview key={event.filesystem_proposal!.proposal_id} proposal={event.filesystem_proposal!} ownerId={ownerId} conversationId={activeConversation?.id||''} revision={activeConversation?.revision||0}/>)}{message.readEvents?.filter(event=>event.delivery_review).slice(-1).map(event=><section key={event.delivery_review!.review_id} aria-label={t('agentTools.deliveryReview')}><h3>{t('agentTools.deliveryReview')}</h3><p role="status">{event.delivery_review!.decision==='bloqueada'?t('agentTools.blocked'):event.delivery_review!.decision==='lista_para_revision'?t('agentTools.readyReview'):t('agentTools.needsClarification')}</p>{event.delivery_review!.pending.length>0&&<p>{t('agentTools.contentPending')}</p>}<p>{t('agentTools.noSend')}</p><details><summary>{t('agentTools.details')}</summary><pre>{JSON.stringify(event.delivery_review,null,2)}</pre></details></section>)}{message.trace && <div className="message-trace" aria-label={t('commerce.execution_trace_evidence')}>{activeConversation && onInspectExecution && <button type="button" onClick={() => onInspectExecution({conversationId:activeConversation.id,revision:activeConversation.revision,traceId:message.trace!.localId})}>{t('commerce.inspect_execution')}</button>}<details><summary>{t('commerce.trace_details')} {humanState(message.trace.state)}</summary><code>Local: {message.trace.localId}</code>{message.trace.jaegerId && <code>Jaeger: {message.trace.jaegerId}</code>}{message.trace.jaegerUrl && <a href={message.trace.jaegerUrl} target="_blank" rel="noreferrer">{t('commerce.open_in_jaeger')}</a>}</details></div>}</article>)}
          {capabilityDraft && <section className="capability-chat-card" aria-labelledby="capability-draft-title"><div className="draft-heading"><div><p className="section-eyebrow">{t('commerce.proposal_review')}</p><h3 id="capability-draft-title">{t('commerce.review_before_saving')}</h3></div><span className="draft-status">{t('commerce.not_saved')}</span></div><label>{t('commerce.capability')}<select value={capabilityDraft.capabilityId} onChange={(event) => setCapabilityDraft({ ...capabilityDraft, capabilityId: event.target.value })} disabled={capabilityBusy}><option value="">{t('commerce.choose_a_catalog_entry')}</option>{capabilityDraft.capabilities.map((item) => <option key={item.id} value={item.id}>{item.id} · {item.status} · {item.effect}</option>)}</select></label>{capabilityDraft.capabilityId && <p className="capability-chat-selected">{capabilityDraft.capabilities.find((item) => item.id === capabilityDraft.capabilityId)?.summary}</p>}<label>{t('commerce.request_summary')}<input value={capabilityDraft.summary} maxLength={500} onChange={(event) => setCapabilityDraft({ ...capabilityDraft, summary: event.target.value })} disabled={capabilityBusy} /></label><label>{t('commerce.requested_scope')}<textarea value={capabilityDraft.requestedScope} maxLength={1000} rows={3} onChange={(event) => setCapabilityDraft({ ...capabilityDraft, requestedScope: event.target.value })} disabled={capabilityBusy} /></label><div className="draft-actions"><button type="button" className="secondary-action" onClick={() => setCapabilityDraft(null)} disabled={capabilityBusy}>{t('commerce.discard')}</button><button type="button" className="primary-action" onClick={() => void saveCapabilityProposal()} disabled={capabilityBusy || !capabilityDraft.capabilityId || !capabilityDraft.summary.trim() || !capabilityDraft.requestedScope.trim()}>{capabilityBusy ? t('commerce.saving') : t('commerce.save_proposal')}</button></div></section>}
          {capabilityProposals.map((proposal) => <article className="capability-chat-saved" key={proposal.id}><div><strong>{proposal.capability_id}</strong><span>{humanState(proposal.status)} {t('commerce.revision')} {proposal.revision}</span></div><p>{proposal.summary}</p><p><strong>{t('commerce.requested_scope_148')}</strong> {proposal.requested_scope}</p><code>{proposal.id}</code>{proposal.status === 'PENDING_REVIEW' && <button type="button" className="secondary-action" onClick={() => void cancelChatProposal(proposal)} disabled={capabilityBusy}>{t('commerce.cancel_proposal')}</button>}</article>)}
          {error && <p className="chat-error" role="alert">{errorMessage(error)}{errorMessage(error).toLowerCase().includes('ollama') || errorMessage(error).toLowerCase().includes('provider') ? <button type="button" onClick={onOpenProviderSettings}>{t('commerce.open_provider_settings')}</button> : null}</p>}
          {sending && <p className="muted-state" role="status">{t('commerce.waiting_for_the_provider_response')}</p>}
          <div ref={messagesEndRef} />
        </div>
        {showConversationScrollControls && <div className="conversation-scroll-controls" role="group" aria-label={t('commerce.conversation_navigation')}>
          <button type="button" aria-label={t('commerce.scroll_to_conversation_start')} onClick={() => scrollConversation('start')}>↑</button>
          <button type="button" aria-label={t('commerce.scroll_to_conversation_end')} onClick={() => scrollConversation('end')}>↓</button>
        </div>}
        </div>
        {humanCorrection && <HumanCorrectionReview source={humanCorrection.source} current={correctionSourceCurrent(humanCorrection.source)} busy={sending} permissions={correctionPermissions} permissionIdentity={correctionPermissionIdentity} onCancel={closeHumanCorrection} onSend={prepared=>void sendMessage(undefined,prepared)}/>}
        <form className="control-chat-composer" onSubmit={(event) => void sendMessage(event)}><label className="visually-hidden" htmlFor="control-chat-input">{t('commerce.message_the_assistant_or_selected_agent')}</label>
          <div className="chat-composer-actions">
            <label className="workspace-read-toggle"><input type="checkbox" checked={allowPublicWebRead} onChange={event => setAllowPublicWebRead(event.target.checked)} disabled={sending || Boolean(activeConversation && activeConversation.status !== 'active')} /><span>{t('commerce.allow_public_web_reading')}</span></label>
            <div className="chat-context-controls">
              <ChatTools conversationId={activeConversation?.id} onOpenCommunication={onOpenCommunication} />
              <button type="button" onClick={onOpenCognitionSettings} aria-label={t('commerce.open_cognition_and_context_settings')}>{t('commerce.cognition')} {cognitiveMode === 'bago5' ? t('commerce.bago5_experimental') : t('commerce.baseline')} <span aria-hidden="true">↗</span></button>
            {!selectedAgent && <label className="chat-provider-picker"><span className="visually-hidden">{t('commerce.orchestrator_model')}</span><select aria-label={t('commerce.orchestrator_model')} value={!chatProviderSelectionFailed && chatProviderSelection ? `${chatProviderSelection.provider_id}|${chatProviderSelection.model_id}` : ''} onChange={event => void changeChatProvider(event.target.value)} aria-busy={savingChatProvider} data-provider-selection-state={savingChatProvider ? 'pending' : chatProviderSelectionFailed ? 'failed' : chatProviderSelection ? 'confirmed' : 'unselected'} disabled={sending || savingChatProvider || chatProviders.length === 0}><option value="" disabled>{chatProviders.length ? t('commerce.select_a_model') : t('commerce.configure_a_provider')}</option>{chatProviders.map(provider => <option key={`${provider.provider_id}|${provider.model_id}`} value={`${provider.provider_id}|${provider.model_id}`}>{provider.label} · {provider.display_name ?? provider.model_id}{provider.state === 'configured_unverified' ? t('commerce.unverified') : ''}</option>)}</select></label>}
            </div>
          </div><div className="chat-composer-input"><textarea ref={composerRef} id="control-chat-input" rows={2} value={input} onChange={(event) => setInput(event.target.value)} onKeyDown={(event) => {
          if (event.key !== 'Enter' || event.shiftKey || event.nativeEvent.isComposing || event.repeat) return
          event.preventDefault()
          void sendMessage()
        }} placeholder={activeConversation?.status && activeConversation.status !== 'active' ? t('commerce.restore_or_start_a_new_conversation') : selectedAgent ? t('commerce.message_agent',{name:selectedAgent.config.name}) : t('commerce.message_the_assistant')} disabled={sending || Boolean(activeConversation && activeConversation.status !== 'active')} />
            <button className="primary-action" type="submit" disabled={sending || orchestratorSelectionBlocked || !input.trim() || Boolean(activeConversation && activeConversation.status !== 'active')}>{sending ? 'Sending.' : t('commerce.send')}</button>
          </div>
          {allowPublicWebRead && <section aria-label={t('commerce.public_web_reading_scope')}><label className="workspace-read-paths">{t('commerce.entry_https_urls_one_per_line')}<textarea rows={3} value={publicWebUrls} onChange={event => setPublicWebUrls(event.target.value)} placeholder="https://www.ejemplo.com/" maxLength={16384} disabled={sending} /></label><p>{t('commerce.this_turn_only_public_pages_from_these_origins')}</p><ul aria-label={t('commerce.requested_web_origins')}>{[...new Set(publicWebUrls.split(/\r?\n/).map(value => {try {return new URL(value.trim()).origin} catch {return value.trim() ? t('commerce.invalid_url',{url:value.trim()}) : ''}}).filter(Boolean))].map(origin => <li key={origin}><code>{origin}</code></li>)}</ul></section>}

        </form>
        {!selectedAgent && <DevelopmentPanel key="app-assistant-context" ownerId={ownerId} projectRoot={activeProject?.root ?? null} portalTarget={developmentPanelTarget} disabled={sending} onExpandedChange={setProjectPanelExpanded} showChanges={false} historyContent={!agentPanelOpen ? conversationLibrary : undefined} workspaceContent={
          <ProjectPermissions
            projectId={activeProject?.project_id ?? null}
            projectRoot={activeProject?.root ?? null}
            refreshKey={workspaceScopeVersion}
            onBrowseWorkspace={() => onNavigate('workspace')}
          />
        } />}
        {selectedAgent && <DevelopmentPanel key={selectedAgent.id} ownerId={selectedAgent.id} projectRoot={activeProject?.root ?? null} portalTarget={developmentPanelTarget} disabled={sending} onExpandedChange={setProjectPanelExpanded} showChanges={Boolean(selectedAgent.config.tools?.some(tool=>tool.startsWith('development_')))} workspaceContent={
          <ProjectPermissions
            projectId={activeProject?.project_id ?? null}
            projectRoot={activeProject?.root ?? null}
            refreshKey={workspaceScopeVersion}
            onBrowseWorkspace={() => onNavigate('workspace')}
            workspaceContent={selectedAgent.config.tools?.some(tool=>['document_','filesystem_','delivery_','development_'].some(prefix=>tool.startsWith(prefix))) && (
                  <details className="workspace-read-paths project-sidebar-section">
                    <summary>{t('agentTools.workspace')}</summary>
                    <div className="project-sidebar-section-body">
                      <p className="project-sidebar-scope">Los permisos del proyecto se conservan entre conversaciones. Las operaciones de escritura propuestas requieren revisión y confirmación humanas.</p>
                      <button type="button" disabled={sending||documentBrowseBusy} onClick={()=>void browseDocuments()}>{t('agentTools.chooseFolder')}</button>
                      {documentBrowseError && <p role="alert">{documentBrowseError}</p>}
                      {documentFolders && <div aria-label={t('agentTools.browser')}>
                        <nav aria-label={t('agentTools.allowedFolders')}>{documentFolders.roots.map(root=><button type="button" key={root.path} disabled={documentBrowseBusy} onClick={()=>void browseDocuments(root.path)}>{root.name}</button>)}</nav>
                        {documentFolders.path && <><p><code>{documentFolders.path}</code></p><button type="button" disabled={documentBrowseBusy} onClick={()=>{setDocumentRoot(documentFolders.path!);setDocumentConsent(false);setDocumentOutputConsent(false);setDocumentFolders(null)}}>{t('agentTools.useFolder')}</button></>}
                        {documentFolders.parent && <button type="button" disabled={documentBrowseBusy} onClick={()=>void browseDocuments(documentFolders.parent!)}>{t('agentTools.parent')}</button>}
                        <ul>{documentFolders.directories.map(folder=><li key={folder.path}><button type="button" disabled={documentBrowseBusy} onClick={()=>void browseDocuments(folder.path)}>{folder.name}</button></li>)}</ul>
                      </div>}
                      {selectedAgent.config.tools?.some(tool=>tool.startsWith('delivery_'))&&<section aria-label={t('agentTools.deliveryReview')}>
                        <button type="button" disabled={sending} onClick={()=>void loadReviewContext()}>{t('agentTools.reloadResults')}</button>
                        {reviewContextError&&<p role="alert">{t('agentTools.contextUnavailable')}</p>}
                        <label>{t('agentTools.work')}<select value={reviewWork} disabled={sending} onChange={event=>{const run=reviewContext.runs.find(item=>item.work_id===event.target.value);setReviewWork(event.target.value);if(run)setDocumentRoot(run.source_root);setDocumentConsent(false);setDraftConsent(false)}}><option value="">{t('agentTools.chooseWork')}</option>{reviewContext.runs.map(run=><option key={run.work_id} value={run.work_id}>{run.producer_name||run.owner_id} · {run.artifacts.map(a=>a.path.split('/').pop()).join(', ')} · {run.business_acceptance==='PASS'?t('agentTools.readyReview'):t('agentTools.contentPending')}</option>)}</select></label>
                        {!reviewContext.runs.length&&<p>{t('agentTools.noWork')}</p>}
                        <label>{t('agentTools.contact')}<select value={reviewContact} disabled={sending} onChange={event=>{setReviewContact(event.target.value);setDraftConsent(false);setDocumentConsent(false)}}><option value="">{t('agentTools.chooseContact')}</option>{reviewContext.contacts.map(contact=><option key={contact.id} value={contact.id}>{contact.name} · {contact.phone}</option>)}</select></label>
                        <button type="button" onClick={()=>onNavigate('communications')}>{t('agentTools.manageContacts')}</button>
                        {selectedAgent.config.tools.includes('delivery_prepare_draft')&&<label><input type="checkbox" checked={draftConsent} disabled={sending||!documentConsent||!reviewWork||!reviewContact} onChange={event=>setDraftConsent(event.target.checked)}/>{t('agentTools.allowDraft')}</label>}
                      </section>}
                      {documentRoot && <><p><code>{documentRoot}</code></p><label><input type="checkbox" checked={documentConsent} disabled={sending} onChange={event=>setDocumentConsent(event.target.checked)}/>{t('agentTools.scopeGrant')}</label>
                        {selectedAgent.config.tools.includes('document_export') && <label><input type="checkbox" checked={documentOutputConsent} disabled={sending||!documentConsent||!documentOutputDirectory} onChange={event=>setDocumentOutputConsent(event.target.checked)}/>{t('agentTools.reportGrant')}<code>{documentOutputDirectory}</code></label>}
                        <p>{t('agentTools.confirmationNotice')}</p></>}
                    </div>
                  </details>
                )}
          />
        } />}
        <div className="chat-agent-panel-slot" ref={setAgentPanelTarget} />
      </WindowPanel>
      {menuMessage && messageContextMenu && createPortal(<div ref={messageMenuRef} className="chat-message-context-menu" role="menu" aria-labelledby={`message-author-${menuMessage.id}`} style={{ left: messageContextMenu.x, top: messageContextMenu.y }} onKeyDown={event => {
        if (event.key === 'Escape') { event.preventDefault(); closeMessageMenu(true); return }
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
        {menuMessage.role==='assistant' && <button type="button" role="menuitem" tabIndex={-1} disabled={messageEditDisabled||Boolean(humanCorrection)||!activeConversation} onClick={()=>{const origin=messageContextMenu.origin;closeMessageMenu();openHumanCorrection(menuMessage,origin)}}>Corregir interpretación</button>}
        {canEditMessage(menuMessage) && <button type="button" role="menuitem" tabIndex={-1} disabled={messageEditDisabled} onClick={() => { closeMessageMenu(); editLatestMessage(menuMessage) }}>{t('commerce.edit')}</button>}
      </div>, document.body)}
    </section>
  )
}
