// @vitest-environment jsdom
import React from 'react'
import {afterEach,beforeEach,expect,it,vi} from 'vitest'
import {act,cleanup,fireEvent,render,screen,waitFor,within} from '@testing-library/react'
import WorkspaceManager from '../../src/components/WorkspaceManager'
import CognitionSettings from '../../src/components/CognitionSettings'
import {resetLocaleForTests,setLocale} from '../../src/i18n'
import {folderFixture,metadata,planFor,receiptFor,reply,workspace} from './fixtures'
beforeEach(()=>{localStorage.clear();resetLocaleForTests();setLocale('es')})
afterEach(()=>{cleanup();vi.unstubAllGlobals();vi.restoreAllMocks()})
const pathInput=()=>screen.getByLabelText('Carpeta del proyecto o padre elegido') as HTMLInputElement
const useFolder=()=>screen.getByRole('button',{name:'Usar carpeta'})
const dialog=()=>screen.getByRole('dialog',{name:'Revisar operación del espacio de trabajo'})
async function ready(){await waitFor(()=>expect((useFolder() as HTMLButtonElement).disabled).toBe(false))}
async function prepare(){fireEvent.click(useFolder());await screen.findByRole('dialog',{name:'Revisar operación del espacio de trabajo'})}
const accept=()=>fireEvent.click(within(dialog()).getByRole('checkbox'))
const confirm=()=>fireEvent.click(within(dialog()).getByRole('button',{name:'Confirmar y ejecutar'}))
function deferred<T>(){let resolve!:(value:T)=>void;const promise=new Promise<T>(r=>{resolve=r});return {promise,resolve}}

it('defaults to the exact active D folder with mount GETs only and no administrative C fallback',async()=>{
 const f=folderFixture({workspaces:[workspace('C:/old-admin-root')]});render(<WorkspaceManager/>);await ready()
 expect(pathInput().value).toBe('D:/selected-project');expect((screen.getByLabelText('Usar esta carpeta existente') as HTMLInputElement).checked).toBe(true)
 expect(f.mutations()).toEqual([]);expect(f.calls.map(c=>c.url).sort()).toEqual(['/api/chat/context','/api/project-folders/v1/config','/api/project-folders/v1/workspaces'].sort())
 await prepare();expect(dialog().textContent).toContain('D:/selected-project');expect(dialog().textContent).not.toContain('C:/old-admin-root')
 expect(within(dialog()).getAllByText('Falta · se creará')).toHaveLength(3)
 expect(dialog().querySelector('.wm-folder-plan-files li')?.textContent).toContain('Existe · se conserva')
 expect(dialog().querySelector('.wm-folder-directories')?.hasAttribute('open')).toBe(false)
 expect(f.mutations()).toHaveLength(1);expect(f.mutations()[0].body).toEqual({mode:'existing',path:'D:/selected-project',name:'',title:'',expected_workspace_root:'D:/selected-project'})
 expect((within(dialog()).getByRole('button',{name:'Confirmar y ejecutar'}) as HTMLButtonElement).disabled).toBe(true)
})
it('applies only the reviewed ID and hash after explicit consent; no old bind, grants, minimum writes or model dispatch are inferred by UI',async()=>{
 const f=folderFixture(),selected=vi.fn();render(<WorkspaceManager onSelected={selected}/>);await ready();await prepare()
 expect(f.getRoot()).toBe('D:/selected-project');accept();confirm();await screen.findByText(/El servicio confirmó la carpeta activa/)
 expect(f.mutations().map(c=>c.url)).toEqual(['/api/project-folders/v1/plans','/api/project-folders/v1/plans/folder_plan_1/apply'])
 expect(f.mutations()[1].body).toEqual({plan_sha256:'1'.repeat(64),confirmed:true});expect(selected).toHaveBeenCalledTimes(1)
 expect(f.calls.some(c=>/workspace\/select|workspaces\/v1|authorizations|chat\/control|agent.*\/chat/.test(c.url))).toBe(false)
 expect(screen.queryByRole('dialog')).toBeNull();expect(screen.getByText('Recibo devuelto por el servicio')).toBeTruthy()
})
it('creates a child only in the selected parent and only by the explicit child mode',async()=>{
 const f=folderFixture();render(<WorkspaceManager/>);await ready()
 fireEvent.click(screen.getByLabelText('Crear una carpeta hija'));fireEvent.change(pathInput(),{target:{value:'E:/chosen-parent'}});fireEvent.change(screen.getByLabelText('Nombre de carpeta'),{target:{value:'child-name'}});fireEvent.change(screen.getByLabelText('Título del proyecto'),{target:{value:'Child title'}})
 await prepare();expect(dialog().textContent).toContain('E:/chosen-parent/child-name');expect(f.getRoot()).toBe('D:/selected-project')
 accept();confirm();await screen.findByText(/El servicio confirmó la carpeta activa/)
 expect(f.getRoot()).toBe('E:/chosen-parent/child-name');expect(pathInput().value).toBe(f.getRoot());expect((screen.getByLabelText('Usar esta carpeta existente') as HTMLInputElement).checked).toBe(true)
})
it.each([false,true])('browse is selection-only and cancellation=%s preserves active binding and drafts',async cancelled=>{
 const f=folderFixture({browse:{path:cancelled?null:'E:/chosen-folder',cancelled}});render(<WorkspaceManager/>);await ready();fireEvent.change(screen.getByLabelText('Título del proyecto'),{target:{value:'Human draft'}})
 fireEvent.click(screen.getByRole('button',{name:'Examinar…'}));await waitFor(()=>expect((screen.getByRole('button',{name:'Examinar…'}) as HTMLButtonElement).disabled).toBe(false))
 expect(pathInput().value).toBe(cancelled?'D:/selected-project':'E:/chosen-folder');expect(f.getRoot()).toBe('D:/selected-project');expect((screen.getByLabelText('Título del proyecto') as HTMLInputElement).value).toBe('Human draft')
 expect(f.mutations()).toEqual([{url:'/api/project-folders/v1/browse',method:'POST',body:{}}]);expect(screen.queryByRole('dialog')).toBeNull()
})
it('cancel retains fields and returns focus without applying a reviewed plan',async()=>{
 const f=folderFixture();render(<WorkspaceManager/>);await ready();fireEvent.change(screen.getByLabelText('Nombre de carpeta'),{target:{value:'Human name'}});await prepare();accept();fireEvent.click(within(dialog()).getByRole('button',{name:'Cancelar'}))
 expect((screen.getByLabelText('Nombre de carpeta') as HTMLInputElement).value).toBe('Human name');expect(document.activeElement).toBe(useFolder());expect(f.mutations()).toHaveLength(1);expect(screen.queryByRole('dialog')).toBeNull()
})
it('keeps keyboard focus in review and Escape cancels back to Projects without applying or losing the draft',async()=>{
 const f=folderFixture();render(<WorkspaceManager/>);await ready();fireEvent.change(screen.getByLabelText('Título del proyecto'),{target:{value:'Keyboard draft'}});await prepare()
 const cancel=within(dialog()).getByRole('button',{name:'Cancelar'}),first=dialog().querySelector('summary')!
 cancel.focus();fireEvent.keyDown(cancel,{key:'Tab'});expect(document.activeElement).toBe(first)
 fireEvent.keyDown(first,{key:'Tab',shiftKey:true});expect(document.activeElement).toBe(cancel)
 fireEvent.keyDown(cancel,{key:'Escape'});expect(screen.queryByRole('dialog')).toBeNull();expect(document.activeElement).toBe(useFolder());expect((screen.getByLabelText('Título del proyecto') as HTMLInputElement).value).toBe('Keyboard draft');expect(f.mutations()).toHaveLength(1)
})
it.each(['path','name','title','mode'])('changing %s invalidates the accepted plan even when the old value is restored',async field=>{
 const f=folderFixture();render(<WorkspaceManager/>);await ready();await prepare();accept()
 if(field==='mode'){fireEvent.click(screen.getByLabelText('Crear una carpeta hija'));fireEvent.click(screen.getByLabelText('Usar esta carpeta existente'))}
 else{const control=field==='path'?pathInput():screen.getByLabelText(field==='name'?'Nombre de carpeta':'Título del proyecto') as HTMLInputElement;const original=control.value;fireEvent.change(control,{target:{value:original+'-edited'}});fireEvent.change(control,{target:{value:original}})}
 expect(screen.queryByRole('dialog')).toBeNull();expect(f.mutations()).toHaveLength(1);await prepare();expect((within(dialog()).getByRole('checkbox') as HTMLInputElement).checked).toBe(false)
})
it('late context does not overwrite a human draft and late preparation cannot resurrect an edited review',async()=>{
 const context=deferred<unknown>(),pendingPlan=deferred<unknown>();let captured:any
 const f=folderFixture({route:(url,body)=>{if(url==='/api/chat/context')return context.promise;if(url==='/api/project-folders/v1/plans'){captured=body;return pendingPlan.promise}}});render(<WorkspaceManager/>)
 fireEvent.change(pathInput(),{target:{value:'E:/human-draft'}});await act(async()=>context.resolve(reply(metadata('D:/selected-project'))));await ready();expect(pathInput().value).toBe('E:/human-draft')
 fireEvent.click(useFolder());fireEvent.change(pathInput(),{target:{value:'E:/newer-draft'}});await act(async()=>pendingPlan.resolve(reply(planFor(captured))))
 expect(screen.queryByRole('dialog')).toBeNull();expect(pathInput().value).toBe('E:/newer-draft');expect(f.mutations()).toHaveLength(1)
})
it('a refreshed binding invalidates plan and consent without silently overwriting edited fields',async()=>{
 const f=folderFixture();const view=render(<WorkspaceManager refreshKey={0}/>);await ready();fireEvent.change(pathInput(),{target:{value:'E:/human-draft'}});await prepare();accept()
 f.setRoot('F:/other-active');view.rerender(<WorkspaceManager refreshKey={1}/>);await ready();expect(screen.queryByRole('dialog')).toBeNull();expect(pathInput().value).toBe('E:/human-draft');expect(view.container.textContent).toContain('F:/other-active');expect(f.mutations()).toHaveLength(1)
})
it.each(['hash','target','binding','expiry','absolute','traversal','mode'])('rejects a mismatched or malformed %s plan without apply',async fault=>{
 const f=folderFixture({plan:normal=>({...normal,...(fault==='hash'?{plan_sha256:'bad'}:fault==='target'?{target_root:'C:/wrong-admin'}:fault==='binding'?{expected_workspace_root:'C:/wrong-admin'}:fault==='expiry'?{expires_at:'invalid'}:fault==='mode'?{mode:'create_child'}:{files:[{path:fault==='absolute'?'C:/not-relative':'../escape',action:'create'}]})})});render(<WorkspaceManager/>);await ready();fireEvent.click(useFolder());await screen.findByRole('alert');expect(screen.queryByRole('dialog')).toBeNull();expect(f.mutations()).toHaveLength(1)
})
it('never treats partial failure or an error with created files as a selected project and never retries apply',async()=>{
 let plan:any;const partial={receipt_id:'partial',plan_id:'folder_plan_1',plan_sha256:'1'.repeat(64),status:'PARTIAL_FAILED',target_root:'D:/selected-project',created_files:['.bago/state/PROJECT_STATE.json'],created_directories:[],registry_applied:false,binding_applied:false,actual_workspace_root:'D:/selected-project',error_code:'SYNTHETIC_PARTIAL'}
 const f=folderFixture({plan:normal=>{plan=normal;return normal},route:url=>url.endsWith('/apply')?reply({error:{code:'SYNTHETIC_PARTIAL',message:'Partial fixture error',receipt:partial}},409):undefined}),selected=vi.fn();render(<WorkspaceManager onSelected={selected}/>);await ready();await prepare();expect(plan).toBeTruthy();accept();confirm();await screen.findByRole('alert')
 expect(screen.queryByText(/El servicio confirmó la carpeta activa/)).toBeNull();expect(screen.queryByRole('dialog')).toBeNull();expect(selected).not.toHaveBeenCalled();expect(f.mutations()).toHaveLength(2)
 fireEvent.click(screen.getByText('Recibo devuelto por el servicio'));expect(screen.getByText(/PARTIAL_FAILED/, {selector:'pre'})).toBeTruthy();expect(screen.getByText(/\.bago\/state\/PROJECT_STATE.json/, {selector:'pre'})).toBeTruthy()
})
it('requires the receipt to confirm the exact reviewed identity before announcing success',async()=>{
 let planned:any;const f=folderFixture({plan:normal=>{planned=normal;return normal},route:url=>url.endsWith('/apply')?reply({workspace_root:'D:/selected-project',workspace:workspace(),receipt:receiptFor(planned,{plan_sha256:'f'.repeat(64)})}):undefined}),selected=vi.fn();render(<WorkspaceManager onSelected={selected}/>);await ready();await prepare();accept();confirm();await screen.findByRole('alert');expect(selected).not.toHaveBeenCalled();expect(screen.queryByText(/El servicio confirmó la carpeta activa/)).toBeNull();expect(f.mutations()).toHaveLength(2)
})
it('fails closed for legacy or inconsistent config and never chooses a C fallback',async()=>{
 const f=folderFixture({route:url=>url==='/api/project-folders/v1/config'?reply({configured:true,parent:'C:/old-admin'}):undefined});render(<WorkspaceManager/>);await screen.findByRole('alert');expect((useFolder() as HTMLButtonElement).disabled).toBe(true);expect(pathInput().value).not.toBe('C:/old-admin');expect(f.mutations()).toEqual([])
})
it('Context is an active-folder view that returns to Projects with focus and never uses legacy browse/bind',async()=>{
 const f=folderFixture();render(<WorkspaceManager contextPanel={({openProjectSelection,refreshKey})=><CognitionSettings key={refreshKey} mode="baseline" onModeChange={vi.fn()} workspaceOnly onRequestWorkspaceSelection={openProjectSelection}/>}/>);await ready()
 fireEvent.click(screen.getByRole('tab',{name:'Contexto y memoria'}));await screen.findByRole('button',{name:'Editar carpeta en Proyectos'})
 expect(screen.queryByRole('button',{name:'Examinar…'})).toBeNull();expect(screen.queryByRole('button',{name:'Usar carpeta'})).toBeNull()
 fireEvent.click(screen.getByRole('button',{name:'Editar carpeta en Proyectos'}));await waitFor(()=>expect(document.activeElement).toBe(pathInput()));expect(pathInput().value).toBe('D:/selected-project');expect(f.mutations()).toEqual([])
 fireEvent.change(pathInput(),{target:{value:'E:/next-active'}});await prepare();accept();confirm();await screen.findByText(/El servicio confirmó la carpeta activa/);fireEvent.click(screen.getByRole('tab',{name:'Contexto y memoria'}));await screen.findByText('E:/next-active',{selector:'code.context-location-path'})
 expect(f.calls.some(c=>c.url==='/api/workspace/browse'||c.url==='/api/workspace/select')).toBe(false)
})
it('preserves a standalone CognitionSettings picker when no selection callback is supplied',async()=>{
 const calls:string[]=[];vi.stubGlobal('fetch',vi.fn(async(url:string)=>{calls.push(url);return reply(url==='/api/chat/context'?metadata('D:/legacy-standalone'):{cancelled:true})}));render(<CognitionSettings mode="baseline" onModeChange={vi.fn()} workspaceOnly/>);await screen.findByDisplayValue('D:/legacy-standalone');fireEvent.click(screen.getByRole('button',{name:'Examinar…'}));await screen.findByText('Selección cancelada.');expect(calls).toContain('/api/workspace/browse')
})
it('does not reinterpret a persisted relative file proposal as an absolute folder or auto-apply it',async()=>{
 const f=folderFixture();render(<WorkspaceManager inline proposal={{intent:'create',name:'Human proposal',path:'notes/relative.txt'}}/>);await ready();expect(pathInput().value).toBe('D:/selected-project');expect((screen.getByLabelText('Nombre de carpeta') as HTMLInputElement).value).toBe('Human proposal');expect(f.mutations()).toEqual([])
})
it('keeps an existing Unicode folder and canonical project metadata without implying a rename',async()=>{
 const root='D:/Empresa Ñ/Proyecto válido',registered=workspace(root,'Proyecto válido','TÍTULO CANÓNICO')
 const f=folderFixture({root,workspaces:[registered],plan:normal=>({...normal,name:registered.name,title:registered.title})});render(<WorkspaceManager/>);await ready()
 expect(pathInput().value).toBe(root);expect((screen.getByLabelText('Título del proyecto') as HTMLInputElement).value).toBe(registered.title)
 fireEvent.change(screen.getByLabelText('Título del proyecto'),{target:{value:'Different draft'}});await prepare();expect(dialog().textContent).toContain(registered.title);expect(dialog().textContent).not.toContain('Different draft')
 accept();confirm();await screen.findByText(/El servicio confirmó la carpeta activa/);expect(f.getRoot()).toBe(root);expect((screen.getByLabelText('Título del proyecto') as HTMLInputElement).value).toBe(registered.title)
})
it('does not resurrect a plan or issue an apply when its prepare response arrives after unmount',async()=>{
 const pending=deferred<unknown>();let input:any;const f=folderFixture({route:(url,body)=>{if(url==='/api/project-folders/v1/plans'){input=body;return pending.promise}}}),view=render(<WorkspaceManager/>);await ready();fireEvent.click(useFolder());view.unmount();await act(async()=>pending.resolve(reply(planFor(input))));expect(f.mutations()).toHaveLength(1)
})
