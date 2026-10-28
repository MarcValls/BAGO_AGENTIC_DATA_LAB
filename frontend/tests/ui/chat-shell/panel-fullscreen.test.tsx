// @vitest-environment jsdom
import React from 'react'
import {beforeEach,afterEach,expect,it,vi} from 'vitest'
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import {readFileSync} from 'node:fs'
import postcss from 'postcss'
import AgentChat from '../../../src/components/AgentChat'
import {resetLocaleForTests,setLocale} from '../../../src/i18n'
import {openDelegatedChild,withPersistedDelegation} from '../../helpers/delegated-agent-chat'
beforeEach(()=>{localStorage.clear();resetLocaleForTests();setLocale('es');HTMLElement.prototype.scrollIntoView=vi.fn()})
afterEach(()=>{cleanup();vi.unstubAllGlobals();vi.restoreAllMocks()})
function fixture(options:{failure?:boolean;detailFailure?:boolean;foreign?:boolean;defer?:boolean}={}){
 const calls:Array<{url:string;method:string;body?:string}>=[]
 let release:(value:unknown)=>void=()=>{};let created=false;let createdOwner:'assistant'|'agent'='assistant';let pendingOwner:'assistant'|'agent'='assistant'
 const agent={id:'agent-one',config:{name:'Agente fixture',type:'rag',model_id:'fixture-model',description:'Synthetic fixture'}}
 const conversation=(id:string,owner='assistant')=>({id,owner_kind:owner,owner_id:owner==='agent'?'agent-one':'app-assistant',title:id,status:'active',revision:1,updated_at:'2026-10-23T12:00:00Z',messages:id.startsWith('old')?[{id:'old-msg',role:'user',content:'PREVIOUS_CONTENT'}]:[]})
 const child=conversation('old-agent-chat','agent')
 const parent=withPersistedDelegation(conversation('old-chat'),agent,child.id)
 const response=(body:unknown,ok=true)=>({ok,status:ok?200:503,json:async()=>body})
 vi.stubGlobal('fetch',vi.fn(async(input:string,init?:RequestInit)=>{
  const url=String(input);calls.push({url,method:init?.method??'GET',body:init?.body as string})
  if(url==='/api/conversations'&&init?.method==='POST'){
   const owner=JSON.parse(init.body as string).owner_kind
   if(options.defer){pendingOwner=owner;return await new Promise(resolve=>{release=resolve})}
   if(options.failure)return response({detail:{message:'CREATE_FAILED_DIAGNOSTIC'}},false)
   created=true;createdOwner=owner;return response(conversation('new-chat',owner))
  }
  if(url==='/api/agents/list')return response({agents:[agent]})
  if(url==='/api/providers/chat-models')return response({models:[]})
  if(url.startsWith('/api/conversations?')){const owner=new URLSearchParams(url.split('?')[1]).get('owner_kind')!;return response({conversations:owner==='agent'?(created&&createdOwner==='agent'?[conversation('new-chat','agent')]:[child]):(created&&createdOwner==='assistant'?[conversation('new-chat','assistant')]:[parent])})}
  if(url.startsWith('/api/conversations/')){
   const id=decodeURIComponent(url.split('/').pop()!)
   if(id==='new-chat'&&options.detailFailure)return response({detail:{message:'DETAIL_FAILED_DIAGNOSTIC'}},false)
   if(id===parent.id)return response(parent)
   if(id===child.id)return response(child)
   const owner=id==='new-chat'?createdOwner:'assistant'
   return response(conversation(id,options.foreign&&id==='new-chat'?'agent':owner))
  }
  if(url.startsWith('/api/capabilities/proposals?'))return response({proposals:[]})
  return response(null)
 }))
 const view=render(<AgentChat cognitiveMode="baseline" onNavigate={()=>{}}/>);
 const panel=view.container.querySelector('details.chat-agent-panel') as HTMLDetailsElement
 const composer=screen.getByRole('textbox',{name:'Mensaje al asistente o agente seleccionado'}) as HTMLTextAreaElement
 return {view,panel,composer,calls,release:()=>release(response(conversation('new-chat',pendingOwner)))}
}
function open(panel:HTMLDetailsElement){if(!panel.open)fireEvent.click(panel.querySelector('summary')!)}
it('full area rules hide mounted siblings including composer from layout and keyboard while native details is open',()=>{
 const css=readFileSync('src/components/AgentChat.css','utf8'),rules:Record<string,Record<string,string>>={}
 postcss.parse(css).walkRules(rule=>{const values=rules[rule.selector]??={};rule.walkDecls(d=>{values[d.prop]=d.value})})
 expect(rules['.control-chat .control-chat-window:has(> .window-panel-content > .chat-agent-panel-slot > .chat-agent-panel[open]) > .window-panel-content > :not(.chat-agent-panel-slot)']?.display).toBe('none')
 expect(rules['.control-chat .chat-agent-panel-slot:has(.chat-agent-panel[open])']['max-height']).toBe('none')
})
it.each(['assistant','agent'])('New closes library, clears the new composer and focuses it after verified creation for %s',async owner=>{
 const f=fixture();await screen.findByText('PREVIOUS_CONTENT')
 if(owner==='agent'){await openDelegatedChild('Agente fixture');await waitFor(()=>expect(f.calls.filter(c=>c.url.includes('owner_kind=agent')).length).toBeGreaterThan(0))}
 fireEvent.change(f.composer,{target:{value:'UNSENT_DRAFT'}});open(f.panel)
 fireEvent.click(screen.getByRole('button',{name:'Nueva',exact:true}))
 await waitFor(()=>expect(f.panel.open).toBe(false))
 expect(f.composer.value).toBe('');expect(document.activeElement).toBe(f.composer)
 expect(f.calls.filter(c=>c.method==='POST')).toHaveLength(1)
 expect(JSON.parse(f.calls.find(c=>c.method==='POST')!.body!)).toEqual({owner_kind:owner,owner_id:owner==='agent'?'agent-one':'app-assistant'})
 expect(f.calls.every(c=>c.method==='GET'||c.url==='/api/conversations')).toBe(true)
 expect(f.view.container.querySelector('.chat-context-controls')).not.toBeNull()
})
it.each([{failure:true},{detailFailure:true},{foreign:true}])('creation failure/invalid identity keeps library, prior content and draft: %j',async options=>{
 const f=fixture(options);await screen.findByText('PREVIOUS_CONTENT');fireEvent.change(f.composer,{target:{value:'KEEP_DRAFT'}});open(f.panel)
 fireEvent.click(screen.getByRole('button',{name:'Nueva',exact:true}))
 await screen.findByRole('alert')
 expect(f.panel.open).toBe(true);expect(f.composer.value).toBe('KEEP_DRAFT');expect(screen.getByText('PREVIOUS_CONTENT')).not.toBeNull()
})
it('manual close restores the same mounted composer and its draft without network mutation',async()=>{
 const f=fixture();await screen.findByText('PREVIOUS_CONTENT');fireEvent.change(f.composer,{target:{value:'KEEP_DRAFT'}});open(f.panel);fireEvent.click(f.panel.querySelector('summary')!)
 expect(f.panel.open).toBe(false);expect(f.composer.isConnected).toBe(true);expect(f.composer.value).toBe('KEEP_DRAFT');expect(f.calls.every(c=>c.method==='GET')).toBe(true)
})
it('ignores late agent conversation creation after switching back to BAGO5 and prevents duplicate New while pending',async()=>{
 const f=fixture({defer:true});await screen.findByText('PREVIOUS_CONTENT');await openDelegatedChild('Agente fixture');open(f.panel)
 const create=screen.getByRole('button',{name:'Nueva',exact:true}) as HTMLButtonElement;fireEvent.click(create)
 expect(create.disabled).toBe(true);fireEvent.click(create);expect(f.calls.filter(c=>c.method==='POST')).toHaveLength(1)
 fireEvent.click(screen.getByRole('button',{name:'Orquestador BAGO5'}));await waitFor(()=>expect(f.calls.some(c=>c.url.includes('owner_kind=assistant'))).toBe(true))
 f.release();await waitFor(()=>expect((screen.getByRole('button',{name:'Nueva',exact:true}) as HTMLButtonElement).disabled).toBe(false));expect(f.panel.open).toBe(true)
 expect(f.composer.value).toBe('');expect(f.calls.some(c=>c.url==='/api/conversations/new-chat')).toBe(false)
})
