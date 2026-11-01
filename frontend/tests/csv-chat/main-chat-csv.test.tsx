// @vitest-environment jsdom
// The HTTP transport/provider is controlled here. These tests prove UI dispatch,
// scope changes and evidence rendering, not backend IO or a live model response.
import React from 'react'
import {createHash, webcrypto} from 'node:crypto'
import {afterEach, beforeEach, expect, it, vi} from 'vitest'
import {act, cleanup, fireEvent, render, screen, waitFor, within} from '@testing-library/react'
import AgentChat from '../../src/components/AgentChat'
import CsvChatQuery from '../../src/components/CsvChatQuery'
import {resetLocaleForTests, setLocale, t} from '../../src/i18n'
import type {CsvChatContext} from '../../src/types/csvChat'

const response = (body: unknown, status = 200) => ({ok: status < 400, status, json: async () => body})
const deferred = () => {let resolve!: (value: any) => void; let reject!: (value: any) => void; const promise = new Promise<any>((yes, no) => {resolve = yes; reject = no}); return {promise, resolve, reject}}
const project = {project_id: 'csv-project', title: 'Proyecto CSV', scope: 'project', root: 'D:/work/csv-project'}
const policy = {...project, binding: 'binding-csv', revision: 'policy-revision', state: 'configured', read_directories: ['data'], write_directories: []}
const baseConversation = {id: 'csv-conversation', owner_kind: 'assistant', owner_id: 'app-assistant', title: 'Consulta CSV', status: 'active', revision: 7, updated_at: '2026-11-01', messages: [] as any[]}
const csvRead = {path: 'data/pedidos.csv', delimiter: 'auto', decimal_separator: '.'}
function grantFor(request = {message: 'Calcula el total de pedidos pendientes', csv_read: csvRead}) {
  const selection = request.csv_read
  const canonical = JSON.stringify({csv_read: {decimal_separator: selection.decimal_separator, delimiter: selection.delimiter, path: selection.path}, message: request.message})
  return {authorization_id: 'csv-grant', paths: [selection.path], project_id: policy.project_id, binding: policy.binding, policy_revision: policy.revision, request_sha256: createHash('sha256').update(canonical).digest('hex')}
}
const analysis = {interpretation: {aggregates: [{op: 'sum', column: 'total', as: 'total_pendiente'}]}, decimal_separator: '.', result: {columns: ['total_pendiente'], rows: [['247.30']]}, source_sha256: 'a'.repeat(64), plan_sha256: 'b'.repeat(64), result_sha256: 'c'.repeat(64)}

beforeEach(() => {
  localStorage.clear(); resetLocaleForTests(); setLocale('es')
  vi.stubGlobal('crypto', webcrypto)
  HTMLElement.prototype.scrollIntoView = vi.fn()
  HTMLDialogElement.prototype.showModal = function () {this.open = true}
  HTMLDialogElement.prototype.close = function () {this.open = false}
})
afterEach(() => {cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks()})

async function setup(options: {grant?: unknown; grantStatus?: number; grantPending?: ReturnType<typeof deferred>; chatPending?: ReturnType<typeof deferred>; noConversation?: boolean; read?: string[]; revokeStatus?: number; revoked?: boolean; recoveryConversation?: Record<string, unknown>} = {}) {
  const calls: Array<{url: string; method: string; body: any}> = []
  let conversation = {...baseConversation}
  let chatRequests = 0
  const makeAnswer = () => {
    const references = {csv_analysis: analysis, sources: [{source_type: 'csv', path: csvRead.path, start_line: 1, end_line: 4, file_sha256: analysis.source_sha256, content_sha256: 'd'.repeat(64)}], read_events: [{kind: 'csv_read', decision: 'ALLOW', path: csvRead.path}]}
    conversation = {...conversation, revision: conversation.revision + 2, messages: [{id: 'query', role: 'user', content: 'Calcula el total de pedidos pendientes'}, {id: 'result', role: 'assistant', content: 'Total pendiente: 247.30. Filas 2 y 4.', references}]}
    return response({operation: 'chat', assistant_message: 'Total pendiente: 247.30. Filas 2 y 4.', conversation, sources: references.sources, read_events: references.read_events, csv_analysis: analysis})
  }
  const fetcher = vi.fn(async (url: string, init?: RequestInit) => {
    const body = init?.body ? JSON.parse(String(init.body)) : null
    calls.push({url, method: init?.method ?? 'GET', body})
    if (url === '/api/agents/list') return response({agents: []})
    if (url === '/api/providers/selection') return response({provider_id: 'fixture', model_id: 'fixture-model'})
    if (url === '/api/project-folders/v1/active') return response(project)
    if (url === '/api/project-permissions') return response({...policy, read_directories: options.read ?? policy.read_directories})
    if (url === '/api/project-permissions/directories') {
      const root = body.directory === '.'
      return response({...policy, directory: body.directory, directories: root ? [{name: 'data', path: 'data'}] : [], files: root ? [] : [{name: 'pedidos.csv', path: 'data/pedidos.csv'}, {name: 'notes.md', path: 'data/notes.md'}], truncated: false})
    }
    if (url.startsWith('/api/conversations?')) return response({conversations: options.noConversation ? [] : [conversation]})
    if (url === '/api/conversations/csv-conversation') return response(chatRequests ? {...conversation, ...options.recoveryConversation} : conversation)
    if (url === '/api/conversations' && init?.method === 'POST') return response(conversation)
    if (url === '/api/workspace-read/authorizations') return options.grantPending?.promise ?? response(options.grant ?? grantFor(body.csv_request), options.grantStatus)
    if (url === '/api/workspace-read/authorizations/csv-grant') return response({revoked: options.revoked ?? true}, options.revokeStatus)
    if (url === '/api/chat/control') {chatRequests++; return chatRequests === 1 && options.chatPending ? options.chatPending.promise : makeAnswer()}
    return response({models: [], proposals: []})
  })
  vi.stubGlobal('fetch', fetcher)
  const props = {cognitiveMode: 'baseline' as const, onNavigate: vi.fn(), onOpenProviderSettings: vi.fn(), onOpenCognitionSettings: vi.fn(), workspaceScopeVersion: 0}
  const view = render(<AgentChat {...props}/>)
  await waitFor(() => expect(calls.some(call => call.url === '/api/project-folders/v1/active')).toBe(true))
  if (!options.noConversation) await waitFor(() => expect(calls.some(call => call.url === '/api/conversations/csv-conversation')).toBe(true))
  await act(async () => {})
  return {calls, view, props, makeAnswer}
}

async function openCsv() {
  fireEvent.click(screen.getByText('Recursos', {exact: true}))
  fireEvent.click(screen.getByRole('button', {name: 'Consultar archivo'}))
  const dialog = await screen.findByRole('dialog', {name: 'Consultar archivo'})
  await within(dialog).findByRole('button', {name: 'Abrir carpeta data'})
  fireEvent.click(within(dialog).getByRole('button', {name: 'Abrir carpeta data'}))
  await within(dialog).findByRole('button', {name: 'Seleccionar data/pedidos.csv'})
  fireEvent.click(within(dialog).getByRole('button', {name: 'Seleccionar data/pedidos.csv'}))
  fireEvent.change(within(dialog).getByLabelText(t('csvChat.question')), {target: {value: 'Calcula el total de pedidos pendientes'}})
  return dialog
}

const mutations = (calls: Array<{url: string; method: string; body: any}>) => calls.filter(call => call.method !== 'GET' && call.url !== '/api/project-permissions/directories')
function authorizeAndSubmit(dialog: HTMLElement) {
  fireEvent.click(within(dialog).getByLabelText(t('csvChat.consent')))
  fireEvent.click(within(dialog).getByRole('button', {name: t('csvChat.submit')}))
}

it('F11 selects metadata, authorizes an exact question and options, then shows the persisted CSV answer in main chat', async () => {
  const f = await setup()
  const composer = screen.getByLabelText('Mensaje al asistente o agente seleccionado') as HTMLTextAreaElement
  fireEvent.change(composer, {target: {value: 'Mi borrador todavía no enviado'}})
  fireEvent.click(screen.getByLabelText('Permitir lectura web pública'))
  expect(screen.queryByLabelText('URL HTTPS de entrada · una por línea')).toBeNull()
  const dialog = await openCsv()
  expect(mutations(f.calls)).toEqual([])
  expect(within(dialog).queryByText('notes.md')).toBeNull()
  expect(dialog.closest('form')).toBeNull()
  expect((within(dialog).getByRole('button', {name: t('csvChat.submit')}) as HTMLButtonElement).disabled).toBe(true)
  authorizeAndSubmit(dialog)
  await screen.findByText('Total pendiente: 247.30. Filas 2 y 4.')
  await waitFor(() => expect(screen.queryByRole('dialog', {name: 'Consultar archivo'})).toBeNull())
  expect(mutations(f.calls).map(call => call.url)).toEqual(['/api/workspace-read/authorizations', '/api/chat/control'])
  expect(mutations(f.calls)[0].body).toEqual({owner_kind: 'assistant', owner_id: 'app-assistant', conversation_id: 'csv-conversation', revision: 7, paths: [csvRead.path], csv_request: {message: 'Calcula el total de pedidos pendientes', csv_read: csvRead}, expected_project: {project_id: policy.project_id, binding: policy.binding, revision: policy.revision}})
  expect(mutations(f.calls)[1].body).toMatchObject({operation: 'chat', message: 'Calcula el total de pedidos pendientes', conversation_id: 'csv-conversation', revision: 7, workspace_read_authorization_id: 'csv-grant', csv_read: csvRead})
  expect(mutations(f.calls)[1].body).not.toHaveProperty('web_read_authorization_id')
  expect(mutations(f.calls)[1].body).not.toHaveProperty('document_authorization_id')
  expect(composer.value).toBe('Mi borrador todavía no enviado')
  expect(screen.getByLabelText('Evidencia de la consulta CSV').textContent).toContain('247.30')
  expect(screen.getByLabelText('Archivos del proyecto consultados').textContent).toContain('a'.repeat(64))
})

it('can start from blank chat without inheriting a draft or duplicating a conversation', async () => {
  const f = await setup({noConversation: true})
  const dialog = await openCsv(); authorizeAndSubmit(dialog)
  await screen.findByText('Total pendiente: 247.30. Filas 2 y 4.')
  expect(mutations(f.calls).map(call => call.url)).toEqual(['/api/conversations', '/api/workspace-read/authorizations', '/api/chat/control'])
})

it('keeps CSV scoped consent separate from saved READ and clears it when the question or parse settings change', async () => {
  const f = await setup(); const dialog = await openCsv()
  const checkbox = within(dialog).getByLabelText(t('csvChat.consent')) as HTMLInputElement
  fireEvent.click(checkbox); expect(checkbox.checked).toBe(true)
  fireEvent.change(within(dialog).getByLabelText(t('csvChat.question')), {target: {value: 'Otra pregunta'}}); expect(checkbox.checked).toBe(false)
  fireEvent.click(checkbox)
  fireEvent.change(within(dialog).getByLabelText(t('csvChat.delimiter')), {target: {value: ';'}}); expect(checkbox.checked).toBe(false)
  fireEvent.click(checkbox)
  fireEvent.change(within(dialog).getByLabelText(t('csvChat.decimal')), {target: {value: ','}}); expect(checkbox.checked).toBe(false)
  expect(mutations(f.calls)).toEqual([])
})

it('binds explicit delimiter and decimal settings identically and obtains a fresh grant for each new question', async () => {
  const f = await setup(); const dialog = await openCsv()
  fireEvent.change(within(dialog).getByLabelText(t('csvChat.delimiter')), {target: {value: ';'}})
  fireEvent.change(within(dialog).getByLabelText(t('csvChat.decimal')), {target: {value: ','}})
  authorizeAndSubmit(dialog)
  await screen.findByText('Total pendiente: 247.30. Filas 2 y 4.')
  const first = mutations(f.calls)
  expect(first[0].body.csv_request.csv_read).toEqual({...csvRead, delimiter: ';', decimal_separator: ','})
  expect(first[1].body.csv_read).toEqual(first[0].body.csv_request.csv_read)
  await waitFor(() => expect(screen.queryByRole('dialog', {name: 'Consultar archivo'})).toBeNull())
  const next = await openCsv()
  expect((within(next).getByLabelText(t('csvChat.consent')) as HTMLInputElement).checked).toBe(false)
  authorizeAndSubmit(next)
  await waitFor(() => expect(mutations(f.calls).filter(call => call.url === '/api/chat/control')).toHaveLength(2))
  expect(mutations(f.calls)[2].body.revision).toBe(9)
})

it.each([{paths: ['data/pedidos.csv']}, {authorization_id: '', paths: ['data/pedidos.csv']}, {authorization_id: 'csv-grant', paths: ['data/pedidos.csv', 'extra.csv']}])('rejects incomplete or widened authorizations without dispatch', async grant => {
  const f = await setup({grant}); const dialog = await openCsv(); authorizeAndSubmit(dialog)
  await waitFor(() => expect(within(dialog).getByRole('alert').textContent).toContain(t('csvChat.grantMismatch')))
  expect(f.calls.some(call => call.url === '/api/chat/control')).toBe(false)
})

it('requires the existing saved READ scope before issuing a CSV grant', async () => {
  const f = await setup({read: ['other']}); const dialog = await openCsv()
  expect((within(dialog).getByLabelText(t('csvChat.consent')) as HTMLInputElement).disabled).toBe(true)
  expect(within(dialog).getByText(t('csvChat.readRequired'))).toBeTruthy()
  fireEvent.submit(within(dialog).getByRole('form'))
  expect(mutations(f.calls)).toEqual([])
})

it.each(['/tmp/outside.csv', '../outside.csv', 'D:\\private\\outside.csv', 'data/readme.md'])('does not authorize an external or unsupported selection: %s', async path => {
  const f = await setup(); const dialog = await openCsv()
  fireEvent.change(within(dialog).getByLabelText(t('csvChat.path')), {target: {value: path}})
  expect(within(dialog).getByRole('alert').textContent).toContain(t('csvChat.invalidPath'))
  fireEvent.submit(within(dialog).getByRole('form'))
  expect(mutations(f.calls)).toEqual([])
})

it('retains the diagnostic and does not send to chat when the backend denies authorization', async () => {
  const f = await setup({grantStatus: 403, grant: {detail: {code: 'read_authorization_invalid', message: 'Revoked CSV policy'}}})
  const dialog = await openCsv(); authorizeAndSubmit(dialog)
  await waitFor(() => expect(within(dialog).getByRole('alert').textContent).toContain('Revoked CSV policy'))
  expect(mutations(f.calls).map(call => call.url)).toEqual(['/api/workspace-read/authorizations'])
  expect((within(dialog).getByLabelText(t('csvChat.consent')) as HTMLInputElement).checked).toBe(false)
})

it('rejects and revokes a mismatched returned grant without sending the question', async () => {
  const f = await setup({grant: {authorization_id: 'csv-grant', paths: ['other.csv']}})
  const dialog = await openCsv(); authorizeAndSubmit(dialog)
  await waitFor(() => expect(within(dialog).getByRole('alert').textContent).toContain(t('csvChat.grantMismatch')))
  expect(mutations(f.calls).map(call => call.url)).toEqual(['/api/workspace-read/authorizations', '/api/workspace-read/authorizations/csv-grant'])
})

it.each([
  {project_id: 'other-project'},
  {binding: 'previous-binding'},
  {policy_revision: 'previous-policy'},
  {request_sha256: '0'.repeat(64)},
  {request_sha256: 'invalid-hash'},
])('rejects and revokes a grant with mismatched project or request identity: %j', async mismatch => {
  const f = await setup({grant: {...grantFor(), ...mismatch}})
  const dialog = await openCsv(); authorizeAndSubmit(dialog)
  await waitFor(() => expect(within(dialog).getByRole('alert').textContent).toContain(t('csvChat.grantMismatch')))
  expect(mutations(f.calls).map(call => call.url)).toEqual(['/api/workspace-read/authorizations', '/api/workspace-read/authorizations/csv-grant'])
  expect(f.calls.some(call => call.url === '/api/chat/control')).toBe(false)
})

it('revokes immediately, waits for server completion, synchronizes only revision and retries with new consent', async () => {
  const pending = deferred(); const f = await setup({chatPending: pending})
  const dialog = await openCsv(); authorizeAndSubmit(dialog)
  await waitFor(() => expect(f.calls.some(call => call.url === '/api/chat/control')).toBe(true))
  fireEvent.click(within(dialog).getByRole('button', {name: t('csvChat.cancel')}))
  await waitFor(() => expect(f.calls.some(call => call.method === 'DELETE')).toBe(true))
  expect((within(dialog).getByRole('button', {name: t('csvChat.submit')}) as HTMLButtonElement).disabled).toBe(true)
  const revocation = f.calls.find(call => call.method === 'DELETE')!
  expect(revocation.body).toEqual({owner_kind: 'assistant', owner_id: 'app-assistant', conversation_id: 'csv-conversation', revision: 7})
  await act(async () => pending.resolve(f.makeAnswer()))
  await waitFor(() => expect(within(dialog).getByRole('alert').textContent).toContain(t('csvChat.cancelled')))
  expect(screen.queryByText('Total pendiente: 247.30. Filas 2 y 4.')).toBeNull()
  fireEvent.click(within(dialog).getByRole('button', {name: t('commerce.close_tool')}))
  const next = await openCsv()
  expect((within(next).getByLabelText(t('csvChat.consent')) as HTMLInputElement).checked).toBe(false)
  authorizeAndSubmit(next)
  await screen.findByText('Total pendiente: 247.30. Filas 2 y 4.')
  const grants = f.calls.filter(call => call.url === '/api/workspace-read/authorizations')
  const chats = f.calls.filter(call => call.url === '/api/chat/control')
  expect(grants.map(call => call.body.revision)).toEqual([7, 9])
  expect(chats.map(call => call.body.revision)).toEqual([7, 9])
})

it.each([{revokeStatus: 503}, {revoked: false}])('reports an unconfirmed revocation without claiming cancellation succeeded: %j', async options => {
  const pending = deferred(); const f = await setup({chatPending: pending, ...options})
  const dialog = await openCsv(); authorizeAndSubmit(dialog)
  await waitFor(() => expect(f.calls.some(call => call.url === '/api/chat/control')).toBe(true))
  fireEvent.click(within(dialog).getByRole('button', {name: t('csvChat.cancel')}))
  await waitFor(() => expect(within(dialog).getByRole('alert').textContent).toContain(t('csvChat.cancelFailed')))
  expect(within(dialog).queryByText(t('csvChat.cancelled'))).toBeNull()
  await act(async () => pending.resolve(f.makeAnswer()))
  await waitFor(() => expect(within(dialog).getByRole('alert').textContent).toContain(t('csvChat.cancelFailed')))
})

it.each([{revokeStatus: 503}, {revoked: false}])('keeps an unconfirmed revocation visible in chat after closing the resource: %j', async options => {
  const pending = deferred(); const f = await setup({chatPending: pending, ...options})
  const dialog = await openCsv(); authorizeAndSubmit(dialog)
  await waitFor(() => expect(f.calls.some(call => call.url === '/api/chat/control')).toBe(true))
  fireEvent.click(within(dialog).getByRole('button', {name: t('commerce.close_tool')}))
  await screen.findByText(t('csvChat.cancelFailed'))
  expect(screen.queryByRole('dialog', {name: 'Consultar archivo'})).toBeNull()
  await act(async () => pending.resolve(f.makeAnswer()))
  expect(screen.queryByText('Total pendiente: 247.30. Filas 2 y 4.')).toBeNull()
  expect(screen.getByText(t('csvChat.cancelFailed'))).toBeTruthy()
})

it('blocks retry when cancellation transport fails instead of treating a local failure as server completion', async () => {
  const pending = deferred(); const f = await setup({chatPending: pending})
  const dialog = await openCsv(); authorizeAndSubmit(dialog)
  await waitFor(() => expect(f.calls.some(call => call.url === '/api/chat/control')).toBe(true))
  fireEvent.click(within(dialog).getByRole('button', {name: t('csvChat.cancel')}))
  await waitFor(() => expect(f.calls.some(call => call.method === 'DELETE')).toBe(true))
  await act(async () => pending.reject(new Error('Connection lost; completion unknown')))
  await waitFor(() => expect(within(dialog).getByRole('alert').textContent).toContain(t('csvChat.reloadRequired')))
  fireEvent.submit(within(dialog).getByRole('form'))
  expect(f.calls.filter(call => call.url === '/api/workspace-read/authorizations')).toHaveLength(1)
  expect((within(dialog).getByRole('button', {name: t('csvChat.submit')}) as HTMLButtonElement).disabled).toBe(true)
})

it('rejects recovery metadata for a different owner without accepting late content or enabling retry', async () => {
  const pending = deferred(); const f = await setup({chatPending: pending, recoveryConversation: {owner_id: 'another-owner'}})
  const dialog = await openCsv(); authorizeAndSubmit(dialog)
  await waitFor(() => expect(f.calls.some(call => call.url === '/api/chat/control')).toBe(true))
  fireEvent.click(within(dialog).getByRole('button', {name: t('csvChat.cancel')}))
  await act(async () => pending.resolve(f.makeAnswer()))
  await waitFor(() => expect(within(dialog).getByRole('alert').textContent).toContain(t('csvChat.reloadRequired')))
  expect(screen.queryByText('Total pendiente: 247.30. Filas 2 y 4.')).toBeNull()
  expect((within(dialog).getByRole('button', {name: t('csvChat.submit')}) as HTMLButtonElement).disabled).toBe(true)
})

it('does not reconcile a cancelled request into a changed workspace context', async () => {
  const pending = deferred(); const f = await setup({chatPending: pending})
  const dialog = await openCsv(); authorizeAndSubmit(dialog)
  await waitFor(() => expect(f.calls.some(call => call.url === '/api/chat/control')).toBe(true))
  fireEvent.click(within(dialog).getByRole('button', {name: t('csvChat.cancel')}))
  await waitFor(() => expect(f.calls.some(call => call.method === 'DELETE')).toBe(true))
  f.view.rerender(<AgentChat {...f.props} workspaceScopeVersion={1}/>)
  await act(async () => {})
  const recoveryReads = f.calls.filter(call => call.url === '/api/conversations/csv-conversation').length
  await act(async () => pending.resolve(f.makeAnswer()))
  expect(f.calls.filter(call => call.url === '/api/conversations/csv-conversation')).toHaveLength(recoveryReads)
  expect(screen.queryByText('Total pendiente: 247.30. Filas 2 y 4.')).toBeNull()
})

it('revokes a late grant after closing the dialog and never dispatches it', async () => {
  const pending = deferred(); const f = await setup({grantPending: pending})
  const dialog = await openCsv(); authorizeAndSubmit(dialog)
  await waitFor(() => expect(f.calls.some(call => call.url === '/api/workspace-read/authorizations')).toBe(true))
  fireEvent.click(within(dialog).getByRole('button', {name: t('commerce.close_tool')}))
  await act(async () => pending.resolve(response(grantFor())))
  await waitFor(() => expect(f.calls.some(call => call.method === 'DELETE')).toBe(true))
  expect(f.calls.some(call => call.url === '/api/chat/control')).toBe(false)
})

it('scope changes cancel pending authorization and clear the chosen CSV and consent', async () => {
  const pending = deferred(); const f = await setup({grantPending: pending})
  const dialog = await openCsv(); authorizeAndSubmit(dialog)
  await waitFor(() => expect(f.calls.some(call => call.url === '/api/workspace-read/authorizations')).toBe(true))
  f.view.rerender(<AgentChat {...f.props} workspaceScopeVersion={1}/>)
  await act(async () => pending.resolve(response(grantFor())))
  await waitFor(() => expect(f.calls.some(call => call.method === 'DELETE')).toBe(true))
  expect(f.calls.some(call => call.url === '/api/chat/control')).toBe(false)
  expect((screen.getByLabelText(t('csvChat.path')) as HTMLInputElement).value).toBe('')
  expect((screen.getByLabelText(t('csvChat.consent')) as HTMLInputElement).checked).toBe(false)
})

it('discards a stale directory response instead of attaching its files to the new context', async () => {
  const pending = deferred(); const onSubmit = vi.fn()
  const fetcher = vi.fn(async (url: string) => url === '/api/project-permissions' ? response(policy) : pending.promise)
  vi.stubGlobal('fetch', fetcher)
  const props: CsvChatContext = {projectId: project.project_id, projectRoot: project.root, contextKey: 'old-conversation', disabled: false, onSubmit}
  const view = render(<CsvChatQuery {...props} onSent={() => {}}/>)
  await waitFor(() => expect(fetcher.mock.calls.length).toBe(2))
  view.rerender(<CsvChatQuery {...props} projectId="different-project" projectRoot="D:/different" contextKey="new-conversation" onSent={() => {}}/>)
  await act(async () => pending.resolve(response({...policy, directory: '.', directories: [], files: [{name: 'foreign.csv', path: 'foreign.csv'}], truncated: false})))
  expect(screen.queryByRole('button', {name: 'Seleccionar foreign.csv'})).toBeNull()
  expect(onSubmit).not.toHaveBeenCalled()
})
