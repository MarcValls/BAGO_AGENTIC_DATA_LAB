// @vitest-environment jsdom
import React,{useEffect,useState} from 'react'
import {afterEach,beforeEach,expect,it,vi} from 'vitest'
import {act,cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import {readFileSync} from 'node:fs'
import RuntimeStatusBar from '../../src/components/RuntimeStatusBar'
import {PROVIDER_RESPONSE_OBSERVED_EVENT} from '../../src/contracts/provider-response-observation'
import {formatDate,resetLocaleForTests,setLocale} from '../../src/i18n'

const now=()=>new Date().toISOString()
const payload=(overrides:Record<string,unknown>={})=>({schema:'runtime-status.v1',checked_at:now(),backend:{responding:true},activity:{state:'idle',active_requests:0,scope:'current_process_http_api_requests',background_activity:'not_observed'},memory:{state:'available',history:{kind:'conversation_history',state:'present',proof:'metadata_presence_only'},general:{state:'disconnected'},checked_at:now(),error_code:null},provider:{state:'configured_unverified',provider_id:'ollama-cloud',model_id:'gemma4:31b',label:'Ollama',model:'gemma4:31b',observation:'registration_metadata',response_verified:false,checked_at:now(),error_code:null},git:{state:'repository',repo_detected:true,branch:'main',detached:false,remote_configured:true,remote_verification:'not_checked',checked_at:now(),cached:false,cache_ttl_seconds:5,error_code:null},...overrides})
const reply=(body:unknown,status=200)=>({ok:status<400,status,json:vi.fn(async()=>body)})
type Call={url:string;init?:RequestInit}
const group=(id:string)=>document.querySelector<HTMLButtonElement>(`.runtime-status-bar [data-group="${id}"]`)!
const refresh=()=>screen.getByRole('button',{name:/Actualizar estado de BAGO5|Refresh BAGO5 status/})
function deferred<T>(){let resolve!:(value:T)=>void;const promise=new Promise<T>(r=>{resolve=r});return {promise,resolve}}
async function setup(handler:(index:number)=>unknown|Promise<unknown>=()=>reply(payload())){
 const calls:Call[]=[];vi.stubGlobal('fetch',vi.fn(async(url:string,init?:RequestInit)=>{calls.push({url,init});return await handler(calls.length-1)}))
 const view=render(<RuntimeStatusBar/>);await act(async()=>{});return {view,calls}
}
const visibility=(value:'visible'|'hidden')=>{Object.defineProperty(document,'visibilityState',{configurable:true,value});document.dispatchEvent(new Event('visibilitychange'))}
let originalVisibility:PropertyDescriptor|undefined
beforeEach(()=>{localStorage.clear();resetLocaleForTests();setLocale('es');originalVisibility=Object.getOwnPropertyDescriptor(document,'visibilityState');Object.defineProperty(document,'visibilityState',{configurable:true,value:'visible'})})
afterEach(()=>{cleanup();vi.useRealTimers();vi.unstubAllGlobals();vi.restoreAllMocks();if(originalVisibility)Object.defineProperty(document,'visibilityState',originalVisibility);else delete (document as any).visibilityState})

it.each(['es','en'] as const)('queries one readonly aggregate and presents five bounded groups in %s',async locale=>{
 setLocale(locale);const raw=payload({content:'PRIVATE_BODY_MARKER',workspace_root:'PRIVATE_PATH_MARKER',credentials:'PRIVATE_SECRET_MARKER'}),f=await setup(()=>reply(raw))
 expect(f.calls).toHaveLength(1);expect(f.calls[0].url).toBe('/api/runtime/status');expect(f.calls[0].init).toMatchObject({method:'GET',cache:'no-store'});expect(f.calls[0].init?.body).toBeUndefined()
 expect(f.view.container.querySelectorAll('[data-group]')).toHaveLength(5)
 expect(group('backend').textContent).toContain(locale==='es'?'API responde':'API responds')
 expect(group('activity').textContent).toContain(locale==='es'?'0 solicitudes activas':'0 active API requests')
 expect(group('memory').textContent).toContain(locale==='es'?'Historial disponible · general sin conectar':'History available · general disconnected')
 expect(group('git').textContent).toContain(locale==='es'?'main · remoto configurado':'main · remote configured')
 expect(group('provider').textContent).toContain('Ollama / gemma4:31b')
 expect(group('provider').querySelector('strong')?.textContent).toBe(locale==='es'?'Proveedores':'Providers')
 expect(screen.getByText(locale==='es'?'Desliza para ver Git y proveedores →':'Swipe to see Git and providers →')).toBeTruthy()
 expect(f.view.container.textContent).not.toMatch(/PRIVATE_(BODY|PATH|SECRET)_MARKER/)
 fireEvent.click(group('git'));const panel=screen.getByRole('region',{name:locale==='es'?'Git · detalles':'Git · details'})
 expect(within(panel).getByText(locale==='es'?'Autenticación GitHub':'GitHub authentication').nextElementSibling?.textContent).toBe(locale==='es'?'Sin comprobar':'Not checked')
 expect(panel.querySelector('time')?.dateTime).toBe(raw.git.checked_at)
 expect(panel.textContent).toContain(formatDate(raw.git.checked_at)+' UTC');expect(f.calls).toHaveLength(1)
})

const providerStates=[['ready','registrado, sin respuesta verificada','registered, response not verified'],['configured_unverified','configurado, sin verificar','configured, unverified'],['not_configured','no configurado','not configured'],['needs_authentication','requiere autenticación','authentication required'],['error','error de configuración','configuration error'],['unsupported_runtime','runtime no compatible','unsupported runtime'],['unavailable','sin datos','unavailable']]
it.each(providerStates.flatMap(([state,es,en])=>(['es','en'] as const).map(locale=>[state,locale,locale==='es'?es:en] as const)))('keeps provider %s honest in %s without probing or generation',async(state,locale,label)=>{
 setLocale(locale);const raw=payload();const f=await setup(()=>reply({...raw,provider:{...raw.provider,state}}));expect(group('provider').textContent).toContain(label)
 expect(group('provider').getAttribute('data-tone')).not.toBe('good')
 fireEvent.click(group('provider'));expect(screen.getByText(locale==='es'?'No verificada':'Not verified')).toBeTruthy()
 expect(f.calls.map(c=>c.url)).toEqual(['/api/runtime/status'])
})
it.each(['present','absent','unknown'])('distinguishes history %s from disconnected general memory without constructing records',async state=>{
 const raw=payload(),f=await setup(()=>reply({...raw,memory:{...raw.memory,history:{...raw.memory.history,state}}}));expect(group('memory').textContent).toContain(state==='present'?'Historial disponible':state==='absent'?'Historial ausente':'Historial sin comprobar');expect(group('memory').textContent).toContain('general sin conectar');expect(f.calls.every(c=>c.init?.method==='GET'&&!c.init.body)).toBe(true)
})
it('keeps partial errors local while backend and API activity remain observed',async()=>{
 const raw=payload(),f=await setup(()=>reply({...raw,memory:{...raw.memory,state:'unavailable',history:{kind:'conversation_history',state:'unknown'},general:{state:'not_observed'},error_code:'memory_metadata_unavailable'},provider:{...raw.provider,state:'unavailable',error_code:'provider_metadata_unavailable'},git:{...raw.git,state:'unavailable',repo_detected:null,branch:null,detached:null,remote_configured:null,error_code:'git_metadata_unavailable'}}))
 expect(group('backend').textContent).toContain('API responde');expect(group('activity').textContent).toContain('0 solicitudes activas');expect(group('memory').textContent).toContain('Sin datos de memoria');expect(group('git').textContent).toContain('Git no disponible')
 fireEvent.click(group('memory'));expect(screen.getByText('memory_metadata_unavailable')).toBeTruthy();expect(screen.getByText('No hay una lectura válida para acreditar presencia de historial.')).toBeTruthy();expect(f.calls).toHaveLength(1)
})
it('represents active requests only in the current API scope, never host Codex or all jobs',async()=>{
 const f=await setup(()=>reply(payload({activity:{state:'active',active_requests:3,scope:'current_process_http_api_requests',background_activity:'not_observed'}})))
 expect(group('activity').textContent).toContain('Actividad ADL');expect(group('activity').textContent).toContain('3 solicitudes activas');fireEvent.click(group('activity'));expect(screen.getByText('Peticiones HTTP del proceso API actual.')).toBeTruthy();expect(screen.getByText('Trabajos de fondo y actividad del host Codex.')).toBeTruthy();expect(f.calls).toHaveLength(1)
})
it('does not replace unknown API activity with zero or infer GitHub authentication from a remote',async()=>{
 const raw=payload();await setup(()=>reply({...raw,activity:{...raw.activity,active_requests:null},git:{...raw.git,remote_configured:true}}));expect(group('activity').textContent).toContain('Sin comprobar');expect(group('activity').textContent).not.toContain('0');fireEvent.click(group('git'));expect(screen.getByText('Autenticación GitHub').nextElementSibling?.textContent).toBe('Sin comprobar')
})
it.each([404,503])('keeps unknown states for aggregate HTTP%s without reading raw errors or fallback APIs',async status=>{
 const failed=reply({error:'PRIVATE_ERROR_MARKER'},status),f=await setup(()=>failed)
 expect(f.view.container.textContent).toContain('HTTP '+status);for(const id of ['memory','backend','activity','git','provider'])expect(group(id).textContent).toContain('Sin comprobar')
 expect(failed.json).not.toHaveBeenCalled();expect(f.view.container.textContent).not.toContain('PRIVATE_ERROR_MARKER');expect(f.calls).toHaveLength(1)
})
it('rejects malformed envelopes but isolates malformed individual sources',async()=>{
 const raw=payload(),f=await setup(i=>reply(i===0?{...raw,schema:'unknown'}:{...raw,provider:{...raw.provider,response_verified:true}}))
 expect(f.view.container.textContent).toContain('Respuesta de metadatos incompatible.');fireEvent.click(refresh());await act(async()=>{});expect(group('backend').textContent).toContain('API responde');expect(group('provider').textContent).toContain('Sin comprobar');expect(group('provider').getAttribute('data-tone')).toBe('unknown')
})
it('shows a session-local provider response without promoting registration metadata and keeps it through polling',async()=>{
 vi.useFakeTimers();const f=await setup();const observedAt='2026-10-26T10:30:00.000Z'
 act(()=>window.dispatchEvent(new CustomEvent(PROVIDER_RESPONSE_OBSERVED_EVENT,{detail:{provider_id:'ollama-cloud',model_id:'gemma4:31b',observed_at:observedAt}})))
 expect(group('provider').textContent).toContain('Respuesta recibida en esta sesión')
 fireEvent.click(group('provider'));let panel=screen.getByRole('region',{name:'Proveedores · detalles'})
 expect(panel.textContent).toContain('configurado, sin verificar');expect(panel.textContent).toContain('ollama-cloud / gemma4:31b');expect(panel.textContent).toContain('2026');expect(panel.textContent).toContain('No; esta observación sólo dura en esta pestaña.')
 fireEvent.click(refresh());await act(async()=>{});await act(async()=>{await vi.advanceTimersByTimeAsync(30_000)})
 expect(f.calls.length).toBeGreaterThanOrEqual(3);expect(group('provider').textContent).toContain('Respuesta recibida en esta sesión')
 f.view.unmount();const remounted=await setup();expect(group('provider').textContent).toContain('configurado, sin verificar');expect(group('provider').textContent).not.toContain('Respuesta recibida')
})
it('separates another provider response and ignores malformed session events',async()=>{
 await setup();act(()=>window.dispatchEvent(new CustomEvent(PROVIDER_RESPONSE_OBSERVED_EVENT,{detail:{provider_id:'openai-platform',model_id:'gpt-test',observed_at:'2026-10-26T10:30:00Z'}})))
 expect(group('provider').textContent).toContain('configurado, sin verificar');fireEvent.click(group('provider'));const panel=screen.getByRole('region',{name:'Proveedores · detalles'})
 expect(panel.textContent).toContain('openai-platform / gpt-test');expect(panel.textContent).toContain('Ninguna para este proveedor y modelo.')
 act(()=>window.dispatchEvent(new CustomEvent(PROVIDER_RESPONSE_OBSERVED_EVENT,{detail:{provider_id:'ollama-cloud',model_id:'private',observed_at:'not-a-time'}})))
 expect(group('provider').textContent).toContain('configurado, sin verificar')
})
it('preserves the last observation as earlier data after a failed refresh, never as newly disconnected',async()=>{
 const f=await setup(i=>i===0?reply(payload()):Promise.reject(new Error('PRIVATE_NETWORK_MARKER')))
 const button=refresh();button.focus();fireEvent.click(button);await act(async()=>{})
 expect(group('backend').textContent).toContain('API responde');expect(group('backend').textContent).toContain('Anterior');expect(group('backend').getAttribute('data-tone')).toBe('warning');expect(f.view.container.textContent).toContain('Se conserva la observación anterior.');expect(f.view.container.textContent).not.toContain('PRIVATE_NETWORK_MARKER');expect(document.activeElement).toBe(button)
})
it('uses each source observed UTC time and preserves stale cached Git rather than refreshing its timestamp',async()=>{
 const old=new Date(Date.now()-90_000).toISOString(),raw=payload();await setup(()=>reply({...raw,git:{...raw.git,checked_at:old,cached:true}}));expect(group('git').textContent).toContain('Anterior');expect(group('backend').textContent).not.toContain('Anterior');fireEvent.click(group('git'));const panel=screen.getByRole('region',{name:'Git · detalles'});expect(panel.querySelector('time')?.dateTime).toBe(old);expect(panel.textContent).toContain('Dato anterior; no es una comprobación actual')
})

it('polls every 30 seconds without overlap or an implicit 5-second active mode',async()=>{
 vi.useFakeTimers();const f=await setup(()=>reply(payload({activity:{state:'active',active_requests:1,scope:'current_process_http_api_requests',background_activity:'not_observed'}})))
 await act(async()=>{await vi.advanceTimersByTimeAsync(29_999)});expect(f.calls).toHaveLength(1)
 await act(async()=>{await vi.advanceTimersByTimeAsync(1)});expect(f.calls).toHaveLength(2)
 expect(f.calls.every(c=>c.url==='/api/runtime/status'&&c.init?.method==='GET')).toBe(true)
})
it('pauses hidden-tab polling and refreshes when visible, without fabricating an offline state',async()=>{
 vi.useFakeTimers();const f=await setup();await act(async()=>visibility('hidden'));await act(async()=>{await vi.advanceTimersByTimeAsync(90_000)});expect(f.calls).toHaveLength(1);expect(group('backend').textContent).toContain('API responde')
 await act(async()=>visibility('visible'));expect(f.calls).toHaveLength(2);expect(group('backend').textContent).not.toContain('Anterior')
})
it('starts unknown without a request when initially hidden',async()=>{
 visibility('hidden');const f=await setup();expect(f.calls).toHaveLength(0);expect(group('backend').textContent).toContain('Sin comprobar');await act(async()=>visibility('visible'));expect(f.calls).toHaveLength(1)
})
it('aborts a hidden request and ignores its late response after a newer visible reading',async()=>{
 const old=deferred<unknown>(),f=await setup(i=>i===0?old.promise:reply({...payload(),provider:{...payload().provider,model:'NEW-OBSERVED-MODEL'}}))
 await act(async()=>visibility('hidden'));expect(f.calls[0].init?.signal?.aborted).toBe(true);await act(async()=>visibility('visible'));expect(group('provider').textContent).toContain('NEW-OBSERVED-MODEL')
 await act(async()=>old.resolve(reply({...payload(),provider:{...payload().provider,model:'OLD-LATE-MODEL'}})));expect(group('provider').textContent).not.toContain('OLD-LATE-MODEL');expect(f.calls).toHaveLength(2)
})
it('bounds a hung request, does not overlap manual refreshes, and aborts on unmount',async()=>{
 vi.useFakeTimers();const pending=deferred<unknown>(),f=await setup(()=>pending.promise);fireEvent.click(refresh());fireEvent.click(refresh());expect(f.calls).toHaveLength(1)
 await act(async()=>{await vi.advanceTimersByTimeAsync(8000)});expect(f.calls[0].init?.signal?.aborted).toBe(true);expect(f.view.container.textContent).toContain('agotó su tiempo')
 fireEvent.click(refresh());await act(async()=>{});expect(f.calls).toHaveLength(2);f.view.unmount();expect(f.calls[1].init?.signal?.aborted).toBe(true);await act(async()=>pending.resolve(reply(payload())));expect(f.calls).toHaveLength(2)
})
it('preserves the active workspace node, draft, Git review and focus through refresh, polling, details and locale changes',async()=>{
 vi.useFakeTimers();const mounts=vi.fn(),unmounts=vi.fn(),calls:Call[]=[];vi.stubGlobal('fetch',vi.fn(async(url:string,init?:RequestInit)=>{calls.push({url,init});return reply(payload())}))
 function Workspace(){const [draft,setDraft]=useState('USER ACTIVE PROJECT');useEffect(()=>{mounts();return()=>unmounts()},[]);return <main><input aria-label="Project draft" value={draft} onChange={e=>setDraft(e.target.value)}/><section role="dialog" aria-label="Git review"><input type="checkbox" aria-label="Git consent" defaultChecked/><p>Existing Git error retained</p></section></main>}
 const f=render(<div className="app-shell"><aside>Sidebar</aside><Workspace/><RuntimeStatusBar/></div>);await act(async()=>{})
 const draft=screen.getByLabelText('Project draft'),review=screen.getByRole('dialog',{name:'Git review'}),consent=screen.getByLabelText('Git consent');fireEvent.change(draft,{target:{value:'UNSAVED USER DRAFT'}})
 const provider=group('provider');provider.focus();fireEvent.click(provider);expect(provider.getAttribute('aria-expanded')).toBe('true');fireEvent.keyDown(provider,{key:'Escape'});expect(document.activeElement).toBe(provider)
 fireEvent.click(refresh());await act(async()=>{});await act(async()=>{await vi.advanceTimersByTimeAsync(30_000)});const count=calls.length;act(()=>setLocale('en'))
 expect(screen.getByLabelText('Project draft')).toBe(draft);expect((draft as HTMLInputElement).value).toBe('UNSAVED USER DRAFT');expect(screen.getByRole('dialog',{name:'Git review'})).toBe(review);expect(screen.getByLabelText('Git consent')).toBe(consent);expect((consent as HTMLInputElement).checked).toBe(true);expect(calls).toHaveLength(count);expect(mounts).toHaveBeenCalledTimes(1);expect(unmounts).not.toHaveBeenCalled()
 expect(f.container.querySelector('.app-shell')?.lastElementChild?.tagName).toBe('FOOTER')
})
it('uses an opt-in normal-flow row and minimal App import/final-child integration without a fixed overlay',()=>{
 const css=readFileSync('src/components/RuntimeStatusBar.css','utf8'),app=readFileSync('src/App.tsx','utf8').replace(/\r\n/g,'\n')
 expect(css).toContain('grid-template-rows: minmax(0, 1fr) auto');expect(css).toContain('grid-template-rows: auto minmax(0, 1fr) auto');expect(css).toContain('grid-row: 2');expect(css).toContain('grid-row: 3');expect(css).not.toMatch(/position\s*:\s*(?:fixed|absolute)/);expect(css).toContain('font-size: 15px');expect(css).toContain('font-weight: 700');expect(css).toContain('runtime-status-bar__scroll-hint')
 const groupRule=css.split('.runtime-status-bar .runtime-status-bar__group {')[1]?.split('}')[0]??'',valueRule=css.split('.runtime-status-bar .runtime-status-bar__value {')[1]?.split('}')[0]??''
 expect(groupRule).toContain('display: grid');expect(groupRule).toContain('grid-template-rows: minmax(0, 1fr)');expect(groupRule).toContain('white-space: nowrap');expect(css).toContain('scroll-snap-type: x proximity')
 expect(valueRule).toContain('white-space: nowrap');expect(valueRule).toContain('text-overflow: ellipsis');expect(valueRule).toContain('overflow: hidden');expect(css).toContain('max-height: 28px')
 expect(app.match(/import RuntimeStatusBar from/g)).toHaveLength(1);expect(app.match(/<RuntimeStatusBar \/>/g)).toHaveLength(1);expect(app).toContain('</dialog>\n      <RuntimeStatusBar />\n    </div>')
})
it.each(['es','en'] as const)('separates summary, source-colored detail cards and UTC freshness without promoting configuration in %s',async locale=>{
 setLocale(locale);await setup();
 for(const id of ['memory','backend','activity','git','provider']){
  fireEvent.click(group(id));const panel=document.querySelector<HTMLElement>('.runtime-status-bar__details')!
  expect(panel.dataset.section).toBe(id);expect(panel.querySelector('h3')?.textContent).toBeTruthy();expect(panel.querySelector('.runtime-status-bar__summary .runtime-status-bar__state')?.textContent).toBe(group(id).querySelector('.runtime-status-bar__value')?.textContent)
  expect(panel.querySelectorAll('.runtime-status-bar__detail-grid > .runtime-status-bar__detail-card').length).toBeGreaterThan(0);expect(panel.querySelectorAll('.runtime-status-bar__detail-meta > div')).toHaveLength(2);expect(panel.querySelector('.runtime-status-bar__detail-meta time')?.dateTime).toBeTruthy()
  if(id==='provider'){expect(panel.querySelector('.runtime-status-bar__state')?.getAttribute('data-tone')).toBe('warning');expect(panel.textContent).toContain(locale==='es'?'No verificada':'Not verified')}
 }
 const css=readFileSync('src/components/RuntimeStatusBar.css','utf8');for(const id of ['memory','backend','activity','git','provider'])expect(css).toContain(`[data-section="${id}"]`)
 expect(css).toContain('grid-template-columns: repeat(2, minmax(0, 1fr))');expect(css).toContain('grid-template-columns: minmax(0, 1fr)');expect(css).toContain('overflow-y: auto')
})
