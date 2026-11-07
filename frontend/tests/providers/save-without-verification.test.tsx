// @vitest-environment jsdom
import React from 'react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import ProviderSettings from '../../src/components/ProviderSettings'
import { resetLocaleForTests } from '../../src/i18n'

beforeEach(() => { localStorage.clear(); resetLocaleForTests() })
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks() })

it.each(['codex', 'github-copilot'])('guarda %s sin iniciar la comprobación de inferencia', async provider => {
  const calls: Array<{ url: string; method: string }> = []
  const registration = (id: string) => ({ provider_id: id, state: 'configured_unverified', model_id: 'synthetic-model', auth_mode: id === 'codex' ? 'codex_cli' : 'copilot_cli', runtime_support: 'chat_and_agent_runner', has_credential: false })
  vi.stubGlobal('fetch', vi.fn(async (input: string, init?: RequestInit) => {
    const url = String(input); const method = init?.method || 'GET'; calls.push({ url, method })
    let body: any
    if (url === '/api/providers/registry') body = { registrations: [registration('codex'), registration('github-copilot')] }
    else if (url === '/api/providers/ollama/status') body = { state: 'not_configured' }
    else if (url === '/api/providers/codex/session') body = { authenticated: true, auth_mode: 'chatgpt', models: [{ model_id: 'synthetic-model', display_name: 'Synthetic model', is_default: true }] }
    else if (url === '/api/providers/github-copilot/session') body = { authenticated: true }
    else if (url === '/api/providers/github-copilot/models') body = { models: [{ provider_id: 'github-copilot', model_id: 'synthetic-model', display_name: 'Synthetic model' }] }
    else if (url === `/api/providers/registry/${provider}` && method === 'PUT') body = registration(provider)
    else throw new Error(`Petición inesperada: ${method} ${url}`)
    return { ok: true, status: 200, json: async () => body }
  }))

  render(<ProviderSettings />)
  await waitFor(() => expect(screen.queryByText('Cargando registros guardados.')).toBeNull())
  fireEvent.click(screen.getByRole('tab', { name: provider === 'codex' ? /OpenAI/ : /GitHub Copilot/ }))
  if (provider === 'codex') {
    const region = within(screen.getByRole('region', { name: 'ChatGPT / Codex' }))
    await region.findByRole('option', { name: /Synthetic model/ })
    fireEvent.click(region.getByRole('button', { name: 'Guardar registro' }))
  } else {
    await screen.findByRole('option', { name: 'Synthetic model' })
    fireEvent.click(screen.getByRole('button', { name: 'Guardar registro' }))
  }
  await screen.findByText('Acceso guardado.')
  expect(calls).toContainEqual({ url: `/api/providers/registry/${provider}`, method: 'PUT' })
  expect(calls.some(call => call.url === `/api/providers/registry/${provider}/verify`)).toBe(false)
})

it('no permite guardar Copilot mientras se actualiza su catálogo', async () => {
  let finish: ((value: any) => void) | undefined
  const copilot = { provider_id: 'github-copilot', state: 'configured_unverified', model_id: 'synthetic-model', auth_mode: 'copilot_cli', runtime_support: 'chat_and_agent_runner', has_credential: false }
  vi.stubGlobal('fetch', vi.fn(async (input: string) => {
    const url = String(input)
    if (url === '/api/providers/registry') return { ok: true, json: async () => ({ registrations: [copilot] }) }
    if (url === '/api/providers/ollama/status') return { ok: true, json: async () => ({ state: 'not_configured' }) }
    if (url === '/api/providers/github-copilot/session') return { ok: true, json: async () => ({ authenticated: true }) }
    if (url === '/api/providers/github-copilot/models') return new Promise(resolve => { finish = resolve })
    throw new Error(`Petición inesperada: ${url}`)
  }))
  render(<ProviderSettings />)
  await waitFor(() => expect(screen.queryByText('Cargando registros guardados.')).toBeNull())
  fireEvent.click(screen.getByRole('tab', { name: /GitHub Copilot/ }))
  await waitFor(() => expect(finish).toBeDefined())
  expect((screen.getByRole('button', { name: 'Guardar registro' }) as HTMLButtonElement).disabled).toBe(true)
  expect((screen.getByRole('button', { name: 'Guardar y comprobar acceso' }) as HTMLButtonElement).disabled).toBe(true)
  finish?.({ ok: true, json: async () => ({ models: [{ provider_id: 'github-copilot', model_id: 'synthetic-model', display_name: 'Synthetic model' }] }) })
  await screen.findByRole('option', { name: 'Synthetic model' })
  await waitFor(() => expect((screen.getByRole('button', { name: 'Guardar registro' }) as HTMLButtonElement).disabled).toBe(false))
})

it('no permite cambiar el token durante la carga y descarta modelos al editarlo después', async () => {
  let finish: ((value: any) => void) | undefined
  const copilot = { provider_id: 'github-copilot', state: 'configured_unverified', model_id: 'synthetic-model', auth_mode: 'token', runtime_support: 'chat_and_agent_runner', has_credential: true }
  vi.stubGlobal('fetch', vi.fn(async (input: string) => {
    const url = String(input)
    if (url === '/api/providers/registry') return { ok: true, json: async () => ({ registrations: [copilot] }) }
    if (url === '/api/providers/ollama/status') return { ok: true, json: async () => ({ state: 'not_configured' }) }
    if (url === '/api/providers/github-copilot/models') return new Promise(resolve => { finish = resolve })
    throw new Error(`Petición inesperada: ${url}`)
  }))
  render(<ProviderSettings />)
  await waitFor(() => expect(screen.queryByText('Cargando registros guardados.')).toBeNull())
  fireEvent.click(screen.getByRole('tab', { name: /GitHub Copilot/ }))
  fireEvent.click(screen.getByRole('button', { name: 'Cargar modelos disponibles' }))
  await waitFor(() => expect(finish).toBeDefined())
  const token = screen.getByLabelText(/Token de GitHub/, { selector: 'input[type=password]' }) as HTMLInputElement
  expect(token.disabled).toBe(true)
  finish?.({ ok: true, json: async () => ({ models: [{ provider_id: 'github-copilot', model_id: 'synthetic-model', display_name: 'Synthetic model' }] }) })
  await screen.findByRole('option', { name: 'Synthetic model' })
  fireEvent.change(token, { target: { value: 'NEW_TOKEN_FIXTURE' } })
  expect(screen.queryByRole('option', { name: 'Synthetic model' })).toBeNull()
  expect((screen.getByRole('button', { name: 'Guardar registro' }) as HTMLButtonElement).disabled).toBe(true)
})
