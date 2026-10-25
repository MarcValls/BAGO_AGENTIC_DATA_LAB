// @vitest-environment jsdom
import React from 'react'
import {afterEach,beforeEach,expect,it,vi} from 'vitest'
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import {resetLocaleForTests,setLocale,t} from '../../src/i18n'
vi.mock('axios',()=>({default:{get:vi.fn(async()=>({data:{}}))}}))
vi.mock('../../src/components/CognitionSettings',()=>({default:()=>null,readCognitiveMode:()=> 'baseline'}))
vi.mock('../../src/components/ProviderSettings',()=>({default:()=>null}))
import App from '../../src/App'
beforeEach(()=>{localStorage.clear();resetLocaleForTests();setLocale('es');HTMLElement.prototype.scrollIntoView=vi.fn();HTMLDialogElement.prototype.showModal=function(){this.setAttribute('open','')};HTMLDialogElement.prototype.close=function(){this.removeAttribute('open');this.dispatchEvent(new Event('close'))}})
afterEach(()=>{cleanup();vi.restoreAllMocks();vi.unstubAllGlobals()})
it('catalog to App to React draft preserves only the selected scan route until a human sends, then displays its existing consent form',async()=>{
 const calls:Array<{url:string;method:string;body:any}>=[];let conversation:any
 vi.stubGlobal('fetch',vi.fn(async(url:string,init?:RequestInit)=>{const method=init?.method??'GET',body=init?.body?JSON.parse(String(init.body)):null;calls.push({url,method,body});const ok=(data:unknown)=>({ok:true,status:200,json:async()=>data})
 if(url==='/api/capabilities')return ok({capabilities:[{id:'workspace.scan_duplicates',name:'original',provider:'local',effect:'READ',status:'AVAILABLE',integration:'CONNECTED',summary:'original',limits:{},source_fingerprints:{},source_available:false,fingerprint:'a'.repeat(64)}]})
 if(url.startsWith('/api/capabilities/proposals'))return ok({proposals:[]})
 if(url==='/api/agents/list')return ok({agents:[]})
 if(url.startsWith('/api/conversations?'))return ok({conversations:[]})
 if(url==='/api/providers/selection')return ok({provider_id:null,model_id:null})
 if(url==='/api/conversations'&&method==='POST'){conversation={id:'conv-app-route',owner_kind:'assistant',owner_id:'app-assistant',title:'Fixture',revision:1,status:'active',messages:[]};return ok(conversation)}
 if(url==='/api/chat/control'){conversation={...conversation,revision:3,messages:[{id:'u-one',role:'user',content:body.message},{id:'a-form',role:'assistant',content:'Revisa y autoriza la carpeta exacta.',references:{control_capability:'workspace.scan_duplicates'}}]};return ok({operation:'workspace_scan',conversation})}
 return ok({models:[],proposals:[]})}))
 render(<App/>);const composer=screen.getByRole('textbox',{name:'Mensaje al asistente o agente seleccionado'}) as HTMLTextAreaElement
 fireEvent.click(screen.getByRole('button',{name:'Capacidades',exact:true}));fireEvent.click(await screen.findByRole('button',{name:'Preparar con BAGO5'}));expect(await screen.findByRole('textbox',{name:'Mensaje al asistente o agente seleccionado'})).toBe(composer);await waitFor(()=>expect(composer.value).toBe(t('commerce.capability_ui.workspace.scan_duplicates.prompt')));expect(calls.every(c=>c.method==='GET')).toBe(true);expect(screen.queryByLabelText(t('core.DirectoryScanRun.project_relative_directory_d5bd1c'))).toBeNull()
 const send=screen.getByRole('button',{name:'Enviar',exact:true}) as HTMLButtonElement;await waitFor(()=>expect(send.disabled).toBe(false));fireEvent.click(send);await screen.findByLabelText(t('core.DirectoryScanRun.project_relative_directory_d5bd1c'));expect(calls.find(c=>c.url==='/api/chat/control')!.body).toMatchObject({operation:'chat',message:t('commerce.capability_ui.workspace.scan_duplicates.prompt'),capability_id:'workspace.scan_duplicates'});expect(calls.filter(c=>c.method==='POST').map(c=>c.url)).toEqual(['/api/conversations','/api/chat/control']);expect(calls.some(c=>c.url.startsWith('/api/workspace-scan/'))).toBe(false);expect((screen.getByRole('button',{name:t('core.DirectoryScanRun.scan_duplicates_bb7da0')}) as HTMLButtonElement).disabled).toBe(true)
})
