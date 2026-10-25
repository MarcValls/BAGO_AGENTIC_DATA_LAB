// @vitest-environment jsdom
import React from 'react'
import {afterEach,beforeEach,expect,it,vi} from 'vitest'
import {cleanup,fireEvent,render,screen,within,waitFor} from '@testing-library/react'
import {readFileSync} from 'node:fs'
import {createHash} from 'node:crypto'
import postcss from 'postcss'
import App from '../../../src/App'
import {resetLocaleForTests} from '../../../src/i18n'
let returnFocus:Element|null=null
beforeEach(()=>{
 localStorage.clear();resetLocaleForTests();HTMLElement.prototype.scrollIntoView=vi.fn()
 // Emulate native dialog focus restoration in JSDOM; real browser behavior is a separate integration check.
 HTMLDialogElement.prototype.showModal=function(){returnFocus=document.activeElement;this.open=true}
 HTMLDialogElement.prototype.close=function(){this.open=false;(returnFocus as HTMLElement)?.focus();this.dispatchEvent(new Event('close'))}
 vi.stubGlobal('fetch',vi.fn(async(input:string,init?:RequestInit)=>{
  if(init?.method && init.method!=='GET')throw new Error('Mutation forbidden in static navigation fixture')
  const url=String(input)
  const body=url==='/api/chat/context'?{workspace_root:'/synthetic',paths:[],cognition:{profile:'baseline',capacity:0,max_hops:0,max_expansions:0},memory:{kind:'conversation_history',state:'present',description:'Synthetic'}}:
   url.includes('/agents/list')?{agents:[]}:url.includes('chat-models')?{models:[]}:url.includes('/conversations')?{conversations:[]}:url.includes('/contacts')?{contacts:[]}:url.endsWith('/drafts')?{drafts:[]}:url.endsWith('/runs')?{runs:[]}:{ }
  return {ok:true,status:200,json:async()=>body}
 }))
})
afterEach(()=>{cleanup();vi.unstubAllGlobals();localStorage.clear();resetLocaleForTests()})
it('keeps Settings uniquely in its original footer and orders actual controls while retaining Chat, localized focus/draft and groups',async()=>{
 const view=render(<App/>),sidebar=view.container.querySelector('.workspace-sidebar') as HTMLElement
 const buttons=within(sidebar).getAllByRole('button')
 expect(buttons.map(b=>b.getAttribute('aria-label')||b.textContent?.trim())).toEqual(['Espacio de trabajo','Chat','Agentes','Capacidades','Comunicaciones','Abrir inspector','Abrir configuración'])
 const menuToggle=screen.getByRole('button',{name:'Contraer barra lateral'})
 expect(menuToggle.closest('.app-menu-brand')?.querySelector('img')?.getAttribute('src')).toBe('/brand/BAGO_logotipo_horizontal.svg');expect(menuToggle.getAttribute('aria-controls')).toBe(sidebar.id)
 expect(menuToggle.compareDocumentPosition(sidebar)&Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
 expect(sidebar.contains(menuToggle)).toBe(false)
 expect(within(sidebar).getAllByRole('button',{name:'Abrir configuración'})).toHaveLength(1)
 expect(sidebar.querySelector('footer .settings-trigger')).toBe(within(sidebar).getByRole('button',{name:'Abrir configuración'}))
 expect(sidebar.querySelector('.primary-navigation .settings-trigger')).toBeNull()
 const manual=within(sidebar).getByRole('link',{name:'Manual'})
 expect(buttons[5].compareDocumentPosition(manual)&Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
 expect(within(sidebar).getByRole('button',{name:'Chat'}).getAttribute('aria-current')).toBe('page')
 const draft=screen.getByRole('textbox',{name:'Mensaje al asistente o agente seleccionado'}) as HTMLTextAreaElement
 fireEvent.change(draft,{target:{value:'UNSENT_USER_DRAFT'}})
 const settings=within(sidebar).getByRole('button',{name:'Abrir configuración'});settings.focus();fireEvent.click(settings)
 expect(screen.getByRole('heading',{name:'Configuración'})).toBeTruthy()
 fireEvent.change(screen.getByLabelText('Idioma de la interfaz'),{target:{value:'en'}})
 expect(within(sidebar).getByRole('button',{name:'Open settings'})).toBe(settings)
 expect(screen.getByRole('heading',{name:'Settings'})).toBeTruthy()
 fireEvent.change(screen.getByLabelText('Interface language'),{target:{value:'es'}})
 fireEvent.click(screen.getByRole('button',{name:'Cerrar configuración'}))
 await waitFor(()=>expect(document.activeElement).toBe(settings))
 expect(draft.isConnected).toBe(true);expect(draft.value).toBe('UNSENT_USER_DRAFT')
 for(const name of ['Agentes','Comunicaciones']){
  const parent=within(sidebar).getByRole('button',{name});fireEvent.click(parent)
  expect(parent.getAttribute('aria-expanded')).toBe('true');expect(draft.isConnected).toBe(true)
  const first=sidebar.querySelector(name==='Agentes'?'#agent-navigation-items button':'#communications-navigation-items button') as HTMLElement
  first.focus();fireEvent.keyDown(first,{key:'Escape'});expect(document.activeElement).toBe(parent)
  expect(parent.getAttribute('aria-expanded')).toBe('false')
 }
 fireEvent.click(within(sidebar).getByRole('button',{name:'Comunicaciones'}))
 fireEvent.click(within(sidebar).getByRole('button',{name:'Mensajes'}))
 expect(await screen.findByRole('textbox',{name:'Mensaje'})).toBeTruthy()
 fireEvent.click(within(sidebar).getByRole('button',{name:'Agentes'}))
 fireEvent.click(within(sidebar).getByRole('button',{name:'Mis agentes'}))
 expect(view.container.querySelector('.agent-management')).not.toBeNull()
 expect((fetch as any).mock.calls.every(([,init]:[string,RequestInit?])=>!init?.method||init.method==='GET')).toBe(true)
})
it('keeps historical CSS and original narrow footer geometry, with finite rectangular beige-only sidebar styling',()=>{
 const appCss=readFileSync('src/App.css')
 expect(createHash('sha256').update(appCss).digest('hex')).toBe('5aabb6c16fde081d2f3bf2ac8fb4c8a469346b1fcf7138d373ebcafc91043555')
 const css=readFileSync('src/NavigationOrder.css','utf8'),ast=postcss.parse(css)
 const allowed=new Set(['--nav-beige','--nav-beige-line','color','background','border-color','border-radius','outline-color','box-shadow'])
 let rules=0
 ast.walkAtRules(()=>{throw new Error('No responsive override: retain original App.css footer/nav rows')})
 ast.walkRules(rule=>{rules++;expect(rule.selector.split(',').every(selector=>selector.trim().startsWith('#root .app-shell .workspace-sidebar'))).toBe(true)})
 ast.walkDecls(decl=>{expect(allowed.has(decl.prop)).toBe(true);expect(decl.important).not.toBe(true);if(decl.prop==='border-radius')expect(decl.value).toBe('0')})
 expect(rules).toBe(6)
 expect(css).toContain('.workspace-sidebar-footer .settings-trigger')
 expect(css).toContain('box-shadow: inset 3px 0 0 var(--nav-beige)')
 expect(css).not.toContain('grid-row')
 const app=readFileSync('src/App.tsx','utf8').replace(/\r\n/g,'\n')
 expect(app).toContain("import './App.css'\nimport './NavigationOrder.css'")
 expect(app).toContain("import './ServiceSurfaces.css'\nimport './VisualSystem.css'")
})
