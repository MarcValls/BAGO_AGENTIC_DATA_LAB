import {setLocale,t} from '../../src/i18n'
import {beforeEach as beforeLocaleExpectation} from 'vitest'
beforeLocaleExpectation(() => setLocale('es'))
// @vitest-environment jsdom
import React from 'react'
import {afterEach,expect,it,vi} from 'vitest'
import {act,cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import ChatInspection from '../../src/components/ChatInspection'
import AgentChat from '../../src/components/AgentChat'
const tid='trace-496fac766f384348'
const body=(id:string,selected:any=null)=>({schema:'bago.chat.inspection.v1',conversation_id:id,revision:1,state:selected?'selected':'no_artifacts',executions:selected?[{trace_id:tid,message_id:'a1',execution_id:'run-current'}]:[],total:selected?1:0,offset:0,next_offset:null,selected})
const selected={trace_id:tid,execution_id:'run-current',message_id:'a1',state:'available',integrity:'legacy_unverified',sha256:'a'.repeat(64),limitations:['No evaluation bundle'],trace:{trace_id:tid,run_id:'run-current',event_count:1,cost_usd:0,evidence_refs:[],events:[{evidence_refs:[],kind:'authorization',event_id:'e-current',trace_id:tid,sequence:0,status:'DENY',name:'workspace.read',attributes:{redacted:true}}]}}
const response=(b:unknown,status=200)=>({ok:status<400,status,json:async()=>b})
afterEach(()=>{cleanup();vi.unstubAllGlobals()})
it('switches conversation inspection panes without refetching or inventing authorization/evaluation',async()=>{
 const fetch=vi.fn(async()=>response(body('conv-current',selected)));vi.stubGlobal('fetch',fetch)
 const view=render(<ChatInspection view="trace" selection={{conversationId:'conv-current'}} onSelect={()=>{}} />)
 await screen.findByText('e-current')
 view.rerender(<ChatInspection view="summary" selection={{conversationId:'conv-current'}} onSelect={()=>{}} />)
 expect(screen.getByRole('heading',{name:t('agents.ChatInspection.resumen_de_la_ejecucion')})).toBeTruthy()
 expect(screen.getByText(t('agents.ChatInspection.eventos_registrados'))).toBeTruthy();expect(screen.queryByRole('table')).toBeNull()
 view.rerender(<ChatInspection view="authorization" selection={{conversationId:'conv-current'}} onSelect={()=>{}} />)
 expect(screen.getByRole('heading',{name:t('agents.ChatInspection.sin_paquete_de_autorizacion')})).toBeTruthy();expect(screen.queryByText('DENY')).toBeNull()
 view.rerender(<ChatInspection view="evaluation" selection={{conversationId:'conv-current'}} onSelect={()=>{}} />)
 expect(screen.getByRole('heading',{name:t('agents.ChatInspection.sin_evaluacion_registrada')})).toBeTruthy();expect(screen.queryByText('PASS')).toBeNull()
 view.rerender(<ChatInspection view="retrieval" selection={{conversationId:'conv-current'}} onSelect={()=>{}} />)
 expect(screen.getByText(t('agents.ChatInspection.no_hay_referencias_de_evidencia_en_los_eventos_de_esta_traza'))).toBeTruthy()
 expect(fetch).toHaveBeenCalledTimes(1)
})
it('no selection and no artifacts stay honest without fetching demo',async()=>{
 const fetch=vi.fn(async()=>response(body('conv-new')));vi.stubGlobal('fetch',fetch)
 const view=render(<ChatInspection selection={null} onSelect={()=>{}} />);expect(fetch).not.toHaveBeenCalled()
 view.rerender(<ChatInspection selection={{conversationId:'conv-new'}} onSelect={()=>{}} />)
 expect(await screen.findByText(/Esta conversación no tiene artefactos/)).toBeTruthy()
 expect(fetch.mock.calls[0][0]).toContain('/api/conversations/conv-new/inspection')
 expect(screen.queryByText(/Bruma/)).toBeNull()
})
it('renders only selected trace failure/redaction without creating evaluation PASS',async()=>{
 vi.stubGlobal('fetch',vi.fn(async()=>response(body('conv-current',selected))))
 render(<ChatInspection selection={{conversationId:'conv-current',traceId:tid}} onSelect={()=>{}} />)
 expect(await screen.findByText('e-current')).toBeTruthy();expect(screen.getByText('DENY')).toBeTruthy();expect(screen.getByText('legacy_unverified')).toBeTruthy();expect(screen.queryByText('PASS')).toBeNull()
 expect(screen.getByText(/No equivalen a una evaluación PASS/)).toBeTruthy()
})
it('rejects response belonging to another conversation and mismatch run',async()=>{
 vi.stubGlobal('fetch',vi.fn(async()=>response(body('foreign',selected))))
 render(<ChatInspection selection={{conversationId:'conv-current'}} onSelect={()=>{}} />)
 expect(await screen.findByRole('alert')).toBeTruthy();expect(screen.queryByText('e-current')).toBeNull()
})
it('clears old trace immediately and ignores late responses after switching conversation',async()=>{
 let finishOld:(value:any)=>void=()=>{}
 vi.stubGlobal('fetch',vi.fn((url:string)=>url.includes('conv-old')?new Promise(resolve=>{finishOld=resolve}):Promise.resolve(response(body('conv-new')))))
 const view=render(<ChatInspection selection={{conversationId:'conv-old'}} onSelect={()=>{}} />)
 view.rerender(<ChatInspection selection={{conversationId:'conv-new'}} onSelect={()=>{}} />)
 await screen.findByText(/Esta conversación no tiene artefactos/)
 await act(async()=>{finishOld(response(body('conv-old',selected)))})
 expect(screen.queryByText('e-current')).toBeNull();expect(screen.queryByText('conv-old')).toBeNull()
})
it('renders unavailable/invalid states and explicit paged execution selection',async()=>{
 const choose=vi.fn();let calls=0
 vi.stubGlobal('fetch',vi.fn(async()=>{calls++;return response({...body('c'),state:'selection_required',total:21,next_offset:calls===1?20:null,offset:calls===1?0:20,executions:[{trace_id:tid,message_id:'a',execution_id:'run-current'}]})}))
 render(<ChatInspection selection={{conversationId:'c'}} onSelect={choose} />)
 fireEvent.click(await screen.findByText(t('agents.ChatInspection.mas_ejecuciones')))
 await screen.findByText('21 trazas asociadas; página desde 21.')
 fireEvent.change(screen.getByLabelText(t('agents.ChatInspection.ejecucion_de_esta_conversacion')),{target:{value:tid}})
 expect(choose).toHaveBeenCalledWith({conversationId:'c',traceId:tid,executionId:undefined})
})
it('real AgentChat emits current conversation and per-message inspect identity',async()=>{
 HTMLElement.prototype.scrollIntoView=()=>{}
 const conv={id:'conv-replay',owner_kind:'assistant',owner_id:'app-assistant',title:'Replay fixture',status:'active',revision:2,updated_at:'2026-10-23',messages:[{id:'a',role:'assistant',content:'REPLAY',references:{trace:{trace_id:tid,trace_state:'local_only'}}}]}
 vi.stubGlobal('fetch',vi.fn(async(url:string)=>{
  if(url.startsWith('/api/conversations?'))return response({conversations:[conv]})
  if(url==='/api/conversations/conv-replay')return response(conv)
  if(url==='/api/agents/list')return response({agents:[]})
  return response({models:[]})
 }))
 const selection=vi.fn(),inspect=vi.fn();render(<AgentChat cognitiveMode="baseline" onNavigate={()=>{}} onInspectionSelection={selection} onInspectExecution={inspect} onOpenProviderSettings={()=>{}} onOpenCognitionSettings={()=>{}} />)
 fireEvent.click(await screen.findByRole('button',{name:'Inspeccionar ejecución'}))
 expect(selection).toHaveBeenCalledWith({conversationId:'conv-replay',revision:2})
 expect(inspect).toHaveBeenCalledWith({conversationId:'conv-replay',revision:2,traceId:tid})
})
it('AgentChat ignores a late previously selected conversation response',async()=>{
 HTMLElement.prototype.scrollIntoView=()=>{}
 const make=(id:string)=>({id,owner_kind:'assistant',owner_id:'app-assistant',title:id,status:'active',revision:1,updated_at:'2026-10-23',messages:[{id:'msg-'+id,role:'assistant',content:'Content '+id,references:{trace:{trace_id:tid,trace_state:'local_only'}}}]})
 const a=make('conv-A'),b=make('conv-B');let initial=true,finishA:(value:any)=>void=()=>{}
 vi.stubGlobal('fetch',vi.fn(async(url:string)=>{
  if(url.startsWith('/api/conversations?'))return response({conversations:[a,b]})
  if(url==='/api/conversations/conv-A'){if(initial){initial=false;return response(a)};return new Promise(resolve=>{finishA=resolve})}
  if(url==='/api/conversations/conv-B')return response(b)
  if(url==='/api/agents/list')return response({agents:[]})
  return response({models:[]})
 }))
 const select=vi.fn();render(<AgentChat cognitiveMode="baseline" onNavigate={()=>{}} onInspectionSelection={select} onOpenProviderSettings={()=>{}} onOpenCognitionSettings={()=>{}} />)
 await screen.findByText('Content conv-A')
 fireEvent.click(screen.getByRole('button',{name:/conv-A/}));fireEvent.click(screen.getByRole('button',{name:/conv-B/}))
 await screen.findByText('Content conv-B')
 await act(async()=>{finishA(response(a))})
 expect(screen.queryByText('Content conv-A')).toBeNull()
 expect(select).toHaveBeenLastCalledWith({conversationId:'conv-B',revision:1})
})
it.each(['name','kind'] as const)('rejects malformed event %s fields before React can render them',async(field)=>{
 for(const bad of [{},null,[],undefined]){
  const malformed=structuredClone(selected) as any
  if(bad===undefined)delete malformed.trace.events[0][field]
  else malformed.trace.events[0][field]=bad
  vi.stubGlobal('fetch',vi.fn(async()=>response(body('conv-current',malformed))))
  const view=render(<ChatInspection selection={{conversationId:'conv-current'}} onSelect={()=>{}} />)
  expect(await screen.findByRole('alert')).toBeTruthy();expect(screen.queryByText('e-current')).toBeNull();view.unmount()
 }
})
it.each([
 ['executions',null],['executions',[null]],['executions',[{trace_id:tid,message_id:{},execution_id:null}]],
 ['revision',{}],['total',null],['next_offset',[]],['state',{}],
] as const)('rejects malformed envelope %s',async(field,bad)=>{
 const malformed={...body('conv-current',selected),[field]:bad}
 vi.stubGlobal('fetch',vi.fn(async()=>response(malformed)))
 render(<ChatInspection selection={{conversationId:'conv-current'}} onSelect={()=>{}} />)
 expect(await screen.findByRole('alert')).toBeTruthy();expect(screen.queryByText('e-current')).toBeNull()
})
it.each([
 ['limitations',null],['limitations',[{}]],['sha256',{}],['message_id',[]],['integrity',{}],['state',null],['execution_id',{}],
] as const)('rejects malformed selection metadata %s',async(field,bad)=>{
 vi.stubGlobal('fetch',vi.fn(async()=>response(body('conv-current',{...selected,[field]:bad}))))
 render(<ChatInspection selection={{conversationId:'conv-current'}} onSelect={()=>{}} />)
 expect(await screen.findByRole('alert')).toBeTruthy();expect(screen.queryByText('e-current')).toBeNull()
})
it.each([
 ['events',null],['events',[null]],['event_count',true],['cost_usd',{}],['evidence_refs',[{}]],
] as const)('rejects malformed trace metadata %s',async(field,bad)=>{
 const malformed=structuredClone(selected) as any;malformed.trace[field]=bad
 vi.stubGlobal('fetch',vi.fn(async()=>response(body('conv-current',malformed))))
 render(<ChatInspection selection={{conversationId:'conv-current'}} onSelect={()=>{}} />)
 expect(await screen.findByRole('alert')).toBeTruthy();expect(screen.queryByText('e-current')).toBeNull()
})
