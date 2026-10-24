// @vitest-environment jsdom
import React from 'react'
import {resetLocaleForTests,setLocale,t} from '../../../src/i18n'
beforeEach(()=>{localStorage.clear();resetLocaleForTests();setLocale('es')})
import { beforeEach, afterEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import AgentChat from '../../../src/components/AgentChat'

afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks() })

function fixture(failure = false) {
  HTMLElement.prototype.scrollIntoView = vi.fn()
  let exists = true
  const conversation = { id: 'conv_fixture', owner_kind: 'assistant', owner_id: 'app-assistant', title: 'Synthetic trash item', status: 'deleted', revision: 2, updated_at: '2026-10-22T12:00:00Z' }
  const deletes: RequestInit[] = []
  vi.stubGlobal('fetch', vi.fn(async (input: string, init?: RequestInit) => {
    const url = String(input)
    if (init?.method === 'DELETE') {
      deletes.push(init)
      if (!failure) exists = false
      return { ok: !failure, status: failure ? 409 : 200, json: async () => failure ? { detail: { message: 'Conversation changed elsewhere.' } } : { id: conversation.id, status: 'permanently_deleted' } }
    }
    const body = url === '/api/agents/list' ? { agents: [] }
      : url === '/api/providers/chat-models' ? { models: [] }
      : url === '/api/providers/selection' ? null
      : url.startsWith('/api/conversations?') ? { conversations: url.includes('status=deleted') && exists ? [conversation] : [] }
      : url.startsWith('/api/capabilities/proposals?') ? { proposals: [] }
      : null
    return { ok: body !== null, status: body !== null ? 200 : 404, json: async () => body }
  }))
  render(<AgentChat onNavigate={() => {}} />)
  return deletes
}

it('shows permanent deletion only in trash, requires confirmation and clears selection after success', async () => {
  const deletes = fixture()
  const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true)
  expect(screen.queryByRole('button', { name: 'Eliminar definitivamente' })).toBeNull()
  fireEvent.click(screen.getByRole('button', { name: 'Papelera' }))
  const remove = await screen.findByRole('button', { name: 'Eliminar definitivamente' })
  fireEvent.click(remove)
  await waitFor(() => expect(deletes).toHaveLength(1))
  expect(confirm.mock.calls[0][0]).toContain('irreversible')
  expect(confirm.mock.calls[0][0]).toContain('Synthetic trash item')
  expect(JSON.parse(deletes[0].body as string)).toEqual({ expected_revision: 2, confirmed: true })
  await waitFor(() => expect(screen.queryByRole('button', { name: 'Eliminar definitivamente' })).toBeNull())
  expect(screen.queryByText('Synthetic trash item')).toBeNull()
})

it('cancelling the irreversible confirmation sends no DELETE', async () => {
  const deletes = fixture()
  vi.spyOn(window, 'confirm').mockReturnValue(false)
  fireEvent.click(screen.getByRole('button', { name: 'Papelera' }))
  fireEvent.click(await screen.findByRole('button', { name: 'Eliminar definitivamente' }))
  expect(deletes).toHaveLength(0)
  expect(screen.getByText('Synthetic trash item')).not.toBeNull()
})

it('trash context menu exposes the same confirmation; conflict keeps the item and reports error', async () => {
  const deletes = fixture(true)
  vi.spyOn(window, 'confirm').mockReturnValue(true)
  fireEvent.click(screen.getByRole('button', { name: 'Papelera' }))
  const title = await screen.findByText('Synthetic trash item')
  fireEvent.contextMenu(title.closest('button')!)
  fireEvent.click(screen.getByRole('menuitem', { name: 'Eliminar definitivamente' }))
  await waitFor(() => expect(deletes).toHaveLength(1))
  expect(await screen.findByRole('alert')).not.toBeNull()
  expect(screen.getByText('Synthetic trash item')).not.toBeNull()
})
