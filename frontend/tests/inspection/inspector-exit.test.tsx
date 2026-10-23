// @vitest-environment jsdom
import React,{useState} from 'react'
import {afterEach,beforeEach,expect,it,vi} from 'vitest'
import {act,cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import {readFileSync} from 'node:fs'
import {resetLocaleForTests,setLocale} from '../../src/i18n'
vi.mock('axios',()=>({default:{get:vi.fn(()=>new Promise(()=>{}))}}))
vi.mock('../../src/components/AgentChat',()=>({default:()=>{const[draft,setDraft]=useState('UNSENT_ORIGINAL');return <input aria-label="Unsent fixture draft" value={draft} onChange={event=>setDraft(event.target.value)}/>}}))
vi.mock('../../src/components/CognitionSettings',()=>({default:()=> <p>Cognition fixture</p>,readCognitiveMode:()=> 'baseline'}))
import App from '../../src/App'
beforeEach(()=>{
 localStorage.clear();resetLocaleForTests()
 // jsdom has no native dialog behavior. Emulate open/close events only; application must restore focus itself.
 HTMLDialogElement.prototype.showModal=function(){this.setAttribute('open','')}
 HTMLDialogElement.prototype.close=function(){this.removeAttribute('open');this.dispatchEvent(new Event('close'))}
 vi.stubGlobal('fetch',vi.fn(async()=>({ok:true,status:200,json:async()=>({agents:[],models:[]})})))
})
afterEach(()=>{cleanup();vi.unstubAllGlobals();vi.restoreAllMocks()})
function openInspector(){
 render(<App/>);const trigger=screen.getByRole('button',{name:'Abrir inspector'});trigger.focus();fireEvent.click(trigger)
 const dialog=document.getElementById('data-layer') as HTMLDialogElement
 expect(dialog.open).toBe(true)
 return {dialog,trigger}
}
it('has one native Salir at the navigation foot, no inspector header X, and restores trigger focus on click',()=>{
 const {dialog,trigger}=openInspector(),nav=within(dialog).getByRole('navigation',{name:'Vistas de datos'})
 const exit=within(nav).getByRole('button',{name:'Salir'})
 expect(exit.tagName).toBe('BUTTON');expect(exit.getAttribute('type')).toBe('button')
 expect(within(dialog).getAllByRole('button',{name:'Salir'})).toHaveLength(1)
 expect(dialog.querySelector('.data-layer-header .settings-layer-close')).toBeNull();expect(within(dialog).queryByText('×')).toBeNull()
 expect(exit.closest('.data-layer-navigation-footer')?.parentElement).toBe(nav)
 expect(nav.querySelector('.data-layer-navigation-items')?.contains(exit)).toBe(false)
 fireEvent.change(screen.getByLabelText('Unsent fixture draft'),{target:{value:'PRESERVE_NO_SEND_123'}})
 exit.focus();expect(document.activeElement).toBe(exit);fireEvent.click(exit)
 expect(dialog.open).toBe(false);expect(document.activeElement).toBe(trigger)
 expect((screen.getByLabelText('Unsent fixture draft') as HTMLInputElement).value).toBe('PRESERVE_NO_SEND_123')
 fireEvent.click(trigger);expect(dialog.open).toBe(true)
})
it('retains the native cancel path used by Escape and restores focus without application effects',()=>{
 const {dialog,trigger}=openInspector();const calls=(fetch as any).mock.calls.length
 within(dialog).getByRole('button',{name:'Salir'}).focus()
 // UA dispatches cancel for Escape. Do not claim jsdom synthesizes native keyboard default actions.
 fireEvent(dialog,new Event('cancel',{bubbles:false,cancelable:true}))
 expect(dialog.open).toBe(false);expect(document.activeElement).toBe(trigger)
 expect((fetch as any).mock.calls.length).toBe(calls)
})
it('translates Salir to Exit in place without closing or fetching and keeps Settings close unchanged',()=>{
 const {dialog,trigger}=openInspector();const calls=(fetch as any).mock.calls.length
 act(()=>setLocale('en'))
 const exit=within(dialog).getByRole('button',{name:'Exit'})
 expect(dialog.open).toBe(true);expect(within(dialog).queryByRole('button',{name:'Salir'})).toBeNull()
 expect((fetch as any).mock.calls.length).toBe(calls)
 exit.focus();fireEvent.click(exit);expect(dialog.open).toBe(false);expect(document.activeElement).toBe(trigger)
 fireEvent.click(screen.getByRole('button',{name:'Open settings'}))
 const settings=document.getElementById('settings-layer') as HTMLDialogElement
 expect(settings.open).toBe(true);expect(within(settings).getByRole('button',{name:'Close settings'})).toBeTruthy()
 expect(settings.querySelector('.settings-layer-close')).toBeTruthy()
})
it('keeps the footer outside the horizontally scrollable narrow navigation row',()=>{
 const {dialog}=openInspector(),nav=dialog.querySelector('.data-layer-navigation')!
 const items=nav.querySelector('.data-layer-navigation-items')!,footer=nav.querySelector('.data-layer-navigation-footer')!
 expect(nav.lastElementChild).toBe(footer);expect(items.contains(footer)).toBe(false)
 const css=readFileSync('src/App.css','utf8')
 expect(css).toMatch(/\.data-layer-navigation-items\s*\{[^}]*overflow:\s*auto/)
 expect(css).toMatch(/\.data-layer-navigation-footer\s*\{[^}]*flex:\s*0 0 auto/)
 expect(css).toMatch(/@media\s*\(max-width:\s*760px\)\s*\{\s*\.data-layer-navigation\s*\{[^}]*flex-direction:\s*column/)
 expect(css).toMatch(/\.data-layer-navigation-items\s*\{[^}]*overflow-x:\s*auto/)
})
