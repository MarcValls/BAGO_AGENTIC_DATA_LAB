// @vitest-environment jsdom
import React from 'react'
import {resetLocaleForTests,setLocale,t} from '../../src/i18n'
beforeEach(()=>{localStorage.clear();resetLocaleForTests();setLocale('es')})
import {beforeEach,afterEach,expect,it,vi} from 'vitest'
import {act,cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import AgentChat from '../../src/components/AgentChat'
import {summary,review,context,response} from './fixtures'
afterEach(()=>{cleanup();vi.unstubAllGlobals()})
async function setup(options:{stored?:any;role?:string;failed?:boolean}={}){
 HTMLElement.prototype.scrollIntoView=()=>{}
 const agent={id:context.owner_id,config:{name:'Agente fixture',type:'tool',description:'Fixture',provider_id:'ollama-cloud',model_id:'model-fixture'}}
 const make=(id:string,owner_kind:string,owner_id:string)=>({id,owner_kind,owner_id,title:id,status:'active',revision:7,updated_at:'2026-10-23',messages:[] as any[]})
 const assistant=make('conv-assistant','assistant','app-assistant');let agentConv=make(context.conversation_id,'agent',context.owner_id)
 if(options.stored!==undefined)agentConv.messages=[{id:'saved',role:options.role??'assistant',content:options.failed?'':'### Propuesta guardada',...(options.failed?{status:'failed'}:{}),references:{workspace_write_proposal:options.stored,trace:{trace_id:'trace-proposal',trace_state:'local_only'}}}]
 const calls:Array<{path:string;body:any}>=[]
 vi.stubGlobal('fetch',vi.fn(async(path:string,init?:RequestInit)=>{
  const body=init?.body?JSON.parse(String(init.body)):null
  if(init?.method&&init.method!=='GET')calls.push({path,body})
  if(path.startsWith('/api/conversations?'))return response({conversations:[path.includes('owner_kind=agent')?agentConv:assistant]})
  if(path==='/api/conversations/'+assistant.id)return response(assistant)
  if(path==='/api/conversations/'+agentConv.id)return response(agentConv)
  if(path==='/api/agents/list')return response({agents:[agent]})
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
 fireEvent.click(screen.getByText(/Conversaciones y agentes/));fireEvent.click(await screen.findByRole('button',{name:/Agente fixture/}))
 await screen.findByRole('region',{name:'Agente fixture'});await act(async()=>{})
 return {calls,inspect}
}
function send(){fireEvent.change(screen.getByPlaceholderText('Escribe a Agente fixture.'),{target:{value:'Prepara un informe'}});fireEvent.click(screen.getByRole('button',{name:'Enviar'}))}
it('selected agent requires opt-in each turn independently of web, preserves Markdown and never autoapplies a returned proposal',async()=>{
 const {calls,inspect}=await setup()
 fireEvent.click(screen.getByLabelText('Proponer archivos'));fireEvent.click(screen.getByLabelText('Permitir lectura web pública'));fireEvent.change(screen.getByLabelText('URL HTTPS de entrada · una por línea'),{target:{value:'https://example.org/'}})
 send();await screen.findByDisplayValue(review.proposed_text)
 const sent=calls.find(c=>c.path.endsWith('/chat'))!
 expect(sent.body).toMatchObject({allow_workspace_write_proposals:true,web_read_authorization_id:'web-grant',conversation_id:context.conversation_id,revision:7})
 expect((screen.getByLabelText('Proponer archivos') as HTMLInputElement).checked).toBe(false)
 expect(screen.getByRole('table')).toBeTruthy()
 fireEvent.click(screen.getByRole('button',{name:'Inspeccionar ejecución'}));expect(inspect).toHaveBeenCalledWith({conversationId:context.conversation_id,revision:9,traceId:'trace-proposal'})
 expect(calls.filter(c=>c.path.endsWith('/actions')).every(c=>c.body.operation==='review_write')).toBe(true)
 send();await waitFor(()=>expect(calls.filter(c=>c.path.endsWith('/chat'))).toHaveLength(2))
 expect(calls.filter(c=>c.path.endsWith('/chat'))[1].body.allow_workspace_write_proposals).toBeUndefined()
})
it('does not infer proposal authorization from a request without the per-turn checkbox',async()=>{
 const {calls}=await setup();send();await screen.findByDisplayValue(review.proposed_text)
 expect(calls.find(c=>c.path.endsWith('/chat'))!.body.allow_workspace_write_proposals).toBeUndefined();expect(calls.some(c=>c.body?.operation==='apply_write')).toBe(false)
})
it('restores the trusted summary into the same review card with only a read request',async()=>{
 const {calls}=await setup({stored:summary});await screen.findByDisplayValue(review.proposed_text)
 expect(calls.map(c=>c.body.operation)).toEqual(['review_write']);expect((screen.getByRole('button',{name:'Confirmar y escribir'}) as HTMLButtonElement).disabled).toBe(true)
})
it.each([
 {...summary,context:{...context,owner_id:'foreign'}},
 {...summary,context:{...context,conversation_id:'foreign'}},
 {...summary,context:{...context,conversation_revision:99}},
 {...summary,path:'../outside'},null,
])('rejects persisted foreign or malformed summary without SDK action',async(stored)=>{
 const {calls}=await setup({stored});await screen.findByRole('alert');expect(screen.queryByRole('button',{name:'Confirmar y escribir'})).toBeNull();expect(calls).toEqual([])
})
it('does not trust a proposal reference attached to a user message',async()=>{
 const {calls}=await setup({stored:summary,role:'user'});await screen.findByRole('alert');expect(calls).toEqual([])
})
it('switching back to assistant clears the selected-agent proposal permission',async()=>{
 await setup();fireEvent.click(screen.getByLabelText('Proponer archivos'));fireEvent.click(screen.getByRole('button',{name:'Orquestador BAGO5'}));await screen.findByRole('region',{name:'conv-assistant'});expect(screen.queryByLabelText('Proponer archivos')).toBeNull()
 fireEvent.click(screen.getByRole('button',{name:/Agente fixture/}));await screen.findByRole('region',{name:'Agente fixture'});expect((screen.getByLabelText('Proponer archivos') as HTMLInputElement).checked).toBe(false)
})


it('restores a persisted partial proposal alongside FAILED state and its own Inspect identity',async()=>{
 const {calls,inspect}=await setup({stored:summary,failed:true});await screen.findByDisplayValue(review.proposed_text)
 expect(screen.getByText('Respuesta fallida · no se recibió una respuesta del proveedor.')).toBeTruthy()
 fireEvent.click(screen.getByRole('button',{name:'Inspeccionar ejecución'}))
 expect(inspect).toHaveBeenCalledWith({conversationId:context.conversation_id,revision:7,traceId:'trace-proposal'})
 expect(calls.map(c=>c.body.operation)).toEqual(['review_write'])
})
