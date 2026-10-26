// @vitest-environment jsdom
import React from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { resetLocaleForTests, setLocale } from '../../../src/i18n'
import ToolsConnectionsView from '../../../src/components/ToolsConnectionsView'

beforeEach(() => { localStorage.clear(); resetLocaleForTests(); setLocale('es'); vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ connections: [] }), { status: 200 }))) })
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals() })

describe('Settings > External connections page', () => {
  it('explains connection versus per-agent assignment and renders the real connections surface', async () => {
    render(<ToolsConnectionsView />)
    expect(screen.getAllByRole('heading', { name: 'Conexiones externas' })).toHaveLength(2)
    expect(screen.getByText(/no las asigna a un agente ni las ejecuta/)).toBeTruthy()
  })
})
