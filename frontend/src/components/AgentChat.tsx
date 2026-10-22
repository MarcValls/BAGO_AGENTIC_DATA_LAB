import './AgentChat.css'
import './WindowsSurface.css'
import { FormEvent, useCallback, useEffect, useRef, useState } from 'react'
import type { UIEvent } from 'react'
import { createPortal } from 'react-dom'
import { Capability, CapabilityProposal, capabilityResponseError } from './CapabilityManager'
import AgentBuilder from './AgentBuilder'
import DirectoryScanRun, { type ScanOutcome, type ScanReceipt, type ScanReport, type ScanTrace } from './DirectoryScanRun'
import JobHistory from './JobHistory'
import ChatTools from './ChatTools'
import WindowPanel from './WindowPanel'
import TabStrip from './TabStrip'

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
type WorkspaceSource = { path: string; start_line: number; end_line: number; file_sha256?: string; content_sha256?: string }
type WorkspaceReadEvent = { decision: 'ALLOW' | 'DENY'; kind?: string; path: string | null; reason_code?: string; file_sha256?: string; content_sha256?: string; files_scanned?: number; files_skipped?: number; bytes_scanned?: number; lines_scanned?: number; finding_count?: number; truncated?: boolean; manifest_sha256?: string }
type CognitiveTrace = { mode: 'baseline' | 'bago5'; enabled: boolean; profile?: string | null; method?: string; focus: Array<{ id: string; kind: string; label: string; score: number }>; capacity?: number; max_hops?: number; trace_id?: string; trace_state?: string }
type Message = { id: string; role: 'user' | 'assistant'; content: string; trace?: MessageTrace; cognitiveTrace?: CognitiveTrace; sources?: WorkspaceSource[]; readEvents?: WorkspaceReadEvent[]; agentBuilderDraft?: AgentConfig; inlineJobHistory?: boolean; inlineDirectoryScan?: boolean; scanOutcome?: ScanOutcome; pendingNavigation?: ExistingView; navigationDecision?: 'accepted' | 'declined' }
type ConversationSummary = { id: string; owner_kind: 'assistant' | 'agent'; owner_id: string; title: string; status: 'active' | 'archived' | 'deleted'; updated_at: string; revision: number }
type StoredConversation = ConversationSummary & { messages: Array<{ id: string; role: 'user' | 'assistant'; content: string; references?: { trace?: { trace_id?: string; trace_state?: string; jaeger_trace_id?: string; jaeger_url?: string } & Partial<ScanTrace>; cognitive_trace?: CognitiveTrace; sources?: WorkspaceSource[]; read_events?: Array<WorkspaceReadEvent & Partial<ScanReceipt>>; scan_result?: ScanReport; control_capability?: string } }> }
type LibraryMode = 'active' | 'archived' | 'deleted'
type ControlOperation = 'chat' | 'help' | 'list_agents' | 'draft_agent' | 'navigate' | 'list_capabilities' | 'propose_capability'
type ExistingView = 'inspector' | 'builder' | 'chat' | 'workspace' | 'runner' | 'control' | 'jobs' | 'traces' | 'summary' | 'retrieval' | 'authorization' | 'evaluation' | 'evaluation_lab' | 'provider_settings' | 'cognition_settings' | 'capabilities'
type CapabilityDraft = { capabilities: Capability[]; capabilityId: string; summary: string; requestedScope: string; conversationId: string | null }

function CognitiveContextPanel({ trace }: { trace: CognitiveTrace }) {
  const experimental = trace.mode === 'bago5'
  return <section className={`message-cognition${experimental ? ' message-cognition-bago5' : ''}`} aria-label="Model prompt mode and cognitive context">
    <div className="message-cognition-heading"><strong>{experimental ? 'BAGO5 cognitive focus' : 'Baseline prompt'}</strong><span>{experimental ? 'experimental' : 'comparison'}</span></div>
    {experimental ? <>
      <ul>{trace.focus.map((item) => <li key={item.id}><span>{item.label}</span><code>{item.score.toFixed(3)}</code></li>)}</ul>
      <small>{trace.profile} · {trace.method} · capacity {trace.capacity} · {trace.max_hops} hops</small>
    </> : null}
    {trace.trace_id && <small>Local focus trace: {trace.trace_id} · {trace.trace_state}</small>}
  </section>
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
  onNavigate: (view: ExistingView) => void
  onOpenProviderSettings: () => void
  onOpenCognitionSettings: () => void
  cognitiveMode: 'baseline' | 'bago5'
}

const idFor = () => `${Date.now()}-${Math.random().toString(16).slice(2)}`

const viewLabels: Record<ExistingView, string> = {
  inspector: 'Decision Inspector', builder: 'Agent Builder', chat: 'Chat', workspace: 'Workspace', runner: 'Agent Runs',
  control: 'Control', jobs: 'Job History', traces: 'Trace', summary: 'Summary', retrieval: 'Retrieval',
  authorization: 'Authorization', evaluation: 'Evaluation', evaluation_lab: 'Agent Evaluation Lab',
  provider_settings: 'Provider & models', cognition_settings: 'Cognition & context', capabilities: 'Capabilities',
}

async function responseError(response: Response): Promise<string> {
  try {
    const body = await response.json()
    const detail = body?.detail
    if (typeof detail === 'string') return detail
    if (typeof detail?.message === 'string') return detail.message
  } catch { /* keep a safe generic error */ }
  return `Request failed (${response.status}).`
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

export default function AgentChat({ onNavigate, onOpenProviderSettings, onOpenCognitionSettings, cognitiveMode }: AgentChatProps) {
  const [agents, setAgents] = useState<Agent[]>([])
  const [agentsState, setAgentsState] = useState<'loading' | 'ready' | 'error'>('loading')
  const [inventoryWarning, setInventoryWarning] = useState('')
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [activeConversation, setActiveConversation] = useState<StoredConversation | null>(null)
  const [conversationList, setConversationList] = useState<ConversationSummary[]>([])
  const [conversationContextMenu, setConversationContextMenu] = useState<{ conversation: ConversationSummary; x: number; y: number } | null>(null)
  const [libraryMode, setLibraryMode] = useState<LibraryMode>('active')
  const [libraryError, setLibraryError] = useState('')
  const [loadingConversation, setLoadingConversation] = useState(false)
  const [input, setInput] = useState('')
  const [messageCopyState, setMessageCopyState] = useState<{ id: string; state: 'copied' | 'failed' } | null>(null)
  const [allowWorkspaceRead, setAllowWorkspaceRead] = useState(false)
  const [workspaceReadPaths, setWorkspaceReadPaths] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState('')
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

  useEffect(() => {
    let active = true
    const load = () => { void Promise.all([
      fetch('/api/providers/chat-models').then(async response => {
        if (!response.ok) throw new Error(await responseError(response))
        return response.json() as Promise<{ models?: ChatProvider[] }>
      }),
      fetch('/api/providers/selection').then(async response => response.ok ? response.json() as Promise<ChatProviderSelection> : null),
    ]).then(([available, selected]) => {
      if (!active) return
      const usable = (available.models ?? []).filter(provider => ['ready', 'configured_unverified'].includes(provider.state) && provider.model_id && (provider.orchestrator_enabled ?? provider.chat_enabled) !== false)
      setChatProviders(usable)
      setChatProviderSelection(selected)
    }).catch(cause => {
      if (active) setError(cause instanceof Error ? cause.message : 'No se pudieron cargar los modelos del orquestador.')
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
      if (!response.ok) throw new Error(await responseError(response))
      setChatProviderSelection(await response.json() as ChatProviderSelection)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'No se pudo cambiar el modelo del orquestador.')
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
        if (!response.ok) throw new Error(await responseError(response))
        const data = await response.json()
        const nextAgents = Array.isArray(data.agents) ? data.agents as Agent[] : []
        setAgents(nextAgents)
        setSelectedAgent((current) => current ? nextAgents.find((agent) => agent.id === current.id) ?? current : null)
        agentsLoadedRef.current = true
        setInventoryWarning(data.warning_count
          ? `${data.warning_count} stored agent record(s) could not be loaded.`
          : '')
        setAgentsState('ready')
      } catch (cause) {
        if (background && agentsLoadedRef.current) {
          setInventoryWarning('Could not refresh the agent list. Showing the last loaded list.')
        } else {
          setAgentsState('error')
          setError(cause instanceof Error ? cause.message : 'Agent inventory could not be loaded.')
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

  const applyConversation = (conversation: StoredConversation) => {
    const inlineAgentDrafts = new Map(messages.filter((message) => message.agentBuilderDraft).map((message) => [message.id, message.agentBuilderDraft as AgentConfig]))
    const inlineJobHistoryIds = new Set(messages.filter((message) => message.inlineJobHistory).map((message) => message.id))
    const inlineDirectoryScanIds = new Set(messages.filter((message) => message.inlineDirectoryScan).map((message) => message.id))
    const pendingNavigations = new Map(messages.filter((message) => message.pendingNavigation).map((message) => [message.id, { view: message.pendingNavigation as ExistingView, decision: message.navigationDecision }]))
    setActiveConversation(conversation)
    setMessages(conversation.messages.map((message) => {
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
        ...(inlineAgentDrafts.has(message.id) ? { agentBuilderDraft: inlineAgentDrafts.get(message.id) } : {}),
        ...(inlineJobHistoryIds.has(message.id) ? { inlineJobHistory: true } : {}),
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
    setLibraryError('')
    try {
      const query = new URLSearchParams({ owner_kind: ownerKind, owner_id: ownerId, status: libraryMode })
      const response = await fetch(`/api/conversations?${query}`)
      if (!response.ok) throw new Error(await responseError(response))
      const data = await response.json()
      const conversations = Array.isArray(data.conversations) ? data.conversations as ConversationSummary[] : []
      setConversationList(conversations)
      if (!activeConversation || activeConversation.owner_kind !== ownerKind || activeConversation.owner_id !== ownerId || activeConversation.status !== libraryMode) {
        if (libraryMode === 'deleted' && conversations.length) {
          setActiveConversation({ ...conversations[0], messages: [] })
          setMessages([])
        } else if (conversations.length) {
          const latest = await fetch(`/api/conversations/${encodeURIComponent(conversations[0].id)}`)
          if (latest.ok) applyConversation(await latest.json() as StoredConversation)
          else { setActiveConversation(null); setMessages([]) }
        } else {
          setActiveConversation(null)
          setMessages([])
        }
      }
    } catch (cause) {
      setLibraryError(cause instanceof Error ? cause.message : 'Conversation library could not be loaded.')
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
  useEffect(() => { void refreshConversationList() }, [ownerKind, ownerId, libraryMode])
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
    setLibraryError('')
    try {
      const response = await fetch('/api/conversations', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ owner_kind: ownerKind, owner_id: ownerId }),
      })
      if (!response.ok) throw new Error(await responseError(response))
      const conversation = await response.json() as ConversationSummary
      setLibraryMode('active')
      const detail = await fetch(`/api/conversations/${encodeURIComponent(conversation.id)}`)
      if (!detail.ok) throw new Error(await responseError(detail))
      applyConversation(await detail.json() as StoredConversation)
      const query = new URLSearchParams({ owner_kind: ownerKind, owner_id: ownerId, status: 'active' })
      const list = await fetch(`/api/conversations?${query}`)
      if (list.ok) setConversationList((await list.json()).conversations || [])
    } catch (cause) {
      setLibraryError(cause instanceof Error ? cause.message : 'A new conversation could not be created.')
    }
  }

  const openConversation = async (conversationId: string) => {
    setLoadingConversation(true)
    setLibraryError('')
    try {
      const response = await fetch(`/api/conversations/${encodeURIComponent(conversationId)}`)
      if (!response.ok) throw new Error(await responseError(response))
      applyConversation(await response.json() as StoredConversation)
    } catch (cause) {
      setLibraryError(cause instanceof Error ? cause.message : 'Conversation could not be opened.')
    } finally { setLoadingConversation(false) }
  }

  const manageConversation = async (action: 'rename' | 'archive' | 'delete' | 'restore', target: ConversationSummary | StoredConversation | null = activeConversation) => {
    if (!target) return
    const title = action === 'rename' ? window.prompt('Conversation title', target.title) : null
    if (action === 'rename' && title === null) return
    const route = action === 'rename' ? `/api/conversations/${target.id}` : `/api/conversations/${target.id}/${action}`
    const method = action === 'rename' ? 'PATCH' : 'POST'
    const body = action === 'rename' ? { revision: target.revision, title } : { revision: target.revision }
    try {
      const response = await fetch(route, { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
      if (!response.ok) throw new Error(await responseError(response))
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
      setLibraryError(cause instanceof Error ? cause.message : 'Conversation could not be updated.')
      if (cause instanceof Error && cause.message.includes('changed elsewhere')) await refreshConversationList()
    }
  }

  const showConversationContextMenu = (conversation: ConversationSummary, x: number, y: number) => {
    const menuWidth = 184
    const menuHeight = conversation.status === 'active' ? 132 : conversation.status === 'archived' ? 104 : 56
    setConversationContextMenu({
      conversation,
      x: Math.max(8, Math.min(x, window.innerWidth - menuWidth - 8)),
      y: Math.max(8, Math.min(y, window.innerHeight - menuHeight - 8)),
    })
  }

  const cancelConversationLongPress = () => {
    if (longPressTimerRef.current !== null) window.clearTimeout(longPressTimerRef.current)
    longPressTimerRef.current = null
  }

  async function refreshConversationProposals(conversationId: string | null) {
    if (!conversationId) { setCapabilityProposals([]); return }
    try {
      const response = await fetch('/api/capabilities/proposals?status=all&limit=100')
      if (!response.ok) throw new Error(await capabilityResponseError(response))
      const data = await response.json()
      setCapabilityProposals((Array.isArray(data.proposals) ? data.proposals : []).filter((item: CapabilityProposal) => item.conversation_id === conversationId))
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Capability proposals could not be loaded.')
    }
  }

  async function beginCapabilityRequest(content: string, operation: 'list_capabilities' | 'propose_capability', conversationId: string | null) {
    setCapabilityBusy(true)
    setCapabilityDraft(null)
    setError('')
    try {
      const response = await fetch('/api/capabilities')
      if (!response.ok) throw new Error(await capabilityResponseError(response))
      const catalog = await response.json()
      const capabilities = Array.isArray(catalog.capabilities) ? catalog.capabilities as Capability[] : []
      setMessages((previous) => [...previous, { id: idFor(), role: 'user', content }])
      if (operation === 'list_capabilities') {
        const summary = capabilities.length
          ? capabilities.map((item) => `${item.id}: ${item.status} (${item.effect}) — ${item.name}`).join('\n')
          : 'The backend returned no capability records.'
        setMessages((previous) => [...previous, { id: idFor(), role: 'assistant', content: `${summary}\n\n${catalog.authority_notice || 'Catalog status does not grant permission or enable execution.'}` }])
        return
      }
      const lower = content.toLocaleLowerCase()
      const exactMatches = capabilities.filter((item) => lower.includes(item.id.toLocaleLowerCase()) || lower.includes(item.name.toLocaleLowerCase()))
      const capabilityId = exactMatches.length === 1 ? exactMatches[0].id : ''
      const summary = content.trim().slice(0, 500)
      setCapabilityDraft({ capabilities, capabilityId, summary, requestedScope: '', conversationId })
      setMessages((previous) => [...previous, { id: idFor(), role: 'assistant', content: exactMatches.length === 1
        ? `I found the exact backend catalog entry “${exactMatches[0].id}”. Review the capability, summary, and requested scope below before saving a proposal.`
        : 'I could not select one exact catalog entry from that request. Choose the intended capability below; no fuzzy selection was made.' }])
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Capability catalog could not be loaded.')
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
      if (!response.ok) throw new Error(await capabilityResponseError(response))
      const result = await response.json()
      const saved = result.proposal as CapabilityProposal
      setCapabilityProposals((previous) => [saved, ...previous.filter((item) => item.id !== saved.id)])
      setMessages((previous) => [...previous, { id: idFor(), role: 'assistant', content: `${result.authority_notice || 'Proposal saved for review only; no permission, job, or execution was created.'}\nProposal ID: ${saved.id}` }])
      setCapabilityDraft(null)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Capability proposal could not be saved.')
    } finally { setCapabilityBusy(false) }
  }

  async function cancelChatProposal(proposal: CapabilityProposal) {
    setCapabilityBusy(true)
    setError('')
    try {
      const response = await fetch(`/api/capabilities/proposals/${encodeURIComponent(proposal.id)}/cancel`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ revision: proposal.revision }) })
      if (!response.ok) throw new Error(await capabilityResponseError(response))
      const result = await response.json()
      setCapabilityProposals((previous) => previous.map((item) => item.id === proposal.id ? result.proposal : item))
      setMessages((previous) => [...previous, { id: idFor(), role: 'assistant', content: result.authority_notice }])
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Capability proposal could not be cancelled.')
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
    setAllowWorkspaceRead(false)
    setSending(true)
    let attemptedConversation: StoredConversation | null = null
    try {
      let conversation = activeConversation
      if (!conversation || conversation.owner_kind !== ownerKind || conversation.owner_id !== ownerId || conversation.status !== 'active') {
        const createResponse = await fetch('/api/conversations', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ owner_kind: ownerKind, owner_id: ownerId }),
        })
        if (!createResponse.ok) throw new Error(await responseError(createResponse))
        const summary = await createResponse.json() as ConversationSummary
        conversation = { ...summary, messages: [] }
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
        if (!paths.length) throw new Error('Enter the exact project-relative file paths to authorize, one per line.')
        const authorizationResponse = await fetch('/api/workspace-read/authorizations', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ owner_kind: ownerKind, owner_id: ownerId, conversation_id: conversation.id, revision: conversation.revision, paths }),
        })
        if (!authorizationResponse.ok) throw new Error(await responseError(authorizationResponse))
        const authorization = await authorizationResponse.json()
        workspaceReadAuthorizationId = authorization.authorization_id
      }
      let response: Response
      let data: any
      let intent: ReturnType<typeof inferIntent> | null = null
      if (selectedAgent) {
        response = await fetch(`/api/agents/${encodeURIComponent(selectedAgent.id)}/chat`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: content, conversation_id: conversation.id, revision: conversation.revision, cognitive_mode: cognitiveMode, ...(workspaceReadAuthorizationId ? { workspace_read_authorization_id: workspaceReadAuthorizationId } : {}) }),
        })
      } else {
        intent = localCapabilityIntent ?? inferIntent(content, cognitiveMode)
        response = await fetch('/api/chat/control', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ operation: intent.operation, message: content, conversation_id: conversation.id, revision: conversation.revision, ...(intent.operation === 'chat' ? { cognitive_mode: cognitiveMode } : {}), ...(workspaceReadAuthorizationId ? { workspace_read_authorization_id: workspaceReadAuthorizationId } : {}), ...(intent.view ? { view: intent.view } : {}) }),
        })
      }
      if (!response.ok) throw new Error(await responseError(response))
      data = await response.json()
      if (selectedAgent) {
        const provider = selectedAgent.config.provider_id || 'ollama-cloud'
        const expectedSource = provider === 'ollama-cloud' ? 'ollama' : provider
        if (data.source !== expectedSource || typeof data.assistant_message !== 'string') throw new Error('The server did not confirm a response from the selected provider.')
      }
      if (Array.isArray(data.read_events) && data.read_events.length) {
        setMessages((previous) => [...previous, { id: idFor(), role: 'assistant', content: '', readEvents: data.read_events }])
      }
      if (!data.conversation || !Array.isArray(data.conversation.messages)) throw new Error('The server did not return the saved conversation.')
      applyConversation(data.conversation as StoredConversation)
      if (data.operation === 'list_agents') {
        setAgents(Array.isArray(data.agents) ? data.agents : [])
        setInventoryWarning(data.warning_count ? `${data.warning_count} stored agent record(s) could not be loaded.` : '')
      } else if (data.operation === 'draft_agent') {
        if (!data.agent_draft || data.created !== false) throw new Error('The server returned an invalid or already-created proposal.')
        const proposedDraft = data.agent_draft as AgentConfig
        const assistantMessages = (data.conversation as StoredConversation).messages.filter((message) => message.role === 'assistant')
        const assistantMessageId = assistantMessages[assistantMessages.length - 1]?.id
        if (!assistantMessageId) throw new Error('The agent proposal has no matching assistant message.')
        setMessages((previous) => previous.map((message) => message.id === assistantMessageId
          ? { ...message, agentBuilderDraft: proposedDraft }
          : message))
      } else if (data.operation === 'job_history') {
        const assistantMessages = (data.conversation as StoredConversation).messages.filter((message) => message.role === 'assistant')
        const assistantMessageId = assistantMessages[assistantMessages.length - 1]?.id
        if (!assistantMessageId) throw new Error('The job history request has no matching assistant message.')
        setMessages((previous) => previous.map((message) => message.id === assistantMessageId
          ? { ...message, inlineJobHistory: true }
          : message))
      } else if (data.operation === 'workspace_scan') {
        const assistantMessages = (data.conversation as StoredConversation).messages.filter((message) => message.role === 'assistant')
        const assistantMessageId = assistantMessages[assistantMessages.length - 1]?.id
        if (!assistantMessageId) throw new Error('The code scan request has no matching assistant message.')
        setMessages((previous) => previous.map((message) => message.id === assistantMessageId
          ? { ...message, inlineDirectoryScan: true }
          : message))
      } else if (data.operation === 'confirm_navigation') {
        const view = data.navigation?.view as ExistingView | undefined
        if (!view || !(view in viewLabels)) throw new Error('The server did not identify a valid destination view.')
        const assistantMessages = (data.conversation as StoredConversation).messages.filter((message) => message.role === 'assistant')
        const assistantMessageId = assistantMessages[assistantMessages.length - 1]?.id
        if (!assistantMessageId) throw new Error('The navigation confirmation has no matching assistant message.')
        setMessages((previous) => previous.map((message) => message.id === assistantMessageId ? { ...message, pendingNavigation: view } : message))
      } else if (!selectedAgent && !['chat', 'help'].includes(data.operation)) {
        throw new Error('The server returned an unsupported chat operation.')
      }
      const query = new URLSearchParams({ owner_kind: ownerKind, owner_id: ownerId, status: libraryMode })
      const listResponse = await fetch(`/api/conversations?${query}`)
      if (listResponse.ok) setConversationList((await listResponse.json()).conversations || [])
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'The request could not be completed.')
      if (attemptedConversation) await openConversation(attemptedConversation.id)
    } finally {
      setSending(false)
    }
  }

  const openControlChat = () => { setSelectedAgent(null); setAllowWorkspaceRead(false); setWorkspaceReadPaths(''); setCapabilityDraft(null); setCapabilityProposals([]); setError('') }
  const selectAgent = (agent: Agent) => { setSelectedAgent(agent); setAllowWorkspaceRead(false); setWorkspaceReadPaths(''); setCapabilityDraft(null); setCapabilityProposals([]); setError('') }
  const latestDirectoryScanPromptId = [...messages].reverse().find((message) => message.inlineDirectoryScan)?.id

  return (
    <section className="control-chat" aria-label="Agent and application chat" onScrollCapture={revealScrollbarWhileScrolling}>
      {agentPanelTarget && createPortal(
        <details className="chat-agent-panel">
          <summary>Conversations and agents <span>{agentsState === 'ready' ? agents.length : '—'}</span></summary>
          <aside className="control-chat-sidebar" aria-label="Orchestrator conversations and agents">
            <section className="chat-sidebar-pane conversation-library" aria-label="Conversation library">
              {selectedAgent && <div className="conversation-library-heading"><strong>Chats · {selectedAgent.config.name}</strong></div>}
              <TabStrip<LibraryMode> label="Conversation status" value={libraryMode} onChange={setLibraryMode} items={[{ id: 'active', label: 'Recent' }, { id: 'archived', label: 'Archived' }, { id: 'deleted', label: 'Trash' }]} />
              {loadingConversation && <p className="muted-state" role="status">Opening conversation…</p>}
              {libraryError && <p className="inline-error" role="alert">{libraryError}</p>}
              {conversationList.length === 0 && !libraryError && <p className="muted-state">No {libraryMode === 'active' ? 'recent' : libraryMode} chats {selectedAgent ? 'for this agent' : 'with the orchestrator'}.</p>}
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
              ><strong>{conversation.title}</strong><span>{new Date(conversation.updated_at).toLocaleString()}</span></button>)}</div>
              <div className="conversation-library-footer"><button className="conversation-library-new" type="button" onClick={() => void startConversation()}>New</button></div>
              {conversationContextMenu && <div
                ref={contextMenuRef}
                className="conversation-context-menu"
                data-conversation-context-menu
                role="menu"
                aria-label={`Actions for ${conversationContextMenu.conversation.title}`}
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
                {conversationContextMenu.conversation.status !== 'deleted' && <button type="button" role="menuitem" onClick={() => { const { conversation } = conversationContextMenu; setConversationContextMenu(null); void manageConversation('rename', conversation) }}>Rename</button>}
                {conversationContextMenu.conversation.status === 'active' && <button type="button" role="menuitem" onClick={() => { const { conversation } = conversationContextMenu; setConversationContextMenu(null); void manageConversation('archive', conversation) }}>Archive</button>}
                {conversationContextMenu.conversation.status !== 'deleted' && <button type="button" role="menuitem" onClick={() => { const { conversation } = conversationContextMenu; setConversationContextMenu(null); void manageConversation('delete', conversation) }}>Move to trash</button>}
                {conversationContextMenu.conversation.status !== 'active' && <button type="button" role="menuitem" onClick={() => { const { conversation } = conversationContextMenu; setConversationContextMenu(null); void manageConversation('restore', conversation) }}>Restore</button>}
              </div>}
            </section>
            <section className="chat-sidebar-pane chat-sidebar-agents" aria-labelledby="chat-agents-title">
              <div className="chat-sidebar-heading"><div><h2 id="chat-agents-title">Agents</h2></div></div>
              <section className="conversation-agent-activity" aria-label="Agents participating in the selected conversation">
                <strong>Agents in this chat</strong>
                <p>{!selectedAgent && activeConversation?.owner_kind === 'assistant'
                  ? 'No agent tasks are linked to this conversation yet.'
                  : 'Select an orchestrator conversation to see its linked agent tasks.'}</p>
              </section>
              <button type="button" className={`control-agent-option ${selectedAgent === null ? 'selected' : ''}`} onClick={openControlChat}><strong>App assistant</strong></button>
              <div className="agent-list-label"><span>Available agents</span><span>{agentsState === 'ready' ? agents.length : '—'}</span></div>
              {agentsState === 'loading' && <p className="muted-state" role="status">Loading agents…</p>}
              {agentsState === 'error' && <p className="inline-error">Agent inventory unavailable.</p>}
              {agentsState === 'ready' && agents.length === 0 && <p className="muted-state">No agents created yet. Ask the app assistant to create one.</p>}
              <div className="control-agent-list">{agents.map((agent) => <button key={agent.id} type="button" className={`control-agent-option ${selectedAgent?.id === agent.id ? 'selected' : ''}`} onClick={() => selectAgent(agent)}><strong>{agent.config.name}</strong><span>{agent.config.type} · {agent.config.model_id || 'Sin modelo asignado'}</span><span>{agent.config.description}</span></button>)}</div>
              {inventoryWarning && <p className="warning-state" role="status">{inventoryWarning}</p>}
            </section>
          </aside>
        </details>,
        agentPanelTarget,
      )}
      <WindowPanel
        title={selectedAgent?.config.name ?? activeConversation?.title ?? 'How can I help?'}
        className="control-chat-main control-chat-window"
        hideTitlebar
      >
        <div className="chat-mode-header">
          <ChatTools />
          <button type="button" onClick={onOpenCognitionSettings} aria-label="Open cognition and context settings">Cognition: {cognitiveMode === 'bago5' ? 'BAGO5 experimental' : 'Baseline'} <span aria-hidden="true">↗</span></button>
        </div>
        <div className="control-chat-messages" aria-live="polite">
          {messages.length === 0 && <div className="chat-welcome"><div className="welcome-mark" aria-hidden="true">✳</div><h3>{selectedAgent ? `Chat with ${selectedAgent.config.name}` : 'Your workspace, through chat'}</h3>{!selectedAgent && <div className="prompt-suggestions"><button type="button" onClick={() => setInput('Lista mis agentes')}>List my agents</button><button type="button" onClick={() => setInput('Quiero crear un agente para…')}>Create an agent</button><button type="button" onClick={() => setInput('Abre el Decision Inspector')}>Open the Inspector</button></div>}</div>}
          {messages.map((message) => <article key={message.id} className={`control-message control-message-${message.role}`}><div className="control-message-heading"><span className="message-speaker">{message.role === 'user' ? 'You' : selectedAgent?.config.name ?? 'Assistant'}</span>{message.content && <div className="control-message-actions"><button type="button" className="message-action" onClick={() => void copyMessage(message)}>{messageCopyState?.id === message.id ? messageCopyState.state === 'copied' ? 'Copied' : 'Copy failed' : message.role === 'user' ? 'Copy message' : 'Copy response'}</button>{message.role === 'user' && message.id === latestUserMessageId && <button type="button" className="message-action" onClick={() => editLatestMessage(message)} disabled={sending || Boolean(activeConversation && activeConversation.status !== 'active')}>Edit</button>}</div>}</div>{message.content && <div className="control-message-content">{message.content}</div>}{message.agentBuilderDraft && <AgentBuilder key={message.id} inline initialAgent={message.agentBuilderDraft} onAgentCreated={() => void refreshAgents()} />}{message.inlineJobHistory && <JobHistory key={message.id} inline />}{message.inlineDirectoryScan && message.id === latestDirectoryScanPromptId && !selectedAgent && activeConversation?.owner_kind === 'assistant' && <DirectoryScanRun key={`scan-form-${message.id}`} conversationId={activeConversation.id} revision={activeConversation.revision} disabled={activeConversation.status !== 'active'} showForm onConversationUpdate={(conversation) => applyConversation(conversation as StoredConversation)} />}{message.scanOutcome && activeConversation?.owner_kind === 'assistant' && <DirectoryScanRun key={`scan-results-${message.id}`} conversationId={activeConversation.id} revision={activeConversation.revision} showForm={false} initialOutcome={message.scanOutcome} onConversationUpdate={(conversation) => applyConversation(conversation as StoredConversation)} />}{message.pendingNavigation && <section className="chat-navigation-confirmation" aria-label="Confirm screen change"><p>¿Quieres cambiar a <strong>{viewLabels[message.pendingNavigation]}</strong>?</p>{message.navigationDecision === 'accepted' ? <span role="status">Cambiando de pantalla…</span> : message.navigationDecision === 'declined' ? <span role="status">Seguimos en el chat.</span> : <div className="draft-actions"><button type="button" className="secondary-action" onClick={() => setMessages((previous) => previous.map((item) => item.id === message.id ? { ...item, navigationDecision: 'declined' } : item))}>Seguir en el chat</button><button type="button" className="primary-action" onClick={() => { setMessages((previous) => previous.map((item) => item.id === message.id ? { ...item, navigationDecision: 'accepted' } : item)); onNavigate(message.pendingNavigation as ExistingView) }}>Sí, cambiar de pantalla</button></div>}</section>}{message.cognitiveTrace && <CognitiveContextPanel trace={message.cognitiveTrace} />}{message.sources?.length ? <div className="message-sources" aria-label="Project files read"><strong>Project files read</strong><ul>{message.sources.map((source) => <li key={`${source.path}:${source.start_line}-${source.end_line}`}><code>{source.path}:{source.start_line}-{source.end_line}</code>{source.content_sha256 && <small> SHA-256 {source.content_sha256}</small>}</li>)}</ul></div> : null}{message.readEvents?.length ? <div className="message-sources" aria-label="Read-only analysis evidence"><strong>Read-only analysis evidence</strong><ul>{message.readEvents.map((event, index) => <li key={`${event.path}:${index}`}><code>{event.decision} {event.path || '(unresolved path)'} {event.reason_code ? `· ${event.reason_code}` : ''}</code>{event.kind === 'directory_code_scan' && <small>{` · ${event.files_scanned ?? 0} files · ${event.lines_scanned ?? 0} lines · ${event.finding_count ?? 0} findings${event.truncated ? ' · capped' : ''} · manifest SHA-256 ${event.manifest_sha256 ?? 'unavailable'}`}</small>}</li>)}</ul></div> : null}{message.trace && <div className="message-trace" aria-label="Execution trace evidence"><span>Trace {message.trace.state}</span><code>Local: {message.trace.localId}</code>{message.trace.jaegerId && <code>Jaeger: {message.trace.jaegerId}</code>}{message.trace.jaegerUrl && <a href={message.trace.jaegerUrl} target="_blank" rel="noreferrer">Open in Jaeger</a>}</div>}</article>)}
          {capabilityDraft && <section className="capability-chat-card" aria-labelledby="capability-draft-title"><div className="draft-heading"><div><p className="section-eyebrow">Proposal review</p><h3 id="capability-draft-title">Review before saving</h3></div><span className="draft-status">Not saved</span></div><label>Capability<select value={capabilityDraft.capabilityId} onChange={(event) => setCapabilityDraft({ ...capabilityDraft, capabilityId: event.target.value })} disabled={capabilityBusy}><option value="">Choose a catalog entry</option>{capabilityDraft.capabilities.map((item) => <option key={item.id} value={item.id}>{item.id} · {item.status} · {item.effect}</option>)}</select></label>{capabilityDraft.capabilityId && <p className="capability-chat-selected">{capabilityDraft.capabilities.find((item) => item.id === capabilityDraft.capabilityId)?.summary}</p>}<label>Request summary<input value={capabilityDraft.summary} maxLength={500} onChange={(event) => setCapabilityDraft({ ...capabilityDraft, summary: event.target.value })} disabled={capabilityBusy} /></label><label>Requested scope<textarea value={capabilityDraft.requestedScope} maxLength={1000} rows={3} onChange={(event) => setCapabilityDraft({ ...capabilityDraft, requestedScope: event.target.value })} disabled={capabilityBusy} /></label><div className="draft-actions"><button type="button" className="secondary-action" onClick={() => setCapabilityDraft(null)} disabled={capabilityBusy}>Discard</button><button type="button" className="primary-action" onClick={() => void saveCapabilityProposal()} disabled={capabilityBusy || !capabilityDraft.capabilityId || !capabilityDraft.summary.trim() || !capabilityDraft.requestedScope.trim()}>{capabilityBusy ? 'Saving…' : 'Save proposal'}</button></div></section>}
          {capabilityProposals.map((proposal) => <article className="capability-chat-saved" key={proposal.id}><div><strong>{proposal.capability_id}</strong><span>{proposal.status} · revision {proposal.revision}</span></div><p>{proposal.summary}</p><p><strong>Requested scope:</strong> {proposal.requested_scope}</p><code>{proposal.id}</code>{proposal.status === 'PENDING_REVIEW' && <button type="button" className="secondary-action" onClick={() => void cancelChatProposal(proposal)} disabled={capabilityBusy}>Cancel proposal</button>}</article>)}
          {error && <p className="chat-error" role="alert">{error}{error.toLowerCase().includes('ollama') || error.toLowerCase().includes('provider') ? <button type="button" onClick={onOpenProviderSettings}>Open provider settings</button> : null}</p>}
          {sending && <p className="muted-state" role="status">Esperando la respuesta del proveedor…</p>}
          <div ref={messagesEndRef} />
        </div>
        <form className="control-chat-composer" onSubmit={(event) => void sendMessage(event)}><label className="visually-hidden" htmlFor="control-chat-input">Message the assistant or selected agent</label><div className="chat-composer-input"><textarea ref={composerRef} id="control-chat-input" rows={2} value={input} onChange={(event) => setInput(event.target.value)} onKeyDown={(event) => {
          if (event.key !== 'Enter' || event.shiftKey || event.nativeEvent.isComposing || event.repeat) return
          event.preventDefault()
          void sendMessage()
        }} placeholder={activeConversation?.status && activeConversation.status !== 'active' ? 'Restore or start a new conversation.' : selectedAgent ? `Message ${selectedAgent.config.name}.` : 'Message the assistant…'} disabled={sending || Boolean(activeConversation && activeConversation.status !== 'active')} />
            <button className="primary-action" type="submit" disabled={sending || !input.trim() || Boolean(activeConversation && activeConversation.status !== 'active')}>{sending ? 'Sending.' : 'Send'}</button>
          </div>
          <div className="chat-composer-actions">
            <label className="workspace-read-toggle"><input type="checkbox" checked={allowWorkspaceRead} onChange={(event) => setAllowWorkspaceRead(event.target.checked)} disabled={sending || Boolean(activeConversation && activeConversation.status !== 'active')} /><span>Allow project file reads</span></label>
            {!selectedAgent && <label className="chat-provider-picker"><span className="visually-hidden">Modelo del orquestador</span><select aria-label="Modelo del orquestador" value={chatProviderSelection ? `${chatProviderSelection.provider_id}|${chatProviderSelection.model_id}` : ''} onChange={event => void changeChatProvider(event.target.value)} disabled={savingChatProvider || chatProviders.length === 0}><option value="" disabled>{chatProviders.length ? 'Selecciona un modelo' : 'Configura un proveedor'}</option>{chatProviders.map(provider => <option key={`${provider.provider_id}|${provider.model_id}`} value={`${provider.provider_id}|${provider.model_id}`}>{provider.label} · {provider.display_name ?? provider.model_id}{provider.state === 'configured_unverified' ? ' · sin verificar' : ''}</option>)}</select></label>}
          </div>
          {allowWorkspaceRead && <label className="workspace-read-paths">Project-relative paths<textarea rows={3} value={workspaceReadPaths} onChange={(event) => setWorkspaceReadPaths(event.target.value)} placeholder={'src/api/server.py\nsrc/agent_tools/workspace_read.py'} disabled={sending} /></label>}
        </form>
        <div className="chat-agent-panel-slot" ref={setAgentPanelTarget} />
      </WindowPanel>
    </section>
  )
}
