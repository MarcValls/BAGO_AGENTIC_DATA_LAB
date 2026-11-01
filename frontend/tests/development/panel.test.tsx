// @vitest-environment jsdom
import React from 'react'
import {afterEach, expect, it, vi} from 'vitest'
import {cleanup, fireEvent, render, screen, waitFor} from '@testing-library/react'
import DevelopmentPanel, {type DevelopmentChange} from '../../src/components/DevelopmentPanel'
afterEach(() => {cleanup(); vi.unstubAllGlobals()})
const response = (data: unknown, ok = true) => ({ok, json: async () => data})
const change = (extra: Partial<DevelopmentChange> = {}): DevelopmentChange => ({change_id: 'change_1', patch_sha256: 'a'.repeat(64), status: 'PREPARED', author: {owner_id:'engineer',conversation_id:'conv1'}, diff:'--- old\n+++ new\n+fixture', checks:[{check_id:'unit',status:'PASS',returncode:0}], reviews:[{reviewer_id:'reviewer',approved:true,reason:'Checks inspected'}], apply_eligible:true, rollback_eligible:false, ...extra})
function serve(c = change()) {
  const fetcher = vi.fn(async (_path: string, init?: RequestInit) => response(init ? {...c,status:'APPLIED',apply_eligible:false,rollback_eligible:true} : _path.endsWith('/changes') ? {changes:[c]} : c))
  vi.stubGlobal('fetch', fetcher); return fetcher
}
async function open(c = change()) {
  const fetcher=serve(c);render(<DevelopmentPanel ownerId="engineer"/>);fireEvent.click(await screen.findByText('change_1 · '+c.status));await screen.findByText(/\+fixture/);return fetcher
}
it('shows loading and empty states',async()=>{
  let resolve!: (value: unknown) => void
  vi.stubGlobal('fetch',vi.fn(()=>new Promise(r=>{resolve=r})))
  render(<DevelopmentPanel ownerId="engineer"/>);expect(screen.getByRole('status').textContent).toContain('Cargando')
  resolve(response({changes:[]}));expect(await screen.findByText(/Todavía no hay cambios/)).toBeTruthy()
})
it('shows service failure without mutation controls',async()=>{
  vi.stubGlobal('fetch',vi.fn(async()=>response({detail:{message:'Servicio no disponible'}},false)))
  render(<DevelopmentPanel ownerId="engineer"/>);expect(await screen.findByRole('alert')).toHaveProperty('textContent','Servicio no disponible');expect(screen.queryByText('Aceptar plan y ejecutar')).toBeNull()
})
it('rejects unsupported candidates',async()=>{
  vi.stubGlobal('fetch',vi.fn(async()=>response({changes:[{change_id:'unknown'}]})))
  render(<DevelopmentPanel ownerId="engineer"/>);expect((await screen.findByRole('alert')).textContent).toContain('no compatible')
})
it('requires human confirmation, sends exact hash once, and shows returned state',async()=>{
  const f=await open();const button=screen.getByText('Aceptar plan y ejecutar') as HTMLButtonElement
  expect(button.disabled).toBe(false);expect(f.mock.calls.filter(c=>c[1])).toHaveLength(0)
  fireEvent.click(button);fireEvent.click(button)
  await screen.findByText('Resultado recibido: APPLIED')
  const writes=f.mock.calls.filter(c=>c[1]);expect(writes).toHaveLength(1)
  expect(writes[0][0]).toBe('/api/development/changes/change_1/apply')
  expect(JSON.parse(String(writes[0][1]?.body))).toEqual({expected_sha256:'a'.repeat(64),confirmed:true})
  expect((screen.getByText('Revertir cambio') as HTMLButtonElement).disabled).toBe(false);expect(writes).toHaveLength(1)
})
it.each([{checks:[]},{reviews:[]},{checks:[{check_id:'unit',status:'FAIL'}]},{reviews:[{reviewer_id:'r',approved:false,reason:'failure'}]},{apply_eligible:undefined}])('blocks incomplete or rejected candidate %j',async extra=>{
  await open(change(extra));expect((screen.getByText('Aceptar plan y ejecutar') as HTMLButtonElement).disabled).toBe(true)
})
it('only allows rollback for an applied eligible candidate',async()=>{
  const f=await open(change({status:'APPLIED',apply_eligible:false,rollback_eligible:true}))
  fireEvent.click(screen.getByText('Revertir cambio'))
  await waitFor(()=>expect(f.mock.calls.some(c=>c[0].endsWith('/rollback'))).toBe(true))
})
it('invalidates review after an apply failure',async()=>{
  const c=change();vi.stubGlobal('fetch',vi.fn(async(path:string,init?:RequestInit)=>response(init?{detail:'El candidato cambió'}:path.endsWith('/changes')?{changes:[c]}:c,!init)))
  render(<DevelopmentPanel ownerId="engineer"/>);fireEvent.click(await screen.findByText('change_1 · PREPARED'));await screen.findByText(/\+fixture/)
  fireEvent.click(screen.getByText('Aceptar plan y ejecutar'))
  expect((await screen.findByRole('alert')).textContent).toContain('El candidato cambió');expect(screen.queryByText('Aceptar plan y ejecutar')).toBeNull()
})

