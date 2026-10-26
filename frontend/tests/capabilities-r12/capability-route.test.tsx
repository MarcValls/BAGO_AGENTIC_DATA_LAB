// @vitest-environment jsdom
import React from 'react'
import {afterEach,beforeEach,expect,it,vi} from 'vitest'
import {act,cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import AgentChat,{type PreparedChatPrompt} from '../../src/components/AgentChat'
import {resetLocaleForTests,setLocale,t} from '../../src/i18n'
beforeEach(()=>{localStorage.clear();resetLocaleForTests();setLocale('es');HTMLElement.prototype.scrollIntoView=vi.fn()})
afterEach(()=>{cleanup();vi.unstubAllGlobals()})
const response=(body:unknown,status=200)=>({ok:status<400,status,json:async()=>body})
const prompt=()=>t('commerce.capability_ui.workspace.scan_duplicates.prompt')
const request=():PreparedChatPrompt=>({id:'catalog-selection',text:prompt(),capabilityId:'workspace.scan_duplicates'})
async function fixture({initial='',selection=request(),delayed=false,grantFailure=false}:{initial?:string;selection?:PreparedChatPrompt|null;delayed?:boolean;grantFailure?:boolean}={}){
 const calls:Array<{url:string;method:string;body:any}>=[];let current:any=null;let release!:(v:unknown)=>void
 function reply(body:any){current={...current,revision:current.revision+2,messages:[{id:'user-'+current.revision,role:'user',content:body.message},{id:'answer-'+current.revision,role:'assistant',content:'Revisa la carpeta antes de autorizar el escaneo.',references:body.capability_id?{control_capability:body.capability_id}:{}}]};return response({operation:body.capability_id?'workspace_scan':'chat',conversation:current})}
 vi.stubGlobal('fetch',vi.fn(async(url:string,init?:RequestInit)=>{const method=init?.method??'GET',body=init?.body?JSON.parse(String(init.body)):null;calls.push({url,method,body})
 if(url==='/api/agents/list')return response({agents:[]})
 if(url==='/api/providers/selection')return response({provider_id:null,model_id:null})
 if(url.startsWith('/api/conversations?'))return response({conversations:[]})
 if(url==='/api/conversations'&&method==='POST'){current={id:'conv-route',owner_kind:'assistant',owner_id:'app-assistant',title:'Fixture route',revision:1,status:'active',messages:[]};return response(current)}
 if(url==='/api/chat/control'){if(delayed)return await new Promise(r=>{release=r});return reply(body)}
 if(url==='/api/workspace-scan/authorizations')return grantFailure?response({detail:{message:'Synthetic grant denied'}},403):response({authorization_id:'grant-exact-directory'})
 if(url==='/api/workspace-scan/run')return response({result:{ok:true,directory:body.directory,files_scanned:2,files_skipped:0,lines_scanned:20,bytes_scanned:120,finding_count:0,truncated:false,manifest_sha256:'a'.repeat(64),supported_extensions:['.py'],method:{exact:'fixture',similar:'fixture'},limitations:[],findings:[]},receipt:{path:body.directory,files_scanned:2,finding_count:0,manifest_sha256:'a'.repeat(64),duration_ms:1,truncated:false,files:[]},trace:{trace_id:'trace-fixture',trace_state:'saved'},conversation_id:'conv-route'})
 return response({models:[],proposals:[]})}))
 const handled=vi.fn();const props={historySelection:'explicit' as const,cognitiveMode:'baseline' as const,onNavigate:vi.fn(),onOpenProviderSettings:vi.fn(),onOpenCognitionSettings:vi.fn(),onPreparedPromptHandled:handled}
 const view=render(<AgentChat {...props}/>);const input=screen.getByRole('textbox',{name:'Mensaje al asistente o agente seleccionado'}) as HTMLTextAreaElement
 if(initial)fireEvent.change(input,{target:{value:initial}})
 view.rerender(<AgentChat {...props} preparedPrompt={selection}/>);await act(async()=>{})
 return {view,input,calls,props,handled,releaseReply:async()=>{const body=calls.find(c=>c.url==='/api/chat/control')!.body;await act(async()=>release(reply(body)))}}
}
const writes=(calls:Array<{method:string}>)=>calls.filter(c=>c.method!=='GET')
const chatBody=(calls:Array<{url:string;body:any}>)=>calls.find(c=>c.url==='/api/chat/control')!.body
async function send(){const button=screen.getByRole('button',{name:'Enviar',exact:true}) as HTMLButtonElement;await waitFor(()=>expect(button.disabled).toBe(false));fireEvent.click(button)}
it('selection only fills the exact draft; explicit send carries its id and only the backend reply displays the existing scan form',async()=>{
 const f=await fixture({delayed:true});expect(f.input.value).toBe(prompt());expect(writes(f.calls)).toEqual([]);expect(screen.queryByLabelText(t('core.DirectoryScanRun.project_relative_directory_d5bd1c'))).toBeNull()
 await send();await waitFor(()=>expect(f.calls.some(c=>c.url==='/api/chat/control')).toBe(true));expect(chatBody(f.calls)).toMatchObject({operation:'chat',message:prompt(),capability_id:'workspace.scan_duplicates',conversation_id:'conv-route',revision:1});expect(f.calls.some(c=>c.url.startsWith('/api/workspace-scan/'))).toBe(false);expect(screen.queryByLabelText(t('core.DirectoryScanRun.project_relative_directory_d5bd1c'))).toBeNull()
 await f.releaseReply();const directory=await screen.findByLabelText(t('core.DirectoryScanRun.project_relative_directory_d5bd1c'));expect(directory).toHaveProperty('value','.');const run=screen.getByRole('button',{name:t('core.DirectoryScanRun.scan_duplicates_bb7da0')}) as HTMLButtonElement;expect(run.disabled).toBe(true);expect(f.calls.some(c=>c.url.startsWith('/api/workspace-scan/'))).toBe(false)
})
it.each(['edit','edit-then-restore'] as const)('editing permanently drops direct route identity: %s',async(mode)=>{
 const f=await fixture();fireEvent.change(f.input,{target:{value:prompt()+' Revisión humana'}});if(mode==='edit-then-restore')fireEvent.change(f.input,{target:{value:prompt()}});await send();await waitFor(()=>expect(f.calls.some(c=>c.url==='/api/chat/control')).toBe(true));expect(chatBody(f.calls)).not.toHaveProperty('capability_id');expect(f.calls.some(c=>c.url.startsWith('/api/workspace-scan/'))).toBe(false);expect(screen.queryByLabelText(t('core.DirectoryScanRun.project_relative_directory_d5bd1c'))).toBeNull()
})
it.each(['Borrador anterior','  \n '])('queued selection preserves existing draft and combining it never carries the id: %j',async(initial)=>{
 const f=await fixture({initial});expect(f.input.value).toBe(initial);expect(writes(f.calls)).toEqual([]);expect(await screen.findByRole('region',{name:'Solicitud preparada para BAGO5'})).toBeTruthy();fireEvent.click(screen.getByRole('button',{name:'Añadir al borrador de BAGO5'}));expect(f.input.value).toBe(initial+'\n\n'+prompt());expect(writes(f.calls)).toEqual([]);await send();await waitFor(()=>expect(f.calls.some(c=>c.url==='/api/chat/control')).toBe(true));expect(chatBody(f.calls)).not.toHaveProperty('capability_id');expect(f.calls.some(c=>c.url.startsWith('/api/workspace-scan/'))).toBe(false)
})
it('typing the catalog wording manually never invents a route id',async()=>{
 const f=await fixture({selection:null});fireEvent.change(f.input,{target:{value:prompt()}});await send();await waitFor(()=>expect(f.calls.some(c=>c.url==='/api/chat/control')).toBe(true));expect(chatBody(f.calls)).not.toHaveProperty('capability_id')
})
it('other prepared capabilities retain their existing chat behavior without this route id',async()=>{
 const f=await fixture({selection:{id:'other',text:'Quiero leer documentos con fuentes',capabilityId:'document_extract'} as any});expect(writes(f.calls)).toEqual([]);await send();await waitFor(()=>expect(f.calls.some(c=>c.url==='/api/chat/control')).toBe(true));expect(chatBody(f.calls)).not.toHaveProperty('capability_id');expect(chatBody(f.calls)).toHaveProperty('message','Quiero leer documentos con fuentes')
})
it('the existing form grants only a human-confirmed exact directory and changing it removes consent',async()=>{
 const f=await fixture();await send();const directory=await screen.findByLabelText(t('core.DirectoryScanRun.project_relative_directory_d5bd1c'));const consent=screen.getByLabelText(t('core.DirectoryScanRun.authorize_one_read_only_scan_of_this_68c104')) as HTMLInputElement;const run=screen.getByRole('button',{name:t('core.DirectoryScanRun.scan_duplicates_bb7da0')}) as HTMLButtonElement
 fireEvent.click(consent);expect(run.disabled).toBe(false);fireEvent.change(directory,{target:{value:'fixtures/code'}});expect(consent.checked).toBe(false);expect(run.disabled).toBe(true);expect(f.calls.some(c=>c.url.startsWith('/api/workspace-scan/'))).toBe(false);fireEvent.click(consent);fireEvent.click(run);await waitFor(()=>expect(f.calls.some(c=>c.url==='/api/workspace-scan/run')).toBe(true));expect(f.calls.find(c=>c.url==='/api/workspace-scan/authorizations')!.body).toEqual({owner_kind:'assistant',owner_id:'app-assistant',conversation_id:'conv-route',revision:3,directories:['fixtures/code']});expect(f.calls.find(c=>c.url==='/api/workspace-scan/run')!.body).toEqual({conversation_id:'conv-route',revision:3,authorization_id:'grant-exact-directory',directory:'fixtures/code'});expect(consent.checked).toBe(false)
})
it('authorization refusal stops the existing form before its execution API',async()=>{
 const f=await fixture({grantFailure:true});await send();await screen.findByLabelText(t('core.DirectoryScanRun.project_relative_directory_d5bd1c'));fireEvent.click(screen.getByLabelText(t('core.DirectoryScanRun.authorize_one_read_only_scan_of_this_68c104')));fireEvent.click(screen.getByRole('button',{name:t('core.DirectoryScanRun.scan_duplicates_bb7da0')}));await screen.findByRole('alert');expect(f.calls.filter(c=>c.url==='/api/workspace-scan/authorizations')).toHaveLength(1);expect(f.calls.some(c=>c.url==='/api/workspace-scan/run')).toBe(false)
})
