// @vitest-environment jsdom
import React from 'react'
import {afterEach,beforeEach,expect,it,vi} from 'vitest'
import {act,cleanup,fireEvent,render,screen,waitFor,within} from '@testing-library/react'
import AgentChat from '../../src/components/AgentChat'
import {resetLocaleForTests,setLocale} from '../../src/i18n'
beforeEach(()=>{localStorage.clear();resetLocaleForTests();setLocale('es');HTMLElement.prototype.scrollIntoView=vi.fn()})
afterEach(()=>{cleanup();vi.unstubAllGlobals()})
const rows=[{id:'older',title:'Conversación antigua',updated_at:'2026-10-20T10:15:00Z'},{id:'newer',title:'Conversación reciente',updated_at:'2026-10-24T12:30:00+02:00'},{id:'unknown',title:'Sin fecha',updated_at:'bad-date'}].map(c=>({...c,owner_kind:'assistant',owner_id:'app-assistant',status:'active',revision:2}))
async function mount({fail=false,linked=false}:{fail?:boolean;linked?:boolean}={}){
 const calls:Array<{url:string;method:string;body:any}>=[];const navigate=vi.fn()
 const fetcher=vi.fn(async(url:string,init?:RequestInit)=>{const method=init?.method??'GET';calls.push({url,method,body:init?.body?JSON.parse(String(init.body)):null});const ok=(data:unknown,status=200)=>({ok:status<400,status,json:async()=>data})
  if(url==='/api/agents/list')return ok({agents:[{id:'plain-agent',config:{name:'Agente sin desarrollo',type:'tool',tools:[],system_prompt:'fixture'},created_at:'2026-10-24'}]})
  if(url==='/api/providers/selection')return ok({provider_id:null,model_id:null})
  if(url.startsWith('/api/conversations?')){if(fail)return ok({detail:'synthetic history unavailable'},500);return ok({conversations:new URLSearchParams(url.split('?')[1]).get('owner_kind')==='agent'?[]:rows})}
  if(url.startsWith('/api/conversations/')){const item=rows.find(c=>url.endsWith('/'+c.id));return ok({...item,messages:[{id:'answer-'+item?.id,role:'assistant',content:'Respuesta conservada '+item?.id,...(linked&&item?.id==='older'?{references:{agent_delegation:{proposal_id:'delegation-linked',state:'PASSED',parent_conversation_id:'older',parent_revision:2,agent_id:'linked-agent',agent_name:'Agente participante vinculado',agent_config_sha256:'a'.repeat(64),provider_id:'fixture',model_id:'fixture-model',assigned_tools:[],task:'fixture bounded task',task_sha256:'b'.repeat(64),proposal_sha256:'c'.repeat(64),expires_at:2000000000,child_conversation_id:'child-linked',child_revision:1}}}:{})}]})}
  return ok({models:[],proposals:[]})
 });vi.stubGlobal('fetch',fetcher)
 const props={historySelection:'explicit' as const,cognitiveMode:'baseline' as const,onNavigate:navigate,onOpenProviderSettings:vi.fn(),onOpenCognitionSettings:vi.fn()}
 const view=render(<AgentChat {...props}/>);await waitFor(()=>expect(calls.some(c=>c.url.startsWith('/api/conversations?'))).toBe(true));await act(async()=>{});return {view,calls,navigate,props}
}
const mutations=(calls:Array<{method:string}>)=>calls.filter(c=>c.method!=='GET')
it('general blank startup exposes the original project panel with honest workspace and conversation history, without development calls or writes',async()=>{
 const f=await mount();const panel=screen.getByRole('region',{name:'Contexto del proyecto'});expect(panel.hidden).toBe(false)
 expect(within(panel).getByText('Historial de conversaciones')).toBeTruthy();expect(within(panel).queryByText('Historial de cambios')).toBeNull();expect(within(panel).getByText('Solicitud de lectura de archivos del proyecto: no marcada.')).toBeTruthy();expect(within(panel).getByText('No hay rutas indicadas para este turno.')).toBeTruthy()
 expect(panel.querySelectorAll('.project-sidebar-sections > details[open]')).toHaveLength(2)
 expect(f.view.container.querySelectorAll('article.control-message')).toHaveLength(0);expect(f.calls.filter(c=>c.url.startsWith('/api/development/'))).toEqual([]);expect(f.calls.filter(c=>c.url.startsWith('/api/conversations/'))).toEqual([]);expect(mutations(f.calls)).toEqual([])
 expect(within(panel).queryByRole('button',{name:'Aplicar cambio'})).toBeNull();expect(within(panel).queryByRole('button',{name:'Revertir cambio'})).toBeNull();expect(within(panel).queryByRole('button',{name:'Elegir carpeta'})).toBeNull()
})
it('right history uses actual dated conversations in activity order and manual exact-id selection preserves the draft',async()=>{
 const f=await mount();const panel=screen.getByRole('region',{name:'Contexto del proyecto'});const library=within(panel).getByRole('region',{name:'Biblioteca de conversaciones'})
 expect(Array.from(library.querySelectorAll('.conversation-library-item strong')).map(e=>e.textContent)).toEqual(['Conversación reciente','Conversación antigua','Sin fecha'])
 expect(Array.from(library.querySelectorAll('time')).map(e=>e.getAttribute('dateTime'))).toEqual([rows[1].updated_at,rows[0].updated_at]);expect(within(library).getByText('Última actividad no disponible')).toBeTruthy()
 const composer=screen.getByRole('textbox',{name:'Mensaje al asistente o agente seleccionado'}) as HTMLTextAreaElement;fireEvent.change(composer,{target:{value:'Borrador del usuario'}})
 fireEvent.click(within(library).getByRole('button',{name:/Conversación antigua/}));await screen.findByText('Respuesta conservada older');expect(composer.value).toBe('Borrador del usuario');expect(f.calls.filter(c=>c.url.startsWith('/api/conversations/')).map(c=>c.url)).toEqual(['/api/conversations/older']);expect(mutations(f.calls)).toEqual([])
})
it('folding sections and whole panel preserves draft, returns keyboard focus and produces no calls',async()=>{
 const f=await mount();const composer=screen.getByRole('textbox',{name:'Mensaje al asistente o agente seleccionado'}) as HTMLTextAreaElement;fireEvent.change(composer,{target:{value:'No borrar'}});const count=f.calls.length
 const panel=screen.getByRole('region',{name:'Contexto del proyecto'});const sections=Array.from(panel.querySelectorAll('.project-sidebar-sections > details'));sections.forEach(section=>{section.removeAttribute('open');fireEvent(section,new Event('toggle'))});expect(sections.every(s=>!s.hasAttribute('open'))).toBe(true);sections.forEach(s=>s.setAttribute('open',''))
 fireEvent.click(screen.getByRole('button',{name:'Cerrar cambios del proyecto'}));const tab=screen.getByRole('button',{name:/Proyecto/});expect(tab.getAttribute('aria-expanded')).toBe('false');expect(document.activeElement).toBe(tab);expect(panel.hidden).toBe(true);fireEvent.click(tab);expect(document.activeElement).toBe(screen.getByRole('button',{name:'Cerrar cambios del proyecto'}));expect(composer.value).toBe('No borrar');expect(f.calls).toHaveLength(count);expect(mutations(f.calls)).toEqual([])
})
it('workspace status reflects only the existing next-turn request and navigation remains an explicit local action',async()=>{
 const f=await mount();fireEvent.click(screen.getByLabelText('Permitir lectura de archivos del proyecto'));const paths=screen.getByLabelText('Rutas relativas al proyecto');fireEvent.change(paths,{target:{value:'docs/fixture.md'}})
 const panel=screen.getByRole('region',{name:'Contexto del proyecto'});expect(within(panel).getByText('Solicitud de lectura de archivos del proyecto: marcada.')).toBeTruthy();expect(within(panel).getByText('docs/fixture.md')).toBeTruthy();expect(within(panel).getByText('La autorización se comprueba al enviar el mensaje.')).toBeTruthy();fireEvent.click(within(panel).getByRole('button',{name:'Abrir espacio de trabajo'}));expect(f.navigate).toHaveBeenCalledWith('workspace');expect(mutations(f.calls)).toEqual([]);expect(f.calls.some(c=>c.url.includes('/browse')||c.url.startsWith('/api/development/'))).toBe(false)
})
it('general panel lists only agents linked to this conversation, not the saved-agent inventory, without grants or development requests',async()=>{
 const f=await mount({linked:true});const composer=screen.getByRole('textbox',{name:'Mensaje al asistente o agente seleccionado'}) as HTMLTextAreaElement;fireEvent.change(composer,{target:{value:'Borrador exacto'}});expect(screen.queryByText('Agente sin desarrollo')).toBeNull();expect(screen.queryByText('Agente participante vinculado')).toBeNull();expect(f.view.container.querySelectorAll('article.control-message')).toHaveLength(0)
 fireEvent.click(screen.getByRole('button',{name:/Conversación antigua/}));await screen.findByText('Respuesta conservada older');const summary=screen.getByText(/Conversaciones y agentes/).closest('summary')!;fireEvent.click(summary);const participants=f.view.container.querySelector('.conversation-agent-activity')!;expect(within(participants as HTMLElement).getByText('Agente participante vinculado')).toBeTruthy();expect(within(participants as HTMLElement).queryByText('Agente sin desarrollo')).toBeNull();expect(participants.querySelectorAll('.conversation-participant')).toHaveLength(1);expect(composer.value).toBe('Borrador exacto');expect(f.calls.some(c=>c.url.startsWith('/api/development/'))).toBe(false);expect(mutations(f.calls)).toEqual([])
})
it('history failure keeps general panel and draft usable without fetching development or creating an empty record',async()=>{
 const f=await mount({fail:true});const panel=screen.getByRole('region',{name:'Contexto del proyecto'});expect(within(panel).getByRole('alert')).toBeTruthy();const composer=screen.getByRole('textbox',{name:'Mensaje al asistente o agente seleccionado'}) as HTMLTextAreaElement;fireEvent.change(composer,{target:{value:'Continuar después'}});expect(composer.value).toBe('Continuar después');expect(mutations(f.calls)).toEqual([]);expect(f.calls.some(c=>c.url.startsWith('/api/development/'))).toBe(false)
})
