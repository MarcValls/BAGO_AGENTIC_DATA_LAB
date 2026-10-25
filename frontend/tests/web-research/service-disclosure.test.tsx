// @vitest-environment jsdom
import React from 'react'
import {resetLocaleForTests,setLocale,t} from '../../src/i18n'
beforeEach(()=>{localStorage.clear();resetLocaleForTests();setLocale('es')})
import {beforeEach,afterEach,expect,it,vi} from 'vitest'
import {cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import {readFileSync} from 'node:fs'
vi.mock('axios',()=>({default:{get:vi.fn(()=>new Promise(()=>{}))}}))
vi.mock('../../src/components/AgentChat',()=>({default:()=> <div>Chat fixture</div>}))
vi.mock('../../src/components/WorkspaceManager',()=>({default:({contextPanel}:any)=> <section>Gestor de proyecto fixture{typeof contextPanel==='function'?contextPanel({openProjectSelection:vi.fn(),refreshKey:0}):contextPanel}</section>}))
vi.mock('../../src/components/CognitionSettings',()=>({default:()=> <section>Contexto conservado fixture</section>,readCognitiveMode:()=> 'baseline'}))
import App from '../../src/App'
afterEach(()=>{cleanup();vi.unstubAllGlobals()})
it('offers one manual link without adding instructions to each screen',()=>{
 render(<App />)
 const links=screen.getAllByRole('link',{name:'Manual'})
 expect(links).toHaveLength(1);expect(links[0].getAttribute('href')).toBe('/manual');expect(links[0].getAttribute('target')).toBe('_blank')
})
it('passes existing context into Workspace without a duplicated sibling disclosure',()=>{
 render(<App />);fireEvent.click(screen.getByRole('button',{name:'Espacio de trabajo'}))
 const panel=document.querySelector('.context-memory-panel')!
 expect(within(panel as HTMLElement).getByText('Contexto conservado fixture')).toBeTruthy()
 expect(document.querySelector('details.context-memory-details')).toBeNull()
 expect(screen.getByText('Gestor de proyecto fixture')).toBeTruthy()
})
it('scopes disclosure styling to service surfaces and preserves native keyboard controls',()=>{
 const css=readFileSync('src/ServiceSurfaces.css','utf8')
 expect(css).toContain('summary:focus-visible');expect(css).toContain('min-height: 44px');expect(css).toContain('details[open] > summary::after')
 expect(css).toContain('transform: rotate(-45deg)');expect(css).toContain('transform: rotate(45deg)')
 expect(css).toContain('@container service-surface (max-width: 720px)');expect(css).toContain('minmax(0, 1fr)')
 expect(css).toContain('.app-shell .agent-tasks-advanced > summary');expect(css).toContain('.app-shell .context-memory-details { max-width: none; margin-inline: 0; }')
 expect(css).not.toMatch(/\.app-shell\s+details\s*[{>,]/)
})
it('keeps detailed operating instructions and truthful limits in the manual',()=>{
 const manual=readFileSync('../docs/public-web/MANUAL.md','utf8')
 for(const section of ['Chat y lectura de páginas públicas','Proyectos, archivos y contexto','Contactos e importación de Google','Vincular WhatsApp','Preparar mensajes y programarlos','Experimento de lectura y revisión'])expect(manual).toContain('## '+section)
 expect(manual).toContain('no equivale a cerrar sesión');expect(manual).toContain('no afirma que un experimento concreto haya pasado')
})

