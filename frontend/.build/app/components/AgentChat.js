import { Fragment as _Fragment, jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import './AgentChat.css';
import './WindowsSurface.css';
import { useCallback, useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { capabilityResponseError } from './CapabilityManager';
import WindowPanel from './WindowPanel';
import TabStrip from './TabStrip';
function CognitiveContextPanel({ trace }) {
    const experimental = trace.mode === 'bago5';
    return _jsxs("section", { className: `message-cognition${experimental ? ' message-cognition-bago5' : ''}`, "aria-label": "Model prompt mode and cognitive context", children: [_jsxs("div", { className: "message-cognition-heading", children: [_jsx("strong", { children: experimental ? 'BAGO5 cognitive focus' : 'Baseline prompt' }), _jsx("span", { children: experimental ? 'experimental' : 'comparison' })] }), experimental ? _jsxs(_Fragment, { children: [_jsx("p", { children: "Bounded attention cues passed to the model as prompt guidance. This is not the model\u2019s hidden reasoning." }), _jsx("ul", { children: trace.focus.map((item) => _jsxs("li", { children: [_jsx("span", { children: item.label }), _jsx("code", { children: item.score.toFixed(3) })] }, item.id)) }), _jsxs("small", { children: [trace.profile, " \u00B7 ", trace.method, " \u00B7 capacity ", trace.capacity, " \u00B7 ", trace.max_hops, " hops"] })] }) : _jsx("p", { children: "The model received its normal chat prompt without the BAGO5 cognitive layer." }), trace.trace_id && _jsxs("small", { children: ["Local focus trace: ", trace.trace_id, " \u00B7 ", trace.trace_state] })] });
}
const scrollbarHideTimers = new WeakMap();
function revealScrollbarWhileScrolling(event) {
    const element = event.target;
    element.classList.add('is-scrolling');
    const existingTimer = scrollbarHideTimers.get(element);
    if (existingTimer !== undefined)
        window.clearTimeout(existingTimer);
    scrollbarHideTimers.set(element, window.setTimeout(() => {
        element.classList.remove('is-scrolling');
        scrollbarHideTimers.delete(element);
    }, 700));
}
const idFor = () => `${Date.now()}-${Math.random().toString(16).slice(2)}`;
async function responseError(response) {
    try {
        const body = await response.json();
        const detail = body?.detail;
        if (typeof detail === 'string')
            return detail;
        if (typeof detail?.message === 'string')
            return detail.message;
    }
    catch { /* keep a safe generic error */ }
    return `Request failed (${response.status}).`;
}
function inferIntent(message) {
    const text = message.toLocaleLowerCase();
    const capabilityIdMentioned = /\b(?:workspace\.read_text|mcp\.execute|sandbox\.execute|agent\.run)\b/.test(text);
    if (/\b(capabilities|capability manager|gestor de capacidades|capacidades)\b/.test(text) && /\b(abre|abrir|open|show|muestra|ir a|ve a|navega|gestiona|manager|gestor|vista)\b/.test(text))
        return { operation: 'navigate', view: 'capabilities' };
    if (/\b(propuesta|proponer|propose|proposal)\b/.test(text) && (/\b(capacidad|capability|acceso|access|habilitar|enable|registrar|register)\b/.test(text) || capabilityIdMentioned))
        return { operation: 'propose_capability' };
    if (/\b(capacidades|capability catalog|capabilities|estado de (?:la )?capacidad|list(?:ar)? capabilities)\b/.test(text) || (capabilityIdMentioned && /\b(estado|status|lista|listar|mostrar|show|describe|qu[eé])\b/.test(text)))
        return { operation: 'list_capabilities' };
    if (/^\s*(hola|buenas|hello|hi|hey)[!.\s]*$/.test(text) || /\b(qu[eé] puedes hacer|what can you do|capacidades del asistente|assistant capabilities)\b/.test(text) || /\b(puedes|can you|could you)\s+(crear|create|diseñar|design)\s+(un\s+|a\s+)?agentes?\s*[?!.]*$/.test(text) || /\b(no puedes|cannot|can't)\s+(crear|create)\s+agentes?\b/.test(text)) {
        return { operation: 'help' };
    }
    if (/\b(lista|listar|muestra|mostrar|qué|cu[aá]les)\b.*\b(agentes|agente)\b/.test(text) || /\b(agentes|agente)\b.*\b(lista|listar|hay|tengo)\b/.test(text)) {
        return { operation: 'list_agents' };
    }
    if (/\b(crea|crear|diseña|diseñar|configura|configurar)\b.*\bagente\b/.test(text) || /\b(necesito|quiero)\s+(un\s+)?agente\b/.test(text)) {
        return { operation: 'draft_agent' };
    }
    const destinations = [
        [/\b(agent evaluation lab|evaluation lab|laboratorio de evaluaci[oó]n de agentes|laboratorio de evaluaci[oó]n)\b/, 'evaluation_lab'],
        [/\b(inspector|decisiones)\b/, 'inspector'],
        [/\b(builder|creaci[oó]n de agentes)\b/, 'builder'],
        [/\b(chat)\b/, 'chat'],
        [/\b(agent runs|runner|ejecutor)\b/, 'runner'],
        [/\b(control)\b/, 'control'],
        [/\b(jobs?|trabajos|historial)\b/, 'jobs'],
        [/\b(traces?|trazas)\b/, 'traces'],
        [/\b(summary|resumen)\b/, 'summary'],
        [/\b(retrieval|ontology|recuperaci[oó]n|ontolog[ií]a)\b/, 'retrieval'],
        [/\b(authorization|autorizaci[oó]n)\b/, 'authorization'],
        [/\b(evaluation|evaluaci[oó]n)\b/, 'evaluation'],
        [/\b(provider|proveedor|ollama)\b/, 'provider_settings'],
    ];
    if (/\b(abre|abrir|ve a|ir a|navega|muestra la vista|ll[eé]vame|ll[eé]vame a|entra a|open|go to|show me)\b/.test(text)) {
        const destination = destinations.find(([pattern]) => pattern.test(text));
        if (destination) {
            return { operation: 'navigate', view: destination[1] };
        }
    }
    return { operation: 'chat' };
}
export default function AgentChat({ onNavigate, onOpenProviderSettings, onOpenCognitionSettings, cognitiveMode }) {
    const [agents, setAgents] = useState([]);
    const [agentsState, setAgentsState] = useState('loading');
    const [inventoryWarning, setInventoryWarning] = useState('');
    const [selectedAgent, setSelectedAgent] = useState(null);
    const [messages, setMessages] = useState([]);
    const [activeConversation, setActiveConversation] = useState(null);
    const [conversationList, setConversationList] = useState([]);
    const [conversationContextMenu, setConversationContextMenu] = useState(null);
    const [libraryMode, setLibraryMode] = useState('active');
    const [libraryError, setLibraryError] = useState('');
    const [loadingConversation, setLoadingConversation] = useState(false);
    const [input, setInput] = useState('');
    const [allowWorkspaceRead, setAllowWorkspaceRead] = useState(false);
    const [workspaceReadPaths, setWorkspaceReadPaths] = useState('');
    const [sending, setSending] = useState(false);
    const [error, setError] = useState('');
    const [draft, setDraft] = useState(null);
    const [draftModels, setDraftModels] = useState([]);
    const [loadingDraftModels, setLoadingDraftModels] = useState(false);
    const [draftModelsError, setDraftModelsError] = useState('');
    const [creatingDraft, setCreatingDraft] = useState(false);
    const [createdNotice, setCreatedNotice] = useState('');
    const [capabilityDraft, setCapabilityDraft] = useState(null);
    const [capabilityProposals, setCapabilityProposals] = useState([]);
    const [capabilityBusy, setCapabilityBusy] = useState(false);
    const [agentPanelTarget, setAgentPanelTarget] = useState(null);
    const messagesEndRef = useRef(null);
    const contextMenuRef = useRef(null);
    const longPressTimerRef = useRef(null);
    const longPressTriggeredRef = useRef(false);
    const agentRefreshAtRef = useRef(0);
    const agentRefreshInFlightRef = useRef(null);
    const agentsLoadedRef = useRef(false);
    const refreshAgents = useCallback(async ({ background = false } = {}) => {
        const inFlight = agentRefreshInFlightRef.current;
        if (inFlight)
            return inFlight;
        if (!background)
            setAgentsState('loading');
        agentRefreshAtRef.current = Date.now();
        const request = (async () => {
            try {
                const response = await fetch('/api/agents/list');
                if (!response.ok)
                    throw new Error(await responseError(response));
                const data = await response.json();
                const nextAgents = Array.isArray(data.agents) ? data.agents : [];
                setAgents(nextAgents);
                setSelectedAgent((current) => current ? nextAgents.find((agent) => agent.id === current.id) ?? current : null);
                agentsLoadedRef.current = true;
                setInventoryWarning(data.warning_count
                    ? `${data.warning_count} stored agent record(s) could not be loaded.`
                    : '');
                setAgentsState('ready');
            }
            catch (cause) {
                if (background && agentsLoadedRef.current) {
                    setInventoryWarning('Could not refresh the agent list. Showing the last loaded list.');
                }
                else {
                    setAgentsState('error');
                    setError(cause instanceof Error ? cause.message : 'Agent inventory could not be loaded.');
                }
            }
        })();
        agentRefreshInFlightRef.current = request;
        try {
            await request;
        }
        finally {
            if (agentRefreshInFlightRef.current === request)
                agentRefreshInFlightRef.current = null;
        }
    }, []);
    const ownerKind = selectedAgent ? 'agent' : 'assistant';
    const ownerId = selectedAgent?.id ?? 'app-assistant';
    const applyConversation = (conversation) => {
        setActiveConversation(conversation);
        setMessages(conversation.messages.map((message) => {
            const trace = message.references?.trace;
            return {
                id: message.id,
                role: message.role,
                content: message.content,
                ...(trace?.trace_id ? { trace: { localId: trace.trace_id, state: trace.trace_state || 'unknown', jaegerId: trace.jaeger_trace_id, jaegerUrl: trace.jaeger_url } } : {}),
                ...(message.references?.cognitive_trace ? { cognitiveTrace: message.references.cognitive_trace } : {}),
                ...(message.references?.sources?.length ? { sources: message.references.sources } : {}),
                ...(Array.isArray(message.references?.read_events) ? { readEvents: message.references.read_events } : {}),
            };
        }));
    };
    const refreshConversationList = async () => {
        setLibraryError('');
        try {
            const query = new URLSearchParams({ owner_kind: ownerKind, owner_id: ownerId, status: libraryMode });
            const response = await fetch(`/api/conversations?${query}`);
            if (!response.ok)
                throw new Error(await responseError(response));
            const data = await response.json();
            const conversations = Array.isArray(data.conversations) ? data.conversations : [];
            setConversationList(conversations);
            if (!activeConversation || activeConversation.owner_kind !== ownerKind || activeConversation.owner_id !== ownerId || activeConversation.status !== libraryMode) {
                if (libraryMode === 'deleted' && conversations.length) {
                    setActiveConversation({ ...conversations[0], messages: [] });
                    setMessages([]);
                }
                else if (conversations.length) {
                    const latest = await fetch(`/api/conversations/${encodeURIComponent(conversations[0].id)}`);
                    if (latest.ok)
                        applyConversation(await latest.json());
                    else {
                        setActiveConversation(null);
                        setMessages([]);
                    }
                }
                else {
                    setActiveConversation(null);
                    setMessages([]);
                }
            }
        }
        catch (cause) {
            setLibraryError(cause instanceof Error ? cause.message : 'Conversation library could not be loaded.');
        }
    };
    useEffect(() => { void refreshAgents(); }, [refreshAgents]);
    useEffect(() => {
        const refreshIfStale = () => {
            if (document.visibilityState !== 'visible' || Date.now() - agentRefreshAtRef.current < 30000)
                return;
            void refreshAgents({ background: true });
        };
        document.addEventListener('visibilitychange', refreshIfStale);
        window.addEventListener('focus', refreshIfStale);
        return () => {
            document.removeEventListener('visibilitychange', refreshIfStale);
            window.removeEventListener('focus', refreshIfStale);
        };
    }, [refreshAgents]);
    useEffect(() => { void refreshConversationList(); }, [ownerKind, ownerId, libraryMode]);
    useEffect(() => { void refreshConversationProposals(activeConversation?.id ?? null); }, [activeConversation?.id]);
    useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);
    useEffect(() => {
        if (!conversationContextMenu)
            return;
        contextMenuRef.current?.querySelector('button')?.focus();
        const dismiss = (event) => {
            if (event.target instanceof Element && event.target.closest('[data-conversation-context-menu]'))
                return;
            setConversationContextMenu(null);
        };
        const dismissOnEscape = (event) => {
            if (event.key === 'Escape')
                setConversationContextMenu(null);
        };
        document.addEventListener('pointerdown', dismiss);
        document.addEventListener('keydown', dismissOnEscape);
        return () => {
            document.removeEventListener('pointerdown', dismiss);
            document.removeEventListener('keydown', dismissOnEscape);
        };
    }, [conversationContextMenu]);
    useEffect(() => () => {
        if (longPressTimerRef.current !== null)
            window.clearTimeout(longPressTimerRef.current);
    }, []);
    const startConversation = async () => {
        setLibraryError('');
        try {
            const response = await fetch('/api/conversations', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ owner_kind: ownerKind, owner_id: ownerId }),
            });
            if (!response.ok)
                throw new Error(await responseError(response));
            const conversation = await response.json();
            setLibraryMode('active');
            const detail = await fetch(`/api/conversations/${encodeURIComponent(conversation.id)}`);
            if (!detail.ok)
                throw new Error(await responseError(detail));
            applyConversation(await detail.json());
            const query = new URLSearchParams({ owner_kind: ownerKind, owner_id: ownerId, status: 'active' });
            const list = await fetch(`/api/conversations?${query}`);
            if (list.ok)
                setConversationList((await list.json()).conversations || []);
        }
        catch (cause) {
            setLibraryError(cause instanceof Error ? cause.message : 'A new conversation could not be created.');
        }
    };
    const openConversation = async (conversationId) => {
        setLoadingConversation(true);
        setLibraryError('');
        try {
            const response = await fetch(`/api/conversations/${encodeURIComponent(conversationId)}`);
            if (!response.ok)
                throw new Error(await responseError(response));
            applyConversation(await response.json());
        }
        catch (cause) {
            setLibraryError(cause instanceof Error ? cause.message : 'Conversation could not be opened.');
        }
        finally {
            setLoadingConversation(false);
        }
    };
    const manageConversation = async (action, target = activeConversation) => {
        if (!target)
            return;
        const title = action === 'rename' ? window.prompt('Conversation title', target.title) : null;
        if (action === 'rename' && title === null)
            return;
        const route = action === 'rename' ? `/api/conversations/${target.id}` : `/api/conversations/${target.id}/${action}`;
        const method = action === 'rename' ? 'PATCH' : 'POST';
        const body = action === 'rename' ? { revision: target.revision, title } : { revision: target.revision };
        try {
            const response = await fetch(route, { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
            if (!response.ok)
                throw new Error(await responseError(response));
            if (action === 'delete') {
                if (activeConversation?.id === target.id) {
                    setActiveConversation(null);
                    setMessages([]);
                }
                setLibraryMode('deleted');
            }
            else {
                const updated = await response.json();
                if (activeConversation?.id === target.id)
                    applyConversation(updated);
                if (action === 'archive')
                    setLibraryMode('archived');
                if (action === 'restore')
                    setLibraryMode('active');
            }
            await refreshConversationList();
        }
        catch (cause) {
            setLibraryError(cause instanceof Error ? cause.message : 'Conversation could not be updated.');
            if (cause instanceof Error && cause.message.includes('changed elsewhere'))
                await refreshConversationList();
        }
    };
    const showConversationContextMenu = (conversation, x, y) => {
        const menuWidth = 184;
        const menuHeight = conversation.status === 'active' ? 132 : conversation.status === 'archived' ? 104 : 56;
        setConversationContextMenu({
            conversation,
            x: Math.max(8, Math.min(x, window.innerWidth - menuWidth - 8)),
            y: Math.max(8, Math.min(y, window.innerHeight - menuHeight - 8)),
        });
    };
    const cancelConversationLongPress = () => {
        if (longPressTimerRef.current !== null)
            window.clearTimeout(longPressTimerRef.current);
        longPressTimerRef.current = null;
    };
    async function refreshConversationProposals(conversationId) {
        if (!conversationId) {
            setCapabilityProposals([]);
            return;
        }
        try {
            const response = await fetch('/api/capabilities/proposals?status=all&limit=100');
            if (!response.ok)
                throw new Error(await capabilityResponseError(response));
            const data = await response.json();
            setCapabilityProposals((Array.isArray(data.proposals) ? data.proposals : []).filter((item) => item.conversation_id === conversationId));
        }
        catch (cause) {
            setError(cause instanceof Error ? cause.message : 'Capability proposals could not be loaded.');
        }
    }
    async function beginCapabilityRequest(content, operation, conversationId) {
        setCapabilityBusy(true);
        setCapabilityDraft(null);
        setError('');
        try {
            const response = await fetch('/api/capabilities');
            if (!response.ok)
                throw new Error(await capabilityResponseError(response));
            const catalog = await response.json();
            const capabilities = Array.isArray(catalog.capabilities) ? catalog.capabilities : [];
            setMessages((previous) => [...previous, { id: idFor(), role: 'user', content }]);
            if (operation === 'list_capabilities') {
                const summary = capabilities.length
                    ? capabilities.map((item) => `${item.id}: ${item.status} (${item.effect}) — ${item.name}`).join('\n')
                    : 'The backend returned no capability records.';
                setMessages((previous) => [...previous, { id: idFor(), role: 'assistant', content: `${summary}\n\n${catalog.authority_notice || 'Catalog status does not grant permission or enable execution.'}` }]);
                return;
            }
            const lower = content.toLocaleLowerCase();
            const exactMatches = capabilities.filter((item) => lower.includes(item.id.toLocaleLowerCase()) || lower.includes(item.name.toLocaleLowerCase()));
            const capabilityId = exactMatches.length === 1 ? exactMatches[0].id : '';
            const summary = content.trim().slice(0, 500);
            setCapabilityDraft({ capabilities, capabilityId, summary, requestedScope: '', conversationId });
            setMessages((previous) => [...previous, { id: idFor(), role: 'assistant', content: exactMatches.length === 1
                        ? `I found the exact backend catalog entry “${exactMatches[0].id}”. Review the capability, summary, and requested scope below before saving a proposal.`
                        : 'I could not select one exact catalog entry from that request. Choose the intended capability below; no fuzzy selection was made.' }]);
        }
        catch (cause) {
            setError(cause instanceof Error ? cause.message : 'Capability catalog could not be loaded.');
        }
        finally {
            setCapabilityBusy(false);
        }
    }
    async function saveCapabilityProposal() {
        if (!capabilityDraft || capabilityBusy || !capabilityDraft.capabilityId || !capabilityDraft.summary.trim() || !capabilityDraft.requestedScope.trim())
            return;
        setCapabilityBusy(true);
        setError('');
        try {
            const response = await fetch('/api/capabilities/proposals', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ capability_id: capabilityDraft.capabilityId, summary: capabilityDraft.summary, requested_scope: capabilityDraft.requestedScope, ...(capabilityDraft.conversationId ? { conversation_id: capabilityDraft.conversationId } : {}) }),
            });
            if (!response.ok)
                throw new Error(await capabilityResponseError(response));
            const result = await response.json();
            const saved = result.proposal;
            setCapabilityProposals((previous) => [saved, ...previous.filter((item) => item.id !== saved.id)]);
            setMessages((previous) => [...previous, { id: idFor(), role: 'assistant', content: `${result.authority_notice || 'Proposal saved for review only; no permission, job, or execution was created.'}\nProposal ID: ${saved.id}` }]);
            setCapabilityDraft(null);
        }
        catch (cause) {
            setError(cause instanceof Error ? cause.message : 'Capability proposal could not be saved.');
        }
        finally {
            setCapabilityBusy(false);
        }
    }
    async function cancelChatProposal(proposal) {
        setCapabilityBusy(true);
        setError('');
        try {
            const response = await fetch(`/api/capabilities/proposals/${encodeURIComponent(proposal.id)}/cancel`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ revision: proposal.revision }) });
            if (!response.ok)
                throw new Error(await capabilityResponseError(response));
            const result = await response.json();
            setCapabilityProposals((previous) => previous.map((item) => item.id === proposal.id ? result.proposal : item));
            setMessages((previous) => [...previous, { id: idFor(), role: 'assistant', content: result.authority_notice }]);
        }
        catch (cause) {
            setError(cause instanceof Error ? cause.message : 'Capability proposal could not be cancelled.');
            await refreshConversationProposals(activeConversation?.id ?? null);
        }
        finally {
            setCapabilityBusy(false);
        }
    }
    const sendMessage = async (event) => {
        event?.preventDefault();
        const content = input.trim();
        if (!content || sending)
            return;
        setInput('');
        setError('');
        setLibraryError('');
        setCreatedNotice('');
        setDraft(null);
        const readFilesForThisMessage = allowWorkspaceRead;
        setAllowWorkspaceRead(false);
        setSending(true);
        let attemptedConversation = null;
        try {
            let conversation = activeConversation;
            if (!conversation || conversation.owner_kind !== ownerKind || conversation.owner_id !== ownerId || conversation.status !== 'active') {
                const createResponse = await fetch('/api/conversations', {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ owner_kind: ownerKind, owner_id: ownerId }),
                });
                if (!createResponse.ok)
                    throw new Error(await responseError(createResponse));
                const summary = await createResponse.json();
                conversation = { ...summary, messages: [] };
                setActiveConversation(conversation);
            }
            attemptedConversation = conversation;
            const localCapabilityIntent = !selectedAgent ? inferIntent(content) : null;
            if (localCapabilityIntent?.operation === 'list_capabilities' || localCapabilityIntent?.operation === 'propose_capability') {
                await beginCapabilityRequest(content, localCapabilityIntent.operation, conversation.id);
                return;
            }
            if (localCapabilityIntent?.operation === 'navigate' && localCapabilityIntent.view === 'capabilities') {
                setMessages((previous) => [...previous, { id: idFor(), role: 'user', content }]);
                onNavigate('capabilities');
                return;
            }
            if (localCapabilityIntent?.operation === 'navigate' && localCapabilityIntent.view === 'evaluation_lab') {
                setMessages((previous) => [...previous, { id: idFor(), role: 'user', content }]);
                onNavigate('evaluation_lab');
                return;
            }
            setMessages((previous) => [...previous, { id: idFor(), role: 'user', content }]);
            let workspaceReadAuthorizationId;
            if (readFilesForThisMessage) {
                const paths = workspaceReadPaths.split(/\r?\n/).map((path) => path.trim()).filter(Boolean);
                if (!paths.length)
                    throw new Error('Enter the exact project-relative file paths to authorize, one per line.');
                const authorizationResponse = await fetch('/api/workspace-read/authorizations', {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ owner_kind: ownerKind, owner_id: ownerId, conversation_id: conversation.id, revision: conversation.revision, paths }),
                });
                if (!authorizationResponse.ok)
                    throw new Error(await responseError(authorizationResponse));
                const authorization = await authorizationResponse.json();
                workspaceReadAuthorizationId = authorization.authorization_id;
            }
            let response;
            let data;
            let intent = null;
            if (selectedAgent) {
                response = await fetch(`/api/agents/${encodeURIComponent(selectedAgent.id)}/chat`, {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message: content, conversation_id: conversation.id, revision: conversation.revision, cognitive_mode: cognitiveMode, ...(workspaceReadAuthorizationId ? { workspace_read_authorization_id: workspaceReadAuthorizationId } : {}) }),
                });
            }
            else {
                intent = localCapabilityIntent ?? inferIntent(content);
                response = await fetch('/api/chat/control', {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ operation: intent.operation, message: content, conversation_id: conversation.id, revision: conversation.revision, ...(intent.operation === 'chat' ? { cognitive_mode: cognitiveMode } : {}), ...(workspaceReadAuthorizationId ? { workspace_read_authorization_id: workspaceReadAuthorizationId } : {}), ...(intent.view ? { view: intent.view } : {}) }),
                });
            }
            if (!response.ok)
                throw new Error(await responseError(response));
            data = await response.json();
            if (selectedAgent && (data.source !== 'ollama' || typeof data.assistant_message !== 'string'))
                throw new Error('The server did not confirm a live Ollama response.');
            if (Array.isArray(data.read_events) && data.read_events.length) {
                setMessages((previous) => [...previous, { id: idFor(), role: 'assistant', content: '', readEvents: data.read_events }]);
            }
            if (!data.conversation || !Array.isArray(data.conversation.messages))
                throw new Error('The server did not return the saved conversation.');
            applyConversation(data.conversation);
            if (data.operation === 'list_agents') {
                setAgents(Array.isArray(data.agents) ? data.agents : []);
                setInventoryWarning(data.warning_count ? `${data.warning_count} stored agent record(s) could not be loaded.` : '');
            }
            else if (data.operation === 'draft_agent') {
                if (!data.agent_draft || data.created !== false)
                    throw new Error('The server returned an invalid or already-created proposal.');
                const proposedDraft = data.agent_draft;
                setDraft(proposedDraft);
                setDraftModels([]);
                setDraftModelsError('');
                setLoadingDraftModels(true);
                try {
                    const modelsResponse = await fetch('/api/providers/ollama/models');
                    if (!modelsResponse.ok)
                        throw new Error(await responseError(modelsResponse));
                    const modelsData = await modelsResponse.json();
                    const usableModels = Array.isArray(modelsData.models)
                        ? modelsData.models.filter((model) => model.provider_id === 'ollama-cloud' && model.availability_confidence === 'listed' && typeof model.model_id === 'string')
                        : [];
                    setDraftModels(usableModels);
                    if (!usableModels.some((model) => model.model_id === proposedDraft.model_id)) {
                        setDraft((current) => current ? { ...current, model_id: usableModels[0]?.model_id ?? '' } : current);
                    }
                    if (!usableModels.length)
                        setDraftModelsError('No usable Ollama models were confirmed. Configure the provider, then request a new proposal.');
                }
                catch (modelError) {
                    setDraftModelsError(modelError instanceof Error ? modelError.message : 'Could not load confirmed Ollama models.');
                }
                finally {
                    setLoadingDraftModels(false);
                }
            }
            else if (data.operation === 'navigate') {
                const view = data.navigation?.view;
                if (!view)
                    throw new Error('The server did not identify a destination view.');
                onNavigate(view);
            }
            else if (!selectedAgent && !['chat', 'help'].includes(data.operation)) {
                throw new Error('The server returned an unsupported chat operation.');
            }
            const query = new URLSearchParams({ owner_kind: ownerKind, owner_id: ownerId, status: libraryMode });
            const listResponse = await fetch(`/api/conversations?${query}`);
            if (listResponse.ok)
                setConversationList((await listResponse.json()).conversations || []);
        }
        catch (cause) {
            setError(cause instanceof Error ? cause.message : 'The request could not be completed.');
            if (attemptedConversation)
                await openConversation(attemptedConversation.id);
        }
        finally {
            setSending(false);
        }
    };
    const createDraft = async () => {
        if (!draft || creatingDraft)
            return;
        if (draft.provider_id !== 'ollama-cloud' || !draft.model_id?.trim() || !draftModels.some((model) => model.model_id === draft.model_id)) {
            setError('Choose a model confirmed by the configured Ollama provider before creating this agent.');
            return;
        }
        const createPayload = Object.fromEntries(Object.entries(draft).filter(([, value]) => value !== null && value !== undefined));
        setCreatingDraft(true);
        setError('');
        try {
            const response = await fetch('/api/agents/create', {
                method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(createPayload),
            });
            if (!response.ok)
                throw new Error(await responseError(response));
            const created = await response.json();
            setDraft(null);
            setCreatedNotice(`${created.config.name} was created and added to your agent list.`);
            await refreshAgents();
        }
        catch (cause) {
            setError(cause instanceof Error ? cause.message : 'Agent creation failed.');
        }
        finally {
            setCreatingDraft(false);
        }
    };
    const cancelDraft = () => {
        setDraft(null);
        setDraftModels([]);
        setDraftModelsError('');
    };
    const openControlChat = () => { setSelectedAgent(null); setAllowWorkspaceRead(false); setWorkspaceReadPaths(''); setDraft(null); setDraftModels([]); setDraftModelsError(''); setCapabilityDraft(null); setCapabilityProposals([]); setError(''); };
    const selectAgent = (agent) => { setSelectedAgent(agent); setAllowWorkspaceRead(false); setWorkspaceReadPaths(''); setDraft(null); setDraftModels([]); setDraftModelsError(''); setCapabilityDraft(null); setCapabilityProposals([]); setError(''); };
    return (_jsxs("section", { className: "control-chat", "aria-label": "Agent and application chat", onScrollCapture: revealScrollbarWhileScrolling, children: [agentPanelTarget && createPortal(_jsxs("details", { className: "chat-agent-panel", children: [_jsxs("summary", { children: ["Workspace and agents ", _jsx("span", { children: agentsState === 'ready' ? agents.length : '—' })] }), _jsxs("aside", { className: "control-chat-sidebar", "aria-label": "Agent inventory", children: [_jsxs("section", { className: "chat-sidebar-pane chat-sidebar-agents", "aria-labelledby": "chat-agents-title", children: [_jsx("div", { className: "chat-sidebar-heading", children: _jsx("div", { children: _jsx("h2", { id: "chat-agents-title", children: "Agents" }) }) }), _jsxs("button", { type: "button", className: `control-agent-option ${selectedAgent === null ? 'selected' : ''}`, onClick: openControlChat, children: [_jsx("strong", { children: "App assistant" }), _jsx("span", { children: "Chat, list agents, create drafts, navigate" })] }), _jsxs("div", { className: "agent-list-label", children: [_jsx("span", { children: "Your application agents" }), _jsx("span", { children: agentsState === 'ready' ? agents.length : '—' })] }), agentsState === 'loading' && _jsx("p", { className: "muted-state", role: "status", children: "Loading agents\u2026" }), agentsState === 'error' && _jsx("p", { className: "inline-error", children: "Agent inventory unavailable." }), agentsState === 'ready' && agents.length === 0 && _jsx("p", { className: "muted-state", children: "No agents created yet. Ask the app assistant to create one." }), _jsx("div", { className: "control-agent-list", children: agents.map((agent) => _jsxs("button", { type: "button", className: `control-agent-option ${selectedAgent?.id === agent.id ? 'selected' : ''}`, onClick: () => selectAgent(agent), children: [_jsx("strong", { children: agent.config.name }), _jsxs("span", { children: [agent.config.type, " \u00B7 ", agent.config.model_id || 'Sin modelo asignado'] }), _jsx("span", { children: agent.config.description })] }, agent.id)) }), inventoryWarning && _jsx("p", { className: "warning-state", role: "status", children: inventoryWarning })] }), _jsxs("section", { className: "chat-sidebar-pane conversation-library", "aria-label": "Conversation library", children: [_jsx("div", { className: "conversation-library-heading", children: _jsx("strong", { children: "Chats" }) }), _jsx(TabStrip, { label: "Conversation status", value: libraryMode, onChange: setLibraryMode, items: [{ id: 'active', label: 'Recent' }, { id: 'archived', label: 'Archived' }, { id: 'deleted', label: 'Trash' }] }), loadingConversation && _jsx("p", { className: "muted-state", role: "status", children: "Opening conversation\u2026" }), libraryError && _jsx("p", { className: "inline-error", role: "alert", children: libraryError }), conversationList.length === 0 && !libraryError && _jsxs("p", { className: "muted-state", children: ["No ", libraryMode === 'active' ? 'recent' : libraryMode, " chats for this owner."] }), _jsx("div", { className: "conversation-library-list", children: conversationList.map((conversation) => _jsxs("button", { type: "button", className: `conversation-library-item ${activeConversation?.id === conversation.id ? 'selected' : ''}`, onClick: (event) => {
                                                if (longPressTriggeredRef.current) {
                                                    event.preventDefault();
                                                    longPressTriggeredRef.current = false;
                                                    return;
                                                }
                                                setConversationContextMenu(null);
                                                if (conversation.status === 'deleted') {
                                                    setActiveConversation({ ...conversation, messages: [] });
                                                    setMessages([]);
                                                }
                                                else
                                                    void openConversation(conversation.id);
                                            }, onContextMenu: (event) => { event.preventDefault(); cancelConversationLongPress(); showConversationContextMenu(conversation, event.clientX, event.clientY); }, onPointerDown: (event) => {
                                                if (event.pointerType !== 'touch')
                                                    return;
                                                cancelConversationLongPress();
                                                longPressTriggeredRef.current = false;
                                                const { clientX, clientY } = event;
                                                longPressTimerRef.current = window.setTimeout(() => {
                                                    longPressTriggeredRef.current = true;
                                                    showConversationContextMenu(conversation, clientX, clientY);
                                                }, 550);
                                            }, onPointerUp: cancelConversationLongPress, onPointerCancel: cancelConversationLongPress, onPointerLeave: cancelConversationLongPress, onKeyDown: (event) => {
                                                if (event.key !== 'ContextMenu' && !(event.shiftKey && event.key === 'F10'))
                                                    return;
                                                event.preventDefault();
                                                const bounds = event.currentTarget.getBoundingClientRect();
                                                showConversationContextMenu(conversation, bounds.left, bounds.bottom);
                                            }, children: [_jsx("strong", { children: conversation.title }), _jsx("span", { children: new Date(conversation.updated_at).toLocaleString() })] }, conversation.id)) }), _jsx("div", { className: "conversation-library-footer", children: _jsx("button", { className: "conversation-library-new", type: "button", onClick: () => void startConversation(), children: "New" }) }), conversationContextMenu && _jsxs("div", { ref: contextMenuRef, className: "conversation-context-menu", "data-conversation-context-menu": true, role: "menu", "aria-label": `Actions for ${conversationContextMenu.conversation.title}`, style: { left: conversationContextMenu.x, top: conversationContextMenu.y }, onKeyDown: (event) => {
                                            if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp')
                                                return;
                                            event.preventDefault();
                                            const items = Array.from(event.currentTarget.querySelectorAll('button'));
                                            const currentIndex = items.indexOf(document.activeElement);
                                            const direction = event.key === 'ArrowDown' ? 1 : -1;
                                            items[(currentIndex + direction + items.length) % items.length]?.focus();
                                        }, children: [conversationContextMenu.conversation.status !== 'deleted' && _jsx("button", { type: "button", role: "menuitem", onClick: () => { const { conversation } = conversationContextMenu; setConversationContextMenu(null); void manageConversation('rename', conversation); }, children: "Rename" }), conversationContextMenu.conversation.status === 'active' && _jsx("button", { type: "button", role: "menuitem", onClick: () => { const { conversation } = conversationContextMenu; setConversationContextMenu(null); void manageConversation('archive', conversation); }, children: "Archive" }), conversationContextMenu.conversation.status !== 'deleted' && _jsx("button", { type: "button", role: "menuitem", onClick: () => { const { conversation } = conversationContextMenu; setConversationContextMenu(null); void manageConversation('delete', conversation); }, children: "Move to trash" }), conversationContextMenu.conversation.status !== 'active' && _jsx("button", { type: "button", role: "menuitem", onClick: () => { const { conversation } = conversationContextMenu; setConversationContextMenu(null); void manageConversation('restore', conversation); }, children: "Restore" })] })] })] })] }), agentPanelTarget), _jsxs(WindowPanel, { title: selectedAgent?.config.name ?? activeConversation?.title ?? 'How can I help?', className: "control-chat-main control-chat-window", hideTitlebar: true, children: [_jsx("div", { className: "chat-mode-header", children: _jsxs("button", { type: "button", onClick: onOpenCognitionSettings, "aria-label": "Open cognition and context settings", children: ["Cognition: ", cognitiveMode === 'bago5' ? 'BAGO5 experimental' : 'Baseline', " ", _jsx("span", { "aria-hidden": "true", children: "\u2197" })] }) }), _jsxs("div", { className: "control-chat-messages", "aria-live": "polite", children: [messages.length === 0 && _jsxs("div", { className: "chat-welcome", children: [_jsx("div", { className: "welcome-mark", "aria-hidden": "true", children: "\u2733" }), _jsx("h3", { children: selectedAgent ? `Chat with ${selectedAgent.config.name}` : 'Your workspace, through chat' }), _jsx("p", { children: selectedAgent ? 'Messages are sent to this agent through the configured Ollama provider.' : 'The assistant can list your application agents, draft one for your review, and navigate to supported views.' }), !selectedAgent && _jsxs("div", { className: "prompt-suggestions", children: [_jsx("button", { type: "button", onClick: () => setInput('Lista mis agentes'), children: "List my agents" }), _jsx("button", { type: "button", onClick: () => setInput('Quiero crear un agente para…'), children: "Create an agent" }), _jsx("button", { type: "button", onClick: () => setInput('Abre el Decision Inspector'), children: "Open the Inspector" })] })] }), messages.map((message) => _jsxs("article", { className: `control-message control-message-${message.role}`, children: [_jsx("span", { className: "message-speaker", children: message.role === 'user' ? 'You' : selectedAgent?.config.name ?? 'Assistant' }), message.content && _jsx("div", { className: "control-message-content", children: message.content }), message.cognitiveTrace && _jsx(CognitiveContextPanel, { trace: message.cognitiveTrace }), message.sources?.length ? _jsxs("div", { className: "message-sources", "aria-label": "Project files read", children: [_jsx("strong", { children: "Project files read" }), _jsx("ul", { children: message.sources.map((source) => _jsxs("li", { children: [_jsxs("code", { children: [source.path, ":", source.start_line, "-", source.end_line] }), source.content_sha256 && _jsxs("small", { children: [" SHA-256 ", source.content_sha256] })] }, `${source.path}:${source.start_line}-${source.end_line}`)) })] }) : null, message.readEvents?.length ? _jsxs("div", { className: "message-sources", "aria-label": "Read-only analysis evidence", children: [_jsx("strong", { children: "Read-only analysis evidence" }), _jsx("ul", { children: message.readEvents.map((event, index) => _jsxs("li", { children: [_jsxs("code", { children: [event.decision, " ", event.path || '(unresolved path)', " ", event.reason_code ? `· ${event.reason_code}` : ''] }), event.kind === 'directory_code_scan' && _jsx("small", { children: ` · ${event.files_scanned ?? 0} files · ${event.lines_scanned ?? 0} lines · ${event.finding_count ?? 0} findings${event.truncated ? ' · capped' : ''} · manifest SHA-256 ${event.manifest_sha256 ?? 'unavailable'}` })] }, `${event.path}:${index}`)) })] }) : null, message.trace && _jsxs("div", { className: "message-trace", "aria-label": "Execution trace evidence", children: [_jsxs("span", { children: ["Trace ", message.trace.state] }), _jsxs("code", { children: ["Local: ", message.trace.localId] }), message.trace.jaegerId && _jsxs("code", { children: ["Jaeger: ", message.trace.jaegerId] }), message.trace.jaegerUrl && _jsx("a", { href: message.trace.jaegerUrl, target: "_blank", rel: "noreferrer", children: "Open in Jaeger" })] })] }, message.id)), capabilityDraft && _jsxs("section", { className: "capability-chat-card", "aria-labelledby": "capability-draft-title", children: [_jsxs("div", { className: "draft-heading", children: [_jsxs("div", { children: [_jsx("p", { className: "section-eyebrow", children: "Proposal review" }), _jsx("h3", { id: "capability-draft-title", children: "Review before saving" })] }), _jsx("span", { className: "draft-status", children: "Not saved" })] }), _jsxs("label", { children: ["Exact backend capability", _jsxs("select", { value: capabilityDraft.capabilityId, onChange: (event) => setCapabilityDraft({ ...capabilityDraft, capabilityId: event.target.value }), disabled: capabilityBusy, children: [_jsx("option", { value: "", children: "Choose a catalog entry" }), capabilityDraft.capabilities.map((item) => _jsxs("option", { value: item.id, children: [item.id, " \u00B7 ", item.status, " \u00B7 ", item.effect] }, item.id))] })] }), capabilityDraft.capabilityId && _jsx("p", { className: "capability-chat-selected", children: capabilityDraft.capabilities.find((item) => item.id === capabilityDraft.capabilityId)?.summary }), _jsxs("label", { children: ["Request summary", _jsx("input", { value: capabilityDraft.summary, maxLength: 500, onChange: (event) => setCapabilityDraft({ ...capabilityDraft, summary: event.target.value }), disabled: capabilityBusy })] }), _jsxs("label", { children: ["Requested scope", _jsx("textarea", { value: capabilityDraft.requestedScope, maxLength: 1000, rows: 3, placeholder: "Describe the exact scope to review", onChange: (event) => setCapabilityDraft({ ...capabilityDraft, requestedScope: event.target.value }), disabled: capabilityBusy })] }), _jsx("p", { children: "This only saves a review proposal. It does not authorize a capability or run a job." }), _jsxs("div", { className: "draft-actions", children: [_jsx("button", { type: "button", className: "secondary-action", onClick: () => setCapabilityDraft(null), disabled: capabilityBusy, children: "Discard" }), _jsx("button", { type: "button", className: "primary-action", onClick: () => void saveCapabilityProposal(), disabled: capabilityBusy || !capabilityDraft.capabilityId || !capabilityDraft.summary.trim() || !capabilityDraft.requestedScope.trim(), children: capabilityBusy ? 'Saving…' : 'Save proposal' })] })] }), capabilityProposals.map((proposal) => _jsxs("article", { className: "capability-chat-saved", children: [_jsxs("div", { children: [_jsx("strong", { children: proposal.capability_id }), _jsxs("span", { children: [proposal.status, " \u00B7 revision ", proposal.revision] })] }), _jsx("p", { children: proposal.summary }), _jsxs("p", { children: [_jsx("strong", { children: "Requested scope:" }), " ", proposal.requested_scope] }), _jsx("code", { children: proposal.id }), proposal.status === 'PENDING_REVIEW' && _jsx("button", { type: "button", className: "secondary-action", onClick: () => void cancelChatProposal(proposal), disabled: capabilityBusy, children: "Cancel proposal" })] }, proposal.id)), draft && _jsxs("section", { className: "agent-draft-card", "aria-labelledby": "draft-title", children: [_jsxs("div", { className: "draft-heading", children: [_jsxs("div", { children: [_jsx("p", { className: "section-eyebrow", children: "AI-assisted draft" }), _jsx("h3", { id: "draft-title", children: "Review and edit before saving" })] }), _jsx("span", { className: "draft-status", children: "Not created" })] }), _jsxs("div", { className: "draft-fields", children: [_jsxs("label", { children: ["Name", _jsx("input", { value: draft.name, maxLength: 120, onChange: (event) => setDraft({ ...draft, name: event.target.value }), disabled: creatingDraft })] }), _jsxs("label", { children: ["Description", _jsx("textarea", { value: draft.description, maxLength: 1000, rows: 2, onChange: (event) => setDraft({ ...draft, description: event.target.value }), disabled: creatingDraft })] }), _jsxs("label", { children: ["Agent type", _jsxs("select", { value: draft.type, onChange: (event) => setDraft({ ...draft, type: event.target.value }), disabled: creatingDraft, children: [_jsx("option", { value: "rag", children: "RAG" }), _jsx("option", { value: "tool", children: "Tool" }), _jsx("option", { value: "multi-agent", children: "Multi-agent" })] })] }), _jsxs("label", { children: ["Confirmed Ollama model", _jsxs("select", { value: draft.model_id ?? '', onChange: (event) => setDraft({ ...draft, provider_id: 'ollama-cloud', model_id: event.target.value }), disabled: creatingDraft || loadingDraftModels || draftModels.length === 0, children: [_jsx("option", { value: "", children: loadingDraftModels ? 'Loading models…' : 'Select a confirmed model' }), draftModels.map((model) => _jsxs("option", { value: model.model_id, children: [model.display_name, " \u00B7 ", model.source] }, model.model_id))] })] }), _jsxs("label", { className: "draft-prompt-field", children: ["System prompt", _jsx("textarea", { value: draft.system_prompt, maxLength: 12000, rows: 6, onChange: (event) => setDraft({ ...draft, system_prompt: event.target.value }), disabled: creatingDraft })] })] }), _jsxs("p", { className: "draft-model-note", role: draftModelsError ? 'alert' : 'status', children: [draftModelsError || (loadingDraftModels ? 'Checking models from the configured backend…' : 'Model choices come from the configured provider and are not inferred from a public catalog.'), draftModelsError && _jsx("button", { type: "button", onClick: onOpenProviderSettings, children: "Open provider settings" })] }), _jsxs("details", { className: "draft-advanced", children: [_jsx("summary", { children: "Advanced details" }), _jsxs("p", { children: [_jsx("strong", { children: "Tools:" }), " ", draft.tools.length ? draft.tools.join(', ') : 'No tools selected'] }), _jsx("p", { children: "Creating this profile does not grant tool execution or app-control permissions." })] }), _jsxs("div", { className: "draft-actions", children: [_jsx("button", { type: "button", className: "secondary-action", onClick: cancelDraft, disabled: creatingDraft, children: "Cancel proposal" }), _jsx("button", { type: "button", className: "primary-action", onClick: () => void createDraft(), disabled: creatingDraft || loadingDraftModels || draftModels.length === 0 || !draft.name.trim() || !draft.description.trim() || !draft.system_prompt.trim() || draft.provider_id !== 'ollama-cloud' || !draft.model_id?.trim() || !draftModels.some((model) => model.model_id === draft.model_id), children: creatingDraft ? 'Creating…' : 'Create agent' })] })] }), createdNotice && _jsx("p", { className: "success-state", role: "status", children: createdNotice }), error && _jsxs("p", { className: "chat-error", role: "alert", children: [error, error.toLowerCase().includes('ollama') || error.toLowerCase().includes('provider') ? _jsx("button", { type: "button", onClick: onOpenProviderSettings, children: "Open provider settings" }) : null] }), sending && _jsx("p", { className: "muted-state", role: "status", children: "Waiting for Ollama\u2026" }), _jsx("div", { ref: messagesEndRef })] }), _jsxs("form", { className: "control-chat-composer", onSubmit: (event) => void sendMessage(event), children: [_jsx("label", { className: "visually-hidden", htmlFor: "control-chat-input", children: "Message the assistant or selected agent" }), _jsx("textarea", { id: "control-chat-input", rows: 2, value: input, onChange: (event) => setInput(event.target.value), onKeyDown: (event) => {
                                    if (event.key !== 'Enter' || event.shiftKey || event.nativeEvent.isComposing || event.repeat)
                                        return;
                                    event.preventDefault();
                                    void sendMessage();
                                }, placeholder: activeConversation?.status && activeConversation.status !== 'active' ? 'Restore this conversation or start a new one to continue.' : selectedAgent ? `Message ${selectedAgent.config.name}.` : 'Ask a question, list agents, create an agent, or open a view.', disabled: sending || Boolean(activeConversation && activeConversation.status !== 'active') }), _jsxs("div", { className: "chat-composer-actions", children: [_jsxs("label", { className: "workspace-read-toggle", children: [_jsx("input", { type: "checkbox", checked: allowWorkspaceRead, onChange: (event) => setAllowWorkspaceRead(event.target.checked), disabled: sending || Boolean(activeConversation && activeConversation.status !== 'active') }), _jsxs("span", { children: ["Authorize exact project files for this message ", _jsx("small", { children: "Only the paths below, once, for this conversation turn" })] })] }), _jsx("button", { className: "primary-action", type: "submit", disabled: sending || !input.trim() || Boolean(activeConversation && activeConversation.status !== 'active'), children: sending ? 'Sending.' : 'Send' })] }), allowWorkspaceRead && _jsxs("label", { className: "workspace-read-paths", children: ["Project-relative file paths, one per line", _jsx("textarea", { rows: 3, value: workspaceReadPaths, onChange: (event) => setWorkspaceReadPaths(event.target.value), placeholder: 'src/api/server.py\nsrc/agent_tools/workspace_read.py', disabled: sending })] })] }), _jsx("div", { className: "chat-agent-panel-slot", ref: setAgentPanelTarget })] })] }));
}
