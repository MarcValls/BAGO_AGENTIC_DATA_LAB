// @vitest-environment jsdom
import React from 'react'
import {afterEach,beforeEach,expect,it,vi} from 'vitest'
import {cleanup,fireEvent,render,screen,waitFor,within} from '@testing-library/react'
import ProjectPermissions from '../../src/components/ProjectPermissions'

const snapshot=(state='configured')=>({project_id:'project-1',root:'D:/work/project',binding:{workspace_root:'D:/work/project',revision:4},revision:3,state,read_directories:['src'],write_directories:[]})
const listing={project_id:'project-1',root:'D:/work/project',binding:{workspace_root:'D:/work/project',revision:4},revision:3,directory:'.',directories:[{name:'src',path:'src'},{name:'docs',path:'docs'}],files:[{name:'README.md',path:'README.md'}],entries:[{name:'src',path:'src',kind:'directory'},{name:'docs',path:'docs',kind:'directory'},{name:'README.md',path:'README.md',kind:'file'}],truncated:false}
const reply=(data:unknown,status=200)=>({ok:status<400,status,json:async()=>data})
const match=(url:unknown)=>String(url)
beforeEach(()=>localStorage.clear())
afterEach(()=>{cleanup();vi.unstubAllGlobals()})

it('keeps the sidebar compact and loads the bound file tree only when the combined panel opens',async()=>{
 const fetch=vi.fn(async(url:unknown,init?:RequestInit)=>{
  if(match(url).endsWith('/directories')){
   const body=init?.body?JSON.parse(String(init.body)):{}
   return reply(body.directory==='src'?{...listing,directory:'src',directories:[],files:[{name:'nested.py',path:'src/nested.py'}],entries:[{name:'nested.py',path:'src/nested.py',kind:'file'}]}:listing)
  }
  return reply(snapshot())
 })
 const onBrowseWorkspace=vi.fn()
 vi.stubGlobal('fetch',fetch)
 render(<ProjectPermissions projectId="project-1" projectRoot="D:/work/project" onBrowseWorkspace={onBrowseWorkspace}/> )
 expect(await screen.findByText('D:/work/project')).toBeTruthy()
 expect(screen.getByRole('button',{name:'Administrar acceso'})).toBeTruthy()
 expect(screen.queryByLabelText('Resumen de permisos')).toBeNull()
 expect(fetch).not.toHaveBeenCalledWith('/api/project-permissions/directories',expect.anything())
 fireEvent.click(screen.getByRole('button',{name:'Administrar acceso'}))
 expect(await screen.findByRole('dialog',{name:'Permisos del proyecto'})).toBeTruthy()
 fireEvent.click(await screen.findByRole('button',{name:'Expandir carpeta src'}))
 expect(await screen.findByText('nested.py')).toBeTruthy()
 expect(await screen.findByText('README.md')).toBeTruthy()
 expect(screen.queryByRole('region',{name:'Carpeta de trabajo'})).toBeNull()
 expect(screen.getByText('Directorio de trabajo:')).toBeTruthy()
 expect(document.querySelector('.project-permissions__workspace-summary code')?.textContent).toBe('D:/work/project')
 fireEvent.click(screen.getByRole('button',{name:'Examinar carpeta de trabajo'}))
 expect(onBrowseWorkspace).toHaveBeenCalledTimes(1)
 expect(within(screen.getByRole('dialog',{name:'Permisos del proyecto'})).queryByText(/Las herramientas usan los permisos guardados/)).toBeNull()
 expect(fetch).toHaveBeenCalledWith('/api/project-permissions/directories',expect.objectContaining({method:'POST',body:JSON.stringify({expected_project_id:'project-1',expected_binding:snapshot().binding,expected_revision:3,directory:'.'})}))
 expect(fetch).toHaveBeenCalledWith('/api/project-permissions/directories',expect.objectContaining({method:'POST',body:JSON.stringify({expected_project_id:'project-1',expected_binding:snapshot().binding,expected_revision:3,directory:'src'})}))
})

it('saves file and folder scopes only after explicit confirmation, bound to project and revision',async()=>{
 const calls:Array<{url:string;body?:any}>=[]
 vi.stubGlobal('fetch',vi.fn(async(url:unknown,init?:RequestInit)=>{
   const path=match(url);const body=init?.body?JSON.parse(String(init.body)):undefined;calls.push({url:path,body})
   if(path.endsWith('/directories'))return reply(listing)
   if(init?.method==='PUT')return reply({...snapshot(),revision:4,read_directories:['README.md','src'],write_directories:['docs']})
   return reply(snapshot())
 }))
 render(<ProjectPermissions projectId="project-1" projectRoot="D:/work/project"/> )
 fireEvent.click(await screen.findByRole('button',{name:'Administrar acceso'}))
 await screen.findByRole('button',{name:'Expandir carpeta docs'})
 fireEvent.click(screen.getByLabelText('Permitir lectura en README.md'))
 fireEvent.click(screen.getByLabelText('Permitir escritura en docs'))
 const save=screen.getByRole('button',{name:'Guardar permisos'}) as HTMLButtonElement
 expect(save.disabled).toBe(true)
 fireEvent.click(screen.getByLabelText('He revisado este alcance y confirmo los permisos del proyecto.'))
 expect(save.disabled).toBe(false)
 fireEvent.click(save)
 await waitFor(()=>expect(calls.some(call=>call.body?.confirmed===true)).toBe(true))
 expect(calls.find(call=>call.body?.confirmed===true)?.body).toEqual({expected_project_id:'project-1',expected_binding:snapshot().binding,expected_revision:3,read_directories:['README.md','src'],write_directories:['docs'],confirmed:true})
})

it('keeps revoked permissions visible and requires review before defining a replacement',async()=>{
 vi.stubGlobal('fetch',vi.fn(async(url:unknown)=>match(url).endsWith('/directories')?reply(listing):reply(snapshot('revoked'))))
 render(<ProjectPermissions projectId="project-1" projectRoot="D:/work/project"/> )
 fireEvent.click(await screen.findByRole('button',{name:'Administrar acceso'}))
 expect(await screen.findByText(/Permisos revocados para este proyecto/)).toBeTruthy()
 expect((screen.getByRole('button',{name:'Guardar permisos'}) as HTMLButtonElement).disabled).toBe(true)
 expect((screen.getByRole('button',{name:'Revocar permisos'}) as HTMLButtonElement).disabled).toBe(true)
})

it('lets the user remove a saved file scope that is no longer present in the tree',async()=>{
 const calls:Array<{method?:string;body?:any}> = []
 vi.stubGlobal('fetch',vi.fn(async(url:unknown,init?:RequestInit)=>{
   const body=init?.body?JSON.parse(String(init.body)):undefined;calls.push({method:init?.method,body})
   if(match(url).endsWith('/directories'))return reply(listing)
   if(init?.method==='PUT')return reply({...snapshot(),revision:4,read_directories:[],write_directories:[]})
   return reply({...snapshot(),read_directories:['gone.txt']})
 }))
 render(<ProjectPermissions projectId="project-1" projectRoot="D:/work/project"/> )
 fireEvent.click(await screen.findByRole('button',{name:'Administrar acceso'}))
 fireEvent.click(await screen.findByRole('button',{name:'Quitar lectura en gone.txt'}))
 fireEvent.click(screen.getByLabelText('He revisado este alcance y confirmo los permisos del proyecto.'))
 fireEvent.click(screen.getByRole('button',{name:'Guardar permisos'}))
 await waitFor(()=>expect(calls.some(call=>call.method==='PUT')).toBe(true))
 expect(calls.find(call=>call.method==='PUT')?.body.read_directories).toEqual([])
})

it('does not treat an unrecognized permission state as granted',async()=>{
 vi.stubGlobal('fetch',vi.fn(async(url:unknown)=>match(url).endsWith('/directories')?reply(listing):reply(snapshot('future_state'))))
 render(<ProjectPermissions projectId="project-1" projectRoot="D:/work/project"/> )
 fireEvent.click(await screen.findByRole('button',{name:'Administrar acceso'}))
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
 const view=render(<ProjectPermissions projectId="project-1" projectRoot="D:/work/project"/> )
 expect(screen.getByText('Directorio de trabajo:')).toBeTruthy()
 view.unmount()
 vi.stubGlobal('fetch',vi.fn(async()=>reply(snapshot())))
 const mismatch=render(<ProjectPermissions projectId="project-2" projectRoot="D:/elsewhere"/> )
 fireEvent.click(await screen.findByRole('button',{name:'Administrar acceso'}))
 expect(await screen.findByText(/No se puede confirmar el proyecto/)).toBeTruthy()
 mismatch.unmount()
 vi.stubGlobal('fetch',vi.fn(async()=>reply({error:'offline'},503)))
 render(<ProjectPermissions projectId="project-1" projectRoot="D:/work/project"/> )
 fireEvent.click(await screen.findByRole('button',{name:'Administrar acceso'}))
 expect(await screen.findByRole('alert')).toBeTruthy()
 resolve(reply(snapshot()))
})
