// @vitest-environment jsdom
import React from 'react'
import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest'
import {act,cleanup,fireEvent,render,screen,waitFor,within} from '@testing-library/react'
import ProviderSettings from '../../src/components/ProviderSettings'
import ModelAssignments from '../../src/components/ModelAssignments'
import {formatDate,resetLocaleForTests,setLocale,t} from '../../src/i18n'
const response=(body:unknown,status=200)=>({ok:status<400,status,json:async()=>body})
const switchTo=(locale:'es'|'en')=>act(()=>setLocale(locale))
const setupFetch=(registrations:unknown[]=[])=>{
 const fetcher=vi.fn(async(input:string)=>{
  if(input==='/api/providers/registry')return response({registrations})
  if(input==='/api/providers/ollama/status')return response({state:'not_configured',auth_mode:null,model_id:null})
  if(input==='/api/providers/codex/session')return response({authenticated:false,models:[]})
  if(input==='/api/providers/github-copilot/session')return response({authenticated:false})
  throw new Error('Unexpected fixture request '+input)
 });vi.stubGlobal('fetch',fetcher);return fetcher
}
beforeEach(()=>{localStorage.clear();resetLocaleForTests()})
afterEach(()=>{cleanup();vi.unstubAllGlobals();vi.restoreAllMocks()})
describe('provider settings bilingual completion with simulated API only',()=>{
 it.each([
  ['Anthropic','Crea una clave API en tu cuenta de Anthropic.','Create an API key in your Anthropic account.'],
  ['OpenRouter','Crea una clave API en OpenRouter.','Create an API key in OpenRouter.'],
  ['OpenCode','Inicia tu servidor OpenCode.','Start your OpenCode server.'],
  ['GitHub Copilot','Solicita el código de un solo uso desde ADL.','Request the one-time code from ADL.'],
 ])('translates the full %s registration steps without remount or locale requests',async(provider,spanish,english)=>{
  const fetcher=setupFetch();render(<ProviderSettings />)
  await waitFor(()=>expect(screen.queryByText(t('core.ProviderSettings.loading_saved_registrations_7621f4'))).toBeNull())
  fireEvent.click(screen.getByRole('tab',{name:new RegExp(provider)}))
  expect(screen.getByText(spanish)).toBeTruthy()
  const panel=document.getElementById('provider-panel-'+({'Anthropic':'anthropic','OpenRouter':'openrouter','OpenCode':'opencode','GitHub Copilot':'github-copilot'}[provider]))!
  if(provider==='GitHub Copilot')await waitFor(()=>expect(screen.queryByText('Consultando sesión.')).toBeNull())
  const count=fetcher.mock.calls.length
  switchTo('en')
  expect(document.getElementById(panel.id)).toBe(panel)
  expect(screen.getByText(english)).toBeTruthy()
  expect(screen.queryByText(spanish)).toBeNull()
  expect(fetcher.mock.calls.length).toBe(count)
  switchTo('es')
  expect(screen.getByText(spanish)).toBeTruthy()
  expect(fetcher.mock.calls.length).toBe(count)
 })
 it('translates both OpenCode modes and base URL labels while preserving input bytes',async()=>{
  const fetcher=setupFetch();render(<ProviderSettings />)
  fireEvent.click(screen.getByRole('tab',{name:/OpenCode/}))
  fireEvent.click(screen.getByRole('tab',{name:'Clave API',exact:true}))
  const base=screen.getByLabelText('URL base') as HTMLInputElement
  const model=screen.getByLabelText(/Modelo predeterminado/) as HTMLInputElement
  const credential=screen.getByLabelText(/Clave API.*solo escritura/i) as HTMLInputElement
  fireEvent.change(base,{target:{value:'http://127.0.0.1:3000'}})
  fireEvent.change(model,{target:{value:'provider/original-model'}})
  fireEvent.change(credential,{target:{value:'EXACT_SECRET_FIXTURE'}})
  const count=fetcher.mock.calls.length
  switchTo('en')
  expect(screen.getByText('Configure the OpenCode endpoint.')).toBeTruthy()
  expect(screen.getByText('Add the API key if your endpoint requires it.')).toBeTruthy()
  expect(screen.getByLabelText('Base URL')).toBe(base)
  expect(base.value).toBe('http://127.0.0.1:3000')
  expect(model.value).toBe('provider/original-model')
  expect(credential.value).toBe('EXACT_SECRET_FIXTURE')
  expect(fetcher.mock.calls.length).toBe(count)
 })
 it('translates all three Platform steps under the grouped OpenAI tab',async()=>{
  const fetcher=setupFetch();render(<ProviderSettings />)
  fireEvent.click(screen.getByRole('tab',{name:/OpenAI/}))
  const platform=screen.getByRole('region',{name:'OpenAI Platform'})
  const nodes=within(platform).getAllByRole('listitem',{hidden:true})
  expect(nodes.map(node=>node.textContent)).toEqual(['Crea una clave API de proyecto en OpenAI Platform.','Pégala en este formulario seguro; ADL la guarda en el almacén del sistema.','Indica un modelo para completar el registro.'])
  await waitFor(()=>expect(screen.queryByText('Consultando Codex.')).toBeNull())
  const count=fetcher.mock.calls.length
  switchTo('en')
  expect(within(platform).getAllByRole('listitem',{hidden:true}).map(node=>node.textContent)).toEqual(['Create a project API key in OpenAI Platform.','Paste it into this secure form; ADL saves it in the system store.','Enter a model to complete registration.'])
  expect(fetcher.mock.calls.length).toBe(count)
 })
 it('keeps an API diagnostic original and relocalizes the failure after locale switch',async()=>{
  const fetcher=vi.fn(async(input:string)=>input==='/api/providers/registry'?response({detail:{code:'unknown_fixture',message:'EXACT diagnostic α / 503'}},503):response({state:'not_configured',auth_mode:null,model_id:null}))
  vi.stubGlobal('fetch',fetcher);render(<ProviderSettings />)
  const alert=await screen.findByRole('alert')
  expect(alert.textContent).toContain('EXACT diagnostic α / 503')
  expect(alert.textContent).toContain('técnico')
  const count=fetcher.mock.calls.length
  switchTo('en')
  expect(alert.textContent).toContain('EXACT diagnostic α / 503')
  expect(alert.textContent).toContain('technical')
  expect(fetcher.mock.calls.length).toBe(count)
 })
 it('formats last verification in the selected locale without repeating provider work',async()=>{
  const timestamp='2026-10-23T12:30:00Z'
  const fetcher=setupFetch([{provider_id:'openai-platform',state:'ready',auth_mode:'api_key',model_id:'model-original',base_url:null,has_credential:true,runtime_support:'chat_and_agent_runner',last_verified_at:timestamp}])
  render(<ProviderSettings />)
  await waitFor(()=>expect(screen.queryByText(t('core.ProviderSettings.loading_saved_registrations_7621f4'))).toBeNull())
  fireEvent.click(screen.getByRole('tab',{name:/OpenAI/}))
  await screen.findByText(/Última respuesta comprobada:/)
  const count=fetcher.mock.calls.length
  switchTo('en')
  expect(screen.getByText(new RegExp('Last verified response: '+formatDate(timestamp).replace(/[.*+?^${}()|[\]\\]/g,'\\$&')))).toBeTruthy()
  expect(fetcher.mock.calls.length).toBe(count)
 })
 it('preserves assignment roles, primary selection and filter, then submits original protocol enums',async()=>{
  const id='provider-original|model-original';let saved:any
  const fetcher=vi.fn(async(_input:string,init?:RequestInit)=>{
   if(init?.method==='PUT'){saved=JSON.parse(String(init.body));return response({...saved,revision:'revision-next'})}
   return response({models:[],main_chat:null,revision:'revision-original',catalog:[{provider_id:'provider-original',model_id:'model-original',display_name:'Original Model',label:'Original Provider',state:'ready'}],warnings:['EXACT upstream warning']})
  })
  const policyChanged=vi.fn();window.addEventListener('adl-model-policy-changed',policyChanged)
  try{
   vi.stubGlobal('fetch',fetcher);render(<ModelAssignments onExit={()=>{}} />)
   await screen.findByText('Original Model')
   expect(screen.getByRole('columnheader',{name:'Recuperación (RAG)'})).toBeTruthy()
   expect(screen.getByRole('columnheader',{name:'Herramientas'})).toBeTruthy()
   expect(screen.getByRole('columnheader',{name:'Varios agentes'})).toBeTruthy()
   const orchestrator=screen.getByRole('checkbox',{name:'Orquestador · '+id}) as HTMLInputElement
   fireEvent.click(orchestrator)
   fireEvent.click(screen.getByRole('radio',{name:'Principal · '+id}))
   const role=screen.getByRole('checkbox',{name:'Herramientas · '+id}) as HTMLInputElement
   fireEvent.click(role)
   const filter=screen.getByLabelText('Buscar modelo') as HTMLInputElement
   fireEvent.change(filter,{target:{value:'Original'}})
   const count=fetcher.mock.calls.length
   switchTo('en')
   expect(screen.getByRole('columnheader',{name:'Retrieval (RAG)'})).toBeTruthy()
   expect(screen.getByRole('columnheader',{name:'Tools'})).toBeTruthy()
   expect(screen.getByRole('columnheader',{name:'Multi-agent'})).toBeTruthy()
   expect(screen.getByRole('checkbox',{name:'Orchestrator · '+id})).toBe(orchestrator)
   expect(orchestrator.checked).toBe(true)
   expect(screen.getByRole('checkbox',{name:'Tools · '+id})).toBe(role)
   expect(role.checked).toBe(true)
   expect((screen.getByRole('radio',{name:'Primary · '+id}) as HTMLInputElement).checked).toBe(true)
   expect(filter.value).toBe('Original')
   expect(screen.getByText('Original technical detail: EXACT upstream warning')).toBeTruthy()
   expect(fetcher.mock.calls.length).toBe(count)
   fireEvent.click(screen.getByRole('button',{name:'Save',exact:true}))
   await screen.findByText('Selection saved.')
   expect(saved).toEqual({expected_revision:'revision-original',main_chat:id,models:[{provider_id:'provider-original',model_id:'model-original',chat:true,orchestrator:true,agent_types:['tool']}]})
   expect(policyChanged).toHaveBeenCalledTimes(1)
   const after=fetcher.mock.calls.length
   switchTo('es')
   expect(screen.getByText('Selección guardada.')).toBeTruthy()
   expect(fetcher.mock.calls.length).toBe(after)
   expect(policyChanged).toHaveBeenCalledTimes(1)
  }finally{window.removeEventListener('adl-model-policy-changed',policyChanged)}
 })
})
