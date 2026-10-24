// @vitest-environment jsdom
import React from 'react'
import {resetLocaleForTests,setLocale,t} from '../../src/i18n'
beforeEach(()=>{localStorage.clear();resetLocaleForTests();setLocale('es')})
import {beforeEach,afterEach,expect,it,vi} from 'vitest'
import {act,cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import WorkspaceWriteReview,{isWriteProposalSummary} from '../../src/components/WorkspaceWriteReview'
import {summary,review,props,context,response} from './fixtures'
afterEach(()=>{cleanup();vi.unstubAllGlobals()})
function stub(handler?:(body:any)=>any){const calls:any[]=[];vi.stubGlobal('fetch',vi.fn(async(path:string,init:RequestInit)=>{const body=JSON.parse(String(init.body));calls.push({path,body});return handler?handler(body):response(review)}));return calls}
const consent=()=>screen.getByLabelText('He revisado el proyecto, el archivo y el contenido de esta revisión.')
it('restores an applied review in StrictMode with one pending read and no automatic write',async()=>{
 let finish!:(value:any)=>void
 const calls=stub(()=>new Promise(resolve=>{finish=resolve}))
 render(<React.StrictMode><WorkspaceWriteReview {...props}/></React.StrictMode>)
 expect(calls).toHaveLength(1)
 await act(async()=>finish(response({...review,status:'APPLIED',receipt:{id:'strict-receipt'}})))
 await screen.findByText('Aplicada')
 expect(calls.map(c=>c.body.operation)).toEqual(['review_write'])
 expect(screen.queryByRole('button',{name:'Confirmar y escribir'})).toBeNull()
 fireEvent.click(screen.getByRole('button',{name:'Recargar revisión'}))
 expect(calls).toHaveLength(2)
 await act(async()=>finish(response({...review,status:'APPLIED',receipt:{id:'strict-receipt'}})))
 await screen.findByText('Aplicada')
})
it('loads full content/diff with original context, never applies on restoration, and requires explicit approval',async()=>{
 const calls=stub(body=>response(body.operation==='apply_write'?{...review,status:'APPLIED',receipt:{id:'receipt-fixture',after_sha256:review.proposed_sha256}}:review))
 render(<WorkspaceWriteReview {...props}/>);await screen.findByDisplayValue(review.proposed_text)
 expect(calls).toHaveLength(1);expect(calls[0].body).toEqual({operation:'review_write',proposal_id:summary.proposal_id,context})
 expect(screen.getByText(summary.workspace_id)).toBeTruthy();expect(screen.getByText(summary.path)).toBeTruthy()
 const apply=screen.getByRole('button',{name:'Confirmar y escribir'}) as HTMLButtonElement;expect(apply.disabled).toBe(true)
 fireEvent.click(screen.getByRole('tab',{name:'Cambios'}));expect(screen.getByRole('tabpanel',{name:'Cambios'}).querySelector('pre')?.textContent).toBe(review.diff)
 fireEvent.click(consent());fireEvent.click(apply)
 await screen.findByText('Aplicada');expect(calls).toHaveLength(2)
 expect(calls[1].body).toEqual({operation:'apply_write',proposal_id:summary.proposal_id,expected_revision:summary.revision,review_sha256:review.review_sha256,context,confirmation:{confirmed:true,operation:'apply_write',workspace_id:summary.workspace_id,proposal_id:summary.proposal_id,revision:summary.revision,review_sha256:review.review_sha256}})
 expect(screen.queryByRole('button',{name:'Confirmar y escribir'})).toBeNull();expect(screen.getByText('Recibo de escritura')).toBeTruthy()
})
it('editing requires revise then a new explicit review approval, preserving target and context',async()=>{
 const newer={...review,revision:'revision-two',proposed_text:'Mi edición',proposed_sha256:'c'.repeat(64),review_sha256:'d'.repeat(64),diff:'+Mi edición'}
 const calls=stub(body=>response(body.operation==='revise_write'?newer:review))
 render(<WorkspaceWriteReview {...props}/>);await screen.findByDisplayValue(review.proposed_text);fireEvent.click(consent())
 fireEvent.change(screen.getByLabelText('Contenido propuesto'),{target:{value:'Mi edición'}})
 expect((consent() as HTMLInputElement).checked).toBe(false);expect((consent() as HTMLInputElement).disabled).toBe(true)
 expect((screen.getByRole('button',{name:'Confirmar y escribir'}) as HTMLButtonElement).disabled).toBe(true)
 fireEvent.click(screen.getByRole('button',{name:'Guardar propuesta y revisar'}));await screen.findByText('revision-two')
 expect(calls[1].body).toEqual({operation:'revise_write',proposal_id:summary.proposal_id,expected_revision:'revision-one',text:'Mi edición',context})
 expect((consent() as HTMLInputElement).checked).toBe(false);expect((screen.getByRole('button',{name:'Confirmar y escribir'}) as HTMLButtonElement).disabled).toBe(true)
 expect(calls.some(c=>c.body.operation==='apply_write')).toBe(false)
})
it.each(['APPLIED','UNCERTAIN','CONFLICT'] as const)('restores %s without apply or an enabled approval path',async(status)=>{
 const calls=stub(()=>response({...review,status,receipt:status==='APPLIED'?{id:'saved-receipt'}:null,observation:status==='UNCERTAIN'?{after_sha256:'a'.repeat(64),matches_proposed:true}:null}))
 render(<WorkspaceWriteReview {...props}/>);await screen.findByDisplayValue(review.proposed_text)
 expect(screen.queryByRole('button',{name:'Confirmar y escribir'})).toBeNull();expect(calls.map(c=>c.body.operation)).toEqual(['review_write'])
 if(status==='UNCERTAIN')expect(screen.getByRole('alert').textContent).toContain('No se reintentará')
})
it('keeps an uncertain effect visible after apply and never automatically retries',async()=>{
 const calls=stub(body=>response(body.operation==='apply_write'?{...review,status:'UNCERTAIN',observation:{after_sha256:'a'.repeat(64),matches_proposed:true},receipt:null}:review))
 render(<WorkspaceWriteReview {...props}/>);await screen.findByDisplayValue(review.proposed_text);fireEvent.click(consent());fireEvent.click(screen.getByRole('button',{name:'Confirmar y escribir'}))
 await screen.findByText('Resultado incierto');expect(screen.getByText('Resultado observado')).toBeTruthy();expect(calls).toHaveLength(2);expect(screen.queryByRole('button',{name:'Confirmar y escribir'})).toBeNull()
})
it('recovers read-only after a 409 apply failure and clears approval without retrying',async()=>{
 let load=0;const calls=stub(body=>body.operation==='apply_write'?response({error:{message:'La base cambió'}},409):response(++load===1?review:{...review,status:'CONFLICT'}))
 render(<WorkspaceWriteReview {...props}/>);await screen.findByDisplayValue(review.proposed_text);fireEvent.click(consent());fireEvent.click(screen.getByRole('button',{name:'Confirmar y escribir'}))
 await screen.findByText('Conflicto de revisión');expect(calls.map(c=>c.body.operation)).toEqual(['review_write','apply_write','review_write']);expect(screen.getByText((_text,node)=>node?.tagName==='P'&&node.textContent===t('common.requestFailed')+'\n'+t('common.originalDiagnostic')+': La base cambió')).toBeTruthy()
})
it('failed refresh removes the approval path instead of accepting stale review',async()=>{
 let n=0;stub(()=>++n===1?response(review):response({error:{message:'Persistencia no disponible'}},503))
 render(<WorkspaceWriteReview {...props}/>);await screen.findByDisplayValue(review.proposed_text);fireEvent.click(consent());fireEvent.click(screen.getByRole('button',{name:'Recargar revisión'}))
 await screen.findByText((_text,node)=>node?.tagName==='P'&&node.textContent===t('common.requestFailed')+'\n'+t('common.originalDiagnostic')+': Persistencia no disponible');expect(screen.queryByRole('button',{name:'Confirmar y escribir'})).toBeNull()
})
it('failed revise preserves unsaved text and never retains approval',async()=>{
 const calls=stub(body=>body.operation==='revise_write'?response({error:{message:'Revisión obsoleta'}},409):response(review))
 render(<WorkspaceWriteReview {...props}/>);await screen.findByDisplayValue(review.proposed_text);fireEvent.click(consent());fireEvent.change(screen.getByLabelText('Contenido propuesto'),{target:{value:'Conservar borrador'}});fireEvent.click(screen.getByRole('button',{name:'Guardar propuesta y revisar'}))
 await screen.findByText((_text,node)=>node?.tagName==='P'&&node.textContent===t('common.requestFailed')+'\n'+t('common.originalDiagnostic')+': Revisión obsoleta');expect((screen.getByLabelText('Contenido propuesto') as HTMLTextAreaElement).value).toBe('Conservar borrador');expect((consent() as HTMLInputElement).checked).toBe(false);expect(calls.some(c=>c.body.operation==='apply_write')).toBe(false)
})
it('ignores an old review arriving after owner switch and renders no action for foreign scope',async()=>{
 let finish:(r:any)=>void=()=>{};vi.stubGlobal('fetch',vi.fn(()=>new Promise(resolve=>{finish=resolve})))
 const view=render(<WorkspaceWriteReview {...props}/>);view.rerender(<WorkspaceWriteReview {...props} ownerId="other-agent"/>)
 await act(async()=>finish(response(review)))
 expect(screen.getByRole('alert').textContent).toContain('no corresponde');expect(screen.queryByRole('button',{name:'Confirmar y escribir'})).toBeNull()
})
it('changing current conversation revision refetches and invalidates prior consent, retaining original proposal context',async()=>{
 const calls=stub();const view=render(<WorkspaceWriteReview {...props}/>);await screen.findByDisplayValue(review.proposed_text);fireEvent.click(consent())
 view.rerender(<WorkspaceWriteReview {...props} conversationRevision={10}/>);await waitFor(()=>expect(calls).toHaveLength(2));await screen.findByDisplayValue(review.proposed_text)
 expect((consent() as HTMLInputElement).checked).toBe(false);expect(calls[1].body.context.conversation_revision).toBe(7)
})
it.each([
 ['wrong-workspace',{workspace_id:'other'}],['wrong-path',{path:'other.md'}],['wrong-owner',{context:{...context,owner_id:'other'}}],['wrong-conversation',{context:{...context,conversation_id:'other'}}],['changed-original-context',{context:{...context,conversation_revision:8}}],['bad-hash',{review_sha256:null}],['missing-text',{proposed_text:null}],['bad-receipt',{receipt:[]}],['bad-status',{status:'SUCCESS'}],['same-revision-changed-content',{proposed_sha256:'c'.repeat(64)}],
])('rejects invalid full review: %s',async(_name,fields)=>{
 stub(()=>response({...review,...fields}));render(<WorkspaceWriteReview {...props}/>);await screen.findByRole('alert');expect(screen.queryByRole('button',{name:'Confirmar y escribir'})).toBeNull()
})
it('rejects an invalid summary without requesting or authorizing anything',()=>{
 const calls=stub();expect(isWriteProposalSummary({...summary,path:'../outside'})).toBe(false)
 render(<WorkspaceWriteReview {...props} proposal={{...summary,path:'../outside'}}/>);expect(screen.getByRole('alert')).toBeTruthy();expect(calls).toEqual([])
})
it('ignores a late valid response after switching to another proposal in the same conversation',async()=>{
 const second={...summary,proposal_id:'write_'+'b'.repeat(32),path:'results/second.md'};const secondReview={...review,...second,proposed_text:'Segunda propuesta'}
 let finishOld:(r:any)=>void=()=>{}
 vi.stubGlobal('fetch',vi.fn(async(_path:string,init:RequestInit)=>JSON.parse(String(init.body)).proposal_id===summary.proposal_id?new Promise(resolve=>{finishOld=resolve}):response(secondReview)))
 const view=render(<WorkspaceWriteReview {...props}/>);view.rerender(<WorkspaceWriteReview {...props} proposal={second}/>)
 await screen.findByDisplayValue('Segunda propuesta');await act(async()=>finishOld(response(review)))
 expect(screen.queryByDisplayValue(review.proposed_text)).toBeNull();expect(screen.getByText('results/second.md')).toBeTruthy()
})
it('does not attach an old apply receipt to a newly selected proposal',async()=>{
 const second={...summary,proposal_id:'write_'+'b'.repeat(32),path:'results/second.md'};const secondReview={...review,...second,proposed_text:'Segunda propuesta'}
 let finishApply:(r:any)=>void=()=>{}
 vi.stubGlobal('fetch',vi.fn(async(_path:string,init:RequestInit)=>{const b=JSON.parse(String(init.body));if(b.operation==='apply_write')return new Promise(resolve=>{finishApply=resolve});return response(b.proposal_id===second.proposal_id?secondReview:review)}))
 const view=render(<WorkspaceWriteReview {...props}/>);await screen.findByDisplayValue(review.proposed_text);fireEvent.click(consent());fireEvent.click(screen.getByRole('button',{name:'Confirmar y escribir'}))
 view.rerender(<WorkspaceWriteReview {...props} proposal={second}/>);await screen.findByDisplayValue('Segunda propuesta');await act(async()=>finishApply(response({...review,status:'APPLIED',receipt:{id:'old-receipt'}})))
 expect(screen.queryByText('Aplicada')).toBeNull();expect(screen.queryByText('Recibo de escritura')).toBeNull();expect((consent() as HTMLInputElement).checked).toBe(false)
})
it('reviews a modification with original content and base hash without changing the target',async()=>{
 const modified={...summary,mode:'modify' as const},modifiedReview={...review,...modified,before_text:'Texto anterior',before_sha256:'e'.repeat(64),diff:'-Texto anterior\n+Texto original propuesto'}
 const calls=stub(()=>response(modifiedReview));render(<WorkspaceWriteReview {...props} proposal={modified}/>);await screen.findByDisplayValue(review.proposed_text)
 expect(screen.getByRole('heading',{name:'Modificar archivo'})).toBeTruthy();fireEvent.click(screen.getByRole('tab',{name:'Cambios'}));expect(screen.getByRole('tabpanel',{name:'Cambios'}).textContent).toContain('Texto anterior')
 expect(calls.map(c=>c.body.operation)).toEqual(['review_write']);expect((screen.getByRole('button',{name:'Confirmar y escribir'}) as HTMLButtonElement).disabled).toBe(true)
})
