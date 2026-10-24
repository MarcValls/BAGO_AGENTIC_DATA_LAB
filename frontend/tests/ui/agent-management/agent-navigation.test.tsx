// @vitest-environment jsdom
import React from 'react'
import {resetLocaleForTests,setLocale,t} from '../../../src/i18n'
beforeEach(()=>{localStorage.clear();resetLocaleForTests();setLocale('es')})
import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import AgentNavigation from '../../../src/components/AgentNavigation'
import AgentChat from '../../../src/components/AgentChat'

afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals() })
const options = () => ({ activeView: 'chat', collapsed: false, onExpandSidebar: vi.fn(), onNavigate: vi.fn() })

describe('Grupo lateral Agentes', () => {
  it('starts folded on global Chat, opens four reused destinations and never navigates just by unfolding', () => {
    const props=options(); render(<AgentNavigation {...props} />)
    const group=screen.getByRole('button',{name:'Agentes'})
    expect(group.getAttribute('aria-expanded')).toBe('false')
    expect(document.getElementById(group.getAttribute('aria-controls')!)).toBeTruthy()
    expect(screen.queryByRole('button',{name:'Mis agentes'})).toBeNull()
    fireEvent.click(group)
    expect(group.getAttribute('aria-expanded')).toBe('true')
    expect(props.onNavigate).not.toHaveBeenCalled()
    const section=screen.getByRole('group',{name:'Gestión y trabajo con agentes'})
    expect(within(section).getAllByRole('button').length).toBe(4)
    for(const [label,id] of [['Mis agentes','agents'],['Crear agente','builder'],['Ejecutar / Probar','runner'],['Evaluación','evaluation_lab']]) {
      fireEvent.click(within(section).getByRole('button',{name:label}));expect(props.onNavigate).toHaveBeenLastCalledWith(id)
    }
  })

  it('tracks the active page and Escape folds without changing the page, returning focus', () => {
    const props={...options(),activeView:'runner'}; render(<AgentNavigation {...props} />)
    const selected=screen.getByRole('button',{name:'Ejecutar / Probar'})
    expect(selected.getAttribute('aria-current')).toBe('page')
    expect(screen.getAllByRole('button').filter(button=>button.getAttribute('aria-current')==='page').length).toBe(1)
    selected.focus(); fireEvent.keyDown(selected,{key:'Escape'})
    const group=screen.getByRole('button',{name:'Agentes'})
    expect(document.activeElement).toBe(group)
    expect(group.getAttribute('aria-expanded')).toBe('false')
    expect(props.onNavigate).not.toHaveBeenCalled()
  })

  it('ArrowDown opens and focuses the first submenu', async () => {
    vi.spyOn(window,'requestAnimationFrame').mockImplementation(callback=>{setTimeout(()=>callback(0),0);return 1})
    render(<AgentNavigation {...options()} />)
    fireEvent.keyDown(screen.getByRole('button',{name:'Agentes'}),{key:'ArrowDown'})
    await waitFor(()=>expect(document.activeElement).toBe(screen.getByRole('button',{name:'Mis agentes'})))
  })

  it('expands a compact sidebar and opens when another route selects an agent section', async () => {
    const props={...options(),collapsed:true};const {rerender}=render(<AgentNavigation {...props} />)
    fireEvent.click(screen.getByRole('button',{name:'Agentes'}));expect(props.onExpandSidebar).toHaveBeenCalledOnce()
    rerender(<AgentNavigation {...props} collapsed={false} activeView="evaluation_lab" />)
    await waitFor(()=>expect(screen.getByRole('button',{name:'Evaluación'}).getAttribute('aria-current')).toBe('page'))
  })
})

it('Chat opens the same management resource without creating a profile or moving the global conversation', async () => {
  Object.defineProperty(HTMLElement.prototype,'scrollIntoView',{configurable:true,value:vi.fn()})
  const fetcher=vi.fn(async(input:string)=>({ok:true,status:200,json:async()=>String(input)==='/api/agents/list'?{agents:[]}:String(input).startsWith('/api/conversations?')?{conversations:[]}:String(input)==='/api/providers/chat-models'?{models:[]}:{provider_id:null,model_id:null}}))
  vi.stubGlobal('fetch',fetcher)
  const manage=vi.fn()
  render(<AgentChat onNavigate={vi.fn()} onManageAgents={manage} onOpenProviderSettings={vi.fn()} onOpenCognitionSettings={vi.fn()} cognitiveMode="baseline" />)
  const summary=screen.getByText(/Conversaciones y agentes/).closest('summary')!
  fireEvent.click(summary)
  fireEvent.click(await screen.findByRole('button',{name:'Gestionar agentes'}))
  expect(manage).toHaveBeenCalledOnce()
  expect(fetcher.mock.calls.every(call=>!String(call[0]).includes('/create'))).toBe(true)
})
