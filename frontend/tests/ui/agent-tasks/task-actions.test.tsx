// @vitest-environment jsdom
import React from 'react'
import {afterEach,beforeEach,expect,it,vi} from 'vitest'
import {act,cleanup,fireEvent,render,screen,waitFor,within} from '@testing-library/react'
import AgentTasks from '../../../src/components/AgentTasks'
import {resetLocaleForTests,setLocale,t} from '../../../src/i18n'

const A='agent_12345678',B='agent_87654321',sourceHash='d'.repeat(64),profileHash='c'.repeat(64)
const task={prompt:'Current saved task',dates:[]}
const source={run_id:'taskrun_'+'1'.repeat(32),agent_id:A,task_revision:'b'.repeat(64),task_snapshot:{prompt:'Historical request',dates:[]},rendered_prompt:'Historical request',provider_id:'fixture',model_id:'author',workspace_root:'D:/fixture',source_run_id:null,created_at:'2026-11-01T00:00:00Z',completed_at:'2026-11-01T00:00:01Z',status:'answered',answer:'Original model answer',error:null}
const target={agent_id:B,name:'Independent fixture',profile_sha256:profileHash,provider_id:'fixture',model_id:'reviewer'}
const reply=(body:unknown,status=200)=>({ok:status<400,status,json:async()=>body})
function fixture(options:{reviewers?:typeof target[];reviewError?:boolean;invalidReview?:boolean;runningSource?:boolean}={}) {
 const state={task:structuredClone(task),revision:'a'.repeat(64),failTask:false,reviews:[] as any[]}
 const run=options.runningSource?{...source,status:'running',answer:null,completed_at:null}:source
 const calls:Array<{url:string;method:string;body:any}>=[]
 vi.stubGlobal('fetch',vi.fn(async(url:string,init?:RequestInit)=>{
  const method=init?.method??'GET',body=init?.body?JSON.parse(String(init.body)):null;calls.push({url,method,body})
  if(url==='/api/agents/list')return reply({agents:[{id:A,config:{name:'Author',description:''}},{id:B,config:{name:'Independent fixture',description:''}}]})
  if(url.endsWith('/task')&&method==='GET')return state.failTask?reply({detail:{code:'fixture_failure',message:'Read failed'}},503):reply({agent_id:A,task:state.task,revision:state.revision})
  if(url.endsWith('/task')&&method==='PUT'){state.task=body.task;state.revision='e'.repeat(64);return reply({agent_id:A,task:state.task,revision:state.revision})}
  if(url.endsWith('/task-runs?limit=50'))return reply({runs:[run]})
  if(url.endsWith('/reviews')&&method==='GET')return reply({source_run:run,source_sha256:sourceHash,reviewers:options.reviewers??[target],reviews:state.reviews,unavailable_reviewer_count:0})
  if(url.endsWith('/reviews')&&method==='POST'){
   if(options.reviewError)return reply({detail:{code:'task_review_profile_changed',message:'Reviewer profile changed'}},409)
   const item={review_id:'taskreview_'+'2'.repeat(32),source_agent_id:A,source_run_id:source.run_id,source_sha256:sourceHash,source_snapshot:source,
    reviewer_agent_id:options.invalidReview?A:B,reviewer_profile_sha256:profileHash,reviewer_name:target.name,
    review_request:JSON.stringify({source_agent_id:A,source_run_id:source.run_id,source_sha256:sourceHash,source_snapshot:source}),
    created_at:'2026-11-01T00:01:00Z',completed_at:'2026-11-01T00:01:01Z',status:'answered',answer:'Reviewer exact answer <script>inert</script>',error:null}
   state.reviews=[item];return reply(item)
  }
  throw Error('Unexpected fixture '+method+' '+url)
 }))
 return {state,calls}
}
async function loaded(){
 // Flush the agent-list effect and its follow-up task/history reload.
 await act(async()=>{})
 await waitFor(()=>{
  expect((screen.getByRole('combobox',{name:t('agents.AgentTasks.agente_para_tareas')}) as HTMLSelectElement).disabled).toBe(false)
  expect((screen.getByRole('textbox',{name:t('agents.AgentTaskForm.tarea')}) as HTMLTextAreaElement).value).toBe(task.prompt)
  expect((screen.getByRole('button',{name:t('agents.AgentManagement.actualizar')}) as HTMLButtonElement).disabled).toBe(false)
 })
}
async function openReview(){
 await loaded();const history=screen.getByRole('region',{name:t('agents.AgentTasks.historial_de_tareas')})
 fireEvent.click(history.querySelector('summary')!);fireEvent.click(within(history).getByRole('button',{name:t('agents.AgentTasks.independent_review')}))
 return await screen.findByRole('region',{name:t('agents.AgentTasks.independent_review')})
}
async function consent(dialog:HTMLElement){
 await within(dialog).findByLabelText(t('agents.AgentTasks.reviewer_label'))
 expect(within(dialog).queryByRole('checkbox')).toBeNull()
}
beforeEach(()=>{localStorage.clear();resetLocaleForTests();setLocale('es')})
afterEach(()=>{cleanup();vi.unstubAllGlobals()})

it.each(['es','en'] as const)('loads the current saved task and focuses its editor without saving or running in %s',async locale=>{
 setLocale(locale);const f=fixture();render(<AgentTasks initialAgentId={A}/>);await loaded()
 f.state.task={prompt:'Server current task',dates:[]};f.state.revision='f'.repeat(64)
 fireEvent.click(screen.getByRole('button',{name:locale==='es'?'Editar tarea manualmente':'Edit task manually'}))
 await screen.findByText(t('agents.AgentTasks.manual_edit_notice'))
 const editor=screen.getByRole('textbox',{name:t('agents.AgentTaskForm.tarea')}) as HTMLTextAreaElement
 expect(editor.value).toBe('Server current task');expect(document.activeElement).toBe(editor)
 expect(f.calls.filter(c=>c.method!=='GET')).toEqual([])
 fireEvent.change(editor,{target:{value:'Reviewed draft change'}})
 expect((screen.getByRole('button',{name:t('agents.AgentTasks.ejecutar_tarea')}) as HTMLButtonElement).disabled).toBe(true)
 fireEvent.click(screen.getByRole('button',{name:t('agents.AgentTasks.guardar_tarea')}));await screen.findByText(t('agents.AgentTasks.tarea_guardada'))
 expect(f.calls.filter(c=>c.method!=='GET').map(c=>c.method)).toEqual(['PUT'])
})
it('does not silently discard a dirty draft when manual edit is requested',async()=>{
 const f=fixture();render(<AgentTasks initialAgentId={A}/>);await loaded()
 const editor=screen.getByRole('textbox',{name:t('agents.AgentTaskForm.tarea')}) as HTMLTextAreaElement
 fireEvent.change(editor,{target:{value:'Unsaved draft'}});const before=f.calls.length
 fireEvent.click(screen.getByRole('button',{name:t('agents.AgentTasks.edit_manually')}))
 const confirmation=screen.getByRole('alertdialog');expect(f.calls).toHaveLength(before)
 fireEvent.click(within(confirmation).getByRole('button',{name:t('agents.AgentManagement.cancelar')}));expect(editor.value).toBe('Unsaved draft')
 fireEvent.click(screen.getByRole('button',{name:t('agents.AgentTasks.edit_manually')}))
 fireEvent.click(screen.getByRole('button',{name:t('agents.AgentTasks.load_saved_task')}));await screen.findByText(t('agents.AgentTasks.manual_edit_notice'))
 expect(editor.value).toBe(task.prompt);expect(f.calls.filter(c=>c.method!=='GET')).toEqual([])
})
it('retains the draft and surfaces a failed manual reload',async()=>{
 const f=fixture();render(<AgentTasks initialAgentId={A}/>);await loaded();f.state.failTask=true
 fireEvent.click(screen.getByRole('button',{name:t('agents.AgentTasks.edit_manually')}));expect(await screen.findByRole('alert')).toBeTruthy()
 expect((screen.getByRole('textbox',{name:t('agents.AgentTaskForm.tarea')}) as HTMLTextAreaElement).value).toBe(task.prompt)
 expect(f.calls.filter(c=>c.method!=='GET')).toEqual([])
})
it.each(['es','en'] as const)('automatically reviews with the only separate profile, preserves bound evidence and never runs the original task in %s',async locale=>{
 setLocale(locale);const f=fixture();render(<AgentTasks initialAgentId={A}/>);const dialog=await openReview()
 const select=await within(dialog).findByLabelText(t('agents.AgentTasks.reviewer_label'))
 expect(dialog.closest('details.agent-task-run')?.querySelector('.agent-task-run-meta')?.textContent).toContain(source.run_id)
 expect(dialog.closest('.agent-task-history')).toBe(screen.getByRole('region',{name:t('agents.AgentTasks.historial_de_tareas')}))
 expect(within(select).queryByRole('option',{name:/Author/})).toBeNull()
 expect(within(dialog).queryByRole('checkbox')).toBeNull()
 await consent(dialog);expect(await within(dialog).findByText('Reviewer exact answer <script>inert</script>')).toBeTruthy()
 expect(dialog.querySelector('script')).toBeNull();expect(within(dialog).getByText(t('agents.AgentTasks.review_advisory'))).toBeTruthy()
 const posts=f.calls.filter(c=>c.method==='POST');expect(posts).toHaveLength(1)
 expect(posts[0].url).toBe(`/api/agents/${A}/task-runs/${source.run_id}/reviews`)
 expect(posts[0].body).toEqual({reviewer_agent_id:B,expected_source_sha256:sourceHash,expected_reviewer_sha256:profileHash,confirmed:true})
 expect(f.calls.filter(c=>c.url.endsWith('/task-runs')&&c.method==='POST')).toEqual([])
 fireEvent.click(within(dialog).getByRole('button',{name:t('agents.AgentTasks.close_review')}))
 const history=screen.getByRole('region',{name:t('agents.AgentTasks.historial_de_tareas')})
 fireEvent.click(within(history).getByRole('button',{name:t('agents.AgentTasks.independent_review')}))
 expect(await screen.findByText('Reviewer exact answer <script>inert</script>')).toBeTruthy();expect(f.calls.filter(c=>c.method==='POST')).toHaveLength(1)
})
it('explains missing other profiles honestly and cannot submit self-review',async()=>{
 const f=fixture({reviewers:[]});render(<AgentTasks initialAgentId={A}/>);const dialog=await openReview()
 expect(await within(dialog).findByText(t('agents.AgentTasks.no_reviewer'))).toBeTruthy()
 expect(within(dialog).queryByRole('button',{name:t('agents.AgentTasks.confirm_review')})).toBeNull()
 expect(f.calls.filter(c=>c.method!=='GET')).toEqual([])
})
it('shows a stale reviewer rejection without rendering a successful review or running the original',async()=>{
 const f=fixture({reviewError:true});render(<AgentTasks initialAgentId={A}/>);const dialog=await openReview();await consent(dialog)
 expect(await within(dialog).findByRole('alert')).toBeTruthy();expect(within(dialog).queryByText('Reviewer exact answer <script>inert</script>')).toBeNull()
 expect(f.calls.filter(c=>c.method==='POST')).toHaveLength(1)
})
it('rejects a returned self-review rather than labelling it independent',async()=>{
 fixture({invalidReview:true});render(<AgentTasks initialAgentId={A}/>);const dialog=await openReview();await consent(dialog)
 expect((await within(dialog).findByRole('alert')).textContent).toBe(t('agents.AgentTasks.invalid_review'))
 expect(within(dialog).queryByText('Reviewer exact answer <script>inert</script>')).toBeNull()
})
it('does not offer model review for a running source without an answer',async()=>{
 fixture({runningSource:true});render(<AgentTasks initialAgentId={A}/>);await loaded()
 const history=screen.getByRole('region',{name:t('agents.AgentTasks.historial_de_tareas')});fireEvent.click(history.querySelector('summary')!)
 expect((within(history).getByRole('button',{name:t('agents.AgentTasks.independent_review')}) as HTMLButtonElement).disabled).toBe(true)
})
