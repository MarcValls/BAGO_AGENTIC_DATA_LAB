// @vitest-environment jsdom
import React from 'react'
import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import WhatsAppSettings from '../../../src/components/WhatsAppSettings'
const response = (body: unknown, status = 200) => ({ ok: status < 400, status, json: async () => body })
const state = { state: 'disconnected', configured: true, label: 'BAGO prueba', checked_at: '2026-10-22T10:00:00Z', reason: null, browser_available: true, persistent_profile: true }
afterEach(() => { cleanup(); vi.unstubAllGlobals() })
it('does not infer connection from saved configuration; opening sends explicit confirmation', async () => {
  const calls: unknown[] = []
  vi.stubGlobal('fetch', vi.fn(async (_url: string, init?: RequestInit) => { if (init?.method) calls.push(JSON.parse(String(init.body))); return response(state) }))
  render(<WhatsAppSettings />)
  await screen.findByText('Desconectada')
  expect(screen.queryByText('Conectada')).toBeNull()
  fireEvent.click(screen.getByRole('button', { name: 'Abrir navegador y vincular QR' }))
  await waitFor(() => expect(calls).toEqual([{ confirmed: true }]))
})
it('clears connected display immediately on close and observes disconnected result', async () => {
  let current = { ...state, state: 'connected' }
  vi.stubGlobal('fetch', vi.fn(async (_url: string, init?: RequestInit) => { if (init?.method) current = { ...state }; return response(current) }))
  render(<WhatsAppSettings />)
  await screen.findByText('Conectada')
  fireEvent.click(screen.getByRole('button', { name: 'Cerrar navegador conservando sesión' }))
  expect(screen.queryByText('Conectada')).toBeNull()
  await screen.findByText('Desconectada')
})
it('displays unknown and error when the probe fails', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => response({ detail: 'Sonda no disponible' }, 503)))
  render(<WhatsAppSettings />)
  await screen.findByRole('alert')
  expect(screen.getByRole('status').textContent).toContain('Estado desconocido')
})
