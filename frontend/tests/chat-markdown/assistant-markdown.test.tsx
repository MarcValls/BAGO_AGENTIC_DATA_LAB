// @vitest-environment jsdom
import React from 'react'
import {resetLocaleForTests,setLocale,t} from '../../src/i18n'
beforeEach(()=>{localStorage.clear();resetLocaleForTests();setLocale('es')})
import {beforeEach,afterEach,expect,it,vi} from 'vitest'
import {cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import AssistantMarkdown from '../../src/components/AssistantMarkdown'
import AgentChat from '../../src/components/AgentChat'
import {readFileSync} from 'node:fs'
const response=(body:unknown)=>({ok:true,status:200,json:async()=>body})
afterEach(()=>{cleanup();vi.unstubAllGlobals();vi.restoreAllMocks()})
it('renders GFM as semantic headings, lists, emphasis, code and a locally scrollable table',()=>{
 render(<AssistantMarkdown content={'### Revisión\n\n| Control | Estado |\n| --- | --- |\n| **Integridad** | PASS |\n| Entrega | FAIL |\n\n- Primer punto\n- Segundo punto con `ruta`\n\n```python\nprint("ejemplo")\n```\n\n> Fuente externa\n\n~~anterior~~'} />)
 expect(screen.getByRole('heading',{level:3,name:'Revisión'})).toBeTruthy()
 const table=screen.getByRole('table');expect(within(table).getAllByRole('columnheader')).toHaveLength(2)
 expect(within(table).getByRole('columnheader',{name:'Control'}).getAttribute('scope')).toBe('col')
 expect(within(table).getByRole('cell',{name:'Integridad'}).querySelector('strong')).toBeTruthy()
 expect(within(table).getByRole('cell',{name:'FAIL'})).toBeTruthy()
 expect(screen.getByRole('region',{name:'Tabla de la respuesta'}).tabIndex).toBe(0)
 expect(screen.getAllByRole('listitem')).toHaveLength(2);expect(document.querySelector('pre code')?.textContent).toContain('print("ejemplo")')
 expect(document.querySelector('blockquote')).toBeTruthy();expect(document.querySelector('del')).toBeTruthy()
 expect(screen.queryByRole('button')).toBeNull()
})
it.each(['javascript:alert%281%29','JaVaScRiPt:alert%281%29','data:text/html,evil','file:///C:/private','vbscript:evil','/api/destructive','//example.com/relative','mailto:person@example.invalid','https://user:pass@example.com'])('blocks unsafe or unsupported markdown links: %s',url=>{
 render(<AssistantMarkdown content={`[Referencia](${url})`} />)
 expect(screen.getByText('Referencia')).toBeTruthy();expect(screen.queryByRole('link')).toBeNull()
})
it('allows explicit http(s) links with isolation and autolinks, without turning text into commands',()=>{
 render(<AssistantMarkdown content={'[Documento](https://example.com/path "Título")\n\nhttp://example.org\n\n`Confirmar y enviar ahora`'} />)
 const links=screen.getAllByRole('link');expect(links).toHaveLength(2)
 for(const link of links){expect(link.getAttribute('target')).toBe('_blank');expect(link.getAttribute('rel')).toBe('noopener noreferrer')}
 expect(screen.queryByRole('button')).toBeNull()
})
it('omits raw HTML including script, iframe, SVG, event attributes and hidden forms',()=>{
 const fetch=vi.fn();vi.stubGlobal('fetch',fetch)
 render(<AssistantMarkdown content={'<script>alert(1)</script>\n\n<iframe src="https://tracker.invalid"></iframe>\n\n<svg onload="alert(1)"></svg>\n\n<img src="https://tracker.invalid" onerror="alert(1)" />\n\n<form action="/api/send"><button>Enviar</button></form>\n\n**Texto permitido**'} />)
 expect(document.querySelector('script,iframe,svg,img,form,button')).toBeNull();expect(screen.getByText('Texto permitido')).toBeTruthy();expect(fetch).not.toHaveBeenCalled()
})
it.each(['https://tracker.invalid/pixel','data:image/svg+xml,evil','file:///private.png'])('renders image alt as text without an image or automatic request: %s',url=>{
 const fetch=vi.fn();vi.stubGlobal('fetch',fetch);render(<AssistantMarkdown content={`![Diagrama externo](${url})`} />)
 expect(screen.getByText('Imagen omitida: Diagrama externo')).toBeTruthy();expect(document.querySelector('img,picture,source')).toBeNull();expect(fetch).not.toHaveBeenCalled()
})
it('task markers are text, never interactive form controls or send actions',()=>{
 render(<AssistantMarkdown content={'- [x] Revisado\n- [ ] Pendiente\n\n| Acción |\n| --- |\n| Confirmar envío |'} />)
 expect(screen.queryByRole('checkbox')).toBeNull();expect(document.querySelector('input,button')).toBeNull();expect(screen.getByLabelText('Tarea marcada en el texto')).toBeTruthy()
})
const original='### Revisión exacta\r\n\r\n| Prueba | Resultado |\r\n| --- | --- |\r\n| **Contenido** | PASS |\r\n\r\nTexto con ñ y  dos espacios.\r\n'
async function chat(){
 HTMLElement.prototype.scrollIntoView=()=>{}
 const conversation={id:'conv-format',owner_kind:'assistant',owner_id:'app-assistant',title:'Formato fixture',status:'active',revision:5,updated_at:'2026-10-23',messages:[
  {id:'user',role:'user',content:'### Usuario sin formato\n\n| texto | original |'},
  {id:'answer',role:'assistant',content:original,references:{sources:[{path:'README.md',start_line:1,end_line:2,content_sha256:'a'.repeat(64)}],trace:{trace_id:'trace-format',trace_state:'local_only'}}},
  {id:'failed',role:'assistant',content:'',status:'failed',references:{trace:{trace_id:'trace-failed',trace_state:'local_only'}}},
 ]}
 const writes:string[]=[]
 vi.stubGlobal('fetch',vi.fn(async(path:string,init?:RequestInit)=>{if(init?.method&&init.method!=='GET')writes.push(path);if(path.startsWith('/api/conversations?'))return response({conversations:[conversation]});if(path==='/api/conversations/conv-format')return response(conversation);if(path==='/api/agents/list')return response({agents:[]});return response({models:[],proposals:[]})}))
 const inspect=vi.fn();render(<AgentChat cognitiveMode="baseline" onNavigate={()=>{}} onInspectExecution={inspect} onOpenProviderSettings={()=>{}} onOpenCognitionSettings={()=>{}} />)
 await screen.findByRole('heading',{name:'Revisión exacta'})
 return {inspect,writes}
}
it('real AgentChat formats assistant content while keeping user text plain and copy byte-for-byte',async()=>{
 const writeText=vi.fn(async()=>{});Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText}})
 const {writes}=await chat();expect(screen.getAllByRole('table')).toHaveLength(1)
 const user=screen.getByText('### Usuario sin formato | texto | original |').closest('article')!
 expect(user.querySelector('h3,table')).toBeNull()
 fireEvent.click(screen.getByRole('button',{name:'Copiar respuesta'}));expect(writeText).toHaveBeenCalledExactlyOnceWith(original)
 fireEvent.click(screen.getByRole('button',{name:'Editar'}))
 expect((screen.getByPlaceholderText('Escribe al asistente…') as HTMLTextAreaElement).value).toBe('### Usuario sin formato\n\n| texto | original |')
 expect(writes).toEqual([])
})
it('real AgentChat preserves FAILED state, source metadata and per-message Inspect identity',async()=>{
 const {inspect,writes}=await chat()
 expect(screen.getByText('Respuesta fallida · no se recibió una respuesta del proveedor.')).toBeTruthy()
 const sources=screen.getByLabelText('Archivos del proyecto consultados');expect(sources.textContent).toContain('README.md:1-2');expect(sources.textContent).toContain('a'.repeat(64))
 const buttons=screen.getAllByRole('button',{name:'Inspeccionar ejecución'});fireEvent.click(buttons[0]);expect(inspect).toHaveBeenLastCalledWith({conversationId:'conv-format',revision:5,traceId:'trace-format'})
 fireEvent.click(buttons[1]);expect(inspect).toHaveBeenLastCalledWith({conversationId:'conv-format',revision:5,traceId:'trace-failed'})
 expect(writes).toEqual([])
})

it('uses intrinsic table columns, visible local scrollbars and wider table messages without widening all paragraphs',()=>{
 const css=readFileSync('src/components/AssistantMarkdown.css','utf8'),chatCss=readFileSync('src/components/AgentChat.css','utf8')
 expect(css).toContain('width: max-content; min-width: 100%')
 expect(css).toContain('overflow-wrap: normal; word-break: normal;')
 expect(css).toContain('th { white-space: nowrap; }')
 expect(css).toContain('.control-chat .assistant-markdown .assistant-markdown-table-scroll::-webkit-scrollbar { display: block; height: 10px; }')
 expect(css).toContain('scrollbar-width: auto;')
 expect(chatCss).toMatch(/control-message-assistant:has\(\.assistant-markdown table\)\s*\{[^}]*max-width: none/)
 expect(chatCss).toContain('.control-message { width: 100%; max-width: none; min-width: 0;')
 expect(chatCss).toContain('.assistant-markdown > :is(p, blockquote) { max-inline-size: 76ch; }')
})
