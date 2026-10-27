// @vitest-environment jsdom
import React from 'react'
import {afterEach, beforeEach, expect, it, vi} from 'vitest'
import {act, cleanup, fireEvent, render, screen, waitFor} from '@testing-library/react'
import AgentChat from '../../src/components/AgentChat'
import {resetLocaleForTests, setLocale, t} from '../../src/i18n'

beforeEach(() => {
  localStorage.clear()
  resetLocaleForTests()
  setLocale('es')
  HTMLElement.prototype.scrollIntoView = vi.fn()
})
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks() })

// Exact 1002-character live regression input, embedded so CI needs no external evidence.
const parentMission = String.raw`Delega al agente guardado PRUEBA · Operador documental esta misión sintética de aceptación con sus herramientas documentales. Carpeta C:\BAGO_TESTS\JAEGER_ADL_20261024\source\evidence\native-live-90d4-20261025\corpus. Hay exactamente cuatro documentos: pedidos.csv, entregas.csv, catalogo.json y condiciones.txt. Tarea: inventaría los cuatro archivos con document_inventory; léelos juntos con document_extract; compara por order_id y sku las cantidades pedidas/entregadas, comprueba precios contra catálogo y explica cualquier discrepancia con referencias a archivos y posiciones. Exporta el bundle_id REAL obtenido a CSV con document_export en la carpeta de salida que autorice en la tarjeta; no inventes bundle_id ni recibos. Devuelve cobertura, resultado y referencia del informe exportado. No uses development_*, filesystem_plan ni crees agentes. No modifiques los documentos, no renombres ni envíes comunicaciones. Prepara la delegación con este agente y espera la revisión de carpeta/exportación.`

type Call = {url: string; method: string; body: any}
const reply = (body: unknown, status = 200) => ({ok: status < 400, status, json: async () => body})
async function fixture(mode: 'baseline' | 'bago5' = 'baseline', fail = false) {
  const calls: Call[] = []
  const onNavigate = vi.fn()
  let conversation: any = null
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    const method = init?.method ?? 'GET'
    const body = init?.body ? JSON.parse(String(init.body)) : null
    calls.push({url, method, body})
    if (url === '/api/agents/list') return reply({agents: []})
    if (url === '/api/providers/selection') return reply({provider_id: null, model_id: null})
    if (url === '/api/project-folders/v1/active') return reply({project_id: 'project-1', title: 'Proyecto de prueba', scope: 'project', root: 'D:/work/project'})
    if (url === '/api/project-permissions') return reply({project_id: 'project-1', root: 'D:/work/project', binding: {workspace_root: 'D:/work/project', revision: 4}, revision: 3, state: 'active', read_directories: ['src'], write_directories: ['docs']})
    if (url === '/api/project-permissions/directories') return reply({project_id: 'project-1', root: 'D:/work/project', binding: {workspace_root: 'D:/work/project', revision: 4}, revision: 3, directory: '.', directories: [{name: 'src', path: 'src'}, {name: 'docs', path: 'docs'}], truncated: false})
    if (url.startsWith('/api/conversations?')) return reply({conversations: []})
    if (url === '/api/conversations' && method === 'POST') {
      conversation = {id: 'conv-shortcuts', owner_kind: 'assistant', owner_id: 'app-assistant', title: 'Fixture', revision: 1, status: 'active', messages: []}
      return reply(conversation)
    }
    if (url === '/api/capabilities') return reply({capabilities: [{id: 'workspace.read_text', name: 'Lectura fixture', status: 'AVAILABLE', effect: 'read'}]})
    if (url === '/api/web-read/authorizations') return reply({authorization_id: 'explicit-web-grant', allowed_origins: ['https://example.com']})
    if (url === '/api/chat/control') {
      if (fail) return reply({detail: 'Fallo sintético del proveedor'}, 503)
      conversation = {...conversation, revision: 3, messages: [{id: 'user-fixture', role: 'user', content: body.message}, {id: 'assistant-fixture', role: 'assistant', content: 'Respuesta fixture'}]}
      return reply({operation: body.operation, conversation, ...(body.operation === 'list_agents' ? {agents: []} : {})})
    }
    return reply({models: [], proposals: []})
  }))
  const view = render(<AgentChat historySelection="explicit" cognitiveMode={mode} onNavigate={onNavigate} onOpenProviderSettings={vi.fn()} onOpenCognitionSettings={vi.fn()}/>)
  await waitFor(() => expect(calls.some(call => call.url.startsWith('/api/conversations?'))).toBe(true))
  await act(async () => {})
  const input = screen.getByRole('textbox', {name: 'Mensaje al asistente o agente seleccionado'}) as HTMLTextAreaElement
  const mutations = () => calls.filter(call => call.method !== 'GET' && call.url !== '/api/project-permissions/directories')
  const control = () => calls.filter(call => call.url === '/api/chat/control')
  return {calls, input, mutations, control, view, onNavigate}
}
async function send(input: HTMLTextAreaElement, message: string) {
  fireEvent.change(input, {target: {value: message}})
  const button = screen.getByRole('button', {name: 'Enviar', exact: true}) as HTMLButtonElement
  await waitFor(() => expect(button.disabled).toBe(false))
  fireEvent.click(button)
}

it.each(['baseline', 'bago5'] as const)('sends the exact live mission once through the model route in %s without grants or capability shortcuts', async mode => {
  expect(parentMission).toHaveLength(1002)
  const f = await fixture(mode)
  expect(f.mutations()).toEqual([])
  await send(f.input, parentMission)
  await screen.findByText('Respuesta fixture')
  expect(f.control()).toHaveLength(1)
  expect(f.control()[0].body).toEqual({operation: 'chat', message: parentMission, conversation_id: 'conv-shortcuts', revision: 1, cognitive_mode: mode})
  expect(f.mutations().map(call => call.url)).toEqual(['/api/conversations', '/api/chat/control'])
  expect(f.calls.some(call => call.url === '/api/capabilities')).toBe(false)
})

const naturalMessages = [
  'El agente documental tiene el encargo. Hay exactamente cuatro documentos y tengo sus nombres; resume sus diferencias.',
  'No lista mis agentes',
  'No listes mis agentes; resume los documentos.',
  'No puedes crear agentes; trabaja con el perfil guardado y devuelve la tarea si no encaja.',
  'No muestres capacidades ni prepares una propuesta de acceso.',
  '«Lista mis agentes»',
  'El documento dice "Lista mis agentes". Explica la frase.',
  'Lista mis agentes y delega el informe al documental.',
  'Lista mis agentes. Después revisa el informe.',
  'Muestra mis agentes\nNo ejecutes ninguna herramienta.',
  'Explica por qué el formulario pregunta qué agentes hay, sin listar nada.',
  'Usa workspace.read_text para resumir sample_a.py e informa del estado final.',
  'Delega al agente una propuesta comercial y comprueba su capacidad de entrega.',
  'Proponer capacidad workspace.read_text y luego leer sample_a.py',
  'En el documento aparece qué puedes hacer; resume su alcance.',
  'Hay cuatro documentos. Tengo un agente documental para revisarlos.',
  'No quiero una lista de agentes ni un catálogo de capacidades.',
  'Lee el estado de mcp.execute en el informe, no consultes el catálogo.',
]
it.each(naturalMessages.flatMap(message => (['baseline', 'bago5'] as const).map(mode => [mode, message] as const)))('keeps natural/negated/quoted instructions on chat (%s): %s', async (mode, message) => {
  const f = await fixture(mode)
  await send(f.input, message)
  await screen.findByText('Respuesta fixture')
  expect(f.control()).toHaveLength(1)
  expect(f.control()[0].body).toEqual({operation: 'chat', message, conversation_id: 'conv-shortcuts', revision: 1, cognitive_mode: mode})
  expect(f.calls.some(call => call.url === '/api/capabilities')).toBe(false)
  expect(f.mutations().map(call => call.url)).toEqual(['/api/conversations', '/api/chat/control'])
})

it.each(['Lista mis agentes', 'Listar mis agentes', 'Muestra mis agentes', '¿Qué agentes hay?', '¿Cuáles son mis agentes?', 'Qué agentes tengo', 'List my agents', 'Show my agents', 'Which agents are available?', 'What agents do I have?', '  LISTA   MIS AGENTES!  '])('retains complete agent shortcuts without changing their submitted text: %s', async message => {
  const f = await fixture()
  await send(f.input, message)
  await screen.findByText('Respuesta fixture')
  expect(f.control()).toHaveLength(1)
  expect(f.control()[0].body).toEqual({operation: 'list_agents', message: message.trim(), conversation_id: 'conv-shortcuts', revision: 1})
  expect(f.mutations().map(call => call.url)).toEqual(['/api/conversations', '/api/chat/control'])
})

it.each(['Lista capacidades', '¿Cuáles son las capacidades?', 'Consulta el catálogo de capacidades', 'List capabilities', 'Show the capability catalog', 'Estado de workspace.read_text', 'Status of mcp.execute', 'Lista workspace.read_text', '¿Qué es agent.run?', 'What is sandbox.execute?'])('retains complete catalog shortcuts without dispatching chat or authorizing tools: %s', async message => {
  const f = await fixture()
  await send(f.input, message)
  await waitFor(() => expect(f.view.container.textContent).toContain('Lectura fixture'))
  expect(f.calls.filter(call => call.url === '/api/capabilities')).toHaveLength(1)
  expect(f.control()).toEqual([])
  expect(f.mutations().map(call => call.url)).toEqual(['/api/conversations'])
  expect(f.view.container.textContent).toContain(message)
})

it.each(['Proponer capacidad workspace.read_text', 'Propuesta de capacidad', 'Propose a capability mcp.execute', 'Propose access to sandbox.execute'])('opens only a proposal draft for a complete explicit request: %s', async message => {
  const f = await fixture()
  await send(f.input, message)
  await screen.findByRole('region', {name: t('commerce.review_before_saving')})
  expect(f.calls.filter(call => call.url === '/api/capabilities')).toHaveLength(1)
  expect(f.control()).toEqual([])
  expect(f.mutations().map(call => call.url)).toEqual(['/api/conversations'])
})

it.each([['baseline', '¡Hola!', 'help'], ['baseline', 'What can you do?', 'help'], ['bago5', 'Hola', 'chat'], ['bago5', '¿Qué puedes hacer?', 'chat']] as const)('preserves whole-message help behavior (%s): %s', async (mode, message, operation) => {
  const f = await fixture(mode)
  await send(f.input, message)
  await screen.findByText('Respuesta fixture')
  expect(f.control()[0].body).toMatchObject({operation, message})
  expect(f.control()[0].body.cognitive_mode).toBe(operation === 'chat' ? mode : undefined)
})

it.each(['Abre el Decision Inspector', 'Open the Decision Inspector', 'Quiero crear un agente para revisar documentos'])('preserves model routing for navigation and agent creation requests: %s', async message => {
  const f = await fixture()
  await send(f.input, message)
  await screen.findByText('Respuesta fixture')
  expect(f.control()[0].body).toMatchObject({operation: 'chat', message})
  expect(f.onNavigate).not.toHaveBeenCalled()
  expect(f.mutations().map(call => call.url)).toEqual(['/api/conversations', '/api/chat/control'])
})

it('prefills the existing suggestion without sending or creating an empty conversation', async () => {
  const f = await fixture()
  fireEvent.click(screen.getByRole('button', {name: 'Listar mis agentes'}))
  expect(f.input.value).toBe('Lista mis agentes')
  expect(f.mutations()).toEqual([])
  fireEvent.change(f.input, {target: {value: ' \n '}})
  expect((screen.getByRole('button', {name: 'Enviar', exact: true}) as HTMLButtonElement).disabled).toBe(true)
  expect(f.mutations()).toEqual([])
})

it('uses saved project permissions independently from the explicit one-turn web grant', async () => {
  const f = await fixture()
  expect(screen.getByText('src')).toBeTruthy()
  expect(screen.queryByLabelText('Permitir lectura de archivos del proyecto')).toBeNull()
  expect(screen.queryByLabelText('Rutas relativas al proyecto')).toBeNull()
  fireEvent.click(screen.getByLabelText('Permitir lectura web p\u00fablica'))
  fireEvent.change(screen.getByLabelText('URL HTTPS de entrada \u00b7 una por l\u00ednea'), {target: {value: 'https://example.com/'}})
  await send(f.input, naturalMessages[0])
  await screen.findByText('Respuesta fixture')
  expect(f.control()[0].body).toMatchObject({operation: 'chat', web_read_authorization_id: 'explicit-web-grant'})
  expect(f.control()[0].body).not.toHaveProperty('workspace_read_authorization_id')
  const grants = f.mutations().filter(call => call.url.endsWith('/authorizations'))
  expect(grants).toHaveLength(1)
  for (const grant of grants) expect(grant.body).toMatchObject({owner_kind: 'assistant', owner_id: 'app-assistant', conversation_id: 'conv-shortcuts', revision: 1})
  expect((screen.getByLabelText('Permitir lectura web p\u00fablica') as HTMLInputElement).checked).toBe(false)
})

it('keeps provider errors visible and never retries a natural mission automatically', async () => {
  const f = await fixture('bago5', true)
  await send(f.input, parentMission)
  expect((await screen.findByRole('alert')).textContent).toContain('Fallo sintético del proveedor')
  expect(f.control()).toHaveLength(1)
  expect(f.control()[0].body.operation).toBe('chat')
})
