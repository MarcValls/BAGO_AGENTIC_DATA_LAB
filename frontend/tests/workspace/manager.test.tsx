// @vitest-environment jsdom
import React from 'react'
import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import WorkspaceManager from '../../src/components/WorkspaceManager'
import AgentChat from '../../src/components/AgentChat'
afterEach(()=>{cleanup();vi.unstubAllGlobals()})
const response=(body:unknown,status=200)=>({ok:status<400,status,json:async()=>body})

it('reports missing configuration without offering mutations',async()=>{
 vi.stubGlobal('fetch',vi.fn(async()=>response({configured:false,parent:null})))
 render(<WorkspaceManager />)
 expect(await screen.findByText('Carpeta padre sin configurar')).toBeTruthy()
 expect(screen.queryByText('Revisar creación')).toBeNull()
})
it('chat proposal prefills only and requires explicit review before create',async()=>{
 const calls:any[]=[];let created=false
 const w={id:'workspace_fixture',title:'FICTICIO',name:'fixture',root:'C:/isolated/fixture',context_files:[]}
 vi.stubGlobal('fetch',vi.fn(async(path:string,init?:RequestInit)=>{
  if(init){calls.push(JSON.parse(String(init.body)));if(path.endsWith('/workspaces')){created=true;return response(w,201)};return response(calls.at(-1).operation==='list_files'?{files:[],excluded:[]}:{items:[]})}
  return response(path.endsWith('/config')?{configured:true,parent:'C:/isolated'}:{workspaces:created?[w]:[]})
 }))
 render(<WorkspaceManager inline proposal={{intent:'create',name:'fixture'}} />)
 await screen.findByText(/Raíz permitida/)
 expect((screen.getByLabelText('Nombre de carpeta') as HTMLInputElement).value).toBe('fixture')
 fireEvent.change(screen.getByLabelText('Título del proyecto'),{target:{value:'FICTICIO'}})
 fireEvent.click(screen.getByText('Revisar creación'))
 expect(calls).toHaveLength(0)
 expect((screen.getByText('Confirmar y ejecutar') as HTMLButtonElement).disabled).toBe(true)
 fireEvent.click(screen.getByLabelText('He revisado el alcance y confirmo esta operación'))
 fireEvent.click(screen.getByText('Confirmar y ejecutar'))
 await waitFor(()=>expect(calls.some(c=>c.name==='fixture'&&c.confirmed)).toBe(true))
 expect(await screen.findByText('Operación completada por el servicio. Resultado actualizado.')).toBeTruthy()
})
it('keeps server errors visible instead of claiming success',async()=>{
 vi.stubGlobal('fetch',vi.fn(async()=>response({error:{code:'workspace_unavailable',message:'Fallo sintético'}},503)))
 render(<WorkspaceManager />)
 expect(await screen.findByRole('alert')).toBeTruthy()
 expect(screen.queryByText('Operación completada por el servicio. Resultado actualizado.')).toBeNull()
})
it('AgentChat restores a persisted structured proposal into the real inline manager',async()=>{
 HTMLElement.prototype.scrollIntoView=()=>{}
 const conversation={id:'conv-fixture',owner_kind:'assistant',owner_id:'app-assistant',title:'Fixture',status:'active',revision:2,updated_at:'2026-10-23',messages:[{id:'a1',role:'assistant',content:'Revisa el proyecto',references:{workspace_proposal:{intent:'create',name:'chat-demo'}}}]}
 vi.stubGlobal('fetch',vi.fn(async(path:string)=>{
  if(path==='/api/workspaces/v1/config')return response({configured:true,parent:'C:/isolated'})
  if(path==='/api/workspaces/v1/workspaces')return response({workspaces:[]})
  if(path.startsWith('/api/conversations?'))return response({conversations:[conversation]})
  if(path==='/api/conversations/conv-fixture')return response(conversation)
  if(path==='/api/agents/list')return response({agents:[]})
  if(path==='/api/providers/selection')return response({provider_id:null,model_id:null})
  return response({models:[]})
 }))
 render(<AgentChat cognitiveMode="baseline" onNavigate={()=>{}} onOpenProviderSettings={()=>{}} onOpenCognitionSettings={()=>{}} />)
 expect(await screen.findByText(/Propuesta del chat · pendiente de tu revisión/)).toBeTruthy()
 expect((await screen.findByLabelText('Nombre de carpeta') as HTMLInputElement).value).toBe('chat-demo')
 expect(screen.getByText('Revisar creación')).toBeTruthy()
})
it('renders the plain Git status returned after confirmed initialization',async()=>{
 const w={id:'workspace_fixture',title:'FICTICIO',name:'fixture',root:'C:/isolated/fixture',context_files:[]}
 vi.stubGlobal('fetch',vi.fn(async(path:string,init?:RequestInit)=>{
  if(init){const body=JSON.parse(String(init.body));if(body.operation==='list_files')return response({files:[],excluded:[]});if(body.operation==='trash_list')return response({items:[]});if(body.operation==='git_init')return response({head:null,branch:'main',status:[],conflicts:[]})}
  return response(path.endsWith('/config')?{configured:true,parent:'C:/isolated'}:{workspaces:[w]})
 }))
 render(<WorkspaceManager />)
 await screen.findByText(/Raíz permitida/)
 fireEvent.change(screen.getByLabelText('Proyecto gestionado'),{target:{value:w.id}})
 fireEvent.click(screen.getByRole('tab',{name:'Archivos'}))
 fireEvent.click(await screen.findByRole('tab',{name:'Git y GitHub'}))
 await waitFor(()=>expect((screen.getByText('Inicializar Git') as HTMLButtonElement).disabled).toBe(false))
 fireEvent.click(screen.getByText('Inicializar Git'));fireEvent.click(screen.getByLabelText('He revisado el alcance y confirmo esta operación'));fireEvent.click(screen.getByText('Confirmar y ejecutar'))
 expect(await screen.findByText(/Rama main/)).toBeTruthy()
 expect(screen.getByText('Sin cambios')).toBeTruthy()
})
