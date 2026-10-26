// @vitest-environment jsdom
import React from 'react'
import {resetLocaleForTests,setLocale,t} from '../../src/i18n'
beforeEach(()=>{localStorage.clear();resetLocaleForTests();setLocale('es')})
import {beforeEach,afterEach,expect,it,vi} from 'vitest'
import {act,cleanup,fireEvent,render,screen,waitFor,within} from '@testing-library/react'
import AgentChat from '../../src/components/AgentChat'
import {openDelegatedChild,withPersistedDelegation} from '../helpers/delegated-agent-chat'
const response=(body:unknown,status=200)=>({ok:status<400,status,json:async()=>body})
const make=(id='conv-web',messages:any[]=[])=>({id,owner_kind:'assistant',owner_id:'app-assistant',title:id,status:'active',revision:7,updated_at:'2026-10-23',messages})
afterEach(()=>{cleanup();vi.unstubAllGlobals()})
async function setup(options:{grant?:unknown;status?:number;conversation?:any;agents?:any[]}={}){
 HTMLElement.prototype.scrollIntoView=()=>{}
 let conv=options.conversation??make();const mutations:Array<{path:string;body:any}>=[]
 const fetch=vi.fn(async(path:string,init?:RequestInit)=>{
  const body=init?.body?JSON.parse(String(init.body)):null
  if(init?.method&&init.method!=='GET')mutations.push({path,body})
  if(path.startsWith('/api/conversations?'))return response({conversations:[conv]})
  if(path==='/api/conversations/'+conv.id)return response(conv)
  if(path==='/api/agents/list')return response({agents:options.agents??[]})
  if(path==='/api/providers/selection')return response({provider_id:null,model_id:null})
  if(path==='/api/web-read/authorizations')return response(options.grant??{authorization_id:'web-token',allowed_origins:['https://www.sollutia.com']},options.status??200)
  if(path==='/api/workspace-read/authorizations')return response({authorization_id:'local-token'})
  if(path==='/api/chat/control'||path.endsWith('/chat')){
   conv={...conv,revision:conv.revision+1,messages:[...conv.messages,{id:'reply',role:'assistant',content:'Respuesta fixture'}]}
   return response({operation:'chat',source:'ollama',assistant_message:'Respuesta fixture',conversation:conv})
  }
  return response({models:[],proposals:[]})
 });vi.stubGlobal('fetch',fetch)
 render(<AgentChat cognitiveMode="baseline" onNavigate={()=>{}} onOpenProviderSettings={()=>{}} onOpenCognitionSettings={()=>{}} />)
 await waitFor(()=>expect(fetch.mock.calls.some(call=>call[0]==='/api/conversations/'+conv.id)).toBe(true))
 await waitFor(()=>expect(screen.queryByText('Loading conversations…')).toBeNull());await act(async()=>{})
 return {mutations,fetch}
}
function enable(url='https://www.sollutia.com/'){
 fireEvent.click(screen.getByLabelText('Permitir lectura web pública'))
 fireEvent.change(screen.getByLabelText('URL HTTPS de entrada · una por línea'),{target:{value:url}})
}
function send(){fireEvent.change(screen.getByPlaceholderText('Escribe al asistente…'),{target:{value:'Lee esta página pública'}});fireEvent.click(screen.getByRole('button',{name:'Enviar'}))}
it('does not authorize on mount or infer web permission from the message',async()=>{
 const {mutations}=await setup();expect(mutations).toEqual([]);send()
 await screen.findByText('Respuesta fixture')
 expect(mutations.map(item=>item.path)).toEqual(['/api/chat/control'])
 expect(mutations[0].body.web_read_authorization_id).toBeUndefined()
})
it('binds the explicit one-turn grant to exact owner, conversation and revision before sending',async()=>{
 const {mutations}=await setup();enable();expect(within(screen.getByLabelText('Orígenes web solicitados')).getByText('https://www.sollutia.com')).toBeTruthy();send()
 await screen.findByText('Respuesta fixture')
 expect(mutations.map(item=>item.path)).toEqual(['/api/web-read/authorizations','/api/chat/control'])
 expect(mutations[0].body).toEqual({owner_kind:'assistant',owner_id:'app-assistant',conversation_id:'conv-web',revision:7,urls:['https://www.sollutia.com/']})
 expect(mutations[1].body).toMatchObject({conversation_id:'conv-web',revision:7,web_read_authorization_id:'web-token'})
 expect((screen.getByLabelText('Permitir lectura web pública') as HTMLInputElement).checked).toBe(false)
 send();await waitFor(()=>expect(mutations).toHaveLength(3));expect(mutations[2].body.web_read_authorization_id).toBeUndefined()
})
it('preserves independent project-file permission alongside web permission',async()=>{
 const {mutations}=await setup();enable();fireEvent.click(screen.getByLabelText('Permitir lectura de archivos del proyecto'))
 fireEvent.change(screen.getByLabelText('Rutas relativas al proyecto'),{target:{value:'README.md'}});send()
 await screen.findByText('Respuesta fixture')
 expect(mutations.map(item=>item.path)).toEqual(['/api/workspace-read/authorizations','/api/web-read/authorizations','/api/chat/control'])
 expect(mutations[2].body).toMatchObject({workspace_read_authorization_id:'local-token',web_read_authorization_id:'web-token'})
})
it.each(['','http://www.sollutia.com/','https://user:pass@www.sollutia.com/','https://www.sollutia.com:8443/','not a URL',Array.from({length:9},(_,i)=>`https://www.sollutia.com/${i}`).join('\n')])('rejects invalid entry scope before requesting authorization: %s',async(url)=>{
 const {mutations}=await setup();enable(url);send();await screen.findByRole('alert');expect(mutations).toEqual([])
})
it.each([
 [{detail:'web scope denied'},403],
 [{authorization_id:'',allowed_origins:['https://www.sollutia.com']},200],
 [{authorization_id:'web-token',allowed_origins:['https://foreign.example']},200],
 [{authorization_id:'web-token'},200],
])('does not send the turn when grant response is denied or malformed',async(grant,status)=>{
 const {mutations}=await setup({grant,status});enable();send();await screen.findByRole('alert')
 expect(mutations.map(item=>item.path)).toEqual(['/api/web-read/authorizations'])
})
it('restores public-web provenance separately from project files and shows failure honestly',async()=>{
 const hash='a'.repeat(64),raw='b'.repeat(64),manifest='c'.repeat(64)
 await setup({conversation:make('conv-web',[{id:'saved',role:'assistant',content:'Lectura guardada fixture',references:{sources:[{path:'README.md',start_line:1,end_line:2,content_sha256:hash},{source_type:'public_web',path:'https://www.sollutia.com/final',final_url:'https://www.sollutia.com/final',requested_url:'https://www.sollutia.com/',start_line:1,end_line:4,content_sha256:hash,text_sha256:hash,raw_sha256:raw,captured_at:'2026-10-23T12:00:00Z',snapshot_id:'snap-fixture',snapshot_manifest_sha256:manifest}],read_events:[{kind:'public_web_read',decision:'FAIL',path:'https://www.sollutia.com/bad',reason_code:'PERSISTENCE_FAILED'}]}}])})
 const web=await screen.findByLabelText('Fuentes web públicas consultadas');expect(web.hasAttribute('open')).toBe(false);fireEvent.click(within(web).getByText('Fuentes web · 1'));expect(within(web).getByRole('link').getAttribute('href')).toBe('https://www.sollutia.com/final')
 expect(web.textContent).toContain('2026-10-23T12:00:00Z');expect(web.textContent).toContain(raw);expect(web.textContent).toContain(hash);expect(web.textContent).toContain(manifest);expect(web.textContent).toContain('snap-fixture')
 expect(screen.getByLabelText('Archivos del proyecto consultados').textContent).not.toContain('sollutia')
 expect(screen.getByLabelText('Evidencia de análisis de solo lectura').querySelector('summary')?.textContent).toContain('PERSISTENCE_FAILED');expect(screen.getByText(/Lectura web pública: FAIL/)).toBeTruthy()
})
it('does not make an unsafe stored source URL clickable',async()=>{
 await setup({conversation:make('conv-web',[{id:'unsafe',role:'assistant',content:'Fuente corrupta fixture',references:{sources:[{source_type:'public_web',path:'javascript:alert(1)',start_line:1,end_line:1}]}}])})
 const section=await screen.findByLabelText('Fuentes web públicas consultadas');expect(within(section).queryByRole('link')).toBeNull();expect(within(section).getByText('URL no válida para abrir')).toBeTruthy()
})
it('clears consent on owner switch and grants only to the delegated saved agent',async()=>{
 HTMLElement.prototype.scrollIntoView=()=>{}
 const agent={id:'agent-web',config:{name:'Agente Web fixture',type:'analyst',description:'Fixture',provider_id:'ollama-cloud',model_id:'fixture-model'}}
 const agentConv={...make('conv-agent'),owner_kind:'agent',owner_id:agent.id}
 const assistant=withPersistedDelegation(make(),agent,agentConv.id)
 const mutations:Array<{path:string;body:any}>=[]
 vi.stubGlobal('fetch',vi.fn(async(path:string,init?:RequestInit)=>{
  const body=init?.body?JSON.parse(String(init.body)):null;if(init?.method&&init.method!=='GET')mutations.push({path,body})
  if(path.startsWith('/api/conversations?'))return response({conversations:[path.includes('owner_kind=agent')?agentConv:assistant]})
  if(path==='/api/conversations/conv-web')return response(assistant)
  if(path==='/api/conversations/conv-agent')return response(agentConv)
  if(path==='/api/agents/list')return response({agents:[agent]})
  if(path==='/api/web-read/authorizations')return response({authorization_id:'agent-web-token',allowed_origins:['https://www.sollutia.com']})
  if(path==='/api/agents/agent-web/chat')return response({source:'ollama',assistant_message:'Respuesta agente fixture',conversation:{...agentConv,revision:8,messages:[{id:'agent-reply',role:'assistant',content:'Respuesta agente fixture'}]}})
  return response({models:[],proposals:[]})
 }))
 render(<AgentChat cognitiveMode="baseline" onNavigate={()=>{}} onOpenProviderSettings={()=>{}} onOpenCognitionSettings={()=>{}} />)
 await screen.findByRole('region',{name:'conv-web'});await act(async()=>{})
 enable();await openDelegatedChild('Agente Web fixture')
 await waitFor(()=>expect((screen.getByLabelText('Permitir lectura web pública') as HTMLInputElement).checked).toBe(false))
 expect(screen.queryByLabelText('URL HTTPS de entrada · una por línea')).toBeNull()
 await waitFor(()=>expect(screen.getByText('Chats · Agente Web fixture')).toBeTruthy())
 enable();expect((screen.getByLabelText('URL HTTPS de entrada · una por línea') as HTMLTextAreaElement).value).toBe('https://www.sollutia.com/')
 fireEvent.change(screen.getByPlaceholderText('Escribe a Agente Web fixture.'),{target:{value:'Lee el sitio autorizado'}});fireEvent.click(screen.getByRole('button',{name:'Enviar'}))
 await screen.findByText('Respuesta agente fixture')
 expect(mutations.map(item=>item.path)).toEqual(['/api/web-read/authorizations','/api/agents/agent-web/chat'])
 expect(mutations[0].body).toEqual({owner_kind:'agent',owner_id:'agent-web',conversation_id:'conv-agent',revision:7,urls:['https://www.sollutia.com/']})
 expect(mutations[1].body).toMatchObject({conversation_id:'conv-agent',revision:7,web_read_authorization_id:'agent-web-token'})
})

it('clears the editable scope and consent when switching conversations of the same owner',async()=>{
 HTMLElement.prototype.scrollIntoView=()=>{}
 const first=make('conv-first'),second=make('conv-second')
 vi.stubGlobal('fetch',vi.fn(async(path:string)=>{
  if(path.startsWith('/api/conversations?'))return response({conversations:[first,second]})
  if(path==='/api/conversations/conv-first')return response(first)
  if(path==='/api/conversations/conv-second')return response(second)
  return response({models:[],agents:[],proposals:[]})
 }))
 render(<AgentChat cognitiveMode="baseline" onNavigate={()=>{}} onOpenProviderSettings={()=>{}} onOpenCognitionSettings={()=>{}} />)
 await screen.findByRole('region',{name:'conv-first'});await act(async()=>{});enable()
 fireEvent.click(screen.getByText(/Conversaciones y agentes/));fireEvent.click(screen.getByRole('button',{name:/conv-second/}))
 await screen.findByRole('region',{name:'conv-second'});await act(async()=>{})
 expect((screen.getByLabelText('Permitir lectura web pública') as HTMLInputElement).checked).toBe(false)
 fireEvent.click(screen.getByLabelText('Permitir lectura web pública'))
 expect((screen.getByLabelText('URL HTTPS de entrada · una por línea') as HTMLTextAreaElement).value).toBe('')
})
it('deduplicates entry URLs and displays both origins without broadening the server grant',async()=>{
 const {mutations}=await setup({grant:{authorization_id:'two-origins',allowed_origins:['https://www.sollutia.com','https://example.org']}})
 enable('https://www.sollutia.com/\nhttps://example.org/page\nhttps://www.sollutia.com/')
 expect(within(screen.getByLabelText('Orígenes web solicitados')).getAllByRole('listitem')).toHaveLength(2)
 send();await screen.findByText('Respuesta fixture')
 expect(mutations[0].body.urls).toEqual(['https://www.sollutia.com/','https://example.org/page'])
 expect(mutations[1].body.web_read_authorization_id).toBe('two-origins')
})
