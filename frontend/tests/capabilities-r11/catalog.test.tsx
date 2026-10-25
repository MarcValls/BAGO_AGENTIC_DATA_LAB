// @vitest-environment jsdom
import React from 'react'
import {afterEach,beforeEach,expect,it,vi} from 'vitest'
import {act,cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import CapabilityManager from '../../src/components/CapabilityManager'
import {resetLocaleForTests,setLocale,t} from '../../src/i18n'
beforeEach(()=>{localStorage.clear();resetLocaleForTests();setLocale('es')})
afterEach(()=>{cleanup();vi.unstubAllGlobals()})
const ids=['workspace.read_text','workspace.scan_duplicates','agent.evaluate','mcp.execute','sandbox.execute','agent.run','document_inventory','document_extract','document_relate','document_plan_rename','document_export','filesystem_inventory','filesystem_plan','delivery_review','delivery_revalidate','delivery_prepare_draft','development_check','development_inspect','development_prepare','development_read','development_review','development_revise']
const blocked=new Set(['mcp.execute','sandbox.execute','agent.run'])
const entry=(id:string,status=blocked.has(id)?'UNAVAILABLE':'AVAILABLE')=>({id,status,effect:'READ',integration:'CONNECTED',name:'ORIGINAL NAME '+id,summary:'ORIGINAL SUMMARY '+id,provider:'original',limits:{},source_fingerprints:{'path.py':null},source_available:false,fingerprint:'a'.repeat(64)})
const response=(body:unknown,status=200)=>({ok:status<400,status,json:async()=>body})
function stub(value:unknown={capabilities:ids.map(id=>entry(id))},status=200){const calls:Array<{url:string;method:string}>=[];vi.stubGlobal('fetch',vi.fn(async(url:string,init?:RequestInit)=>{calls.push({url,method:init?.method??'GET'});return url==='/api/capabilities'?response(value,status):response({proposals:[]})}));return calls}
it('shows loading then an honest empty catalog without creating proposals or invoking tools',async()=>{
 let resolve!:(v:unknown)=>void;const fetcher=vi.fn((url:string)=>url==='/api/capabilities'?new Promise(r=>{resolve=r}):Promise.resolve(response({proposals:[]})));vi.stubGlobal('fetch',fetcher);render(<CapabilityManager/>);expect(screen.getByRole('status')).toBeTruthy();await act(async()=>resolve(response({capabilities:[]})));expect(await screen.findByText(t('core.CapabilityManager.no_capability_records_were_returned_by_the_199420'))).toBeTruthy();expect(screen.queryByText(t('commerce.capability_ui.prepare'))).toBeNull();expect(fetcher.mock.calls.every(([,init]:any)=>!init?.method)).toBe(true)
})
it('shows an error and reload action for failed or unsupported catalog responses',async()=>{
 const calls=stub({detail:{message:'fixture catalog failure'}},503);const view=render(<CapabilityManager/>);expect(await screen.findByRole('alert')).toBeTruthy();fireEvent.click(screen.getByRole('button',{name:'Volver a cargar'}));await act(async()=>{});expect(calls.filter(c=>c.url==='/api/capabilities')).toHaveLength(2);view.unmount();stub({capabilities:[{status:'AVAILABLE'}]});render(<CapabilityManager/>);expect(await screen.findByText('El servicio devolvió un catálogo con formato no compatible.')).toBeTruthy();expect(screen.queryByRole('button',{name:'Preparar con BAGO5'})).toBeNull()
})
it('all 22 known capabilities have localized product names and explanations without borrowing backend English',async()=>{
 const calls=stub();const view=render(<CapabilityManager onPrepareChat={vi.fn()} onNavigate={vi.fn()}/>);await screen.findByRole('heading',{name:'Leer texto acotado del espacio de trabajo'});const cards=Array.from(view.container.querySelectorAll('.capability-card'));expect(cards).toHaveLength(22);expect(cards.every(c=>!c.querySelector('h3')!.textContent!.includes('sin etiqueta'))).toBe(true);expect(cards.every(c=>!c.querySelector(':scope > p')!.textContent!.includes('ORIGINAL SUMMARY'))).toBe(true);expect(screen.getAllByRole('button',{name:'Preparar con BAGO5'})).toHaveLength(19);expect(screen.queryByRole('button',{name:'Ejecutar'})).toBeNull();expect(calls.every(c=>c.method==='GET')).toBe(true)
 act(()=>setLocale('en'));expect(screen.getByRole('heading',{name:'Create a document report'})).toBeTruthy();expect(screen.getByRole('heading',{name:'Independent code review'})).toBeTruthy();expect(screen.getAllByRole('button',{name:'Prepare with BAGO5'})).toHaveLength(19);expect(calls).toHaveLength(2)
})
it('prepares an explicit localized request through the React callback and does not send or authorize it',async()=>{
 const calls=stub();const prepare=vi.fn();const view=render(<CapabilityManager onPrepareChat={prepare}/>);await screen.findByRole('heading',{name:'Leer documentos con fuentes'});const card=Array.from(view.container.querySelectorAll('.capability-card')).find(c=>c.querySelector('code')?.textContent==='document_extract')!;fireEvent.click(within(card as HTMLElement).getByRole('button',{name:'Preparar con BAGO5'}));expect(prepare).toHaveBeenCalledExactlyOnceWith({capabilityId:'document_extract',prompt:expect.stringContaining('Revisemos el agente')});expect(calls.every(c=>c.method==='GET')).toBe(true)
})
it('unavailable and unknown entries never expose a false universal execution route; MCP opens actual configuration',async()=>{
 const calls=stub({capabilities:[entry('mcp.execute'),entry('sandbox.execute'),entry('future.new'),entry('development_check','UNKNOWN')]});const navigate=vi.fn(),prepare=vi.fn();render(<CapabilityManager onNavigate={navigate} onPrepareChat={prepare}/>);await screen.findByRole('heading',{name:'Capacidad sin etiqueta de producto (future.new)'});expect(screen.queryByRole('button',{name:'Preparar con BAGO5'})).toBeNull();fireEvent.click(screen.getByRole('button',{name:'Conexiones externas'}));expect(navigate).toHaveBeenCalledExactlyOnceWith('connections');expect(prepare).not.toHaveBeenCalled();expect(calls.every(c=>c.method==='GET')).toBe(true)
})
