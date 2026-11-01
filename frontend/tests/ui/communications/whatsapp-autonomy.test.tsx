// @vitest-environment jsdom
import React from 'react'
import {afterEach, beforeEach, expect, it, vi} from 'vitest'
import {act, cleanup, fireEvent, render, screen, waitFor} from '@testing-library/react'
import WhatsAppSettings from '../../../src/components/WhatsAppSettings'
import {resetLocaleForTests, setLocale} from '../../../src/i18n'

beforeEach(() => {localStorage.clear(); resetLocaleForTests(); setLocale('es')})
afterEach(() => {cleanup(); vi.unstubAllGlobals(); vi.useRealTimers()})
const response = (value:unknown, status=200) => ({ok:status<400, status, json:async()=>value})
const consentLabel = 'Permitir envíos automáticos por WhatsApp'
const endpoint = '/api/communications/whatsapp-authorization'

function fixture({state='connected', configured=true, granted=false, authorizationError=false, rejectGrant=false, rejectLabel=false}={}) {
  const calls:Array<{url:string;method:string;body:any}> = []
  let session = {state, configured, label:'Sesión heredada', checked_at:'2026-11-01T12:00:00Z', reason:'controlled-fixture', browser_available:true, persistent_profile:true}
  let authorization = {available:true, enabled:granted, revision:granted?'a'.repeat(64):'none', grant_id:granted?'grant-fixture':null,
    project:{project_id:'fixture-project',root:'D:/private-fixture',binding:'opaque-not-a-root'},session_identity:'b'.repeat(64),validity:'until_revoked',granted_at:null,revoked_at:null}
  const fetcher = vi.fn(async(input:string, init?:RequestInit) => {
    const url=String(input),method=init?.method??'GET',body=init?.body?JSON.parse(String(init.body)):null
    calls.push({url,method,body})
    if (url==='/api/whatsapp/session' && method==='GET') return response(session)
    if (url===endpoint && method==='GET') return authorizationError?response({detail:{message:'Proyecto no disponible'}},409):response(authorization)
    if (url==='/api/whatsapp/session' && method==='PUT') {
      if (rejectLabel) return response({detail:{message:'No se pudo guardar'}},503)
      session={...session,label:body.label,configured:body.enabled,state:body.enabled?state:'not_configured'}
      return response(session)
    }
    if (url===endpoint && method==='PUT') {
      if (rejectGrant) return response({detail:{message:'La autorización cambió'}},409)
      authorization={...authorization,enabled:body.enabled,revision:'c'.repeat(64),grant_id:'grant-new'}
      return response(authorization)
    }
    throw new Error('Unexpected request; no browser or send calls are permitted: '+url)
  })
  vi.stubGlobal('fetch',fetcher)
  return {calls, setState:(value:string)=>{session={...session,state:value}},writes:()=>calls.filter(call=>call.method!=='GET')}
}

async function mount(options:Parameters<typeof fixture>[0]={}) {
  const f=fixture(options);render(<WhatsAppSettings />)
  await waitFor(()=>expect(f.calls.filter(call=>call.method==='GET')).toHaveLength(2))
  await act(async()=>{})
  return f
}

it('legacy enabled is never automatic consent and the connected surface has one authority control',async()=>{
  const f=await mount()
  expect((screen.getByRole('checkbox',{name:consentLabel}) as HTMLInputElement).checked).toBe(false)
  expect(screen.queryByRole('button',{name:'Guardar configuración'})).toBeNull()
  expect(screen.queryByRole('button',{name:'Vincular WhatsApp'})).toBeNull()
  const advanced=screen.getByText('Avanzado').closest('details')!
  expect(advanced.open).toBe(false)
  expect(screen.getByRole('button',{name:'Comprobar conexión ahora'}).closest('details')).toBe(advanced)
  expect(screen.getByRole('button',{name:'Cerrar navegador de vinculación'}).closest('details')).toBe(advanced)
  expect(screen.getByText(/Los borradores anteriores siguen siendo borradores/)).toBeTruthy()
  expect(f.writes()).toEqual([])
})

it('one deliberate checkbox persists channel consent without confirm-per-message or browser effects',async()=>{
  const f=await mount()
  fireEvent.click(screen.getByRole('checkbox',{name:consentLabel}))
  await waitFor(()=>expect((screen.getByRole('checkbox',{name:consentLabel}) as HTMLInputElement).checked).toBe(true))
  expect(f.writes().map(v=>v.url)).toEqual(['/api/whatsapp/session',endpoint])
  expect(f.writes()[1].body).toEqual({enabled:true,expected_project_id:'fixture-project',expected_binding:'opaque-not-a-root',expected_session_identity:'b'.repeat(64),expected_authorization_revision:'none'})
  expect(screen.queryByRole('button',{name:/Aceptar|Confirmar|Guardar/})).toBeNull()
  expect(f.calls.some(v=>/\/open|\/confirm|\/send/.test(v.url))).toBe(false)
})

it('turning off revokes the exact grant before disabling connection configuration',async()=>{
  const f=await mount({granted:true})
  fireEvent.click(screen.getByRole('checkbox',{name:consentLabel}))
  await waitFor(()=>expect(f.writes()).toHaveLength(2))
  expect(f.writes().map(v=>v.url)).toEqual([endpoint,'/api/whatsapp/session'])
  expect(f.writes()[0].body.enabled).toBe(false)
  expect(f.writes()[0].body.expected_authorization_revision).toBe('a'.repeat(64))
  expect(f.writes()[1].body.enabled).toBe(false)
  await waitFor(()=>expect((screen.getByRole('checkbox',{name:consentLabel}) as HTMLInputElement).checked).toBe(false))
})

it('editing the label autosaves once after debounce without granting legacy connection authority',async()=>{
  const f=await mount()
  fireEvent.click(screen.getByText('Avanzado'))
  fireEvent.change(screen.getByRole('textbox',{name:'Nombre de la sesión'}),{target:{value:'Primera edición'}})
  fireEvent.change(screen.getByRole('textbox',{name:'Nombre de la sesión'}),{target:{value:'Nombre definitivo'}})
  expect(f.writes()).toEqual([])
  await waitFor(()=>expect(f.writes()).toHaveLength(1))
  expect(f.writes()[0]).toEqual({url:'/api/whatsapp/session',method:'PUT',body:{label:'Nombre definitivo',enabled:true}})
  expect(f.calls.some(v=>v.url===endpoint&&v.method==='PUT')).toBe(false)
  expect(await screen.findByText('Guardado automáticamente')).toBeTruthy()
})

it('a disconnected first session offers linking but never opens or configures a browser on render',async()=>{
  const f=await mount({state:'not_configured',configured:false})
  expect(screen.getByRole('button',{name:'Vincular WhatsApp'})).toBeTruthy()
  expect(screen.getByText(/La primera vez necesitas vincular/)).toBeTruthy()
  expect(f.writes()).toEqual([])
})

it('automatic checks update the observed connection and remove an unnecessary QR action',async()=>{
  vi.useFakeTimers()
  const f=fixture({state:'linking'})
  render(<WhatsAppSettings />)
  await act(async()=>{})
  expect(screen.getByRole('button',{name:'Vincular WhatsApp'})).toBeTruthy()
  f.setState('connected')
  await act(async()=>{await vi.advanceTimersByTimeAsync(15000)})
  expect(screen.queryByRole('button',{name:'Vincular WhatsApp'})).toBeNull()
  expect(f.calls.filter(v=>v.method==='GET')).toHaveLength(4)
  expect(f.writes()).toEqual([])
})

it('a stale authorization is visibly rejected without claiming permission or retrying a send',async()=>{
  const f=await mount({rejectGrant:true})
  fireEvent.click(screen.getByRole('checkbox',{name:consentLabel}))
  expect((await screen.findByRole('alert')).textContent).toContain('La autorización cambió')
  expect((screen.getByRole('checkbox',{name:consentLabel}) as HTMLInputElement).checked).toBe(false)
  expect(f.writes().filter(v=>v.url===endpoint)).toHaveLength(1)
  expect(f.calls.some(v=>/\/open|\/confirm|\/send/.test(v.url))).toBe(false)
})

it('missing active-project authority disables the consent control while connection status stays visible',async()=>{
  const f=await mount({authorizationError:true})
  expect((screen.getByRole('checkbox',{name:consentLabel}) as HTMLInputElement).disabled).toBe(true)
  expect((await screen.findByRole('alert')).textContent).toContain('Proyecto no disponible')
  expect(f.writes()).toEqual([])
})
