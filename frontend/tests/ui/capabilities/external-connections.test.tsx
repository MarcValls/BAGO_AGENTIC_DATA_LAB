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
  fireEvent.change(screen.getByLabelText('Conexión'), { target: { value: connection.id } })
  fireEvent.change(screen.getByLabelText('Herramienta'), { target: { value: tool.name } })
}
const authorize = () => fireEvent.click(screen.getByLabelText('Autorizo esta herramienta con estos argumentos y este efecto'))
const execute = () => fireEvent.click(screen.getByRole('button', { name: 'Ejecutar herramienta' }))

afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks() })

describe('External connections rendered controls with deterministic API fixtures', () => {
  it('loads configuration without contacting tools and selecting tools does not invoke', async () => {
    const calls = stub()
    render(<ExternalConnections />)
    await selectTool()
    expect(calls).toEqual([{ url: '/api/connections', method: 'GET', body: undefined }])
    expect((screen.getByRole('button', { name: 'Ejecutar herramienta' }) as HTMLButtonElement).disabled).toBe(true)
    expect((screen.getByLabelText('Efecto') as HTMLSelectElement).value).toBe('WRITE')
    expect(screen.getByText('Guardada · acceso sin comprobar')).toBeTruthy()
  })

  it('renders loading, empty, API error and unsupported list states', async () => {
    let release!: (value: unknown) => void
    vi.stubGlobal('fetch', () => new Promise(resolve => { release = resolve }))
    render(<ExternalConnections />)
    expect(screen.getByText('Cargando conexiones…')).toBeTruthy()
    await act(async () => release(response({ connections: [] })))
    expect(await screen.findByText('No hay conexiones guardadas.')).toBeTruthy()
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
    await screen.findByText('No hay conexiones guardadas.')
    fireEvent.change(screen.getByLabelText('Nombre'), { target: { value: 'Docker local' } })
    fireEvent.change(screen.getByLabelText('Perfil existente de Docker'), { target: { value: 'profile' } })
    fireEvent.click(screen.getByRole('button', { name: 'Guardar conexión' }))
    await screen.findByText('Configuración guardada. El servicio todavía no se ha contactado.')
    expect(calls.filter(call => call.method === 'POST')).toEqual([{ url: '/api/connections', method: 'POST', body: { name: 'Docker local', kind: 'docker_mcp', profile: 'profile', auth_mode: 'none' } }])
  })

  it.each([200, 503])('clears write-only credentials after saving (HTTP %s)', async status => {
    const calls = stub({ rows: [], mutate: async call => response(status === 200 ? { ...connection, ...call.body, has_credential: true, tools: [] } : { detail: { message: 'Almacén no disponible.' } }, status) })
    render(<ExternalConnections />)
    await screen.findByText('No hay conexiones guardadas.')
    fireEvent.change(screen.getByLabelText('Tipo'), { target: { value: 'http_api' } })
    fireEvent.change(screen.getByLabelText('Nombre'), { target: { value: 'API de prueba' } })
    fireEvent.change(screen.getByLabelText('URL del endpoint'), { target: { value: 'https://example.test/data' } })
    fireEvent.change(screen.getByLabelText('Método'), { target: { value: 'POST' } })
    fireEvent.change(screen.getByLabelText('Autenticación'), { target: { value: 'api_key' } })
    const secret = screen.getByLabelText('Credencial · solo escritura') as HTMLInputElement
    fireEvent.change(secret, { target: { value: 'SECRET_FIXTURE' } })
    fireEvent.click(screen.getByRole('button', { name: 'Guardar conexión' }))
    await waitFor(() => expect(secret.value).toBe(''))
    await screen.findByText(status === 200 ? 'Configuración guardada. El servicio todavía no se ha contactado.' : 'Almacén no disponible.')
    expect(calls[1].body).toEqual({ name: 'API de prueba', kind: 'http_api', url: 'https://example.test/data', method: 'POST', auth_mode: 'api_key', credential: 'SECRET_FIXTURE', header_name: 'X-API-Key', allow_private: false })
    expect(document.body.textContent).not.toContain('SECRET_FIXTURE')
  })

  it('requires explicit discovery approval and never calls discovered tools', async () => {
    let release!: (value: unknown) => void
    const calls = stub({ rows: [{ ...connection, tools: [] }], mutate: () => new Promise(resolve => { release = resolve }) })
    render(<ExternalConnections />)
    await screen.findByRole('option', { name: connection.name })
    fireEvent.change(screen.getByLabelText('Conexión'), { target: { value: connection.id } })
    const button = screen.getByRole('button', { name: 'Descubrir herramientas' }) as HTMLButtonElement
    expect(button.disabled).toBe(true)
    fireEvent.click(screen.getByLabelText('Autorizo contactar este servicio para descubrir herramientas'))
    fireEvent.click(button)
    expect(await screen.findByText('Contactando el servicio…')).toBeTruthy()
    expect((screen.getByLabelText('Conexión') as HTMLSelectElement).closest('fieldset')?.disabled).toBe(true)
    await act(async () => release(response({ connection: { ...connection, state: 'connected' }, tools: [tool] })))
    await screen.findByText('1 herramientas descubiertas. Ninguna ejecutada.')
    expect(calls[1]).toEqual({ url: '/api/connections/conn-one/discover', method: 'POST', body: { confirmed: true } })
    expect(calls.length).toBe(2)
    expect((screen.getByLabelText('Autorizo contactar este servicio para descubrir herramientas') as HTMLInputElement).checked).toBe(false)
  })

  it.each(['api', 'empty', 'error', 'invalid'])('renders discovery response without fabricating invocation (%s)', async scenario => {
    const calls = stub({ rows: [{ ...connection, kind: scenario === 'api' ? 'http_api' : 'mcp', method: scenario === 'api' ? 'GET' : null, tools: [] }], mutate: async () => scenario === 'error' ? response({ detail: { message: 'Découverte indisponible.' } }, 503) : response({ connection: scenario === 'invalid' ? { ...connection, id: 'other' } : { ...connection, kind: scenario === 'api' ? 'http_api' : 'mcp', state: 'configured' }, tools: scenario === 'empty' ? [] : [tool] }) })
    render(<ExternalConnections />)
    await screen.findByRole('option', { name: connection.name })
    fireEvent.change(screen.getByLabelText('Conexión'), { target: { value: connection.id } })
    fireEvent.click(screen.getByLabelText('Autorizo contactar este servicio para descubrir herramientas'))
    fireEvent.click(screen.getByRole('button', { name: 'Descubrir herramientas' }))
    if (scenario === 'api') expect(await screen.findByText('Endpoint preparado. El acceso se comprobará al ejecutar una solicitud.')).toBeTruthy()
    else if (scenario === 'empty') expect(await screen.findByText('0 herramientas descubiertas. Ninguna ejecutada.')).toBeTruthy()
    else expect((await screen.findByRole('alert')).textContent).toContain(scenario === 'error' ? 'Découverte indisponible.' : 'otra conexión')
    expect(screen.queryByRole('region', { name: 'Recibo de ejecución' })).toBeNull()
    expect(calls.length).toBe(2)
  })

  it('rejects malformed JSON locally and resets approval on every payload change', async () => {
    const calls = stub()
    render(<ExternalConnections />)
    await selectTool()
    authorize()
    fireEvent.change(screen.getByLabelText('Argumentos JSON'), { target: { value: '[]' } })
    expect((screen.getByLabelText('Autorizo esta herramienta con estos argumentos y este efecto') as HTMLInputElement).checked).toBe(false)
    authorize(); execute()
    expect(await screen.findByText('Los argumentos deben ser un objeto JSON válido.')).toBeTruthy()
    expect(calls.length).toBe(1)
    authorize()
    fireEvent.change(screen.getByLabelText('Efecto'), { target: { value: 'READ' } })
    expect((screen.getByLabelText('Autorizo esta herramienta con estos argumentos y este efecto') as HTMLInputElement).checked).toBe(false)
    authorize()
    fireEvent.change(screen.getByLabelText('Herramienta'), { target: { value: '' } })
    expect(screen.queryByLabelText('Autorizo esta herramienta con estos argumentos y este efecto')).toBeNull()
  })

  it('renders only server-observed receipt identity, loading and escaped remote output', async () => {
    let release!: (value: unknown) => void
    const calls = stub({ mutate: () => new Promise(resolve => { release = resolve }) })
    render(<ExternalConnections />)
    await selectTool(); authorize(); execute()
    expect(await screen.findByText('Ejecutando la operación autorizada…')).toBeTruthy()
    await act(async () => release(response(invocation)))
    const receipt = within(await screen.findByRole('region', { name: 'Recibo de ejecución' }))
    expect(receipt.getByText('receipt-one')).toBeTruthy()
    expect(receipt.getByText('trace-one')).toBeTruthy()
    expect(receipt.getByText('Sí')).toBeTruthy()
    expect(document.querySelector('img')).toBeNull()
    expect(receipt.getByText(/<img src=x onerror=alert\(1\)>/)).toBeTruthy()
    expect(calls[1].body).toEqual({ tool_name: 'lookup', arguments: {}, effect: 'WRITE', tool_fingerprint: 'fingerprint-a', confirmed: true })
    fireEvent.change(screen.getByLabelText('Argumentos JSON'), { target: { value: '{"query":"new"}' } })
    expect(screen.queryByRole('region', { name: 'Recibo de ejecución' })).toBeNull()
    expect((screen.getByRole('button', { name: 'Ejecutar herramienta' }) as HTMLButtonElement).disabled).toBe(true)
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
    expect(screen.getByText('Guardada · acceso sin comprobar')).toBeTruthy()
    authorize(); execute()
    expect(await screen.findByText('Conectada')).toBeTruthy()
    expect(screen.getByRole('region', { name: 'Recibo de ejecución' })).toBeTruthy()
    expect(calls.map(call => `${call.method} ${call.url}`)).toEqual(['GET /api/connections', 'POST /api/connections/conn-one/invoke', 'GET /api/connections'])
  })

  it.each(['missing', 'wrong-connection', 'wrong-tool', 'missing-sha', 'false-success'])('rejects invalid receipt identity (%s)', async scenario => {
    const bad = scenario === 'missing' ? {} : scenario === 'wrong-connection' ? { ...invocation, connection_id: 'other' } : scenario === 'wrong-tool' ? { ...invocation, tool_name: 'other' } : scenario === 'missing-sha' ? { ...invocation, evidence: {} } : { ...invocation, actual_effect: { called: false } }
    stub({ mutate: async () => response(bad) })
    render(<ExternalConnections />)
    await selectTool(); authorize(); execute()
    expect((await screen.findByRole('alert')).textContent).toContain('Recibo ausente, incoherente o de otra operación')
    expect(screen.queryByText('Solicitud completada · recibo de ADL')).toBeNull()
  })

  it.each(['DENIED', 'ERROR'])('shows %s without a success claim', async outcome => {
    stub({ mutate: async () => response({ ...invocation, decision: outcome === 'DENIED' ? 'REQUIRE_HUMAN' : 'ALLOW', execution_outcome: outcome, actual_effect: { called: outcome === 'ERROR' }, error: { code: 'test', message: 'No completada.' } }) })
    render(<ExternalConnections />)
    await selectTool(); authorize(); execute()
    const receipt = within(await screen.findByRole('region', { name: 'Recibo de ejecución' }))
    expect(receipt.getByText(outcome)).toBeTruthy()
    expect(screen.queryByText('Solicitud completada · recibo de ADL')).toBeNull()
  })

  it.each(['GET', 'POST'])('fixes API %s effect and reports invocation request errors', async method => {
    const calls = stub({ rows: [{ ...connection, kind: 'http_api', method }], mutate: async () => response({ detail: { code: 'transport', message: 'Servicio no disponible.' } }, 503) })
    render(<ExternalConnections />)
    await selectTool()
    expect((screen.getByLabelText('Efecto') as HTMLSelectElement).disabled).toBe(true)
    expect((screen.getByLabelText('Efecto') as HTMLSelectElement).value).toBe(method === 'GET' ? 'READ' : 'WRITE')
    authorize(); execute()
    expect((await screen.findByRole('alert')).textContent).toContain('Servicio no disponible.')
    expect(calls[1].body.effect).toBe(method === 'GET' ? 'READ' : 'WRITE')
    expect(screen.queryByRole('region', { name: 'Recibo de ejecución' })).toBeNull()
  })
})
