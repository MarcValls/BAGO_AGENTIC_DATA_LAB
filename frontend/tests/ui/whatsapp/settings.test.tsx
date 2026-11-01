// @vitest-environment jsdom
import React from 'react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import WhatsAppSettings from '../../../src/components/WhatsAppSettings'
import {resetLocaleForTests, setLocale} from '../../../src/i18n'
const response = (body: unknown, status = 200) => ({ ok: status < 400, status, json: async () => body })
const state = { state: 'disconnected', configured: true, label: 'BAGO prueba', checked_at: '2026-10-22T10:00:00Z', reason: null, browser_available: true, persistent_profile: true }
const authorization={available:true,enabled:false,revision:'none',grant_id:null,project:{project_id:'private-project',root:'D:/private-fixture',binding:'opaque-binding'},session_identity:'a'.repeat(64),validity:'until_revoked',granted_at:null,revoked_at:null}
const authorizationUrl='/api/communications/whatsapp-authorization'
beforeEach(()=>{localStorage.clear();resetLocaleForTests();setLocale('es')})
afterEach(() => { cleanup(); vi.unstubAllGlobals() })
it('does not infer connection from saved configuration; opening sends explicit confirmation', async () => {
  const calls: unknown[] = []
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {if(url===authorizationUrl)return response(authorization); if (init?.method) calls.push(JSON.parse(String(init.body))); return response(state) }))
  render(<WhatsAppSettings />)
  await screen.findByText('Desconectada')
  expect(screen.queryByText('Conectada')).toBeNull()
  fireEvent.click(screen.getByRole('button', { name: 'Vincular WhatsApp' }))
  await waitFor(() => expect(calls).toEqual([{ confirmed: true }]))
})
it('clears connected display immediately on close and observes disconnected result', async () => {
  let current = { ...state, state: 'connected' }
  let finishClose: (()=>void)|undefined
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    if(url===authorizationUrl)return response(authorization)
    if(init?.method)return new Promise(resolve=>{finishClose=()=>{current={...state};resolve(response(current))}})
    return response(current)
  }))
  render(<WhatsAppSettings />)
  await screen.findByText('Conectada')
  fireEvent.click(screen.getByText('Avanzado'))
  fireEvent.click(screen.getByRole('button', { name: 'Cerrar navegador de vinculación' }))
  expect(screen.queryByText('Conectada')).toBeNull()
  expect(screen.getByRole('status').className).not.toContain('is-connected')
  await act(async()=>{finishClose!()})
  await screen.findByText('Desconectada')
})
it('displays unknown and error when the probe fails', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => response({ detail: 'Sonda no disponible' }, 503)))
  render(<WhatsAppSettings />)
  await screen.findByRole('alert')
  expect(screen.getByRole('status').textContent).toContain('Estado desconocido')
})
it.each([state,{...authorization,project:null},{...authorization,project:{root:'missing-project-identity'}},
  {...authorization,session_identity:undefined},{...authorization,enabled:'true'}])('fails closed on an invalid authorization response without editable authority',async bad=>{
  const writes:unknown[]=[]
  vi.stubGlobal('fetch',vi.fn(async(url:string,init?:RequestInit)=>{
    if(init?.method)writes.push(init)
    return response(url===authorizationUrl?bad:state)
  }))
  render(<WhatsAppSettings />)
  expect((await screen.findByRole('alert')).textContent).toContain('La autorización recibida no es válida')
  expect((screen.getByRole('checkbox',{name:'Permitir envíos automáticos por WhatsApp'}) as HTMLInputElement).disabled).toBe(true)
  expect((screen.getByLabelText('Nombre de la sesión') as HTMLInputElement).disabled).toBe(true)
  expect(writes).toEqual([])
})
