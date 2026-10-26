// @vitest-environment jsdom
import React from 'react'
import {afterEach,beforeEach,expect,it,vi} from 'vitest'
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import {resetLocaleForTests,setLocale,t} from '../../src/i18n'
import AgentBuilder,{type AgentConfig} from '../../src/components/AgentBuilder'

const response=(data:any)=>({ok:true,status:200,json:async()=>data})
const profile:AgentConfig={name:'Fixture',description:'Synthetic fixture',type:'tool',system_prompt:'Use granted tools only.',tools:[],task:{prompt:'Prepare a synthetic file.',dates:[]}}
const entries=[{id:'filesystem_plan',name:'Preparar archivos',name_en:'Plan files',status:'AVAILABLE'},{id:'delivery_review',name:'Revisar entrega',name_en:'Review delivery',status:'AVAILABLE'},{id:'mcp.execute',name:'MCP',status:'UNAVAILABLE'}]
beforeEach(()=>{localStorage.clear();resetLocaleForTests()})
afterEach(()=>{cleanup();vi.unstubAllGlobals()})

function setup(locale:'es'|'en'='es'){
 setLocale(locale)
 const calls:any[]=[]
 vi.stubGlobal('fetch',vi.fn(async(path:string,init?:RequestInit)=>{
   if(init?.method){calls.push({path,body:JSON.parse(String(init.body))});return response({id:'fixture',config:calls.at(-1).body})}
   if(path==='/api/capabilities')return response({agent_tools:entries})
   if(path==='/api/agent-tools/templates')return response({templates:[{id:'delivery-reviewer',config:{...profile,name:'Revisor',tools:['delivery_review']}}]})
   return response({models:[{provider_id:'ollama-cloud',label:'Ollama',state:'ready',model_id:'fixture-model',agent_types:['tool']}]})
 }))
 render(<AgentBuilder initialAgent={profile} agentId="fixture"/>)
 return calls
}

it('uses the raw tool enum in the selector and persists real assignments from the server registry',async()=>{
 const calls=setup()
 expect((screen.getByLabelText('Tipo de agente') as HTMLSelectElement).value).toBe('tool')
 fireEvent.click(await screen.findByLabelText('Preparar archivos'))
 expect((screen.getByLabelText(/^MCP/) as HTMLInputElement).disabled).toBe(true)
 fireEvent.click(screen.getByRole('button',{name:/Vista previa/}))
 fireEvent.click(screen.getByRole('button',{name:t('agents.AgentBuilder.save_changes')}))
 await waitFor(()=>expect(calls).toHaveLength(1))
 expect(calls[0].body.type).toBe('tool');expect(calls[0].body.tools).toEqual(['filesystem_plan'])
 expect(calls[0].path).toBe('/api/agents/fixture')
})

it('selects a canonical reviewer template without enabling filesystem or sending',async()=>{
 setup()
 fireEvent.click(await screen.findByRole('button',{name:t('agentTools.useTemplate')}))
 await screen.findByDisplayValue('Revisor')
 expect((screen.getByLabelText('Revisar entrega') as HTMLInputElement).checked).toBe(true)
 expect((screen.getByLabelText('Preparar archivos') as HTMLInputElement).checked).toBe(false)
})

it('renders the registry labels and enum correctly in English',async()=>{
 setup('en')
 expect((screen.getByLabelText('Agent Type') as HTMLSelectElement).value).toBe('tool')
 expect(await screen.findByLabelText('Plan files')).toBeTruthy()
 expect(screen.getByRole('button',{name:'Use template: Delivery reviewer'})).toBeTruthy()
})
