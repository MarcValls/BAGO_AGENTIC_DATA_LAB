// @vitest-environment jsdom
import React from 'react'
import {afterEach,beforeEach,expect,it,vi} from 'vitest'
import {cleanup,fireEvent,render,screen,waitFor,within} from '@testing-library/react'
import AgentTasks from '../../../src/components/AgentTasks'
import {resetLocaleForTests,setLocale,t} from '../../../src/i18n'

const task={prompt:'Solicitud plantilla {{fecha_1}}',dates:[{key:'fecha_1',label:'Entrega',value:'2026-11-01'}]}
const answer='Respuesta distinta del agente\n\n  Espacios conservados\n<img src=x onerror=alert(1)>\n'+('línea de respuesta\n'.repeat(80))
const run={run_id:'run_fixture',agent_id:'fixture',task_revision:'saved-1',task_snapshot:task,rendered_prompt:'Solicitud plantilla 2026-11-01',provider_id:'synthetic',model_id:'synthetic',workspace_root:'D:/fixture',source_run_id:null,created_at:'2026-11-01T00:00:00Z',completed_at:'2026-11-01T00:00:01Z',status:'answered',answer,error:null}
const response=(body:unknown,status=200)=>({ok:status<400,status,json:async()=>body})
function server(runs:unknown[]=[run]) {
 const calls:Array<{url:string;method:string;body:unknown}>=[]
 vi.stubGlobal('fetch',vi.fn(async(url:string,init?:RequestInit)=>{
  const method=init?.method??'GET';calls.push({url,method,body:init?.body?JSON.parse(String(init.body)):null})
  if(url==='/api/agents/list')return response({agents:[{id:'fixture',config:{name:'Fixture',description:'No inference'}}]})
  if(url.endsWith('/task-runs?limit=50'))return response({runs})
  if(url.endsWith('/task')&&method==='GET')return response({agent_id:'fixture',task,revision:'saved-1'})
  if(url.endsWith('/task')&&method==='PUT')return response({agent_id:'fixture',task:(JSON.parse(String(init?.body))).task,revision:'saved-2'})
  throw Error('Unexpected fixture request '+method+' '+url)
 }))
 return calls
}
async function openHistory() {
 await screen.findByRole('textbox',{name:t('agents.AgentTaskForm.tarea')})
 const history=screen.getByRole('region',{name:t('agents.AgentTasks.historial_de_tareas')})
 const details=history.querySelector<HTMLDetailsElement>('details.agent-task-run')!
 await waitFor(()=>expect(details).not.toBeNull())
 fireEvent.click(details.querySelector('summary')!)
 return {history,details}
}
beforeEach(()=>{localStorage.clear();resetLocaleForTests();setLocale('es')})
afterEach(()=>{cleanup();vi.unstubAllGlobals()})

it.each(['es','en'] as const)('separates real sent text from the full escaped answer and labels copy precisely in %s',async locale=>{
 setLocale(locale);const calls=server();render(<AgentTasks initialAgentId="fixture"/>)
 const {history,details}=await openHistory()
 const heading=within(history).getByRole('heading',{name:locale==='es'?'Respuesta del agente':'Agent response'})
 const pre=details.querySelector('.agent-task-answer')!
 expect(pre.textContent).toBe(answer);expect(pre.querySelector('img')).toBeNull()
 const sent=details.querySelector<HTMLDetailsElement>('.agent-task-sent-request')!
 expect(sent.open).toBe(false);expect(sent.querySelector('.agent-task-run-prompt')!.textContent).toBe(run.rendered_prompt)
 expect(heading.compareDocumentPosition(sent)&Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
 expect(within(history).getByText(locale==='es'?'Solicitud enviada':'Sent request')).toBeTruthy()
 expect(within(history).getByText(t('agents.AgentTasks.answer_scope'))).toBeTruthy()
 fireEvent.click(within(history).getByRole('button',{name:locale==='es'?'Copiar como borrador':'Copy to draft'}))
 expect((screen.getByRole('textbox',{name:t('agents.AgentTaskForm.tarea')}) as HTMLTextAreaElement).value).toBe(task.prompt)
 expect(screen.getByText(t('agents.AgentTasks.sin_guardar'))).toBeTruthy()
 expect((screen.getByRole('button',{name:t('agents.AgentTasks.ejecutar_tarea')}) as HTMLButtonElement).disabled).toBe(true)
 expect(calls.filter(c=>c.method!=='GET')).toEqual([])
 fireEvent.click(screen.getByRole('button',{name:t('agents.AgentTasks.guardar_tarea')}))
 await screen.findByText(t('agents.AgentTasks.tarea_guardada'))
 expect(calls.filter(c=>c.method!=='GET').map(c=>c.method)).toEqual(['PUT'])
 expect(calls.filter(c=>c.url.endsWith('/task-runs')&&c.method==='POST')).toEqual([])
})
it('retains an explicit empty history without inventing a request or answer',async()=>{
 const calls=server([]);render(<AgentTasks initialAgentId="fixture"/>);await screen.findByText(t('agents.AgentTasks.sin_ejecuciones'))
 expect(screen.queryByRole('heading',{name:'Respuesta del agente'})).toBeNull();expect(calls.filter(c=>c.method!=='GET')).toEqual([])
})
it('shows a failed run error separately from its sent request without claiming an answer',async()=>{
 server([{...run,status:'failed',answer:null,error:{code:'synthetic_failure',message:'Fallo sintético'}}]);render(<AgentTasks initialAgentId="fixture"/>)
 const {details}=await openHistory();expect(within(details).getByRole('alert').textContent).toContain('Fallo sintético');expect(details.querySelector('.agent-task-answer')).toBeNull()
 expect(details.querySelector('.agent-task-run-prompt')!.textContent).toBe(run.rendered_prompt)
 expect(screen.queryByText(t('agents.AgentTasks.answer_scope'))).toBeNull()
})
it('rejects an answered state with an empty answer instead of substituting the sent request',async()=>{
 server([{...run,answer:''}]);render(<AgentTasks initialAgentId="fixture"/>);expect((await screen.findByRole('alert')).textContent).toContain('estado de ejecución incoherente')
 expect(screen.queryByText('Respuesta recibida')).toBeNull();expect(document.querySelector('.agent-task-answer')).toBeNull()
})
