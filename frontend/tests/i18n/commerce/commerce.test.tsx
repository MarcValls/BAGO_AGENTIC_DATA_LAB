// @vitest-environment jsdom
import React from 'react'
import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest'
import {act,cleanup,fireEvent,render,screen,waitFor,within} from '@testing-library/react'
import {es,en} from '../../../src/i18n/domains/commerce'
import {resetLocaleForTests,setLocale,t,apiError,localMessage,errorMessage} from '../../../src/i18n'
import Contacts from '../../../src/components/Contacts'
import Communications from '../../../src/components/Communications'
import WorkspaceManager from '../../../src/components/WorkspaceManager'
import WorkspaceWriteReview from '../../../src/components/WorkspaceWriteReview'
import WhatsAppSettings from '../../../src/components/WhatsAppSettings'
import AgentNavigation from '../../../src/components/AgentNavigation'
import AssistantMarkdown from '../../../src/components/AssistantMarkdown'
import ChatTools from '../../../src/components/ChatTools'
import AgentChat from '../../../src/components/AgentChat'

const response=(body:unknown,status=200)=>({ok:status<400,status,json:async()=>body})
const switchTo=(locale:'es'|'en')=>act(()=>setLocale(locale))
beforeEach(()=>{localStorage.clear();resetLocaleForTests();Element.prototype.scrollIntoView=vi.fn()})
afterEach(()=>{cleanup();vi.unstubAllGlobals();vi.restoreAllMocks()})

describe('commerce presentation catalogs and live preference',()=>{
 it('has identical manually authored keys and interpolation parameters',()=>{
  expect(Object.keys(en)).toEqual(Object.keys(es))
  for(const key of Object.keys(es) as (keyof typeof es)[]){
   const params=(value:string)=>[...value.matchAll(/\{(\w+)\}/g)].map(match=>match[1]).sort()
   expect(en[key].trim(),key).not.toBe('')
   expect(params(en[key]),key).toEqual(params(es[key]))
  }
 })
 it('keeps a pending local notice and an unknown original diagnostic reactive',()=>{
  const notice=localMessage('commerce.import_notice',{imported:2,skipped:1})
  const failure=apiError({detail:{code:'unknown_fixture',message:'EXACT diagnosis: café / 503'}},503,'commerce')
  expect(errorMessage(notice)).toContain('Importados: 2')
  switchTo('en')
  expect(errorMessage(notice)).toContain('Imported: 2')
  expect(errorMessage(failure)).toContain('EXACT diagnosis: café / 503')
  expect(errorMessage(failure)).toContain('technical')
  switchTo('es')
  expect(errorMessage(notice)).toContain('Importados: 2')
 })
 it('preserves contact form values and selected tab without refetching on language change',async()=>{
  const fetcher=vi.fn(async(input:string)=>response(input.includes('/google/status')?{configured:false,connected:false,live_verified:false}:{contacts:[]}))
  vi.stubGlobal('fetch',fetcher)
  render(<Contacts />)
  await waitFor(()=>expect(screen.queryByText('Buscando contactos…')).toBeNull())
  const name=screen.getByLabelText('Nombre',{exact:true}) as HTMLInputElement
  fireEvent.change(name,{target:{value:'Nombre propio sin traducción'}})
  const before=fetcher.mock.calls.length
  switchTo('en')
  expect(screen.getByLabelText('Name',{exact:true})).toBe(name)
  expect(name.value).toBe('Nombre propio sin traducción')
  expect(fetcher.mock.calls.length).toBe(before)
  fireEvent.click(screen.getByRole('tab',{name:'Google'}))
  switchTo('es')
  expect(screen.getByRole('tab',{name:'Google'}).getAttribute('aria-selected')).toBe('true')
  expect(name.value).toBe('Nombre propio sin traducción')
 })
 it('preserves a draft editor and scheduling values without any sending or refetch on language change',async()=>{
  const fetcher=vi.fn(async(input:string)=>response(input.endsWith('/contacts')?{contacts:[{id:'contact-original',name:'Ana Original',phone:'+34123456789'}]}:input.endsWith('/drafts')?{drafts:[]}:{runs:[]}))
  vi.stubGlobal('fetch',fetcher)
  render(<Communications initialContact={{id:'contact-original',name:'Ana Original',phone:'+34123456789'}} />)
  const message=await screen.findByLabelText('Mensaje',{selector:'textarea'}) as HTMLTextAreaElement
  fireEvent.change(message,{target:{value:'Contenido del usuario: hello / hola'}})
  fireEvent.change(screen.getByLabelText('Cuándo'),{target:{value:'weekly'}})
  fireEvent.click(screen.getByLabelText('Lunes'))
  const count=fetcher.mock.calls.length
  switchTo('en')
  expect(screen.getByLabelText('Message',{selector:'textarea'})).toBe(message)
  expect(message.value).toBe('Contenido del usuario: hello / hola')
  expect((screen.getByLabelText('Monday') as HTMLInputElement).checked).toBe(true)
  expect((screen.getByLabelText('When') as HTMLSelectElement).value).toBe('weekly')
  expect(fetcher.mock.calls.length).toBe(count)
  expect(fetcher.mock.calls.every(call=>call.length===1||!(call[1] as RequestInit)?.method)).toBe(true)
 })
 it('preserves a project creation review and its approval while translating its parameterized scope',async()=>{
  const fetcher=vi.fn(async(input:string)=>response(input.endsWith('/config')?{configured:true,parent:'C:/ProjectRoot'}:{workspaces:[]}))
  vi.stubGlobal('fetch',fetcher)
  render(<WorkspaceManager />)
  await screen.findByLabelText('Nombre de carpeta')
  fireEvent.change(screen.getByLabelText('Nombre de carpeta'),{target:{value:'original-folder'}})
  fireEvent.change(screen.getByLabelText('Título del proyecto'),{target:{value:'Original title'}})
  fireEvent.click(screen.getByRole('button',{name:'Revisar creación'}))
  const review=screen.getByRole('dialog')
  const approval=within(review).getByRole('checkbox') as HTMLInputElement
  fireEvent.click(approval)
  const count=fetcher.mock.calls.length
  switchTo('en')
  expect(within(review).getByText('Create original-folder under C:/ProjectRoot and seed context, state and continuity')).toBeTruthy()
  expect(within(review).getByRole('checkbox')).toBe(approval)
  expect(approval.checked).toBe(true)
  expect(fetcher.mock.calls.length).toBe(count)
 })
 it('preserves the exact write proposal and consent; changing language never writes',async()=>{
  const context={owner_kind:'agent' as const,owner_id:'agent-original',conversation_id:'conversation-original',conversation_revision:2}
  const proposal={proposal_id:'write_'+'a'.repeat(32),revision:'revision-original',workspace_id:'workspace-original',path:'src/original.txt',mode:'modify' as const,status:'PROPOSED' as const,context,proposed_sha256:'a'.repeat(64)}
  const fetcher=vi.fn(async(_input:string,init:RequestInit)=>{
   expect(JSON.parse(String(init.body)).operation).toBe('review_write')
   return response({...proposal,before_sha256:'b'.repeat(64),review_sha256:'c'.repeat(64),proposed_text:'EXACT proposed content',before_text:'EXACT old content',diff:'EXACT diff',receipt:null,observation:null})
  })
  vi.stubGlobal('fetch',fetcher)
  render(<WorkspaceWriteReview proposal={proposal} ownerKind="agent" ownerId="agent-original" conversationId="conversation-original" conversationRevision={2} />)
  const editor=await screen.findByLabelText('Contenido propuesto') as HTMLTextAreaElement
  const consent=screen.getByRole('checkbox') as HTMLInputElement
  fireEvent.click(consent)
  const count=fetcher.mock.calls.length
  switchTo('en')
  expect(screen.getByLabelText('Proposed content')).toBe(editor)
  expect(editor.value).toBe('EXACT proposed content')
  expect(consent.checked).toBe(true)
  expect(screen.getByRole('button',{name:'Confirm and write'}).hasAttribute('disabled')).toBe(false)
  expect(fetcher.mock.calls.length).toBe(count)
  fireEvent.change(editor,{target:{value:'EXACT edited content'}})
  switchTo('es')
  expect(editor.value).toBe('EXACT edited content')
  expect(consent.checked).toBe(false)
  expect(screen.getByRole('button',{name:'Confirmar y escribir'}).hasAttribute('disabled')).toBe(true)
  expect(fetcher.mock.calls.length).toBe(count)
 })
 it('keeps WhatsApp session settings and their technical reason without opening a browser',async()=>{
  const fetcher=vi.fn(async()=>response({state:'connected',configured:true,label:'Original session',checked_at:'2026-10-23T12:30:00Z',reason:'EXACT backend reason',browser_available:true,persistent_profile:true}))
  vi.stubGlobal('fetch',fetcher)
  render(<WhatsAppSettings />)
  const name=await screen.findByDisplayValue('Original session') as HTMLInputElement
  fireEvent.change(name,{target:{value:'User session label'}})
  const count=fetcher.mock.calls.length
  switchTo('en')
  expect(screen.getByLabelText('Session name')).toBe(name)
  expect(name.value).toBe('User session label')
  expect(screen.getByText('Connected')).toBeTruthy()
  expect(screen.getByText('EXACT backend reason')).toBeTruthy()
  expect(screen.getByText('Original technical detail')).toBeTruthy()
  expect(fetcher.mock.calls.length).toBe(count)
 })
 it('updates navigation and Markdown wrapper accessibility while preserving source text',()=>{
  render(<><AgentNavigation activeView="runner" collapsed={false} onExpandSidebar={()=>{}} onNavigate={()=>{}} /><AssistantMarkdown content={'| Original | Data |\n| --- | --- |\n| café | untouched |\n\n- [x] Original task'} /></>)
  expect(screen.getByRole('button',{name:/Ejecutar/})).toBeTruthy()
  expect(screen.getByRole('region',{name:'Tabla de la respuesta'})).toBeTruthy()
  switchTo('en')
  expect(screen.getByRole('button',{name:/Run \/ Test/})).toBeTruthy()
  expect(screen.getByRole('region',{name:'Response table'})).toBeTruthy()
  expect(screen.getByText('café')).toBeTruthy()
  expect(screen.getByText('Original task')).toBeTruthy()
 })
 it('updates tool labels without replacing the open menu',()=>{
  render(<ChatTools conversationId="original" />)
  const menu=screen.getByText('Recursos').closest('details')!
  menu.open=true
  switchTo('en')
  expect(screen.getByText('Resources').closest('details')).toBe(menu)
  expect(menu.open).toBe(true)
  expect(screen.getByRole('button',{name:'Consult file'})).toBeTruthy()
 })
 it('keeps the chat composer, per-turn permission and paths without executing a turn',async()=>{
  const fetcher=vi.fn(async(input:string)=>response(input.includes('chat-models')?{models:[]}:input.includes('selection')?null:input.includes('/agents/list')?{agents:[]}:{conversations:[]}))
  vi.stubGlobal('fetch',fetcher)
  render(<AgentChat onNavigate={()=>{}} onOpenProviderSettings={()=>{}} onOpenCognitionSettings={()=>{}} cognitiveMode="baseline" />)
  await waitFor(()=>expect(fetcher.mock.calls.some(([url])=>url.includes('/agents/list'))).toBe(true))
  const editor=screen.getByLabelText('Mensaje al asistente o agente seleccionado') as HTMLTextAreaElement
  fireEvent.change(editor,{target:{value:'User prompt must stay original'}})
  fireEvent.click(screen.getByLabelText('Permitir lectura de archivos del proyecto'))
  const paths=screen.getByLabelText('Rutas relativas al proyecto') as HTMLTextAreaElement
  fireEvent.change(paths,{target:{value:'src/original.py'}})
  const count=fetcher.mock.calls.length
  switchTo('en')
  expect(screen.getByLabelText('Message the assistant or selected agent')).toBe(editor)
  expect(editor.value).toBe('User prompt must stay original')
  expect((screen.getByLabelText('Allow project file reads') as HTMLInputElement).checked).toBe(true)
  expect(screen.getByLabelText('Project-relative paths')).toBe(paths)
  expect(paths.value).toBe('src/original.py')
  expect(fetcher.mock.calls.length).toBe(count)
 })
})
