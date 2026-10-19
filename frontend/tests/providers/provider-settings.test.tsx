// @vitest-environment jsdom
import React from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import ProviderSettings from '../../src/components/ProviderSettings'
import AgentBuilder from '../../src/components/AgentBuilder'

const response = (body: unknown, status = 200) => ({ ok: status < 400, status, json: async () => body })
const unconfigured = { provider_id: 'openai-platform', state: 'not_configured', model_id: null, auth_mode: null, has_credential: false, base_url: null, runtime_support: 'chat_and_agent_runner' }
const configured = { ...unconfigured, state: 'configured_unverified', model_id: 'gpt-test', auth_mode: 'api_key', has_credential: true, updated_at: '2026-10-20T10:00:00Z' }

afterEach(() => { cleanup(); vi.unstubAllGlobals() })

describe('Provider settings behavior with simulated API responses', () => {
  it('shows integration before registration, saves a write-only key, and waits for a real verification response', async () => {
    let current = { ...unconfigured }
    const requests: Array<{ url: string; body: any }> = []
    let finishVerification: ((value: any) => void) | undefined
    vi.stubGlobal('fetch', vi.fn(async (input: string, init?: RequestInit) => {
      const url = String(input)
      if (url === '/api/providers/registry') return response({ registrations: [current] })
      if (url === '/api/providers/ollama/status') return response({ state: 'not_configured', auth_mode: null, model_id: null })
      if (url.endsWith('/verify')) return new Promise(resolve => { finishVerification = resolve })
      if (url === '/api/providers/registry/openai-platform' && init?.method === 'PUT') {
        requests.push({ url, body: JSON.parse(String(init.body)) })
        current = { ...configured }
        return response(current)
      }
      throw new Error(`Unexpected request: ${url}`)
    }))
    render(<ProviderSettings />)
    await waitFor(() => expect(screen.queryByText('Cargando registros guardados…')).toBeNull())
    fireEvent.click(screen.getByRole('tab', { name: /OpenAI Platform/ }))
    expect(await screen.findByText('Disponible para chat de agentes y Agent Runner')).toBeTruthy()
    expect(screen.queryByText('El registro no confirma acceso en vivo')).toBeNull()
    const verify = screen.getByRole('button', { name: 'Comprobar acceso en vivo' }) as HTMLButtonElement
    expect(verify.disabled).toBe(true)
    fireEvent.change(screen.getByLabelText(/API key/, { selector: 'input' }), { target: { value: 'TEST_SECRET_WRITE_ONLY' } })
    fireEvent.change(screen.getByLabelText('Modelo predeterminado'), { target: { value: 'gpt-test' } })
    fireEvent.click(screen.getByRole('button', { name: 'Guardar registro' }))
    await waitFor(() => expect(verify.disabled).toBe(false))
    expect(requests[0].body.api_key).toBe('TEST_SECRET_WRITE_ONLY')
    expect((screen.getByLabelText(/API key/, { selector: 'input' }) as HTMLInputElement).value).toBe('')
    expect(screen.queryByText('Acceso comprobado con una respuesta real')).toBeNull()
    fireEvent.click(verify)
    expect(screen.getByRole('button', { name: 'Comprobando acceso…' })).toBeTruthy()
    expect(screen.queryByText('Acceso comprobado con una respuesta real')).toBeNull()
    finishVerification?.(response({ ...configured, state: 'ready', last_verified_at: '2026-10-20T10:05:00Z', generation_performed: true }))
    expect(await screen.findByText('Acceso comprobado con una respuesta real')).toBeTruthy()
    fireEvent.change(screen.getByLabelText('Modelo predeterminado'), { target: { value: 'unsaved-model' } })
    expect((screen.getByRole('button', { name: 'Comprobar acceso en vivo' }) as HTMLButtonElement).disabled).toBe(true)
  })

  it('removes a previous confirmation when verification fails and reloads server status', async () => {
    let ready = true
    vi.stubGlobal('fetch', vi.fn(async (input: string) => {
      const url = String(input)
      if (url === '/api/providers/registry') return response({ registrations: [{ ...configured, state: ready ? 'ready' : 'needs_authentication', last_verified_at: ready ? '2026-10-20T10:00:00Z' : undefined }] })
      if (url === '/api/providers/ollama/status') return response({ state: 'not_configured' })
      if (url.endsWith('/verify')) { ready = false; return response({ detail: { message: 'La credencial fue rechazada.' } }, 401) }
      throw new Error(`Unexpected request: ${url}`)
    }))
    render(<ProviderSettings />)
    fireEvent.click(screen.getByRole('tab', { name: /OpenAI Platform/ }))
    await screen.findByText('Acceso comprobado con una respuesta real')
    await waitFor(() => expect((screen.getByRole('button', { name: 'Comprobar acceso en vivo' }) as HTMLButtonElement).disabled).toBe(false))
    fireEvent.click(screen.getByRole('button', { name: 'Comprobar acceso en vivo' }))
    expect(await screen.findByText('La credencial fue rechazada.')).toBeTruthy()
    await waitFor(() => expect(screen.queryByText('Acceso comprobado con una respuesta real')).toBeNull())
    expect(screen.getByText('Disponible para chat de agentes y Agent Runner')).toBeTruthy()
  })
})

describe('Agent provider selection with simulated API responses', () => {
  it('preserves an unpinned legacy profile when the user saves unrelated edits', async () => {
    let payload: any
    vi.stubGlobal('fetch', vi.fn(async (input: string, init?: RequestInit) => {
      if (String(input) === '/api/providers/available') return response({ providers: [{ provider_id: 'ollama-cloud', state: 'not_configured', model_id: null }] })
      if (String(input) === '/api/agents/agent_legacy') { payload = JSON.parse(String(init?.body)); return response({ id: 'agent_legacy', config: payload }) }
      throw new Error('Unexpected request')
    }))
    render(<AgentBuilder agentId="agent_legacy" initialAgent={{ name: 'Renamed legacy', description: 'Review', system_prompt: 'Review only', type: 'tool', tools: [] }} />)
    await waitFor(() => expect(screen.queryByText('Cargando proveedores…')).toBeNull())
    fireEvent.click(screen.getByRole('button', { name: /Preview/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Save changes' }))
    await screen.findByText(/Agent saved successfully/)
    expect(payload.provider_id).toBeUndefined()
    expect(payload.model_id).toBeUndefined()
  })

  it('shows inventory errors, retries and saves the provider/model chosen by the user', async () => {
    let attempts = 0
    let saved: any
    vi.stubGlobal('fetch', vi.fn(async (input: string, init?: RequestInit) => {
      if (String(input) === '/api/providers/available') {
        attempts += 1
        if (attempts === 1) return response({}, 503)
        return response({ providers: [
          { provider_id: 'ollama-cloud', state: 'not_configured', model_id: null },
          { provider_id: 'github-copilot', label: 'GitHub Copilot', state: 'configured_unverified', model_id: 'copilot-model' },
        ] })
      }
      if (String(input) === '/api/agents/create') { saved = JSON.parse(String(init?.body)); return response({ id: 'agent_saved', config: saved }) }
      throw new Error('Unexpected request')
    }))
    render(<AgentBuilder initialAgent={{ name: 'Review agent', description: 'Review', system_prompt: 'Review only', type: 'tool', tools: [] }} />)
    expect(screen.getByRole('status').textContent).toContain('Cargando proveedores')
    expect(await screen.findByText('No se pudo cargar el registro de proveedores.')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Reintentar' }))
    await waitFor(() => expect((screen.getByLabelText('Proveedor') as HTMLSelectElement).disabled).toBe(false))
    fireEvent.change(screen.getByLabelText('Proveedor'), { target: { value: 'github-copilot' } })
    expect((screen.getByLabelText('Modelo') as HTMLSelectElement).value).toBe('copilot-model')
    fireEvent.click(screen.getByRole('button', { name: /Preview/ }))
    fireEvent.click(screen.getByRole('button', { name: /Save Agent/ }))
    await screen.findByText(/Agent saved successfully/)
    expect(saved.provider_id).toBe('github-copilot')
    expect(saved.model_id).toBe('copilot-model')
  })
})
