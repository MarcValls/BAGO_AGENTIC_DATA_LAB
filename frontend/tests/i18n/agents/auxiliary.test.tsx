// @vitest-environment jsdom
import React from 'react'
import {afterEach,beforeEach,expect,it,vi} from 'vitest'
import {act,cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import CognitionSettings from '../../../src/components/CognitionSettings'
import ProjectContextDocument from '../../../src/components/ProjectContextDocument'
import DirectoryScanRun from '../../../src/components/DirectoryScanRun'
import JobHistory from '../../../src/components/JobHistory'
import CapabilityManager from '../../../src/components/CapabilityManager'
import ExternalConnections from '../../../src/components/ExternalConnections'
import GovernedFixtureRunner from '../../../src/components/GovernedFixtureRunner'
import KnowledgeIngest from '../../../src/components/KnowledgeIngest'
import CatalogQuality from '../../../src/components/CatalogQuality'
import OntologyReview from '../../../src/components/OntologyReview'
import {resetLocaleForTests,setLocale,t,formatDate,formatNumber} from '../../../src/i18n'
const response=(body:any,status=200)=>({ok:status<400,status,json:async()=>body})
const ids=['project-context','project-state','active-handoff','conversations','cognition-traces']
const metadata={workspace_root:'C:/USER PROJECT',cognition:{profile:'bounded-original',capacity:16,max_hops:3,max_expansions:4},paths:ids.map(id=>({id,label:'ORIGINAL LABEL '+id,path:'C:/USER PROJECT/'+id,state:'present',purpose:'ORIGINAL PURPOSE '+id})),memory:{kind:'conversation_history',state:'present',description:'ORIGINAL MEMORY DESCRIPTION'}}
beforeEach(()=>{localStorage.clear();resetLocaleForTests();setLocale('es')})
afterEach(()=>{cleanup();vi.unstubAllGlobals()})
it('maps all known context IDs and memory UI without reading documents or refetching on locale',async()=>{
 const fetch=vi.fn(async()=>response(metadata));vi.stubGlobal('fetch',fetch)
 render(<CognitionSettings mode="baseline" onModeChange={vi.fn()}/>);
 await screen.findByText('Historial de conversaciones');expect(screen.getByText('Trazas cognitivas')).toBeTruthy();expect(screen.getByText('Contexto del proyecto')).toBeTruthy()
 act(()=>setLocale('en'));expect(screen.getByText('Project context')).toBeTruthy();expect(screen.getByText('Cognitive traces')).toBeTruthy();expect(screen.getByText('bounded-original')).toBeTruthy();expect(fetch).toHaveBeenCalledTimes(1)
})
it('changes a saved mode notice reactively without issuing a second selection or clearing the folder draft',async()=>{
 const changed=vi.fn();vi.stubGlobal('fetch',vi.fn(async()=>response(metadata)))
 render(<CognitionSettings mode="baseline" onModeChange={changed}/>);await screen.findByText('Contexto del proyecto')
 fireEvent.click(screen.getByRole('radio',{name:/BAGO5/}));expect(changed).toHaveBeenCalledTimes(1)
 act(()=>setLocale('en'));expect(screen.getByText('BAGO5 experimental applies to new messages.')).toBeTruthy();expect(changed).toHaveBeenCalledTimes(1)
})
it('retains a workspace draft and translates an existing cancelled selection without reapplying it',async()=>{
 const fetch=vi.fn(async(url:string)=>response(url==='/api/chat/context'?metadata:{cancelled:true}));vi.stubGlobal('fetch',fetch)
 render(<CognitionSettings mode="baseline" onModeChange={vi.fn()} workspaceOnly/>);const path=await screen.findByDisplayValue('C:/USER PROJECT');fireEvent.change(path,{target:{value:'C:/User draft'}})
 fireEvent.click(screen.getByRole('button',{name:t('core.CognitionSettings.use_folder_bf3210')}));await screen.findByText('Selección cancelada.')
 act(()=>setLocale('en'));expect(screen.getByText('Selection cancelled.')).toBeTruthy();expect((path as HTMLInputElement).value).toBe('C:/User draft');expect(fetch).toHaveBeenCalledTimes(2)
})
it('keeps an expanded project document and exact original content while localizing its known ID',async()=>{
 const content='# USER HEADING\nUSER ORIGINAL TEXT';const fetch=vi.fn(async()=>response({id:'project-context',workspace_root:'root',format:'markdown',content,path:'root/context.md',size_bytes:content.length,sha256:'a'.repeat(64)}));vi.stubGlobal('fetch',fetch)
 const view=render(<ProjectContextDocument item={{...metadata.paths[0],state:'present'}} workspaceRoot="root"/>);const details=view.container.querySelector('details')!;details.open=true;fireEvent(details,new Event('toggle',{bubbles:true}));await screen.findAllByText('USER ORIGINAL TEXT')
 act(()=>setLocale('en'));expect(screen.getByText('Project context')).toBeTruthy();expect(details.open).toBe(true);expect(view.container.querySelector('.project-document-raw pre')!.textContent).toBe(content);expect(fetch).toHaveBeenCalledTimes(1)
})
it('keeps a foreign document rejected and translates the stored local error without a new read',async()=>{
 const fetch=vi.fn(async()=>response({id:'foreign',workspace_root:'other',format:'markdown',content:'FOREIGN DOCUMENT'}));vi.stubGlobal('fetch',fetch)
 const view=render(<ProjectContextDocument item={{...metadata.paths[0],state:'present'}} workspaceRoot="root"/>);const details=view.container.querySelector('details')!;details.open=true;fireEvent(details,new Event('toggle',{bubbles:true}));await screen.findByRole('alert');expect(screen.queryByText('FOREIGN DOCUMENT')).toBeNull()
 act(()=>setLocale('en'));expect(screen.getByRole('alert').textContent).toContain('does not belong to the selected project');expect(fetch).toHaveBeenCalledTimes(1)
})
it('does not scan on locale change and retains exact directory and one-run consent',()=>{
 const fetch=vi.fn();vi.stubGlobal('fetch',fetch);render(<DirectoryScanRun conversationId="own" revision={4} showForm onConversationUpdate={vi.fn()}/>);
 const directory=screen.getByRole('textbox');fireEvent.change(directory,{target:{value:'src/EXACT'}});const consent=screen.getByRole('checkbox');fireEvent.click(consent)
 act(()=>setLocale('en'));expect((consent as HTMLInputElement).checked).toBe(true);expect((directory as HTMLInputElement).value).toBe('src/EXACT');expect(fetch).not.toHaveBeenCalled()
})
it('preserves an original directory HTTP diagnostic and translates its wrapper after explicit submit',async()=>{
 const fetch=vi.fn(async()=>response({detail:{code:'not_allowed',message:'EXACT SCAN DIAGNOSTIC'}},403));vi.stubGlobal('fetch',fetch)
 render(<DirectoryScanRun conversationId="own" revision={4} showForm onConversationUpdate={vi.fn()}/>);fireEvent.click(screen.getByRole('checkbox'));fireEvent.click(screen.getByRole('button'));await screen.findByRole('alert');const before=screen.getByRole('alert').textContent
 act(()=>setLocale('en'));expect(screen.getByRole('alert').textContent).not.toBe(before);expect(screen.getByRole('alert').textContent).toContain('EXACT SCAN DIAGNOSTIC');expect(fetch).toHaveBeenCalledTimes(1)
})
it('formats work metadata using selected Intl locale while retaining selection, zero cost and exact opaque values without refetch',async()=>{
 const job={key:'legacy_job:job-own',kind:'legacy_job',id:'job-own',agent_id:'agent-own',agent_name:'Historical fixture agent',status:'success',parent_conversation_id:null,conversation_id:null,message_id:null,trace_id:'EXACT OPAQUE TRACE',receipt_id:'EXACT OPAQUE RECEIPT',receipt_sha256:null,created_at:'2026-10-23T12:34:00Z',started_at:null,completed_at:null,activity_at:'2026-10-23T12:34:00Z',duration_ms:0,cost_usd:0,tools_executed:false,target_written:false,tool_receipt_count:0,related_key:null}
 const page={schema:'work-history.v1',items:[job],total:1,limit:50,offset:0,has_more:false,next_offset:null,sources:['legacy_job','task_run','delegation','agent_turn','evaluation'].map(kind=>({kind,state:'available',error_code:null,truncated:false}))}
 const fetch=vi.fn(async(_url:string)=>response(page));vi.stubGlobal('fetch',fetch)
 render(<JobHistory/>);const row=await screen.findByRole('button',{name:/legacy_job:job-own/});fireEvent.click(row)
 expect(screen.getByText('EXACT OPAQUE TRACE')).toBeTruthy();expect(screen.getByText('EXACT OPAQUE RECEIPT')).toBeTruthy();expect(row.getAttribute('aria-expanded')).toBe('true');expect(row.textContent).toContain('Éxito registrado');expect(screen.getByText('0 ms')).toBeTruthy();expect(screen.getByText('$'+formatNumber(0,{minimumFractionDigits:4,maximumFractionDigits:4}))).toBeTruthy()
 act(()=>setLocale('en'));expect(screen.getByText('EXACT OPAQUE TRACE')).toBeTruthy();expect(screen.getByText('EXACT OPAQUE RECEIPT')).toBeTruthy();expect(row.getAttribute('aria-expanded')).toBe('true');expect(row.textContent).toContain('Recorded success');expect(row.textContent).toContain('success');expect(screen.getAllByText(formatDate(job.created_at)+' UTC').length).toBeGreaterThan(0);expect(screen.getByText('0 ms')).toBeTruthy();expect(screen.getByText('$'+formatNumber(0,{minimumFractionDigits:4,maximumFractionDigits:4}))).toBeTruthy();expect(fetch).toHaveBeenCalledTimes(1)
 expect(fetch.mock.calls[0][0]).toBe('/api/work-history?limit=50&offset=0&kind=all')
})
it('maps known capability product metadata by ID and identifies unknown metadata as technical',async()=>{
 const entry={id:'workspace.read_text',name:'BACKEND ENGLISH NAME',provider:'BACKEND ENGLISH PROVIDER',effect:'READ',status:'AVAILABLE',integration:'CONNECTED',summary:'BACKEND ENGLISH SUMMARY',limits:{read_only:true},source_fingerprints:{'path.py':'a'.repeat(64)},source_available:true,fingerprint:'a'.repeat(64)}
 const fetch=vi.fn(async(url:string)=>response(url==='/api/capabilities'?{capabilities:[entry,{...entry,id:'future.id',name:'UNKNOWN ORIGINAL NAME'}]}:url.startsWith('/api/capabilities/proposals')?{proposals:[]}:{connections:[]}));vi.stubGlobal('fetch',fetch)
 render(<CapabilityManager/>);await screen.findByRole('heading',{name:'Leer texto acotado del espacio de trabajo'});expect(screen.queryByRole('heading',{name:'BACKEND ENGLISH NAME'})).toBeNull();expect(screen.getByRole('heading',{name:'Capacidad sin etiqueta de producto (future.id)'})).toBeTruthy();expect(screen.getByText(/UNKNOWN ORIGINAL NAME/)).toBeTruthy()
 const beforeLocale=fetch.mock.calls.map(([url])=>url);expect(beforeLocale).toEqual(['/api/capabilities','/api/capabilities/proposals?status=all&limit=100']);act(()=>setLocale('en'));expect(screen.getByRole('heading',{name:'Read bounded workspace text'})).toBeTruthy();expect(fetch.mock.calls.map(([url])=>url)).toEqual(beforeLocale)
})
it('keeps unsaved external connection values and credentials without contacting a service on locale change',async()=>{
 const fetch=vi.fn(async()=>response({connections:[]}));vi.stubGlobal('fetch',fetch);render(<ExternalConnections/>);await screen.findByText(t('core.ExternalConnections.no_connections_are_saved_8b3a0d'))
 const form=screen.getByRole('form',{name:t('core.ExternalConnections.new_connection_496567')});const name=within(form).getByLabelText(t('core.ExternalConnections.name_562bb1'));fireEvent.change(name,{target:{value:'USER CONNECTION'}})
 act(()=>setLocale('en'));expect((name as HTMLInputElement).value).toBe('USER CONNECTION');expect(fetch).toHaveBeenCalledTimes(1)
})
it('keeps GEX exact task/default instruction and translates existing persistence uncertainty without a second action',async()=>{
 const fetch=vi.fn(async(url:string)=>response(url.endsWith('/status')?{contract_version:'gex-runtime/v1',synthetic:true,capability_id:'fixture.read',state:'READY'}:{detail:{code:'TEMP_UNAVAILABLE',persisted:false}},url.endsWith('/status')?200:503));vi.stubGlobal('fetch',fetch)
 render(<GovernedFixtureRunner agentId="agent-own"/>);const create=screen.getByRole('button',{name:t('core.GovernedFixtureRunner.create_session_1ba8d2')});await screen.findByText(/READY/)
 const secret=screen.getByLabelText(t('core.GovernedFixtureRunner.operator_key_6d4c8e'));fireEvent.change(secret,{target:{value:'SECRET'}});fireEvent.click(create);await screen.findByRole('alert');expect(screen.getByRole('alert').textContent).toContain('TEMP_UNAVAILABLE')
 act(()=>setLocale('en'));expect(screen.getByRole('alert').textContent).toContain('Persistence unconfirmed.');expect(screen.getByDisplayValue('Lee el resumen de cliente de la fixture sintética registrada.')).toBeTruthy();expect(fetch).toHaveBeenCalledTimes(2)
})
it('retains knowledge authority values, source path and question across locale and submits the same raw enums',async()=>{
 const fetch=vi.fn(async()=>response({detail:{message:'EXACT KNOWLEDGE DIAGNOSTIC'}},503));vi.stubGlobal('fetch',fetch);render(<KnowledgeIngest/>);
 const path=screen.getByLabelText(t('core.KnowledgeIngest.project_relative_file_path_8c345b')),question=screen.getByLabelText(t('core.KnowledgeIngest.question_289aff'));fireEvent.change(path,{target:{value:'docs/USER.md'}});fireEvent.change(question,{target:{value:'USER QUESTION'}})
 const authority=screen.getByLabelText(t('core.KnowledgeIngest.declared_source_authority_40eded'));fireEvent.change(authority,{target:{value:'VERIFIED'}});act(()=>setLocale('en'))
 expect((authority as HTMLSelectElement).value).toBe('VERIFIED');expect(screen.getAllByRole('option',{name:'Verified (VERIFIED)'})).toHaveLength(2);expect(fetch).not.toHaveBeenCalled()
 fireEvent.click(screen.getByRole('button',{name:t('core.KnowledgeIngest.index_source_and_answer_281cef')}));await screen.findByRole('alert');expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({path:'docs/USER.md',question:'USER QUESTION',source_authority:'VERIFIED',minimum_authority:'PROPOSED'})
})
it('keeps catalog consent and health gate across locale, then rejects an incomplete explicit result',async()=>{
 const fetch=vi.fn(async(url:string)=>response(url.endsWith('/status')?{state:'healthy',configured:true,healthy:true}:{}));vi.stubGlobal('fetch',fetch);render(<CatalogQuality/>);await screen.findByText(t('core.CatalogQuality.local_service_configured_and_healthy_bd7656'))
 const consent=screen.getByRole('checkbox');fireEvent.click(consent);act(()=>setLocale('en'));expect((consent as HTMLInputElement).checked).toBe(true);expect(fetch).toHaveBeenCalledTimes(1)
 fireEvent.click(screen.getByRole('button',{name:t('core.CatalogQuality.run_local_openmetadata_catalog_check_df3d45')}));await screen.findByRole('alert');expect(screen.getByRole('alert').textContent).toContain('incomplete record');expect(screen.queryByRole('region',{name:t('core.CatalogQuality.catalog_validation_result_cee403')})).toBeNull();expect(fetch).toHaveBeenCalledTimes(2)
})
it('retains ontology source/question and translates invalid-record rejection without creating approval',async()=>{
 const fetch=vi.fn(async()=>response({proposal_id:'incomplete'}));vi.stubGlobal('fetch',fetch);render(<OntologyReview/>);const path=screen.getByLabelText(t('core.OntologyReview.relation_source_file_path_84d4d8'));fireEvent.change(path,{target:{value:'docs/EXACT.md'}})
 fireEvent.click(screen.getByRole('button',{name:t('core.OntologyReview.read_source_and_propose_relations_36e8e0')}));await screen.findByRole('alert');act(()=>setLocale('en'));expect(screen.getByRole('alert').textContent).toContain('incomplete proposal record');expect((path as HTMLInputElement).value).toBe('docs/EXACT.md');expect(screen.queryByRole('button',{name:t('core.OntologyReview.approve_selected_exact_proposal_ids_ee8cdd')})).toBeNull();expect(fetch).toHaveBeenCalledTimes(1)
})

