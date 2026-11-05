// @vitest-environment jsdom
import React from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { resetLocaleForTests } from '../../src/i18n'
import ProviderSettings from '../../src/components/ProviderSettings'

const registration = { provider_id: 'openai-platform', state: 'configured_unverified', model_id: 'fixture-model', auth_mode: 'api_key', has_credential: true, base_url: null, runtime_support: 'chat_and_agent_runner' }
const response = (body: unknown, status = 200) => ({ ok: status < 400, status, json: async () => body })

beforeEach(() => { localStorage.clear(); resetLocaleForTests() })
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks() })

describe('provider verification completion', () => {
  it.each(['success', 'failure'])('allows another operation after %s', async (outcome) => {
    let verifyCalls = 0
    vi.stubGlobal('fetch', vi.fn(async (input: string, init?: RequestInit) => {
      const url = String(input)
      if (url === '/api/providers/registry') return response({ registrations: [registration] })
      if (url === '/api/providers/ollama/status') return response({ state: 'not_configured' })
      if (url === '/api/providers/codex/session') return response({ authenticated: false, models: [] })
      if (url === '/api/providers/registry/openai-platform' && init?.method === 'PUT') return response(registration)
      if (url === '/api/providers/registry/openai-platform/verify') {
        verifyCalls++
        return outcome === 'success' ? response({ ...registration, state: 'ready' }) : response({ detail: { code: 'provider_error', message: 'Fixture failure' } }, 503)
      }
      throw new Error(`Unexpected request: ${url}`)
    }))
    render(<ProviderSettings />)
    await waitFor(() => expect(screen.queryByText('Cargando registros guardados.')).toBeNull())
    fireEvent.click(screen.getByRole('tab', { name: /OpenAI/ }))
    const platform = within(screen.getByRole('region', { name: 'OpenAI Platform' }))
    const button = platform.getByRole('button', { name: 'Guardar y comprobar acceso' }) as HTMLButtonElement
    fireEvent.click(button)
    await waitFor(() => expect(verifyCalls).toBe(1))
    await waitFor(() => expect(button.disabled).toBe(false))
    expect(button.textContent).toBe('Guardar y comprobar acceso')
    fireEvent.click(button)
    await waitFor(() => expect(verifyCalls).toBe(2))
    await waitFor(() => expect(button.disabled).toBe(false))
  })
})
