// @vitest-environment jsdom
import React from 'react'
import {resetLocaleForTests} from '../../src/i18n'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import ModelAssignments from '../../src/components/ModelAssignments'

const catalog = [
  { provider_id: 'ollama-cloud', model_id: 'alpha', display_name: 'Alpha', label: 'Ollama', state: 'ready' },
  { provider_id: 'ollama-cloud', model_id: 'beta', display_name: 'Beta', label: 'Ollama', state: 'ready' },
  { provider_id: 'codex', model_id: 'gamma', display_name: 'Gamma', label: 'OpenAI Codex', state: 'configured_unverified' },
]
const initial = { models: [], main_chat: null, revision: 'revision-1', catalog, warnings: [] }
const response = (body: unknown, status = 200) => ({ ok: status < 400, status, json: async () => body })

beforeEach(()=>{localStorage.clear();resetLocaleForTests()})

afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks() })

describe('Model assignments', () => {
  it('groups the catalog by provider and saves orchestrator and all-agent assignments independently', async () => {
    let saved: any
    vi.stubGlobal('fetch', vi.fn(async (input: string, init?: RequestInit) => {
      if (String(input) === '/api/providers/model-policy' && !init?.method) return response(initial)
      if (String(input) === '/api/providers/model-policy' && init?.method === 'PUT') {
        saved = JSON.parse(String(init.body))
        return response({ ...saved, revision: 'revision-2', configured: true })
      }
      throw new Error(`Unexpected request: ${String(input)}`)
    }))

    render(<ModelAssignments onExit={() => undefined} />)
    expect(await screen.findByRole('region', { name: 'Modelos de Ollama' })).toBeTruthy()
    expect(screen.getByRole('region', { name: 'Modelos de OpenAI Codex' })).toBeTruthy()

    const alpha = 'ollama-cloud|alpha'
    const beta = 'ollama-cloud|beta'
    fireEvent.click(screen.getByRole('checkbox', { name: `Orquestador · ${alpha}` }))
    fireEvent.click(screen.getByRole('radio', { name: `Principal · ${alpha}` }))
    fireEvent.click(screen.getByRole('checkbox', { name: `Recuperación (RAG) · ${alpha}` }))
    fireEvent.click(screen.getByRole('checkbox', { name: `Todos los agentes · ${beta}` }))
    fireEvent.click(screen.getByRole('button', { name: 'Guardar' }))
    await screen.findByText('Selección guardada.')

    const alphaUse = saved.models.find((item: any) => item.model_id === 'alpha')
    const betaUse = saved.models.find((item: any) => item.model_id === 'beta')
    expect(saved.main_chat).toBe(alpha)
    expect(alphaUse).toMatchObject({ chat: true, orchestrator: true, agent_types: ['rag'] })
    expect(betaUse).toMatchObject({ chat: false, orchestrator: false, agent_types: ['rag', 'tool', 'multi-agent'] })
    expect(within(screen.getByRole('region', { name: 'Modelos de OpenAI Codex' })).getByText('Desactivado')).toBeTruthy()
  })
})
