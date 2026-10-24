// @vitest-environment jsdom
import React from 'react'
import {afterEach,beforeEach,expect,it,vi} from 'vitest'
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import Communications from '../../src/components/Communications'
import {resetLocaleForTests} from '../../src/i18n'
const contact={id:'fixture-contact',name:'EMPRESA FICTICIA',phone:'+12025550123'}
const other={id:'fixture-other',name:'OTRA EMPRESA FICTICIA',phone:'+12025550124'}
const draft={id:'fixture-draft',revision:'fixture-revision',contact_id:contact.id,recipient:contact,text:'Resultado guardado ficticio',attachments:[],schedule:{kind:'now',timezone:'Europe/Madrid',at:null,time:null,weekdays:[]},state:'draft',next_run_at:null,created_at:'',updated_at:'',conversation_id:'fixture-conversation',last_error:null}
const response=(body:unknown)=>({ok:true,status:200,json:async()=>body})
let writes:string[]=[]
function fixture(overrides:Partial<typeof draft>={},runs?:()=>Promise<unknown>){
 vi.stubGlobal('fetch',vi.fn(async(input:string,init?:RequestInit)=>{
  const path=String(input);if(init?.method&&init.method!=='GET')writes.push(path)
  if(path.endsWith('/contacts'))return response({contacts:[contact]})
  if(path.endsWith('/drafts'))return response({drafts:[{...draft,...overrides}]})
  if(path.endsWith('/runs'))return runs?runs():response({runs:[]})
  if(path.includes('/drafts/'))return response({...draft,...overrides})
  throw new Error(`Unexpected fixture request ${path}`)
 }))
}
beforeEach(()=>{localStorage.clear();resetLocaleForTests();writes=[];fixture()})
afterEach(()=>{expect(writes).toEqual([]);cleanup();vi.unstubAllGlobals()})
it('defaults to Message; removes top tabs and embedded Contacts; mounts library only in Message',async()=>{
 const {container,rerender}=render(<Communications draftId={draft.id}/>);await screen.findByDisplayValue(draft.text)
 expect(screen.queryByRole('tablist')).toBeNull();expect(container.querySelector('.contacts-page')).toBeNull()
 expect(container.querySelectorAll('aside.communications-library')).toHaveLength(1)
 expect(screen.getByRole('region',{name:'Mensaje'})).toBeTruthy()
 rerender(<Communications draftId={draft.id} activeSection="history"/>)
 expect(container.querySelector('aside.communications-library')).toBeNull()
 expect(screen.getByRole('region',{name:'Historial'})).toBeTruthy()
 expect(screen.queryByRole('region',{name:'Mensaje'})).toBeNull()
 rerender(<Communications draftId={draft.id} activeSection="message"/>)
 expect(container.querySelector('aside.communications-library')?.hasAttribute('hidden')).toBe(false)
 for(const element of container.querySelectorAll('[aria-labelledby]'))for(const id of element.getAttribute('aria-labelledby')!.split(/\s+/))expect(document.getElementById(id)).toBeTruthy()
})
it('keeps the library absent inline in both externally selected sections',async()=>{
 const {container,rerender}=render(<Communications inline draftId={draft.id}/>);await screen.findByDisplayValue(draft.text)
 for(const activeSection of ['history','message'] as const){rerender(<Communications inline draftId={draft.id} activeSection={activeSection}/>);expect(container.querySelector('aside.communications-library')).toBeNull();expect(screen.queryByRole('tablist')).toBeNull()}
})
it('preserves saved review on navigation; preserves dirty message, attachments and calendar and revokes review on edit',async()=>{
 const {rerender}=render(<Communications draftId={draft.id}/>);await screen.findByDisplayValue(draft.text)
 fireEvent.click(screen.getByLabelText(/He revisado/))
 rerender(<Communications draftId={draft.id} activeSection="history"/>);rerender(<Communications draftId={draft.id}/>)
 expect((screen.getByLabelText(/He revisado/) as HTMLInputElement).checked).toBe(true)
 fireEvent.change(screen.getByRole('textbox',{name:'Mensaje'}),{target:{value:'Edición local ficticia'}})
 fireEvent.change(screen.getByLabelText(/Adjuntos del espacio/),{target:{value:'resultados/ficticio.pdf'}})
 fireEvent.change(screen.getByLabelText('Cuándo'),{target:{value:'weekly'}})
 fireEvent.change(screen.getByLabelText('Hora local'),{target:{value:'11:45'}})
 fireEvent.click(screen.getByLabelText('Lunes'))
 rerender(<Communications draftId={draft.id} activeSection="history"/>);rerender(<Communications draftId={draft.id}/>)
 expect((screen.getByRole('textbox',{name:'Mensaje'}) as HTMLTextAreaElement).value).toBe('Edición local ficticia')
 expect((screen.getByLabelText(/Adjuntos del espacio/) as HTMLTextAreaElement).value).toBe('resultados/ficticio.pdf')
 expect((screen.getByLabelText('Cuándo') as HTMLSelectElement).value).toBe('weekly')
 expect((screen.getByLabelText('Hora local') as HTMLInputElement).value).toBe('11:45')
 expect((screen.getByLabelText('Lunes') as HTMLInputElement).checked).toBe(true)
 expect(screen.queryByLabelText(/He revisado/)).toBeNull()
})
it('accepts a newly requested contact without resetting dirty message or schedule',async()=>{
 const {rerender}=render(<Communications draftId={draft.id}/>);await screen.findByDisplayValue(draft.text)
 fireEvent.change(screen.getByRole('textbox',{name:'Mensaje'}),{target:{value:'Mensaje conservado'}})
 fireEvent.change(screen.getByLabelText('Cuándo'),{target:{value:'daily'}})
 fireEvent.change(screen.getByLabelText('Hora local'),{target:{value:'12:15'}})
 rerender(<Communications draftId={draft.id} initialContact={other}/>)
 expect((screen.getByLabelText('Destinatario') as HTMLSelectElement).value).toBe(other.id)
 expect((screen.getByRole('textbox',{name:'Mensaje'}) as HTMLTextAreaElement).value).toBe('Mensaje conservado')
 expect((screen.getByLabelText('Cuándo') as HTMLSelectElement).value).toBe('daily')
 expect((screen.getByLabelText('Hora local') as HTMLInputElement).value).toBe('12:15')
})
it('uses initial contact in an independent mount and invalidates saved approval when contact changes',async()=>{
 const view=render(<Communications initialContact={other}/>);await screen.findByRole('option',{name:/OTRA EMPRESA/})
 expect((screen.getByLabelText('Destinatario') as HTMLSelectElement).value).toBe(other.id)
 view.unmount()
 const {rerender}=render(<Communications draftId={draft.id}/>);await screen.findByDisplayValue(draft.text)
 fireEvent.click(screen.getByLabelText(/He revisado/));rerender(<Communications draftId={draft.id} initialContact={other}/>)
 expect(screen.queryByRole('button',{name:'Confirmar y enviar ahora'})).toBeNull()
})
it('rejects a contact request while busy and does not apply it when the operation finishes',async()=>{
 let resolveRuns:(value:unknown)=>void=()=>{};let count=0
 fixture({},()=>++count===1?Promise.resolve(response({runs:[]})):new Promise(resolve=>{resolveRuns=resolve}))
 const {rerender}=render(<Communications draftId={draft.id}/>);await screen.findByDisplayValue(draft.text)
 rerender(<Communications draftId={draft.id} activeSection="history"/>);fireEvent.click(screen.getByRole('button',{name:'Actualizar historial'}))
 rerender(<Communications draftId={draft.id} activeSection="history" initialContact={other}/>)
 await screen.findByRole('alert');resolveRuns(response({runs:[]}))
 await waitFor(()=>expect((screen.getByRole('button',{name:'Actualizar historial'}) as HTMLButtonElement).disabled).toBe(false))
 rerender(<Communications draftId={draft.id} initialContact={other}/>)
 expect((screen.getByLabelText('Destinatario') as HTMLSelectElement).value).toBe(contact.id)
 rerender(<Communications draftId={draft.id} initialContact={{...other}}/>)
 expect((screen.getByLabelText('Destinatario') as HTMLSelectElement).value).toBe(other.id)
})
it.each(['sent','sending','cancelled','uncertain'])('rejects contact on readonly %s initial mount',async state=>{
 fixture({state});render(<Communications draftId={draft.id} initialContact={other}/>);await screen.findByDisplayValue(draft.text)
 expect(screen.getByRole('alert')).toBeTruthy()
 expect((screen.getByLabelText('Destinatario') as HTMLSelectElement).value).toBe(contact.id)
})
it('rejects a new contact on an already loaded readonly draft',async()=>{
 fixture({state:'sent'});const {rerender}=render(<Communications draftId={draft.id}/>);await screen.findByDisplayValue(draft.text)
 rerender(<Communications draftId={draft.id} initialContact={other}/>)
 expect(screen.getByRole('alert')).toBeTruthy()
 expect((screen.getByLabelText('Destinatario') as HTMLSelectElement).value).toBe(contact.id)
})
