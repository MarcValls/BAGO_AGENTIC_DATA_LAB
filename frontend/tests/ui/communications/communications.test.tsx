// @vitest-environment jsdom
import React from 'react'
import {resetLocaleForTests,setLocale,t} from '../../../src/i18n'
beforeEach(()=>{localStorage.clear();resetLocaleForTests();setLocale('es')})
import { beforeEach, afterEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import Communications from '../../../src/components/Communications'
import AgentChat from '../../../src/components/AgentChat'
import {conversationButton} from '../../helpers/conversation-library'
const contact = { id: 'c1', name: 'Cliente ficticio', phone: '+34600000001' }
const draft = { id: 'd1', revision: 'a'.repeat(64), contact_id: 'c1', recipient: contact, text: 'Resultado revisable', attachments: [], schedule: { kind: 'now', timezone: 'Europe/Madrid', at: null, time: null, weekdays: [] }, state: 'draft', next_run_at: null, created_at: '', updated_at: '', conversation_id: 'conversation1', last_error: null }
const response = (body: unknown, status = 200) => ({ ok: status < 400, status, json: async () => body })
afterEach(() => { cleanup(); vi.unstubAllGlobals() })
function fixture(mutate?: (url: string, init: RequestInit) => unknown) {
  const calls: Array<{ url: string; body: any }> = []
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method) { calls.push({ url, body: JSON.parse(String(init.body)) }); return mutate?.(url, init) ?? response(draft) }
    if (url.endsWith('/contacts')) return response({ contacts: [contact] })
    if (url.endsWith('/drafts')) return response({ drafts: [draft] })
    if (url.endsWith('/runs')) return response({ runs: [] })
    return response(draft)
  }))
  return calls
}
it('shows loading then empty state; network error is visible', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => response({ detail: 'Servicio no disponible' }, 503)))
  render(<Communications />)
  expect(screen.getByRole('status').textContent).toContain('Cargando')
  expect((await screen.findByRole('alert')).textContent).toContain('Servicio no disponible')
})
it('loads canonical server draft by ID in embedded mode and requires separate review before confirmation', async () => {
  const calls = fixture()
  render(<Communications inline draftId="d1" conversationId="conversation1" />)
  await screen.findByDisplayValue('Resultado revisable')
  const confirm = screen.getByRole('button', { name: 'Confirmar y enviar ahora' }) as HTMLButtonElement
  expect(confirm.disabled).toBe(true)
  expect(calls).toHaveLength(0)
  fireEvent.click(screen.getByLabelText(/He revisado/))
  fireEvent.click(confirm)
  await waitFor(() => expect(calls[0].url).toBe('/api/communications/drafts/d1/confirm'))
  expect(calls[0].body).toEqual({ expected_revision: draft.revision, confirmed: true })
})
it('preserves local message on 409 and blocks confirmation until resolving and saving', async () => {
  fixture(() => response({ detail: 'Revisión conflictiva' }, 409))
  render(<Communications inline draftId="d1" />)
  await screen.findByDisplayValue('Resultado revisable')
  fireEvent.change(screen.getByRole('textbox',{name:'Mensaje'}), { target: { value: 'Mi edición local' } })
  fireEvent.click(screen.getByRole('button', { name: 'Guardar y preparar revisión' }))
  await screen.findByText('El borrador cambió en otra sesión')
  expect((screen.getByRole('textbox',{name:'Mensaje'}) as HTMLTextAreaElement).value).toBe('Mi edición local')
  expect(screen.queryByRole('button', { name: 'Confirmar y enviar ahora' })).toBeNull()
  fireEvent.click(screen.getByRole('button', { name: 'Conservar mis cambios para revisar' }))
  expect((screen.getByRole('textbox',{name:'Mensaje'}) as HTMLTextAreaElement).value).toBe('Mi edición local')
})
it('prepares weekly schedule, exact paths, and conversation identity without sending', async () => {
  const calls = fixture()
  render(<Communications />)
  await screen.findByRole('textbox', { name: 'Mensaje' })
  fireEvent.change(screen.getByLabelText('Destinatario'), { target: { value: 'c1' } })
  fireEvent.change(screen.getByRole('textbox',{name:'Mensaje'}), { target: { value: 'Informe semanal' } })
  fireEvent.change(screen.getByLabelText(/Adjuntos del espacio de trabajo/), { target: { value: 'salida/informe.pdf' } })
  fireEvent.change(screen.getByLabelText('Cuándo'), { target: { value: 'weekly' } })
  fireEvent.change(screen.getByLabelText('Hora local'), { target: { value: '10:15' } })
  fireEvent.click(screen.getByLabelText('Lunes'))
  fireEvent.click(screen.getByRole('button', { name: 'Guardar y preparar revisión' }))
  await waitFor(() => expect(calls.length).toBe(1))
  expect(calls[0].body.schedule).toEqual({ kind: 'weekly', timezone: 'Europe/Madrid', at: null, time: '10:15', weekdays: [1] })
  expect(calls[0].body.attachments).toEqual(['salida/informe.pdf'])
  expect(calls[0].url).toBe('/api/communications/drafts')
})
it('renders unknown draft state without exposing a confirm action', async () => {
  fixture()
  const fetcher = global.fetch
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => url.endsWith('/d1') ? response({ ...draft, state: 'new-state' }) : fetcher(url, init)))
  render(<Communications inline draftId="d1" />)
  await screen.findByText('Estado no reconocido')
  expect(screen.queryByRole('button', { name: 'Confirmar y enviar ahora' })).toBeNull()
})
it('rehydrates the persisted orchestrator draft reference in chat and opens the same ID full screen', async () => {
  HTMLElement.prototype.scrollIntoView = vi.fn()
  const open = vi.fn()
  const conversation = { id: 'conversation1', owner_kind: 'assistant', owner_id: 'app-assistant', title: 'Comunicación guardada', status: 'active', updated_at: '2026-10-22T10:00:00Z', revision: 2, messages: [{ id: 'message1', role: 'assistant', content: 'Revisa el mensaje', references: { communication_draft: draft } }] }
  vi.stubGlobal('fetch', vi.fn(async (input: string) => {
    const url = String(input)
    if (url === '/api/agents/list') return response({ agents: [] })
    if (url === '/api/providers/chat-models') return response({ models: [] })
    if (url === '/api/providers/selection') return response(null)
    if (url.startsWith('/api/conversations?')) return response({ conversations: [conversation] })
    if (url === '/api/conversations/conversation1') return response(conversation)
    if (url.endsWith('/contacts')) return response({ contacts: [contact] })
    if (url.endsWith('/drafts')) return response({ drafts: [draft] })
    if (url.endsWith('/runs')) return response({ runs: [] })
    if (url.endsWith('/drafts/d1')) return response(draft)
    throw new Error(`Unexpected fixture request ${url}`)
  }))
  render(<AgentChat onNavigate={() => {}} onOpenCommunication={open} onOpenProviderSettings={() => {}} onOpenCognitionSettings={() => {}} cognitiveMode="baseline" />)
  await screen.findByText('Comunicación guardada')
  fireEvent.click(conversationButton(document, 'Comunicación guardada'))
  await screen.findByRole('heading', { name: 'Revisar comunicación' })
  await screen.findByDisplayValue('Resultado revisable')
  fireEvent.click(screen.getByRole('button', { name: 'Abrir pantalla completa' }))
  expect(open).toHaveBeenCalledWith('d1')
})

