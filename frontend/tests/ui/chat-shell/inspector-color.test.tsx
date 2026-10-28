// @vitest-environment jsdom
import {afterEach,expect,it,vi} from 'vitest'
import React from 'react'
import {fireEvent,render,screen} from '@testing-library/react'
import {readFileSync} from 'node:fs'
import {join} from 'node:path'
import {createHash} from 'node:crypto'
import postcss from 'postcss'
import ChatInspection from '../../../src/components/ChatInspection'
afterEach(()=>document.head.querySelector('[data-inspector-production-styles]')?.remove())
const paths=['src/components/AgentChat.css','src/App.css','src/components/ChatInspection.css']
const fixtureRoot='tests/ui/chat-shell/fixtures/inspector-color'
const provenance=JSON.parse(readFileSync(join(fixtureRoot,'PROVENANCE.json'),'utf8')) as {files:Array<{fixture:string;sha256:string;bytes:number}>}
function assertNoGeneratedContent(value:string){postcss.parse(value).walkDecls(d=>expect(d.prop.toLowerCase()).not.toBe('content'))}
const allowed=new Set(['color','background','background-image','border-color','border-top-color','border-bottom-color','border-left-color','border-right-color','border-radius','box-shadow','outline-color'])
for(const path of paths)it(`preserves prior CSS bytes and limits rectangular color decoration to its owning surface: ${path}`,()=>{
 const css=readFileSync(path,'utf8'),name=path.slice(path.lastIndexOf('/')+1),baseline=readFileSync(join(fixtureRoot,name)),before=baseline.toString('utf8')
 const receipt=provenance.files.find(file=>file.fixture===name)!
 expect(baseline.length).toBe(receipt.bytes);expect(createHash('sha256').update(baseline).digest('hex')).toBe(receipt.sha256)
 expect(css.startsWith(before)).toBe(true)
 const delta=css.slice(before.length).split('/* PANEL_NARROW_REPAIR:')[0].split('/* INSPECTOR_LAYOUT_R2:')[0],ast=postcss.parse(delta)
 expect(delta).toContain('linear-gradient(')
 let count=0
 ast.walkDecls(d=>{expect(allowed.has(d.prop),d.prop).toBe(true);if(d.prop==='border-radius')expect(d.value).toBe('0');count++})
 expect(count).toBeGreaterThan(5)
 ast.walkRules(rule=>{for(const selector of rule.selectors){expect(selector.startsWith(path.includes('AgentChat')?'.control-chat .chat-agent-panel':path.includes('App.css')?'.data-layer':'.chat-inspection'),selector).toBe(true)}})
})
it('keeps integrity warning semantics distinct from the teal checked state and adds no generated instruction',()=>{
 const css=readFileSync('src/components/ChatInspection.css','utf8'),delta=css.split('/* COLOR_INSPECTOR:')[1]
 expect(delta).toContain('.chat-inspection-integrity--checked')
 expect(delta).not.toContain('.chat-inspection-integrity--unverified')
 expect(delta).not.toContain('.chat-inspection-integrity--unavailable')
 for(const path of paths){const extra=readFileSync(path,'utf8').split('/* COLOR_INSPECTOR:')[1];assertNoGeneratedContent('/* COLOR_INSPECTOR:'+extra)}
})

it('detects actual generated-content declarations without treating alignment properties or selectors as content',()=>{
 expect(()=>assertNoGeneratedContent('.heading { justify-content: space-between; } .window-panel-content:has(details[open]) { display: none; }')).not.toThrow()
 expect(()=>assertNoGeneratedContent('.heading::before { content: "label"; }')).toThrow()
 expect(()=>assertNoGeneratedContent('.heading::before { CONTENT: "label"; }')).toThrow()
})

const selected={trace_id:'trace-496fac766f384348',execution_id:'run-current',message_id:'m1',state:'available',integrity:'legacy_unverified',sha256:'a'.repeat(64),limitations:[],trace:{trace_id:'trace-496fac766f384348',run_id:'run-current',event_count:0,cost_usd:0,evidence_refs:[],events:[]}}
function contrastRatio(foreground:string,background:string){
 const linear=(channel:number)=>{const value=channel/255;return value<=.04045?value/12.92:((value+.055)/1.055)**2}
 const luminance=(value:string)=>{const channels=value.match(/\d+/g)?.slice(0,3).map(Number);if(!channels||channels.length!==3)throw new Error(`Unexpected computed color: ${value}`);return .2126*linear(channels[0])+.7152*linear(channels[1])+.0722*linear(channels[2])}
 const values=[luminance(foreground),luminance(background)].sort((a,b)=>b-a)
 return (values[0]+.05)/(values[1]+.05)
}
function loadApplicationStyles(){
 if(document.head.querySelector('[data-inspector-test-styles]'))return
 const style=document.createElement('style');style.dataset.inspectorTestStyles='true'
 style.textContent=['src/index.css','src/App.css','src/VisualSystem.css','src/components/ChatInspection.css','src/components/ChatInspectionOverrides.css'].flatMap(path=>postcss.parse(readFileSync(path,'utf8')).nodes.filter(node=>node.type==='rule'&&(node.selector.includes('chat-inspection')||node.selector==='button'||node.selector==='button:hover')).map(node=>node.toString())).join('\n')
 document.head.append(style)
}
function loadProductionInspectorStyles(){
 if(document.head.querySelector('[data-inspector-production-styles]'))return
 const style=document.createElement('style');style.dataset.inspectorProductionStyles='true'
 const relevant:string[]=[]
 for(const path of ['src/index.css','src/App.css','src/components/ChatInspection.css','src/components/ChatInspectionOverrides.css','src/ServiceSurfaces.css','src/VisualSystem.css','src/AppOverrides.css']){
  const css=postcss.parse(readFileSync(path,'utf8'))
  css.walkRules(rule=>{if(rule.selectors.some(selector=>selector.includes('.chat-inspection')||selector===':root'||selector==='#root .app-shell'||selector==='button'||selector==='button:hover'||selector==='select'||selector==='summary'))relevant.push(rule.toString().replace('#root .app-shell .chat-inspection :is(button, select, .chat-inspection-technical)','#root .app-shell .chat-inspection button, #root .app-shell .chat-inspection select, #root .app-shell .chat-inspection .chat-inspection-technical').replaceAll('var(--vs-work)','#101f2e').replaceAll('var(--vs-line)','#30495c').replaceAll('var(--vs-text)','#e3edf6').replaceAll('var(--vs-selection)','#1c4054').replaceAll('var(--vs-muted)','#abc0d0').replaceAll('var(--vs-accent)','#79c7da').replaceAll('var(--vs-focus)','#a1e5f0'))})
 }
 style.textContent=relevant.join('\n')
 document.head.append(style)
}
it('renders Inspector controls above application-wide dark surfaces with readable spacing and contrast',async()=>{
 vi.stubGlobal('fetch',vi.fn(async()=>({ok:true,status:200,json:async()=>({schema:'bago.chat.inspection.v1',conversation_id:'conv-current',revision:1,state:'selected',executions:[{trace_id:'trace-496fac766f384348',message_id:'m1',execution_id:'run-current'}],total:1,offset:0,next_offset:null,selected})})))
 loadApplicationStyles()
 render(<div id="root"><div className="app-shell"><div id="data-layer" className="data-layer"><ChatInspection view="summary" selection={{conversationId:'conv-current'}} onSelect={()=>{}} /></div></div></div>)
 const conversation=await screen.findByLabelText('Identidad de la conversación')
 await screen.findByText('run-current')
 const inspector=conversation.closest('.chat-inspection')!
 const copyButtons=screen.getAllByRole('button',{name:/copiar ID de/i})
 const select=inspector.querySelector('select')!
 const summary=inspector.querySelector('.chat-inspection-technical > summary')!
 const cs=(node:Element)=>getComputedStyle(node)
 expect(cs(conversation).display).toBe('grid')
 expect(cs(conversation).position).toBe('static')
 expect(cs(conversation).paddingTop).not.toBe('0px')
 expect(cs(conversation).backgroundColor).toBe('rgba(0, 0, 0, 0)')
 expect(cs(conversation).borderTopWidth).toBe('1px')
 expect(conversation.closest('.chat-inspection')?.lastElementChild).toBe(conversation)
 expect(cs(conversation.firstElementChild!).display).toBe('flex')
 expect(cs(conversation.firstElementChild!).gap).not.toBe('normal')
 expect(copyButtons).toHaveLength(3)
 for(const button of copyButtons){expect(button.textContent).toBe('Copiar');expect(['0','0px']).toContain(cs(button).borderRadius);expect(contrastRatio(cs(button).color,cs(button).backgroundColor)).toBeGreaterThanOrEqual(4.5)}
 expect(cs(select).backgroundColor).toBe('rgb(241, 230, 205)')
 expect(cs(summary).backgroundColor).toBe('rgb(43, 52, 64)')
 expect(contrastRatio(cs(select).color,cs(select).backgroundColor)).toBeGreaterThanOrEqual(4.5)
 expect(contrastRatio(cs(summary).color,cs(summary).backgroundColor)).toBeGreaterThanOrEqual(4.5)
 const counters=[...inspector.querySelectorAll('.chat-inspection-counters > div')]
 expect(counters).toHaveLength(4)
 for(const card of counters){const background=cs(card).backgroundColor;expect(background).not.toBe('rgba(0, 0, 0, 0)');for(const text of [...card.querySelectorAll('dt,dd')])expect(contrastRatio(cs(text).color,background)).toBeGreaterThanOrEqual(4.5)}
 const details=inspector.querySelector('.chat-inspection-technical')!,disclosure=details.querySelector(':scope > summary')!
 expect(cs(disclosure).display).toBe('list-item')
 fireEvent.click(disclosure)
 expect((details as HTMLDetailsElement).open).toBe(true)
 const css=readFileSync('src/components/ChatInspection.css','utf8')+readFileSync('src/components/ChatInspectionOverrides.css','utf8'),r2=css.split('/* INSPECTOR_LAYOUT_R2:')[1]
 expect(r2).toContain('@container chat-inspection (max-width: 420px)')
 expect(r2).toContain('grid-template-columns: minmax(0, 1fr)')
 expect(r2).toContain('min-width: 0')
 const r3=css.split('/* INSPECTOR_COUNTERS_R3:')[1]
 const r4=css.split('/* INSPECTOR_IDENTITY_R4:')[1]
 expect(r4).toContain('position: static')
 expect(r4).toContain('border-top: 1px solid')
 expect(r4).toContain('min-height: 32px')
 expect(r4).toContain('overflow-wrap: anywhere')
 expect(r3).toContain('#root #data-layer .chat-inspection .chat-inspection-counters > div')
 expect(r3).toContain('#root #data-layer .chat-inspection .chat-inspection-counters dt')
 expect(r3).toContain('#root #data-layer .chat-inspection .chat-inspection-counters dd')
 expect(r3).toContain('display: list-item')
})

it('keeps embedded Inspector navigation, execution selector and details readable in application CSS order',async()=>{
 vi.stubGlobal('fetch',vi.fn(async()=>({ok:true,status:200,json:async()=>({schema:'bago.chat.inspection.v1',conversation_id:'conv-current',revision:1,state:'selected',executions:[{trace_id:'trace-496fac766f384348',message_id:'m1',execution_id:'run-current'}],total:1,offset:0,next_offset:null,selected})})))
 loadProductionInspectorStyles()
 const view=render(<div id="root"><div className="app-shell"><div id="data-layer" className="data-layer"><ChatInspection view="inspector" embedded selection={{conversationId:'conv-current'}} onSelect={()=>{}} onViewChange={()=>{}} /></div></div></div>)
 const summaryButton=await screen.findByRole('button',{name:'Resumen de la ejecución'})
 const traceButton=screen.getByRole('button',{name:'Traza de la ejecución'})
 const inspector=view.container.querySelector('.chat-inspection')!
 const executionSelect=inspector.querySelector('.chat-inspection-run-control select')!
 const technicalSummary=inspector.querySelector('.chat-inspection-common > summary')!
 const controls=[summaryButton,traceButton,executionSelect,technicalSummary]
 expect(summaryButton.disabled).toBe(false)
 expect(traceButton.disabled).toBe(false)
 expect(getComputedStyle(summaryButton).color).toBe('rgb(227, 237, 246)')
 for(const control of controls){
  expect(contrastRatio(getComputedStyle(control).color,getComputedStyle(control).backgroundColor)).toBeGreaterThanOrEqual(4.5)
 }
})

it('keeps all four honest zero counters opaque and legible in an empty summary',async()=>{
 vi.stubGlobal('fetch',vi.fn(async()=>({ok:true,status:200,json:async()=>({schema:'bago.chat.inspection.v1',conversation_id:'conv-empty',revision:1,state:'no_artifacts',executions:[],total:0,offset:0,next_offset:null,selected:null})})))
 loadApplicationStyles()
 const view=render(<div id="root"><div className="app-shell"><div id="data-layer" className="data-layer"><ChatInspection view="summary" embedded selection={{conversationId:'conv-empty'}} onSelect={()=>{}} /></div></div></div>)
 await screen.findByText(/Esta conversaci.n no tiene artefactos/)
 const cards=[...view.container.querySelectorAll('.chat-inspection-counters > div')]
 expect(cards).toHaveLength(4)
 expect(cards.map(card=>card.querySelector('dd')?.textContent)).toEqual(['0','0','0','0'])
 for(const card of cards){const background=getComputedStyle(card).backgroundColor;expect(background).not.toBe('rgba(0, 0, 0, 0)');for(const text of [...card.querySelectorAll('dt,dd')])expect(contrastRatio(getComputedStyle(text).color,background)).toBeGreaterThanOrEqual(4.5)}
})
