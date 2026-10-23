// @vitest-environment jsdom
import React,{useState} from 'react'
import {afterEach,beforeEach,expect,it,vi} from 'vitest'
import {cleanup,fireEvent,render,screen,act} from '@testing-library/react'
import {resetLocaleForTests} from '../../../src/i18n'
vi.mock('axios',()=>({default:{get:vi.fn(()=>new Promise(()=>{}))}}))
vi.mock('../../../src/components/AgentChat',()=>({default:()=>{const[text,setText]=useState('User original');return <input aria-label="Preserved user draft" value={text} onChange={event=>setText(event.target.value)}/>}}))
vi.mock('../../../src/components/CognitionSettings',()=>({default:()=> <div>Fixture settings content</div>,readCognitiveMode:()=> 'baseline'}))
import App from '../../../src/App'
beforeEach(()=>{localStorage.clear();resetLocaleForTests();HTMLDialogElement.prototype.showModal=function(){this.setAttribute('open','')};HTMLDialogElement.prototype.close=function(){this.removeAttribute('open')};vi.stubGlobal('fetch',vi.fn(async()=>({ok:true,json:async()=>({})})))})
afterEach(()=>{cleanup();vi.unstubAllGlobals();localStorage.clear();resetLocaleForTests()})
it('exposes the actual Settings selector in Spanish, switches ES/EN/ES without remounting or network effects',async()=>{
 render(<App/>);fireEvent.change(screen.getByLabelText('Preserved user draft'),{target:{value:'DO_NOT_TRANSLATE user_123'}})
 fireEvent.click(screen.getByRole('button',{name:'Abrir configuración'}));expect(screen.getByRole('heading',{name:'Configuración'})).toBeTruthy()
 const calls=(fetch as any).mock.calls.length
 fireEvent.change(screen.getByLabelText('Idioma de la interfaz'),{target:{value:'en'}});await act(async()=>{})
 expect(screen.getByRole('heading',{name:'Settings'})).toBeTruthy();expect(document.documentElement.lang).toBe('en');expect((screen.getByLabelText('Preserved user draft') as HTMLInputElement).value).toBe('DO_NOT_TRANSLATE user_123')
 fireEvent.change(screen.getByLabelText('Interface language'),{target:{value:'es'}});await act(async()=>{})
 expect(screen.getByRole('heading',{name:'Configuración'})).toBeTruthy();expect((screen.getByLabelText('Preserved user draft') as HTMLInputElement).value).toBe('DO_NOT_TRANSLATE user_123');expect((fetch as any).mock.calls.length).toBe(calls)
})
