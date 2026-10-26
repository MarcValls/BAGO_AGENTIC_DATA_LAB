// @vitest-environment jsdom
import React from 'react'
import {resetLocaleForTests,setLocale,t} from '../../src/i18n'
beforeEach(()=>{localStorage.clear();resetLocaleForTests();setLocale('es')})
import {beforeEach,afterEach,expect,it,vi} from 'vitest'
import {act,cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import AgentChat from '../../src/components/AgentChat'
import {openDelegatedChild,withPersistedDelegation} from '../helpers/delegated-agent-chat'
const response=(body:unknown,status=200)=>({ok:status<400,status,json:async()=>body})
const source=(path:string)=>({source_type:'public_web',path,start_line:1,end_line:2,content_sha256:'a'.repeat(64)})
const oldMessage={id:'old',role:'assistant',content:'Respuesta anterior',references:{sources:[source('https://prior.example/')]}}
const make=(extra:any={})=>({id:'conv-failed',owner_kind:'assistant',owner_id:'app-assistant',title:'Conversation fixture',status:'active',revision:7,updated_at:'2026-10-23',messages:[oldMessage],...extra})
const failed=()=>make({revision:8,messages:[oldMessage,{id:'user',role:'user',content:'Lee esta página'},{id:'failed',role:'assistant',content:'',status:'failed',references:{sources:[source('https://read.example/')],read_events:[{kind:'public_web_read',decision:'ALLOW',path:'https://read.example/'}],trace:{trace_id:'trace-failed',trace_state:'local_only'},execution_failure:{state:'FAILED',response_received:false}}}]})
const detail=()=>({message:'Provider unavailable original',state:'provider_unavailable',execution_state:'FAILED',conversation_id:'conv-failed',revision:8,trace:{trace_id:'trace-failed',trace_state:'local_only'},evidence_persistence:{conversation:'persisted',trace:'persisted'}})
afterEach(()=>{cleanup();vi.unstubAllGlobals()})
async function setup(options:{initial?:any;saved?:any;error?:any;pending?:boolean;reloadPending?:boolean}={}){
 HTMLElement.prototype.scrollIntoView=()=>{}
 let finish:(value:any)=>void=()=>{};let finishReload:(value:any)=>void=()=>{};let posted=false
 const inspect=vi.fn(), select=vi.fn()
 const other=make({id:'conv-other',title:'Other fixture',messages:[{id:'other',role:'assistant',content:'Other selected'}]})
 const fetch=vi.fn(async(path:string,init?:RequestInit)=>{
  if(path.startsWith('/api/conversations?'))return response({conversations:[options.initial??make(),other]})
  if(path==='/api/conversations/conv-other')return response(other)
  if(path==='/api/conversations/conv-failed'){
   if(posted&&options.reloadPending)return new Promise(resolve=>{finishReload=resolve})
   return response(posted?(options.saved??failed()):(options.initial??make()))
  }
  if(path==='/api/chat/control'){
   posted=true
   if(options.pending)return new Promise(resolve=>{finish=resolve})
   return response({detail:options.error??detail()},503)
  }
  if(path==='/api/agents/list')return response({agents:[]})
  return response({models:[],proposals:[]})
 });vi.stubGlobal('fetch',fetch)
 const props={cognitiveMode:'baseline' as const,onNavigate:()=>{},onOpenProviderSettings:()=>{},onOpenCognitionSettings:()=>{},onInspectExecution:inspect,onInspectionSelection:select}
 const view=render(<AgentChat {...props}/>);await screen.findByText(options.initial?.messages[0]?.content??'Respuesta anterior');await act(async()=>{})
 const send=()=>{fireEvent.change(screen.getByLabelText('Mensaje al asistente o agente seleccionado'),{target:{value:'Lee esta página'}});fireEvent.click(screen.getByRole('button',{name:'Enviar'}))}
 const switchConversation=()=>{fireEvent.click(screen.getByText(/Conversaciones y agentes/));fireEvent.click(screen.getByRole('button',{name:/Other fixture/}))}
 return {view,props,fetch,inspect,select,send,switchConversation,finish:(value:any)=>finish(value),finishReload:(value:any)=>finishReload(value)}
}
it('restores persisted failed turn sources and trace after HTTP failure, keeping the original error',async()=>{
 const {send,inspect,select}=await setup();send()
 await screen.findByText(/Respuesta fallida/)
 expect(screen.getByRole('alert').textContent).toContain('Provider unavailable original')
 expect(screen.getByText('https://read.example/:1-2')).toBeTruthy()
 expect(screen.getByText('https://prior.example/:1-2')).toBeTruthy()
 expect(screen.queryByRole('button',{name:'Copiar respuesta'})).toBeTruthy() // previous response only
 expect(screen.getAllByRole('button',{name:'Copiar respuesta'})).toHaveLength(1)
 fireEvent.click(screen.getByRole('button',{name:'Inspeccionar ejecución'}))
 expect(inspect).toHaveBeenCalledWith({conversationId:'conv-failed',revision:8,traceId:'trace-failed'})
 await waitFor(()=>expect(select).toHaveBeenCalledWith({conversationId:'conv-failed',revision:8}))
 expect((screen.getByLabelText('Permitir lectura web pública') as HTMLInputElement).checked).toBe(false)
})
it('reloads a failed assistant message as failed, retaining inspect identity and collapsed sources',async()=>{
 const {inspect}=await setup({initial:failed()})
 await screen.findByText(/Respuesta fallida/)
 expect(screen.getAllByLabelText('Fuentes web públicas consultadas').every(node=>!node.hasAttribute('open'))).toBe(true)
 fireEvent.click(screen.getByRole('button',{name:'Inspeccionar ejecución'}))
 expect(inspect).toHaveBeenCalledWith({conversationId:'conv-failed',revision:8,traceId:'trace-failed'})
})
it.each([
 ['wrong conversation',()=>failed(),()=>({...detail(),conversation_id:'foreign'})],
 ['wrong owner',()=>({...failed(),owner_id:'another-owner'}),detail],
 ['wrong owner kind',()=>({...failed(),owner_kind:'agent'}),detail],
 ['wrong GET conversation',()=>({...failed(),id:'foreign'}),detail],
 ['wrong revision',()=>({...failed(),revision:9}),detail],
 ['wrong trace',()=>{const c=failed();c.messages[2].references.trace.trace_id='foreign-trace';return c},detail],
 ['not a failed message',()=>{const c=failed();c.messages[2].status='complete';return c},detail],
 ['missing persistence',failed,()=>({...detail(),evidence_persistence:{conversation:'failed'},revision:null})],
 ['missing failure DTO',failed,()=>({message:'Provider unavailable original'})],
])('does not import unrelated or unconfirmed evidence: %s',async(_label,saved,error)=>{
 const {send,inspect}=await setup({saved:saved(),error:error()});send();await screen.findByRole('alert');await act(async()=>{})
 expect(screen.getByText('Respuesta anterior')).toBeTruthy()
 expect(screen.getByText('https://prior.example/:1-2')).toBeTruthy()
 expect(screen.queryByText('https://read.example/:1-2')).toBeNull()
 expect(screen.queryByRole('button',{name:'Inspeccionar ejecución'})).toBeNull()
 expect(inspect).not.toHaveBeenCalled()
 expect(screen.getByRole('alert').textContent).toContain('Provider unavailable original')
})
it('ignores late failed response after selecting another conversation',async()=>{
 const {send,switchConversation,finish,fetch}=await setup({pending:true});send();await waitFor(()=>expect(fetch.mock.calls.some(([path])=>path==='/api/chat/control')).toBe(true))
 switchConversation();await screen.findByText('Other selected')
 await act(async()=>finish(response({detail:detail()},503)))
 expect(screen.queryByText('https://read.example/:1-2')).toBeNull();expect(screen.queryByRole('alert')).toBeNull()
 expect(screen.getByText('Other selected')).toBeTruthy()
})
it('ignores late evidence refresh after selecting another conversation',async()=>{
 const {send,switchConversation,finishReload,fetch}=await setup({reloadPending:true});send();await screen.findByRole('alert')
 await waitFor(()=>expect(fetch.mock.calls.filter(([path])=>path==='/api/conversations/conv-failed')).toHaveLength(2))
 switchConversation();await screen.findByText('Other selected')
 await act(async()=>finishReload(response(failed())))
 expect(screen.queryByText('https://read.example/:1-2')).toBeNull();expect(screen.getByText('Other selected')).toBeTruthy()
})

it('keeps previous sources and provider error when the evidence GET itself fails',async()=>{
 const {send,finishReload}=await setup({reloadPending:true});send();await screen.findByRole('alert')
 await act(async()=>finishReload(response({detail:'Evidence storage offline'},500)))
 expect(screen.getByRole('alert').textContent).toContain('Provider unavailable original')
 expect(screen.queryByText('Evidence storage offline')).toBeNull()
 expect(screen.getByText('https://prior.example/:1-2')).toBeTruthy()
 expect(screen.queryByText(/Respuesta fallida/)).toBeNull()
})
it('restores a persisted failed message without inventing a trace when trace persistence failed',async()=>{
 const saved=failed();delete (saved.messages[2].references as any).trace
 const error={...detail(),trace:{trace_state:'local_trace_failed'},evidence_persistence:{conversation:'persisted',trace:'failed'}}
 const {send}=await setup({saved,error});send();await screen.findByText(/Respuesta fallida/)
 expect(screen.getByText('https://read.example/:1-2')).toBeTruthy()
 expect(screen.queryByRole('button',{name:'Inspeccionar ejecución'})).toBeNull()
 expect(screen.getByRole('alert').textContent).toContain('Provider unavailable original')
})
it('binds failure recovery to the selected agent owner and preserves inspect identity',async()=>{
 HTMLElement.prototype.scrollIntoView=()=>{}
 const agent={id:'agent-web',config:{name:'Web reader fixture',description:'Fixture',type:'tool',system_prompt:'Fixture',tools:[],provider_id:'ollama-cloud',model_id:'fixture'},created_at:'2026-10-23'}
 const initial=make({owner_kind:'agent',owner_id:'agent-web'}),saved={...failed(),owner_kind:'agent',owner_id:'agent-web'}
 const parent=withPersistedDelegation(make({id:'conv-parent'}),agent,initial.id)
 let posted=false
 const inspect=vi.fn()
 const fetch=vi.fn(async(path:string)=>{
  if(path.startsWith('/api/conversations?'))return response({conversations:path.includes('owner_kind=agent')?[initial]:[parent]})
  if(path==='/api/conversations/conv-parent')return response(parent)
  if(path==='/api/conversations/conv-failed')return response(posted?saved:initial)
  if(path==='/api/agents/list')return response({agents:[agent]})
  if(path==='/api/agents/agent-web/chat'){posted=true;return response({detail:detail()},503)}
  return response({models:[],proposals:[]})
 });vi.stubGlobal('fetch',fetch)
 render(<AgentChat cognitiveMode="baseline" onNavigate={()=>{}} onOpenProviderSettings={()=>{}} onOpenCognitionSettings={()=>{}} onInspectExecution={inspect}/>)
 await openDelegatedChild('Web reader fixture')
 await screen.findByText('Respuesta anterior');await act(async()=>{})
 fireEvent.change(screen.getByLabelText('Mensaje al asistente o agente seleccionado'),{target:{value:'Lee esta página'}})
 fireEvent.click(screen.getByRole('button',{name:'Enviar'}));await screen.findByText(/Respuesta fallida/)
 expect(fetch.mock.calls.some(([path])=>path==='/api/agents/agent-web/chat')).toBe(true)
 fireEvent.click(screen.getByRole('button',{name:'Inspeccionar ejecución'}))
 expect(inspect).toHaveBeenCalledWith({conversationId:'conv-failed',revision:8,traceId:'trace-failed'})
 expect(screen.getByRole('alert').textContent).toContain('Provider unavailable original')
})
