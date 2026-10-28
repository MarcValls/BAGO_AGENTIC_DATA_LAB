// @vitest-environment jsdom
import React from 'react'
import {afterEach, expect, it, vi} from 'vitest'
import {cleanup, fireEvent, render, screen} from '@testing-library/react'
import DevelopmentPanel, {type DevelopmentChange} from '../../src/components/DevelopmentPanel'
afterEach(()=>{cleanup();vi.unstubAllGlobals()})
const fixture:DevelopmentChange={change_id:'dev_'+'f'.repeat(64),patch_sha256:'a'.repeat(64),status:'PREPARED',author:{owner_id:'author',conversation_id:'conv'},diff:'+synthetic drawer fixture',checks:[{check_id:'fixed',status:'PASS'}],reviews:[{reviewer_id:'independent',approved:true,reason:'fixture'}],apply_eligible:true}
const response=(data:unknown)=>({ok:true,json:async()=>data})
function setup(){const fetcher=vi.fn(async(path:string)=>response(path.endsWith('/changes')?{changes:[fixture]}:fixture));vi.stubGlobal('fetch',fetcher);return fetcher}
it('folds to a compact tab, keeps candidate and confirmation, and does not fetch or write on toggles',async()=>{
 const fetcher=setup();render(<DevelopmentPanel ownerId="author"/>);
 fireEvent.click(await screen.findByText(fixture.change_id+' · PREPARED'));
 await screen.findByText('+synthetic drawer fixture');
 fireEvent.click(screen.getByLabelText('He revisado las diferencias y confirmo esta operación'));
 expect((screen.getByText('Aplicar cambio') as HTMLButtonElement).disabled).toBe(false);
 const before=fetcher.mock.calls.length;
 fireEvent.click(screen.getByRole('button',{name:'Cerrar panel de Proyecto'}));
 const tab=screen.getByRole('button',{name:'Proyecto',exact:true});
 expect(tab.getAttribute('aria-expanded')).toBe('false');expect(document.activeElement).toBe(tab);
 const panel=document.getElementById(tab.getAttribute('aria-controls')!);
 expect(panel?.hidden).toBe(true);expect(screen.queryByRole('region',{name:'Contexto del proyecto'})).toBeNull();
 fireEvent.click(tab);expect(panel?.hidden).toBe(false);
 expect(document.activeElement).toBe(screen.getByRole('button',{name:'Cerrar panel de Proyecto'}));
 expect((screen.getByLabelText('He revisado las diferencias y confirmo esta operación') as HTMLInputElement).checked).toBe(true);
 expect((screen.getByText('Aplicar cambio') as HTMLButtonElement).disabled).toBe(false);
 expect(fetcher.mock.calls).toHaveLength(before);
})
it('Escape folds without erasing an external chat draft and returns focus to the tab',async()=>{
 setup();render(<><textarea aria-label="Borrador del chat" defaultValue="conservar este borrador"/><DevelopmentPanel ownerId="author"/></>);
 await screen.findByText(fixture.change_id+' · PREPARED');
 fireEvent.keyDown(document,{key:'Escape'});
 const tab=screen.getByRole('button',{name:'Proyecto',exact:true});expect(document.activeElement).toBe(tab);
 expect((screen.getByLabelText('Borrador del chat') as HTMLTextAreaElement).value).toBe('conservar este borrador');
 fireEvent.click(tab);expect(screen.getByRole('region',{name:'Contexto del proyecto'})).toBeTruthy();
})
it('retains pending loading through fold without starting a second request',async()=>{
 let resolve!:(value:unknown)=>void;const fetcher=vi.fn(()=>new Promise(r=>{resolve=r}));vi.stubGlobal('fetch',fetcher);
 render(<DevelopmentPanel ownerId="author"/>);fireEvent.click(screen.getByRole('button',{name:'Cerrar panel de Proyecto'}));
 resolve(response({changes:[]}));fireEvent.click(screen.getByRole('button',{name:'Proyecto',exact:true}));
 expect(await screen.findByText(/Todavía no hay cambios/)).toBeTruthy();expect(fetcher).toHaveBeenCalledTimes(1);
})

it('workspace-only agents never request development API and preserve independent section controls',async()=>{
 const fetcher=vi.fn();vi.stubGlobal('fetch',fetcher);
 render(<DevelopmentPanel ownerId="folder-agent" showChanges={false} initialOpen={false} workspaceContent={<details className="project-sidebar-section"><summary>Carpeta de trabajo</summary><input aria-label="Permiso actual" type="checkbox"/></details>}/>);
 fireEvent.click(screen.getByRole('button',{name:'Proyecto',exact:true}));
 expect(screen.queryByText('Historial de cambios')).toBeNull();
 fireEvent.click(screen.getByText('Carpeta de trabajo'));fireEvent.click(screen.getByLabelText('Permiso actual'));
 fireEvent.click(screen.getByRole('button',{name:'Cerrar panel de Proyecto'}));fireEvent.click(screen.getByRole('button',{name:'Proyecto',exact:true}));
 expect((screen.getByLabelText('Permiso actual') as HTMLInputElement).checked).toBe(true);expect(fetcher).not.toHaveBeenCalled();
})
it('keeps the full project panel open on narrow screens when requested open',()=>{
 const original=Object.getOwnPropertyDescriptor(window,'matchMedia')
 Object.defineProperty(window,'matchMedia',{configurable:true,value:vi.fn(()=>({matches:true}))})
 try{
  render(<DevelopmentPanel ownerId="app-assistant" showChanges={false} initialOpen workspaceContent={<p>Workspace content</p>}/>);
   const tab=screen.getByRole('button',{name:'Proyecto',exact:true});expect(tab.getAttribute('aria-expanded')).toBe('true');
   expect(document.getElementById(tab.getAttribute('aria-controls')!)?.hidden).toBe(false)
   expect(screen.queryByRole('button',{name:/Ampliar panel de Proyecto|Restaurar tamaño del panel de Proyecto/})).toBeNull()
 }finally{
  if(original)Object.defineProperty(window,'matchMedia',original);else delete (window as any).matchMedia
 }
})
it('workspace and history expand independently without changing confirmation',async()=>{
 setup();render(<DevelopmentPanel ownerId="author" workspaceContent={<details className="project-sidebar-section"><summary>Carpeta de trabajo</summary><p>Scope actual</p></details>}/>);
 await screen.findByText(fixture.change_id+' · PREPARED');
 const workspace=screen.getByText('Carpeta de trabajo').closest('details')!;const history=screen.getByText('Historial de cambios').closest('details')!;
 expect(workspace.open).toBe(false);expect(history.open).toBe(true);
 fireEvent.click(screen.getByText('Carpeta de trabajo'));expect(workspace.open).toBe(true);expect(history.open).toBe(true);
 fireEvent.click(screen.getByText('Historial de cambios'));expect(workspace.open).toBe(true);expect(history.open).toBe(false);
})

it('general context slots preserve independent sections and never load development or expose mutation controls',async()=>{
 const fetcher=vi.fn();vi.stubGlobal('fetch',fetcher)
 render(<DevelopmentPanel ownerId="app-assistant" showChanges={false} initialOpen workspaceContent={<details className="project-sidebar-section" open><summary>Workspace actual</summary><p>Sin permiso nuevo</p></details>} historyContent={<p>Conversación conservada</p>}/>);
 expect(screen.getByRole('region',{name:'Contexto del proyecto'})).toBeTruthy();expect(screen.getByText('Historial de conversaciones')).toBeTruthy();expect(screen.queryByText('Historial de cambios')).toBeNull();expect(screen.queryByRole('button',{name:'Aplicar cambio'})).toBeNull();expect(screen.queryByRole('button',{name:'Actualizar cambios'})).toBeNull();expect(document.querySelectorAll('.project-sidebar-sections > details[open]')).toHaveLength(2)
 fireEvent.click(screen.getByRole('button',{name:'Cerrar panel de Proyecto'}));fireEvent.click(screen.getByRole('button',{name:'Proyecto',exact:true}));expect(screen.getByText('Conversación conservada')).toBeTruthy();expect(fetcher).not.toHaveBeenCalled()
})
