// @vitest-environment jsdom
import React from 'react'
import {afterEach, beforeEach, expect, it, vi} from 'vitest'
import {act, cleanup, fireEvent, render, screen, waitFor} from '@testing-library/react'
import AgentChat from '../../src/components/AgentChat'
import {resetLocaleForTests,setLocale} from '../../src/i18n'
import {conversationButton} from '../helpers/conversation-library'
vi.mock('../../src/components/AgentDelegation',()=>({default:({onOpenChild}:any)=><button onClick={()=>onOpenChild({agentId:'agent-a',conversationId:'child'})}>Abrir hijo de prueba</button>}))
beforeEach(()=>{localStorage.clear();resetLocaleForTests();setLocale('es');HTMLElement.prototype.scrollIntoView=vi.fn()})
afterEach(()=>{cleanup();vi.unstubAllGlobals()})
const reply=(x:any)=>({ok:true,status:200,json:async()=>x})
it('does not open a late delegated child after switching back to the assistant',async()=>{
 let finish:((v:any)=>void)|undefined
 const assistant={id:'parent',owner_kind:'assistant',owner_id:'app-assistant',status:'active',title:'Conversación principal',revision:0,messages:[{id:'m1',role:'assistant',content:'Delegación sintética',references:{agent_delegation:{proposal_id:'p1'}}}]}
 const child={id:'child',owner_kind:'agent',owner_id:'agent-a',status:'active',title:'Hijo',revision:0,messages:[{id:'m2',role:'assistant',content:'CONTENIDO HIJO TARDÍO'}]}
 vi.stubGlobal('fetch',vi.fn(async(url:string)=>{
  if(url==='/api/agents/list')return reply({agents:[{id:'agent-a',config:{name:'Agente A',type:'tool',tools:[],system_prompt:'test'},created_at:'2026-10-24'}]})
  if(url==='/api/providers/selection')return reply({provider_id:null,model_id:null})
  if(url==='/api/project-folders/v1/active')return reply({project_id:'project-a',title:'Proyecto A',scope:'project'})
  if(url.startsWith('/api/conversations?')){const q=new URLSearchParams(url.split('?')[1]);return reply({conversations:q.get('owner_kind')==='agent'?[]:[assistant]})}
  if(url==='/api/conversations/parent')return reply(assistant)
  if(url==='/api/conversations/child')return await new Promise(r=>{finish=r})
  return reply({models:[],proposals:[]})
 }))
 render(<AgentChat historySelection="explicit" workspaceScopeVersion={0} cognitiveMode="baseline" onNavigate={()=>{}} onOpenProviderSettings={()=>{}} onOpenCognitionSettings={()=>{}} />)
 await screen.findByText('Conversación principal');fireEvent.click(conversationButton(document,'Conversación principal'));fireEvent.click(await screen.findByRole('button',{name:'Abrir hijo de prueba'}));await waitFor(()=>expect(finish).toBeDefined());fireEvent.click(screen.getByRole('button',{name:'Orquestador BAGO5'}));await act(async()=>{finish!(reply(child));await Promise.resolve()});expect(screen.queryByText('CONTENIDO HIJO TARDÍO')).toBeNull()
})

it('does not open a late delegated child after switching projects',async()=>{
 let finish:((v:any)=>void)|undefined
 const assistant={id:'parent',owner_kind:'assistant',owner_id:'app-assistant',status:'active',title:'Conversación principal',revision:0,messages:[{id:'m1',role:'assistant',content:'Delegación sintética',references:{agent_delegation:{proposal_id:'p1'}}}]}
 const child={id:'child',owner_kind:'agent',owner_id:'agent-a',status:'active',title:'Hijo',revision:0,messages:[{id:'m2',role:'assistant',content:'CONTENIDO HIJO TARDÍO'}]}
 vi.stubGlobal('fetch',vi.fn(async(url:string)=>{
  if(url==='/api/agents/list')return reply({agents:[{id:'agent-a',config:{name:'Agente A',type:'tool',tools:[],system_prompt:'test'},created_at:'2026-10-24'}]})
  if(url==='/api/providers/selection')return reply({provider_id:null,model_id:null})
  if(url==='/api/project-folders/v1/active')return reply({project_id:'project-a',title:'Proyecto A',scope:'project'})
  if(url.startsWith('/api/conversations?')){const q=new URLSearchParams(url.split('?')[1]);return reply({conversations:q.get('owner_kind')==='agent'?[]:[assistant]})}
  if(url==='/api/conversations/parent')return reply(assistant)
  if(url==='/api/conversations/child')return await new Promise(r=>{finish=r})
  return reply({models:[],proposals:[]})
 }))
 const view=render(<AgentChat historySelection="explicit" workspaceScopeVersion={0} cognitiveMode="baseline" onNavigate={()=>{}} onOpenProviderSettings={()=>{}} onOpenCognitionSettings={()=>{}} />)
 await screen.findByText('Conversación principal');fireEvent.click(conversationButton(document,'Conversación principal'));fireEvent.click(await screen.findByRole('button',{name:'Abrir hijo de prueba'}));await waitFor(()=>expect(finish).toBeDefined());view.rerender(<AgentChat historySelection="explicit" workspaceScopeVersion={1} cognitiveMode="baseline" onNavigate={()=>{}} onOpenProviderSettings={()=>{}} onOpenCognitionSettings={()=>{}} />);await act(async()=>{finish!(reply(child));await Promise.resolve()});expect(screen.queryByText('CONTENIDO HIJO TARDÍO')).toBeNull()
})

it('ignores a late failed detail after switching owners',async()=>{
 let failOld:((v:any)=>void)|undefined
 const a={id:'old-parent',owner_kind:'assistant',owner_id:'app-assistant',status:'active',title:'Principal anterior',revision:0,messages:[]}
 const b={id:'new-agent',owner_kind:'agent',owner_id:'agent-a',status:'active',title:'Agente actual',revision:0,messages:[{id:'m',role:'assistant',content:'MENSAJE CORRECTO'}]}
 vi.stubGlobal('fetch',vi.fn(async(url:string)=>{
  if(url==='/api/agents/list')return reply({agents:[{id:'agent-a',config:{name:'Agente A',type:'tool',tools:[],system_prompt:'test'},created_at:'2026-10-24'}]})
  if(url==='/api/providers/selection')return reply({provider_id:null,model_id:null})
  if(url==='/api/project-folders/v1/active')return reply({project_id:'project-a',title:'Proyecto A',scope:'project'})
  if(url.startsWith('/api/conversations?')){const q=new URLSearchParams(url.split('?')[1]);return reply({conversations:q.get('owner_kind')==='agent'?[b]:[a]})}
  if(url==='/api/conversations/old-parent')return await new Promise(r=>{failOld=r})
  if(url==='/api/conversations/new-agent')return reply(b)
  return reply({models:[],proposals:[]})
 }))
 render(<AgentChat historySelection="latest" workspaceScopeVersion={0} cognitiveMode="baseline" onNavigate={()=>{}} onOpenProviderSettings={()=>{}} onOpenCognitionSettings={()=>{}} />)
 await waitFor(()=>expect(failOld).toBeDefined());fireEvent.click(screen.getByRole('button',{name:'Agente A'}));await screen.findByText('MENSAJE CORRECTO');await act(async()=>{failOld!({ok:false,status:404,json:async()=>({})});await Promise.resolve()});expect(screen.getByText('MENSAJE CORRECTO')).toBeTruthy()
})

it('opens the delegated child when the owner and project remain unchanged',async()=>{
 let finish:((v:any)=>void)|undefined
 const assistant={id:'parent',owner_kind:'assistant',owner_id:'app-assistant',status:'active',title:'Conversación principal',revision:0,messages:[{id:'m1',role:'assistant',content:'Delegación sintética',references:{agent_delegation:{proposal_id:'p1'}}}]}
 const child={id:'child',owner_kind:'agent',owner_id:'agent-a',status:'active',title:'Hijo',revision:0,messages:[{id:'m2',role:'assistant',content:'CONTENIDO HIJO TARDÍO'}]}
 vi.stubGlobal('fetch',vi.fn(async(url:string)=>{
  if(url==='/api/agents/list')return reply({agents:[{id:'agent-a',config:{name:'Agente A',type:'tool',tools:[],system_prompt:'test'},created_at:'2026-10-24'}]})
  if(url==='/api/providers/selection')return reply({provider_id:null,model_id:null})
  if(url==='/api/project-folders/v1/active')return reply({project_id:'project-a',title:'Proyecto A',scope:'project'})
  if(url.startsWith('/api/conversations?')){const q=new URLSearchParams(url.split('?')[1]);return reply({conversations:q.get('owner_kind')==='agent'?[]:[assistant]})}
  if(url==='/api/conversations/parent')return reply(assistant)
  if(url==='/api/conversations/child')return await new Promise(r=>{finish=r})
  return reply({models:[],proposals:[]})
 }))
 render(<AgentChat historySelection="explicit" workspaceScopeVersion={0} cognitiveMode="baseline" onNavigate={()=>{}} onOpenProviderSettings={()=>{}} onOpenCognitionSettings={()=>{}} />)
 await screen.findByText('Conversación principal');fireEvent.click(conversationButton(document,'Conversación principal'));fireEvent.click(await screen.findByRole('button',{name:'Abrir hijo de prueba'}));await waitFor(()=>expect(finish).toBeDefined());await act(async()=>{finish!(reply(child));await Promise.resolve()});expect(screen.getByText('CONTENIDO HIJO TARDÍO')).toBeTruthy()
})


it('does not replace a newer manual conversation of the same agent',async()=>{
 let finish:((v:any)=>void)|undefined
 const assistant={id:'parent',owner_kind:'assistant',owner_id:'app-assistant',status:'active',title:'Conversación principal',revision:0,messages:[{id:'m1',role:'assistant',content:'Delegación sintética',references:{agent_delegation:{proposal_id:'p1'}}}]}
 const child={id:'child',owner_kind:'agent',owner_id:'agent-a',status:'active',title:'Hijo',revision:0,messages:[{id:'m2',role:'assistant',content:'CONTENIDO HIJO TARDÍO'}]}
 vi.stubGlobal('fetch',vi.fn(async(url:string)=>{
  if(url==='/api/agents/list')return reply({agents:[{id:'agent-a',config:{name:'Agente A',type:'tool',tools:[],system_prompt:'test'},created_at:'2026-10-24'}]})
  if(url==='/api/providers/selection')return reply({provider_id:null,model_id:null})
  if(url==='/api/project-folders/v1/active')return reply({project_id:'project-a',title:'Proyecto A',scope:'project'})
  if(url.startsWith('/api/conversations?')){const q=new URLSearchParams(url.split('?')[1]);return reply({conversations:q.get('owner_kind')==='agent'?[{id:'other',owner_kind:'agent',owner_id:'agent-a',status:'active',title:'Conversación elegida',revision:0}]:[assistant]})}
  if(url==='/api/conversations/parent')return reply(assistant)
  if(url==='/api/conversations/other')return reply({id:'other',owner_kind:'agent',owner_id:'agent-a',status:'active',title:'Conversación elegida',revision:0,messages:[{id:'m3',role:'assistant',content:'CONTENIDO ELEGIDO'}]})
  if(url==='/api/conversations/child')return await new Promise(r=>{finish=r})
  return reply({models:[],proposals:[]})
 }))
 render(<AgentChat historySelection="explicit" workspaceScopeVersion={0} cognitiveMode="baseline" onNavigate={()=>{}} onOpenProviderSettings={()=>{}} onOpenCognitionSettings={()=>{}} />)
 await screen.findByText('Conversación principal');fireEvent.click(conversationButton(document,'Conversación principal'));fireEvent.click(await screen.findByRole('button',{name:'Abrir hijo de prueba'}));await waitFor(()=>expect(finish).toBeDefined());await screen.findByText('Conversación elegida');fireEvent.click(conversationButton(document,'Conversación elegida'));await screen.findByText('CONTENIDO ELEGIDO');await act(async()=>{finish!(reply(child));await Promise.resolve()});expect(screen.queryByText('CONTENIDO HIJO TARDÍO')).toBeNull();expect(screen.getByText('CONTENIDO ELEGIDO')).toBeTruthy()
})
