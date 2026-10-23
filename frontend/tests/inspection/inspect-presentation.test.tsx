// @vitest-environment jsdom
import React from 'react'
import {afterEach,beforeEach,expect,it,vi} from 'vitest'
import {act,cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import ChatInspection from '../../src/components/ChatInspection'
import {resetLocaleForTests,setLocale} from '../../src/i18n'
const conversation='conversation-'+ 'identity-complete-'.repeat(8)
const traceId='trace-496fac766f384348'
const originalHash='b'.repeat(64)
const response=(body:unknown)=>({ok:true,status:200,json:async()=>body})
const selected=()=>({trace_id:traceId,execution_id:'run-current',message_id:'message-original',state:'available',integrity:'hash_verified',sha256:originalHash,reason:'ORIGINAL_DIAGNOSTIC',limitations:['ORIGINAL LIMITATION'],trace:{trace_id:traceId,run_id:'run-current',event_count:1,cost_usd:0,evidence_refs:['EVIDENCE_ORIGINAL'],events:[{event_id:'event-original',trace_id:traceId,sequence:0,name:'ORIGINAL_EVENT',kind:'authorization',status:'DENY',parent_event_id:null,attributes:{original:'DO_NOT_TRANSLATE'},evidence_refs:['EVIDENCE_ORIGINAL']}]}})
const body=(id=conversation,choice:any=selected())=>({schema:'bago.chat.inspection.v1',conversation_id:id,revision:2,state:choice?'selected':'no_artifacts',total:choice?1:0,offset:0,next_offset:null,executions:choice?[{trace_id:traceId,execution_id:'run-current',message_id:'message-original'}]:[],selected:choice})
beforeEach(()=>{localStorage.clear();resetLocaleForTests()})
afterEach(()=>{cleanup();vi.unstubAllGlobals();vi.restoreAllMocks()})
it('separates full conversation identity, execution selector, trace, integrity and original technical bytes',async()=>{
 const source=body(),original=JSON.stringify(source),writeText=vi.fn(async()=>{})
 vi.stubGlobal('navigator',{clipboard:{writeText}});vi.stubGlobal('fetch',vi.fn(async()=>response(source)))
 render(<ChatInspection selection={{conversationId:conversation}} onSelect={vi.fn()}/>);
 await screen.findByText('event-original')
 const identity=screen.getByRole('group',{name:'Identidad de la conversación'})
 expect(within(identity).getByText(conversation).tagName).toBe('CODE');expect(writeText).not.toHaveBeenCalled()
 expect((screen.getByRole('combobox') as HTMLSelectElement).value).toBe(traceId)
 const execution=screen.getByLabelText('Identidad de la ejecución seleccionada')
 expect(within(execution).getByText('run-current')).toBeTruthy();expect(within(execution).getByText(traceId)).toBeTruthy()
 expect(within(execution).getByText('Hash comprobado')).toBeTruthy();expect(within(execution).queryByText('PASS')).toBeNull()
 const details=screen.getByText('Datos técnicos originales').closest('details')!
 expect(details.hasAttribute('open')).toBe(false)
 for(const raw of [originalHash,'hash_verified','ORIGINAL_DIAGNOSTIC','ORIGINAL LIMITATION'])expect(screen.getByText(raw).closest('details')).toBe(details)
 expect(screen.getByText('Registros de autorización').closest('dl')!.querySelectorAll('dd')).toHaveLength(4)
 expect(JSON.stringify(source)).toBe(original)
})
it('copies only the exact current conversation on explicit click and keeps copy feedback localized without refetch',async()=>{
 const writeText=vi.fn(async()=>{}),fetch=vi.fn(async()=>response(body()))
 vi.stubGlobal('navigator',{clipboard:{writeText}});vi.stubGlobal('fetch',fetch)
 render(<ChatInspection selection={{conversationId:conversation}} onSelect={vi.fn()}/>);await screen.findByText('event-original')
 fireEvent.click(screen.getByRole('button',{name:'Copiar ID de conversación'}))
 expect(await screen.findByText('ID de conversación copiado.')).toBeTruthy();expect(writeText).toHaveBeenCalledExactlyOnceWith(conversation)
 act(()=>setLocale('en'))
 expect(screen.getByRole('button',{name:'Copy conversation ID'})).toBeTruthy();expect(screen.getByText('Conversation ID copied.')).toBeTruthy();expect(screen.getByText('Hash checked')).toBeTruthy()
 expect(screen.getByRole('group',{name:'Conversation identity'})).toBeTruthy();expect(fetch).toHaveBeenCalledTimes(1)
})
it('reports clipboard denial honestly and does not turn it into copied feedback',async()=>{
 const writeText=vi.fn(async()=>{throw new Error('clipboard denied')})
 vi.stubGlobal('navigator',{clipboard:{writeText}});vi.stubGlobal('fetch',vi.fn(async()=>response(body())))
 render(<ChatInspection selection={{conversationId:conversation}} onSelect={vi.fn()}/>);await screen.findByText('event-original')
 fireEvent.click(screen.getByRole('button',{name:'Copiar ID de conversación'}))
 expect(await screen.findByText('No se pudo copiar. Selecciona y copia el ID completo.')).toBeTruthy();expect(screen.queryByText('ID de conversación copiado.')).toBeNull()
 act(()=>setLocale('en'));expect(screen.getByText('Copy failed. Select and copy the complete ID.')).toBeTruthy()
})
it('ignores a late clipboard success from the previous conversation',async()=>{
 let finish:()=>void=()=>{};const writeText=vi.fn(()=>new Promise<void>(resolve=>{finish=resolve}))
 vi.stubGlobal('navigator',{clipboard:{writeText}});vi.stubGlobal('fetch',vi.fn(async(url:string)=>response(url.includes('/conv-next/')?body('conv-next',null):body())))
 const view=render(<ChatInspection selection={{conversationId:conversation}} onSelect={vi.fn()}/>);await screen.findByText('event-original')
 fireEvent.click(screen.getByRole('button',{name:'Copiar ID de conversación'}))
 view.rerender(<ChatInspection selection={{conversationId:'conv-next'}} onSelect={vi.fn()}/>);await screen.findByText('Sin ejecución registrada')
 await act(async()=>finish())
 expect(screen.queryByText('ID de conversación copiado.')).toBeNull();expect(screen.getByText('conv-next')).toBeTruthy();expect(screen.queryByText(conversation)).toBeNull()
 expect(screen.queryByRole('combobox')).toBeNull();expect(screen.getByText('Registros de autorización').closest('dl')!.querySelectorAll('dd')).toHaveLength(4)
})
it.each(['invalid','unavailable'] as const)('keeps %s explicit without a success badge and preserves the original diagnostic in details',async(state)=>{
 const choice={...selected(),state,integrity:'not_available',sha256:null,trace:null}
 vi.stubGlobal('fetch',vi.fn(async()=>response(body(conversation,choice))))
 render(<ChatInspection selection={{conversationId:conversation}} onSelect={vi.fn()}/>);
 const alert=await screen.findByRole('alert')
 expect(alert.textContent).toContain(state==='invalid'?'fue rechazada':'no está disponible');expect(alert.textContent).not.toContain('ORIGINAL_DIAGNOSTIC')
 expect(screen.getByText('Integridad no disponible')).toBeTruthy();expect(screen.getByText('ORIGINAL_DIAGNOSTIC').closest('details')).toBeTruthy()
 expect(screen.queryByText('Hash comprobado')).toBeNull();expect(screen.queryByRole('table')).toBeNull()
})
it('distinguishes legacy integrity from hash verification in both locales',async()=>{
 vi.stubGlobal('fetch',vi.fn(async()=>response(body(conversation,{...selected(),integrity:'legacy_unverified'}))))
 render(<ChatInspection selection={{conversationId:conversation}} onSelect={vi.fn()}/>);await screen.findByText('event-original')
 expect(screen.getByText('Registro histórico sin verificar')).toBeTruthy();expect(screen.queryByText('Hash comprobado')).toBeNull()
 act(()=>setLocale('en'));expect(screen.getByText('Unverified historical record')).toBeTruthy();expect(screen.getByText('legacy_unverified').closest('details')).toBeTruthy()
})
