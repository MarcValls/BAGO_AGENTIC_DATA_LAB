// @vitest-environment jsdom
import React from 'react'
import {afterEach, beforeEach, expect, it, vi} from 'vitest'
import {cleanup, fireEvent, render, screen, waitFor, within} from '@testing-library/react'
import axios from 'axios'
import {resetLocaleForTests, t} from '../../src/i18n'
import {runtimeStatusFixture} from '../runtime-status-bar/fixture'
vi.mock('axios', () => ({default:{get:vi.fn(() => new Promise(() => {}))}}))
vi.mock('../../src/components/AgentChat', () => ({default:({onInspectExecution}:any) => <><input aria-label="Borrador conservado" defaultValue="BORRADOR ORIGINAL"/><button onClick={() => onInspectExecution({conversationId:'conv-owned',revision:2})}>Abrir ejecución fixture</button></>}))
vi.mock('../../src/components/CognitionSettings', () => ({default:() => <p>Context fixture</p>, readCognitiveMode:() => 'baseline'}))
import App from '../../src/App'
const traceId='trace-496fac766f384348'
const selected=() => ({trace_id:traceId,execution_id:'run-owned',message_id:'msg-owned',state:'available',integrity:'hash_verified',sha256:'c'.repeat(64),limitations:['NO EVALUATION'],trace:{trace_id:traceId,run_id:'run-owned',event_count:1,cost_usd:0,evidence_refs:['ref-owned'],events:[{event_id:'event-owned',trace_id:traceId,sequence:0,name:'workspace.read',kind:'authorization',status:'DENY',parent_event_id:null,attributes:{redacted:true},evidence_refs:['ref-owned']}]}})
const body=(choice:any=selected()) => ({schema:'bago.chat.inspection.v1',conversation_id:'conv-owned',revision:2,state:choice?'selected':'no_artifacts',total:choice?1:0,offset:0,next_offset:null,executions:choice?[{trace_id:traceId,execution_id:'run-owned',message_id:'msg-owned'}]:[],selected:choice})
beforeEach(() => {
 localStorage.clear();resetLocaleForTests()
 HTMLDialogElement.prototype.showModal=function(){this.open=true}
 HTMLDialogElement.prototype.close=function(){this.open=false;this.dispatchEvent(new Event('close'))}
})
afterEach(() => {cleanup();vi.unstubAllGlobals();vi.restoreAllMocks();vi.clearAllMocks()})
async function open(data=body()) {
 const fetcher=vi.fn(async(url:string,_init?:RequestInit)=>({ok:true,status:200,json:async()=>url==='/api/runtime/status'?runtimeStatusFixture():data}));vi.stubGlobal('fetch',fetcher)
 render(<App/>);const trigger=screen.getByText('Abrir ejecución fixture');trigger.focus();fireEvent.click(trigger)
 const dialog=document.getElementById('data-layer') as HTMLDialogElement
 await waitFor(()=>expect(dialog.querySelector('.chat-inspection-execution-select')).not.toBeNull())
 await waitFor(()=>expect(dialog.querySelector('[role="status"]')?.textContent??'').not.toContain('Cargando inspección'))
 expect(fetcher.mock.calls.filter(([url])=>url==='/api/runtime/status')).toHaveLength(1)
 expect(fetcher.mock.calls.filter(([url])=>url!=='/api/runtime/status').map(([url])=>url)).toEqual(['/api/conversations/conv-owned/inspection?offset=0&limit=20'])
 expect(fetcher.mock.calls.every(([,init])=>(init?.method??'GET')==='GET'&&init?.body===undefined)).toBe(true)
 return {dialog,trigger,fetcher}
}
it('real App embedded owns one title/context and moves metrics/events to their sections without refetch',async()=>{
 const writeText=vi.fn(async()=>{});vi.stubGlobal('navigator',{clipboard:{writeText}})
 const {dialog,fetcher,trigger}=await open(),d=within(dialog)
 expect(d.getAllByRole('heading',{name:t('core.App.decision_inspector_2bc4a6')})).toHaveLength(1)
 expect(d.queryByRole('table')).toBeNull();expect(dialog.querySelector('.chat-inspection-counters')).toBeNull()
 const details=dialog.querySelector('.chat-inspection-common') as HTMLDetailsElement
 expect(details.open).toBe(false);expect(d.getByRole('group',{name:t('agents.hierarchy.conversationIdentity')}).closest('details')).toBe(details)
 fireEvent.click(within(details).getByText(t('agents.aux.context.technical')));details.open=true
 const identity=d.getByRole('group',{name:t('agents.hierarchy.conversationIdentity')})
 expect(within(identity).getAllByText('conv-owned')).toHaveLength(1);expect(within(identity).getAllByText('run-owned')).toHaveLength(1)
 fireEvent.click(within(identity).getByRole('button',{name:t('agents.hierarchy.copyConversationId')}))
 await waitFor(()=>expect(writeText).toHaveBeenCalledExactlyOnceWith('conv-owned'))
 const nav=d.getByRole('navigation',{name:t('core.App.data_views_bd550f')})
 fireEvent.click(within(nav).getByRole('button',{name:t('core.App.summary_8e76a9')}))
 expect(dialog.querySelectorAll('.chat-inspection-counters dd')).toHaveLength(4);expect(d.queryByRole('table')).toBeNull()
 fireEvent.click(within(nav).getByRole('button',{name:t('core.App.trace_7e14c3')}))
 expect(d.getAllByRole('table')).toHaveLength(1);expect(dialog.querySelector('.chat-inspection-counters')).toBeNull()
 for(const key of ['core.App.retrieval_ontology_608937','core.App.authorization_ca5839','core.App.evaluation_163e44'])fireEvent.click(within(nav).getByRole('button',{name:t(key)}))
 expect(d.queryByText('PASS')).toBeNull();expect(fetcher.mock.calls.filter(([url])=>url!=='/api/runtime/status')).toHaveLength(1);expect(fetcher).toHaveBeenCalledTimes(2);expect(axios.get).not.toHaveBeenCalled()
 fireEvent.click(d.getByRole('button',{name:t('core.App.exit_inspector')}))
 expect(document.activeElement).toBe(trigger);expect((screen.getByLabelText('Borrador conservado') as HTMLInputElement).value).toBe('BORRADOR ORIGINAL')
})
it('keeps overview links as view navigation without effects or new fetches',async()=>{
 const {dialog,fetcher}=await open()
 fireEvent.click(within(dialog).getByRole('button',{name:t('agents.ChatInspection.traza_de_la_ejecucion')}))
 expect(within(dialog).getByRole('table')).toBeTruthy();expect(fetcher.mock.calls.filter(([url])=>url!=='/api/runtime/status')).toHaveLength(1);expect(fetcher).toHaveBeenCalledTimes(2)
})
it('keeps invalid trace rejection visible outside the closed context and never displays fabricated success',async()=>{
 const {dialog}=await open(body({...selected(),state:'invalid',trace:null,integrity:'not_available',sha256:null,reason:'HASH_MISMATCH'}))
 expect(within(dialog).getByRole('alert')).toBeTruthy();expect(within(dialog).queryByText('PASS')).toBeNull();expect(within(dialog).queryByRole('table')).toBeNull()
 expect((dialog.querySelector('.chat-inspection-common') as HTMLDetailsElement).open).toBe(false)
 expect(within(dialog).getByText('HASH_MISMATCH').closest('details')).toBeTruthy()
})
it('keeps no-artifacts explicit and never borrows the demonstration bundle',async()=>{
 vi.stubGlobal('fetch',vi.fn(async()=>({ok:true,status:200,json:async()=>body(null)})))
 render(<App/>);fireEvent.click(screen.getByText('Abrir ejecución fixture'))
 expect(await screen.findByText(/Esta conversación no tiene artefactos/)).toBeTruthy();expect(axios.get).not.toHaveBeenCalled();expect(screen.queryByRole('table')).toBeNull()
})
it('real App demonstration keeps its own bundle and one host title without duplicating answer or run ID',async()=>{
 const demo={summary:{status:'PASS'},agent_run:{run_id:'run-demo-owned',status:'COMPLETED',query:'DEMO QUESTION',answer:'DEMO ORIGINAL ANSWER',retrieval:{hits:[]},proposals:[],decision_receipts:[],mcp_receipts:[]},receipts:{},trace:{trace_id:'trace-demo',run_id:'run-demo-owned',events:[]},evaluation:{}}
 vi.mocked(axios.get).mockResolvedValueOnce({data:demo})
 const {dialog,fetcher}=await open()
 fireEvent.click(within(dialog).getByRole('button',{name:t('core.App.historical_demonstration_independent_of_chat_3b2e02')}))
 await within(dialog).findByText('DEMO ORIGINAL ANSWER')
 expect(within(dialog).getAllByText('DEMO ORIGINAL ANSWER')).toHaveLength(1)
 expect(within(dialog).getAllByText('run-demo-owned')).toHaveLength(1)
 expect(dialog.querySelectorAll('h1')).toHaveLength(0)
 expect(within(dialog).getAllByRole('heading',{name:t('core.App.decision_inspector_2bc4a6')})).toHaveLength(1)
 expect(axios.get).toHaveBeenCalledExactlyOnceWith('/api/artifacts');expect(fetcher.mock.calls.filter(([url])=>url!=='/api/runtime/status')).toHaveLength(1);expect(fetcher).toHaveBeenCalledTimes(2)
})
it('selection and paging still request the selected conversation and trace rather than stale context',async()=>{
 const secondId='trace-2222222222222222'
 const fetcher=vi.fn(async(url:string)=>{
  const page=url.includes('offset=20'),second=url.includes(secondId),choice=selected()
  if(second){choice.trace_id=secondId;choice.trace.trace_id=secondId;choice.trace.events[0].trace_id=secondId}
  const data={...body(choice),total:25,offset:page?20:0,next_offset:page?null:20,executions:[{trace_id:traceId,execution_id:'run-owned',message_id:'msg-owned'},{trace_id:secondId,execution_id:'run-owned',message_id:'msg-owned'}]}
  return {ok:true,status:200,json:async()=>data}
 });vi.stubGlobal('fetch',fetcher)
 render(<App/>);fireEvent.click(screen.getByText('Abrir ejecución fixture'))
 fireEvent.click(await screen.findByRole('button',{name:t('agents.ChatInspection.mas_ejecuciones')}))
 await waitFor(()=>expect(fetcher.mock.calls.some(c=>c[0].includes('offset=20'))).toBe(true))
 const selector=await screen.findByRole('combobox')
 fireEvent.change(selector,{target:{value:secondId}})
 await waitFor(()=>expect(fetcher.mock.calls.some(c=>c[0].includes('conv-owned/inspection')&&c[0].includes('trace_id='+secondId))).toBe(true))
 await waitFor(()=>expect((screen.getByRole('combobox') as HTMLSelectElement).value).toBe(secondId))
})

