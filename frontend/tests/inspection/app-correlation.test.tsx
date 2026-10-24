// @vitest-environment jsdom
import React from 'react'
import {afterEach,beforeEach,expect,it,vi} from 'vitest'
import {act,cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import axios from 'axios'
vi.mock('axios',()=>({default:{get:vi.fn(()=>new Promise(()=>{}))}}))
vi.mock('../../src/components/JobHistory',()=>({default:()=> <p>Global job fixture</p>}))
vi.mock('../../src/features/ber-effect-inspector/BerEffectRecordInspector',()=>({BerEffectRecordInspector:()=> <p>Global BER fixture</p>}))
vi.mock('../../src/components/AgentChat',()=>({default:({onInspectExecution}:any)=><button onClick={()=>onInspectExecution({conversationId:'conv-current',traceId:'trace-496fac766f384348'})}>Inspect current fixture</button>}))
import App from '../../src/App'
import {resetLocaleForTests,setLocale} from '../../src/i18n'
beforeEach(()=>{localStorage.clear();resetLocaleForTests()})
afterEach(()=>{cleanup();vi.unstubAllGlobals();vi.clearAllMocks();vi.restoreAllMocks()})
it('App wires Chat identity to Inspect and never fetches global artifacts until explicit historical demo choice',async()=>{
 HTMLDialogElement.prototype.showModal=function(){this.open=true};HTMLDialogElement.prototype.close=function(){this.open=false}
 const fetch=vi.fn(async()=>({ok:true,status:200,json:async()=>({schema:'bago.chat.inspection.v1',conversation_id:'conv-current',revision:1,state:'no_artifacts',executions:[],total:0,offset:0,next_offset:null,selected:null})}));vi.stubGlobal('fetch',fetch)
 render(<App />);expect(axios.get).not.toHaveBeenCalled()
 fireEvent.click(screen.getByText('Inspect current fixture'))
 expect(await screen.findByText(/Esta conversación no tiene artefactos/)).toBeTruthy()
 const request=fetch.mock.calls.find(call=>String(call[0]).includes('/inspection'))!
 expect(request[0]).toContain('conv-current/inspection')
 expect(request[0]).toContain('trace_id=trace-496fac766f384348')
 expect(axios.get).not.toHaveBeenCalled()
 const source=screen.getByRole('group',{name:'Fuente de inspección'})
 const current=within(source).getByRole('button',{name:'Conversación actual'}),demo=within(source).getByRole('button',{name:'Demostración histórica · independiente del chat'})
 expect(current.getAttribute('aria-pressed')).toBe('true');expect(demo.getAttribute('aria-pressed')).toBe('false')
 demo.focus();expect(document.activeElement).toBe(demo);fireEvent.click(demo)
 expect(demo.getAttribute('aria-pressed')).toBe('true');expect(current.getAttribute('aria-pressed')).toBe('false')
 expect(axios.get).toHaveBeenCalledExactlyOnceWith('/api/artifacts')
})

it.each(['Historial de trabajos','Registro de efectos BER'])('labels %s as global and removes the conversation selector', async label=>{
 HTMLDialogElement.prototype.showModal=function(){this.open=true};HTMLDialogElement.prototype.close=function(){this.open=false}
 vi.stubGlobal('fetch',vi.fn(async()=>({ok:true,status:200,json:async()=>({schema:'bago.chat.inspection.v1',conversation_id:'conv-current',revision:1,state:'no_artifacts',executions:[],total:0,offset:0,next_offset:null,selected:null})})))
 render(<App />)
 fireEvent.click(screen.getByText('Inspect current fixture'))
 await screen.findByText(/Esta conversación no tiene artefactos/)
 fireEvent.click(screen.getByRole('button',{name:label}))
 expect(screen.getByText('Vista global independiente; no vinculada a la conversación seleccionada.')).toBeTruthy()
 expect(screen.queryByRole('button',{name:'Conversación actual'})).toBeNull()
 expect(screen.queryByRole('button',{name:'Demostración histórica · independiente del chat'})).toBeNull()
 expect(axios.get).not.toHaveBeenCalled()
})

class DemoErrorBoundary extends React.Component<{children:React.ReactNode},{error:Error|null}> {
 state={error:null as Error|null}
 static getDerivedStateFromError(error:Error){return {error}}
 render(){return this.state.error?<p role="alert">{this.state.error.message}</p>:this.props.children}
}
it('renders an original demo API diagnostic as localized text without passing an Error object to React',async()=>{
 HTMLDialogElement.prototype.showModal=function(){this.open=true};HTMLDialogElement.prototype.close=function(){this.open=false}
 vi.spyOn(console,'error').mockImplementation(()=>{})
 vi.mocked(axios.get).mockRejectedValueOnce({response:{status:503,data:{detail:{code:'unknown_demo_failure',message:'ORIGINAL_DEMO_FAILURE'}}}})
 vi.stubGlobal('fetch',vi.fn(async()=>({ok:true,status:200,json:async()=>({schema:'bago.chat.inspection.v1',conversation_id:'conv-current',revision:1,state:'no_artifacts',executions:[],total:0,offset:0,next_offset:null,selected:null})})))
 render(<DemoErrorBoundary><App/></DemoErrorBoundary>)
 fireEvent.click(screen.getByText('Inspect current fixture'))
 await screen.findByText(/Esta conversación no tiene artefactos/)
 expect(axios.get).not.toHaveBeenCalled()
 fireEvent.click(screen.getByRole('button',{name:'Demostración histórica · independiente del chat'}))
 expect(await screen.findByText(/ORIGINAL_DEMO_FAILURE/)).toBeTruthy()
 expect(screen.queryByText(/Objects are not valid as a React child/)).toBeNull()
 expect(screen.getByText(/No se pudo completar la solicitud/)).toBeTruthy()
 act(()=>setLocale('en'))
 expect(screen.getByText(/The request could not be completed/)).toBeTruthy()
 expect(screen.getByText(/Original technical detail: ORIGINAL_DEMO_FAILURE/)).toBeTruthy()
 expect(axios.get).toHaveBeenCalledExactlyOnceWith('/api/artifacts')
 vi.restoreAllMocks()
})

it('keeps a null historical bundle explicit and localized without a raw fallback or demo fetch on open',async()=>{
 HTMLDialogElement.prototype.showModal=function(){this.open=true};HTMLDialogElement.prototype.close=function(){this.open=false}
 vi.mocked(axios.get).mockResolvedValueOnce({data:null})
 vi.stubGlobal('fetch',vi.fn(async()=>({ok:true,status:200,json:async()=>({schema:'bago.chat.inspection.v1',conversation_id:'conv-current',revision:1,state:'no_artifacts',executions:[],total:0,offset:0,next_offset:null,selected:null})})))
 render(<App/>);fireEvent.click(screen.getByText('Inspect current fixture'));await screen.findByText(/Esta conversación no tiene artefactos/)
 expect(axios.get).not.toHaveBeenCalled();fireEvent.click(screen.getByRole('button',{name:'Demostración histórica · independiente del chat'}))
 await screen.findByRole('heading',{name:'Todavía no hay artefactos disponibles'})
 expect(screen.queryByText('No artifact bundle was returned.')).toBeNull()
 act(()=>setLocale('en'));expect(screen.getByRole('heading',{name:'Artifacts are not available yet'})).toBeTruthy()
 expect(axios.get).toHaveBeenCalledExactlyOnceWith('/api/artifacts')
})
