// @vitest-environment jsdom
import React from 'react'
import {webcrypto,createHash} from 'node:crypto'
import {beforeEach,afterEach,expect,it,vi} from 'vitest'
import {act,cleanup,fireEvent,render,screen,waitFor,within} from '@testing-library/react'
import AgentChat, {isHumanCorrectionSourceCurrent,type HumanCorrectionContext} from '../../src/components/AgentChat'
import {conversationButton} from '../helpers/conversation-library'
import {readPublicWebPreference} from '../../src/utils/publicWebPreference'
import HumanCorrectionReview,{type HumanCorrectionSource} from '../../src/components/HumanCorrectionReview'
import {resetLocaleForTests,setLocale} from '../../src/i18n'
beforeEach(()=>{localStorage.clear();resetLocaleForTests();setLocale('es');vi.stubGlobal('crypto',webcrypto);HTMLElement.prototype.scrollIntoView=vi.fn()})
afterEach(()=>{cleanup();vi.unstubAllGlobals();vi.restoreAllMocks()})
const response=(data:unknown,status=200)=>({ok:status<400,status,json:async()=>data})
const source:HumanCorrectionSource={ownerKind:'assistant',ownerId:'app-assistant',conversationId:'conv-a',revision:3,messageId:'a-visible',content:'Respuesta original visible: abre el Decision Inspector y lista agentes'}
async function fixture(fail=false,status='active'){
 let selectedModel:string|null=null
 let webGrantSequence=0,turnSequence=0
 let conv:any={id:'conv-a',owner_kind:'assistant',owner_id:'app-assistant',title:'Conversación corrección A',status,updated_at:'2026-10-24',revision:3,messages:[{id:'u-original',role:'user',content:'Pregunta original'},{id:source.messageId,role:'assistant',content:source.content}]}
 const second={...conv,id:'conv-b',revision:1,title:'Conversación B',messages:[{id:'a-b',role:'assistant',content:'Respuesta de B'}]}
 const writes:Array<{url:string;body:any}>=[]
 const fetcher=vi.fn(async(url:string,init?:RequestInit)=>{
 const body=init?.body?JSON.parse(String(init.body)):null
 if(init?.method&&init.method!=='GET')writes.push({url,body})
 if(url==='/api/project-folders/v1/active')return response({project_id:'project-correction',title:'Correction fixture',scope:'project',root:'D:/work/correction'})
 if(url==='/api/agents/list')return response({agents:[{id:'other-agent',config:{name:'Agente alternativo',description:'fixture',type:'tool',system_prompt:'fixture',tools:[]},created_at:'2026-10-24'}]})
 if(url==='/api/providers/selection')return response({provider_id:selectedModel?'ollama-cloud':null,model_id:selectedModel})
 if(url.startsWith('/api/conversations?'))return response({conversations:[conv,second]})
 if(url==='/api/conversations/conv-a')return response(conv)
 if(url==='/api/conversations/conv-b')return response(second)
 if(url==='/api/web-read/authorizations')return response({authorization_id:`new-explicit-grant-${++webGrantSequence}`,allowed_origins:['https://example.com']})
 if(url==='/api/chat/control'){
  if(fail)return response({detail:'Fallo sintético del proveedor'},500)
  turnSequence++;conv={...conv,revision:conv.revision+1,messages:[...conv.messages,{id:`u-correction-${turnSequence}`,role:'user',content:body.message},{id:`a-corrected-${turnSequence}`,role:'assistant',content:'Respuesta corregida fixture'}]}
  return response({operation:'chat',conversation:conv})
 }
 return response({models:[],proposals:[]})
 });vi.stubGlobal('fetch',fetcher)
 const view=render(<AgentChat cognitiveMode="baseline" onNavigate={vi.fn()} onOpenProviderSettings={()=>{}} onOpenCognitionSettings={()=>{}}/>);
 await waitFor(()=>expect(view.container.querySelectorAll('article.control-message')).toHaveLength(2));await act(async()=>{})
 const original=Array.from(view.container.querySelectorAll('article.control-message')).find(a=>a.textContent?.includes(source.content))!
 const trigger=within(original as HTMLElement).getByRole('button',{name:'Corregir interpretación'})
 const draft=screen.getByRole('textbox',{name:'Mensaje al asistente o agente seleccionado'}) as HTMLTextAreaElement
 fireEvent.change(draft,{target:{value:'Borrador previo que debe conservarse'}})
 return {view,writes,fetcher,original,trigger,draft,changeModel:(model:string)=>{selectedModel=model},changeSource:(content=source.content,revision=3)=>{conv={...conv,revision,messages:[conv.messages[0],{id:source.messageId,role:'assistant',content}]}}}
}
async function prepare(text='Necesito una explicación distinta, sin navegar'){
 const editor=screen.getByRole('textbox',{name:'Mi intención corregida'}) as HTMLTextAreaElement
 fireEvent.change(editor,{target:{value:text}});fireEvent.click(screen.getByRole('button',{name:'Preparar corrección'}));await screen.findByRole('button',{name:'Rehacer con esta corrección'});return editor
}
it('opens only from concrete assistant, prepares and cancels with zero mutations, original/draft/focus intact',async()=>{
 const f=await fixture();fireEvent.click(f.trigger);const editor=await prepare();expect(document.activeElement).toBe(editor);expect(f.writes).toEqual([]);expect(f.original.textContent).toContain(source.content);expect(f.draft.value).toContain('Borrador previo');fireEvent.click(screen.getByRole('button',{name:'Cancelar corrección'}));expect(screen.queryByRole('region',{name:'Corrección humana de intención'})).toBeNull();expect(document.activeElement).toBe(f.trigger);expect(f.draft.value).toContain('Borrador previo');expect(f.writes).toEqual([])
})
it('explicit correction sends once via existing chat with operation chat, exact source and no inherited permissions',async()=>{
 const f=await fixture();fireEvent.click(f.trigger);await prepare('Abre el Inspector y lista capacidades, pero corrige mi intención');const send=screen.getByRole('button',{name:'Rehacer con esta corrección'});fireEvent.click(send);fireEvent.click(send);await screen.findByText('Respuesta corregida fixture');expect(f.writes).toHaveLength(1);expect(f.writes[0].url).toBe('/api/chat/control');expect(f.writes[0].body).toMatchObject({operation:'chat',conversation_id:'conv-a',revision:3});expect(f.writes[0].body.message).toContain(source.messageId);expect(f.writes[0].body.message).toContain('SHA-256 de la respuesta visible: '+createHash('sha256').update(source.content).digest('hex'));expect(f.writes[0].body.workspace_read_authorization_id).toBeUndefined();expect(f.writes[0].body.web_read_authorization_id).toBeUndefined();expect(f.draft.value).toContain('Borrador previo');expect(f.view.container.querySelectorAll('article.control-message')[1].textContent).toContain(source.content)
})
it('uses current conversation web preference with fresh grants while preserving correction hash and ordinary dispatch',async()=>{
 const f=await fixture()
 const draft='Borrador previo que debe conservarse https://example.com/'
 fireEvent.change(f.draft,{target:{value:draft}})
 await waitFor(()=>expect((screen.getByLabelText('Permitir lectura web pública') as HTMLInputElement).disabled).toBe(false))
 fireEvent.click(screen.getByLabelText('Permitir lectura web pública'))
 expect(screen.queryByLabelText('URL HTTPS de entrada · una por línea')).toBeNull()
 fireEvent.click(f.trigger);await prepare();fireEvent.click(screen.getByRole('button',{name:'Rehacer con esta corrección'}))
 await screen.findByText('Respuesta corregida fixture')
 expect(f.writes.map(w=>w.url)).toEqual(['/api/web-read/authorizations','/api/chat/control'])
 expect(f.writes[0].body).toEqual({owner_kind:'assistant',owner_id:'app-assistant',conversation_id:'conv-a',revision:3,urls:['https://example.com/']})
 expect(f.writes[1].body.web_read_authorization_id).toBe('new-explicit-grant-1')
 expect(f.writes[1].body.message).toContain('SHA-256 de la respuesta visible: '+createHash('sha256').update(source.content).digest('hex'))
 expect(f.draft.value).toBe(draft)
 expect((screen.getByLabelText('Permitir lectura web pública') as HTMLInputElement).checked).toBe(true)
 const identity={projectId:'project-correction',root:'D:/work/correction',ownerKind:'assistant' as const,ownerId:'app-assistant',conversationId:'conv-a'}
 expect(readPublicWebPreference(identity).preference).toEqual({enabled:true,urls:'https://example.com/'})
 fireEvent.change(f.draft,{target:{value:'Continúa en https://example.com/next'}});fireEvent.click(screen.getByRole('button',{name:'Enviar',exact:true}))
 await waitFor(()=>expect(f.writes).toHaveLength(4))
 expect(f.writes[2].body).toMatchObject({owner_kind:'assistant',owner_id:'app-assistant',conversation_id:'conv-a',revision:4})
 expect(f.writes[3].body.web_read_authorization_id).toBe('new-explicit-grant-2')
 expect(JSON.stringify(localStorage)).not.toContain('new-explicit-grant')
})

it('a different conversation blocks prepared correction without discarding human text or sending',async()=>{
 const f=await fixture();fireEvent.click(f.trigger);const editor=await prepare();fireEvent.click(conversationButton(document,'Conversación B'));await screen.findByText('Respuesta de B');expect(await screen.findByText(/El contexto de la respuesta cambió/)).toBeTruthy();expect(editor.value).toContain('explicación distinta');expect(screen.queryByRole('button',{name:'Rehacer con esta corrección'})).toBeNull();expect(f.writes).toEqual([])
})
it.each([['Contenido fuente cambiado',3],[source.content,4]])('rejects source or revision drift on reloading same conversation: %s/%s',async(content,revision)=>{
 const f=await fixture();fireEvent.click(f.trigger);const editor=await prepare();f.changeSource(content,revision);fireEvent.click(conversationButton(document,'Conversación corrección A'));await screen.findByText(/El contexto de la respuesta cambió/);expect(editor.value).toContain('explicación distinta');expect((screen.getByRole('button',{name:'Preparar corrección'}) as HTMLButtonElement).disabled).toBe(true);expect(f.writes).toEqual([])
})
it('provider failure keeps correction and original composer draft, with no automatic retry',async()=>{
 const f=await fixture(true);fireEvent.click(f.trigger);const editor=await prepare();fireEvent.click(screen.getByRole('button',{name:'Rehacer con esta corrección'}));expect((await screen.findByRole('alert')).textContent).toBeTruthy();expect(editor.value).toContain('explicación distinta');expect(f.draft.value).toContain('Borrador previo');expect(f.writes).toHaveLength(1);expect(f.original.textContent).toContain(source.content)
})
it('changing permission identity invalidates review without erasing text or granting anything',async()=>{
 const onSend=vi.fn(),onCancel=vi.fn();const view=render(<HumanCorrectionReview source={source} current busy={false} permissions="sin permiso" permissionIdentity="off" onSend={onSend} onCancel={onCancel}/>);const editor=await prepare();view.rerender(<HumanCorrectionReview source={source} current busy={false} permissions="permiso actual" permissionIdentity="on" onSend={onSend} onCancel={onCancel}/>);expect(screen.queryByRole('button',{name:'Rehacer con esta corrección'})).toBeNull();expect(editor.value).toContain('explicación distinta');expect(onSend).not.toHaveBeenCalled();fireEvent.keyDown(editor,{key:'Escape'});expect(onCancel).toHaveBeenCalledTimes(1)
})

it.each(['ownerKind','ownerId','conversationId'] as const)('a changed %s binding invalidates correction while preserving original text, draft and zero dispatch',async(field)=>{
 const fetcher=vi.fn(),send=vi.fn();vi.stubGlobal('fetch',fetcher)
 const context:HumanCorrectionContext={ownerKind:'assistant',ownerId:'app-assistant',conversation:{id:'conv-a',revision:3,status:'active',owner_kind:'assistant',owner_id:'app-assistant'},messages:[{id:source.messageId,role:'assistant',content:source.content}]}
 expect(isHumanCorrectionSourceCurrent(source,context)).toBe(true)
 const props={source,current:true,busy:false,permissions:'Sin permisos nuevos',onSend:send,onCancel:vi.fn()}
 const view=render(<><textarea aria-label="Borrador original" defaultValue="Borrador exacto conservado"/><HumanCorrectionReview {...props}/></>);const editor=await prepare()
 const changed:HumanCorrectionContext=field==='ownerKind'?{...context,ownerKind:'agent'}:field==='ownerId'?{...context,ownerId:'other-owner'}:{...context,conversation:{...context.conversation!,id:'another-conversation'}}
 expect(isHumanCorrectionSourceCurrent(source,changed)).toBe(false)
 view.rerender(<><textarea aria-label="Borrador original" defaultValue="Borrador exacto conservado"/><HumanCorrectionReview {...props} current={isHumanCorrectionSourceCurrent(source,changed)}/></>);await screen.findByText(/El contexto de la respuesta cambió/)
 expect(editor.value).toContain('explicación distinta');expect(screen.queryByRole('button',{name:'Rehacer con esta corrección'})).toBeNull();expect((screen.getByLabelText('Borrador original') as HTMLTextAreaElement).value).toBe('Borrador exacto conservado');expect(context.messages[0].content).toBe(source.content);expect(send).not.toHaveBeenCalled();expect(fetcher).not.toHaveBeenCalled()
})
it('rejects a stored conversation whose owner disagrees with the current binding',()=>{
 const context:HumanCorrectionContext={ownerKind:'assistant',ownerId:'app-assistant',conversation:{id:'conv-a',revision:3,status:'active',owner_kind:'agent',owner_id:'app-assistant'},messages:[{id:source.messageId,role:'assistant',content:source.content}]};expect(isHumanCorrectionSourceCurrent(source,context)).toBe(false)
})
it('archived conversation cannot open a correction',async()=>{
 const f=await fixture(false,'archived');expect((f.trigger as HTMLButtonElement).disabled).toBe(true);fireEvent.click(f.trigger);expect(screen.queryByRole('region',{name:'Corrección humana de intención'})).toBeNull();expect(f.writes).toEqual([])
})
it('hash failure denies preparation without losing text or calling send',async()=>{
 vi.stubGlobal('crypto',{subtle:{digest:vi.fn(async()=>{throw new Error('synthetic unavailable')})}});const send=vi.fn();render(<HumanCorrectionReview source={source} current busy={false} permissions="sin permisos" onSend={send} onCancel={()=>{}}/>);const editor=screen.getByRole('textbox',{name:'Mi intención corregida'}) as HTMLTextAreaElement;fireEvent.change(editor,{target:{value:'Texto humano recuperable'}});fireEvent.click(screen.getByRole('button',{name:'Preparar corrección'}));await screen.findByText(/No se pudo preparar la identidad/);expect(editor.value).toBe('Texto humano recuperable');expect(screen.queryByRole('button',{name:'Rehacer con esta corrección'})).toBeNull();expect(send).not.toHaveBeenCalled()
})

it('confirmed model change invalidates prepared correction and preserves editor without any dispatch',async()=>{
 const f=await fixture();fireEvent.click(f.trigger);const editor=await prepare();f.changeModel('different-current-model');act(()=>window.dispatchEvent(new Event('adl-model-policy-changed')));await waitFor(()=>expect(screen.queryByRole('button',{name:'Rehacer con esta corrección'})).toBeNull());expect(editor.value).toContain('explicación distinta');expect(f.writes).toEqual([]);fireEvent.click(screen.getByRole('button',{name:'Preparar corrección'}));await screen.findByRole('button',{name:'Rehacer con esta corrección'});expect(f.writes).toEqual([])
})
