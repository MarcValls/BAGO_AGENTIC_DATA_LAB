import { FormEvent, useEffect, useRef, useState } from 'react'
import { Capability, CapabilityProposal, capabilityResponseError } from './CapabilityManager'
import './AgentChat.css'

type AgentConfig = {
  name: string
  description: string
  type: 'rag' | 'tool' | 'multi-agent'
  system_prompt: string
  provider_id?: 'ollama-cloud' | null
  model_id?: string | null
  tools: string[]
  retrieval_config?: { mode: 'hybrid' | 'semantic' | 'lexical'; top_k: number } | null
  sandbox_profile?: string | null
}

type Agent = { id: string; config: AgentConfig; created_at: string }
type ProviderModel = { provider_id: string; model_id: string; display_name: string; source: string; availability_confidence: string }
type MessageTrace = { localId: string; state: string; jaegerId?: string; jaegerUrl?: string }
type WorkspaceSource = { path: string; start_line: number; end_line: number }
type Message = { id: string; role: 'user' | 'assistant'; content: string; trace?: MessageTrace; sources?: WorkspaceSource[] }
type ConversationSummary = { id: string; owner_kind: 'assistant' | 'agent'; owner_id: string; title: string; status: 'active' | 'archived' | 'deleted'; updated_at: string; revision: number }
type StoredConversation = ConversationSummary & { messages: Array<{ id: string; role: 'user' | 'assistant'; content: string; references?: { trace?: { trace_id?: string; trace_state?: string; jaeger_trace_id?: string; jaeger_url?: string }; sources?: WorkspaceSource[] } }> }
type LibraryMode = 'active' | 'archived' | 'deleted'
type ControlOperation = 'chat' | 'help' | 'list_agents' | 'draft_agent' | 'navigate' | 'list_capabilities' | 'propose_capability'
type ExistingView = 'inspector' | 'builder' | 'chat' | 'runner' | 'control' | 'jobs' | 'traces' | 'summary' | 'retrieval' | 'authorization' | 'evaluation' | 'evaluation_lab' | 'provider_settings' | 'capabilities'
type CapabilityDraft = { capabilities: Capability[]; capabilityId: string; summary: string; requestedScope: string; conversationId: string | null }

interface AgentChatProps {
  onNavigate: (view: ExistingView) => void
  onOpenProviderSettings: () => void
}

const idFor = () => `${Date.now()}-${Math.random().toString(16).slice(2)}`

async function responseError(response: Response): Promise<string> {
  try {
    const body = await response.json()
    const detail = body?.detail
    if (typeof detail === 'string') return detail
    if (typeof detail?.message === 'string') return detail.message
  } catch { /* keep a safe generic error */ }
  return `Request failed (${response.status}).`
}

function inferIntent(message: string): { operation: ControlOperation; view?: ExistingView } {
  const text = message.toLocaleLowerCase()
  const capabilityIdMentioned = /\b(?:workspace\.read_text|mcp\.execute|sandbox\.execute|agent\.run)\b/.test(text)
  if (/\b(capabilities|capability manager|gestor de capacidades|capacidades)\b/.test(text) && /\b(abre|abrir|open|show|muestra|ir a|ve a|navega|gestiona|manager|gestor|vista)\b/.test(text)) return { operation: 'navigate', view: 'capabilities' }
  if (/\b(propuesta|proponer|propose|proposal)\b/.test(text) && (/\b(capacidad|capability|acceso|access|habilitar|enable|registrar|register)\b/.test(text) || capabilityIdMentioned)) return { operation: 'propose_capability' }
  if (/\b(capacidades|capability catalog|capabilities|estado de (?:la )?capacidad|list(?:ar)? capabilities)\b/.test(text) || (capabilityIdMentioned && /\b(estado|status|lista|listar|mostrar|show|describe|qu[eé])\b/.test(text))) return { operation: 'list_capabilities' }
  if (/^\s*(hola|buenas|hello|hi|hey)[!.\s]*$/.test(text) || /\b(qu[eé] puedes hacer|what can you do|capacidades del asistente|assistant capabilities)\b/.test(text) || /\b(puedes|can you|could you)\s+(crear|create|diseñar|design)\s+(un\s+|a\s+)?agentes?\s*[?!.]*$/.test(text) || /\b(no puedes|cannot|can't)\s+(crear|create)\s+agentes?\b/.test(text)) {
    return { operation: 'help' }
  }
  if (/\b(lista|listar|muestra|mostrar|qué|cu[aá]les)\b.*\b(agentes|agente)\b/.test(text) || /\b(agentes|agente)\b.*\b(lista|listar|hay|tengo)\b/.test(text)) {
    return { operation: 'list_agents' }
  }
  if (/\b(crea|crear|diseña|diseñar|configura|configurar)\b.*\bagente\b/.test(text) || /\b(necesito|quiero)\s+(un\s+)?agente\b/.test(text)) {
    return { operation: 'draft_agent' }
  }
  const destinations: Array<[RegExp, ExistingView]> = [
    [/\b(agent evaluation lab|evaluation lab|laboratorio de evaluaci[oó]n de agentes|laboratorio de evaluaci[oó]n)\b/, 'evaluation_lab'],
    [/\b(inspector|decisiones)\b/, 'inspector'],
    [/\b(builder|creaci[oó]n de agentes)\b/, 'builder'],
    [/\b(chat)\b/, 'chat'],
    [/\b(runner|ejecutor)\b/, 'runner'],
    [/\b(control)\b/, 'control'],
    [/\b(jobs?|trabajos|historial)\b/, 'jobs'],
    [/\b(traces?|trazas)\b/, 'traces'],
    [/\b(summary|resumen)\b/, 'summary'],
    [/\b(retrieval|ontology|recuperaci[oó]n|ontolog[ií]a)\b/, 'retrieval'],
    [/\b(authorization|autorizaci[oó]n)\b/, 'authorization'],
    [/\b(evaluation|evaluaci[oó]n)\b/, 'evaluation'],
    [/\b(provider|proveedor|ollama)\b/, 'provider_settings'],
  ]
  if (/\b(abre|abrir|ve a|ir a|navega|muestra la vista|ll[eé]vame|ll[eé]vame a|entra a|open|go to|show me)\b/.test(text)) {
    const destination = destinations.find(([pattern]) => pattern.test(text))
    if (destination) {
      return { operation: 'navigate', view: destination[1] }
    }
  }
  return { operation: 'chat' }
}

export default function AgentChat({ onNavigate, onOpenProviderSettings }: AgentChatProps) {
  const [agents, setAgents] = useState<Agent[]>([])
  const [agentsState, setAgentsState] = useState<'loading' | 'ready' | 'error'>('loading')
  const [inventoryWarning, setInventoryWarning] = useState('')
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [activeConversation, setActiveConversation] = useState<StoredConversation | null>(null)
  const [conversationList, setConversationList] = useState<ConversationSummary[]>([])
  const [libraryMode, setLibraryMode] = useState<LibraryMode>('active')
  const [libraryError, setLibraryError] = useState('')
  const [loadingConversation, setLoadingConversation] = useState(false)
  const [input, setInput] = useState('')
  const [allowWorkspaceRead, setAllowWorkspaceRead] = useState(false)
  const [sending, setSending] = useState(false)
  const [error, setError] = useState('')
  const [draft, setDraft] = useState<AgentConfig | null>(null)
  const [draftModels, setDraftModels] = useState<ProviderModel[]>([])
  const [loadingDraftModels, setLoadingDraftModels] = useState(false)
  const [draftModelsError, setDraftModelsError] = useState('')
  const [creatingDraft, setCreatingDraft] = useState(false)
  const [createdNotice, setCreatedNotice] = useState('')
  const [capabilityDraft, setCapabilityDraft] = useState<CapabilityDraft | null>(null)
  const [capabilityProposals, setCapabilityProposals] = useState<CapabilityProposal[]>([])
  const [capabilityBusy, setCapabilityBusy] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const refreshAgents = async () => {
    setAgentsState('loading')
    try {
      const response = await fetch('/api/agents/list')
      if (!response.ok) throw new Error(await responseError(response))
      const data = await response.json()
      setAgents(Array.isArray(data.agents) ? data.agents : [])
      setInventoryWarning(data.warning_count ? `${data.warning_count} stored agent record(s) could not be loaded.` : '')
      setAgentsState('ready')
    } catch (cause) {
      setAgentsState('error')
      setError(cause instanceof Error ? cause.message : 'Agent inventory could not be loaded.')
    }
  }

  const ownerKind = selectedAgent ? 'agent' : 'assistant'
  const ownerId = selectedAgent?.id ?? 'app-assistant'

  const applyConversation = (conversation: StoredConversation) => {
    setActiveConversation(conversation)
    setMessages(conversation.messages.map((message) => {
      const trace = message.references?.trace
      return {
        id: message.id,
        role: message.role,
        content: message.content,
        ...(trace?.trace_id ? { trace: { localId: trace.trace_id, state: trace.trace_state || 'unknown', jaegerId: trace.jaeger_trace_id, jaegerUrl: trace.jaeger_url } } : {}),
        ...(message.references?.sources?.length ? { sources: message.references.sources } : {}),
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

  useEffect(() => { void refreshAgents() }, [])
  useEffect(() => { void refreshConversationList() }, [ownerKind, ownerId, libraryMode])
  useEffect(() => { void refreshConversationProposals(activeConversation?.id ?? null) }, [activeConversation?.id])
  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])

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

  const manageConversation = async (action: 'rename' | 'archive' | 'delete' | 'restore') => {
    if (!activeConversation) return
    const title = action === 'rename' ? window.prompt('Conversation title', activeConversation.title) : null
    if (action === 'rename' && title === null) return
    const route = action === 'rename' ? `/api/conversations/${activeConversation.id}` : `/api/conversations/${activeConversation.id}/${action}`
    const method = action === 'rename' ? 'PATCH' : 'POST'
    const body = action === 'rename' ? { revision: activeConversation.revision, title } : { revision: activeConversation.revision }
    try {
      const response = await fetch(route, { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
      if (!response.ok) throw new Error(await responseError(response))
      if (action === 'delete') {
        setActiveConversation(null); setMessages([]); setLibraryMode('deleted')
      } else {
        applyConversation(await response.json() as StoredConversation)
        if (action === 'archive') setLibraryMode('archived')
        if (action === 'restore') setLibraryMode('active')
      }
      await refreshConversationList()
    } catch (cause) {
      setLibraryError(cause instanceof Error ? cause.message : 'Conversation could not be updated.')
      if (cause instanceof Error && cause.message.includes('changed elsewhere')) await refreshConversationList()
    }
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
    setCreatedNotice('')
    setDraft(null)
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
      const localCapabilityIntent = !selectedAgent ? inferIntent(content) : null
      if (localCapabilityIntent?.operation === 'list_capabilities' || localCapabilityIntent?.operation === 'propose_capability') {
        await beginCapabilityRequest(content, localCapabilityIntent.operation, conversation.id)
        return
      }
      if (localCapabilityIntent?.operation === 'navigate' && localCapabilityIntent.view === 'capabilities') {
        setMessages((previous) => [...previous, { id: idFor(), role: 'user', content }])
        onNavigate('capabilities')
        return
      }
      if (localCapabilityIntent?.operation === 'navigate' && localCapabilityIntent.view === 'evaluation_lab') {
        setMessages((previous) => [...previous, { id: idFor(), role: 'user', content }])
        onNavigate('evaluation_lab')
        return
      }
      setMessages((previous) => [...previous, { id: idFor(), role: 'user', content }])
      let response: Response
      let data: any
      let intent: ReturnType<typeof inferIntent> | null = null
      if (selectedAgent) {
        response = await fetch(`/api/agents/${encodeURIComponent(selectedAgent.id)}/chat`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: content, conversation_id: conversation.id, revision: conversation.revision, allow_workspace_read: readFilesForThisMessage }),
        })
      } else {
        intent = localCapabilityIntent ?? inferIntent(content)
        response = await fetch('/api/chat/control', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ operation: intent.operation, message: content, conversation_id: conversation.id, revision: conversation.revision, allow_workspace_read: readFilesForThisMessage, ...(intent.view ? { view: intent.view } : {}) }),
        })
      }
      if (!response.ok) throw new Error(await responseError(response))
      data = await response.json()
      if (selectedAgent && (data.source !== 'ollama' || typeof data.assistant_message !== 'string')) throw new Error('The server did not confirm a live Ollama response.')
      if (!data.conversation || !Array.isArray(data.conversation.messages)) throw new Error('The server did not return the saved conversation.')
      applyConversation(data.conversation as StoredConversation)
      if (data.operation === 'list_agents') {
        setAgents(Array.isArray(data.agents) ? data.agents : [])
        setInventoryWarning(data.warning_count ? `${data.warning_count} stored agent record(s) could not be loaded.` : '')
      } else if (data.operation === 'draft_agent') {
        if (!data.agent_draft || data.created !== false) throw new Error('The server returned an invalid or already-created proposal.')
        const proposedDraft = data.agent_draft as AgentConfig
        setDraft(proposedDraft)
        setDraftModels([])
        setDraftModelsError('')
        setLoadingDraftModels(true)
        try {
          const modelsResponse = await fetch('/api/providers/ollama/models')
          if (!modelsResponse.ok) throw new Error(await responseError(modelsResponse))
          const modelsData = await modelsResponse.json()
          const usableModels = Array.isArray(modelsData.models)
            ? modelsData.models.filter((model: ProviderModel) => model.provider_id === 'ollama-cloud' && model.availability_confidence === 'listed' && typeof model.model_id === 'string')
            : []
          setDraftModels(usableModels)
          if (!usableModels.some((model: ProviderModel) => model.model_id === proposedDraft.model_id)) {
            setDraft((current) => current ? { ...current, model_id: usableModels[0]?.model_id ?? '' } : current)
          }
          if (!usableModels.length) setDraftModelsError('No usable Ollama models were confirmed. Configure the provider, then request a new proposal.')
        } catch (modelError) {
          setDraftModelsError(modelError instanceof Error ? modelError.message : 'Could not load confirmed Ollama models.')
        } finally {
          setLoadingDraftModels(false)
        }
      } else if (data.operation === 'navigate') {
        const view = data.navigation?.view as ExistingView | undefined
        if (!view) throw new Error('The server did not identify a destination view.')
        onNavigate(view)
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

  const createDraft = async () => {
    if (!draft || creatingDraft) return
    if (draft.provider_id !== 'ollama-cloud' || !draft.model_id?.trim() || !draftModels.some((model) => model.model_id === draft.model_id)) {
      setError('Choose a model confirmed by the configured Ollama provider before creating this agent.')
      return
    }
    const createPayload = Object.fromEntries(Object.entries(draft).filter(([, value]) => value !== null && value !== undefined))
    setCreatingDraft(true)
    setError('')
    try {
      const response = await fetch('/api/agents/create', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(createPayload),
      })
      if (!response.ok) throw new Error(await responseError(response))
      const created = await response.json() as Agent
      setDraft(null)
      setCreatedNotice(`${created.config.name} was created and added to your agent list.`)
      await refreshAgents()
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Agent creation failed.')
    } finally {
      setCreatingDraft(false)
    }
  }

  const cancelDraft = () => {
    setDraft(null)
    setDraftModels([])
    setDraftModelsError('')
  }

  const openControlChat = () => { setSelectedAgent(null); setAllowWorkspaceRead(false); setDraft(null); setDraftModels([]); setDraftModelsError(''); setCapabilityDraft(null); setCapabilityProposals([]); setError('') }
  const selectAgent = (agent: Agent) => { setSelectedAgent(agent); setAllowWorkspaceRead(false); setDraft(null); setDraftModels([]); setDraftModelsError(''); setCapabilityDraft(null); setCapabilityProposals([]); setError('') }

  return (
    <section className="control-chat" aria-label="Agent and application chat">
      <aside className="control-chat-sidebar" aria-label="Agent inventory">
        <div className="chat-sidebar-heading"><div><p className="section-eyebrow">Workspace</p><h2>Agents</h2></div><button type="button" className="icon-button" onClick={() => void refreshAgents()} aria-label="Refresh agent list" title="Refresh agent list">↻</button></div>
        <button type="button" className={`control-agent-option ${selectedAgent === null ? 'selected' : ''}`} onClick={openControlChat}>
          <strong>App assistant</strong><span>Chat, list agents, create drafts, navigate</span>
        </button>
        <div className="agent-list-label"><span>Your application agents</span><span>{agentsState === 'ready' ? agents.length : '—'}</span></div>
        {agentsState === 'loading' && <p className="muted-state" role="status">Loading agents…</p>}
        {agentsState === 'error' && <p className="inline-error">Agent inventory unavailable.</p>}
        {agentsState === 'ready' && agents.length === 0 && <p className="muted-state">No agents created yet. Ask the app assistant to create one.</p>}
        <div className="control-agent-list">
          {agents.map((agent) => <button key={agent.id} type="button" className={`control-agent-option ${selectedAgent?.id === agent.id ? 'selected' : ''}`} onClick={() => selectAgent(agent)}>
            <strong>{agent.config.name}</strong><span>{agent.config.type} · {agent.config.model_id || 'Sin modelo asignado'}</span><span>{agent.config.description}</span>
          </button>)}
        </div>
        {inventoryWarning && <p className="warning-state" role="status">{inventoryWarning}</p>}
        <section className="conversation-library" aria-label="Conversation library">
          <div className="conversation-library-heading"><strong>Chats</strong><button type="button" onClick={() => void startConversation()}>New</button></div>
          <div className="conversation-library-tabs" role="group" aria-label="Conversation status">
            {(['active', 'archived', 'deleted'] as LibraryMode[]).map((mode) => <button key={mode} type="button" className={libraryMode === mode ? 'selected' : ''} onClick={() => setLibraryMode(mode)}>{mode === 'active' ? 'Recent' : mode === 'archived' ? 'Archived' : 'Trash'}</button>)}
          </div>
          {loadingConversation && <p className="muted-state" role="status">Opening conversation.</p>}
          {libraryError && <p className="inline-error" role="alert">{libraryError}</p>}
          {conversationList.length === 0 && !libraryError && <p className="muted-state">No {libraryMode === 'active' ? 'recent' : libraryMode} chats for this owner.</p>}
          <div className="conversation-library-list">
            {conversationList.map((conversation) => <button key={conversation.id} type="button" className={`conversation-library-item ${activeConversation?.id === conversation.id ? 'selected' : ''}`} onClick={() => conversation.status === 'deleted' ? (setActiveConversation({ ...conversation, messages: [] }), setMessages([])) : void openConversation(conversation.id)}>
              <strong>{conversation.title}</strong><span>{new Date(conversation.updated_at).toLocaleString()}</span>
            </button>)}
          </div>
          {activeConversation && <div className="conversation-library-actions">
            {activeConversation.status !== 'deleted' && <button type="button" onClick={() => void manageConversation('rename')}>Rename</button>}
            {activeConversation.status === 'active' && <button type="button" onClick={() => void manageConversation('archive')}>Archive</button>}
            {activeConversation.status !== 'deleted' && <button type="button" onClick={() => void manageConversation('delete')}>Move to trash</button>}
            {activeConversation.status !== 'active' && <button type="button" onClick={() => void manageConversation('restore')}>Restore</button>}
          </div>}
        </section>
        <button className="provider-shortcut" type="button" onClick={onOpenProviderSettings}>Configure Ollama provider <span aria-hidden="true">→</span></button>
      </aside>

      <div className="control-chat-main">
        <header className="control-chat-header"><div><p className="section-eyebrow">{selectedAgent ? 'Agent conversation' : 'Control plane'}</p><h2>{selectedAgent?.config.name ?? 'How can I help?'}</h2><p>{activeConversation?.title || (selectedAgent ? selectedAgent.config.description : 'Ask about your agents, propose a new agent, or open a view.')}</p></div><span className="chat-mode-badge">{selectedAgent ? selectedAgent.config.model_id || 'Sin modelo asignado' : 'Ollama assistant'}</span></header>
        <div className="control-chat-messages" aria-live="polite">
          {messages.length === 0 && <div className="chat-welcome"><div className="welcome-mark" aria-hidden="true">✳</div><h3>{selectedAgent ? `Chat with ${selectedAgent.config.name}` : 'Your workspace, through chat'}</h3><p>{selectedAgent ? 'Messages are sent to this agent through the configured Ollama provider.' : 'The assistant can list your application agents, draft one for your review, and navigate to supported views.'}</p>{!selectedAgent && <div className="prompt-suggestions"><button type="button" onClick={() => setInput('Lista mis agentes')}>List my agents</button><button type="button" onClick={() => setInput('Quiero crear un agente para…')}>Create an agent</button><button type="button" onClick={() => setInput('Abre el Decision Inspector')}>Open the Inspector</button></div>}</div>}
          {messages.map((message) => <article key={message.id} className={`control-message control-message-${message.role}`}><span className="message-speaker">{message.role === 'user' ? 'You' : selectedAgent?.config.name ?? 'Assistant'}</span><div className="control-message-content">{message.content}</div>{message.sources?.length ? <div className="message-sources" aria-label="Project files read"><strong>Project files read</strong><ul>{message.sources.map((source) => <li key={`${source.path}:${source.start_line}-${source.end_line}`}><code>{source.path}:{source.start_line}-{source.end_line}</code></li>)}</ul></div> : null}{message.trace && <div className="message-trace" aria-label="Execution trace evidence"><span>Trace {message.trace.state}</span><code>Local: {message.trace.localId}</code>{message.trace.jaegerId && <code>Jaeger: {message.trace.jaegerId}</code>}{message.trace.jaegerUrl && <a href={message.trace.jaegerUrl} target="_blank" rel="noreferrer">Open in Jaeger</a>}</div>}</article>)}
          {capabilityDraft && <section className="capability-chat-card" aria-labelledby="capability-draft-title"><div className="draft-heading"><div><p className="section-eyebrow">Proposal review</p><h3 id="capability-draft-title">Review before saving</h3></div><span className="draft-status">Not saved</span></div><label>Exact backend capability<select value={capabilityDraft.capabilityId} onChange={(event) => setCapabilityDraft({ ...capabilityDraft, capabilityId: event.target.value })} disabled={capabilityBusy}><option value="">Choose a catalog entry</option>{capabilityDraft.capabilities.map((item) => <option key={item.id} value={item.id}>{item.id} · {item.status} · {item.effect}</option>)}</select></label>{capabilityDraft.capabilityId && <p className="capability-chat-selected">{capabilityDraft.capabilities.find((item) => item.id === capabilityDraft.capabilityId)?.summary}</p>}<label>Request summary<input value={capabilityDraft.summary} maxLength={500} onChange={(event) => setCapabilityDraft({ ...capabilityDraft, summary: event.target.value })} disabled={capabilityBusy} /></label><label>Requested scope<textarea value={capabilityDraft.requestedScope} maxLength={1000} rows={3} placeholder="Describe the exact scope to review" onChange={(event) => setCapabilityDraft({ ...capabilityDraft, requestedScope: event.target.value })} disabled={capabilityBusy} /></label><p>This only saves a review proposal. It does not authorize a capability or run a job.</p><div className="draft-actions"><button type="button" className="secondary-action" onClick={() => setCapabilityDraft(null)} disabled={capabilityBusy}>Discard</button><button type="button" className="primary-action" onClick={() => void saveCapabilityProposal()} disabled={capabilityBusy || !capabilityDraft.capabilityId || !capabilityDraft.summary.trim() || !capabilityDraft.requestedScope.trim()}>{capabilityBusy ? 'Saving…' : 'Save proposal'}</button></div></section>}
          {capabilityProposals.map((proposal) => <article className="capability-chat-saved" key={proposal.id}><div><strong>{proposal.capability_id}</strong><span>{proposal.status} · revision {proposal.revision}</span></div><p>{proposal.summary}</p><p><strong>Requested scope:</strong> {proposal.requested_scope}</p><code>{proposal.id}</code>{proposal.status === 'PENDING_REVIEW' && <button type="button" className="secondary-action" onClick={() => void cancelChatProposal(proposal)} disabled={capabilityBusy}>Cancel proposal</button>}</article>)}
          {draft && <section className="agent-draft-card" aria-labelledby="draft-title"><div className="draft-heading"><div><p className="section-eyebrow">AI-assisted draft</p><h3 id="draft-title">Review and edit before saving</h3></div><span className="draft-status">Not created</span></div><div className="draft-fields"><label>Name<input value={draft.name} maxLength={120} onChange={(event) => setDraft({ ...draft, name: event.target.value })} disabled={creatingDraft} /></label><label>Description<textarea value={draft.description} maxLength={1000} rows={2} onChange={(event) => setDraft({ ...draft, description: event.target.value })} disabled={creatingDraft} /></label><label>Agent type<select value={draft.type} onChange={(event) => setDraft({ ...draft, type: event.target.value as AgentConfig['type'] })} disabled={creatingDraft}><option value="rag">RAG</option><option value="tool">Tool</option><option value="multi-agent">Multi-agent</option></select></label><label>Confirmed Ollama model<select value={draft.model_id ?? ''} onChange={(event) => setDraft({ ...draft, provider_id: 'ollama-cloud', model_id: event.target.value })} disabled={creatingDraft || loadingDraftModels || draftModels.length === 0}><option value="">{loadingDraftModels ? 'Loading models…' : 'Select a confirmed model'}</option>{draftModels.map((model) => <option key={model.model_id} value={model.model_id}>{model.display_name} · {model.source}</option>)}</select></label><label className="draft-prompt-field">System prompt<textarea value={draft.system_prompt} maxLength={12000} rows={6} onChange={(event) => setDraft({ ...draft, system_prompt: event.target.value })} disabled={creatingDraft} /></label></div><p className="draft-model-note" role={draftModelsError ? 'alert' : 'status'}>{draftModelsError || (loadingDraftModels ? 'Checking models from the configured backend…' : 'Model choices come from the configured provider and are not inferred from a public catalog.')}{draftModelsError && <button type="button" onClick={onOpenProviderSettings}>Open provider settings</button>}</p><details className="draft-advanced"><summary>Advanced details</summary><p><strong>Tools:</strong> {draft.tools.length ? draft.tools.join(', ') : 'No tools selected'}</p><p>Creating this profile does not grant tool execution or app-control permissions.</p></details><div className="draft-actions"><button type="button" className="secondary-action" onClick={cancelDraft} disabled={creatingDraft}>Cancel proposal</button><button type="button" className="primary-action" onClick={() => void createDraft()} disabled={creatingDraft || loadingDraftModels || draftModels.length === 0 || !draft.name.trim() || !draft.description.trim() || !draft.system_prompt.trim() || draft.provider_id !== 'ollama-cloud' || !draft.model_id?.trim() || !draftModels.some((model) => model.model_id === draft.model_id)}>{creatingDraft ? 'Creating…' : 'Create agent'}</button></div></section>}
          {createdNotice && <p className="success-state" role="status">{createdNotice}</p>}
          {error && <p className="chat-error" role="alert">{error}{error.toLowerCase().includes('ollama') || error.toLowerCase().includes('provider') ? <button type="button" onClick={onOpenProviderSettings}>Open provider settings</button> : null}</p>}
          {sending && <p className="muted-state" role="status">Waiting for Ollama…</p>}
          <div ref={messagesEndRef} />
        </div>
        <form className="control-chat-composer" onSubmit={(event) => void sendMessage(event)}><label className="visually-hidden" htmlFor="control-chat-input">Message the assistant or selected agent</label><textarea id="control-chat-input" rows={2} value={input} onChange={(event) => setInput(event.target.value)} placeholder={activeConversation?.status && activeConversation.status !== 'active' ? 'Restore this conversation or start a new one to continue.' : selectedAgent ? `Message ${selectedAgent.config.name}.` : 'Ask a question, list agents, create an agent, or open a view.'} disabled={sending || Boolean(activeConversation && activeConversation.status !== 'active')} /><div className="chat-composer-actions"><label className="workspace-read-toggle"><input type="checkbox" checked={allowWorkspaceRead} onChange={(event) => setAllowWorkspaceRead(event.target.checked)} disabled={sending || Boolean(activeConversation && activeConversation.status !== 'active')} /><span>Allow read-only project files for this message <small>Selected text is sent to Ollama Cloud</small></span></label><button className="primary-action" type="submit" disabled={sending || !input.trim() || Boolean(activeConversation && activeConversation.status !== 'active')}>{sending ? 'Sending.' : 'Send'}</button></div><p>When enabled, chat can read bounded text files in this project and shows the lines it used. It cannot write files or run jobs.</p></form>
      </div>
    </section>
  )
}
