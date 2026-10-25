// @vitest-environment jsdom
import React from 'react'
import {afterEach,beforeEach,expect,it,vi} from 'vitest'
import {act,cleanup,fireEvent,render,screen,waitFor,within} from '@testing-library/react'
import ChatInspection from '../../../src/components/ChatInspection'
import AgentBuilder from '../../../src/components/AgentBuilder'
import AgentTaskForm,{AgentPresentationError,agentStateLabel,presentAgentError,taskError} from '../../../src/components/AgentTaskForm'
import AgentManagement from '../../../src/components/AgentManagement'
import AgentEvaluationLab from '../../../src/components/AgentEvaluationLab'
import {InspectorStateView,EvidenceSupportStatus} from '../../../src/features/decision-inspector/shared/InspectorState'
import {InspectorShell} from '../../../src/features/decision-inspector/shell/InspectorShell'
import {ActionReview} from '../../../src/features/decision-inspector/actions/ActionReview'
import {TraceTimeline} from '../../../src/features/decision-inspector/trace/TraceTimeline'
import {BerEffectRecordInspector} from '../../../src/features/ber-effect-inspector/BerEffectRecordInspector'
import {es,en} from '../../../src/i18n/domains/agents'
import {setLocale,resetLocaleForTests,t} from '../../../src/i18n'
const tid='trace-496fac766f384348'
const trace={trace_id:tid,run_id:'run-current',event_count:1,cost_usd:0,evidence_refs:[],events:[{evidence_refs:[],kind:'authorization',event_id:'event-current',trace_id:tid,sequence:0,status:'DENY',name:'workspace.read',attributes:{redacted:true}}]}
const selected={trace_id:tid,execution_id:'run-current',message_id:'a1',state:'available',integrity:'legacy_unverified',sha256:'a'.repeat(64),limitations:['ORIGINAL LIMITATION'],trace}
const body=(id:string,s:any=null)=>({schema:'bago.chat.inspection.v1',conversation_id:id,revision:1,state:s?'selected':'no_artifacts',executions:s?[{trace_id:tid,message_id:'a1',execution_id:'run-current'}]:[],total:s?1:0,offset:0,next_offset:null,selected:s})
const response=(b:unknown,status=200)=>({ok:status<400,status,json:async()=>b})
beforeEach(()=>{localStorage.clear();resetLocaleForTests();setLocale('es');HTMLElement.prototype.scrollIntoView=()=>{}})
afterEach(()=>{cleanup();vi.unstubAllGlobals()})
it('has authored nonempty ES/EN catalogs with exactly matching keys and placeholders',()=>{
 expect(Object.keys(es).sort()).toEqual(Object.keys(en).sort())
 const parameters=(s:string)=>[...s.matchAll(/\{(\w+)\}/g)].map(x=>x[1]).sort()
 for(const key of Object.keys(es) as (keyof typeof es)[]){expect(es[key].trim(),key).not.toBe('');expect(en[key].trim(),key).not.toBe('');expect(parameters(es[key]),key).toEqual(parameters(en[key]))}
})
it('shows four zero counters without an execution combobox or demo fallback',async()=>{
 const fetch=vi.fn(async()=>response(body('empty')));vi.stubGlobal('fetch',fetch)
 render(<ChatInspection selection={{conversationId:'empty'}} onSelect={vi.fn()} />)
 await screen.findByRole('heading',{name:'Sin ejecución registrada'})
 const counters=screen.getAllByRole('definition')[0].parentElement!.parentElement!
 expect(counters.querySelectorAll('dd')).toHaveLength(4)
 expect([...counters.querySelectorAll('dd')].map(x=>x.textContent)).toEqual(['0','0','0','0'])
 expect(screen.queryByRole('combobox')).toBeNull();expect(screen.queryByText(/trazas asociadas|associated traces/)).toBeNull();expect(fetch).toHaveBeenCalledTimes(1)
 act(()=>setLocale('en'));expect(screen.getByRole('heading',{name:'No run recorded'})).toBeTruthy()
 expect(screen.queryByRole('combobox')).toBeNull();expect(screen.queryByText(/trazas asociadas|associated traces/)).toBeNull();expect(fetch).toHaveBeenCalledTimes(1)
})
it('uses only the backend-selected latest own run and keeps panes/locale from refetching',async()=>{
 const payload={...body('own',selected),total:2,executions:[{trace_id:tid,message_id:'a1',execution_id:'run-current'},{trace_id:'trace-0123456789abcdef',message_id:'a0',execution_id:'older-success'}]}
 const fetch=vi.fn(async()=>response(payload));vi.stubGlobal('fetch',fetch);const choose=vi.fn()
 const view=render(<ChatInspection view="trace" selection={{conversationId:'own'}} onSelect={choose}/>)
 await screen.findByText('event-current');expect((screen.getByRole('combobox') as HTMLSelectElement).value).toBe(tid)
 expect(screen.getByText('DENY')).toBeTruthy();expect(screen.queryByText('PASS')).toBeNull()
 act(()=>setLocale('en'));expect((screen.getByRole('combobox') as HTMLSelectElement).value).toBe(tid)
 expect(screen.getByText('ORIGINAL LIMITATION')).toBeTruthy()
 for(const pane of ['summary','authorization','evaluation','retrieval'] as const){view.rerender(<ChatInspection view={pane} selection={{conversationId:'own'}} onSelect={choose}/>)}
 expect(screen.getByText("No evidence references exist in this trace's events.")).toBeTruthy()
 expect(fetch).toHaveBeenCalledTimes(1);expect(choose).not.toHaveBeenCalled()
})
it.each(['conversation','run','trace','invalid-event'])('rejects foreign or malformed %s identity without falling back to older success',async(kind)=>{
 const p=structuredClone(body('own',selected))
 if(kind==='conversation')p.conversation_id='foreign'
 if(kind==='run')p.selected.execution_id='foreign-run'
 if(kind==='trace')p.selected.trace.trace_id='foreign-trace'
 if(kind==='invalid-event')p.selected.trace.events[0].name={} as any
 vi.stubGlobal('fetch',vi.fn(async()=>response(p)))
 render(<ChatInspection selection={{conversationId:'own'}} onSelect={vi.fn()}/>);
 await screen.findByRole('alert');expect(screen.queryByText('event-current')).toBeNull();expect(screen.queryByRole('table')).toBeNull()
 act(()=>setLocale('en'));expect(screen.getByRole('alert').textContent).toContain('does not match the selection')
})
it('ignores a late previous conversation and never requests data without selection',async()=>{
 let finish:(x:any)=>void=()=>{};const fetch=vi.fn((url:string)=>url.includes('/old/')?new Promise(resolve=>finish=resolve):Promise.resolve(response(body('new'))));vi.stubGlobal('fetch',fetch)
 const view=render(<ChatInspection selection={null} onSelect={vi.fn()}/>);expect(fetch).not.toHaveBeenCalled()
 view.rerender(<ChatInspection selection={{conversationId:'old'}} onSelect={vi.fn()}/>);
 view.rerender(<ChatInspection selection={{conversationId:'new'}} onSelect={vi.fn()}/>);
 await screen.findByRole('heading',{name:'Sin ejecución registrada'});await act(async()=>finish(response(body('old',selected))))
 expect(screen.queryByText('event-current')).toBeNull();expect(screen.queryByText('old')).toBeNull()
})
it('retains builder fields, task, instructions and tool selections without refetch on locale change',async()=>{
 const fetch=vi.fn(async(url:string)=>response(url==='/api/capabilities'
  ? {agent_tools:[{id:'sandbox.run',name:'Preparar BER',name_en:'Sandbox Execution',status:'AVAILABLE'}]}
  : url==='/api/agent-tools/templates' ? {templates:[]}
  : {models:[{provider_id:'ollama-cloud',label:'Ollama',state:'ready',model_id:'model-original'}]}));vi.stubGlobal('fetch',fetch)
 const {container}=render(<AgentBuilder initialAgent={{name:'ORIGINAL NAME',description:'ORIGINAL DESCRIPTION',type:'rag',system_prompt:'ORIGINAL INSTRUCTIONS',tools:['sandbox.run'],task:{prompt:'ORIGINAL TASK',dates:[]}}}/>);
 await screen.findByText('Ollama · acceso comprobado')
 const name=container.querySelector('input[type="text"]') as HTMLInputElement;fireEvent.change(name,{target:{value:'Edited name'}})
 const task=screen.getByLabelText('Tarea *') as HTMLTextAreaElement
 const callsBeforeLocale=fetch.mock.calls.length
 act(()=>setLocale('en'));expect(name.value).toBe('Edited name');expect(task.value).toBe('ORIGINAL TASK')
 expect((container.querySelectorAll('textarea')[2] as HTMLTextAreaElement).value).toBe('ORIGINAL INSTRUCTIONS')
 expect(screen.getByText('Sandbox Execution').parentElement!.querySelector('input')!.checked).toBe(true)
 expect(fetch).toHaveBeenCalledTimes(callsBeforeLocale);expect(screen.getByText('Agent Name *')).toBeTruthy()
})
it('keeps date payload fields and local validation unchanged while labels change',()=>{
 const update=vi.fn();render(<AgentTaskForm value={{prompt:'USER TEXT',dates:[{key:'fecha_1',label:'USER LABEL',value:'2026-10-23'}]}} onChange={update}/>);
 expect(screen.getByLabelText('Nombre de fecha 1')).toBeTruthy();act(()=>setLocale('en'))
 expect((screen.getByLabelText('Date name 1') as HTMLInputElement).value).toBe('USER LABEL');expect(update).not.toHaveBeenCalled()
 expect(taskError({prompt:'',dates:[]})).toBe('Enter a task of up to 8000 characters.')
 const e=new AgentPresentationError(()=>t('agents.AgentTasks.no_se_pudo_guardar'));expect(e.message).toBe('Save failed.');act(()=>setLocale('es'));expect(e.message).toBe('No se pudo guardar.')
})
it('keeps reviewed deletion and checked consent when changing locale without submitting it',async()=>{
 const profile={id:'agent-own',config:{name:'USER AGENT',description:'USER DESCRIPTION',tools:[],type:'rag'}}
 const fetch=vi.fn(async(url:string)=>response(url.endsWith('deletion-review')?{agent_id:'agent-own',name:'USER AGENT',revision:'a'.repeat(64),deletable:true,blockers:[],preserved:[]}: {agents:[profile]}));vi.stubGlobal('fetch',fetch)
 render(<AgentManagement onCreate={vi.fn()} onTest={vi.fn()} onEvaluate={vi.fn()}/>);
 fireEvent.click(await screen.findByRole('button',{name:'Eliminar perfil'}));const consent=await screen.findByRole('checkbox');fireEvent.click(consent)
 act(()=>setLocale('en'));expect((consent as HTMLInputElement).checked).toBe(true);expect(screen.getByRole('button',{name:'Confirm deletion'}).hasAttribute('disabled')).toBe(false)
 expect(fetch).toHaveBeenCalledTimes(2);expect(screen.getByRole('heading',{name:'Delete “USER AGENT”'})).toBeTruthy()
})
it('retains original backend detail while translating an already displayed error',async()=>{
 const fetch=vi.fn(async()=>response({detail:{code:'unknown_remote',message:'EXACT ORIGINAL DIAGNOSTIC'}},503));vi.stubGlobal('fetch',fetch)
 render(<ChatInspection selection={{conversationId:'own'}} onSelect={vi.fn()}/>);
 await screen.findByRole('alert');const before=screen.getByRole('alert').textContent
 act(()=>setLocale('en'));expect(screen.getByRole('alert').textContent).not.toBe(before);expect(screen.getByRole('alert').textContent).toContain('EXACT ORIGINAL DIAGNOSTIC');expect(fetch).toHaveBeenCalledTimes(1)
})
it('preserves evaluation unavailable detection before diagnostic localization and translates retained errors',async()=>{
 const fetch=vi.fn(async()=>response({detail:'service unavailable'},503));vi.stubGlobal('fetch',fetch)
 render(<AgentEvaluationLab/>);await screen.findByText('Servicio de evaluación no disponible')
 act(()=>setLocale('en'));expect(screen.getByText('Evaluation service unavailable')).toBeTruthy();expect(screen.getByRole('alert').textContent).toContain('service unavailable');expect(fetch).toHaveBeenCalledTimes(5)
})
it.each(['loading','empty','unsupported','partial','stale','unverified','unknown'] as const)('updates shared %s state headings without remount',status=>{
 const view=render(<InspectorStateView state={{status} as any}/>);const section=view.container.querySelector('section')
 const before=screen.getByRole('heading').textContent;act(()=>setLocale('en'));expect(screen.getByRole('heading').textContent).not.toBe(before);expect(view.container.querySelector('section')).toBe(section)
})
it('translates empty inspector descendants and keeps unknown states explicit',()=>{
 const view=render(<><InspectorShell conclusions={[]}/><ActionReview/><TraceTimeline/><EvidenceSupportStatus status="missing"/><BerEffectRecordInspector/></>)
 expect(screen.getByText('La evidencia referenciada no está disponible')).toBeTruthy();act(()=>setLocale('en'))
 expect(screen.getByText('Referenced evidence is unavailable')).toBeTruthy();expect(screen.getByText('Trace timeline')).toBeTruthy();expect(screen.getByText('Choose BER effect JSON')).toBeTruthy();expect(agentStateLabel('future_code')).toBe('Unknown state (future_code)');expect(agentStateLabel('__proto__')).toBe('Unknown state (__proto__)')
})



it('keeps free-form original limitations only in technical details beside the localized scope warning',async()=>{
 const original='No governed decision/evaluation/authorization bundle was produced by this chat trace.'
 const payload=body('own',{...selected,limitations:[original]});const fetch=vi.fn(async()=>response(payload));vi.stubGlobal('fetch',fetch)
 render(<ChatInspection view="authorization" selection={{conversationId:'own'}} onSelect={vi.fn()}/>);
 const diagnostic=await screen.findByText(original);const details=diagnostic.closest('details')
 expect(details).not.toBeNull();expect(details!.open).toBe(false);expect(within(details!).getByText('Datos técnicos originales')).toBeTruthy()
 const warning=screen.getByText('Esta traza no aporta una autorización gobernada. Un estado ALLOW de una herramienta no sustituye la confirmación de una acción.')
 expect(warning.closest('details')).toBeNull();expect(diagnostic.textContent).toBe(original)
 act(()=>setLocale('en'));expect(within(details!).getByText('Original technical data')).toBeTruthy();expect(diagnostic.textContent).toBe(original);expect(fetch).toHaveBeenCalledTimes(1)
})
