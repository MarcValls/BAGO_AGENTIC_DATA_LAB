// @vitest-environment jsdom
import React from 'react'
import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import AgentChat from '../../../src/components/AgentChat'

afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks() })

it('keeps Send inside the text field frame and preserves empty-message submission rules', async () => {
  HTMLElement.prototype.scrollIntoView = vi.fn()
  const calls: string[] = []
  vi.stubGlobal('fetch', vi.fn(async (input: string) => {
    const url = String(input)
    calls.push(url)
    const body = url === '/api/agents/list' ? { agents: [] }
      : url === '/api/providers/chat-models' ? { models: [] }
      : url === '/api/providers/selection' ? null
      : url.startsWith('/api/conversations?') ? { conversations: [] }
      : null
    return { ok: body !== null, status: body !== null ? 200 : 404, json: async () => body }
  }))
  const { container } = render(<AgentChat onNavigate={() => {}} />)
  await waitFor(() => expect(calls.some(url => url.startsWith('/api/conversations?'))).toBe(true))
  const textarea = screen.getByRole('textbox', { name: 'Message the assistant or selected agent' }) as HTMLTextAreaElement
  const send = screen.getByRole('button', { name: 'Send', exact: true }) as HTMLButtonElement
  expect(textarea.parentElement?.classList.contains('chat-composer-input')).toBe(true)
  expect(textarea.parentElement?.contains(send)).toBe(true)
  expect(send.form).toBe(textarea.form)
  expect(send.type).toBe('submit')
  expect(send.disabled).toBe(true)
  fireEvent.change(textarea, { target: { value: '   ' } })
  expect(send.disabled).toBe(true)
  fireEvent.change(textarea, { target: { value: 'Un mensaje' } })
  expect(send.disabled).toBe(false)
  fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: true })
  expect(textarea.value).toBe('Un mensaje')
  expect(container.querySelector('.chat-composer-actions')?.contains(send)).toBe(false)
  expect(container.querySelector('.chat-composer-actions .chat-provider-picker')).not.toBeNull()
  expect(calls).not.toContain('/api/conversations')
})
