// @vitest-environment jsdom
import React from 'react'
import {afterEach,beforeEach,expect,it,vi} from 'vitest'
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import ProjectPermissions from '../../src/components/ProjectPermissions'

const snapshot=(state='active')=>({project_id:'project-1',root:'D:/work/project',binding:{workspace_root:'D:/work/project',revision:4},revision:3,state,read_directories:['src'],write_directories:[]})
const listing={project_id:'project-1',root:'D:/work/project',binding:{workspace_root:'D:/work/project',revision:4},revision:3,directory:'.',directories:[{name:'src',path:'src'},{name:'docs',path:'docs'}],truncated:false}
const reply=(data:unknown,status=200)=>({ok:status<400,status,json:async()=>data})
const match=(url:unknown)=>String(url)
beforeEach(()=>localStorage.clear())
afterEach(()=>{cleanup();vi.unstubAllGlobals()})

it('shows the selected project root and reads the real folder tree with the saved project binding',async()=>{
 const fetch=vi.fn(async(url:unknown,init?:RequestInit)=>match(url).endsWith('/directories')?reply(listing):reply(snapshot()))
 vi.stubGlobal('fetch',fetch)
 render(<ProjectPermissions projectId="project-1" projectRoot="D:/work/project"/>)
 expect(await screen.findByText('D:/work/project')).toBeTruthy()
 expect(await screen.findByRole('button',{name:'Abrir carpeta src'})).toBeTruthy()
 expect(fetch).toHaveBeenCalledWith('/api/project-permissions/directories',expect.objectContaining({method:'POST',body:JSON.stringify({expected_project_id:'project-1',expected_binding:snapshot().binding,expected_revision:3,directory:'.'})}))
})

it('saves the directory policy only after explicit confirmation and binds it to project, binding and revision',async()=>{
 const calls:Array<{url:string;body?:any}>=[]
 vi.stubGlobal('fetch',vi.fn(async(url:unknown,init?:RequestInit)=>{
   const path=match(url);const body=init?.body?JSON.parse(String(init.body)):undefined;calls.push({url:path,body})
   if(path.endsWith('/directories'))return reply(listing)
   if(init?.method==='PUT')return reply({...snapshot(),revision:4,read_directories:['src'],write_directories:['docs']})
   return reply(snapshot())
 }))
 render(<ProjectPermissions projectId="project-1" projectRoot="D:/work/project"/>)
 await screen.findByRole('button',{name:'Abrir carpeta docs'})
 fireEvent.click(screen.getByLabelText('Permitir escritura en docs'))
 const save=screen.getByRole('button',{name:'Guardar permisos'}) as HTMLButtonElement
 expect(save.disabled).toBe(true)
 fireEvent.click(screen.getByLabelText('He revisado este alcance y confirmo los permisos del proyecto.'))
 expect(save.disabled).toBe(false)
 fireEvent.click(save)
 await waitFor(()=>expect(calls.some(call=>call.body?.confirmed===true)).toBe(true))
 expect(calls.find(call=>call.body?.confirmed===true)?.body).toEqual({expected_project_id:'project-1',expected_binding:snapshot().binding,expected_revision:3,read_directories:['src'],write_directories:['docs'],confirmed:true})
})

it('keeps a revoked policy visible and requires review before defining a replacement',async()=>{
 vi.stubGlobal('fetch',vi.fn(async(url:unknown)=>match(url).endsWith('/directories')?reply(listing):reply(snapshot('revoked'))))
 render(<ProjectPermissions projectId="project-1" projectRoot="D:/work/project"/>)
 expect(await screen.findByText(/Permisos revocados para este proyecto/)).toBeTruthy()
 expect((screen.getByRole('button',{name:'Guardar permisos'}) as HTMLButtonElement).disabled).toBe(true)
 expect((screen.getByRole('button',{name:'Revocar permisos'}) as HTMLButtonElement).disabled).toBe(true)
})

it('does not treat an unrecognized permission state as granted',async()=>{
 vi.stubGlobal('fetch',vi.fn(async(url:unknown)=>match(url).endsWith('/directories')?reply(listing):reply(snapshot('future_state'))))
 render(<ProjectPermissions projectId="project-1" projectRoot="D:/work/project"/>)
 expect(await screen.findByText(/No se presupone acceso/)).toBeTruthy()
 const save=screen.getByRole('button',{name:'Guardar permisos'}) as HTMLButtonElement
 expect(save.disabled).toBe(true)
 fireEvent.click(screen.getByLabelText('He revisado este alcance y confirmo los permisos del proyecto.'))
 expect(save.disabled).toBe(false)
 expect((screen.getByRole('button',{name:'Revocar permisos'}) as HTMLButtonElement).disabled).toBe(true)
})

it('shows loading, unknown binding and API errors without granting access',async()=>{
 let resolve:(value:any)=>void=()=>{}
 vi.stubGlobal('fetch',vi.fn(()=>new Promise(done=>{resolve=done})))
 const view=render(<ProjectPermissions projectId="project-1" projectRoot="D:/work/project"/>)
 expect(screen.getByRole('status').textContent).toContain('Cargando')
 view.unmount()
 vi.stubGlobal('fetch',vi.fn(async()=>reply(snapshot())))
 render(<ProjectPermissions projectId="project-2" projectRoot="D:/elsewhere"/>)
 expect(await screen.findByText(/No se puede confirmar el proyecto/)).toBeTruthy()
 vi.stubGlobal('fetch',vi.fn(async()=>reply({error:'offline'},503)))
 render(<ProjectPermissions projectId="project-1" projectRoot="D:/work/project"/>)
 expect(await screen.findByRole('alert')).toBeTruthy()
 resolve(reply(snapshot()))
})
