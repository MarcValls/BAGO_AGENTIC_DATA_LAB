import {t, useI18n, formatNumber, apiError, errorMessage, localMessage} from '../i18n'
import { useEffect, useId, useRef, useState } from 'react'
import type {ReactNode, KeyboardEvent} from 'react'
import ServiceTabs from './ServiceTabs'
import CsvTablePreview from './CsvTablePreview'
import {delimitedFile} from '../utils/delimitedText'
import './WorkspaceManager.css'

type Workspace = { id: string; root: string; name: string; title: string; context_files: Array<{ path: string; sha256: string }> }
type FileRecord = { path: string; sha256: string; size: number; text?: string }
type Trash = { trash_id: string; path: string; sha256: string; revision: string; integrity: string; recovery_required: boolean }
type Git = { head: string | null; branch: string; status: string[]; conflicts: string[] }
type Review = { workspaceId: string; operation: string; args: Record<string, unknown>; label: string|Error }
type FolderInput = {mode:'existing'|'create_child';path:string;name:string;title:string;expected_workspace_root:string}
type FolderPlan = FolderInput & {plan_id:string;plan_sha256:string;target_root:string;files:Array<{path:string;action:'create'|'preserve'}>;directories:Array<{path:string;action:'create'|'preserve'}>;expires_at:string}
type FolderError = Error & {folderReceipt?:Record<string,unknown>|null}
type ContextPanel = ReactNode | ((controls:{openProjectSelection:()=>void;refreshKey:number})=>ReactNode)
const isRecord=(value:unknown):value is Record<string,unknown>=>value!==null&&typeof value==='object'&&!Array.isArray(value)
function sameFolder(left:string,right:string){const normalize=(value:string)=>value.replace(/\\/g,'/').replace(/\/+$/,'');const a=normalize(left),b=normalize(right);return /^[a-z]:/i.test(a)&&/^[a-z]:/i.test(b)?a.toLocaleLowerCase()===b.toLocaleLowerCase():a===b}
async function folderRequest(path:string,body:unknown){
 const response=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})
 const data=await response.json()
 if(!response.ok){const error=apiError(data,response.status,'commerce') as FolderError;const receipt=data?.error?.receipt??data?.receipt;error.folderReceipt=isRecord(receipt)?receipt:null;throw error}
 return data
}
function validateFolderPlan(value:unknown,input:FolderInput):FolderPlan {
 if(!isRecord(value)||typeof value.plan_id!=='string'||!value.plan_id||typeof value.plan_sha256!=='string'||! /^[a-f0-9]{64}$/.test(value.plan_sha256)||value.mode!==input.mode||typeof value.path!=='string'||!sameFolder(value.path,input.path)||typeof value.expected_workspace_root!=='string'||!sameFolder(value.expected_workspace_root,input.expected_workspace_root)||typeof value.target_root!=='string'||typeof value.name!=='string'||typeof value.title!=='string'||typeof value.expires_at!=='string'||!Number.isFinite(Date.parse(value.expires_at)))throw localMessage('commerce.project_folder.invalid_plan')
 const target=input.mode==='existing'?input.path:input.path.replace(/[\\/]+$/,'')+'/'+input.name
 if(!sameFolder(value.target_root,target))throw localMessage('commerce.project_folder.invalid_plan')
 for(const field of ['files','directories'] as const){if(!Array.isArray(value[field])||value[field].some(entry=>!isRecord(entry)||typeof entry.path!=='string'||!entry.path||/^(?:[A-Za-z]:|[\\/])|(?:^|[\\/])\.\.(?:[\\/]|$)/.test(entry.path)||!['create','preserve'].includes(entry.action as string)))throw localMessage('commerce.project_folder.invalid_plan')}
 return value as unknown as FolderPlan
}

async function request(path: string, body?: unknown) {
  const response = await fetch(path, body === undefined ? undefined : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
  const data = await response.json()
  if (!response.ok) throw apiError(data,response.status,'commerce')
  return data
}

export type WorkspaceProposal = { intent: 'manage' | 'create' | 'open' | 'files' | 'git'; name?: string; path?: string }
export default function WorkspaceManager({ inline = false, onSelected, proposal, contextPanel, refreshKey = 0 }: { inline?: boolean; onSelected?: () => void; proposal?: WorkspaceProposal; contextPanel?:ContextPanel; refreshKey?:number }) {
  useI18n()

  const uid=useId()
  const [area,setArea]=useState<'projects'|'files'|'context'>(proposal?.intent==='files'||proposal?.intent==='git'?'files':'projects')
  const [config, setConfig] = useState<{workspace_root:string;scope:'global_workspace'}|null>(null)
  const [workspaces, setWorkspaces] = useState<Workspace[]>([])
  const [workspace, setWorkspace] = useState<Workspace | null>(null)
  const identity = useRef<string | null>(null)
  const [name, setName] = useState(''), [title, setTitle] = useState('')
  const [folderPath,setFolderPath]=useState(''),[folderMode,setFolderMode]=useState<'existing'|'create_child'>('existing')
  const [activeRoot,setActiveRoot]=useState<string|null>(null),[contextRefresh,setContextRefresh]=useState(0)
  const [folderPlan,setFolderPlan]=useState<{plan:FolderPlan;revision:number}|null>(null)
  const [folderReceipt,setFolderReceipt]=useState<Record<string,unknown>|null>(null),[folderBusy,setFolderBusy]=useState(false)
  const folderRevision=useRef(0),folderEdited=useRef(false),folderPathEdited=useRef(false),folderMounted=useRef(true),folderInput=useRef<HTMLInputElement|null>(null),folderHeading=useRef<HTMLHeadingElement|null>(null),folderOrigin=useRef<HTMLButtonElement|null>(null)
  const [focusRequest,setFocusRequest]=useState(0),focusTarget=useRef<'folder'|'origin'>('folder')
  const invalidateFolderPlan=()=>{folderRevision.current++;setFolderPlan(null)}
  const editFolder=(update:()=>void,pathChanged=false)=>{invalidateFolderPlan();folderEdited.current=true;if(pathChanged)folderPathEdited.current=true;update()}
  const openProjectSelection=()=>{focusTarget.current='folder';setArea('projects');setFocusRequest(value=>value+1)}
  const cancelFolderReview=()=>{if(folderBusy)return;invalidateFolderPlan();focusTarget.current='origin';setArea('projects');setFocusRequest(value=>value+1)}
  const reviewKeyboard=(event:KeyboardEvent<HTMLElement>)=>{if(event.key==='Escape'){event.preventDefault();cancelFolderReview();return}if(event.key!=='Tab')return;const controls=Array.from(event.currentTarget.querySelectorAll<HTMLElement>('summary,input:not(:disabled),button:not(:disabled)'));const first=controls[0],last=controls[controls.length-1];if(!first||!last)return;if(event.shiftKey&&(document.activeElement===first||document.activeElement===folderHeading.current)){event.preventDefault();last.focus()}else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus()}}
  useEffect(()=>{if(focusRequest){if(focusTarget.current==='origin'&&folderOrigin.current?.isConnected&&!folderOrigin.current.disabled)folderOrigin.current.focus();else folderInput.current?.focus()}},[focusRequest])
  useEffect(()=>{folderHeading.current?.focus()},[folderPlan])
  useEffect(()=>{folderMounted.current=true;return()=>{folderMounted.current=false;folderRevision.current++}},[])

  const [files, setFiles] = useState<FileRecord[]>([]), [excluded, setExcluded] = useState<Array<{ path: string; reason: string }>>([])
  const [directory, setDirectory] = useState(''), [path, setPath] = useState(''), [text, setText] = useState(''), [destination, setDestination] = useState('')
  const [file, setFile] = useState<FileRecord | null>(null), [trash, setTrash] = useState<Trash[]>([])
  const [contentView, setContentView] = useState<'table' | 'text'>('table')
  const delimiter = delimitedFile(path)
  const [tab, setTab] = useState<'files' | 'trash' | 'git'>('files')
  const [git, setGit] = useState<Git | null>(null), [selection, setSelection] = useState<string[]>([]), [stage, setStage] = useState<{ revision: string; head: string | null; paths: string[] } | null>(null)
  const [message, setMessage] = useState(''), [branch, setBranch] = useState(''), [diff, setDiff] = useState('')
  const [repo, setRepo] = useState(''), [planKind, setPlanKind] = useState('pr_create'), [plan, setPlan] = useState('')
  const [review, setReview] = useState<Review | null>(null), [accepted, setAccepted] = useState(false)
  const [busy, setBusy] = useState(false), [loading, setLoading] = useState(true), [error, setError] = useState<string|Error>(''), [notice, setNotice] = useState('')
  const dirty = Boolean(workspace) && (file ? text !== file.text || path !== file.path : Boolean(text || path))
  useEffect(() => { if (proposal?.name) {folderEdited.current=true;invalidateFolderPlan();setName(proposal.name)}; if (proposal?.path) setPath(proposal.path); if (proposal?.intent === 'git') {setTab('git');setArea('files')};if(proposal?.intent==='files')setArea('files') }, [proposal])
  const mutate = (operation: string, args: Record<string, unknown>, label: string|Error) => {
    if (!workspace||folderBusy) return
    invalidateFolderPlan();setAccepted(false); setReview({ workspaceId: workspace.id, operation, args, label }); setError('')
  }
  const action = (id: string, operation: string, args: Record<string, unknown> = {}) => request(`/api/project-folders/v1/workspaces/${encodeURIComponent(id)}/actions`, { operation, ...args })
  async function loadList() {
    const data = await request('/api/project-folders/v1/workspaces')
    if(folderMounted.current)setWorkspaces(data.workspaces)
  }
  useEffect(() => {let current=true;invalidateFolderPlan();setLoading(true);setError('')
    void Promise.all([request('/api/chat/context'),request('/api/project-folders/v1/config'),request('/api/project-folders/v1/workspaces')]).then(([context,settings,list])=>{
      if(!current)return
      if(typeof context?.workspace_root!=='string'||!context.workspace_root||settings?.scope!=='global_workspace'||typeof settings.workspace_root!=='string'||!sameFolder(settings.workspace_root,context.workspace_root)||!Array.isArray(list?.workspaces))throw localMessage('commerce.project_folder.unavailable')
      invalidateFolderPlan();setConfig(settings);setActiveRoot(context.workspace_root);if(!folderPathEdited.current)setFolderPath(context.workspace_root);if(!folderEdited.current){const matching=list.workspaces.find((entry:Workspace)=>typeof entry?.root==='string'&&sameFolder(entry.root,context.workspace_root));if(matching){setName(matching.name);setTitle(matching.title)}};setWorkspaces(list.workspaces)
    }).catch(cause=>{if(current){setConfig(null);setActiveRoot(null);setError(cause instanceof Error?cause:String(cause))}}).finally(()=>{if(current)setLoading(false)})
    return()=>{current=false}
  },[refreshKey])
  async function prepareFolder(inputOverride?:FolderInput){
    if(folderBusy||busy||loading||dirty||!activeRoot||!config)return
    if(inputOverride){invalidateFolderPlan();folderEdited.current=true;folderPathEdited.current=true;setFolderMode(inputOverride.mode);setFolderPath(inputOverride.path);setName(inputOverride.name);setTitle(inputOverride.title)}
    const input=inputOverride??{mode:folderMode,path:folderPath,name,title,expected_workspace_root:activeRoot}
    const revision=folderRevision.current;setFolderBusy(true);setError('');setNotice('');setReview(null);setAccepted(false);setFolderPlan(null);setFolderReceipt(null)
    try{const data=await folderRequest('/api/project-folders/v1/plans',input);if(!folderMounted.current||folderRevision.current!==revision)return;setFolderPlan({plan:validateFolderPlan(data,input),revision})}
    catch(cause){if(folderMounted.current&&folderRevision.current===revision)setError(cause as Error)}finally{if(folderMounted.current)setFolderBusy(false)}
  }
  async function browseFolder(){
    if(folderBusy||busy)return
    const revision=folderRevision.current;setFolderBusy(true);setError('');setNotice('')
    try{const data=await folderRequest('/api/project-folders/v1/browse',{});if(!folderMounted.current||revision!==folderRevision.current)return
      if(data?.cancelled===true){setNotice('commerce.project_folder.browse_cancelled');return}
      if(data?.cancelled!==false||typeof data.path!=='string'||!data.path)throw localMessage('commerce.project_folder.invalid_response')
      editFolder(()=>setFolderPath(data.path),true)
    }catch(cause){if(folderMounted.current&&revision===folderRevision.current)setError(cause as Error)}finally{if(folderMounted.current)setFolderBusy(false)}
  }
  async function applyFolder(){
    if(!folderPlan||folderBusy||busy||loading||dirty||folderPlan.revision!==folderRevision.current)return
    const exact=folderPlan;setFolderBusy(true);setError('');setNotice('')
    try{const data=await folderRequest(`/api/project-folders/v1/plans/${encodeURIComponent(exact.plan.plan_id)}/apply`,{plan_sha256:exact.plan.plan_sha256,confirmed:true})
      if(!folderMounted.current)return
      if(isRecord(data?.receipt))setFolderReceipt(data.receipt)
      if(typeof data?.workspace_root!=='string'||!sameFolder(data.workspace_root,exact.plan.target_root)||!isRecord(data.workspace)||typeof data.workspace.id!=='string'||typeof data.workspace.name!=='string'||typeof data.workspace.title!=='string'||typeof data.workspace.root!=='string'||!sameFolder(data.workspace.root,data.workspace_root)||!Array.isArray(data.workspace.context_files)||data.receipt?.plan_id!==exact.plan.plan_id||data.receipt?.plan_sha256!==exact.plan.plan_sha256||typeof data.receipt?.target_root!=='string'||!sameFolder(data.receipt.target_root,exact.plan.target_root)||typeof data.receipt?.actual_workspace_root!=='string'||!sameFolder(data.receipt.actual_workspace_root,exact.plan.target_root)||data.receipt?.status!=='APPLIED'||data.receipt?.binding_applied!==true||data.receipt?.registry_applied!==true)throw localMessage('commerce.project_folder.invalid_response')
      invalidateFolderPlan();folderEdited.current=false;folderPathEdited.current=false;setActiveRoot(data.workspace_root);setFolderMode('existing');setFolderPath(data.workspace_root);setName(data.workspace.name);setTitle(data.workspace.title)
      identity.current=data.workspace.id;setWorkspace(data.workspace);setFile(null);setPath(proposal?.path??'');setText('');setFiles([]);setTrash([]);setGit(null);setStage(null);setSelection([]);setDiff('');setPlan('')
      setNotice('commerce.project_folder.applied');setContextRefresh(value=>value+1);onSelected?.();await loadList()
    }catch(cause){if(folderMounted.current){const receipt=(cause as FolderError)?.folderReceipt;if(receipt)setFolderReceipt(receipt);setError(cause as Error)}}
    finally{if(folderMounted.current){invalidateFolderPlan();setFolderBusy(false)}}
  }
  async function refresh(id: string) {
    const listing = await action(id, 'list_files', { directory: '' })
    const deleted = await action(id, 'trash_list')
    if (identity.current === id) { setFiles(listing.files); setExcluded(listing.excluded); setTrash(deleted.items) }
  }
  async function select(next: Workspace) {
    if(folderBusy)return
    invalidateFolderPlan();identity.current = next.id; setWorkspace(next); setFile(null); setPath(proposal?.path ?? ''); setText(''); setDirectory(''); setGit(null); setStage(null); setSelection([]); setReview(null); setError(''); setNotice(''); setDiff(''); setPlan('')
    setBusy(true)
    try { await refresh(next.id) } catch (e) { setError(e as Error) } finally { setBusy(false) }
  }
  async function read(relative: string) {
    if (!workspace) return
    setBusy(true); setError('')
    try { const data = await action(workspace.id, 'read', { path: relative }); if (identity.current === workspace.id) { setFile(data); setPath(data.path); setText(data.text); setContentView('table'); setTab('files') } }
    catch (e) { setError(e as Error) } finally { setBusy(false) }
  }
  async function execute() {
    if(folderBusy)return
    if(review&&['create','bind'].includes(review.operation)){setReview(null);setAccepted(false);setError(localMessage('commerce.project_folder.old_review'));return}
    if (!review || (review.operation==='delete_trash'&&!accepted) || !workspace || review.workspaceId !== workspace.id) return
    setBusy(true); setError(''); setNotice('')
    const id = review.workspaceId
    try {
      const result = await action(id, review.operation, { ...review.args, confirmation: { confirmed: true, operation: review.operation, workspace_id: id } })
      if (identity.current === id) {
        if (review.operation === 'write' || review.operation === 'move' || review.operation === 'restore' || review.operation === 'resolve') { setFile(result); setPath(result.path); setText(result.text) }
        if (review.operation === 'trash') { setFile(null); setPath(''); setText('') }
        if (review.operation === 'git_stage') setStage({ revision: result.selection_revision, head: result.status.head, paths: result.paths })
        if (review.operation === 'git_commit') setStage(null)
        if (review.operation.startsWith('git_')) setGit(result.status && !Array.isArray(result.status) ? result.status : result)
        await refresh(id)
      }
      setNotice("commerce.operation_completed_by_the_service_result_updated"); setReview(null); setAccepted(false)
    } catch (e) { setError(e as Error) } finally { setBusy(false) }
  }
  async function observeGit() {
    if (!workspace) return
    setBusy(true); setError('')
    try { setGit(await action(workspace.id, 'git_status')) } catch (e) { setError(e as Error) } finally { setBusy(false) }
  }
  const folders = [...new Set(files.flatMap(f => f.path.split('/').slice(0, -1).map((_part, i, parts) => parts.slice(0, i + 1).join('/'))))].sort()
  const visible = files.filter(f => !directory || f.path.startsWith(directory + '/'))
  return <section className={`workspace-manager ${inline ? 'workspace-manager--inline' : ''}`} aria-label={t('commerce.project_and_file_management')}>
    <header><h2>{t('commerce.projects_and_files')}</h2></header>
    <ServiceTabs<'projects'|'files'|'context'> id={uid} label={t('commerce.workspace_sections')} value={area} onChange={setArea} items={[{id:'projects',label:t('commerce.projects')},{id:'files',label:t('commerce.files')},{id:'context',label:t('commerce.context_and_memory')}]} />
    {proposal && <p role="status">{t('commerce.chat_proposal_awaiting_your_review')}</p>}
    {loading && <p role="status">{t('commerce.loading_projects')}</p>}
    {error && <p className="wm-error" role="alert">{errorMessage(error)}</p>}{notice && <p role="status">{errorMessage(notice)}</p>}
    {config && <>
      <label>{t('commerce.managed_project')}<select value={workspace?.id ?? ''} disabled={busy || folderBusy || dirty || Boolean(review) || Boolean(folderPlan)} onChange={e => { const next = workspaces.find(w => w.id === e.target.value); if (next) void select(next) }}><option value="">{t('commerce.select_a_project')}</option>{workspaces.map(w => <option key={w.id} value={w.id}>{w.title} · {w.name}</option>)}</select></label>
      {!workspaces.length && <p>{t('commerce.no_managed_projects_creating_one_does_not_modify_existing_folders')}</p>}
    </>}
    <section role="tabpanel" tabIndex={0} id={`${uid}-panel-projects`} aria-labelledby={`${uid}-tab-projects`} hidden={area !== 'projects'}>
      <fieldset className="wm-folder-selection"><legend>{t('commerce.project_folder.form_title')}</legend>
        <p>{t('commerce.project_folder.global_scope')}</p>
        <p>{t('commerce.project_folder.active')} <code>{activeRoot??t('commerce.project_folder.active_unavailable')}</code></p>
        <div className="wm-folder-modes"><label><input type="radio" name={`${uid}-folder-mode`} checked={folderMode==='existing'} onChange={()=>editFolder(()=>setFolderMode('existing'))} disabled={folderBusy}/>{t('commerce.project_folder.existing')}</label><label><input type="radio" name={`${uid}-folder-mode`} checked={folderMode==='create_child'} onChange={()=>editFolder(()=>setFolderMode('create_child'))} disabled={folderBusy}/>{t('commerce.project_folder.child')}</label></div>
        <p>{t(folderMode==='existing'?'commerce.project_folder.existing_notice':'commerce.project_folder.child_notice')}</p>
        <label htmlFor={`${uid}-folder-path`}>{t('commerce.project_folder.path')}</label><div className="wm-folder-path"><input id={`${uid}-folder-path`} ref={folderInput} value={folderPath} onChange={event=>editFolder(()=>setFolderPath(event.target.value),true)} disabled={folderBusy}/><button type="button" onClick={()=>void browseFolder()} disabled={busy||folderBusy}>{t('commerce.project_folder.browse')}</button></div>
        <div className="wm-folder-names"><label>{t('commerce.folder_name')}<input value={name} onChange={event=>editFolder(()=>setName(event.target.value))} disabled={folderBusy}/></label><label>{t('commerce.project_title')}<input value={title} onChange={event=>editFolder(()=>setTitle(event.target.value))} disabled={folderBusy}/></label></div>
        <button type="button" disabled={busy||folderBusy||loading||dirty||!config||!activeRoot||!folderPath.trim()||(folderMode==='create_child'&&(!name.trim()||!title.trim()))} onClick={event=>{folderOrigin.current=event.currentTarget;void prepareFolder()}}>{t('commerce.project_folder.prepare')}</button>
      </fieldset>
      {workspace && <div className="wm-card"><strong>{workspace.title}</strong><details><summary>{t('commerce.project_location')}</summary><code>{workspace.root}</code></details><button type="button" disabled={busy||folderBusy||dirty||!activeRoot||!config} onClick={event=>{folderOrigin.current=event.currentTarget;void prepareFolder({mode:'existing',path:workspace.root,name:workspace.name,title:workspace.title,expected_workspace_root:activeRoot!})}}>{t('commerce.use_this_project_in_adl')}</button><button type="button" disabled={busy} onClick={()=>{setBusy(true);void refresh(workspace.id).catch(e=>setError(e)).finally(()=>setBusy(false))}}>{t('commerce.refresh_files')}</button></div>}
    </section>
    <section role="tabpanel" tabIndex={0} id={`${uid}-panel-files`} inert={folderBusy} aria-labelledby={`${uid}-tab-files`} hidden={area !== 'files'}>
      {!workspace && <p>{t('commerce.select_a_project_in_projects_to_work_with_its_files')}</p>}
      {workspace && <>
        <ServiceTabs<'files'|'trash'|'git'> id={`${uid}-files`} label={t('commerce.file_areas')} value={tab} onChange={setTab} items={[{id:'files',label:t('commerce.explorer')},{id:'trash',label:t('commerce.trash_198')},{id:'git',label:t('commerce.git_and_github')}]} />
        <section role="tabpanel" tabIndex={0} id={`${uid}-files-panel-files`} aria-labelledby={`${uid}-files-tab-files`} hidden={tab !== 'files'}>
<div className="wm-files"><div className="wm-card"><h3>{t('commerce.explorer')}</h3><label>{t('commerce.folder')}<select value={directory} onChange={e => setDirectory(e.target.value)}><option value="">{t('commerce.entire_project')}</option>{folders.map(folder => <option key={folder}>{folder}</option>)}</select></label>
          <ul>{visible.map(item => <li key={item.path}><button disabled={busy || dirty} onClick={() => void read(item.path)}>{item.path}</button><small>{formatNumber(item.size)} bytes</small></li>)}</ul>
          {!visible.length && <p>{t('commerce.no_files_in_this_folder')}</p>}<details><summary>{t('commerce.excluded_entries',{count:formatNumber(excluded.length)})}</summary>{excluded.map(item => <p key={item.path}>{item.path}: {item.reason}</p>)}</details>
        </div><div className="wm-card"><h3>{file ? t('commerce.edit_file') : t('commerce.create_file')}</h3><label>{t('commerce.relative_path')}<input value={path} readOnly={Boolean(file)} onChange={e => setPath(e.target.value)} /></label>
          {delimiter && <ServiceTabs<'table'|'text'> id={`${uid}-content`} label={t('commerce.csv.views')} value={contentView} onChange={setContentView} items={[{id:'table',label:t('commerce.csv.table')},{id:'text',label:t('commerce.csv.text')}]} />}
          {delimiter && <section role="tabpanel" tabIndex={0} id={`${uid}-content-panel-table`} aria-labelledby={`${uid}-content-tab-table`} hidden={contentView !== 'table'}><CsvTablePreview text={text} delimiter={delimiter}/></section>}
          <section role={delimiter ? 'tabpanel' : undefined} tabIndex={delimiter ? 0 : undefined} id={`${uid}-content-panel-text`} aria-labelledby={delimiter ? `${uid}-content-tab-text` : undefined} hidden={Boolean(delimiter) && contentView !== 'text'}><label>{t('commerce.content')}<textarea rows={12} value={text} onChange={e => setText(e.target.value)} /></label></section>
          {file && <details><summary>{t('commerce.file_review')}</summary><code>{file.sha256}</code></details>}{dirty && <p role="status">{t('commerce.unsaved_edits_save_or_discard_before_switching_file_or_project')}</p>}
          <button disabled={busy || !path} onClick={() => mutate('write', { path, text, expected_sha256: file?.sha256 ?? null }, localMessage('commerce.save_file_review',{path}))}>{t('commerce.review_save')}</button>
          <button disabled={busy} onClick={() => { setFile(null); setPath(''); setText(''); setError('') }}>{t('commerce.discard_edits_new_file')}</button>
          {file && <><label>{t('commerce.destination_to_move_or_rename')}<input value={destination} onChange={e => setDestination(e.target.value)} /></label><button disabled={busy || dirty || !destination} onClick={() => mutate('move', { path: file.path, destination, expected_sha256: file.sha256 }, localMessage('commerce.move_file_review',{path:file.path,destination}))}>{t('commerce.review_move')}</button><button disabled={busy || dirty} onClick={() => mutate('trash', { path: file.path, expected_sha256: file.sha256 }, localMessage('commerce.trash_file_review',{path:file.path}))}>{t('commerce.move_to_trash_213')}</button>{git?.conflicts.includes(file.path) && <button disabled={busy} onClick={() => mutate('resolve', { path: file.path, text, expected_sha256: file.sha256 }, localMessage('commerce.resolve_file_review',{path:file.path}))}>{t('commerce.review_conflict_resolution')}</button>}</>}
        </div></div>
        </section>
        <section role="tabpanel" tabIndex={0} id={`${uid}-files-panel-trash`} aria-labelledby={`${uid}-files-tab-trash`} hidden={tab !== 'trash'}>
<div className="wm-card"><h3>{t('commerce.project_trash')}</h3>{!trash.length && <p>{t('commerce.trash_is_empty')}</p>}{trash.map(item => <article key={item.trash_id}><p>{item.path} {t('commerce.integrity',{status:item.integrity})}{item.recovery_required ? t('commerce.recovery_required') : ''}</p><button disabled={busy || dirty || item.integrity !== 'PASS'} onClick={() => mutate('restore', { trash_id: item.trash_id, expected_revision: item.revision }, localMessage('commerce.restore_file_review',{path:item.path}))}>{t('commerce.restore_218')}</button><button disabled={busy || item.integrity !== 'PASS'} onClick={() => mutate('delete_trash', { trash_id: item.trash_id, expected_revision: item.revision }, localMessage('commerce.delete_file_review',{path:item.path}))}>{t('commerce.permanently_delete')}</button></article>)}</div>
        </section>
        <section role="tabpanel" tabIndex={0} id={`${uid}-files-panel-git`} aria-labelledby={`${uid}-files-tab-git`} hidden={tab !== 'git'}>
<div className="wm-card"><h3>{t('commerce.local_git')}</h3><p>{t('commerce.this_project_only_no_remote_changes')}</p><button disabled={busy} onClick={() => mutate('git_init', {}, localMessage('commerce.initialize_a_new_local_repository_without_a_remote'))}>{t('commerce.initialize_git')}</button><button disabled={busy} onClick={() => void observeGit()}>{t('commerce.read_git_status')}</button>
          {git && <><p>{t('commerce.branch')} {git.branch} · HEAD <code>{git.head ?? t('commerce.no_commits')}</code></p><pre>{git.status.join('\n') || t('commerce.no_changes')}</pre>{git.conflicts.length > 0 && <p role="alert">{t('commerce.conflicts')} {git.conflicts.join(', ')}{t('commerce.read_the_file_and_propose_explicit_text_there_is_no_automatic_resolution')}</p>}
            <fieldset disabled={busy}><legend>{t('commerce.files_for_the_next_commit')}</legend>{files.map(item => <label className="wm-check" key={item.path}><input type="checkbox" checked={selection.includes(item.path)} onChange={e => setSelection(old => e.target.checked ? [...old, item.path] : old.filter(p => p !== item.path))} />{item.path}</label>)}</fieldset>
            <button disabled={busy || !selection.length} onClick={() => { setBusy(true); void action(workspace.id, 'git_diff', { paths: selection }).then(result => setDiff(result.diff)).catch(e => setError(e)).finally(() => setBusy(false)) }}>{t('commerce.view_selected_diff')}</button><pre>{diff}</pre>
            <button disabled={busy || dirty || Boolean(stage) || !selection.length} onClick={() => mutate('git_stage', { paths: selection, expected_head: git.head, expected_hashes: Object.fromEntries(files.filter(f => selection.includes(f.path)).map(f => [f.path, f.sha256])) }, localMessage('commerce.stage_review',{paths:selection.join(', '),get head(){return git.head??t('commerce.empty')}}))}>{t('commerce.review_staging')}</button>
            <p>{t('commerce.staged_selection')} {stage?.paths.join(', ') ?? t('commerce.none')}</p><label>{t('commerce.commit_message')}<input value={message} onChange={e => setMessage(e.target.value)} /></label><button disabled={busy || dirty || !stage || !message} onClick={() => mutate('git_commit', { message, expected_head: stage?.head, selection_revision: stage?.revision }, localMessage('commerce.commit_review',{paths:stage?.paths.join(', ')??''}))}>{t('commerce.review_commit')}</button>
            <label>{t('commerce.new_branch')}<input value={branch} onChange={e => setBranch(e.target.value)} /></label><button disabled={busy || !git.head || !branch} onClick={() => mutate('git_branch', { name: branch, expected_head: git.head }, localMessage('commerce.branch_review',{branch}))}>{t('commerce.review_branch')}</button>
          </>}
          <h3>{t('commerce.github_plans')}</h3><p>{t('commerce.proposed_no_external_operations_are_executed')}</p><label>{t('commerce.owner_repo_repository')}<input value={repo} onChange={e => setRepo(e.target.value)} /></label><label>{t('commerce.plan')}<select value={planKind} onChange={e => setPlanKind(e.target.value)}><option value="repo_create">{t('commerce.create_repository')}</option><option value="pr_create">{t('commerce.create_pr')}</option><option value="pr_merge">{t('commerce.merge_pr')}</option><option value="conflict_review">{t('commerce.review_conflicts')}</option></select></label><button disabled={busy || !repo} onClick={() => { setBusy(true); void action(workspace.id, 'remote_plan', { kind: planKind, repo, base: 'main', head: git?.branch ?? '', title: message }).then(data => setPlan(JSON.stringify(data, null, 2))).catch(e => setError(e)).finally(() => setBusy(false)) }}>{t('commerce.prepare_plan_without_executing')}</button><pre>{plan}</pre>
        </div>
        </section>
      </>}
    </section>
    <section role="tabpanel" tabIndex={0} id={`${uid}-panel-context`} aria-labelledby={`${uid}-tab-context`} hidden={area !== 'context'}>
      {(typeof contextPanel==='function'?contextPanel({openProjectSelection,refreshKey:contextRefresh+refreshKey}):contextPanel) ?? (workspace ? <div className="wm-card"><h3>{t('commerce.project_documents')}</h3>{workspace.context_files.map(item=><p key={item.path}><button disabled={busy || dirty} onClick={()=>{setArea('files');void read(item.path)}}>{item.path}</button></p>)}</div> : <p>{t('commerce.select_a_project_to_read_its_context')}</p>)}
    </section>
    {folderPlan && <section className="wm-review wm-folder-review" onKeyDown={reviewKeyboard} role="dialog" aria-modal="true" aria-label={t('commerce.review_workspace_operation')}>
      <h3 ref={folderHeading} tabIndex={-1}>{t('commerce.project_folder.plan_title')}</h3><p>{t('commerce.project_folder.readonly_notice')}</p>
      <dl><div><dt>{t('commerce.project_folder.target')}</dt><dd><code>{folderPlan.plan.target_root}</code></dd></div><div><dt>{t('commerce.folder_name')}</dt><dd>{folderPlan.plan.name}</dd></div><div><dt>{t('commerce.project_title')}</dt><dd>{folderPlan.plan.title}</dd></div><div><dt>{t('commerce.project_folder.binding')}</dt><dd><code>{folderPlan.plan.expected_workspace_root}</code></dd></div><div><dt>{t('commerce.project_folder.expires')}</dt><dd><time dateTime={folderPlan.plan.expires_at}>{folderPlan.plan.expires_at}</time></dd></div></dl>
      <h4 id={`${uid}-plan-files`}>{t('commerce.project_folder.files')}</h4><ul className="wm-folder-plan-files" aria-labelledby={`${uid}-plan-files`}>{folderPlan.plan.files.map(entry=><li key={entry.path}><code>{entry.path}</code><span>{t(entry.action==='create'?'commerce.project_folder.create':'commerce.project_folder.preserve')}</span></li>)}</ul>
      <details className="wm-folder-directories"><summary>{t('commerce.project_folder.directories')} ({formatNumber(folderPlan.plan.directories.length)})</summary><ul>{folderPlan.plan.directories.map(entry=><li key={entry.path}><code>{entry.path}</code> · {t(entry.action==='create'?'commerce.project_folder.create':'commerce.project_folder.preserve')}</li>)}</ul></details>
      <details><summary>{t('commerce.operation_details')}</summary><code>{folderPlan.plan.plan_id}</code><code>{folderPlan.plan.plan_sha256}</code></details>
      <div className="wm-folder-review-actions">
      <button type="button" disabled={folderBusy||busy||loading||dirty||folderPlan.revision!==folderRevision.current} onClick={()=>void applyFolder()}>{t('agents.TaskExecution.accept')}</button>
      <button type="button" disabled={folderBusy} onClick={cancelFolderReview}>{t('commerce.cancel')}</button></div>
    </section>}
    {folderReceipt && <details className="wm-folder-receipt"><summary>{t('commerce.project_folder.receipt')}</summary><pre>{JSON.stringify(folderReceipt,null,2)}</pre></details>}
    {review && !['create','bind'].includes(review.operation) && <section className="wm-review" role="dialog" aria-modal="true" aria-label={t('commerce.review_workspace_operation')}><h3>{t('commerce.review_operation')}</h3><p>{errorMessage(review.label)}</p><p>{t('commerce.project')} <code>{workspace?.root ?? review.workspaceId}</code></p><details><summary>{t('commerce.operation_details')}</summary><code>{review.workspaceId}</code><pre>{JSON.stringify(review.args, null, 2)}</pre></details>{review.operation==='delete_trash'&&<label className="wm-check"><input type="checkbox" checked={accepted} onChange={e => setAccepted(e.target.checked)} />{t('commerce.i_reviewed_the_scope_and_confirm_this_operation')}</label>}<button disabled={busy || folderBusy || (review.operation==='delete_trash'&&!accepted) || review.workspaceId !== workspace?.id} onClick={() => void execute()}>{review.operation==='delete_trash'?t('commerce.confirm_and_execute'):t('agents.TaskExecution.accept')}</button><button disabled={busy} onClick={() => { setReview(null); setAccepted(false) }}>{t('commerce.cancel')}</button></section>}
  </section>
}
