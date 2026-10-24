import {setLocale,t} from '../../../src/i18n'
import {beforeEach as beforeLocaleExpectation} from 'vitest'
beforeLocaleExpectation(() => setLocale('es'))
// @vitest-environment jsdom
import React from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import ExternalConnections from '../../../src/components/ExternalConnections'

const response = (body: unknown, status = 200) => ({ ok: status < 400, status, json: async () => body })
const tool = { name: 'lookup', description: 'Consulta de ejemplo', input_schema: { type: 'object', properties: { query: { type: 'string' } } }, fingerprint: 'fingerprint-a' }
const connection = { id: 'conn-one', name: 'Servidor de prueba', kind: 'mcp', url: 'https://example.test/mcp', profile: null, method: null, auth_mode: 'none', header_name: null, allow_private: false, state: 'configured', has_credential: false, tools: [tool], last_checked_at: null, last_error: null, revision: 'revision-one' }
const invocation = { run_id: 'run-one', connection_id: connection.id, tool_name: tool.name, decision: 'ALLOW', execution_outcome: 'SUCCESS', actual_effect: { called: true }, receipt_id: 'receipt-one', trace_id: 'trace-one', evidence: { path: '.bago/connections/run-one.json', sha256: 'a'.repeat(64) }, result: { message: '<img src=x onerror=alert(1)>' } }
type Call = { url: string; body: any; method: string }
function stub({ rows = [connection], mutate = async (_call: Call) => response(invocation) } = {}) {
  const calls: Call[] = []
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    const call = { url: String(url), method: init?.method ?? 'GET', body: init?.body ? JSON.parse(String(init.body)) : undefined }
    calls.push(call)
    return call.method === 'GET' ? response({ connections: rows }) : mutate(call)
  }))
  return calls
}
async function selectTool() {
  await screen.findByRole('option', { name: connection.name })
  fireEvent.change(screen.getByLabelText(t('core.ExternalConnections.connection_a7f534')), { target: { value: connection.id } })
  fireEvent.change(screen.getByLabelText(t('core.Authorization.tool_2e53bd')), { target: { value: tool.name } })
}
const authorize = () => fireEvent.click(screen.getByLabelText(t('core.ExternalConnections.i_authorize_this_tool_with_these_arguments_1ddfd0')))
const execute = () => fireEvent.click(screen.getByRole('button', { name: t('core.ExternalConnections.run_tool_35cb23') }))

afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks() })

describe('External connections rendered controls with deterministic API fixtures', () => {
  it('loads configuration without contacting tools and selecting tools does not invoke', async () => {
    const calls = stub()
    render(<ExternalConnections />)
    await selectTool()
    expect(calls).toEqual([{ url: '/api/connections', method: 'GET', body: undefined }])
    expect((screen.getByRole('button', { name: t('core.ExternalConnections.run_tool_35cb23') }) as HTMLButtonElement).disabled).toBe(true)
    expect((screen.getByLabelText(t('core.ExternalConnections.effect_315ea9')) as HTMLSelectElement).value).toBe('WRITE')
    expect(screen.getByText(t('agents.aux.ExternalConnections.guardada_acceso_sin_comprobar'))).toBeTruthy()
  })

  it('renders loading, empty, API error and unsupported list states', async () => {
    let release!: (value: unknown) => void
    vi.stubGlobal('fetch', () => new Promise(resolve => { release = resolve }))
    render(<ExternalConnections />)
    expect(screen.getByText(t('core.ExternalConnections.loading_connections_18736c'))).toBeTruthy()
    await act(async () => release(response({ connections: [] })))
    expect(await screen.findByText(t('core.ExternalConnections.no_connections_are_saved_8b3a0d'))).toBeTruthy()
    cleanup()
    vi.stubGlobal('fetch', async () => response({ detail: { code: 'offline', message: 'Registro no disponible.' } }, 503))
    render(<ExternalConnections />)
    expect((await screen.findByRole('alert')).textContent).toContain('Registro no disponible.')
    cleanup()
    stub({ rows: [{ ...connection, kind: 'unsupported' }] })
    render(<ExternalConnections />)
    expect((await screen.findByRole('alert')).textContent).toContain('tipos no compatibles')
  })

  it('saves only an existing Docker profile configuration without discovery', async () => {
    const calls = stub({ rows: [], mutate: async call => response({ ...connection, ...call.body, tools: [], id: 'docker-one' }) })
    render(<ExternalConnections />)
    await screen.findByText(t('core.ExternalConnections.no_connections_are_saved_8b3a0d'))
    fireEvent.change(screen.getByLabelText(t('core.ExternalConnections.name_562bb1')), { target: { value: 'Docker local' } })
    fireEvent.change(screen.getByLabelText(t('core.ExternalConnections.existing_docker_profile_227daf')), { target: { value: 'profile' } })
    fireEvent.click(screen.getByRole('button', { name: t('core.ExternalConnections.save_connection_021985') }))
    await screen.findByText(t('core.ExternalConnections.configuration_saved_the_service_has_not_been_0332dc'))
    expect(calls.filter(call => call.method === 'POST')).toEqual([{ url: '/api/connections', method: 'POST', body: { name: 'Docker local', kind: 'docker_mcp', profile: 'profile', auth_mode: 'none' } }])
  })

  it.each([200, 503])('clears write-only credentials after saving (HTTP %s)', async status => {
    const calls = stub({ rows: [], mutate: async call => response(status === 200 ? { ...connection, ...call.body, has_credential: true, tools: [] } : { detail: { message: 'Almacén no disponible.' } }, status) })
    render(<ExternalConnections />)
    await screen.findByText(t('core.ExternalConnections.no_connections_are_saved_8b3a0d'))
    fireEvent.change(screen.getByLabelText(t('core.ExternalConnections.type_3868d2')), { target: { value: 'http_api' } })
    fireEvent.change(screen.getByLabelText(t('core.ExternalConnections.name_562bb1')), { target: { value: 'API de prueba' } })
    fireEvent.change(screen.getByLabelText(t('agents.aux.ExternalConnections.url_del_endpoint')), { target: { value: 'https://example.test/data' } })
    fireEvent.change(screen.getByLabelText(t('agents.aux.ExternalConnections.metodo')), { target: { value: 'POST' } })
    fireEvent.change(screen.getByLabelText(t('core.ExternalConnections.authentication_ec4bc9')), { target: { value: 'api_key' } })
    const secret = screen.getByLabelText(t('core.ExternalConnections.credential_write_only_8caf83')) as HTMLInputElement
    fireEvent.change(secret, { target: { value: 'SECRET_FIXTURE' } })
    fireEvent.click(screen.getByRole('button', { name: t('core.ExternalConnections.save_connection_021985') }))
    await waitFor(() => expect(secret.value).toBe(''))
    await screen.findByText(status === 200 ? t('core.ExternalConnections.configuration_saved_the_service_has_not_been_0332dc') : /Almacén no disponible./)
    expect(calls[1].body).toEqual({ name: 'API de prueba', kind: 'http_api', url: 'https://example.test/data', method: 'POST', auth_mode: 'api_key', credential: 'SECRET_FIXTURE', header_name: 'X-API-Key', allow_private: false })
    expect(document.body.textContent).not.toContain('SECRET_FIXTURE')
  })

  it('requires explicit discovery approval and never calls discovered tools', async () => {
    let release!: (value: unknown) => void
    const calls = stub({ rows: [{ ...connection, tools: [] }], mutate: () => new Promise(resolve => { release = resolve }) })
    render(<ExternalConnections />)
    await screen.findByRole('option', { name: connection.name })
    fireEvent.change(screen.getByLabelText(t('core.ExternalConnections.connection_a7f534')), { target: { value: connection.id } })
    const button = screen.getByRole('button', { name: t('core.ExternalConnections.discover_tools_41eb80') }) as HTMLButtonElement
    expect(button.disabled).toBe(true)
    fireEvent.click(screen.getByLabelText(t('core.ExternalConnections.i_authorize_contacting_this_service_to_discover_03b14b')))
    fireEvent.click(button)
    expect(await screen.findByText(t('core.ExternalConnections.contacting_the_service_27cb07'))).toBeTruthy()
    expect((screen.getByLabelText(t('core.ExternalConnections.connection_a7f534')) as HTMLSelectElement).closest('fieldset')?.disabled).toBe(true)
    await act(async () => release(response({ connection: { ...connection, state: 'connected' }, tools: [tool] })))
    await screen.findByText('1 herramientas descubiertas. Ninguna ejecutada.')
    expect(calls[1]).toEqual({ url: '/api/connections/conn-one/discover', method: 'POST', body: { confirmed: true } })
    expect(calls.length).toBe(2)
    expect((screen.getByLabelText(t('core.ExternalConnections.i_authorize_contacting_this_service_to_discover_03b14b')) as HTMLInputElement).checked).toBe(false)
  })

  it.each(['api', 'empty', 'error', 'invalid'])('renders discovery response without fabricating invocation (%s)', async scenario => {
    const calls = stub({ rows: [{ ...connection, kind: scenario === 'api' ? 'http_api' : 'mcp', method: scenario === 'api' ? 'GET' : null, tools: [] }], mutate: async () => scenario === 'error' ? response({ detail: { message: 'Découverte indisponible.' } }, 503) : response({ connection: scenario === 'invalid' ? { ...connection, id: 'other' } : { ...connection, kind: scenario === 'api' ? 'http_api' : 'mcp', state: 'configured' }, tools: scenario === 'empty' ? [] : [tool] }) })
    render(<ExternalConnections />)
    await screen.findByRole('option', { name: connection.name })
    fireEvent.change(screen.getByLabelText(t('core.ExternalConnections.connection_a7f534')), { target: { value: connection.id } })
    fireEvent.click(screen.getByLabelText(t('core.ExternalConnections.i_authorize_contacting_this_service_to_discover_03b14b')))
    fireEvent.click(screen.getByRole('button', { name: t('core.ExternalConnections.discover_tools_41eb80') }))
    if (scenario === 'api') expect(await screen.findByText(t('agents.aux.ExternalConnections.endpoint_preparado_el_acceso_se_comprobara_al_ejecutar_una_solicitud'))).toBeTruthy()
    else if (scenario === 'empty') expect(await screen.findByText('0 herramientas descubiertas. Ninguna ejecutada.')).toBeTruthy()
    else expect((await screen.findByRole('alert')).textContent).toContain(scenario === 'error' ? 'Découverte indisponible.' : 'otra conexión')
    expect(screen.queryByRole('region', { name: t('core.ExternalConnections.execution_receipt_fedb8a') })).toBeNull()
    expect(calls.length).toBe(2)
  })

  it('rejects malformed JSON locally and resets approval on every payload change', async () => {
    const calls = stub()
    render(<ExternalConnections />)
    await selectTool()
    authorize()
    fireEvent.change(screen.getByLabelText(t('core.ExternalConnections.json_arguments_effac4')), { target: { value: '[]' } })
    expect((screen.getByLabelText(t('core.ExternalConnections.i_authorize_this_tool_with_these_arguments_1ddfd0')) as HTMLInputElement).checked).toBe(false)
    authorize(); execute()
    expect(await screen.findByText(t('core.ExternalConnections.arguments_must_be_a_valid_json_object_a85f3d'))).toBeTruthy()
    expect(calls.length).toBe(1)
    authorize()
    fireEvent.change(screen.getByLabelText(t('core.ExternalConnections.effect_315ea9')), { target: { value: 'READ' } })
    expect((screen.getByLabelText(t('core.ExternalConnections.i_authorize_this_tool_with_these_arguments_1ddfd0')) as HTMLInputElement).checked).toBe(false)
    authorize()
    fireEvent.change(screen.getByLabelText(t('core.Authorization.tool_2e53bd')), { target: { value: '' } })
    expect(screen.queryByLabelText(t('core.ExternalConnections.i_authorize_this_tool_with_these_arguments_1ddfd0'))).toBeNull()
  })

  it('renders only server-observed receipt identity, loading and escaped remote output', async () => {
    let release!: (value: unknown) => void
    const calls = stub({ mutate: () => new Promise(resolve => { release = resolve }) })
    render(<ExternalConnections />)
    await selectTool(); authorize(); execute()
    expect(await screen.findByText(t('core.ExternalConnections.running_the_authorized_operation_fc4f8e'))).toBeTruthy()
    await act(async () => release(response(invocation)))
    const receipt = within(await screen.findByRole('region', { name: t('core.ExternalConnections.execution_receipt_fedb8a') }))
    expect(receipt.getByText('receipt-one')).toBeTruthy()
    expect(receipt.getByText('trace-one')).toBeTruthy()
    expect(receipt.getByText('Sí')).toBeTruthy()
    expect(document.querySelector('img')).toBeNull()
    expect(receipt.getByText(/<img src=x onerror=alert\(1\)>/)).toBeTruthy()
    expect(calls[1].body).toEqual({ tool_name: 'lookup', arguments: {}, effect: 'WRITE', tool_fingerprint: 'fingerprint-a', confirmed: true })
    fireEvent.change(screen.getByLabelText(t('core.ExternalConnections.json_arguments_effac4')), { target: { value: '{"query":"new"}' } })
    expect(screen.queryByRole('region', { name: t('core.ExternalConnections.execution_receipt_fedb8a') })).toBeNull()
    expect((screen.getByRole('button', { name: t('core.ExternalConnections.run_tool_35cb23') }) as HTMLButtonElement).disabled).toBe(true)
  })

  it('refreshes the actual registered connection state after an observed invocation', async () => {
    let registryReads = 0
    const calls: Call[] = []
    vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
      calls.push({ url: String(url), method: init?.method ?? 'GET', body: init?.body ? JSON.parse(String(init.body)) : undefined })
      if (!init?.method) return response({ connections: [{ ...connection, state: registryReads++ ? 'connected' : 'configured' }] })
      return response(invocation)
    }))
    render(<ExternalConnections />)
    await selectTool()
    expect(screen.getByText(t('agents.aux.ExternalConnections.guardada_acceso_sin_comprobar'))).toBeTruthy()
    authorize(); execute()
    expect(await screen.findByText(t('agents.aux.state.CONNECTED'))).toBeTruthy()
    expect(screen.getByRole('region', { name: t('core.ExternalConnections.execution_receipt_fedb8a') })).toBeTruthy()
    expect(calls.map(call => `${call.method} ${call.url}`)).toEqual(['GET /api/connections', 'POST /api/connections/conn-one/invoke', 'GET /api/connections'])
  })

  it.each(['missing', 'wrong-connection', 'wrong-tool', 'missing-sha', 'false-success'])('rejects invalid receipt identity (%s)', async scenario => {
    const bad = scenario === 'missing' ? {} : scenario === 'wrong-connection' ? { ...invocation, connection_id: 'other' } : scenario === 'wrong-tool' ? { ...invocation, tool_name: 'other' } : scenario === 'missing-sha' ? { ...invocation, evidence: {} } : { ...invocation, actual_effect: { called: false } }
    stub({ mutate: async () => response(bad) })
    render(<ExternalConnections />)
    await selectTool(); authorize(); execute()
    expect((await screen.findByRole('alert')).textContent).toContain('Recibo ausente, incoherente o de otra operación')
    expect(screen.queryByText(t('core.ExternalConnections.request_completed_adl_receipt_f3e4b4'))).toBeNull()
  })

  it.each(['DENIED', 'ERROR'])('shows %s without a success claim', async outcome => {
    stub({ mutate: async () => response({ ...invocation, decision: outcome === 'DENIED' ? 'REQUIRE_HUMAN' : 'ALLOW', execution_outcome: outcome, actual_effect: { called: outcome === 'ERROR' }, error: { code: 'test', message: 'No completada.' } }) })
    render(<ExternalConnections />)
    await selectTool(); authorize(); execute()
    const receipt = within(await screen.findByRole('region', { name: t('core.ExternalConnections.execution_receipt_fedb8a') }))
    expect(receipt.getByText(outcome === 'DENIED' ? 'Denegada (DENIED)' : 'Error (ERROR)')).toBeTruthy()
    expect(screen.queryByText(t('core.ExternalConnections.request_completed_adl_receipt_f3e4b4'))).toBeNull()
  })

  it.each(['GET', 'POST'])('fixes API %s effect and reports invocation request errors', async method => {
    const calls = stub({ rows: [{ ...connection, kind: 'http_api', method }], mutate: async () => response({ detail: { code: 'transport', message: 'Servicio no disponible.' } }, 503) })
    render(<ExternalConnections />)
    await selectTool()
    expect((screen.getByLabelText(t('core.ExternalConnections.effect_315ea9')) as HTMLSelectElement).disabled).toBe(true)
    expect((screen.getByLabelText(t('core.ExternalConnections.effect_315ea9')) as HTMLSelectElement).value).toBe(method === 'GET' ? 'READ' : 'WRITE')
    authorize(); execute()
    expect((await screen.findByRole('alert')).textContent).toContain('Servicio no disponible.')
    expect(calls[1].body.effect).toBe(method === 'GET' ? 'READ' : 'WRITE')
    expect(screen.queryByRole('region', { name: t('core.ExternalConnections.execution_receipt_fedb8a') })).toBeNull()
  })
})

