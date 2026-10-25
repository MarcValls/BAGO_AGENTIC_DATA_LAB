// @vitest-environment jsdom
import React from 'react'
import {beforeEach,afterEach,expect,it,vi} from 'vitest'
import {act,cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import AgentChat from '../../src/components/AgentChat'
import {resetLocaleForTests,setLocale,formatDate} from '../../src/i18n'
beforeEach(()=>{localStorage.clear();resetLocaleForTests();setLocale('es');HTMLElement.prototype.scrollIntoView=vi.fn()})
afterEach(()=>{cleanup();vi.unstubAllGlobals()})
const response=(data:unknown,status=200)=>({ok:status<400,status,json:async()=>data})
const summary=(id:string,date?:string)=>({id,owner_kind:'assistant',owner_id:'app-assistant',title:'Historial '+id,status:'active',updated_at:date,revision:2})
const rows=[summary('old','2026-10-20T10:15:00Z'),summary('tie-one','2026-10-24T11:00:00+01:00'),summary('tie-two','2026-10-24T10:00:00Z'),summary('bad','invalid-date'),summary('missing'),summary('date-only','2026-10-24')]
function chat(policy:'explicit'|'latest'|undefined='explicit'){return <AgentChat historySelection={policy} cognitiveMode="baseline" onNavigate={()=>{}} onOpenProviderSettings={()=>{}} onOpenCognitionSettings={()=>{}}/>}
async function fixture({policy='explicit',late=false,fail=false}:{policy?:'explicit'|'latest';late?:boolean;fail?:boolean}={}){
 const calls:Array<{url:string;method:string;body:any}>=[];const created=new Map<string,any>();let delayed:((value:any)=>void)|null=null
 const fetcher=vi.fn(async(url:string,init?:RequestInit)=>{
 const method=init?.method??'GET',body=init?.body?JSON.parse(String(init.body)):null;calls.push({url,method,body})
 if(url==='/api/agents/list')return response({agents:[{id:'fixture-agent',config:{name:'Agente de prueba',type:'tool',tools:[],system_prompt:'fixture'},created_at:'2026-10-24'}]})
 if(url==='/api/providers/selection')return response({provider_id:null,model_id:null})
 if(url.startsWith('/api/conversations?')){
  if(fail)return response({detail:'synthetic list failure'},500)
  if(late)return await new Promise(r=>{delayed=r})
  const query=new URLSearchParams(url.split('?')[1]);return response({conversations:query.get('owner_kind')==='agent'?[{...summary('agent-history','2026-10-24T12:00:00Z'),owner_kind:'agent',owner_id:'fixture-agent'}]:rows})
 }
 if(url==='/api/conversations'&&method==='POST'){
  const c={...summary('created-'+(created.size+1),'2026-10-24T14:00:00Z'),owner_kind:body.owner_kind,owner_id:body.owner_id,revision:1,messages:[]};created.set(c.id,c);return response(c)
 }
 if(url.startsWith('/api/conversations/')&&method==='GET'){
  const id=url.split('/').pop()!;const existing=created.get(id);if(existing)return response(existing)
  const c=id==='agent-history'?{...summary(id,'2026-10-24T12:00:00Z'),owner_kind:'agent',owner_id:'fixture-agent'}:rows.find(r=>r.id===id)
  return response({...c,messages:[{id:'answer-'+id,role:'assistant',content:'Contenido elegido '+id}]})
 }
 if(url==='/api/chat/control'){
  const c=created.get(body.conversation_id);const saved={...c,revision:c.revision+1,messages:[{id:'user-first',role:'user',content:body.message},{id:'reply-first',role:'assistant',content:'Respuesta al primer mensaje'}]};created.set(c.id,saved);return response({operation:'chat',conversation:saved})
 }
 return response({models:[],proposals:[]})
 });vi.stubGlobal('fetch',fetcher);const view=render(chat(policy));await waitFor(()=>expect(calls.some(c=>c.url.startsWith('/api/conversations?'))).toBe(true));if(!late)await act(async()=>{})
 return {view,calls,created,resolveList:async()=>{await act(async()=>{delayed!(response({conversations:rows}))})}}
}
const writes=(calls:Array<{method:string}>)=>calls.filter(c=>c.method!=='GET')
const details=(calls:Array<{url:string;method:string}>)=>calls.filter(c=>c.method==='GET'&&c.url.startsWith('/api/conversations/'))
it('explicit product policy mounts and remounts blank, lists history without detail, grants or empty records',async()=>{
 const f=await fixture();expect(f.view.container.querySelectorAll('article.control-message')).toHaveLength(0);expect(details(f.calls)).toEqual([]);expect(writes(f.calls)).toEqual([]);expect(f.created.size).toBe(0);f.view.unmount();render(chat());await waitFor(()=>expect(f.calls.filter(c=>c.url.startsWith('/api/conversations?')).length).toBe(2));expect(details(f.calls)).toEqual([]);expect(writes(f.calls)).toEqual([]);expect(screen.getByRole('textbox',{name:'Mensaje al asistente o agente seleccionado'})).toHaveProperty('value','')
})
it('late history list cannot pick a chat or overwrite the blank composer draft',async()=>{
 const f=await fixture({late:true});const composer=screen.getByRole('textbox',{name:'Mensaje al asistente o agente seleccionado'}) as HTMLTextAreaElement;fireEvent.change(composer,{target:{value:'Borrador pendiente'}});await f.resolveList();expect(composer.value).toBe('Borrador pendiente');expect(details(f.calls)).toEqual([]);expect(f.view.container.querySelectorAll('article.control-message')).toHaveLength(0);expect(writes(f.calls)).toEqual([])
})
it('manual history selection alone reads the exact selected record, preserving draft and producing no write',async()=>{
 const f=await fixture();const composer=screen.getByRole('textbox',{name:'Mensaje al asistente o agente seleccionado'}) as HTMLTextAreaElement;fireEvent.change(composer,{target:{value:'Borrador no enviado'}});fireEvent.click(screen.getByRole('button',{name:/Historial tie-two/}));await screen.findByText('Contenido elegido tie-two');expect(details(f.calls).map(c=>c.url)).toEqual(['/api/conversations/tie-two']);expect(composer.value).toBe('Borrador no enviado');expect(writes(f.calls)).toEqual([])
})
it('first explicit send lazily creates one record and uses the ordinary chat revision with no grants',async()=>{
 const f=await fixture();const composer=screen.getByRole('textbox',{name:'Mensaje al asistente o agente seleccionado'});fireEvent.change(composer,{target:{value:'Una pregunta sintética nueva'}});fireEvent.click(screen.getByRole('button',{name:'Enviar',exact:true}));await screen.findByText('Respuesta al primer mensaje');const actual=writes(f.calls);expect(actual.map(c=>c.url)).toEqual(['/api/conversations','/api/chat/control']);expect(actual[0].body).toEqual({owner_kind:'assistant',owner_id:'app-assistant'});expect(actual[1].body).toMatchObject({operation:'chat',conversation_id:'created-1',revision:1,message:'Una pregunta sintética nueva'});expect(actual[1].body.workspace_read_authorization_id).toBeUndefined();expect(actual[1].body.web_read_authorization_id).toBeUndefined();expect(f.created.size).toBe(1)
})
it('New stays an explicit one-record action instead of a mount effect',async()=>{
 const f=await fixture();fireEvent.click(screen.getByRole('button',{name:'Nueva',exact:true}));await waitFor(()=>expect(f.created.size).toBe(1));expect(writes(f.calls).map(c=>c.url)).toEqual(['/api/conversations']);expect(f.calls.some(c=>c.url==='/api/chat/control')).toBe(false)
})
it('blank BAGO5 lists only assistant history, keeps agent histories inaccessible and clears turn consent on manual selection without writes',async()=>{
 const f=await fixture();const composer=screen.getByRole('textbox',{name:'Mensaje al asistente o agente seleccionado'}) as HTMLTextAreaElement;fireEvent.change(composer,{target:{value:'Borrador del orquestador'}});fireEvent.click(screen.getByLabelText('Permitir lectura web pública'))
 const lists=f.calls.filter(c=>c.url.startsWith('/api/conversations?'));expect(lists.every(c=>{const q=new URLSearchParams(c.url.split('?')[1]);return q.get('owner_kind')==='assistant'&&q.get('owner_id')==='app-assistant'})).toBe(true);expect(screen.queryByRole('button',{name:/Historial agent-history/})).toBeNull();expect(screen.queryByRole('button',{name:/Agente de prueba/})).toBeNull();expect(details(f.calls)).toEqual([]);expect(f.view.container.querySelectorAll('article.control-message')).toHaveLength(0)
 fireEvent.click(screen.getByRole('button',{name:/Historial tie-two/}));await screen.findByText('Contenido elegido tie-two');expect(details(f.calls).map(c=>c.url)).toEqual(['/api/conversations/tie-two']);await waitFor(()=>expect((screen.getByLabelText('Permitir lectura web pública') as HTMLInputElement).checked).toBe(false));expect(composer.value).toBe('Borrador del orquestador');expect(writes(f.calls)).toEqual([]);expect(f.created.size).toBe(0)
})
it('orders valid activity instants newest-first with stable ties and exposes true UTC date/time only',async()=>{
 const f=await fixture();const buttons=Array.from(f.view.container.querySelectorAll('.conversation-library-item'));expect(buttons.map(b=>b.querySelector('strong')?.textContent)).toEqual(['Historial tie-one','Historial tie-two','Historial old','Historial bad','Historial missing','Historial date-only']);const times=Array.from(f.view.container.querySelectorAll('time'));expect(times.map(t=>t.getAttribute('dateTime'))).toEqual([rows[1].updated_at,rows[2].updated_at,rows[0].updated_at]);expect(times[0].textContent).toBe('Última actividad · '+formatDate(rows[1].updated_at!)+' UTC');expect(f.view.container.querySelectorAll('.conversation-library-item span')).toHaveLength(6);expect(screen.getAllByText('Última actividad no disponible')).toHaveLength(3)
})
it('list failure shows error while blank composer remains usable and no record or inference is created',async()=>{
 const f=await fixture({fail:true});await waitFor(()=>expect(f.view.container.querySelector('.conversation-library .inline-error')?.textContent).toBeTruthy());const composer=screen.getByRole('textbox',{name:'Mensaje al asistente o agente seleccionado'}) as HTMLTextAreaElement;fireEvent.change(composer,{target:{value:'Borrador recuperable'}});expect(composer.disabled).toBe(false);expect(composer.value).toBe('Borrador recuperable');expect(details(f.calls)).toEqual([]);expect(writes(f.calls)).toEqual([])
})
it('latest embedding compatibility remains available explicitly without changing its old detail selection',async()=>{
 const f=await fixture({policy:'latest'});await screen.findByText('Contenido elegido old');expect(details(f.calls).map(c=>c.url)).toEqual(['/api/conversations/old']);expect(writes(f.calls)).toEqual([])
})
