// @vitest-environment jsdom
import React from 'react'
import {afterEach, expect, it, vi} from 'vitest'
import {cleanup, fireEvent, render, screen} from '@testing-library/react'
import AgentChat from '../../src/components/AgentChat'
const response=(body:unknown)=>({ok:true,status:200,json:async()=>body})
afterEach(()=>{cleanup();vi.unstubAllGlobals()})
it('restores communication identity and Workspace proposal together without executing either action',async()=>{
 HTMLElement.prototype.scrollIntoView=()=>{}
 const contact={id:'contact-cross',name:'FICTICIO',phone:'+34600000001'}
 const draft={id:'draft-cross',revision:'a'.repeat(64),contact_id:contact.id,recipient:contact,text:'Resultado ficticio',attachments:[],schedule:{kind:'now',timezone:'Europe/Madrid',at:null,time:null,weekdays:[]},state:'draft',next_run_at:null,created_at:'',updated_at:'',conversation_id:'conv-cross',last_error:null}
 const conversation={id:'conv-cross',owner_kind:'assistant',owner_id:'app-assistant',title:'Cruce ficticio',status:'active',revision:2,updated_at:'2026-10-23',messages:[{id:'message-cross',role:'assistant',content:'Revisión combinada',references:{communication_draft_id:draft.id,communication_draft:draft,workspace_proposal:{intent:'create',name:'cross-project'}}}]}
 const mutations:string[]=[];const open=vi.fn()
 vi.stubGlobal('fetch',vi.fn(async(path:string,init?:RequestInit)=>{
  if(init?.method&&init.method!=='GET')mutations.push(path)
  if(path.startsWith('/api/conversations?'))return response({conversations:[conversation]})
  if(path==='/api/conversations/conv-cross')return response(conversation)
  if(path==='/api/agents/list')return response({agents:[]})
  if(path==='/api/providers/selection')return response({provider_id:null,model_id:null})
  if(path==='/api/communications/contacts')return response({contacts:[contact]})
  if(path==='/api/communications/drafts')return response({drafts:[draft]})
  if(path==='/api/communications/runs')return response({runs:[]})
  if(path==='/api/communications/drafts/draft-cross')return response(draft)
  if(path==='/api/workspaces/v1/config')return response({configured:true,parent:'C:/FICTICIO'})
  if(path==='/api/workspaces/v1/workspaces')return response({workspaces:[]})
  return response({models:[]})
 }))
 render(<AgentChat cognitiveMode="baseline" onNavigate={()=>{}} onOpenCommunication={open} onOpenProviderSettings={()=>{}} onOpenCognitionSettings={()=>{}} />)
 expect(await screen.findByDisplayValue('Resultado ficticio')).toBeTruthy()
 expect((await screen.findByLabelText('Nombre de carpeta') as HTMLInputElement).value).toBe('cross-project')
 expect(mutations).toEqual([])
 expect((screen.getByRole('button',{name:'Confirmar y enviar ahora'}) as HTMLButtonElement).disabled).toBe(true)
 fireEvent.click(screen.getByRole('button',{name:'Abrir pantalla completa'}))
 expect(open).toHaveBeenCalledExactlyOnceWith('draft-cross')
 expect(mutations).toEqual([])
})
