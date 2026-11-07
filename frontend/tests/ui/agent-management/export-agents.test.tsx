// @vitest-environment jsdom
import React from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import AgentManagement from '../../../src/components/AgentManagement'
import { setLocale } from '../../../src/i18n'

const props = { onCreate: vi.fn(), onTest: vi.fn(), onEvaluate: vi.fn() }

beforeEach(() => setLocale('es'))
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals() })

describe('Exportación desde Mis agentes', () => {
  it('descarga la respuesta JSON con el nombre previsto', async () => {
    const blob = new Blob(['{"agents":[]}'], { type: 'application/json' })
    const fetchMock = vi.fn(async (path: string) => path === '/api/agents/export'
      ? { ok: true, blob: async () => blob }
      : { ok: true, json: async () => ({ agents: [] }) })
    vi.stubGlobal('fetch', fetchMock)
    const create = vi.fn(() => 'blob:export-test')
    const revoke = vi.fn()
    const NativeURL = URL
    class TestURL extends NativeURL {
      static createObjectURL = create
      static revokeObjectURL = revoke
    }
    vi.stubGlobal('URL', TestURL)
    let filename = ''
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) { filename = this.download })

    render(<AgentManagement {...props} />)
    fireEvent.click(screen.getByRole('button', { name: 'Exportar todos los agentes' }))
    await waitFor(() => expect(filename).toBe('agents-export.json'))
    expect(fetchMock).toHaveBeenCalledWith('/api/agents/export')
    expect(create).toHaveBeenCalledWith(blob)
    expect(revoke).toHaveBeenCalledWith('blob:export-test')
  })

  it('muestra el error sin ocultar la lista de agentes', async () => {
    const agent = { id: 'agent_1234abcd', created_at: '2026-10-17T12:00:00Z', config: { name: 'Agente de prueba', description: 'Perfil sintético', type: 'tool', tools: [] } }
    vi.stubGlobal('fetch', vi.fn(async (path: string) => path === '/api/agents/export'
      ? { ok: false }
      : { ok: true, json: async () => ({ agents: [agent] }) }))
    render(<AgentManagement {...props} />)
    await screen.findByRole('heading', { name: 'Agente de prueba' })
    fireEvent.click(screen.getByRole('button', { name: 'Exportar todos los agentes' }))
    expect((await screen.findByRole('alert')).textContent).toContain('No se pudieron exportar los perfiles de agentes.')
    expect(screen.getByRole('heading', { name: 'Agente de prueba' })).toBeTruthy()
    await waitFor(() => expect((screen.getByRole('button', { name: 'Exportar todos los agentes' }) as HTMLButtonElement).disabled).toBe(false))
  })
})
