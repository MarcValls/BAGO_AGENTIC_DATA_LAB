// @vitest-environment jsdom
import React from 'react'
import {afterEach,beforeEach,expect,it,vi} from 'vitest'
import {act,cleanup,fireEvent,render,screen,waitFor,within} from '@testing-library/react'
import {readFileSync} from 'node:fs'
import postcss from 'postcss'
import AgentChat from '../../../src/components/AgentChat'
import {resetLocaleForTests,setLocale} from '../../../src/i18n'

beforeEach(()=>{localStorage.clear();resetLocaleForTests();setLocale('es');HTMLElement.prototype.scrollIntoView=vi.fn()})
afterEach(()=>{cleanup();vi.restoreAllMocks();vi.unstubAllGlobals()})
const messages=[{id:'u-first',role:'user',content:'Primera pregunta exacta'},
 {id:'a-first',role:'assistant',content:'Primera respuesta exacta'},
 {id:'u-last',role:'user',content:'Última pregunta exacta\ncon segunda línea'},
 {id:'a-last',role:'assistant',content:'Última respuesta exacta'}]
async function fixture(status='active',storedMessages=messages){
 const calls:Array<{url:string;method:string}>=[]
 const first={id:'conv-message-A',owner_kind:'assistant',owner_id:'app-assistant',title:'Conversación A',status,updated_at:'2026-10-23T10:00:00Z',revision:3}
 const second={...first,id:'conv-message-B',title:'Conversación B',revision:1}
 vi.stubGlobal('fetch',vi.fn(async(input:string,init?:RequestInit)=>{
  const url=String(input);calls.push({url,method:init?.method??'GET'})
  const body=url==='/api/agents/list'?{agents:[{id:'agent-other',config:{name:'Otro agente',description:'Synthetic',type:'tool',tools:[],system_prompt:'Synthetic'},created_at:first.updated_at}]}
   :url==='/api/providers/chat-models'?{models:[]}:url==='/api/providers/selection'?null
   :url.startsWith('/api/conversations?')?{conversations:[first,second]}
   :url==='/api/conversations/conv-message-A'?{...first,messages:storedMessages}
   :url==='/api/conversations/conv-message-B'?{...second,messages:[{id:'u-B',role:'user',content:'Otro contexto'}]}
   :url.startsWith('/api/capabilities/proposals?')?{proposals:[]}:null
  return {ok:true,status:200,json:async()=>body}
 }))
 const copy=vi.fn().mockResolvedValue(undefined)
 Object.defineProperty(navigator,'clipboard',{value:{writeText:copy},configurable:true})
 const view=render(<AgentChat cognitiveMode="baseline" onNavigate={()=>{}} onOpenProviderSettings={()=>{}} onOpenCognitionSettings={()=>{}}/>)
 await waitFor(()=>expect(view.container.querySelectorAll('article.control-message')).toHaveLength(storedMessages.length))
 const articles=Array.from(view.container.querySelectorAll<HTMLElement>('article.control-message'))
 return {...view,articles,copy,calls}
}
it('frames author, content and inline actions together for each exact message; only latest user is editable',async()=>{
 const {articles,copy,calls}=await fixture()
 expect(articles[0].classList.contains('control-message-user')).toBe(true)
 expect(articles[1].classList.contains('control-message-assistant')).toBe(true)
 expect(within(articles[0]).getByText('Tú').id).toBe(articles[0].getAttribute('aria-labelledby'))
 expect(within(articles[1]).getByText('Asistente').id).toBe(articles[1].getAttribute('aria-labelledby'))
 expect(within(articles[0]).queryByRole('button',{name:'Editar'})).toBeNull()
 expect(within(articles[1]).queryByRole('button',{name:'Editar'})).toBeNull()
 fireEvent.click(within(articles[1]).getByRole('button',{name:'Copiar respuesta'}))
 await waitFor(()=>expect(copy).toHaveBeenLastCalledWith(messages[1].content))
 fireEvent.click(within(articles[2]).getByRole('button',{name:'Editar'}))
 const composer=screen.getByRole('textbox',{name:'Mensaje al asistente o agente seleccionado'}) as HTMLTextAreaElement
 expect(composer.value).toBe(messages[2].content);expect(document.activeElement).toBe(composer)
 expect(calls.every(call=>call.method==='GET')).toBe(true)
})
it('right click targets one message and contextual copy copies only that response, restoring focus',async()=>{
 const {articles,copy,calls}=await fixture()
 fireEvent.contextMenu(articles[1],{clientX:90,clientY:80})
 const menu=screen.getByRole('menu',{name:'Asistente'})
 expect(within(menu).queryByRole('menuitem',{name:'Editar'})).toBeNull()
 fireEvent.click(within(menu).getByRole('menuitem',{name:'Copiar respuesta'}))
 await waitFor(()=>expect(copy).toHaveBeenCalledWith(messages[1].content))
 expect(screen.queryByRole('menu')).toBeNull();expect(document.activeElement).toBe(articles[1])
 expect(calls.every(call=>call.method==='GET')).toBe(true)
})
it('switching the contextual target cannot retain an old user edit action',async()=>{
 const {articles,copy}=await fixture()
 fireEvent.contextMenu(articles[2]);expect(screen.getByRole('menuitem',{name:'Editar'})).not.toBeNull()
 fireEvent.contextMenu(articles[0]);expect(screen.queryByRole('menuitem',{name:'Editar'})).toBeNull()
 fireEvent.click(screen.getByRole('menuitem',{name:'Copiar mensaje'}))
 await waitFor(()=>expect(copy).toHaveBeenLastCalledWith(messages[0].content))
})
it('contextual edit only prepares the existing composer without sending or mutating a stored message',async()=>{
 const {articles,calls}=await fixture()
 fireEvent.contextMenu(articles[2]);fireEvent.click(screen.getByRole('menuitem',{name:'Editar'}))
 const composer=screen.getByRole('textbox',{name:'Mensaje al asistente o agente seleccionado'}) as HTMLTextAreaElement
 expect(composer.value).toBe(messages[2].content);expect(document.activeElement).toBe(composer)
 expect(articles[2].querySelector('.control-message-content')?.textContent).toBe(messages[2].content)
 expect(screen.queryByRole('menu')).toBeNull();expect(calls.every(call=>call.method==='GET')).toBe(true)
})
it('keeps editing disabled for an archived conversation in both inline and context actions',async()=>{
 const {articles,copy}=await fixture('archived')
 expect((within(articles[2]).getByRole('button',{name:'Editar'}) as HTMLButtonElement).disabled).toBe(true)
 fireEvent.contextMenu(articles[2]);const edit=screen.getByRole('menuitem',{name:'Editar'}) as HTMLButtonElement
 expect(edit.disabled).toBe(true);fireEvent.click(edit)
 expect((screen.getByRole('textbox',{name:'Mensaje al asistente o agente seleccionado'}) as HTMLTextAreaElement).value).toBe('')
 expect(copy).not.toHaveBeenCalled()
})
it('supports ContextMenu and Shift F10, focus navigation, Escape restoration and Tab dismissal',async()=>{
 const {articles}=await fixture()
 articles[2].focus();fireEvent.keyDown(articles[2],{key:'ContextMenu'})
 const copy=screen.getByRole('menuitem',{name:'Copiar mensaje'}),edit=screen.getByRole('menuitem',{name:'Editar'})
 expect(document.activeElement).toBe(copy)
 fireEvent.keyDown(copy,{key:'ArrowDown'});expect(document.activeElement).toBe(edit)
 fireEvent.keyDown(edit,{key:'Home'});expect(document.activeElement).toBe(copy)
 fireEvent.keyDown(copy,{key:'End'});expect(document.activeElement).toBe(edit)
 fireEvent.keyDown(edit,{key:'ArrowDown'});expect(document.activeElement).toBe(copy)
 fireEvent.keyDown(copy,{key:'ArrowUp'});expect(document.activeElement).toBe(edit)
 fireEvent.keyDown(edit,{key:'Escape'});expect(screen.queryByRole('menu')).toBeNull();expect(document.activeElement).toBe(articles[2])
 fireEvent.keyDown(articles[2],{key:'F10',shiftKey:true});expect(screen.getByRole('menu')).not.toBeNull()
 fireEvent.keyDown(screen.getByRole('menu'),{key:'Tab'});expect(screen.queryByRole('menu')).toBeNull()
})
it('dismisses on outside click, resize and scroll, and clamps menu to viewport',async()=>{
 const {articles}=await fixture()
 vi.spyOn(HTMLElement.prototype,'getBoundingClientRect').mockReturnValue({left:0,top:0,right:180,bottom:100,width:180,height:100,x:0,y:0,toJSON:()=>({})})
 vi.stubGlobal('innerWidth',320);vi.stubGlobal('innerHeight',200)
 fireEvent.contextMenu(articles[2],{clientX:315,clientY:199})
 const menu=screen.getByRole('menu');expect(menu.style.left).toBe('132px');expect(menu.style.top).toBe('92px')
 fireEvent.pointerDown(document.body);expect(screen.queryByRole('menu')).toBeNull()
 fireEvent.contextMenu(articles[2]);fireEvent(window,new Event('resize'));expect(screen.queryByRole('menu')).toBeNull()
 fireEvent.contextMenu(articles[2]);fireEvent.scroll(articles[2].parentElement!);expect(screen.queryByRole('menu')).toBeNull()
})
it('discards menu on every conversation change before a stale action can run, with no legacy agent selector',async()=>{
 const {articles,copy,calls}=await fixture()
 fireEvent.contextMenu(articles[2]);fireEvent.click(screen.getByRole('button',{name:/Conversación B/}))
 await screen.findByText('Otro contexto');expect(screen.queryByRole('menu')).toBeNull();expect(copy).not.toHaveBeenCalled()
 const other=screen.getByText('Otro contexto').closest('article')!
 fireEvent.contextMenu(other);expect(screen.queryByRole('button',{name:/Otro agente/})).toBeNull();fireEvent.click(screen.getByRole('button',{name:/Conversación A/}));await screen.findByText(messages[1].content);expect(screen.queryByRole('menu')).toBeNull();expect(copy).not.toHaveBeenCalled();expect(calls.every(c=>c.method==='GET')).toBe(true)
})
it('does not hijack editable embedded fields or offer actions on a missing response',async()=>{
 const {articles}=await fixture('active',[{id:'empty',role:'assistant',content:'',status:'failed'}])
 fireEvent.contextMenu(articles[0]);expect(screen.queryByRole('menu')).toBeNull()
 cleanup()
 const next=await fixture();const field=document.createElement('textarea');next.articles[0].appendChild(field)
 const event=new MouseEvent('contextmenu',{bubbles:true,cancelable:true});field.dispatchEvent(event)
 expect(event.defaultPrevented).toBe(false);expect(screen.queryByRole('menu')).toBeNull();field.remove()
})
it('keeps clipboard failures attached to their original message and supports EN labels without altering payload',async()=>{
 const {articles,copy}=await fixture();copy.mockRejectedValueOnce(new Error('clipboard denied'))
 fireEvent.contextMenu(articles[1]);fireEvent.click(screen.getByRole('menuitem',{name:'Copiar respuesta'}))
 await waitFor(()=>expect(within(articles[1]).getByRole('button',{name:'No se pudo copiar'})).not.toBeNull())
 act(()=>setLocale('en'));fireEvent.contextMenu(articles[2])
 expect(screen.getByRole('menu',{name:'You'})).not.toBeNull()
 fireEvent.click(screen.getByRole('menuitem',{name:'Copy message'}))
 await waitFor(()=>expect(copy).toHaveBeenLastCalledWith(messages[2].content))
})
it('defines one bounded frame with an internal action heading and different role composition, without hiding rich outputs',()=>{
 const css=postcss.parse(readFileSync('src/components/ChatMessage.css','utf8'))
 const declarations=(selector:string)=>{const out:Record<string,string>={};css.walkRules(rule=>{if(rule.selector===selector)rule.walkDecls(d=>{out[d.prop]=d.value})});return out}
 expect(declarations('.control-chat .control-message')['border-inline-start-width']).toBe('4px')
 expect(declarations('.control-chat .control-message-user')['border-inline-end-width']).toBe('4px')
 expect(declarations('.control-chat .control-message-user')['margin-inline-start']).toBe('auto')
 expect(declarations('.control-chat .control-message > .control-message-heading').margin).toBe('0')
 expect(declarations('.control-chat .control-message').overflow).toBeUndefined()
 expect(declarations('.chat-message-context-menu')['max-width']).toBe('calc(100vw - 16px)')
})
