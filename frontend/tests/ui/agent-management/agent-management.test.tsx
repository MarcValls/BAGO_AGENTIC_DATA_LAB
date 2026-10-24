import {setLocale,t} from '../../../src/i18n'
import {beforeEach as beforeLocaleExpectation} from 'vitest'
beforeLocaleExpectation(() => setLocale('es'))
// @vitest-environment jsdom
import React from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import AgentManagement from '../../../src/components/AgentManagement'
import AgentBuilder from '../../../src/components/AgentBuilder'

const id = 'agent_12345678'
const original = { id, created_at: '2026-10-22T00:00:00Z', config: { name: 'Ámbar', description: 'Gastos de empresa', type: 'tool', system_prompt: '', tools: [], provider_id: 'codex', model_id: 'fixture', task: { prompt: 'Revisar gastos', dates: [] } } }
const second = { ...original, id: 'agent_87654321', config: { ...original.config, name: 'Norte', description: 'Facturación' } }
const response = (body: unknown, status = 200) => ({ ok: status < 400, status, json: async () => body })
const props = () => ({ onCreate: vi.fn(), onTest: vi.fn(), onEvaluate: vi.fn() })
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals() })

describe('Gestión de agentes con API', () => {
  it('only changes provider/model after explicit selection and preserves unavailable saved identities',async()=>{
    let saved:any
    vi.stubGlobal('fetch',vi.fn(async(_path:string,init?:RequestInit)=>{
      if(init?.method==='PUT'){saved=JSON.parse(String(init.body));return response({...original,config:saved})}
      return response({models:[{provider_id:'ollama-cloud',model_id:'selected-fixture',state:'ready',label:'Ollama'}]})
    }))
    render(<AgentBuilder agentId={id} initialAgent={original.config as any} />)
    await waitFor(()=>expect((screen.getByLabelText(t('core.CapabilityManager.provider_472590')) as HTMLSelectElement).disabled).toBe(false))
    expect((screen.getByLabelText(t('core.CapabilityManager.provider_472590')) as HTMLSelectElement).value).toBe('codex')
    expect((screen.getByLabelText(t('core.ModelAssignments.model_a5ab32')) as HTMLSelectElement).value).toBe('fixture')
    fireEvent.change(screen.getByLabelText(t('core.CapabilityManager.provider_472590')),{target:{value:'ollama-cloud'}})
    fireEvent.click(screen.getByRole('button',{name:/Vista previa/}))
    expect(screen.getByText(/Proveedor y modelo:/).parentElement?.textContent).toContain('Ollama · selected-fixture')
    fireEvent.click(screen.getByRole('button',{name:t('agents.AgentBuilder.save_changes')}))
    await waitFor(()=>expect(saved?.provider_id).toBe('ollama-cloud'));expect(saved.model_id).toBe('selected-fixture')
  })
  it.each([null, undefined])('preserves unassigned provider/model in edit preview and PUT (%s)', async missing => {
    const config = {...original.config, provider_id: missing, model_id: missing} as any
    let saved:any
    vi.stubGlobal('fetch', vi.fn(async (_path:string, init?:RequestInit) => {
      if (init?.method === 'PUT') { saved=JSON.parse(String(init.body)); return response({...original,config:saved}) }
      return response({models:[{provider_id:'ollama-cloud',model_id:'unselected-model',state:'ready',label:'Ollama'}]})
    }))
    render(<AgentBuilder agentId={id} initialAgent={config} />)
    await waitFor(()=>expect((screen.getByLabelText(t('core.CapabilityManager.provider_472590')) as HTMLSelectElement).disabled).toBe(false))
    expect((screen.getByLabelText(t('core.CapabilityManager.provider_472590')) as HTMLSelectElement).value).toBe('')
    expect((screen.getByLabelText(t('core.ModelAssignments.model_a5ab32')) as HTMLSelectElement).value).toBe('')
    fireEvent.change(screen.getByDisplayValue('Ámbar'),{target:{value:'Solo nombre'}})
    fireEvent.click(screen.getByRole('button',{name:/Vista previa/}))
    expect(screen.getByText(/Proveedor y modelo:/).parentElement?.textContent).toContain('Sin asignar · Sin asignar')
    fireEvent.click(screen.getByRole('button',{name:t('agents.AgentBuilder.save_changes')}))
    await waitFor(()=>expect(saved?.name).toBe('Solo nombre'))
    expect(saved.provider_id).toBe(missing);expect(saved.model_id).toBe(missing)
  })

  it('focuses and scrolls blocked review, Escape restores the exact trigger without DELETE', async()=>{
    const scroll=vi.fn();vi.stubGlobal('fetch',vi.fn(async(path:string)=>path.endsWith('/deletion-review')?response({agent_id:id,name:'Ámbar',revision:'a'.repeat(64),deletable:false,blockers:['job_active'],preserved:[]}):response({agents:[original]})))
    const descriptor=Object.getOwnPropertyDescriptor(HTMLElement.prototype,'scrollIntoView')
    Object.defineProperty(HTMLElement.prototype,'scrollIntoView',{value:scroll,configurable:true})
    try {
      render(<AgentManagement {...props()} />)
      const trigger=await screen.findByRole('button',{name:t('agents.AgentManagement.eliminar_perfil')});trigger.focus();fireEvent.click(trigger)
      const region=await screen.findByRole('region',{name:t('agents.AgentManagement.confirmar_eliminacion')})
      await waitFor(()=>expect(document.activeElement).toBe(region));expect(scroll).toHaveBeenCalledWith({block:'nearest'})
      expect(within(region).getByRole('alert').textContent).toContain('job_active')
      fireEvent.keyDown(region,{key:'Escape'})
      expect(screen.queryByRole('region',{name:t('agents.AgentManagement.confirmar_eliminacion')})).toBeNull();expect(document.activeElement).toBe(trigger)
      expect((fetch as any).mock.calls.some((c:any[])=>c[1]?.method==='DELETE')).toBe(false)
    } finally { if(descriptor) Object.defineProperty(HTMLElement.prototype,'scrollIntoView',descriptor);else delete (HTMLElement.prototype as any).scrollIntoView }
  })
  it('lists, searches and navigates using exact identity', async () => {
    vi.stubGlobal('fetch',vi.fn(async () => response({ agents: [original,second] })))
    const callbacks=props(); render(<AgentManagement {...callbacks} />)
    await screen.findByText('2 de 2 agentes')
    fireEvent.change(screen.getByRole('searchbox',{name:t('agents.AgentManagement.buscar_agente')}),{target:{value:'gastos'}})
    expect(screen.getByText('1 de 2 agentes')).toBeTruthy()
    expect(screen.queryByRole('heading',{name:'Norte'})).toBeNull()
    fireEvent.click(screen.getByRole('button',{name:t('agents.AgentManagement.probar_tarea')})); expect(callbacks.onTest).toHaveBeenCalledWith(id)
    fireEvent.click(screen.getByRole('button',{name:t('agents.AgentManagement.evaluar')})); expect(callbacks.onEvaluate).toHaveBeenCalledWith(id)
    fireEvent.click(screen.getByRole('button',{name:t('agents.AgentManagement.crear_agente')})); expect(callbacks.onCreate).toHaveBeenCalledOnce()
  })

  it('shows empty, error and recoverable refresh states',async()=>{
    let fail=true
    vi.stubGlobal('fetch',vi.fn(async()=>fail?response({detail:{message:'Sin conexión'}},503):response({agents:[]})))
    render(<AgentManagement {...props()} />)
    await screen.findByText(/Sin conexión/); fail=false
    fireEvent.click(screen.getByRole('button',{name:t('agents.AgentManagement.actualizar_y_reintentar')}))
    await screen.findByText(t('agents.AgentManagement.aun_no_hay_agentes_guardados'))
  })

  it('requires review and explicit checkbox before DELETE with exact hash',async()=>{
    let removed=false; let sent:any
    vi.stubGlobal('fetch',vi.fn(async(path:string,init?:RequestInit)=>{
      if(init?.method==='DELETE'){sent=JSON.parse(String(init.body));removed=true;return response({id,state:'deleted'})}
      if(path.endsWith('/deletion-review')) return response({agent_id:id,name:'Ámbar',revision:'a'.repeat(64),deletable:true,blockers:[],preserved:['conversations','traces']})
      return response({agents:removed?[]:[original]})
    }))
    render(<AgentManagement {...props()} />)
    fireEvent.click(await screen.findByRole('button',{name:t('agents.AgentManagement.eliminar_perfil')}))
    const dialog=await screen.findByRole('region',{name:t('agents.AgentManagement.confirmar_eliminacion')})
    const confirm=within(dialog).getByRole('button',{name:'Confirmar eliminación'}) as HTMLButtonElement
    expect(confirm.disabled).toBe(true);expect(sent).toBeUndefined()
    fireEvent.click(within(dialog).getByRole('checkbox'))
    fireEvent.click(confirm)
    await screen.findByText(t('agents.AgentManagement.aun_no_hay_agentes_guardados'))
    expect(sent).toEqual({confirmed:true,expected_revision:'a'.repeat(64)})
  })

  it('blocks active work and keeps profile on conflict',async()=>{
    let deletable=false
    vi.stubGlobal('fetch',vi.fn(async(path:string,init?:RequestInit)=>{
      if(init?.method==='DELETE') return response({detail:{message:'El perfil cambió. Actualiza.'}},409)
      if(path.endsWith('/deletion-review')) return response({agent_id:id,name:'Ámbar',revision:'a'.repeat(64),deletable,blockers:deletable?[]:['job_active'],preserved:[]})
      return response({agents:[original]})
    }))
    render(<AgentManagement {...props()} />)
    fireEvent.click(await screen.findByRole('button',{name:t('agents.AgentManagement.eliminar_perfil')}))
    await screen.findByText('No se puede eliminar: hay trabajo activo (job_active).')
    expect((screen.getByRole('checkbox') as HTMLInputElement).disabled).toBe(true)
    fireEvent.click(screen.getByRole('button',{name:t('agents.state.cancel')})); deletable=true
    fireEvent.click(screen.getByRole('button',{name:t('agents.AgentManagement.eliminar_perfil')}))
    fireEvent.click(await screen.findByRole('checkbox'))
    fireEvent.click(screen.getByRole('button',{name:t('agents.AgentManagement.confirmar_eliminacion')}))
    await screen.findByText(/El perfil cambió. Actualiza./)
    expect((screen.getByRole('checkbox') as HTMLInputElement).checked).toBe(false)
    expect(screen.getByRole('heading',{name:'Ámbar'})).toBeTruthy()
  })

  it('loads real selected profile into existing Builder and saves through PUT',async()=>{
    let saved:any
    vi.stubGlobal('fetch',vi.fn(async(path:string,init?:RequestInit)=>{
      if(path==='/api/agents/list') return response({agents:[original]})
      if(path==='/api/providers/chat-models') return response({models:[{provider_id:'codex',model_id:'fixture',state:'ready',label:'Codex'}]})
      if(path===`/api/agents/${id}` && init?.method==='PUT'){saved=JSON.parse(String(init.body));return response({...original,config:saved})}
      if(path===`/api/agents/${id}`) return response(original)
      throw Error(`Unexpected request ${path}`)
    }))
    render(<AgentManagement {...props()} />)
    fireEvent.click(await screen.findByRole('button',{name:t('agents.AgentManagement.editar')}))
    const name=await screen.findByDisplayValue('Ámbar')
    fireEvent.change(name,{target:{value:'Ámbar revisado'}})
    fireEvent.click(screen.getByRole('button',{name:/Vista previa/}))
    fireEvent.click(screen.getByRole('button',{name:t('agents.AgentBuilder.save_changes')}))
    await waitFor(()=>expect(saved?.name).toBe('Ámbar revisado'))
  })
})
