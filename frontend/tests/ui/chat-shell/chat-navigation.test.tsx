// @vitest-environment jsdom
import React from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { resetLocaleForTests, setLocale } from '../../../src/i18n'
import ChatNavigation from '../../../src/components/ChatNavigation'

beforeEach(() => { localStorage.clear(); resetLocaleForTests(); setLocale('es') })
afterEach(() => { cleanup(); vi.restoreAllMocks() })

describe('Chat submenu', () => {
  it('groups general chat and capabilities and selects the requested destination', () => {
    const onNavigate = vi.fn()
    render(<ChatNavigation activeView="chat" collapsed={false} onExpandSidebar={vi.fn()} onNavigate={onNavigate} />)
    const parent = screen.getByRole('button', { name: 'BAGO5' })
    expect(parent.getAttribute('aria-expanded')).toBe('true')
    const group = screen.getByRole('group', { name: 'Chat' })
    expect(within(group).getAllByRole('button').map(button => button.textContent?.trim())).toEqual(['◉Chat', '◇Capacidades'])
    fireEvent.click(within(group).getByRole('button', { name: /Capacidades/ }))
    expect(onNavigate).toHaveBeenCalledExactlyOnceWith('capabilities')
  })

  it('folds on Escape and returns keyboard focus to the Chat parent', () => {
    render(<ChatNavigation activeView="capabilities" collapsed={false} onExpandSidebar={vi.fn()} onNavigate={vi.fn()} />)
    const parent = screen.getByRole('button', { name: 'BAGO5' })
    const capability = screen.getByRole('button', { name: /Capacidades/ })
    capability.focus()
    fireEvent.keyDown(capability, { key: 'Escape' })
    expect(parent.getAttribute('aria-expanded')).toBe('false')
    expect(document.activeElement).toBe(parent)
    expect(screen.queryByRole('button', { name: /Capacidades/ })).toBeNull()
  })
})
