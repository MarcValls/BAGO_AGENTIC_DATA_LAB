// @vitest-environment jsdom
/** App/AgentChat wiring. Resource widgets and HTTP are fixtures; no live effects claimed. */
import React from 'react'
import {webcrypto, createHash} from 'node:crypto'
import {afterEach, beforeEach, expect, it, vi} from 'vitest'
import {cleanup, fireEvent, render, screen, waitFor, within} from '@testing-library/react'
import {resetLocaleForTests, setLocale, t} from '../../../src/i18n'

const prepared = vi.hoisted(() => vi.fn())
vi.mock('axios', () => ({default: {get: vi.fn(async () => ({data: {}}))}}))
vi.mock('../../../src/components/RuntimeStatusBar', () => ({default: () => null}))
vi.mock('../../../src/components/TaskExecutionPanel', () => ({default: ({taskText, sourceIdentity}: any) => <button data-source={sourceIdentity} onClick={() => prepared(taskText, sourceIdentity)}>Preparar ejecución real fixture</button>}))
vi.mock('../../../src/components/WorkspaceManager', () => ({default: () => <h3>Workspace inline fixture</h3>}))
vi.mock('../../../src/components/AgentTasks', () => ({default: ({initialAgentId}: any) => <h3>Tareas inline fixture {initialAgentId}</h3>}))
vi.mock('../../../src/components/AgentBuilder', () => ({default: ({onBack}: any) => <div><h3>Constructor inline fixture</h3><button onClick={onBack}>Volver a agentes fixture</button></div>}))
vi.mock('../../../src/components/AgentManagement', () => ({default: ({onCreate, onTest}: any) => <div><h3>Agentes inline fixture</h3><button onClick={onCreate}>Crear perfil fixture</button><button onClick={() => onTest('agent-saved')}>Tareas del perfil fixture</button></div>}))
vi.mock('../../../src/components/AgentEvaluationLab', () => ({default: () => <h3>Laboratorio inline fixture</h3>}))
vi.mock('../../../src/components/ProviderSettings', () => ({default: ({onExit}: any) => <div><h3>Proveedores inline fixture</h3><button onClick={onExit}>Salir proveedor fixture</button></div>}))
vi.mock('../../../src/components/CognitionSettings', () => ({readCognitiveMode: () => 'baseline', default: ({onRequestWorkspaceSelection}: any) => <div><h3>Cognición inline fixture</h3><button onClick={onRequestWorkspaceSelection}>Carpeta desde cognición fixture</button></div>}))
vi.mock('../../../src/components/WhatsAppSettings', () => ({default: () => <h3>WhatsApp inline fixture</h3>}))
vi.mock('../../../src/components/ToolsConnectionsView', () => ({default: () => <h3>Conexiones inline fixture</h3>}))
vi.mock('../../../src/components/AgentToolsView', () => ({default: ({onOpenConnections}: any) => <div><h3>Herramientas inline fixture</h3><button onClick={onOpenConnections}>Abrir conexiones fixture</button></div>}))
vi.mock('../../../src/components/Communications', () => ({default: ({draftId, onOpenFull}: any) => <div><h3>Comunicaciones inline fixture</h3><span>{draftId}</span><button onClick={() => onOpenFull('draft-exact')}>Abrir borrador fixture</button></div>}))
vi.mock('../../../src/components/Contacts', () => ({default: () => <h3>Contactos inline fixture</h3>}))
vi.mock('../../../src/components/JobHistory', () => ({default: () => <h3>Trabajos inline fixture</h3>}))
vi.mock('../../../src/components/ChatInspection', () => ({default: ({selection, view}: any) => <section aria-label="Inspección inline fixture"><code>{JSON.stringify(selection)}</code><span>{view}</span></section>}))
vi.mock('../../../src/components/CapabilityManager', async importOriginal => ({...await importOriginal<any>(), default: ({onNavigate}: any) => <div><h3>Capacidades inline fixture</h3><button onClick={() => onNavigate('connections')}>Configurar conexión fixture</button></div>}))
import App from '../../../src/App'
import AgentChat from '../../../src/components/AgentChat'

beforeEach(() => {
  localStorage.clear(); sessionStorage.clear(); resetLocaleForTests(); setLocale('es'); prepared.mockClear()
  vi.stubGlobal('crypto', webcrypto)
  HTMLElement.prototype.scrollIntoView = vi.fn()
  HTMLDialogElement.prototype.showModal = function () {this.setAttribute('open', '')}
  HTMLDialogElement.prototype.close = function () {this.removeAttribute('open')}
})
afterEach(() => {cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks()})

async function setup(view: string, requestText = `Abre el recurso ${view}`, direct = false) {
  let conversation: any
  const mutations: Array<{path: string; body: any}> = []
  const fetch = vi.fn(async (path: string, init?: RequestInit) => {
    const body = init?.body ? JSON.parse(String(init.body)) : null
    if (init?.method && init.method !== 'GET') mutations.push({path, body})
    const ok = (value: unknown) => ({ok: true, status: 200, json: async () => value})
    if (path === '/api/project-folders/v1/active') return ok({project_id: 'project-inline', root: 'D:/inline', title: 'Inline', scope: 'project'})
    if (path.startsWith('/api/conversations?')) return ok({conversations: []})
    if (path === '/api/agents/list') return ok({agents: []})
    if (path === '/api/providers/selection') return ok({provider_id: null, model_id: null})
    if (path === '/api/conversations') {conversation = {id: 'conv-inline', owner_kind: 'assistant', owner_id: 'app-assistant', title: 'Solicitud inline', status: 'active', revision: 0, messages: []}; return ok(conversation)}
    if (path === '/api/chat/control') {
      conversation = {...conversation, revision: 2, messages: [{id: 'human-exact', role: 'user', content: body.message}, {id: 'answer-exact', role: 'assistant', content: 'Respuesta de la solicitud', references: {trace: {trace_id: 'trace-496fac766f384348', trace_state: 'persisted'}}}]}
      return ok({operation: 'confirm_navigation', navigation: {view}, conversation})
    }
    return ok({models: [], agents: [], proposals: []})
  })
  vi.stubGlobal('fetch', fetch)
  const navigate = vi.fn()
  render(direct ? <AgentChat historySelection="explicit" cognitiveMode="baseline" onNavigate={navigate} onOpenProviderSettings={() => {}} onOpenCognitionSettings={() => {}} renderInlineView={inlineView => <h3>Direct inline {inlineView}</h3>} /> : <App />)
  const composer = screen.getByRole('textbox', {name: t('commerce.message_the_assistant_or_selected_agent')}) as HTMLTextAreaElement
  fireEvent.change(composer, {target: {value: requestText}})
  fireEvent.click(screen.getByRole('button', {name: 'Enviar', exact: true}))
  const answer = await screen.findByRole('article', {name: 'Asistente'})
  return {composer, answer, mutations, fetch, navigate}
}

it.each([
  ['workspace', 'Workspace inline fixture'], ['runner', 'Tareas inline fixture'], ['control', 'Tareas inline fixture'],
  ['builder', 'Constructor inline fixture'], ['evaluation_lab', 'Laboratorio inline fixture'], ['provider_settings', 'Proveedores inline fixture'],
  ['cognition_settings', 'Cognición inline fixture'], ['whatsapp_settings', 'WhatsApp inline fixture'], ['communications', 'Comunicaciones inline fixture'],
  ['capabilities', 'Capacidades inline fixture'], ['jobs', 'Trabajos inline fixture'],
])('opens offered %s inside its response while preserving the same chat and composer', async (view, heading) => {
  const {composer, answer} = await setup(view)
  fireEvent.click(within(answer).getByRole('button', {name: 'Abrir aquí en el chat'}))
  expect(within(answer).getByRole('heading', {name: heading})).toBeTruthy()
  expect(screen.getByRole('textbox', {name: t('commerce.message_the_assistant_or_selected_agent')})).toBe(composer)
  expect(screen.getByRole('main').getAttribute('aria-label')).toContain('Chat')
  expect(screen.queryByRole('button', {name: /Volver al chat/})).toBeNull()
})

it('keeps nested capability callbacks inline and the resource close preserves the request/response', async () => {
  const {answer, composer} = await setup('capabilities')
  fireEvent.click(within(answer).getByRole('button', {name: 'Abrir aquí en el chat'}))
  fireEvent.click(within(answer).getByRole('button', {name: 'Configurar conexión fixture'}))
  expect(within(answer).getByRole('heading', {name: 'Conexiones inline fixture'})).toBeTruthy()
  fireEvent.click(within(answer).getByRole('button', {name: 'Cerrar recurso'}))
  expect(within(answer).queryByRole('heading', {name: 'Conexiones inline fixture'})).toBeNull()
  expect(within(answer).getByText('Respuesta de la solicitud')).toBeTruthy()
  expect(composer.isConnected).toBe(true)
})

it('pins inline inspection to the clicked response trace, not the global inspector selection', async () => {
  const {answer, composer} = await setup('summary')
  fireEvent.click(within(answer).getByRole('button', {name: 'Inspeccionar ejecución'}))
  const inspection = within(answer).getByRole('region', {name: 'Inspección inline fixture'})
  expect(inspection.textContent).toContain('conv-inline')
  expect(inspection.textContent).toContain('trace-496fac766f384348')
  expect(inspection.textContent).toContain('inspector')
  expect(composer.isConnected).toBe(true)
})

it('mounts a dormant task action inside the response and binds it to the exact human request and source digest', async () => {
  const text = 'Explica cómo mover un archivo; todavía no lo ejecutes.'
  const {answer, mutations} = await setup('workspace', text)
  const task = await within(answer).findByRole('button', {name: 'Preparar ejecución real fixture'})
  expect(prepared).not.toHaveBeenCalled()
  expect(mutations.map(row => row.path)).toEqual(['/api/conversations', '/api/chat/control'])
  const digest = createHash('sha256').update(JSON.stringify(['project-inline', 'D:/inline', 'assistant', 'app-assistant', 'conv-inline', 'human-exact', text, 'answer-exact', 'Respuesta de la solicitud'])).digest('hex')
  expect(task.getAttribute('data-source')).toBe(`chat:${digest}`)
  fireEvent.click(task)
  expect(prepared).toHaveBeenCalledExactlyOnceWith(text, `chat:${digest}`)
})

it('does not call the outer navigation callback when an inline renderer is available', async () => {
  const {answer, navigate, composer} = await setup('workspace', 'Abre los archivos aquí', true)
  fireEvent.click(within(answer).getByRole('button', {name: 'Abrir aquí en el chat'}))
  expect(within(answer).getByRole('heading', {name: 'Direct inline workspace'})).toBeTruthy()
  expect(navigate).not.toHaveBeenCalled()
  expect(composer.isConnected).toBe(true)
})

it.each(['inspector', 'summary', 'retrieval', 'authorization', 'traces', 'evaluation'])('keeps offered %s inspection on the requesting response and its trace', async view => {
  const {answer, composer} = await setup(view)
  fireEvent.click(within(answer).getByRole('button', {name: 'Abrir aquí en el chat'}))
  const resource = within(answer).getByRole('region', {name: 'Inspección inline fixture'})
  expect(resource.textContent).toContain('conv-inline')
  expect(resource.textContent).toContain('trace-496fac766f384348')
  expect(within(resource).getByText(view === 'traces' ? 'trace' : view)).toBeTruthy()
  expect(composer.isConnected).toBe(true)
})

it('starts the real App with chat usable and Project collapsed, then opens it only on request',async()=>{
 const {composer}=await setup('workspace')
 expect(composer.isConnected).toBe(true)
 const toggle=screen.getByRole('button',{name:t('commerce.project_panel_title'),exact:true})
 expect(toggle.getAttribute('aria-expanded')).toBe('false')
 expect(screen.queryByRole('region',{name:t('commerce.project_context_label')})).toBeNull()
 fireEvent.click(toggle)
 expect(toggle.getAttribute('aria-expanded')).toBe('true')
 expect(screen.getByRole('region',{name:t('commerce.project_context_label')})).toBeTruthy()
 expect(screen.getByRole('textbox',{name:t('commerce.message_the_assistant_or_selected_agent')})).toBe(composer)
})
