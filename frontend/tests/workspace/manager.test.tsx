// @vitest-environment jsdom
import React from 'react'
import {afterEach,beforeEach,expect,it,vi} from 'vitest'
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import WorkspaceManager from '../../src/components/WorkspaceManager'
import AgentChat from '../../src/components/AgentChat'
import {resetLocaleForTests,setLocale} from '../../src/i18n'
import {folderFixture,reply,workspace} from '../project-folders/fixtures'
beforeEach(()=>{localStorage.clear();resetLocaleForTests();setLocale('es')})
afterEach(()=>{cleanup();vi.unstubAllGlobals()})
it('reports unavailable configuration without offering an executable mutation or alternative root',async()=>{
 const f=folderFixture({route:url=>url==='/api/project-folders/v1/config'?reply({error:{code:'unavailable',message:'Fallo sintético'}},503):undefined});render(<WorkspaceManager/>);expect(await screen.findByRole('alert')).toBeTruthy();expect((screen.getByRole('button',{name:'Usar carpeta'}) as HTMLButtonElement).disabled).toBe(true);expect(f.mutations()).toEqual([])
})
it('chat proposal prefills only and explicit child selection needs exact plan review and consent before create/apply',async()=>{
 const f=folderFixture({root:'D:/isolated'});render(<WorkspaceManager inline proposal={{intent:'create',name:'fixture'}}/>);await waitFor(()=>expect((screen.getByRole('button',{name:'Usar carpeta'}) as HTMLButtonElement).disabled).toBe(false));expect((screen.getByLabelText('Nombre de carpeta') as HTMLInputElement).value).toBe('fixture');expect(f.mutations()).toHaveLength(0)
 fireEvent.click(screen.getByLabelText('Crear una carpeta hija'));fireEvent.change(screen.getByLabelText('Título del proyecto'),{target:{value:'FICTICIO'}});fireEvent.click(screen.getByRole('button',{name:'Usar carpeta'}));await screen.findByRole('dialog');expect(f.mutations().map(c=>c.url)).toEqual(['/api/project-folders/v1/plans']);expect((screen.getByRole('button',{name:'Aceptar plan y ejecutar'}) as HTMLButtonElement).disabled).toBe(false);expect(screen.queryByRole('checkbox')).toBeNull();expect(f.getRoot()).toBe('D:/isolated')
 fireEvent.click(screen.getByRole('button',{name:'Aceptar plan y ejecutar'}));await screen.findByText(/El servicio confirmó la carpeta activa/);expect(f.getRoot()).toBe('D:/isolated/fixture');expect(f.mutations()[1].body).toEqual({plan_sha256:'1'.repeat(64),confirmed:true})
})
it('keeps server errors visible instead of claiming success',async()=>{
 folderFixture({route:()=>reply({error:{code:'workspace_unavailable',message:'Fallo sintético'}},503)});render(<WorkspaceManager/>);expect(await screen.findByRole('alert')).toBeTruthy();expect(screen.queryByText(/El servicio confirmó la carpeta activa/)).toBeNull()
})
it('AgentChat restores a persisted structured proposal into the real inline manager without using its file path as folder authority',async()=>{
 HTMLElement.prototype.scrollIntoView=()=>{}
 const conversation={id:'conv-fixture',owner_kind:'assistant',owner_id:'app-assistant',title:'Fixture',status:'active',revision:2,updated_at:'2026-10-23',messages:[{id:'a1',role:'assistant',content:'Revisa el proyecto',references:{workspace_proposal:{intent:'create',name:'chat-demo',path:'notes/relative.txt'}}}]}
 const f=folderFixture({route:url=>url.startsWith('/api/conversations?')?reply({conversations:[conversation]}):url==='/api/conversations/conv-fixture'?reply(conversation):url==='/api/agents/list'?reply({agents:[]}):url==='/api/providers/selection'?reply({provider_id:null,model_id:null}):url.startsWith('/api/providers/')?reply({models:[]}):undefined})
 render(<AgentChat cognitiveMode="baseline" onNavigate={()=>{}} onOpenProviderSettings={()=>{}} onOpenCognitionSettings={()=>{}}/>);expect(await screen.findByText(/Propuesta del chat · pendiente de tu revisión/)).toBeTruthy();expect((await screen.findByLabelText('Nombre de carpeta') as HTMLInputElement).value).toBe('chat-demo');expect((screen.getByLabelText('Carpeta del proyecto o padre elegido') as HTMLInputElement).value).not.toBe('notes/relative.txt');expect(screen.getByRole('button',{name:'Usar carpeta'})).toBeTruthy();expect(f.mutations()).toEqual([])
})
it('renders the plain Git status returned after confirmed initialization through the aggregate legacy workspace route',async()=>{
 const w=workspace('C:/isolated/fixture','fixture','FICTICIO');folderFixture({workspaces:[w]});render(<WorkspaceManager/>);await screen.findByRole('option',{name:'FICTICIO · fixture'});fireEvent.change(screen.getByLabelText('Proyecto gestionado'),{target:{value:w.id}});fireEvent.click(screen.getByRole('tab',{name:'Archivos'}));fireEvent.click(await screen.findByRole('tab',{name:'Git y GitHub'}));await waitFor(()=>expect((screen.getByText('Inicializar Git') as HTMLButtonElement).disabled).toBe(false));fireEvent.click(screen.getByText('Inicializar Git'));fireEvent.click(screen.getByText('Aceptar plan y ejecutar'));expect(await screen.findByText(/Rama main/)).toBeTruthy();expect(screen.getByText('Sin cambios')).toBeTruthy()
})
