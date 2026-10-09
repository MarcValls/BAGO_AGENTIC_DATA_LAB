import { FormEvent, useEffect, useRef, useState } from 'react'
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
type ControlOperation = 'chat' | 'list_agents' | 'draft_agent' | 'navigate'
type ExistingView = 'inspector' | 'builder' | 'chat' | 'runner' | 'control' | 'jobs' | 'traces' | 'summary' | 'retrieval' | 'authorization' | 'evaluation' | 'provider_settings'

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

function inferIntent(message: string): { operation: ControlOperation | 'local_navigate'; view?: ExistingView } {
  const text = message.toLocaleLowerCase()
  if (/\b(lista|listar|muestra|mostrar|qué|cu[aá]les)\b.*\b(agentes|agente)\b/.test(text) || /\b(agentes|agente)\b.*\b(lista|listar|hay|tengo)\b/.test(text)) {
    return { operation: 'list_agents' }
  }
  if (/\b(crea|crear|diseña|diseñar|configura|configurar)\b.*\bagente\b/.test(text) || /\b(necesito|quiero)\s+(un\s+)?agente\b/.test(text)) {
    return { operation: 'draft_agent' }
  }
  const destinations: Array<[RegExp, ExistingView]> = [
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
      const backendViews: ExistingView[] = ['inspector', 'builder', 'chat', 'runner', 'control', 'jobs', 'traces']
      return { operation: backendViews.includes(destination[1]) ? 'navigate' : 'local_navigate', view: destination[1] }
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

  useEffect(() => { void refreshAgents() }, [])
  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])

  const addAssistantMessage = (content: string, trace?: MessageTrace, sources?: WorkspaceSource[]) => {
    setMessages((previous) => [...previous, { id: idFor(), role: 'assistant', content, ...(trace ? { trace } : {}), ...(sources?.length ? { sources } : {}) }])
  }

  const sendMessage = async (event?: FormEvent) => {
    event?.preventDefault()
    const content = input.trim()
    if (!content || sending) return
    setInput('')
    setError('')
    setCreatedNotice('')
    setDraft(null)
    const readFilesForThisMessage = allowWorkspaceRead
    setAllowWorkspaceRead(false)
    const userMessage = { id: idFor(), role: 'user' as const, content }
    setMessages((previous) => [...previous, userMessage])
    setSending(true)
    try {
      if (selectedAgent) {
        const history = [...messages, userMessage]
          .filter((message) => message.id !== userMessage.id)
          .slice(-30)
          .map(({ role, content: text }) => ({ role, content: text }))
        const response = await fetch(`/api/agents/${encodeURIComponent(selectedAgent.id)}/chat`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: content, conversation_history: history, allow_workspace_read: readFilesForThisMessage }),
        })
        if (!response.ok) throw new Error(await responseError(response))
        const data = await response.json()
        if (data.source !== 'ollama' || typeof data.assistant_message !== 'string') throw new Error('The server did not confirm a live Ollama response.')
        const localId = response.headers.get('X-Bago-Trace-Id')
        addAssistantMessage(data.assistant_message, localId ? {
          localId,
          state: response.headers.get('X-Bago-Trace-State') || 'unknown',
          jaegerId: response.headers.get('X-Bago-Jaeger-Trace-Id') || undefined,
          jaegerUrl: response.headers.get('X-Bago-Jaeger-Trace-Url') || undefined,
        } : undefined, Array.isArray(data.sources) ? data.sources : undefined)
      } else {
        const intent = inferIntent(content)
        if (intent.operation === 'local_navigate' && intent.view) {
          addAssistantMessage(`Opening ${intent.view.replace('_', ' ')}.`)
          onNavigate(intent.view)
          return
        }
        const response = await fetch('/api/chat/control', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ operation: intent.operation, message: content, allow_workspace_read: readFilesForThisMessage, ...(intent.view ? { view: intent.view } : {}) }),
        })
        if (!response.ok) throw new Error(await responseError(response))
        const data = await response.json()
        if (data.operation === 'list_agents') {
          setAgents(Array.isArray(data.agents) ? data.agents : [])
          setInventoryWarning(data.warning_count ? `${data.warning_count} stored agent record(s) could not be loaded.` : '')
          addAssistantMessage(`${data.assistant_message}${data.agents?.length ? `\n${data.agents.map((agent: Agent) => `• ${agent.config.name} (${agent.config.type})`).join('\n')}` : ''}`)
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
          addAssistantMessage(data.assistant_message)
        } else if (data.operation === 'navigate') {
          const view = data.navigation?.view as ExistingView | undefined
          if (!view) throw new Error('The server did not identify a destination view.')
          addAssistantMessage(data.assistant_message)
          onNavigate(view)
        } else if (data.operation === 'chat' && typeof data.assistant_message === 'string') {
          addAssistantMessage(data.assistant_message, undefined, Array.isArray(data.sources) ? data.sources : undefined)
        } else {
          throw new Error('The server returned an unsupported chat operation.')
        }
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'The request could not be completed.')
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
      addAssistantMessage(`Agent “${created.config.name}” created. You can select it from the agent list to start a live conversation.`)
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
    addAssistantMessage('Proposal cancelled. No agent was created.')
  }

  const openControlChat = () => { setSelectedAgent(null); setAllowWorkspaceRead(false); setMessages([]); setDraft(null); setDraftModels([]); setDraftModelsError(''); setError('') }
  const selectAgent = (agent: Agent) => { setSelectedAgent(agent); setAllowWorkspaceRead(false); setMessages([]); setDraft(null); setDraftModels([]); setDraftModelsError(''); setError('') }

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
        <button className="provider-shortcut" type="button" onClick={onOpenProviderSettings}>Configure Ollama provider <span aria-hidden="true">→</span></button>
      </aside>

      <div className="control-chat-main">
        <header className="control-chat-header"><div><p className="section-eyebrow">{selectedAgent ? 'Agent conversation' : 'Control plane'}</p><h2>{selectedAgent?.config.name ?? 'How can I help?'}</h2><p>{selectedAgent ? selectedAgent.config.description : 'Ask about your agents, propose a new agent, or open a view.'}</p></div><span className="chat-mode-badge">{selectedAgent ? selectedAgent.config.model_id || 'Sin modelo asignado' : 'Ollama assistant'}</span></header>
        <div className="control-chat-messages" aria-live="polite">
          {messages.length === 0 && <div className="chat-welcome"><div className="welcome-mark" aria-hidden="true">✳</div><h3>{selectedAgent ? `Chat with ${selectedAgent.config.name}` : 'Your workspace, through chat'}</h3><p>{selectedAgent ? 'Messages are sent to this agent through the configured Ollama provider.' : 'The assistant can list your application agents, draft one for your review, and navigate to supported views.'}</p>{!selectedAgent && <div className="prompt-suggestions"><button type="button" onClick={() => setInput('Lista mis agentes')}>List my agents</button><button type="button" onClick={() => setInput('Quiero crear un agente para…')}>Create an agent</button><button type="button" onClick={() => setInput('Abre el Decision Inspector')}>Open the Inspector</button></div>}</div>}
          {messages.map((message) => <article key={message.id} className={`control-message control-message-${message.role}`}><span className="message-speaker">{message.role === 'user' ? 'You' : selectedAgent?.config.name ?? 'Assistant'}</span><div className="control-message-content">{message.content}</div>{message.sources?.length ? <div className="message-sources" aria-label="Project files read"><strong>Project files read</strong><ul>{message.sources.map((source) => <li key={`${source.path}:${source.start_line}-${source.end_line}`}><code>{source.path}:{source.start_line}-{source.end_line}</code></li>)}</ul></div> : null}{message.trace && <div className="message-trace" aria-label="Execution trace evidence"><span>Trace {message.trace.state}</span><code>Local: {message.trace.localId}</code>{message.trace.jaegerId && <code>Jaeger: {message.trace.jaegerId}</code>}{message.trace.jaegerUrl && <a href={message.trace.jaegerUrl} target="_blank" rel="noreferrer">Open in Jaeger</a>}</div>}</article>)}
          {draft && <section className="agent-draft-card" aria-labelledby="draft-title"><div className="draft-heading"><div><p className="section-eyebrow">AI-assisted draft</p><h3 id="draft-title">Review and edit before saving</h3></div><span className="draft-status">Not created</span></div><div className="draft-fields"><label>Name<input value={draft.name} maxLength={120} onChange={(event) => setDraft({ ...draft, name: event.target.value })} disabled={creatingDraft} /></label><label>Description<textarea value={draft.description} maxLength={1000} rows={2} onChange={(event) => setDraft({ ...draft, description: event.target.value })} disabled={creatingDraft} /></label><label>Agent type<select value={draft.type} onChange={(event) => setDraft({ ...draft, type: event.target.value as AgentConfig['type'] })} disabled={creatingDraft}><option value="rag">RAG</option><option value="tool">Tool</option><option value="multi-agent">Multi-agent</option></select></label><label>Confirmed Ollama model<select value={draft.model_id ?? ''} onChange={(event) => setDraft({ ...draft, provider_id: 'ollama-cloud', model_id: event.target.value })} disabled={creatingDraft || loadingDraftModels || draftModels.length === 0}><option value="">{loadingDraftModels ? 'Loading models…' : 'Select a confirmed model'}</option>{draftModels.map((model) => <option key={model.model_id} value={model.model_id}>{model.display_name} · {model.source}</option>)}</select></label><label className="draft-prompt-field">System prompt<textarea value={draft.system_prompt} maxLength={12000} rows={6} onChange={(event) => setDraft({ ...draft, system_prompt: event.target.value })} disabled={creatingDraft} /></label></div><p className="draft-model-note" role={draftModelsError ? 'alert' : 'status'}>{draftModelsError || (loadingDraftModels ? 'Checking models from the configured backend…' : 'Model choices come from the configured provider and are not inferred from a public catalog.')}{draftModelsError && <button type="button" onClick={onOpenProviderSettings}>Open provider settings</button>}</p><details className="draft-advanced"><summary>Advanced details</summary><p><strong>Tools:</strong> {draft.tools.length ? draft.tools.join(', ') : 'No tools selected'}</p><p>Creating this profile does not grant tool execution or app-control permissions.</p></details><div className="draft-actions"><button type="button" className="secondary-action" onClick={cancelDraft} disabled={creatingDraft}>Cancel proposal</button><button type="button" className="primary-action" onClick={() => void createDraft()} disabled={creatingDraft || loadingDraftModels || draftModels.length === 0 || !draft.name.trim() || !draft.description.trim() || !draft.system_prompt.trim() || draft.provider_id !== 'ollama-cloud' || !draft.model_id?.trim() || !draftModels.some((model) => model.model_id === draft.model_id)}>{creatingDraft ? 'Creating…' : 'Create agent'}</button></div></section>}
          {createdNotice && <p className="success-state" role="status">{createdNotice}</p>}
          {error && <p className="chat-error" role="alert">{error}{error.toLowerCase().includes('ollama') || error.toLowerCase().includes('provider') ? <button type="button" onClick={onOpenProviderSettings}>Open provider settings</button> : null}</p>}
          {sending && <p className="muted-state" role="status">Waiting for Ollama…</p>}
          <div ref={messagesEndRef} />
        </div>
        <form className="control-chat-composer" onSubmit={(event) => void sendMessage(event)}><label className="visually-hidden" htmlFor="control-chat-input">Message the assistant or selected agent</label><textarea id="control-chat-input" rows={2} value={input} onChange={(event) => setInput(event.target.value)} placeholder={selectedAgent ? `Message ${selectedAgent.config.name}…` : 'Ask a question, list agents, create an agent, or open a view…'} disabled={sending} /><div className="chat-composer-actions"><label className="workspace-read-toggle"><input type="checkbox" checked={allowWorkspaceRead} onChange={(event) => setAllowWorkspaceRead(event.target.checked)} disabled={sending} /><span>Allow read-only project files for this message <small>Selected text is sent to Ollama Cloud</small></span></label><button className="primary-action" type="submit" disabled={sending || !input.trim()}>{sending ? 'Sending…' : 'Send'}</button></div><p>When enabled, chat can read bounded text files in this project and shows the lines it used. It cannot write files or run jobs.</p></form>
      </div>
    </section>
  )
}
