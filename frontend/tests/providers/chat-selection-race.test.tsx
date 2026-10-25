// @vitest-environment jsdom
import React from 'react'
import {afterEach,beforeEach,expect,it,vi} from 'vitest'
import {act,cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import AgentChat from '../../src/components/AgentChat'
import {resetLocaleForTests,setLocale,t} from '../../src/i18n'

const response=(data:any,status=200)=>({ok:status>=200&&status<300,status,json:async()=>data})
const deferred=()=>{let resolve!:(value:any)=>void,reject!:(value:any)=>void;const promise=new Promise<any>((yes,no)=>{resolve=yes;reject=no});return {promise,resolve,reject}}
const oldSelection={provider_id:'github-copilot',model_id:'old-model'}
const selected={provider_id:'ollama-cloud',model_id:'gemma4:31b'}
const selectedValue='ollama-cloud|gemma4:31b'
beforeEach(()=>{localStorage.clear();resetLocaleForTests();setLocale('en');HTMLElement.prototype.scrollIntoView=()=>{}})
afterEach(()=>{cleanup();vi.unstubAllGlobals();vi.restoreAllMocks()})

async function setup(){
 const put=deferred(),chat=deferred(),calls:Array<{url:string;method?:string;body:any}>=[]
 let currentPut=put
 let nextSelection:ReturnType<typeof deferred>|null=null
 const conversation={id:'assistant-conv',owner_kind:'assistant',owner_id:'app-assistant',status:'active',title:'Fixture conversation',revision:0,messages:[],updated_at:'2026-10-24'}
 const agentConversation={...conversation,id:'agent-conv',owner_kind:'agent',owner_id:'fixture-agent'}
 const actor={id:'fixture-agent',config:{name:'Own model agent',type:'tool',tools:[],provider_id:'ollama-cloud',model_id:'own-agent-model',system_prompt:'Fixture'}}
 vi.stubGlobal('fetch',vi.fn(async(url:string,init?:RequestInit)=>{
   const body=init?.body?JSON.parse(String(init.body)):null
   calls.push({url,method:init?.method,body})
   if(url==='/api/agents/list')return response({agents:[actor]})
   if(url==='/api/providers/chat-models')return response({models:[
     {...oldSelection,label:'Copilot',state:'ready',chat_enabled:true},
     {...selected,label:'Ollama',state:'ready',chat_enabled:true}]})
   if(url==='/api/providers/selection'){
     if(init?.method==='PUT')return currentPut.promise
     if(nextSelection){const pending=nextSelection;nextSelection=null;return pending.promise}
     return response(oldSelection)
   }
   if(url.startsWith('/api/conversations?'))return response({conversations:[url.includes('owner_kind=agent')?agentConversation:conversation]})
   if(url==='/api/conversations/assistant-conv')return response(conversation)
   if(url==='/api/conversations/agent-conv')return response(agentConversation)
   if(url==='/api/chat/control')return chat.promise
   if(url==='/api/agents/fixture-agent/chat')return response({source:'ollama',assistant_message:'Own model response',conversation:{...agentConversation,revision:2,messages:[{id:'agent-answer',role:'assistant',content:'Own model response'}]}})
   return response({proposals:[],models:[]})
 }))
 render(<AgentChat onNavigate={()=>{}}/>)
 const picker=await screen.findByRole('combobox',{name:t('commerce.orchestrator_model')}) as HTMLSelectElement
 await waitFor(()=>expect(picker.value).toBe('github-copilot|old-model'))
 await screen.findByRole('region',{name:conversation.title})
 const input=screen.getByRole('textbox',{name:t('commerce.message_the_assistant_or_selected_agent')}) as HTMLTextAreaElement
 fireEvent.change(input,{target:{value:'Synthetic fixture message'}})
 return {put,chat,calls,picker,input,conversation,retry:()=>{currentPut=deferred();return currentPut},refresh:()=>{const value=deferred();nextSelection=value;act(()=>window.dispatchEvent(new Event('adl-model-policy-changed')));return value}}
}
const writes=(calls:Array<{method?:string}>)=>calls.filter(c=>c.method==='POST')

it('blocks Send, Enter, form submission and suggestions until the exact selection PUT is acknowledged; preserves draft and consent',async()=>{
 const f=await setup()
 fireEvent.click(screen.getByLabelText(t('commerce.allow_public_web_reading')))
 act(()=>{fireEvent.change(f.picker,{target:{value:selectedValue}});fireEvent.submit(f.input.form!)})
 expect(writes(f.calls)).toHaveLength(0)
 expect(f.input.value).toBe('Synthetic fixture message')
 expect((screen.getByLabelText(t('commerce.allow_public_web_reading')) as HTMLInputElement).checked).toBe(true)
 expect((screen.getByRole('button',{name:t('commerce.send'),exact:true}) as HTMLButtonElement).disabled).toBe(true)
 expect((screen.getByRole('button',{name:t('commerce.create_an_agent')}) as HTMLButtonElement).disabled).toBe(true)
 fireEvent.keyDown(f.input,{key:'Enter'});fireEvent.submit(f.input.form!)
 expect(writes(f.calls)).toHaveLength(0)
 fireEvent.change(f.picker,{target:{value:'github-copilot|old-model'}})
 expect(f.calls.filter(c=>c.method==='PUT')).toHaveLength(1)
 await act(async()=>f.put.resolve(response(selected)))
 expect(f.picker.value).toBe(selectedValue)
 expect((screen.getByRole('button',{name:t('commerce.send'),exact:true}) as HTMLButtonElement).disabled).toBe(false)
 // Avoid requesting web read; the checked consent above was never consumed by a blocked send.
 fireEvent.click(screen.getByLabelText(t('commerce.allow_public_web_reading')))
 fireEvent.submit(f.input.form!)
 await waitFor(()=>expect(f.calls.filter(c=>c.url==='/api/chat/control')).toHaveLength(1))
 expect(f.picker.disabled).toBe(true)
 fireEvent.change(f.picker,{target:{value:'github-copilot|old-model'}})
 expect(f.calls.filter(c=>c.method==='PUT')).toHaveLength(1)
 await act(async()=>f.chat.resolve(response({operation:'chat',conversation:{...f.conversation,revision:2,messages:[{id:'answer',role:'assistant',content:'Confirmed provider fixture'}]}})))
 await screen.findByText('Confirmed provider fixture')
 expect(f.picker.value).toBe(selectedValue)
})

it.each(['http','network','mismatch','malformed'] as const)('keeps submission blocked after %s selection failure despite a policy refresh and locale switch',async(kind)=>{
 const f=await setup()
 fireEvent.click(screen.getByLabelText(t('commerce.allow_public_web_reading')))
 fireEvent.change(f.picker,{target:{value:selectedValue}})
 await act(async()=>{
   if(kind==='network')f.put.reject(new Error('Synthetic network failure'))
   else f.put.resolve(kind==='http'?response({detail:{message:'Synthetic refusal'}},422):response(kind==='malformed'?null:{...selected,model_id:'wrong-model'}))
 })
 expect(f.picker.value).toBe('')
 const refresh=f.refresh();await act(async()=>refresh.resolve(response(oldSelection)))
 act(()=>setLocale('es'))
 fireEvent.keyDown(f.input,{key:'Enter'});fireEvent.submit(f.input.form!)
 expect(writes(f.calls)).toHaveLength(0)
 expect(f.input.value).toBe('Synthetic fixture message')
 expect((screen.getByLabelText(t('commerce.allow_public_web_reading')) as HTMLInputElement).checked).toBe(true)
 expect((screen.getByRole('button',{name:t('commerce.send'),exact:true}) as HTMLButtonElement).disabled).toBe(true)
 expect(f.picker.disabled).toBe(false) // User can explicitly choose and confirm a model again.
})

it('ignores an older selection GET finishing after the user PUT and ignores older refresh generations',async()=>{
 const f=await setup(),oldRefresh=f.refresh()
 fireEvent.change(f.picker,{target:{value:selectedValue}})
 await act(async()=>f.put.resolve(response(selected)))
 await act(async()=>oldRefresh.resolve(response(oldSelection)))
 expect(f.picker.value).toBe(selectedValue)
 const older=f.refresh(),newer=f.refresh()
 await act(async()=>newer.resolve(response(selected)))
 await act(async()=>older.resolve(response(oldSelection)))
 expect(f.picker.value).toBe(selectedValue)
 expect((screen.getByRole('button',{name:t('commerce.send'),exact:true}) as HTMLButtonElement).disabled).toBe(false)
})

it('recovers a failed selection only after a new explicit exact PUT, retaining the drafted message',async()=>{
 const f=await setup()
 fireEvent.change(f.picker,{target:{value:selectedValue}})
 await act(async()=>f.put.resolve(response({},422)))
 const retry=f.retry()
 fireEvent.change(f.picker,{target:{value:'github-copilot|old-model'}})
 fireEvent.submit(f.input.form!)
 expect(writes(f.calls)).toHaveLength(0)
 await act(async()=>retry.resolve(response(oldSelection)))
 expect(f.picker.value).toBe('github-copilot|old-model')
 expect(f.input.value).toBe('Synthetic fixture message')
 expect((screen.getByRole('button',{name:t('commerce.send'),exact:true}) as HTMLButtonElement).disabled).toBe(false)
 expect(f.calls.filter(c=>c.method==='PUT')).toHaveLength(2)
})

it('preserves an assigned agent own provider while the unrelated orchestrator selection has failed',async()=>{
 const f=await setup()
 fireEvent.change(f.picker,{target:{value:selectedValue}})
 await act(async()=>f.put.resolve(response({},422)))
 fireEvent.click(screen.getByText(/Conversations and agents/))
 fireEvent.click(await screen.findByRole('button',{name:/Own model agent/}))
 await screen.findByRole('region',{name:'Own model agent'})
 fireEvent.change(f.input,{target:{value:'Use the assigned model only'}})
 fireEvent.submit(f.input.form!)
 await screen.findByText('Own model response')
 expect(f.calls.filter(c=>c.url==='/api/agents/fixture-agent/chat')).toHaveLength(1)
 expect(f.calls.filter(c=>c.url==='/api/chat/control')).toHaveLength(0)
 expect(f.calls.filter(c=>c.method==='PUT')).toHaveLength(1)
})
