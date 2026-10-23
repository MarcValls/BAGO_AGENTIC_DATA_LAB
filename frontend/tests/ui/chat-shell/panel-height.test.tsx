// @vitest-environment jsdom
import React from 'react'
import {beforeEach,afterEach,expect,it,vi} from 'vitest'
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import {readFileSync} from 'node:fs'
import postcss from 'postcss'
import AgentChat from '../../../src/components/AgentChat'
import {resetLocaleForTests} from '../../../src/i18n'
const css=readFileSync('src/components/AgentChat.css','utf8')
function declarations(selector:string){const result:Record<string,string>={};postcss.parse(css).walkRules(rule=>{if(rule.selector===selector)rule.walkDecls(d=>{result[d.prop]=d.value})});return result}
beforeEach(()=>{localStorage.clear();resetLocaleForTests()})
afterEach(()=>{cleanup();vi.unstubAllGlobals();vi.restoreAllMocks()})
it('fills the owner only while open with no half-height cap or positive minimum',()=>{
 const open=declarations('.control-chat .chat-agent-panel-slot:has(.chat-agent-panel[open])')
 expect(open['max-height']).toBe('none');expect(open['min-height']).toBe('0');expect(open.height).toBeUndefined()
 expect(open.flex).toBe('1 1 0');expect(open.overflow).toBe('hidden');expect(open.width).toBe('100%');expect(open['min-width']).toBe('0')
 const collapsed=declarations('.chat-agent-panel-slot')
 expect(collapsed.flex).toBe('0 0 auto');expect(collapsed.height).toBeUndefined();expect(collapsed['max-height']).toBeUndefined()
 expect(declarations('.control-chat .control-chat-messages').flex).toBe('1 1 0')
 expect(declarations('.control-chat-composer').flex).toBe('0 0 auto')
})
it('keeps summary outside the shrinking scrolling body and preserves responsive inner panes',()=>{
 const details=declarations('.control-chat .chat-agent-panel-slot > .chat-agent-panel[open]')
 expect(details.display).toBe('flex');expect(details['flex-direction']).toBe('column');expect(details.overflow).toBe('hidden');expect(details['min-height']).toBe('0')
 expect(declarations('.control-chat .chat-agent-panel[open] > summary').flex).toBe('0 0 auto')
 expect(declarations('.control-chat .chat-agent-panel[open] .control-chat-sidebar')['min-height']).toBe('0')
 expect(declarations('.conversation-library-list')['overflow-y']).toBe('auto')
 expect(declarations('.chat-sidebar-agents')['overflow-y']).toBe('auto')
 const narrow:Record<string,string>={};postcss.parse(css).walkAtRules('media',media=>{if(media.params!=='(max-width: 760px)')return;media.walkRules(rule=>{if(rule.selector==='.chat-agent-panel .control-chat-sidebar')rule.walkDecls(d=>{narrow[d.prop]=d.value})})})
 expect(narrow['grid-template-columns']).toBe('minmax(0, 1fr)');expect(narrow['min-height']).toBe('0')
})
it('constrains the native details wrapper and both responsive grid tracks instead of clipping an intrinsic-height sidebar',()=>{
 const wrapper=declarations('.control-chat .chat-agent-panel[open]::details-content')
 expect(wrapper.display).toBe('flex');expect(wrapper['flex-direction']).toBe('column');expect(wrapper.flex).toBe('1 1 0')
 expect(wrapper['min-height']).toBe('0');expect(wrapper['min-width']).toBe('0');expect(wrapper.overflow).toBe('hidden');expect(wrapper.height).toBeUndefined()
 const wide:Record<string,string>={};postcss.parse(css).walkRules(rule=>{if(rule.parent?.type==='root'&&rule.selector==='.chat-agent-panel .control-chat-sidebar')rule.walkDecls(d=>{wide[d.prop]=d.value})})
 expect(wide['grid-template-rows']).toBe('minmax(0, 1fr)')
 expect(declarations('.chat-sidebar-pane')['min-height']).toBe('0')
 const narrow:Record<string,string>={};postcss.parse(css).walkAtRules('media',media=>{if(media.params!=='(max-width: 760px)')return;media.walkRules(rule=>{if(rule.selector==='.chat-agent-panel .control-chat-sidebar')rule.walkDecls(d=>{narrow[d.prop]=d.value})})})
 expect(narrow['grid-template-rows']).toBe('minmax(0, 1.2fr) minmax(0, .8fr)')
 const selectors:string[]=[];postcss.parse(css).walkRules(rule=>{if(rule.selector.includes('::details-content'))selectors.push(rule.selector)})
 expect(selectors).toEqual(['.control-chat .chat-agent-panel[open]::details-content'])
})
it('preserves native collapse/open, draft and enabled composer without requests that mutate application state',async()=>{
 HTMLElement.prototype.scrollIntoView=vi.fn()
 const calls:Array<{url:string;method:string}>=[]
 vi.stubGlobal('fetch',vi.fn(async(input:string,init?:RequestInit)=>{
  const url=String(input);calls.push({url,method:init?.method??'GET'})
  const body=url==='/api/agents/list'?{agents:[]}:url.startsWith('/api/conversations?')?{conversations:[]}:url==='/api/providers/chat-models'?{models:[]}:null
  return {ok:true,status:200,json:async()=>body}
 }))
 const view=render(<AgentChat cognitiveMode="baseline" onNavigate={()=>{}} onOpenProviderSettings={()=>{}} onOpenCognitionSettings={()=>{}}/>);
 await waitFor(()=>expect(calls.some(call=>call.url.startsWith('/api/conversations?'))).toBe(true))
 const details=view.container.querySelector('details.chat-agent-panel') as HTMLDetailsElement,summary=details.querySelector('summary')!
 const composer=screen.getByRole('textbox',{name:'Mensaje al asistente o agente seleccionado'}) as HTMLTextAreaElement
 expect(details.open).toBe(false);expect(view.container.querySelector('.chat-agent-panel-slot')?.contains(details)).toBe(true)
 fireEvent.change(composer,{target:{value:'UNSENT_PANEL_DRAFT'}})
 const send=screen.getByRole('button',{name:'Enviar'}) as HTMLButtonElement
 expect(send.disabled).toBe(false)
 fireEvent.click(summary);expect(details.open).toBe(true);expect(composer.value).toBe('UNSENT_PANEL_DRAFT');expect(send.disabled).toBe(false)
 expect(composer.closest('.chat-agent-panel-slot')).toBeNull();expect(composer.closest('.control-chat-main')).not.toBeNull()
 fireEvent.click(summary);expect(details.open).toBe(false);expect(composer.value).toBe('UNSENT_PANEL_DRAFT')
 expect(calls.every(call=>call.method==='GET')).toBe(true)
})

it('uses one narrow scroll body and intrinsic non-clipping panes so even the last agent remains reachable',()=>{
 const narrow:Record<string,Record<string,string>>={}
 postcss.parse(css).walkAtRules('media',media=>{if(media.params!=='(max-width: 760px)')return;media.walkRules(rule=>{const values=narrow[rule.selector]??={};rule.walkDecls(d=>{values[d.prop]=d.value})})})
 const body=narrow['.control-chat .chat-agent-panel[open] .control-chat-sidebar']
 expect(body.display).toBe('block');expect(body['overflow-y']).toBe('auto')
 const pane=narrow['.control-chat .chat-agent-panel .chat-sidebar-pane']
 expect(pane.display).toBe('block');expect(pane.overflow).toBe('visible');expect(pane.height).toBe('auto');expect(pane['max-height']).toBe('none')
 const lists=narrow['.control-chat .chat-agent-panel :is(.conversation-library-list, .control-agent-list)']
 expect(lists.flex).toBe('none');expect(lists.height).toBe('auto');expect(lists['max-height']).toBe('none');expect(lists.overflow).toBe('visible')
 expect(declarations('.control-chat .chat-agent-panel-slot:has(.chat-agent-panel[open])')['max-height']).toBe('none')
 expect(declarations('.control-chat .chat-agent-panel[open]::details-content')['min-height']).toBe('0')
})
