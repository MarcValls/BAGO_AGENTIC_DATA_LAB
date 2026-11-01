// @vitest-environment jsdom
import React from 'react'
import {afterEach,beforeEach,expect,it,vi} from 'vitest'
import {act,cleanup,fireEvent,render,screen,waitFor,within} from '@testing-library/react'
import TaskExecutionPanel from '../../../src/components/TaskExecutionPanel'
import {resetLocaleForTests,setLocale,t} from '../../../src/i18n'

const agent='agent_12345678',hash='a'.repeat(64),executionId='taskexec_'+'1'.repeat(32),planId='taskplan_'+'2'.repeat(32)
const context={project_id:'project-fixture',root:'D:/authorized',binding:'binding-fixture',revision:'b'.repeat(64)}
const model={provider_id:'fixture',model_id:'model-a',state:'configured_unverified',orchestrator_enabled:true,agent_types:['tool']}
const profile={id:agent,config:{name:'Fixture task agent',description:'Fixture description',type:'tool',provider_id:'fixture',model_id:'model-a',system_prompt:'Review the task',tools:[],task:{prompt:'Make a file',dates:[]}}}
const prepared=()=>({execution_id:executionId,plan_id:planId,plan_revision:1,plan_sha256:hash,status:'AWAITING_ACCEPTANCE',plan:{project:{project_id:context.project_id,root:context.root,binding:context.binding,permissions_revision:context.revision},agent:{agent_id:agent,profile_sha256:'c'.repeat(64),created_for_task:true},model:{provider_id:'fixture',model_id:'model-a',policy_eligible:true,catalog_state:'configured_unverified',probe_state:'operation_ready'},steps:[{step_id:'s1',type:'filesystem',operation:'write',arguments:{target:'result.txt',content:'fixture only'},depends_on:[]}],required_checks:[],review:{status:'not_required',reviewer_id:null,reviewer_sha256:null},scopes:{requested:['write:result.txt'],granted:['write:result.txt']}}})
const reply=(body:any,status=200)=>({ok:status<400,status,json:async()=>body})
function fixture(options:{models?:any[];profiles?:any[];prepareError?:string;invalidPlan?:boolean;acceptFailure?:boolean;slowAccept?:boolean}={}){
 const calls:Array<{url:string;method:string;body:any}>=[],state={record:prepared(),profile:structuredClone(profile),accepts:0}
 let release:()=>void=()=>{}
 vi.stubGlobal('fetch',vi.fn(async(url:string,init?:RequestInit)=>{
  const method=init?.method||'GET',body=init?.body?JSON.parse(String(init.body)):null;calls.push({url,method,body})
  if(url==='/api/providers/chat-models')return reply({models:options.models??[model]})
  if(url==='/api/agents/list')return reply({agents:options.profiles??[state.profile]})
  if(url==='/api/project-permissions')return reply(context)
  if(url===`/api/agents/${agent}`&&method==='GET')return reply(state.profile)
  if(url===`/api/agents/${agent}`&&method==='PUT'){state.profile={...state.profile,config:{...state.profile.config,...body}};return reply(state.profile)}
  if(url==='/api/task-executions/plans'){
   if(options.prepareError)return reply({error:{code:options.prepareError,message:'Preparation blocked',retryable:false,details:{}}},409)
   return reply(options.invalidPlan?{...state.record,plan_sha256:'bad'}:state.record)
  }
  if(url===`/api/task-executions/plans/${planId}/accept`){
   state.accepts++
   if(options.slowAccept)await new Promise<void>(resolve=>{release=resolve})
   if(options.acceptFailure)return reply({error:{code:'plan_stale',message:'Plan changed',retryable:false,details:{}}},409)
   state.record={...state.record,status:'SUCCEEDED',step_results:{s1:{step_id:'s1',status:'SUCCEEDED',receipt:{receipt_id:'receipt-fixture',status:'PASS'},receipt_sha256:'d'.repeat(64)}}} as any
   return reply({execution_id:executionId,plan_id:planId,status:'SUCCEEDED',step_results:(state.record as any).step_results})
  }
  if(url===`/api/task-executions/${executionId}/stop`){state.record={...state.record,status:'STOPPED_BEFORE_EFFECT'};return reply(state.record)}
  if(url===`/api/task-executions/${executionId}`)return reply(state.record)
  throw Error(`Unexpected fixture ${method} ${url}`)
 }))
 return {calls,state,release:()=>release()}
}
async function open(){fireEvent.click(screen.getByRole('button',{name:t('agents.TaskExecution.title')}))}
async function plan(){await screen.findByText(t('agents.TaskExecution.state.AWAITING_ACCEPTANCE'))}
beforeEach(()=>{sessionStorage.clear();localStorage.clear();resetLocaleForTests();setLocale('es');let next=0;vi.stubGlobal('crypto',{randomUUID:()=>`00000000-0000-4000-8000-${String(++next).padStart(12,'0')}`})})
afterEach(()=>{cleanup();vi.unstubAllGlobals()})

it('keeps a compact unopened panel inert and automatically prepares once with real context after opening',async()=>{
 const f=fixture();render(<TaskExecutionPanel taskText="Write result.txt"/>);expect(f.calls).toHaveLength(0);await open();await plan()
 expect(f.calls.filter(c=>c.url.endsWith('/plans'))).toHaveLength(1)
 const body=f.calls.find(c=>c.url.endsWith('/plans'))!.body
 expect(body).toMatchObject({task_text:'Write result.txt',expected_project_id:context.project_id,expected_binding:context.binding,expected_permissions_revision:context.revision,model_selection:{mode:'auto'},agent_selection:{mode:'auto'}})
 expect(f.state.accepts).toBe(0);expect(screen.queryByRole('checkbox')).toBeNull()
 expect((screen.getByRole('button',{name:t('agents.TaskExecution.accept')}) as HTMLButtonElement).disabled).toBe(false)
})
it('does not need a saved agent when Auto prepares a task-specific profile',async()=>{
 fixture({profiles:[]});render(<TaskExecutionPanel taskText="Write result.txt"/>);await open();await plan();expect(screen.getByText(/Agente listo/)).toBeTruthy()
})
it.each(['es','en'] as const)('one acceptance sends exact hash and revision and renders actual returned receipts in %s',async locale=>{
 setLocale(locale);const f=fixture();render(<TaskExecutionPanel taskText="Write result.txt"/>);await open();await plan()
 const accept=screen.getByRole('button',{name:t('agents.TaskExecution.accept')});fireEvent.click(accept);fireEvent.click(accept)
 await screen.findByText(t('agents.TaskExecution.state.SUCCEEDED'))
 expect(f.state.accepts).toBe(1)
 expect(f.calls.find(c=>c.url.endsWith('/accept'))!.body).toMatchObject({expected_plan_sha256:hash,expected_plan_revision:1,confirmed:true})
 expect(screen.getByText(t('agents.TaskExecution.receipt'))).toBeTruthy();expect(screen.getAllByText(/receipt-fixture/)).toHaveLength(2)
})
it('shows unavailable models without pretending preparation or execution happened',async()=>{
 const f=fixture({models:[{...model,state:'not_configured'}]});render(<TaskExecutionPanel taskText="Write result.txt"/>);await open();await screen.findByText(t('agents.TaskExecution.noModel'))
 expect(f.calls.some(c=>c.method==='POST')).toBe(false);expect(screen.queryByRole('button',{name:t('agents.TaskExecution.accept')})).toBeNull()
})
it('the last model selection automatically replans using an explicit real provider/model without modifying settings',async()=>{
 const f=fixture();render(<TaskExecutionPanel taskText="Write result.txt"/>);await open();await plan()
 fireEvent.change(screen.getByLabelText(t('agents.TaskExecution.model')),{target:{value:JSON.stringify(['fixture','model-a'])}});await plan()
 expect(f.calls.filter(c=>c.url.endsWith('/plans'))).toHaveLength(2)
 expect(f.calls.filter(c=>c.url.endsWith('/plans'))[1].body.model_selection).toEqual({mode:'explicit',provider_id:'fixture',model_id:'model-a'})
 expect(f.calls.some(c=>c.method==='PUT')).toBe(false)
})
it('existing-agent selection automatically replans without inventing a profile hash from the list response',async()=>{
 const f=fixture();render(<TaskExecutionPanel taskText="Write result.txt"/>);await open();await plan()
 fireEvent.change(screen.getByLabelText(t('agents.TaskExecution.agent')),{target:{value:agent}});await plan()
 expect(f.calls.filter(c=>c.url.endsWith('/plans'))[1].body.agent_selection).toEqual({mode:'existing',agent_id:agent})
})
it('optional edit pauses acceptance and saving only profile fields invalidates and prepares a new plan',async()=>{
 const f=fixture();render(<TaskExecutionPanel taskText="Write result.txt"/>);await open();await plan()
 fireEvent.click(screen.getByRole('button',{name:t('agents.TaskExecution.edit')}));const name=await screen.findByLabelText(t('agents.TaskExecution.name'))
 expect((screen.getByRole('button',{name:t('agents.TaskExecution.accept')}) as HTMLButtonElement).disabled).toBe(true)
 fireEvent.change(name,{target:{value:'Edited task agent'}});fireEvent.click(screen.getByRole('button',{name:t('agents.TaskExecution.saveAgent')}));await plan()
 await waitFor(()=>expect(f.calls.filter(c=>c.url.endsWith('/plans'))).toHaveLength(2))
 expect(f.calls.find(c=>c.method==='PUT')!.body).toEqual({name:'Edited task agent',description:profile.config.description,type:profile.config.type,system_prompt:profile.config.system_prompt})
 expect(f.state.accepts).toBe(0)
})
it('closing optional edit unchanged resumes the same exact prepared plan without any write',async()=>{
 const f=fixture();render(<TaskExecutionPanel taskText="Write result.txt"/>);await open();await plan();fireEvent.click(screen.getByRole('button',{name:t('agents.TaskExecution.edit')}));await screen.findByLabelText(t('agents.TaskExecution.name'));fireEvent.click(screen.getByRole('button',{name:t('agents.TaskExecution.cancelEdit')}))
 expect((screen.getByRole('button',{name:t('agents.TaskExecution.accept')}) as HTMLButtonElement).disabled).toBe(false)
 expect(f.calls.filter(c=>c.url.endsWith('/plans'))).toHaveLength(1);expect(f.calls.some(c=>c.method==='PUT')).toBe(false)
})
it('rejects malformed plan identity and has no executable acceptance',async()=>{
 fixture({invalidPlan:true});render(<TaskExecutionPanel taskText="Write result.txt"/>);await open();await screen.findByText(t('agents.TaskExecution.invalid'));expect(screen.queryByRole('button',{name:t('agents.TaskExecution.accept')})).toBeNull()
})
it('surfaces scope denial as a blocker and never fabricates a successful result',async()=>{
 const f=fixture({prepareError:'scope_denied'});render(<TaskExecutionPanel taskText="Write result.txt"/>);await open();await screen.findByText(/scope_denied/);expect(f.state.accepts).toBe(0);expect(screen.queryByText(t('agents.TaskExecution.state.SUCCEEDED'))).toBeNull()
})
it('preserves uncertain acceptance and requires read-only recovery before any repeated effect',async()=>{
 const f=fixture({acceptFailure:true});render(<TaskExecutionPanel taskText="Write result.txt"/>);await open();await plan();fireEvent.click(screen.getByRole('button',{name:t('agents.TaskExecution.accept')}));await screen.findByText(t('agents.TaskExecution.unknown'))
 expect(f.state.accepts).toBe(1);expect((screen.getByRole('button',{name:t('agents.TaskExecution.accept')}) as HTMLButtonElement).disabled).toBe(true)
})
it('STOP persists through its own route without reaccepting or rolling back the plan',async()=>{
 const f=fixture();render(<TaskExecutionPanel taskText="Write result.txt"/>);await open();await plan();fireEvent.click(screen.getByRole('button',{name:t('agents.TaskExecution.cancelPlan')}));await screen.findByText(t('agents.TaskExecution.state.STOPPED_BEFORE_EFFECT'))
 expect(f.calls.find(c=>c.url.endsWith('/stop'))!.body).toEqual({reason:'user_stop'});expect(f.state.accepts).toBe(0)
})
it('remount reads the durable prepared record without asking the provider to prepare again',async()=>{
 const f=fixture();const first=render(<TaskExecutionPanel sourceIdentity="persisted-source" taskText="Write result.txt"/>);await open();await plan();first.unmount()
 render(<TaskExecutionPanel sourceIdentity="persisted-source" taskText="Write result.txt"/>);await open();await plan()
 expect(f.calls.filter(c=>c.url.endsWith('/plans'))).toHaveLength(1);expect(f.calls.some(c=>c.url===`/api/task-executions/${executionId}`)).toBe(true)
})
it('automatic progress does not move keyboard focus from the user-selected model',async()=>{
 fixture();render(<TaskExecutionPanel taskText="Write result.txt"/>);await open();const select=await screen.findByLabelText(t('agents.TaskExecution.model'));select.focus();await plan();expect(document.activeElement).toBe(select)
})
it('a durable PREPARING record remains readable and stoppable without an executable plan',async()=>{
 const f=fixture();f.state.record={...prepared(),status:'PREPARING',plan_sha256:'',plan:null} as any
 render(<TaskExecutionPanel taskText="Write result.txt"/>);await open();await screen.findByText(t('agents.TaskExecution.state.PREPARING'))
 expect(screen.queryByRole('button',{name:t('agents.TaskExecution.accept')})).toBeNull()
 fireEvent.click(screen.getByRole('button',{name:t('agents.TaskExecution.cancelPlan')}));await screen.findByText(t('agents.TaskExecution.state.STOPPED_BEFORE_EFFECT'));expect(f.state.accepts).toBe(0)
})
it('rejects a plan from a different bound project before an acceptance can be sent',async()=>{
 const f=fixture();f.state.record.plan.project.binding='different-binding'
 render(<TaskExecutionPanel taskText="Write result.txt"/>);await open();await screen.findByText(t('agents.TaskExecution.bindingChanged'));expect(f.state.accepts).toBe(0)
 expect(screen.queryByRole('button',{name:t('agents.TaskExecution.accept')})).toBeNull()
})
it('unsupported operations cannot look like an acceptable real execution',async()=>{
 const f=fixture();f.state.record.plan.steps[0].type='arbitrary_shell'
 render(<TaskExecutionPanel taskText="Write result.txt"/>);await open();await screen.findByText(t('agents.TaskExecution.unsupported'));expect(f.state.accepts).toBe(0)
})
it('a profile changed elsewhere during optional editing is not overwritten or silently accepted',async()=>{
 const f=fixture();render(<TaskExecutionPanel taskText="Write result.txt"/>);await open();await plan();fireEvent.click(screen.getByRole('button',{name:t('agents.TaskExecution.edit')}));await screen.findByLabelText(t('agents.TaskExecution.name'))
 f.state.profile={...f.state.profile,config:{...f.state.profile.config,name:'Concurrent edit'}}
 fireEvent.click(screen.getByRole('button',{name:t('agents.TaskExecution.saveAgent')}));await screen.findByText(t('agents.TaskExecution.profileChanged'))
 expect(f.calls.some(c=>c.method==='PUT')).toBe(false);expect((screen.getByRole('button',{name:t('agents.TaskExecution.accept')}) as HTMLButtonElement).disabled).toBe(true)
})
it('does not create a second preparation while the first POST awaits its ID',async()=>{
 const f=fixture(),original=globalThis.fetch;let first=true,release:(value:any)=>void=()=>{}
 f.state.record={...prepared(),status:'PREPARING',plan_sha256:'',plan:null} as any
 vi.stubGlobal('fetch',vi.fn(async(url:string,init?:RequestInit)=>{
  if(url==='/api/task-executions/plans'&&first){first=false;const value=await original(url,init);return await new Promise(resolve=>{release=()=>resolve(value)})}
  return original(url,init)
 }))
 render(<TaskExecutionPanel taskText="Write result.txt"/>);await open();await waitFor(()=>expect(first).toBe(false))
 try{
  fireEvent.change(screen.getByLabelText(t('agents.TaskExecution.model')),{target:{value:JSON.stringify(['fixture','model-a'])}})
  fireEvent.change(screen.getByLabelText(t('agents.TaskExecution.agent')),{target:{value:agent}})
  fireEvent.change(screen.getByLabelText(t('agents.TaskExecution.task')),{target:{value:'Changed during pending preparation'}})
  await act(async()=>{await new Promise(resolve=>setTimeout(resolve,450))})
  expect(f.calls.filter(c=>c.url==='/api/task-executions/plans')).toHaveLength(1)
  for(const control of [screen.getByLabelText(t('agents.TaskExecution.model')),screen.getByLabelText(t('agents.TaskExecution.agent')),screen.getByLabelText(t('agents.TaskExecution.task'))])expect((control as HTMLInputElement).disabled).toBe(true)
 }finally{await act(async()=>{release(null)})}
 await screen.findByText(t('agents.TaskExecution.state.PREPARING'))
 expect((screen.getByLabelText(t('agents.TaskExecution.model')) as HTMLSelectElement).value).toBe('auto')
 expect((screen.getByLabelText(t('agents.TaskExecution.agent')) as HTMLSelectElement).value).toBe('auto')
 expect((screen.getByLabelText(t('agents.TaskExecution.task')) as HTMLTextAreaElement).value).toBe('Write result.txt')
 fireEvent.click(screen.getByRole('button',{name:t('agents.TaskExecution.refresh')}))
 await waitFor(()=>expect(f.calls.some(c=>c.url===`/api/task-executions/${executionId}`)).toBe(true))
 fireEvent.click(screen.getByRole('button',{name:t('agents.TaskExecution.cancelPlan')}))
 await screen.findByText(t('agents.TaskExecution.state.STOPPED_BEFORE_EFFECT'))
 expect(f.calls.filter(c=>c.url==='/api/task-executions/plans')).toHaveLength(1)
 expect(f.calls.find(c=>c.url.endsWith('/stop'))!.body).toEqual({reason:'user_stop'});expect(f.state.accepts).toBe(0)
})
it('an obsolete response from a different source identity cannot replace the current source plan',async()=>{
 const f=fixture(),original=globalThis.fetch;let first=true,release:()=>void=()=>{}
 vi.stubGlobal('fetch',vi.fn(async(url:string,init?:RequestInit)=>{
  if(url==='/api/task-executions/plans'&&first){first=false;await original(url,init);return await new Promise(resolve=>{release=()=>resolve(reply({...prepared(),plan_sha256:'f'.repeat(64)}))})}
  return original(url,init)
 }))
 const view=render(<TaskExecutionPanel sourceIdentity="old-human-source" taskText="Original task"/>);await open();await waitFor(()=>expect(first).toBe(false))
 view.rerender(<TaskExecutionPanel sourceIdentity="new-human-source" taskText="New explicit human task"/>);await plan()
 await act(async()=>{release()})
 fireEvent.click(screen.getByRole('button',{name:t('agents.TaskExecution.accept')}));await screen.findByText(t('agents.TaskExecution.state.SUCCEEDED'))
 const preparations=f.calls.filter(c=>c.url==='/api/task-executions/plans')
 expect(preparations).toHaveLength(2);expect(preparations.map(c=>c.body.task_text)).toEqual(['Original task','New explicit human task'])
 expect(f.calls.find(c=>c.url.endsWith('/accept'))!.body.expected_plan_sha256).toBe(hash)
})
it.each(['es','en'] as const)('shows a bounded human cause from preparation failure events in %s',async locale=>{
 setLocale(locale);const f=fixture()
 f.state.record={...prepared(),status:'FAILED_NO_EFFECT',plan:null,events:[{event_type:'PREPARATION_FAILED',payload:{reason_code:'profile_revision_changed'}},{event_type:'PREPARATION_FAILED',payload:{reason_code:'model_not_eligible'}}]} as any
 render(<TaskExecutionPanel taskText="Write result.txt"/>);await open()
 expect(await screen.findByRole('alert')).toHaveProperty('textContent',t('agents.TaskExecution.failure.model_not_eligible'))
 expect(screen.queryByText(t('agents.TaskExecution.failure.profile_revision_changed'))).toBeNull()
 expect(screen.queryByRole('button',{name:t('agents.TaskExecution.accept')})).toBeNull()
 expect(screen.queryByText(t('agents.TaskExecution.state.SUCCEEDED'))).toBeNull();expect(f.state.accepts).toBe(0)
})
it.each(['__proto__','<script>untrusted reason</script>'])('unknown failure reason %s remains technical data instead of becoming a human instruction',async reason=>{
 const f=fixture();f.state.record={...prepared(),status:'FAILED_NO_EFFECT',plan:null,events:[{event_type:'PREPARATION_FAILED',payload:{reason_code:reason}}]} as any
 const view=render(<TaskExecutionPanel taskText="Write result.txt"/>);await open()
 expect(await screen.findByRole('alert')).toHaveProperty('textContent',t('agents.TaskExecution.failure.unknown'))
 const details=screen.getByText(t('agents.TaskExecution.evidence')).closest('details')!
 expect(details.open).toBe(false);expect(details.querySelector('pre')?.textContent).toContain(reason)
 expect(view.container.querySelector('script')).toBeNull();expect(f.state.accepts).toBe(0)
})
it('persists the exact preparation identity before POST and recovers a lost response after remount with the same request ID',async()=>{
 const f=fixture(),original=globalThis.fetch;let loseFirst=true
 const key='bago.task-execution.v1:lost-response:preparation'
 vi.stubGlobal('fetch',vi.fn(async(url:string,init?:RequestInit)=>{
  if(url==='/api/task-executions/plans'){
   const body=JSON.parse(String(init?.body)),saved=JSON.parse(sessionStorage.getItem(key)||'null')
   expect(saved.request_id).toBe(body.request_id);expect(saved.input.task_text).toBe(body.task_text)
   const result=await original(url,init)
   if(loseFirst){loseFirst=false;throw Error('Lost preparation response')}
   return result
  }
  return original(url,init)
 }))
 const first=render(<TaskExecutionPanel sourceIdentity="lost-response" taskText="Write result.txt"/>);await open();await screen.findByText('Lost preparation response');first.unmount()
 render(<TaskExecutionPanel sourceIdentity="lost-response" taskText="Write result.txt"/>);await open();await plan()
 const preparedRequests=f.calls.filter(c=>c.url==='/api/task-executions/plans')
 expect(preparedRequests).toHaveLength(2);expect(preparedRequests[0].body).toEqual(preparedRequests[1].body)
 expect(f.state.accepts).toBe(0);expect(sessionStorage.getItem(key)).toBeNull()
})
it('does not start preparation when its recoverable identity cannot be persisted',async()=>{
 const f=fixture(),original=Storage.prototype.setItem
 const storage=vi.spyOn(Storage.prototype,'setItem').mockImplementation(function(this:Storage,key:string,value:string){if(key.endsWith(':preparation'))throw Error('Fixture storage blocked');return original.call(this,key,value)})
 try{
  render(<TaskExecutionPanel taskText="Write result.txt"/>);await open();await screen.findByText(t('agents.TaskExecution.storageBlocked'))
  expect(f.calls.some(c=>c.method==='POST')).toBe(false)
 }finally{storage.mockRestore()}
})

const nativeInventory=()=>({root:context.root,recursive:false,entries:[
 {path:'report.csv',kind:'file',snapshot:{sha256:'e'.repeat(64),size:23,mtime_ns:1793517900000000000,inode:12345}},
 {path:'archive',kind:'directory',snapshot:null},
]})
function inventoryFixture(inventory:any=nativeInventory(),status='SUCCEEDED',stepStatus='SUCCEEDED',receiptStatus='PASS'){
 const f=fixture(),record=prepared() as any
 record.status=status;record.plan.steps=[{step_id:'s1',type:'filesystem',operation:'inventory',arguments:{path:'.'},depends_on:[]}]
 record.step_results={s1:{step_id:'s1',status:stepStatus,receipt:{receipt_id:'native-read-fixture',operation:'inventory',status:receiptStatus,effect_executed:false,inventory_sha256:'f'.repeat(64),inventory},receipt_sha256:'d'.repeat(64)}}
 f.state.record=record
 return f
}
it.each(['es','en'] as const)('renders actual native file and directory inventory inside its succeeded step in %s',async locale=>{
 setLocale(locale);const f=inventoryFixture(),view=render(<TaskExecutionPanel taskText="List the folder"/>);await open()
 const table=await screen.findByRole('table',{name:t('agents.TaskExecution.inventory.title')})
 expect(table.closest('li')?.textContent).toContain('s1')
 const rows=within(table).getAllByRole('row');expect(rows).toHaveLength(3)
 expect(within(rows[1]).getAllByRole('cell').map(cell=>cell.textContent)).toEqual(['report.csv',t('agents.TaskExecution.inventory.file'),'23','e'.repeat(64)])
 expect(within(rows[2]).getAllByRole('cell').map(cell=>cell.textContent)).toEqual(['archive',t('agents.TaskExecution.inventory.directory'),'—','—'])
 expect(view.container.querySelector('.task-execution-inventory-scroll')?.getAttribute('tabindex')).toBe('0')
 expect(f.calls.some(call=>call.url.includes('filesystem'))).toBe(false);expect(f.state.accepts).toBe(0)
})
it('distinguishes a genuinely empty observed inventory from a missing result',async()=>{
 const f=inventoryFixture({...nativeInventory(),entries:[]});render(<TaskExecutionPanel taskText="List the empty folder"/>);await open()
 expect(await screen.findByText(t('agents.TaskExecution.inventory.empty'))).toBeTruthy()
 expect(screen.queryByRole('table')).toBeNull();expect(screen.queryByText(t('agents.TaskExecution.inventory.invalid'))).toBeNull();expect(f.state.accepts).toBe(0)
})
it.each(['AWAITING_ACCEPTANCE','PREPARING','FAILED_NO_EFFECT','STOPPED_BEFORE_EFFECT','DENIED','STALE'])('does not promote inventory in a nonexecuted %s record to a visible read result',async status=>{
 inventoryFixture(nativeInventory(),status);render(<TaskExecutionPanel taskText="List folder"/>);await open();await screen.findByText(t(`agents.TaskExecution.state.${status}`))
 expect(screen.queryByRole('table')).toBeNull();expect(screen.queryByText(t('agents.TaskExecution.inventory.empty'))).toBeNull()
})
it.each(['PREPARED','RUNNING','FAILED','STOPPED'])('does not expose an inventory whose durable step is %s',async status=>{
 inventoryFixture(nativeInventory(),'SUCCEEDED',status);render(<TaskExecutionPanel taskText="List folder"/>);await open();await screen.findByText(t('agents.TaskExecution.state.SUCCEEDED'))
 expect(screen.queryByRole('table')).toBeNull();expect(screen.queryByText(t('agents.TaskExecution.inventory.empty'))).toBeNull()
})
it('does not use a result embedded only in the proposed plan as observed evidence',async()=>{
 const f=inventoryFixture(),record=f.state.record as any
 Object.assign(record.plan.steps[0],record.step_results.s1);record.step_results={}
 render(<TaskExecutionPanel taskText="List folder"/>);await open();await screen.findByText(t('agents.TaskExecution.state.SUCCEEDED'))
 expect(screen.queryByRole('table')).toBeNull()
})
it.each([
 ['missing payload',undefined],['wrong collection',{...nativeInventory(),entries:{}}],['recursive',{...nativeInventory(),recursive:true}],
 ['file without snapshot',{...nativeInventory(),entries:[{path:'report.csv',kind:'file',snapshot:null}]}],
 ['directory with fabricated size',{...nativeInventory(),entries:[{path:'archive',kind:'directory',snapshot:{sha256:'e'.repeat(64),size:0,mtime_ns:0,inode:0}}]}],
 ['invalid hash',{...nativeInventory(),entries:[{path:'bad.csv',kind:'file',snapshot:{sha256:'not-a-hash',size:23,mtime_ns:0,inode:0}}]}],
 ['oversize file',{...nativeInventory(),entries:[{path:'large.csv',kind:'file',snapshot:{sha256:'e'.repeat(64),size:16*1024*1024+1,mtime_ns:0,inode:0}}]}],
 ['too many entries',{...nativeInventory(),entries:Array.from({length:1001},(_,i)=>({path:`dir-${i}`,kind:'directory',snapshot:null}))}],
 ['duplicate path',{...nativeInventory(),entries:[nativeInventory().entries[0],nativeInventory().entries[0]]}],
 ['path traversal',{...nativeInventory(),entries:[{path:'../private',kind:'directory',snapshot:null}]}],
 ['absolute path',{...nativeInventory(),entries:[{path:'C:/private',kind:'directory',snapshot:null}]}],
])('reports malformed inventory (%s) without rendering a successful result table',async(_name,value)=>{
 const f=inventoryFixture(value);if(value===undefined)delete(f.state.record as any).step_results.s1.receipt.inventory
 render(<TaskExecutionPanel taskText="List folder"/>);await open();expect(await screen.findByText(t('agents.TaskExecution.inventory.invalid'))).toBeTruthy()
 expect(screen.queryByRole('table')).toBeNull();expect(screen.queryByText(t('agents.TaskExecution.inventory.empty'))).toBeNull();expect(f.state.accepts).toBe(0)
})
it('requires a PASS receipt and renders untrusted long file names only as inert text',async()=>{
 const inventory=nativeInventory(),name='<img onerror=alert(1)>-'+ 'x'.repeat(300)+'.csv';inventory.entries[0].path=name
 const f=inventoryFixture(inventory),view=render(<TaskExecutionPanel taskText="List folder"/>);await open()
 const table=await screen.findByRole('table',{name:t('agents.TaskExecution.inventory.title')})
 expect(within(table).getByText(name)).toBeTruthy();expect(table.querySelectorAll('img,script,a,input,button')).toHaveLength(0)
 expect(view.container.querySelector('.task-execution-inventory-scroll')).toBeTruthy();expect(f.calls).toHaveLength(4)
 view.unmount();sessionStorage.clear();inventoryFixture(nativeInventory(),'SUCCEEDED','SUCCEEDED','FAIL')
 render(<TaskExecutionPanel taskText="List folder"/>);await open();await screen.findByText(t('agents.TaskExecution.inventory.invalid'));expect(screen.queryByRole('table')).toBeNull()
})
