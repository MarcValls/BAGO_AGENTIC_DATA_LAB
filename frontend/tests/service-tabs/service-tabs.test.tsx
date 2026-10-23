// @vitest-environment jsdom
import React,{useState} from 'react'
import {afterEach,beforeEach,expect,it,vi} from 'vitest'
import {cleanup,fireEvent,render,screen,within,waitFor} from '@testing-library/react'
import {readFileSync} from 'node:fs'
import {resetLocaleForTests} from '../../src/i18n'
beforeEach(()=>{localStorage.clear();resetLocaleForTests()})
import ServiceTabs from '../../src/components/ServiceTabs'
import Contacts from '../../src/components/Contacts'
import Communications from '../../src/components/Communications'
import WorkspaceManager from '../../src/components/WorkspaceManager'
const response=(body:unknown)=>({ok:true,status:200,json:async()=>body})
afterEach(()=>{cleanup();vi.unstubAllGlobals()})
function Tabs(){const [value,setValue]=useState<'a'|'b'|'c'>('a');return <><ServiceTabs<'a'|'b'|'c'> id="fixture" label="Áreas" value={value} onChange={setValue} items={[{id:'a',label:'Uno'},{id:'b',label:'Dos'},{id:'c',label:'Tres'}]}/>{['a','b','c'].map(id=><section key={id} id={'fixture-panel-'+id} role="tabpanel" aria-labelledby={'fixture-tab-'+id} hidden={value!==id}>{id}</section>)}</>}
it('moves focus and selected state with arrows, wrap, Home and End while linking exact panels',()=>{
 render(<Tabs/>);const first=screen.getByRole('tab',{name:'Uno'});first.focus()
 fireEvent.keyDown(first,{key:'ArrowLeft'});expect(document.activeElement).toBe(screen.getByRole('tab',{name:'Tres'}))
 fireEvent.keyDown(document.activeElement!,{key:'ArrowRight'});expect(document.activeElement).toBe(first)
 fireEvent.keyDown(first,{key:'End'});expect(screen.getByRole('tab',{name:'Tres'}).getAttribute('aria-selected')).toBe('true')
 fireEvent.keyDown(document.activeElement!,{key:'Home'});expect(first.getAttribute('aria-selected')).toBe('true')
 for(const tab of screen.getAllByRole('tab')){const panel=document.getElementById(tab.getAttribute('aria-controls')!)!;expect(panel).toBeTruthy();expect(panel.getAttribute('aria-labelledby')).toBe(tab.id)}
 expect(screen.getAllByRole('tab').filter(t=>t.tabIndex===0)).toHaveLength(1)
})
it('preserves unsaved local-contact edits between Agenda and Google without mutation',async()=>{
 const writes:string[]=[];vi.stubGlobal('fetch',vi.fn(async(path:string,init?:RequestInit)=>{if(init?.method&&init.method!=='GET')writes.push(path);return response(path.includes('google')?{configured:false,connected:false}:{contacts:[]})}))
 render(<Contacts/>);fireEvent.change(screen.getByLabelText('Nombre'),{target:{value:'BORRADOR FICTICIO'}})
 fireEvent.click(screen.getByRole('tab',{name:'Google'}));expect(screen.queryByRole('button',{name:'Guardar contacto'})).toBeNull()
 expect(screen.getByRole('tabpanel',{name:'Google'}).tabIndex).toBe(0)
 fireEvent.click(screen.getByRole('tab',{name:'Agenda'}));expect((screen.getByLabelText('Nombre') as HTMLInputElement).value).toBe('BORRADOR FICTICIO');expect(writes).toEqual([])
})
it('gives embedded Contact instances unique tab and panel IDs',()=>{
 vi.stubGlobal('fetch',vi.fn(async()=>response({configured:false,connected:false,contacts:[]})))
 render(<><Contacts inline/><Contacts inline/></>)
 const tabs=screen.getAllByRole('tab');expect(new Set(tabs.map(tab=>tab.id)).size).toBe(4)
 for(const tab of tabs)expect(document.getElementById(tab.getAttribute('aria-controls')!)).toBeTruthy()
})
it('preserves message, calendar and review confirmation across externally selected message and history sections without sending',async()=>{
 const contact={id:'contact',name:'FICTICIO',phone:'+12025550123'};const draft={id:'draft',revision:'r',contact_id:contact.id,recipient:contact,text:'Texto guardado',attachments:[],schedule:{kind:'now',timezone:'Europe/Madrid',at:null,time:null,weekdays:[]},state:'draft',next_run_at:null,created_at:'',updated_at:'',conversation_id:'conv',last_error:null}
 const writes:string[]=[];vi.stubGlobal('fetch',vi.fn(async(path:string,init?:RequestInit)=>{if(init?.method&&init.method!=='GET')writes.push(path);if(path==='/api/communications/contacts')return response({contacts:[contact]});if(path.endsWith('/drafts'))return response({drafts:[draft]});if(path.endsWith('/runs'))return response({runs:[]});if(path.includes('/drafts/'))return response(draft);return response({contacts:[],configured:false,connected:false})}))
 const {rerender}=render(<Communications draftId="draft"/>);await screen.findByDisplayValue('Texto guardado')
 fireEvent.click(screen.getByLabelText('He revisado el destinatario exacto, el texto, los adjuntos y el calendario.'))
 rerender(<Communications draftId="draft" activeSection="history"/>);expect(screen.queryByRole('button',{name:'Confirmar y enviar ahora'})).toBeNull()
 expect(screen.queryByRole('tablist',{name:'Secciones de Comunicaciones'})).toBeNull()
 rerender(<Communications draftId="draft" activeSection="message"/>)
 expect((screen.getByRole('button',{name:'Confirmar y enviar ahora'}) as HTMLButtonElement).disabled).toBe(false)
 fireEvent.change(screen.getByRole('textbox',{name:'Mensaje'}),{target:{value:'Edición sin guardar'}})
 fireEvent.change(screen.getByLabelText('Cuándo'),{target:{value:'weekly'}})
 rerender(<Communications draftId="draft" activeSection="history"/>);rerender(<Communications draftId="draft" activeSection="message"/>)
 expect((screen.getByRole('textbox',{name:'Mensaje'}) as HTMLTextAreaElement).value).toBe('Edición sin guardar')
 expect((screen.getByLabelText('Cuándo') as HTMLSelectElement).value).toBe('weekly')
 expect(screen.queryByLabelText('He revisado el destinatario exacto, el texto, los adjuntos y el calendario.')).toBeNull();expect(screen.queryByRole('button',{name:'Confirmar y enviar ahora'})).toBeNull()
 expect(writes).toEqual([])
})
it('preserves selected project and dirty file across areas; exposes one context panel and exact file controls',async()=>{
 const w={id:'workspace_fixture',name:'fixture',title:'FICTICIO',root:'C:/isolated/fixture',context_files:[]};const requests:any[]=[]
 vi.stubGlobal('fetch',vi.fn(async(path:string,init?:RequestInit)=>{
  if(init){const body=JSON.parse(String(init.body));requests.push(body);if(body.operation==='list_files')return response({files:[{path:'note.txt',sha256:'a'.repeat(64),size:4}],excluded:[]});if(body.operation==='trash_list')return response({items:[]});if(body.operation==='read')return response({path:'note.txt',sha256:'a'.repeat(64),size:4,text:'Base'})}
  return response(path.endsWith('/config')?{configured:true,parent:'C:/isolated'}:{workspaces:[w]})
 }))
 render(<WorkspaceManager contextPanel={<p>Contexto actual de ADL fixture</p>}/>);await screen.findByRole('option',{name:'FICTICIO · fixture'})
 fireEvent.change(screen.getByLabelText('Proyecto gestionado'),{target:{value:w.id}})
 fireEvent.click(screen.getByRole('tab',{name:'Archivos'}));fireEvent.click(await screen.findByRole('button',{name:'note.txt'}))
 await screen.findByDisplayValue('Base');fireEvent.change(screen.getByLabelText('Contenido'),{target:{value:'Mi edición'}})
 fireEvent.click(screen.getByRole('tab',{name:'Contexto y memoria'}));expect(screen.getByText('Contexto actual de ADL fixture')).toBeTruthy()
 expect(screen.queryByRole('textbox',{name:'Contenido'})).toBeNull()
 fireEvent.click(screen.getByRole('tab',{name:'Proyectos'}));expect((screen.getByLabelText('Proyecto gestionado') as HTMLSelectElement).disabled).toBe(true)
 fireEvent.click(screen.getByRole('tab',{name:'Archivos'}));expect((screen.getByLabelText('Contenido') as HTMLTextAreaElement).value).toBe('Mi edición')
 for(const tab of screen.getAllByRole('tab'))expect(document.getElementById(tab.getAttribute('aria-controls')!)).toBeTruthy()
 expect(requests.every(r=>['list_files','trash_list','read'].includes(r.operation))).toBe(true)
})
it('keeps operation review visible and unconfirmed when switching Workspace areas',async()=>{
 vi.stubGlobal('fetch',vi.fn(async(path:string)=>response(path.endsWith('/config')?{configured:true,parent:'C:/isolated'}:{workspaces:[]})))
 render(<WorkspaceManager/>);await screen.findByLabelText('Nombre de carpeta')
 fireEvent.change(screen.getByLabelText('Nombre de carpeta'),{target:{value:'nuevo'}});fireEvent.change(screen.getByLabelText('Título del proyecto'),{target:{value:'Nuevo'}})
 fireEvent.click(screen.getByRole('button',{name:'Revisar creación'}));fireEvent.click(screen.getByRole('tab',{name:'Contexto y memoria'}))
 const review=screen.getByRole('dialog',{name:'Revisar operación del espacio de trabajo'});expect(review.textContent).toContain('C:/isolated/nuevo')
 expect((within(review).getByRole('button',{name:'Confirmar y ejecutar'}) as HTMLButtonElement).disabled).toBe(true)
})
it('has scoped hidden rules and automatic width for nested contact containment, without fixed minimum containers',()=>{
 const css=readFileSync('src/ServiceSurfaces.css','utf8');expect(css).toContain("[role='tabpanel'][hidden]");expect(css).toContain(".communications-library[hidden] { display: none; }")
 expect(css).toMatch(/:is\(details, \[role='tabpanel'\]\) > \.contacts-page--inline\s*\{[^}]*width: auto;/)
 expect(css).not.toMatch(/min-width:\s*(?:[1-9]\d*)(?:px|rem)/)
 expect(css).toContain("[role='tab'][aria-selected='true']")
})
