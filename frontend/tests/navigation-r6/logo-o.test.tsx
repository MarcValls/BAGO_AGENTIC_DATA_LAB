// @vitest-environment jsdom
import React,{useState} from 'react'
import {afterEach,beforeEach,expect,it,vi} from 'vitest'
import {cleanup,fireEvent,render,screen,waitFor,within} from '@testing-library/react'
import {createHash} from 'node:crypto'
import {readFileSync} from 'node:fs'
import {resetLocaleForTests,t} from '../../src/i18n'
vi.mock('axios',()=>({default:{get:vi.fn(()=>new Promise(()=>{}))}}))
vi.mock('../../src/components/AgentChat',()=>({default:({historySelection}:any)=>{const[draft,setDraft]=useState('UNSENT');return <textarea aria-label="Chat draft fixture" data-history-policy={historySelection} value={draft} onChange={e=>setDraft(e.target.value)}/>}}))
vi.mock('../../src/components/CognitionSettings',()=>({default:()=> <p>Context fixture</p>,readCognitiveMode:()=> 'baseline'}))
import App from '../../src/App'
beforeEach(()=>{
 localStorage.clear();resetLocaleForTests()
 HTMLDialogElement.prototype.showModal=function(){this.open=true}
 HTMLDialogElement.prototype.close=function(){this.open=false;this.dispatchEvent(new Event('close'))}
 vi.stubGlobal('fetch',vi.fn(async()=>({ok:true,status:200,json:async()=>({agents:[],models:[],conversations:[]})})))
 vi.stubGlobal('requestAnimationFrame',(fn:FrameRequestCallback)=>setTimeout(()=>fn(0),0))
})
afterEach(()=>{cleanup();vi.unstubAllGlobals();vi.restoreAllMocks()})
it('reuses the untouched asset once, binds only O and composes explicit history in the real App',()=>{
 const view=render(<App/>),sidebar=view.container.querySelector('.workspace-sidebar') as HTMLElement
 const image=screen.getByRole('img',{name:'BAGO'}),button=screen.getByRole('button',{name:t('core.App.collapse_sidebar_aab31c')})
 expect(screen.getAllByRole('img',{name:'BAGO'})).toHaveLength(1)
 expect(image.getAttribute('src')).toBe('/brand/BAGO_logotipo_horizontal.svg');expect(image.closest('button')).toBeNull()
 expect(image.closest('.app-navigation-shell')).not.toBeNull();expect(sidebar.querySelector('img')).toBeNull();expect(view.container.querySelector('.app-menu-toolbar')).toBeNull();expect(view.container.textContent).not.toContain('☰')
 fireEvent.click(image);expect(button.getAttribute('aria-expanded')).toBe('true')
 const draft=screen.getByLabelText('Chat draft fixture') as HTMLTextAreaElement
 expect(draft.dataset.historyPolicy).toBe('explicit');fireEvent.change(draft,{target:{value:'ORIGINAL USER DRAFT'}})
 fireEvent.click(button);expect(sidebar.hidden).toBe(false);expect(button.getAttribute('aria-expanded')).toBe('false')
 expect(screen.getByRole('button',{name:t('core.App.open_inspector_f351c3')})).toHaveProperty('title',t('core.App.inspector_e0723a'))
 expect(screen.getByRole('button',{name:t('core.App.open_settings_ca381c')})).toHaveProperty('title',t('core.App.settings_74a883'));expect(screen.getAllByRole('button').length).toBeGreaterThan(1)
 expect(screen.getByRole('img',{name:'BAGO'})).toBe(image);expect(draft.isConnected).toBe(true);expect(draft.value).toBe('ORIGINAL USER DRAFT')
 fireEvent.click(button);expect(sidebar.hidden).toBe(false);expect((fetch as any).mock.calls).toHaveLength(0)
})
it('preserves ArrowDown, Escape, focus, submenus and manual with the O control',async()=>{
 const view=render(<App/>),sidebar=view.container.querySelector('.workspace-sidebar') as HTMLElement
 const button=screen.getByRole('button',{name:t('core.App.collapse_sidebar_aab31c')})
 fireEvent.click(screen.getByRole('button',{name:t('commerce.agents_455')}));fireEvent.click(button)
 fireEvent.keyDown(button,{key:'ArrowDown'})
 await waitFor(()=>expect(document.activeElement).toBe(within(sidebar).getByRole('button',{name:t('core.App.workspace_87bb59')})))
 expect(screen.getByRole('button',{name:t('commerce.my_agents')})).toBeTruthy()
 expect(screen.getByRole('link',{name:t('core.App.manual_b0b9fe')})).toHaveProperty('target','_blank')
 fireEvent.keyDown(document.activeElement!,{key:'Escape'});expect(sidebar.hidden).toBe(false);expect(document.activeElement).toBe(button)
})
it('keeps dialog actions, original focus target and the draft intact',()=>{
 const view=render(<App/>),sidebar=view.container.querySelector('.workspace-sidebar') as HTMLElement
 const trigger=within(sidebar).getByRole('button',{name:t('core.App.open_inspector_f351c3')});trigger.focus();fireEvent.click(trigger)
 expect((document.getElementById('data-layer') as HTMLDialogElement).open).toBe(true)
 fireEvent.click(screen.getByRole('button',{name:t('core.App.exit_inspector')}));expect(document.activeElement).toBe(trigger)
 fireEvent.click(within(sidebar).getByRole('button',{name:t('core.App.open_settings_ca381c')}))
 expect((document.getElementById('settings-layer') as HTMLDialogElement).open).toBe(true)
 expect((screen.getByLabelText('Chat draft fixture') as HTMLTextAreaElement).value).toBe('UNSENT')
})
it('places the 44px hit target on the actual O pivot while the menu remains in grid flow',()=>{
 const css=readFileSync('src/components/NavMenu.css','utf8'),svg=readFileSync('public/brand/BAGO_logotipo_horizontal.svg')
 expect(createHash('sha256').update(svg).digest('hex')).toBe('e06014adf28e831ab5ada712a1e29f902bd3a6616737e8ddde1c02ae88f9a0b7')
 const xml=new DOMParser().parseFromString(svg.toString(),'image/svg+xml')
 expect(xml.documentElement.getAttribute('viewBox')).toBe('0 -1.75 200 51.35')
 expect(xml.querySelector('g[transform]')?.getAttribute('transform')).toBe('translate(-19.7 -5.28) translate(181 29.2) scale(.907) translate(-181 -29.2)')
 const style=document.createElement('style');style.textContent=css;document.head.append(style)
 const view=render(<App/>),button=screen.getByRole('button',{name:t('core.App.collapse_sidebar_aab31c')}),brand=button.parentElement!
 const target=getComputedStyle(button);expect(target.left).toBe('145.752px');expect(target.top).toBe('4.6968px');expect(target.width).toBe('44px');expect(target.height).toBe('44px')
 expect(getComputedStyle(brand).width).toBe('208px');expect(getComputedStyle(brand).height).toBe('53.404px')
 const shell=view.container.querySelector('.app-shell')!,sidebar=view.container.querySelector('.workspace-sidebar')!,main=view.container.querySelector('.app-main')!
 expect(getComputedStyle(shell).gridTemplateColumns).toContain('286px');expect(getComputedStyle(main).gridColumn).toBe('2');expect(getComputedStyle(main).gridRow).toBe('1');expect(getComputedStyle(view.container.querySelector('.app-navigation-shell')!).gridRow).toBe('1');expect(getComputedStyle(sidebar).position).not.toMatch(/absolute|fixed/)
 fireEvent.click(button);expect(getComputedStyle(sidebar).display).toBe('flex');expect(getComputedStyle(shell).gridTemplateColumns).toBe('72px minmax(0, 1fr)');expect(getComputedStyle(main).gridColumn).toBe('2');expect(getComputedStyle(main).gridRow).toBe('1');expect(getComputedStyle(shell).gridTemplateRows).toBe('minmax(0, 1fr)')
 expect(getComputedStyle(brand).width).toBe('44px');expect(getComputedStyle(brand).height).toBe('44px');expect(getComputedStyle(brand).overflow).toBe('hidden')
 expect(getComputedStyle(button).left).toBe('0px');expect(getComputedStyle(button).top).toBe('0px')
 const image=brand.querySelector('img')!;expect(getComputedStyle(image).width).toBe('208px');expect(getComputedStyle(image).transform).toBe('translate(-145.752px, -4.6968px)')
 for(const control of sidebar.querySelectorAll('.navigation-item')) {
  if(control.closest('[hidden]'))continue
  expect(control.getAttribute('aria-label')||control.getAttribute('title')).toBeTruthy()
  const icon=control.querySelector('.navigation-item-icon')!;expect(getComputedStyle(icon).display).not.toBe('none')
  for(const label of control.querySelectorAll('span:not(.navigation-item-icon)'))expect(getComputedStyle(label).display).toBe('none')
 }
 style.remove()
})

it('keeps O visually unselected for pointer focus and expanded state, with a keyboard-only focus indicator',()=>{
 const css=readFileSync('src/components/NavMenu.css','utf8')
 expect(css).toContain('.app-menu-brand > .app-menu-toggle:focus:not(:focus-visible) { outline: none; box-shadow: none; }')
 expect(css).toContain('.app-menu-brand > .app-menu-toggle:focus-visible { outline: 2px solid')
 expect(css).not.toMatch(/\[aria-(expanded|pressed)/)
 expect(css).not.toContain('.app-menu-toggle:hover')
})
