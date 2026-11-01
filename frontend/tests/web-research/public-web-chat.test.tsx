// @vitest-environment jsdom
import React from 'react'
import {resetLocaleForTests,setLocale,t} from '../../src/i18n'
beforeEach(()=>{localStorage.clear();resetLocaleForTests();setLocale('es')})
import {beforeEach,afterEach,expect,it,vi} from 'vitest'
import {act,cleanup,fireEvent,render,screen,waitFor,within} from '@testing-library/react'
import {readPublicWebPreference,readPublicWebNotice} from '../../src/utils/publicWebPreference'
import AgentChat from '../../src/components/AgentChat'
import {conversationButton} from '../helpers/conversation-library'
import {openDelegatedChild,withPersistedDelegation} from '../helpers/delegated-agent-chat'
const response=(body:unknown,status=200)=>({ok:status<400,status,json:async()=>body})
const webIdentity={projectId:'project-1',root:'D:/work/project',ownerKind:'assistant' as const,ownerId:'app-assistant',conversationId:'conv-web'}
const project={project_id:'project-1',title:'Proyecto de prueba',scope:'project',root:'D:/work/project'}
const make=(id='conv-web',messages:any[]=[])=>({id,owner_kind:'assistant',owner_id:'app-assistant',title:id,status:'active',revision:7,updated_at:'2026-10-23',messages})
afterEach(()=>{cleanup();vi.unstubAllGlobals()})
async function setup(options:{grant?:unknown;status?:number;conversation?:any;agents?:any[];project?:unknown;grantWait?:Promise<void>;chatWait?:Promise<void>;chatStatus?:number;wrongConversation?:boolean;replyStatus?:string}={}){
 HTMLElement.prototype.scrollIntoView=()=>{}
 let grantCount=0;let conv=options.conversation??make();const mutations:Array<{path:string;body:any}>=[]
 const fetch=vi.fn(async(path:string,init?:RequestInit)=>{
  const body=init?.body?JSON.parse(String(init.body)):null
  if(init?.method&&init.method!=='GET'&&path!=='/api/project-permissions/directories')mutations.push({path,body})
  if(path.startsWith('/api/conversations?'))return response({conversations:[conv]})
  if(path==='/api/conversations/'+conv.id)return response(conv)
  if(path==='/api/agents/list')return response({agents:options.agents??[]})
  if(path==='/api/providers/selection')return response({provider_id:null,model_id:null})
  if(path==='/api/project-folders/v1/active')return response(options.project??project)
  if(path==='/api/project-permissions')return response({project_id:'project-1',root:'D:/work/project',binding:{workspace_root:'D:/work/project',revision:4},revision:3,state:'active',read_directories:['src'],write_directories:['docs']})
  if(path==='/api/project-permissions/directories')return response({project_id:'project-1',root:'D:/work/project',binding:{workspace_root:'D:/work/project',revision:4},revision:3,directory:'.',directories:[{name:'src',path:'src'},{name:'docs',path:'docs'}],truncated:false})
  if(path==='/api/web-read/authorizations'){await options.grantWait;grantCount++;return response(options.grant??{authorization_id:grantCount===1?'web-token':`web-token-${grantCount}`,allowed_origins:[...new Set(body.urls.map((url:string)=>new URL(url).origin))]},options.status??200)}
  if(path==='/api/workspace-read/authorizations')return response({authorization_id:'local-token'})
  if(path==='/api/chat/control'||path.endsWith('/chat')){
   await options.chatWait
   if(options.chatStatus)return response({detail:'Provider unavailable fixture'},options.chatStatus)
   if(options.wrongConversation)return response({operation:'chat',conversation:{...conv,id:'foreign-conversation',revision:conv.revision+1,messages:[{id:'foreign-reply',role:'assistant',content:'Wrong context fixture'}]}})
   conv={...conv,revision:conv.revision+1,messages:[...conv.messages,{id:'reply-'+(conv.revision+1),role:'assistant',content:'Respuesta fixture',...(options.replyStatus?{status:options.replyStatus}:{})}]}
   return response({operation:'chat',source:'ollama',assistant_message:'Respuesta fixture',conversation:conv})
  }
  return response({models:[],proposals:[]})
 });vi.stubGlobal('fetch',fetch)
 const view=render(<AgentChat cognitiveMode="baseline" onNavigate={()=>{}} onOpenProviderSettings={()=>{}} onOpenCognitionSettings={()=>{}} />)
 await waitFor(()=>expect(fetch.mock.calls.some(call=>call[0]==='/api/conversations/'+conv.id)).toBe(true))
 await waitFor(()=>expect(screen.queryByText('Loading conversations…')).toBeNull());await act(async()=>{})
 return {mutations,fetch,view,conversation:()=>conv}
}
function enable(url='https://www.sollutia.com/'){
 fireEvent.change(screen.getByPlaceholderText(t('commerce.message_the_assistant')),{target:{value:url}})
 fireEvent.click(screen.getByLabelText('Permitir lectura web pública'))
}
function send(message='Lee esta página pública'){fireEvent.change(screen.getByPlaceholderText(t('commerce.message_the_assistant')),{target:{value:message}});fireEvent.click(screen.getByRole('button',{name:t('commerce.send')}))}
it('does not authorize on mount or infer web permission from the message',async()=>{
 const {mutations}=await setup();expect(mutations).toEqual([]);send('Lee https://www.sollutia.com/')
 await screen.findByText('Respuesta fixture')
 expect(mutations.map(item=>item.path)).toEqual(['/api/chat/control'])
 expect(mutations[0].body.web_read_authorization_id).toBeUndefined()
})
it('persists explicit conversation consent but mints a fresh revision-bound grant on each turn',async()=>{
 const {mutations}=await setup();enable();expect(screen.queryByLabelText('Alcance de lectura web pública')).toBeNull();send()
 await screen.findByText('Respuesta fixture')
 expect(mutations.map(item=>item.path)).toEqual(['/api/web-read/authorizations','/api/chat/control'])
 expect(mutations[0].body).toEqual({owner_kind:'assistant',owner_id:'app-assistant',conversation_id:'conv-web',revision:7,urls:['https://www.sollutia.com/']})
 expect(mutations[1].body).toMatchObject({conversation_id:'conv-web',revision:7,web_read_authorization_id:'web-token'})
 expect((screen.getByLabelText('Permitir lectura web pública') as HTMLInputElement).checked).toBe(true)
 send();await waitFor(()=>expect(mutations).toHaveLength(4));expect(mutations[2].body).toMatchObject({conversation_id:'conv-web',revision:8});expect(mutations[3].body.web_read_authorization_id).toBe('web-token-2')
 expect(JSON.stringify(localStorage)).not.toContain('web-token')
})
it('keeps saved project READ policy separate from the one-turn public-web grant',async()=>{
 const {mutations}=await setup();enable();
 const panel=screen.getByRole('region',{name:'Contexto del proyecto'});fireEvent.click(within(panel).getByRole('button',{name:'Administrar acceso'}));const dialog=await screen.findByRole('dialog',{name:'Permisos del proyecto'});expect(within(dialog).getByText('src',{selector:'.project-permissions__scope code'})).toBeTruthy();fireEvent.click(within(dialog).getByRole('button',{name:'Cerrar'}));send()
 await screen.findByText('Respuesta fixture')
 expect(mutations.map(item=>item.path)).toEqual(['/api/web-read/authorizations','/api/chat/control'])
 expect(mutations[1].body).toMatchObject({web_read_authorization_id:'web-token'})
 expect(mutations[1].body).not.toHaveProperty('workspace_read_authorization_id')
})
it.each(['http://www.sollutia.com/','https://user:pass@www.sollutia.com/','https://www.sollutia.com:8443/',Array.from({length:9},(_,i)=>`https://www.sollutia.com/${i}`).join('\n')])('rejects invalid entry scope before requesting authorization: %s',async(url)=>{
 const {mutations}=await setup();enable(url);send(url || 'Lee esta página pública');await screen.findByRole('alert');expect(mutations).toEqual([])
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
  const body=init?.body?JSON.parse(String(init.body)):null;if(init?.method&&init.method!=='GET'&&path!=='/api/project-permissions/directories')mutations.push({path,body})
  if(path.startsWith('/api/conversations?'))return response({conversations:[path.includes('owner_kind=agent')?agentConv:assistant]})
  if(path==='/api/conversations/conv-web')return response(assistant)
  if(path==='/api/conversations/conv-agent')return response(agentConv)
  if(path==='/api/agents/list')return response({agents:[agent]})
  if(path==='/api/project-folders/v1/active')return response(project)
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
 fireEvent.change(screen.getByPlaceholderText('Escribe a Agente Web fixture.'),{target:{value:'https://www.sollutia.com/'}});fireEvent.click(screen.getByLabelText('Permitir lectura web pública'));expect(readPublicWebPreference({...webIdentity,ownerKind:'agent',ownerId:'agent-web',conversationId:'conv-agent'}).preference.urls).toBe('https://www.sollutia.com/')
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
  if(path==='/api/project-folders/v1/active')return response(project)
  return response({models:[],agents:[],proposals:[]})
 }))
 render(<AgentChat cognitiveMode="baseline" onNavigate={()=>{}} onOpenProviderSettings={()=>{}} onOpenCognitionSettings={()=>{}} />)
 await screen.findByRole('region',{name:'conv-first'});await act(async()=>{});enable()
 fireEvent.click(screen.getByText(/Conversaciones y agentes/));fireEvent.click(conversationButton(document,'conv-second'))
 await screen.findByRole('region',{name:'conv-second'});await act(async()=>{})
 expect((screen.getByLabelText('Permitir lectura web pública') as HTMLInputElement).checked).toBe(false)
 fireEvent.click(screen.getByLabelText('Permitir lectura web pública'))
 expect(screen.queryByLabelText('URL HTTPS de entrada · una por línea')).toBeNull()
})
it('deduplicates entry URLs and displays both origins without broadening the server grant',async()=>{
 const {mutations}=await setup({grant:{authorization_id:'two-origins',allowed_origins:['https://www.sollutia.com','https://example.org']}})
 enable('https://www.sollutia.com/\nhttps://example.org/page\nhttps://www.sollutia.com/')
 expect(screen.queryByLabelText('Alcance de lectura web pública')).toBeNull()
 send();await screen.findByText('Respuesta fixture')
 expect(within(screen.getByLabelText('Orígenes web solicitados')).getAllByRole('listitem')).toHaveLength(2)
 expect(mutations[0].body.urls).toEqual(['https://www.sollutia.com/','https://example.org/page'])
 expect(mutations[1].body.web_read_authorization_id).toBe('two-origins')
})

it('restores exact conversation consent on remount and persists OFF for the next remount',async()=>{
 const first=await setup();enable();first.view.unmount()
 const second=await setup();expect((screen.getByLabelText('Permitir lectura web pública') as HTMLInputElement).checked).toBe(true)
 expect(readPublicWebPreference(webIdentity).preference.urls).toBe('https://www.sollutia.com/')
 fireEvent.click(screen.getByLabelText('Permitir lectura web pública'));send();await screen.findByText('Respuesta fixture')
 expect(second.mutations.map(item=>item.path)).toEqual(['/api/chat/control']);second.view.unmount()
 await setup();expect((screen.getByLabelText('Permitir lectura web pública') as HTMLInputElement).checked).toBe(false)
})

it('does not inherit consent in another project, root or conversation',async()=>{
 const first=await setup();enable();first.view.unmount()
 const otherProject=await setup({project:{...project,project_id:'project-2'}});expect((screen.getByLabelText('Permitir lectura web pública') as HTMLInputElement).checked).toBe(false);otherProject.view.unmount()
 const otherRoot=await setup({project:{...project,root:'D:/other'}});expect((screen.getByLabelText('Permitir lectura web pública') as HTMLInputElement).checked).toBe(false);otherRoot.view.unmount()
 await setup({conversation:make('other-conversation')});expect((screen.getByLabelText('Permitir lectura web pública') as HTMLInputElement).checked).toBe(false)
})

it('fails closed when project identity is unknown and never issues a web grant',async()=>{
 const {mutations}=await setup({project:{project_id:null,root:null}})
 const checkbox=screen.getByLabelText('Permitir lectura web pública') as HTMLInputElement
 expect(checkbox.disabled).toBe(true);send();await screen.findByText('Respuesta fixture')
 expect(mutations.map(item=>item.path)).toEqual(['/api/chat/control'])
})

it('keeps consent after provider or grant failure without storing a bearer token',async()=>{
 const first=await setup({chatStatus:503});enable();send();await screen.findByRole('alert')
 expect((screen.getByLabelText('Permitir lectura web pública') as HTMLInputElement).checked).toBe(true);first.view.unmount()
 await setup({status:403});send();await screen.findByRole('alert')
 expect((screen.getByLabelText('Permitir lectura web pública') as HTMLInputElement).checked).toBe(true)
 expect(JSON.stringify(localStorage)).not.toContain('web-token')
})

it('OFF while waiting for a grant prevents sending the turn and a late result cannot restore ON',async()=>{
 let release!:()=>void;const grantWait=new Promise<void>(resolve=>{release=resolve})
 const {mutations,view}=await setup({grantWait});enable();send()
 await waitFor(()=>expect(mutations.map(item=>item.path)).toEqual(['/api/web-read/authorizations']))
 fireEvent.click(screen.getByLabelText('Permitir lectura web pública'));await act(async()=>release())
 await screen.findByRole('alert');expect(mutations.map(item=>item.path)).toEqual(['/api/web-read/authorizations'])
 expect((screen.getByLabelText('Permitir lectura web pública') as HTMLInputElement).checked).toBe(false)
 view.unmount();await setup();expect((screen.getByLabelText('Permitir lectura web pública') as HTMLInputElement).checked).toBe(false)
})

it('seeds an explicitly enabled empty scope from the message on Send; later same-origin paths need no extra click',async()=>{
 const {mutations}=await setup();fireEvent.click(screen.getByLabelText('Permitir lectura web pública'))
 fireEvent.change(screen.getByPlaceholderText(t('commerce.message_the_assistant')),{target:{value:'Lee (https://www.sollutia.com/), por favor.'}});fireEvent.click(screen.getByRole('button',{name:'Enviar'}))
 await screen.findByText('Respuesta fixture');expect(mutations[0].body.urls).toEqual(['https://www.sollutia.com/'])
 fireEvent.change(screen.getByPlaceholderText(t('commerce.message_the_assistant')),{target:{value:'Continúa con https://www.sollutia.com/otra'}});fireEvent.click(screen.getByRole('button',{name:'Enviar'}))
 await waitFor(()=>expect(mutations).toHaveLength(4));expect(mutations[3].body.web_read_authorization_id).toBe('web-token-2')
 fireEvent.change(screen.getByPlaceholderText(t('commerce.message_the_assistant')),{target:{value:'Lee https://other.example/'}});fireEvent.click(screen.getByRole('button',{name:'Enviar'}))
 await screen.findByRole('article',{name:'Mensaje pendiente de permiso web'});expect(mutations).toHaveLength(4)
 expect(screen.getByLabelText('Orígenes web solicitados').textContent).not.toContain('other.example')
})

it('shows the one-time notice in English only after the first actual reply',async()=>{
 setLocale('en');const {mutations}=await setup()
 fireEvent.click(screen.getByLabelText('Allow public web reading'))
 expect(screen.queryByRole('note')).toBeNull()
 send();await screen.findByText('Respuesta fixture')
 expect(screen.getByRole('note').textContent).toContain('Web reading notice')
 expect(screen.getByRole('note').textContent).toContain('does not confirm that a page was read')
 expect(mutations.map(item=>item.path)).toEqual(['/api/chat/control'])
})

it.each([true,false])('transfers an explicit draft choice to its first conversation, with origins=%s',async(withOrigins)=>{
 HTMLElement.prototype.scrollIntoView=()=>{}
 const created={...make('created-explicitly'),revision:0},mutations:Array<{path:string;body:any}>=[]
 vi.stubGlobal('fetch',vi.fn(async(path:string,init?:RequestInit)=>{
  const body=init?.body?JSON.parse(String(init.body)):null
  if(init?.method&&init.method!=='GET'&&path!=='/api/project-permissions/directories')mutations.push({path,body})
  if(path==='/api/project-folders/v1/active')return response(project)
  if(path.startsWith('/api/conversations?'))return response({conversations:[]})
  if(path==='/api/conversations')return response(created)
  if(path==='/api/web-read/authorizations')return response({authorization_id:'fresh-first',allowed_origins:['https://www.sollutia.com']})
  if(path==='/api/chat/control')return response({operation:'chat',assistant_message:'Primera respuesta',conversation:{...created,revision:1,messages:[{id:'first',role:'assistant',content:'Primera respuesta'}]}})
  return response({models:[],agents:[],proposals:[]})
 }))
 const view=render(<AgentChat cognitiveMode="baseline" onNavigate={()=>{}} onOpenProviderSettings={()=>{}} onOpenCognitionSettings={()=>{}} />)
 await waitFor(()=>expect((screen.getByLabelText('Permitir lectura web pública') as HTMLInputElement).disabled).toBe(false))
 fireEvent.click(screen.getByLabelText('Permitir lectura web pública'))
 fireEvent.change(screen.getByPlaceholderText(t('commerce.message_the_assistant')),{target:{value:withOrigins?'Lee https://www.sollutia.com/':'Hola, responde en esta conversación'}});fireEvent.click(screen.getByRole('button',{name:'Enviar'}))
 await screen.findByText('Primera respuesta')
 expect(mutations.map(item=>item.path)).toEqual(withOrigins?['/api/conversations','/api/web-read/authorizations','/api/chat/control']:['/api/conversations','/api/chat/control'])
 expect(mutations[1].body).toMatchObject({conversation_id:created.id,revision:0})
 expect(readPublicWebPreference({...webIdentity,conversationId:created.id}).preference).toEqual({enabled:true,urls:withOrigins?'https://www.sollutia.com/':''})
 expect(screen.getByRole('note').closest('article')?.textContent).toContain('Primera respuesta')
 expect((screen.getByLabelText('Permitir lectura web pública') as HTMLInputElement).checked).toBe(true)
 view.unmount();await setup({conversation:created});expect((screen.getByLabelText('Permitir lectura web pública') as HTMLInputElement).checked).toBe(true)
})

it('does not issue a grant after storage fails and displays a truthful disabled preference',async()=>{
 const {mutations}=await setup()
 const storage=vi.spyOn(Storage.prototype,'setItem').mockImplementation(()=>{throw new Error('Storage full')})
 try {
  fireEvent.click(screen.getByLabelText('Permitir lectura web pública'))
  expect((screen.getByLabelText('Permitir lectura web pública') as HTMLInputElement).checked).toBe(false)
  expect(screen.getByRole('alert').textContent).toContain('queda desactivada')
  send();await screen.findByText('Respuesta fixture');expect(mutations.map(item=>item.path)).toEqual(['/api/chat/control'])
 } finally {storage.mockRestore()}
})

it('uses only the chat composer for URLs and permits new sites beside the pending human message with one automatic send',async()=>{
 const {mutations}=await setup();enable();send();await screen.findByText('Respuesta fixture')
 expect(screen.queryByLabelText('URL HTTPS de entrada · una por línea')).toBeNull()
 expect([...document.querySelectorAll('textarea')].every(node=>node.id==='control-chat-input')).toBe(true)
 const text='Lee https://other.example/nueva y cita su contenido.'
 send(text)
 const pending=await screen.findByRole('article',{name:'Mensaje pendiente de permiso web'})
 expect(within(pending).getByText(text)).toBeTruthy()
 expect(within(pending).getByText('https://other.example')).toBeTruthy()
 expect(mutations).toHaveLength(2)
 fireEvent.click(within(pending).getByRole('button',{name:'Permitir estos sitios'}))
 await waitFor(()=>expect(mutations).toHaveLength(4))
 expect(mutations[2].body.urls).toEqual(['https://other.example/nueva'])
 expect(mutations[3].body.message).toBe(text)
 expect(mutations[3].body.web_read_authorization_id).toBe('web-token-2')
 expect(screen.queryByRole('article',{name:'Mensaje pendiente de permiso web'})).toBeNull()
})

it('editing a pending message even back to its old text invalidates its site approval',async()=>{
 const {mutations}=await setup();enable();send();await screen.findByText('Respuesta fixture')
 const text='Lee https://other.example/nueva';send(text)
 const pending=await screen.findByRole('article',{name:'Mensaje pendiente de permiso web'})
 const composer=screen.getByPlaceholderText(t('commerce.message_the_assistant'))
 fireEvent.change(composer,{target:{value:text+' editado'}});fireEvent.change(composer,{target:{value:text}})
 const button=within(pending).getByRole('button',{name:'Permitir estos sitios'}) as HTMLButtonElement
 expect(button.disabled).toBe(true);fireEvent.click(button);expect(mutations).toHaveLength(2)
 fireEvent.click(screen.getByRole('button',{name:'Enviar'}))
 const updated=screen.getByRole('article',{name:'Mensaje pendiente de permiso web'})
 fireEvent.click(within(updated).getByRole('button',{name:'Permitir estos sitios'}))
 await waitFor(()=>expect(mutations).toHaveLength(4));expect(mutations[3].body.message).toBe(text)
})

it('OFF invalidates the message-bound site approval without granting or sending',async()=>{
 const {mutations}=await setup();enable();send();await screen.findByText('Respuesta fixture');send('Lee https://other.example/')
 const pending=await screen.findByRole('article',{name:'Mensaje pendiente de permiso web'})
 fireEvent.click(screen.getByLabelText('Permitir lectura web pública'))
 const button=within(pending).getByRole('button',{name:'Permitir estos sitios'}) as HTMLButtonElement
 expect(button.disabled).toBe(true);fireEvent.click(button);expect(mutations).toHaveLength(2)
})

it('puts the amber notice only in the first received reply per activation; empty ON sends ordinary chat with zero grants',async()=>{
 const {mutations}=await setup()
 fireEvent.click(screen.getByLabelText('Permitir lectura web pública'))
 expect(screen.queryByRole('note')).toBeNull()
 expect(document.querySelector('form.control-chat-composer')?.querySelector('[aria-label="Alcance de lectura web pública"]')).toBeNull()
 expect(readPublicWebPreference(webIdentity).preference).toEqual({enabled:true,urls:''})
 send('Hola, explícame qué puedes hacer')
 const notice=await screen.findByRole('note',{name:'Alcance de lectura web pública'})
 expect(notice.classList.contains('chat-web-notice')).toBe(true)
 expect(notice.closest('article')?.textContent).toContain('Respuesta fixture')
 expect(notice.closest('form')).toBeNull()
 expect(notice.textContent).toContain('Todavía no hay sitios permitidos')
 expect(notice.textContent).toContain('no confirma que se haya leído una página')
 expect(notice.textContent).toContain('⚠')
 const firstActivation=readPublicWebNotice(webIdentity).state.activationId
 expect(readPublicWebNotice(webIdentity).state.pending).toBe(false)
 send('Continúa con una explicación normal')
 await waitFor(()=>expect(mutations).toHaveLength(2))
 await waitFor(()=>expect(screen.getAllByRole('article',{name:'Asistente'})).toHaveLength(2))
 const replies=screen.getAllByRole('article',{name:'Asistente'})
 expect(screen.getAllByRole('note')).toHaveLength(1)
 expect(within(replies[replies.length-1]).queryByRole('note')).toBeNull()
 fireEvent.click(screen.getByLabelText('Permitir lectura web pública'))
 fireEvent.click(screen.getByLabelText('Permitir lectura web pública'))
 expect(screen.getAllByRole('note')).toHaveLength(1)
 expect(readPublicWebNotice(webIdentity).state.activationId).not.toBe(firstActivation)
 send('Nuevo turno tras reactivar')
 await waitFor(()=>expect(screen.getAllByRole('note')).toHaveLength(2))
 expect(mutations.map(item=>item.path)).toEqual(['/api/chat/control','/api/chat/control','/api/chat/control'])
 expect(mutations.every(item=>item.body.web_read_authorization_id===undefined)).toBe(true)
})

it('restores consumed message annotations on reload without repeating the notice on the next reply',async()=>{
 const first=await setup();fireEvent.click(screen.getByLabelText('Permitir lectura web pública'));send('Hola')
 await screen.findByRole('note')
 const conversation=first.conversation();first.view.unmount()
 const second=await setup({conversation})
 expect(screen.getAllByRole('note')).toHaveLength(1)
 send('Otra respuesta')
 await waitFor(()=>expect(second.mutations).toHaveLength(1))
 await waitFor(()=>expect(screen.getAllByRole('article',{name:'Asistente'})).toHaveLength(2))
 expect(screen.getAllByRole('note')).toHaveLength(1)
 const replies=screen.getAllByRole('article',{name:'Asistente'})
 expect(within(replies[replies.length-1]).queryByRole('note')).toBeNull()
})

it.each([{chatStatus:503},{wrongConversation:true},{replyStatus:'failed'}])('does not consume or attach a notice on failed or mismatched reply: %j',async(options)=>{
 const first=await setup(options);fireEvent.click(screen.getByLabelText('Permitir lectura web pública'))
 const activation=readPublicWebNotice(webIdentity).state.activationId
 send('Hola sin enlaces')
 if(options.replyStatus)await screen.findByText('Respuesta fixture');else await screen.findByRole('alert')
 expect(screen.queryByRole('note')).toBeNull()
 expect(first.mutations.map(item=>item.path)).toEqual(['/api/chat/control'])
 expect(readPublicWebNotice(webIdentity).state).toMatchObject({activationId:activation,pending:true,notices:[]})
 first.view.unmount();const retry=await setup();send('Reintenta la respuesta')
 await screen.findByRole('note');expect(retry.mutations.map(item=>item.path)).toEqual(['/api/chat/control'])
})

it('OFF while a reply is in flight prevents its annotation, and the next activation waits for its own reply',async()=>{
 let release!:()=>void;const chatWait=new Promise<void>(resolve=>{release=resolve})
 const {mutations}=await setup({chatWait});fireEvent.click(screen.getByLabelText('Permitir lectura web pública'));send('Respuesta pendiente')
 await waitFor(()=>expect(mutations).toHaveLength(1))
 fireEvent.click(screen.getByLabelText('Permitir lectura web pública'))
 await act(async()=>release());await screen.findByText('Respuesta fixture')
 expect(screen.queryByRole('note')).toBeNull()
 fireEvent.click(screen.getByLabelText('Permitir lectura web pública'));send('Respuesta de la nueva activación')
 await screen.findByRole('note');expect(mutations).toHaveLength(2)
 const replies=screen.getAllByRole('article',{name:'Asistente'})
 expect(within(replies[0]).queryByRole('note')).toBeNull()
 expect(within(replies[1]).getByRole('note')).toBeTruthy()
})

it('does not attach a late reply notice to another conversation after switching',async()=>{
 let release!:(value:unknown)=>void;const chatWait=new Promise(resolve=>{release=resolve})
 const first=make(),other=make('conv-other',[{id:'other-reply',role:'assistant',content:'Respuesta de otra conversación'}])
 const calls:string[]=[]
 vi.stubGlobal('fetch',vi.fn(async(path:string,init?:RequestInit)=>{
  if(init?.method==='POST')calls.push(path)
  if(path==='/api/project-folders/v1/active')return response(project)
  if(path.startsWith('/api/conversations?'))return response({conversations:[first,other]})
  if(path==='/api/conversations/conv-web')return response(first)
  if(path==='/api/conversations/conv-other')return response(other)
  if(path==='/api/chat/control')return chatWait
  return response({models:[],agents:[],proposals:[]})
 }))
 render(<AgentChat cognitiveMode="baseline" onNavigate={()=>{}} onOpenProviderSettings={()=>{}} onOpenCognitionSettings={()=>{}} />)
 await screen.findByRole('region',{name:'conv-web'});await act(async()=>{})
 fireEvent.click(screen.getByLabelText('Permitir lectura web pública'));send('Mensaje del primer contexto')
 await waitFor(()=>expect(calls).toEqual(['/api/chat/control']))
 fireEvent.click(conversationButton(document,'conv-other'));await screen.findByText('Respuesta de otra conversación')
 await act(async()=>release(response({operation:'chat',conversation:{...first,revision:8,messages:[{id:'late-reply',role:'assistant',content:'Respuesta tardía del otro contexto'}]}})))
 expect(screen.queryByText('Respuesta tardía del otro contexto')).toBeNull()
 expect(screen.queryByRole('note')).toBeNull()
 expect(readPublicWebNotice(webIdentity).state.pending).toBe(true)
})
