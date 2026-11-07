// @vitest-environment jsdom
import React from 'react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import ProviderSettings from '../../src/components/ProviderSettings'
import { resetLocaleForTests } from '../../src/i18n'

beforeEach(() => { localStorage.clear(); resetLocaleForTests() })
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks() })

it('comprueba el catálogo sin enviar una petición de generación', async () => {
  const calls: Array<{ url: string; method: string }> = []
  vi.stubGlobal('fetch', vi.fn(async (input: string, init?: RequestInit) => {
    const url = String(input)
    calls.push({ url, method: init?.method || 'GET' })
    const body = url === '/api/providers/registry' ? { registrations: [] }
      : url === '/api/providers/ollama/status' ? { state: 'configured_unverified', auth_mode: 'local_cli', model_id: 'model-a' }
      : url === '/api/providers/ollama/models' ? { models: [{ provider_id: 'ollama-cloud', model_id: 'model-a', display_name: 'model-a' }] }
      : null
    if (!body) throw new Error(`Petición inesperada: ${url}`)
    return { ok: true, json: async () => body }
  }))

  render(<ProviderSettings />)
  await screen.findByText('Se encontraron 1 modelos. Comprueba el acceso al elegido.')
  fireEvent.click(within(screen.getByRole('tablist', { name: 'Configuración de Ollama' })).getByRole('tab', { name: 'Modelo', exact: true }))
  fireEvent.click(screen.getByRole('button', { name: 'Consultar disponibilidad sin generar' }))
  expect(await screen.findByText('model-a figura en el catálogo. No se ha generado ninguna respuesta.')).toBeTruthy()
  expect(calls.filter(call => call.url === '/api/providers/ollama/models')).toHaveLength(2)
  expect(calls.every(call => call.method === 'GET')).toBe(true)
})

it('bloquea cambios durante la consulta y borra el resultado al elegir otro modelo', async () => {
  let count = 0
  let finish: ((value: any) => void) | undefined
  const models = { models: ['model-a', 'model-b'].map(model_id => ({ provider_id: 'ollama-cloud', model_id, display_name: model_id })) }
  vi.stubGlobal('fetch', vi.fn(async (input: string) => {
    const url = String(input)
    if (url === '/api/providers/registry') return { ok: true, json: async () => ({ registrations: [] }) }
    if (url === '/api/providers/ollama/status') return { ok: true, json: async () => ({ state: 'configured_unverified', auth_mode: 'local_cli', model_id: 'model-a' }) }
    if (url === '/api/providers/ollama/models') {
      count++
      if (count > 1) return new Promise(resolve => { finish = resolve })
      return { ok: true, json: async () => models }
    }
    throw new Error(`Petición inesperada: ${url}`)
  }))
  render(<ProviderSettings />)
  await screen.findByText('Se encontraron 2 modelos. Comprueba el acceso al elegido.')
  fireEvent.click(within(screen.getByRole('tablist', { name: 'Configuración de Ollama' })).getByRole('tab', { name: 'Modelo', exact: true }))
  const model = screen.getByRole('combobox', { name: 'Modelo' }) as HTMLSelectElement
  fireEvent.click(screen.getByRole('button', { name: 'Consultar disponibilidad sin generar' }))
  await waitFor(() => expect(model.disabled).toBe(true))
  finish?.({ ok: true, json: async () => models })
  await screen.findByText('model-a figura en el catálogo. No se ha generado ninguna respuesta.')
  fireEvent.change(model, { target: { value: 'model-b' } })
  expect(screen.queryByText('model-a figura en el catálogo. No se ha generado ninguna respuesta.')).toBeNull()
})

it('mantiene el modelo consultado si desaparece del catálogo', async () => {
  let calls = 0
  vi.stubGlobal('fetch', vi.fn(async (input: string) => {
    const url = String(input)
    if (url === '/api/providers/registry') return { ok: true, json: async () => ({ registrations: [] }) }
    if (url === '/api/providers/ollama/status') return { ok: true, json: async () => ({ state: 'configured_unverified', auth_mode: 'local_cli', model_id: 'model-a' }) }
    if (url === '/api/providers/ollama/models') {
      calls++
      const model_id = calls === 1 ? 'model-a' : 'model-b'
      return { ok: true, json: async () => ({ models: [{ provider_id: 'ollama-cloud', model_id, display_name: model_id }] }) }
    }
    throw new Error(`Petición inesperada: ${url}`)
  }))
  render(<ProviderSettings />)
  await screen.findByText('Se encontraron 1 modelos. Comprueba el acceso al elegido.')
  fireEvent.click(within(screen.getByRole('tablist', { name: 'Configuración de Ollama' })).getByRole('tab', { name: 'Modelo', exact: true }))
  fireEvent.click(screen.getByRole('button', { name: 'Consultar disponibilidad sin generar' }))
  expect(await screen.findByText('model-a no figura en el catálogo. No se ha generado ninguna respuesta.')).toBeTruthy()
  expect((screen.getByRole('combobox', { name: 'Modelo' }) as HTMLSelectElement).value).toBe('model-a')
})

it('informa de un fallo de catálogo sin afirmar disponibilidad', async () => {
  let calls = 0
  vi.stubGlobal('fetch', vi.fn(async (input: string) => {
    const url = String(input)
    if (url === '/api/providers/registry') return { ok: true, json: async () => ({ registrations: [] }) }
    if (url === '/api/providers/ollama/status') return { ok: true, json: async () => ({ state: 'configured_unverified', auth_mode: 'local_cli', model_id: 'model-a' }) }
    if (url === '/api/providers/ollama/models') {
      calls++
      if (calls > 1) return { ok: false, status: 503, json: async () => ({ detail: { message: 'Catálogo no disponible.' } }) }
      return { ok: true, json: async () => ({ models: [{ provider_id: 'ollama-cloud', model_id: 'model-a', display_name: 'model-a' }] }) }
    }
    throw new Error(`Petición inesperada: ${url}`)
  }))
  render(<ProviderSettings />)
  await screen.findByText('Se encontraron 1 modelos. Comprueba el acceso al elegido.')
  fireEvent.click(within(screen.getByRole('tablist', { name: 'Configuración de Ollama' })).getByRole('tab', { name: 'Modelo', exact: true }))
  fireEvent.click(screen.getByRole('button', { name: 'Consultar disponibilidad sin generar' }))
  expect((await screen.findByRole('alert')).textContent).toContain('Catálogo no disponible.')
  expect(screen.queryByText('model-a figura en el catálogo. No se ha generado ninguna respuesta.')).toBeNull()
})

it('no consulta el catálogo con una clave nueva sin guardar', async () => {
  const calls: Array<{ url: string; method: string }> = []
  vi.stubGlobal('fetch', vi.fn(async (input: string, init?: RequestInit) => {
    const url = String(input)
    calls.push({ url, method: init?.method || 'GET' })
    if (url === '/api/providers/registry') return { ok: true, json: async () => ({ registrations: [] }) }
    if (url === '/api/providers/ollama/status') return { ok: true, json: async () => ({ state: 'configured_unverified', auth_mode: 'api_key', model_id: 'model-a' }) }
    if (url === '/api/providers/ollama/models') return { ok: true, json: async () => ({ models: [{ provider_id: 'ollama-cloud', model_id: 'model-a', display_name: 'model-a' }] }) }
    throw new Error(`Petición inesperada: ${url}`)
  }))
  render(<ProviderSettings />)
  await screen.findByText('Se encontraron 1 modelos. Comprueba el acceso al elegido.')
  fireEvent.change(screen.getByLabelText(/Clave API/, { selector: 'input[type=password]' }), { target: { value: 'UNSAVED_KEY_FIXTURE' } })
  fireEvent.click(within(screen.getByRole('tablist', { name: 'Configuración de Ollama' })).getByRole('tab', { name: 'Modelo', exact: true }))
  fireEvent.click(screen.getByRole('button', { name: 'Consultar disponibilidad sin generar' }))
  expect(await screen.findByText('Guarda primero el método de autenticación y la clave API antes de cargar modelos.')).toBeTruthy()
  expect(calls.filter(call => call.url === '/api/providers/ollama/models')).toHaveLength(1)
  expect(calls.every(call => call.method === 'GET')).toBe(true)
})
