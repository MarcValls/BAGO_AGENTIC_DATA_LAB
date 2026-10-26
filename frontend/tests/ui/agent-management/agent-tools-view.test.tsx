// @vitest-environment jsdom
import React from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { resetLocaleForTests, setLocale } from '../../../src/i18n'
import AgentToolsView from '../../../src/components/AgentToolsView'

beforeEach(() => { localStorage.clear(); resetLocaleForTests(); setLocale('es') })
afterEach(() => { cleanup(); vi.unstubAllGlobals() })

const profile = { id: 'agent-a', config: { name: 'Auditoría', description: 'Revisa documentos', type: 'tool', system_prompt: '', tools: ['document_extract'], task: { prompt: 'Revisa', dates: [] } } }

describe('Agentes > Herramientas', () => {
  it('shows catalog assignment separately from connection and execution, and opens the existing editor', async () => {
    const fetcher = vi.fn(async (input: string) => {
      const path = String(input)
      const body = path === '/api/capabilities'
        ? { agent_tools: [{ id: 'document_extract', name: 'Extraer documento', status: 'AVAILABLE', assignable: true }] }
        : path === '/api/agents/list' ? { agents: [profile] }
        : path === '/api/agents/agent-a' ? profile
        : path === '/api/agent-tools/templates' ? { templates: [] }
        : path === '/api/providers/chat-models' ? { models: [] }
        : { agent_tools: [] }
      return { ok: true, status: 200, json: async () => body }
    })
    vi.stubGlobal('fetch', fetcher)
    render(<AgentToolsView onOpenConnections={vi.fn()} onCreateAgent={vi.fn()} />)
    expect(await screen.findByText('Extraer documento')).toBeTruthy()
    expect(screen.getAllByText('Auditoría')).toHaveLength(2)
    expect(screen.getByText(/no concede permisos ni demuestra/i)).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Revisar asignación' }))
    await waitFor(() => expect(fetcher).toHaveBeenCalledWith('/api/agents/agent-a', expect.anything()))
    expect(await screen.findByText('Editar agente')).toBeTruthy()
  })

  it('keeps external connection setup as an explicit navigation action', async () => {
    const openConnections = vi.fn()
    vi.stubGlobal('fetch', vi.fn(async (input: string) => ({ ok: true, status: 200, json: async () => String(input) === '/api/capabilities' ? { agent_tools: [] } : { agents: [] } })))
    render(<AgentToolsView onOpenConnections={openConnections} onCreateAgent={vi.fn()} />)
    fireEvent.click(await screen.findByRole('button', { name: 'Configurar conexiones externas' }))
    expect(openConnections).toHaveBeenCalledOnce()
  })
})
