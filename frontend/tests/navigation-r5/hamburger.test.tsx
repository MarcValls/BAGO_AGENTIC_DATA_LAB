// @vitest-environment jsdom
import React,{useState} from 'react'
import {afterEach,beforeEach,expect,it,vi} from 'vitest'
import {cleanup,fireEvent,render,screen,waitFor,within} from '@testing-library/react'
import {readFileSync} from 'node:fs'
import {resetLocaleForTests,t} from '../../src/i18n'
vi.mock('axios',()=>({default:{get:vi.fn(()=>new Promise(()=>{}))}}))
vi.mock('../../src/components/AgentChat',()=>({default:()=>{const[draft,setDraft]=useState('UNSENT');return <textarea aria-label="Chat draft fixture" value={draft} onChange={e=>setDraft(e.target.value)}/>}}))
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
it('retains an accessible icon rail without labels while preserving the active chat and draft',()=>{
 const view=render(<App/>),sidebar=view.container.querySelector('.workspace-sidebar') as HTMLElement
 const draft=screen.getByLabelText('Chat draft fixture') as HTMLTextAreaElement
 fireEvent.change(draft,{target:{value:'ORIGINAL USER DRAFT'}})
 const toggle=screen.getByRole('button',{name:t('core.App.collapse_sidebar_aab31c')})
 expect(toggle.closest('.app-menu-brand')?.querySelector('img')?.getAttribute('src')).toBe('/brand/BAGO_logotipo_horizontal.svg');expect(toggle.getAttribute('aria-expanded')).toBe('true');expect(sidebar.hidden).toBe(false)
 fireEvent.click(toggle)
 expect(toggle.getAttribute('aria-expanded')).toBe('false');expect(sidebar.hidden).toBe(false)
 expect(screen.getByRole('button',{name:t('core.App.workspace_87bb59')})).toHaveProperty('title',t('core.App.workspace_87bb59'))
 expect(screen.getByRole('button',{name:t('core.App.open_settings_ca381c')})).toHaveProperty('title',t('core.App.settings_74a883'))
 expect(screen.getByRole('link',{name:t('core.App.manual_b0b9fe')})).toHaveProperty('title',t('core.App.manual_b0b9fe'))
 expect(screen.getAllByRole('button').length).toBeGreaterThan(1)
 expect(draft.isConnected).toBe(true);expect(draft.value).toBe('ORIGINAL USER DRAFT')
 fireEvent.click(toggle);expect(sidebar.hidden).toBe(false)
 expect(screen.getByRole('button',{name:t('core.App.open_inspector_f351c3')})).toBeTruthy()
 expect(screen.getByRole('link',{name:t('core.App.manual_b0b9fe')})).toHaveProperty('target','_blank')
 expect((fetch as any).mock.calls).toHaveLength(0)
})
it('uses ArrowDown and Escape with focus restoration and preserves submenu state across folding',async()=>{
 const view=render(<App/>),sidebar=view.container.querySelector('.workspace-sidebar') as HTMLElement
 const toggle=screen.getByRole('button',{name:t('core.App.collapse_sidebar_aab31c')})
 fireEvent.click(screen.getByRole('button',{name:t('commerce.agents_455')}))
 expect(screen.getByRole('button',{name:t('commerce.my_agents')})).toBeTruthy()
 fireEvent.click(toggle);fireEvent.keyDown(toggle,{key:'ArrowDown'})
 await waitFor(()=>expect(document.activeElement).toBe(within(sidebar).getByRole('button',{name:t('core.App.workspace_87bb59')})))
 expect(screen.getByRole('button',{name:t('commerce.my_agents')})).toBeTruthy()
 fireEvent.keyDown(document.activeElement!,{key:'Escape'})
 expect(sidebar.hidden).toBe(false);expect(document.activeElement).toBe(toggle)
})
it('retains Inspector and Settings dialogs and returns focus without changing chat draft',()=>{
 const view=render(<App/>),sidebar=view.container.querySelector('.workspace-sidebar') as HTMLElement
 const trigger=within(sidebar).getByRole('button',{name:t('core.App.open_inspector_f351c3')});trigger.focus();fireEvent.click(trigger)
 expect((document.getElementById('data-layer') as HTMLDialogElement).open).toBe(true)
 fireEvent.click(screen.getByRole('button',{name:t('core.App.exit_inspector')}));expect(document.activeElement).toBe(trigger)
 fireEvent.click(within(sidebar).getByRole('button',{name:t('core.App.open_settings_ca381c')}))
 expect((document.getElementById('settings-layer') as HTMLDialogElement).open).toBe(true)
 expect((screen.getByLabelText('Chat draft fixture') as HTMLTextAreaElement).value).toBe('UNSENT')
})
it('puts the menu and content in normal grid flow, including a narrow stacked layout',()=>{
 const css=readFileSync('src/components/NavMenu.css','utf8')
 const style=document.createElement('style');style.textContent=css;document.head.append(style)
 const view=render(<App/>),shell=view.container.querySelector('.app-shell')!,sidebar=view.container.querySelector('.workspace-sidebar')!,main=view.container.querySelector('.app-main')!
 expect(getComputedStyle(shell).gridTemplateColumns).toContain('286px')
 expect(getComputedStyle(main).gridColumn).toBe('2');expect(getComputedStyle(sidebar).position).not.toMatch(/absolute|fixed/)
 fireEvent.click(screen.getByRole('button',{name:t('core.App.collapse_sidebar_aab31c')}))
 expect(getComputedStyle(sidebar).display).toBe('flex');expect(getComputedStyle(shell).gridTemplateColumns).toBe('72px minmax(0, 1fr)')
 expect(getComputedStyle(main).gridColumn).toBe('2')
 expect(view.container.querySelector('.app-menu-toolbar')).toBeNull();expect(getComputedStyle(main).gridRow).toBe('1');expect(css).toMatch(/@media \(max-width: 760px\)/);expect(css).toContain('grid-template-rows: auto minmax(0, 1fr)')
 const oControl=view.container.querySelector('.app-menu-toggle')!;expect(getComputedStyle(oControl).position).toBe('absolute');expect(oControl.parentElement?.className).toBe('app-menu-brand');expect(getComputedStyle(oControl).width).toBe('44px');expect(getComputedStyle(oControl).height).toBe('44px');expect(css).not.toMatch(/position\s*:\s*fixed/)
 style.remove()
})
