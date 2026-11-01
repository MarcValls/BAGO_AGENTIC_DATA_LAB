// @vitest-environment jsdom
import React from 'react'
import {resetLocaleForTests,setLocale,t} from '../../src/i18n'
beforeEach(()=>{localStorage.clear();resetLocaleForTests();setLocale('es')})
import {beforeEach,afterEach,expect,it,vi} from 'vitest'
import {act,cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import AgentChat from '../../src/components/AgentChat'
import {summary,review,context,response} from './fixtures'
import {openDelegatedChild,withPersistedDelegation} from '../helpers/delegated-agent-chat'
afterEach(()=>{cleanup();vi.unstubAllGlobals()})
async function setup(options:{stored?:any;role?:string;failed?:boolean}={}){
 HTMLElement.prototype.scrollIntoView=()=>{}
 const agent={id:context.owner_id,config:{name:'Agente fixture',type:'tool',description:'Fixture',provider_id:'ollama-cloud',model_id:'model-fixture'}}
 const make=(id:string,owner_kind:string,owner_id:string)=>({id,owner_kind,owner_id,title:id,status:'active',revision:7,updated_at:'2026-10-23',messages:[] as any[]})
 const assistantBase=make('conv-assistant','assistant','app-assistant');let agentConv=make(context.conversation_id,'agent',context.owner_id)
 const assistant=withPersistedDelegation(assistantBase,agent,agentConv.id)
 if(options.stored!==undefined)agentConv.messages=[{id:'saved',role:options.role??'assistant',content:options.failed?'':'### Propuesta guardada',...(options.failed?{status:'failed'}:{}),references:{workspace_write_proposal:options.stored,trace:{trace_id:'trace-proposal',trace_state:'local_only'}}}]
 const calls:Array<{path:string;body:any}>=[]
 vi.stubGlobal('fetch',vi.fn(async(path:string,init?:RequestInit)=>{
  const body=init?.body?JSON.parse(String(init.body)):null
  if(init?.method&&init.method!=='GET'&&path!=='/api/project-permissions/directories')calls.push({path,body})
  if(path.startsWith('/api/conversations?'))return response({conversations:[path.includes('owner_kind=agent')?agentConv:assistant]})
  if(path==='/api/conversations/'+assistant.id)return response(assistant)
  if(path==='/api/conversations/'+agentConv.id)return response(agentConv)
  if(path==='/api/agents/list')return response({agents:[agent]})
  if(path==='/api/project-folders/v1/active')return response({project_id:'project-1',title:'Proyecto de prueba',scope:'project',root:'D:/work/project'})
  if(path==='/api/project-permissions')return response({project_id:'project-1',root:'D:/work/project',binding:{workspace_root:'D:/work/project',revision:4},revision:3,state:'active',read_directories:['src'],write_directories:['docs']})
  if(path==='/api/project-permissions/directories')return response({project_id:'project-1',root:'D:/work/project',binding:{workspace_root:'D:/work/project',revision:4},revision:3,directory:'.',directories:[{name:'src',path:'src'},{name:'docs',path:'docs'}],truncated:false})
  if(path==='/api/web-read/authorizations')return response({authorization_id:'web-grant',allowed_origins:['https://example.org']})
  if(path.endsWith('/actions'))return response(review)
  if(path==='/api/agents/'+agent.id+'/chat'){
   agentConv={...agentConv,revision:agentConv.revision+2,messages:[...agentConv.messages,{id:'answer-'+agentConv.revision,role:'assistant',content:'### Propuesta\n\n| Estado |\n| --- |\n| PROPOSED |',references:{workspace_write_proposal:summary,trace:{trace_id:'trace-proposal',trace_state:'local_only'}}}]}
   return response({source:'ollama',assistant_message:'Propuesta',workspace_write_proposal:summary,conversation:agentConv})
  }
  return response({models:[],proposals:[]})
 }))
 const inspect=vi.fn();render(<AgentChat cognitiveMode="baseline" onNavigate={()=>{}} onOpenProviderSettings={()=>{}} onOpenCognitionSettings={()=>{}} onInspectExecution={inspect}/>)
 await screen.findByRole('region',{name:assistant.id});await act(async()=>{})
 expect(screen.queryByLabelText('Proponer archivos')).toBeNull()
 await openDelegatedChild('Agente fixture');await act(async()=>{})
 return {calls,inspect}
}
function send(message='Prepara un informe'){fireEvent.change(screen.getByPlaceholderText('Escribe a Agente fixture.'),{target:{value:message}});fireEvent.click(screen.getByRole('button',{name:'Enviar'}))}
it('uses project WRITE policy without per-turn opt-in, preserves Markdown and never autoapplies a proposal',async()=>{
 const {calls,inspect}=await setup()
 expect(screen.queryByLabelText('Proponer archivos')).toBeNull()
 fireEvent.click(screen.getByLabelText('Permitir lectura web p\u00fablica'))
 send('Prepara un informe con https://example.org/')
 await screen.findByDisplayValue(review.proposed_text)
 expect(screen.queryByLabelText('URL HTTPS de entrada · una por línea')).toBeNull()
 expect(calls.filter(c=>c.path==='/api/web-read/authorizations')).toHaveLength(1)
 const sent=calls.find(c=>c.path.endsWith('/chat'))!
 expect(sent.body).toMatchObject({web_read_authorization_id:'web-grant',conversation_id:context.conversation_id,revision:7})
 expect(sent.body).not.toHaveProperty('allow_workspace_write_proposals')
 expect(screen.queryByLabelText('Proponer archivos')).toBeNull()
 expect(screen.getByRole('table')).toBeTruthy()
 fireEvent.click(screen.getByRole('button',{name:'Inspeccionar ejecuci\u00f3n'}));expect(inspect).toHaveBeenCalledWith({conversationId:context.conversation_id,revision:9,traceId:'trace-proposal'})
 expect(calls.filter(c=>c.path.endsWith('/actions')).every(c=>c.body.operation==='review_write')).toBe(true)
 send();await waitFor(()=>expect(calls.filter(c=>c.path.endsWith('/chat'))).toHaveLength(2))
 expect(calls.filter(c=>c.path.endsWith('/chat'))[1].body).not.toHaveProperty('allow_workspace_write_proposals')
})
it('does not infer proposal authorization from a request without the per-turn checkbox',async()=>{
 const {calls}=await setup();send();await screen.findByDisplayValue(review.proposed_text)
 expect(calls.find(c=>c.path.endsWith('/chat'))!.body.allow_workspace_write_proposals).toBeUndefined();expect(calls.some(c=>c.body?.operation==='apply_write')).toBe(false)
})
it('restores the trusted summary into the same review card with only a read request',async()=>{
 const {calls}=await setup({stored:summary});await screen.findByDisplayValue(review.proposed_text)
 expect(calls.map(c=>c.body.operation)).toEqual(['review_write']);expect((screen.getByRole('button',{name:'Aceptar plan y ejecutar'}) as HTMLButtonElement).disabled).toBe(false);expect(calls.some(c=>c.body?.operation==='apply_write')).toBe(false)
})
it.each([
 {...summary,context:{...context,owner_id:'foreign'}},
 {...summary,context:{...context,conversation_id:'foreign'}},
 {...summary,context:{...context,conversation_revision:99}},
 {...summary,path:'../outside'},null,
])('rejects persisted foreign or malformed summary without SDK action',async(stored)=>{
 const {calls}=await setup({stored});await screen.findByRole('alert');expect(screen.queryByRole('button',{name:'Aceptar plan y ejecutar'})).toBeNull();expect(calls).toEqual([])
})
it('does not trust a proposal reference attached to a user message',async()=>{
 const {calls}=await setup({stored:summary,role:'user'});await screen.findByRole('alert');expect(calls).toEqual([])
})
it('assistant and delegated-agent navigation do not expose a per-turn project permission control',async()=>{
 await setup();expect(screen.queryByLabelText('Proponer archivos')).toBeNull()
 fireEvent.click(screen.getByRole('button',{name:'Orquestador BAGO5'}));await screen.findByRole('region',{name:'conv-assistant'});expect(screen.queryByLabelText('Proponer archivos')).toBeNull()
 await openDelegatedChild('Agente fixture');expect(screen.queryByLabelText('Proponer archivos')).toBeNull()
})

it('restores a persisted partial proposal alongside FAILED state and its own Inspect identity',async()=>{
 const {calls,inspect}=await setup({stored:summary,failed:true});await screen.findByDisplayValue(review.proposed_text)
 expect(screen.getByText('Respuesta fallida · no se recibió una respuesta del proveedor.')).toBeTruthy()
 fireEvent.click(screen.getByRole('button',{name:'Inspeccionar ejecución'}))
 expect(inspect).toHaveBeenCalledWith({conversationId:context.conversation_id,revision:7,traceId:'trace-proposal'})
 expect(calls.map(c=>c.body.operation)).toEqual(['review_write'])
})
