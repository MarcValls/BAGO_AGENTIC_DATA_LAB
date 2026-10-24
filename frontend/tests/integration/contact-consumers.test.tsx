// @vitest-environment jsdom
import React from 'react'
import {afterEach, expect, it, vi} from 'vitest'
import {cleanup, fireEvent, render, screen, waitFor} from '@testing-library/react'
import ChatTools from '../../src/components/ChatTools'
import App from '../../src/App'
import {t} from '../../src/i18n'
const contact={id:'canonical-id',name:'FICTICIO',phone:'+34600000001',email:'',source:'local',source_id:'',revision:'r',created_at:'',updated_at:''}
const emailOnly={...contact,id:'email-only',name:'Solo correo FICTICIO',phone:'',email:'fixture@example.invalid'}
const response=(body:unknown)=>({ok:true,status:200,json:async()=>body})
afterEach(()=>{cleanup();vi.unstubAllGlobals()})
function fixture(){
 const writes:any[]=[]
 vi.stubGlobal('fetch',vi.fn(async(url:string,init?:RequestInit)=>{
  if(init?.method==='POST'){
   const body=JSON.parse(String(init.body));writes.push({url,body})
   return response({...body,id:'saved-canonical-draft',revision:'a'.repeat(64),recipient:contact,attachments:[],state:'draft',last_error:null})
  }
  if(url.startsWith('/api/contacts/v1/contacts'))return response({contacts:[contact,emailOnly]})
  if(url==='/api/contacts/v1/google/status')return response({configured:false,connected:false,state:'unconfigured',scope:'contacts.readonly',live_verified:false,last_error:null})
  if(url==='/api/communications/contacts')return response({contacts:[contact,emailOnly]})
  if(url.endsWith('/drafts'))return response({drafts:[]})
  if(url.endsWith('/runs'))return response({runs:[]})
  return response({})
 }))
 return writes
}
it('manual chat tool uses real shared contacts and creates only a reviewed draft with canonical ID',async()=>{
 HTMLDialogElement.prototype.showModal=function(){this.open=true}
 HTMLDialogElement.prototype.close=function(){this.open=false}
 const writes=fixture();const open=vi.fn()
 render(<ChatTools conversationId="conv-canonical" onOpenCommunication={open} />)
 fireEvent.click(screen.getByRole('button',{name:'Contactos'}))
 const prepare=await screen.findAllByRole('button',{name:'Preparar mensaje'})
 expect((prepare[1] as HTMLButtonElement).disabled).toBe(true)
 fireEvent.click(prepare[0])
 await screen.findByRole('textbox',{name:'Mensaje'})
 expect((screen.getByLabelText('Destinatario') as HTMLSelectElement).value).toBe('canonical-id')
 expect(writes).toHaveLength(0)
 fireEvent.change(screen.getByRole('textbox',{name:'Mensaje'}),{target:{value:'Texto ficticio para revisar'}})
 fireEvent.click(screen.getByRole('button',{name:'Guardar y preparar revisión'}))
 await waitFor(()=>expect(writes).toHaveLength(1))
 expect(writes[0].body.contact_id).toBe('canonical-id')
 expect(writes[0].body.conversation_id).toBe('conv-canonical')
 expect(writes[0].url).toBe('/api/communications/drafts')
 fireEvent.click(await screen.findByRole('button',{name:'Abrir pantalla completa'}))
 expect(open).toHaveBeenCalledExactlyOnceWith('saved-canonical-draft')
 expect(writes.some(item=>item.url.includes('/confirm'))).toBe(false)
})
it('full shared Contacts is reached through Communications navigation and selects a recipient without losing the message or sending',async()=>{
 HTMLDialogElement.prototype.showModal=function(){this.open=true}
 HTMLDialogElement.prototype.close=function(){this.open=false}
 HTMLElement.prototype.scrollIntoView=vi.fn()
 const writes=fixture(),view=render(<App />)
 fireEvent.click(screen.getByRole('button',{name:'Comunicaciones'}))
 expect(screen.queryByRole('textbox',{name:'Mensaje'})).toBeNull()
 fireEvent.click(screen.getByRole('button',{name:'Mensajes'}))
 const message=await screen.findByRole('textbox',{name:'Mensaje'}) as HTMLTextAreaElement
 const recipient=screen.getByLabelText('Destinatario') as HTMLSelectElement
 expect(recipient.value).toBe('');expect(writes).toHaveLength(0)
 fireEvent.change(message,{target:{value:'UNSENT_TEXT_PRESERVED'}})
 const timezone=screen.getByLabelText(t('commerce.iana_time_zone')) as HTMLInputElement
 fireEvent.change(timezone,{target:{value:'Etc/UTC'}})
 fireEvent.click(screen.getByRole('button',{name:'Contactos'}))
 const contacts=view.container.querySelector('.communications-section-panel > .contacts-page')!
 expect(contacts).not.toBeNull();expect(contacts.classList.contains('contacts-page--inline')).toBe(false)
 expect(view.container.querySelector('.communications .contacts-page')).toBeNull()
 expect(screen.queryByRole('tab',{name:'Contactos'})).toBeNull()
 const prepare=await screen.findAllByRole('button',{name:'Preparar mensaje'})
 expect((prepare[1] as HTMLButtonElement).disabled).toBe(true)
 const name=screen.getByRole('textbox',{name:t('commerce.name')}) as HTMLInputElement
 fireEvent.change(name,{target:{value:'UNSAVED_CONTACT_EDIT'}})
 expect(writes).toHaveLength(0);fireEvent.click(prepare[0])
 await waitFor(()=>expect((screen.getByLabelText('Destinatario') as HTMLSelectElement).value).toBe('canonical-id'))
 expect(screen.getByRole('button',{name:'Mensajes'}).getAttribute('aria-current')).toBe('page')
 expect(message.isConnected).toBe(true);expect(message.value).toBe('UNSENT_TEXT_PRESERVED');expect(timezone.value).toBe('Etc/UTC')
 expect(writes).toHaveLength(0)
 fireEvent.click(screen.getByRole('button',{name:'Contactos'}));expect(name.isConnected).toBe(true);expect(name.value).toBe('UNSAVED_CONTACT_EDIT')
 expect(writes.some(item=>item.url.includes('/confirm'))).toBe(false);expect(writes).toHaveLength(0)
})
