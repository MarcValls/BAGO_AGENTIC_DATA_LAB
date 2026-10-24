import {t, useI18n, formatNumber, apiError, errorMessage, localMessage} from '../i18n'
import { useEffect, useId, useRef, useState } from 'react'
import type {ReactNode} from 'react'
import ServiceTabs from './ServiceTabs'
import './WorkspaceManager.css'

type Workspace = { id: string; root: string; name: string; title: string; context_files: Array<{ path: string; sha256: string }> }
type FileRecord = { path: string; sha256: string; size: number; text?: string }
type Trash = { trash_id: string; path: string; sha256: string; revision: string; integrity: string; recovery_required: boolean }
type Git = { head: string | null; branch: string; status: string[]; conflicts: string[] }
type Review = { workspaceId: string; operation: string; args: Record<string, unknown>; label: string|Error }

async function request(path: string, body?: unknown) {
  const response = await fetch(path, body === undefined ? undefined : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
  const data = await response.json()
  if (!response.ok) throw apiError(data,response.status,'commerce')
  return data
}

export type WorkspaceProposal = { intent: 'manage' | 'create' | 'open' | 'files' | 'git'; name?: string; path?: string }
export default function WorkspaceManager({ inline = false, onSelected, proposal, contextPanel }: { inline?: boolean; onSelected?: () => void; proposal?: WorkspaceProposal; contextPanel?:ReactNode }) {
  useI18n()

  const uid=useId()
  const [area,setArea]=useState<'projects'|'files'|'context'>(proposal?.intent==='files'||proposal?.intent==='git'?'files':'projects')
  const [config, setConfig] = useState<{ configured: boolean; parent: string | null } | null>(null)
  const [workspaces, setWorkspaces] = useState<Workspace[]>([])
  const [workspace, setWorkspace] = useState<Workspace | null>(null)
  const identity = useRef<string | null>(null)
  const [name, setName] = useState(''), [title, setTitle] = useState('')
  const [files, setFiles] = useState<FileRecord[]>([]), [excluded, setExcluded] = useState<Array<{ path: string; reason: string }>>([])
  const [directory, setDirectory] = useState(''), [path, setPath] = useState(''), [text, setText] = useState(''), [destination, setDestination] = useState('')
  const [file, setFile] = useState<FileRecord | null>(null), [trash, setTrash] = useState<Trash[]>([])
  const [tab, setTab] = useState<'files' | 'trash' | 'git'>('files')
  const [git, setGit] = useState<Git | null>(null), [selection, setSelection] = useState<string[]>([]), [stage, setStage] = useState<{ revision: string; head: string | null; paths: string[] } | null>(null)
  const [message, setMessage] = useState(''), [branch, setBranch] = useState(''), [diff, setDiff] = useState('')
  const [repo, setRepo] = useState(''), [planKind, setPlanKind] = useState('pr_create'), [plan, setPlan] = useState('')
  const [review, setReview] = useState<Review | null>(null), [accepted, setAccepted] = useState(false)
  const [busy, setBusy] = useState(false), [loading, setLoading] = useState(true), [error, setError] = useState<string|Error>(''), [notice, setNotice] = useState('')
  const dirty = Boolean(workspace) && (file ? text !== file.text || path !== file.path : Boolean(text || path))
  useEffect(() => { if (proposal?.name) setName(proposal.name); if (proposal?.path) setPath(proposal.path); if (proposal?.intent === 'git') {setTab('git');setArea('files')};if(proposal?.intent==='files')setArea('files') }, [proposal])
  const mutate = (operation: string, args: Record<string, unknown>, label: string|Error) => {
    if (!workspace) return
    setAccepted(false); setReview({ workspaceId: workspace.id, operation, args, label }); setError('')
  }
  const action = (id: string, operation: string, args: Record<string, unknown> = {}) => request(`/api/workspaces/v1/workspaces/${id}/actions`, { operation, ...args })
  async function loadList() {
    const data = await request('/api/workspaces/v1/workspaces')
    setWorkspaces(data.workspaces)
  }
  useEffect(() => { let current = true
    request('/api/workspaces/v1/config').then(async data => {
      if (!current) return
      setConfig(data)
      if (data.configured) await loadList()
    }).catch(e => { if (current) setError(e instanceof Error ? e : String(e)) }).finally(() => { if (current) setLoading(false) })
    return () => { current = false }
  }, [])
  async function refresh(id: string) {
    const listing = await action(id, 'list_files', { directory: '' })
    const deleted = await action(id, 'trash_list')
    if (identity.current === id) { setFiles(listing.files); setExcluded(listing.excluded); setTrash(deleted.items) }
  }
  async function select(next: Workspace) {
    identity.current = next.id; setWorkspace(next); setFile(null); setPath(proposal?.path ?? ''); setText(''); setDirectory(''); setGit(null); setStage(null); setSelection([]); setReview(null); setError(''); setNotice(''); setDiff(''); setPlan('')
    setBusy(true)
    try { await refresh(next.id) } catch (e) { setError(e as Error) } finally { setBusy(false) }
  }
  async function read(relative: string) {
    if (!workspace) return
    setBusy(true); setError('')
    try { const data = await action(workspace.id, 'read', { path: relative }); if (identity.current === workspace.id) { setFile(data); setPath(data.path); setText(data.text); setTab('files') } }
    catch (e) { setError(e as Error) } finally { setBusy(false) }
  }
  async function execute() {
    if (!review || !accepted || (review.operation !== 'create' && (!workspace || review.workspaceId !== workspace.id))) return
    setBusy(true); setError(''); setNotice('')
    const id = review.workspaceId
    try {
      const result = review.operation === 'create' ? await request('/api/workspaces/v1/workspaces', review.args)
        : review.operation === 'bind' ? await request('/api/workspace/select', { path: workspace!.root })
        : await action(id, review.operation, { ...review.args, confirmation: { confirmed: true, operation: review.operation, workspace_id: id } })
      if (review.operation === 'create') { await loadList(); await select(result) }
      else if (identity.current === id) {
        if (review.operation === 'write' || review.operation === 'move' || review.operation === 'restore' || review.operation === 'resolve') { setFile(result); setPath(result.path); setText(result.text) }
        if (review.operation === 'trash') { setFile(null); setPath(''); setText('') }
        if (review.operation === 'git_stage') setStage({ revision: result.selection_revision, head: result.status.head, paths: result.paths })
        if (review.operation === 'git_commit') setStage(null)
        if (review.operation.startsWith('git_')) setGit(result.status && !Array.isArray(result.status) ? result.status : result)
        if (review.operation === 'bind') onSelected?.()
        await refresh(id)
      }
      setNotice(review.operation === 'bind' ? "commerce.project_selected_in_adl_reading_and_editing_permissions_remain_explicit" : "commerce.operation_completed_by_the_service_result_updated"); setReview(null); setAccepted(false)
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
    {config?.configured && <>
      <label>{t('commerce.managed_project')}<select value={workspace?.id ?? ''} disabled={busy || dirty || Boolean(review)} onChange={e => { const next = workspaces.find(w => w.id === e.target.value); if (next) void select(next) }}><option value="">{t('commerce.select_a_project')}</option>{workspaces.map(w => <option key={w.id} value={w.id}>{w.title} · {w.name}</option>)}</select></label>
      {!workspaces.length && <p>{t('commerce.no_managed_projects_creating_one_does_not_modify_existing_folders')}</p>}
    </>}
    <section role="tabpanel" tabIndex={0} id={`${uid}-panel-projects`} aria-labelledby={`${uid}-tab-projects`} hidden={area !== 'projects'}>
      {config && !config.configured && <div className="wm-card"><h3>{t('commerce.parent_folder_not_configured')}</h3><p>{t('commerce.ask_the_administrator_to_configure_the_projects_folder_see_the_manual')}</p></div>}
      {config?.configured && <>
      <details><summary>{t('commerce.projects_folder_details')}</summary><p>{t('commerce.allowed_root')} <code>{config.parent}</code></p></details>
      <fieldset disabled={busy}><legend>{t('commerce.create_a_project')}</legend><label>{t('commerce.folder_name')}<input value={name} onChange={e => setName(e.target.value)} /></label><label>{t('commerce.project_title')}<input value={title} onChange={e => setTitle(e.target.value)} /></label>
        <button disabled={!name || !title || dirty} onClick={() => { setAccepted(false); setReview({ workspaceId: workspace?.id ?? '__new__', operation: 'create', args: { name, title, confirmed: true }, label: localMessage('commerce.create_project_review',{name,parent:config.parent}) }) }}>{t('commerce.review_creation')}</button>
      </fieldset>
      {workspace && <>
        <div className="wm-card"><strong>{workspace.title}</strong><details><summary>{t('commerce.project_location')}</summary><code>{workspace.root}</code></details><button disabled={busy} onClick={() => mutate('bind', {}, localMessage('commerce.bind_project_review',{root:workspace.root}))}>{t('commerce.use_this_project_in_adl')}</button><button disabled={busy} onClick={() => { setBusy(true); void refresh(workspace.id).catch(e => setError(e)).finally(() => setBusy(false)) }}>{t('commerce.refresh_files')}</button></div>
      </>}
      </>}
    </section>
    <section role="tabpanel" tabIndex={0} id={`${uid}-panel-files`} aria-labelledby={`${uid}-tab-files`} hidden={area !== 'files'}>
      {!workspace && <p>{t('commerce.select_a_project_in_projects_to_work_with_its_files')}</p>}
      {workspace && <>
        <ServiceTabs<'files'|'trash'|'git'> id={`${uid}-files`} label={t('commerce.file_areas')} value={tab} onChange={setTab} items={[{id:'files',label:t('commerce.explorer')},{id:'trash',label:t('commerce.trash_198')},{id:'git',label:t('commerce.git_and_github')}]} />
        <section role="tabpanel" tabIndex={0} id={`${uid}-files-panel-files`} aria-labelledby={`${uid}-files-tab-files`} hidden={tab !== 'files'}>
<div className="wm-files"><div className="wm-card"><h3>{t('commerce.explorer')}</h3><label>{t('commerce.folder')}<select value={directory} onChange={e => setDirectory(e.target.value)}><option value="">{t('commerce.entire_project')}</option>{folders.map(folder => <option key={folder}>{folder}</option>)}</select></label>
          <ul>{visible.map(item => <li key={item.path}><button disabled={busy || dirty} onClick={() => void read(item.path)}>{item.path}</button><small>{formatNumber(item.size)} bytes</small></li>)}</ul>
          {!visible.length && <p>{t('commerce.no_files_in_this_folder')}</p>}<details><summary>{t('commerce.excluded_entries',{count:formatNumber(excluded.length)})}</summary>{excluded.map(item => <p key={item.path}>{item.path}: {item.reason}</p>)}</details>
        </div><div className="wm-card"><h3>{file ? t('commerce.edit_file') : t('commerce.create_file')}</h3><label>{t('commerce.relative_path')}<input value={path} readOnly={Boolean(file)} onChange={e => setPath(e.target.value)} /></label><label>{t('commerce.content')}<textarea rows={12} value={text} onChange={e => setText(e.target.value)} /></label>
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
      {contextPanel ?? (workspace ? <div className="wm-card"><h3>{t('commerce.project_documents')}</h3>{workspace.context_files.map(item=><p key={item.path}><button disabled={busy || dirty} onClick={()=>{setArea('files');void read(item.path)}}>{item.path}</button></p>)}</div> : <p>{t('commerce.select_a_project_to_read_its_context')}</p>)}
    </section>
    {review && <section className="wm-review" role="dialog" aria-modal="true" aria-label={t('commerce.review_workspace_operation')}><h3>{t('commerce.review_operation')}</h3><p>{errorMessage(review.label)}</p><p>{t('commerce.project')} <code>{review.operation === 'create' ? `${config?.parent}/${String(review.args.name)}` : workspace?.root ?? review.workspaceId}</code></p><details><summary>{t('commerce.operation_details')}</summary><code>{review.workspaceId}</code><pre>{JSON.stringify(review.args, null, 2)}</pre></details><label className="wm-check"><input type="checkbox" checked={accepted} onChange={e => setAccepted(e.target.checked)} />{t('commerce.i_reviewed_the_scope_and_confirm_this_operation')}</label><button disabled={busy || !accepted || (review.operation !== 'create' && review.workspaceId !== workspace?.id)} onClick={() => void execute()}>{t('commerce.confirm_and_execute')}</button><button disabled={busy} onClick={() => { setReview(null); setAccepted(false) }}>{t('commerce.cancel')}</button></section>}
  </section>
}
