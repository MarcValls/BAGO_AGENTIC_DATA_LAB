// @vitest-environment jsdom
import React from 'react'
import {resetLocaleForTests,setLocale,t} from '../../src/i18n'
beforeEach(()=>{localStorage.clear();resetLocaleForTests();setLocale('es')})
import {beforeEach,afterEach, describe, expect, it, vi} from 'vitest'
import {cleanup, fireEvent, render, screen, waitFor} from '@testing-library/react'
import Contacts from '../../src/components/Contacts'

const response = (body: unknown, status = 200) => ({ok: status < 400, status, json: async () => body})
const contact = {id: 'local-a', name: 'PRUEBA Alfa', phone: '+12025550123', email: '', source: 'local', source_id: '', revision: 'revision-1', created_at: '', updated_at: ''}
const disconnected = {configured: false, connected: false, state: 'disconnected', scope: 'contacts.readonly', live_verified: false, last_error: null}
function stub(extra: (path: string, init?: RequestInit) => unknown = () => undefined, contacts = [contact], status = disconnected) {
  const calls: Array<{path: string; method: string; body: any}> = []
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    const path = String(url).replace('/api/contacts/v1', '')
    calls.push({path, method: init?.method ?? 'GET', body: init?.body ? JSON.parse(String(init.body)) : undefined})
    const override = extra(path, init)
    if (override !== undefined) return override
    if (path.startsWith('/contacts?')) return response({contacts})
    if (path === '/google/status') return response(status)
    throw Error('Unexpected fixture request')
  }))
  return calls
}
afterEach(() => {cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks()})

describe('Contacts UI — simulated API, no Google account or external sends', () => {
  it('shows loading, empty agenda and unconfigured Google distinctly', async () => {
    stub(undefined, [])
    render(<Contacts />)
    expect(screen.getByText('Buscando contactos…')).toBeTruthy()
    expect(await screen.findByText('No hay contactos en esta búsqueda.')).toBeTruthy()
    expect(screen.getByText('Sin configurar')).toBeTruthy()
    fireEvent.click(screen.getByRole('tab',{name:'Google'}))
    expect((screen.getByRole('button', {name: 'Conectar con Google'}) as HTMLButtonElement).disabled).toBe(true)
  })
  it('renders service failures without inventing a connection', async () => {
    stub(() => response({error: {message: 'Servicio no instalado'}}, 503))
    render(<Contacts />)
    expect(await screen.findByRole('alert')).toHaveProperty('textContent', t('common.requestFailed')+'\n'+t('common.originalDiagnostic')+': Servicio no instalado')
    expect(screen.getByText('Sin comprobar')).toBeTruthy()
  })
  it('saves an edited contact using its current revision', async () => {
    const calls = stub((path, init) => path === '/contacts/local-a' && init?.method === 'PUT'
      ? response({...contact, name: 'PRUEBA Alfa editada', revision: 'revision-2'}) : undefined)
    render(<Contacts />)
    fireEvent.click(await screen.findByRole('button', {name: 'Editar PRUEBA Alfa'}))
    fireEvent.change(screen.getByLabelText('Nombre'), {target: {value: 'PRUEBA Alfa editada'}})
    fireEvent.click(screen.getByRole('button', {name: 'Guardar cambios'}))
    await screen.findByText('Contacto guardado en la agenda local.')
    expect(calls.find(call => call.method === 'PUT')?.body).toEqual({name: 'PRUEBA Alfa editada', phone: contact.phone, email: '', expected_revision: 'revision-1'})
  })
  it('requires separate confirmation before deleting and preserves edit after a conflict', async () => {
    const calls = stub((path, init) => path === '/contacts/local-a' && init?.method === 'DELETE'
      ? response({error: {message: 'La revisión cambió; vuelve a abrir el contacto.'}}, 409) : undefined)
    render(<Contacts />)
    fireEvent.click(await screen.findByRole('button', {name: 'Editar PRUEBA Alfa'}))
    fireEvent.click(screen.getByRole('button', {name: 'Eliminar de la agenda local'}))
    const remove = screen.getByRole('button', {name: 'Eliminar contacto local'}) as HTMLButtonElement
    expect(remove.disabled).toBe(true)
    expect(calls.filter(call => call.method === 'DELETE')).toHaveLength(0)
    fireEvent.click(screen.getByLabelText('Confirmo la eliminación de este contacto local.'))
    fireEvent.click(remove)
    expect(await screen.findByRole('alert')).toHaveProperty('textContent', t('common.requestFailed')+'\n'+t('common.originalDiagnostic')+': La revisión cambió; vuelve a abrir el contacto.')
    expect(calls.find(call => call.method === 'DELETE')?.body).toEqual({expected_revision: 'revision-1', confirmed: true})
    expect((screen.getByLabelText('Nombre') as HTMLInputElement).value).toBe('PRUEBA Alfa')
  })
  it('does not equate stored authorization with a verified Google response', async () => {
    stub(undefined, [], {...disconnected, configured: true, connected: true})
    render(<Contacts />)
    expect(await screen.findByText('Autorización guardada · lectura sin comprobar')).toBeTruthy()
    expect(screen.queryByText('Lectura real comprobada')).toBeNull()
  })
  it('imports only explicitly selected rows and requires re-review when selection changes', async () => {
    const preview = {preview_id: 'preview-1', revision: 'snapshot-1', source: 'fixture', expires_at: '2030-01-01T00:00:00Z', created_at: '', contacts: [
      {selection_id: 'a', name: 'FICTICIO Uno', phone: '+12025550124', email: '', source_id: 'x', duplicates: [], warnings: []},
      {selection_id: 'b', name: 'FICTICIO Dos', phone: '+12025550125', email: '', source_id: 'y', duplicates: [], warnings: []}]}
    const calls = stub((path) => path === '/google/preview' ? response(preview)
      : path === '/imports/selected' ? response({imported: [contact], skipped: []}) : undefined,
      [], {...disconnected, configured: true, connected: true})
    render(<Contacts />)
    fireEvent.click(screen.getByRole('tab',{name:'Google'}))
    fireEvent.click(await screen.findByRole('button', {name: 'Ver contactos para seleccionar'}))
    await screen.findByText('Vista previa de prueba · no es una conexión Google')
    const importButton = screen.getByRole('button', {name: 'Importar selección (0)'}) as HTMLButtonElement
    expect(importButton.disabled).toBe(true)
    fireEvent.click(screen.getByLabelText(/FICTICIO Uno/))
    fireEvent.click(screen.getByLabelText(/He revisado las 1 filas/))
    fireEvent.click(screen.getByLabelText(/FICTICIO Dos/))
    expect((screen.getByRole('button', {name: 'Importar selección (2)'}) as HTMLButtonElement).disabled).toBe(true)
    fireEvent.click(screen.getByLabelText(/FICTICIO Dos/))
    fireEvent.click(screen.getByLabelText(/He revisado las 1 filas/))
    fireEvent.click(screen.getByRole('button', {name: 'Importar selección (1)'}))
    await screen.findByText('Importados: 1. Omitidos: 0. No se ha modificado Google.')
    expect(calls.find(call => call.path === '/imports/selected')?.body).toEqual({preview_id: 'preview-1', expected_revision: 'snapshot-1', selected_ids: ['a'], duplicate_policy: 'skip'})
  })
  it('rejects an authorization link outside the official Google origin', async () => {
    stub(path => path === '/google/connect' ? response({authorization_url: 'https://example.invalid/steal'}) : undefined,
      [], {...disconnected, configured: true})
    render(<Contacts />)
    fireEvent.click(screen.getByRole('tab',{name:'Google'}))
    fireEvent.click(await screen.findByRole('button', {name: 'Conectar con Google'}))
    expect(await screen.findByRole('alert')).toHaveProperty('textContent', 'La dirección de autorización no es de Google.')
    expect(screen.queryByRole('link', {name: /Continuar autorización/})).toBeNull()
  })
})
