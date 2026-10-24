// @vitest-environment jsdom
import React from 'react'
import {beforeEach,afterEach,expect,it,vi} from 'vitest'
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import {readFileSync} from 'node:fs'
import {createHash} from 'node:crypto'
import postcss from 'postcss'
import AgentChat from '../../../src/components/AgentChat'
import {resetLocaleForTests} from '../../../src/i18n'
const raw=readFileSync('src/components/AgentChat.css'),css=raw.toString('utf8')
const heading='.control-chat .chat-agent-panel .chat-sidebar-agents .chat-sidebar-heading'
function declarations(selector:string){const values:Record<string,string>={};postcss.parse(css).walkRules(rule=>{if(rule.selector===selector)rule.walkDecls(d=>{values[d.prop]=d.value})});return values}
beforeEach(()=>{localStorage.clear();resetLocaleForTests();HTMLElement.prototype.scrollIntoView=vi.fn()})
afterEach(()=>{cleanup();vi.unstubAllGlobals();vi.restoreAllMocks()})
it('preserves the exact full-panel CSS prefix and separates title/action without changing container sizing',()=>{
 expect(createHash('sha256').update(raw.subarray(0,26613)).digest('hex')).toBe('9876ba72e23fc88a87935c61e1a4fadec33458ee1909aafe22f0e5aa42d040ad')
 const style=declarations(heading)
 expect(style['justify-content']).toBe('space-between');expect(style.gap).toBe('12px');expect(style['flex-wrap']).toBe('wrap');expect(style['text-align']).toBe('left')
 const action=declarations(heading+' > .secondary-action')
 expect(action['border-radius']).toBe('0');expect(action.background).toBe('transparent');expect(action['box-shadow']).toBe('none');expect(action.width).toBeUndefined();expect(action['min-width']).toBeUndefined()
 expect(declarations(heading+' > .secondary-action:focus-visible').outline).toBe('2px solid #9de9f1')
 const delta=css.split('/* MANAGE_AGENT_ACTION:')[1],allowed=new Set(['justify-content','text-align','gap','flex-wrap','flex','padding','border-radius','color','border-color','background','box-shadow','outline','outline-offset'])
 postcss.parse(delta.slice(delta.indexOf('*/')+2)).walkRules(rule=>{expect(rule.selector.startsWith(heading)).toBe(true);rule.walkDecls(d=>expect(allowed.has(d.prop),d.prop).toBe(true))})
})
it('keeps the same labelled native button and invokes only its supplied management action',async()=>{
 const manage=vi.fn(),calls:Array<{url:string;method:string}>=[]
 vi.stubGlobal('fetch',vi.fn(async(input:string,init?:RequestInit)=>{const url=String(input);calls.push({url,method:init?.method??'GET'});return {ok:true,status:200,json:async()=>url==='/api/agents/list'?{agents:[]}:url.startsWith('/api/conversations?')?{conversations:[]}:url==='/api/providers/chat-models'?{models:[]}:null}}))
 const view=render(<AgentChat onNavigate={()=>{}} onManageAgents={manage}/>)
 await waitFor(()=>expect(calls.some(call=>call.url.startsWith('/api/conversations?'))).toBe(true))
 const panel=view.container.querySelector('details.chat-agent-panel') as HTMLDetailsElement;fireEvent.click(panel.querySelector('summary')!)
 const action=screen.getByRole('button',{name:'Gestionar agentes'}) as HTMLButtonElement
 expect(action.type).toBe('button');expect(action.closest('.chat-sidebar-heading')?.querySelector('h2')?.textContent).toBe('Agentes')
 fireEvent.click(action);expect(manage).toHaveBeenCalledTimes(1);expect(calls.every(call=>call.method==='GET')).toBe(true)
})
