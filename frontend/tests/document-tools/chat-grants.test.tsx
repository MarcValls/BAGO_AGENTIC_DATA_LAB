// @vitest-environment jsdom
import React from 'react'
import {afterEach,beforeEach,expect,it,vi} from 'vitest'
import {act,cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import {resetLocaleForTests,t} from '../../src/i18n'
import AgentChat from '../../src/components/AgentChat'
import {openDelegatedChild,withPersistedDelegation} from '../helpers/delegated-agent-chat'

const response=(data:any)=>({ok:true,status:200,json:async()=>data})
beforeEach(()=>{localStorage.clear();resetLocaleForTests();HTMLElement.prototype.scrollIntoView=()=>{}})
afterEach(()=>{cleanup();vi.unstubAllGlobals()})

it('delegates one selected producer snapshot and contact to the reviewer, with per-message draft consent',async()=>{
 const agent={id:'reviewer',config:{name:'Revisor fixture',type:'tool',description:'Synthetic reviewer',provider_id:'ollama-cloud',model_id:'fixture-model',tools:['delivery_review','delivery_prepare_draft']}}
 const make=(id:string,kind:string,owner:string)=>({id,owner_kind:kind,owner_id:owner,title:id,status:'active',revision:7,updated_at:'2026-10-24',messages:[] as any[]})
 const assistantBase=make('conv-assistant','assistant','app-assistant');let conversation=make('conv-review','agent','reviewer')
 const assistant=withPersistedDelegation(assistantBase,agent,conversation.id)
 const otherConversation=make('conv-other','agent','reviewer')
 const run={work_id:'production_1',owner_id:'different-producer',conversation_id:'other-conversation',source_root:'C:/synthetic',candidate_id:'a'.repeat(64),scope_sha256:'b'.repeat(64),artifacts:[{path:'out/report.csv',sha256:'c'.repeat(64)}],business_acceptance:'NOT_RUN'}
 const calls:Array<{path:string;body:any}>=[]
 vi.stubGlobal('fetch',vi.fn(async(path:string,init?:RequestInit)=>{
   const body=init?.body?JSON.parse(String(init.body)):null
   if(init?.method)calls.push({path,body})
   if(path==='/api/agents/list')return response({agents:[agent]})
   if(path.startsWith('/api/providers/chat-models'))return response({models:[{provider_id:'ollama-cloud',label:'Ollama',state:'ready',model_id:'fixture-model',chat_enabled:true}]})
   if(path==='/api/providers/selection')return response({provider_id:'ollama-cloud',model_id:'fixture-model'})
   if(path.startsWith('/api/conversations?'))return response({conversations:path.includes('owner_kind=agent')?[conversation,otherConversation]:[assistant]})
   if(path==='/api/conversations/conv-assistant')return response(assistant)
   if(path==='/api/conversations/conv-review')return response(conversation)
   if(path==='/api/conversations/conv-other')return response(otherConversation)
   if(path.startsWith('/api/agent-tools/context'))return response({runs:[run],contacts:[{id:'contact_fixture',name:'Contacto fixture',phone:'+34911000000'}]})
   if(path==='/api/document-tools/authorizations')return response({authorization_id:'review-grant',root:run.source_root})
   if(path==='/api/agents/reviewer/chat'){
     conversation={...conversation,revision:conversation.revision+2,messages:[...conversation.messages,{id:'answer-'+conversation.revision,role:'assistant',content:'La entrega queda bloqueada; ningún envío realizado.',references:{read_events:[{kind:'delivery_tool',decision:'ALLOW',executed:true,delivery_review:{review_id:'review_1',decision:'bloqueada',errors:[],missing:[],pending:['Falta revisión de contenido.'],send_executed:false}}]}}]}
     return response({agent_id:'reviewer',source:'ollama',provider_id:'ollama-cloud',assistant_message:'Bloqueada.',conversation})
   }
   return response({models:[],proposals:[],templates:[]})
 }))
 render(<AgentChat cognitiveMode="baseline" onNavigate={()=>{}} onOpenProviderSettings={()=>{}} onOpenCognitionSettings={()=>{}}/>)
 await screen.findByRole('region',{name:assistant.id});await act(async()=>{})
 await openDelegatedChild('Revisor fixture');await act(async()=>{})
 fireEvent.click(screen.getByText(t('agentTools.workspace')))
 fireEvent.change(await screen.findByLabelText(t('agentTools.work')),{target:{value:run.work_id}})
 fireEvent.change(screen.getByLabelText(t('agentTools.contact')),{target:{value:'contact_fixture'}})
 fireEvent.click(screen.getByLabelText(t('agentTools.scopeGrant')))
 fireEvent.click(screen.getByLabelText(t('agentTools.allowDraft')))
 const send=()=>{fireEvent.change(screen.getByPlaceholderText('Escribe a Revisor fixture.'),{target:{value:'Revisa el resultado seleccionado.'}});fireEvent.click(screen.getByRole('button',{name:'Enviar'}))}
 send();await screen.findByText(t('agentTools.blocked'))
 const grant=calls.find(c=>c.path==='/api/document-tools/authorizations')!
 expect(grant.body).toMatchObject({owner_id:'reviewer',conversation_id:'conv-review',revision:7,root:run.source_root,confirmed:true,
   review_work_id:run.work_id,review_candidate_id:run.candidate_id,review_scope_sha256:run.scope_sha256,contact_id:'contact_fixture',allow_draft:true})
 expect((screen.getByLabelText(t('agentTools.scopeGrant')) as HTMLInputElement).checked).toBe(false)
 expect((screen.getByLabelText(t('agentTools.allowDraft')) as HTMLInputElement).checked).toBe(false)
 send();await waitFor(()=>expect(calls.filter(c=>c.path==='/api/agents/reviewer/chat')).toHaveLength(2))
 expect(calls.filter(c=>c.path==='/api/agents/reviewer/chat')[1].body.document_authorization_id).toBeUndefined()
 expect(calls.filter(c=>c.path==='/api/document-tools/authorizations')).toHaveLength(1)
 expect(calls.some(c=>c.path.endsWith('/execute')||c.path.includes('/confirm'))).toBe(false)
 // A consent checked in one conversation must not authorize another conversation.
 await waitFor(()=>expect((screen.getByLabelText(t('agentTools.scopeGrant')) as HTMLInputElement).disabled).toBe(false))
 fireEvent.click(screen.getByLabelText(t('agentTools.scopeGrant')))
 fireEvent.click(screen.getByLabelText(t('agentTools.allowDraft')))
 fireEvent.click(screen.getByText(/Conversaciones y agentes/))
 fireEvent.click(await screen.findByRole('button',{name:/conv-other/}))
 await waitFor(()=>expect((screen.getByLabelText(t('agentTools.scopeGrant')) as HTMLInputElement).checked).toBe(false))
 expect((screen.getByLabelText(t('agentTools.allowDraft')) as HTMLInputElement).checked).toBe(false)
})
