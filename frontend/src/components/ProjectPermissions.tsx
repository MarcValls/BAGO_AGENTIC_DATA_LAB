import {useCallback, useEffect, useId, useRef, useState, type ReactNode} from 'react'
import {createPortal} from 'react-dom'
import ProjectPermissionTree from './ProjectPermissionTree'
import {isDirectoryListing, isProjectPermissionSnapshot, type ProjectPermissionSnapshot, type ProjectTreeEntry} from '../types/projectPermissions'
import './ProjectPermissions.css'

type Props = {projectId: string | null; projectRoot: string | null; refreshKey?: string | number; disabled?: boolean; onBrowseWorkspace?: () => void; workspaceContent?: ReactNode}
type ViewState = 'loading' | 'ready' | 'error' | 'unknown'

export default function ProjectPermissions({projectId, projectRoot, refreshKey = 0, disabled = false, onBrowseWorkspace, workspaceContent}: Props) {
  const [snapshot, setSnapshot] = useState<ProjectPermissionSnapshot | null>(null)
  const [state, setState] = useState<ViewState>('loading')
  const [error, setError] = useState('')
  const [open, setOpen] = useState(false)
  const [entriesByDirectory, setEntriesByDirectory] = useState<Record<string, ProjectTreeEntry[]>>({})
  const [loadingDirectories, setLoadingDirectories] = useState<string[]>([])
  const [truncatedDirectories, setTruncatedDirectories] = useState<string[]>([])
  const [expandedDirectories, setExpandedDirectories] = useState<string[]>([])
  const [readDirectories, setReadDirectories] = useState<string[]>([])
  const [writeDirectories, setWriteDirectories] = useState<string[]>([])
  const [confirmed, setConfirmed] = useState(false)
  const [busy, setBusy] = useState(false)
  const generation = useRef(0)
  const opener = useRef<HTMLButtonElement>(null)
  const closeButton = useRef<HTMLButtonElement>(null)
  const dialog = useRef<HTMLElement>(null)
  const treeRevision = useRef('')
  const dialogId = useId()
  const titleId = useId()

  const load = useCallback(async () => {
    const request = ++generation.current
    setState('loading'); setError(''); setConfirmed(false); setSnapshot(null); setReadDirectories([]); setWriteDirectories([]); setEntriesByDirectory({}); setExpandedDirectories([]); setTruncatedDirectories([]); treeRevision.current = ''
    if (!projectId || !projectRoot) { setSnapshot(null); setState('unknown'); return }
    try {
      const response = await fetch('/api/project-permissions')
      if (!response.ok) throw new Error(`No se pudieron cargar los permisos (${response.status}).`)
      const value: unknown = await response.json()
      if (!isProjectPermissionSnapshot(value)) throw new Error('La respuesta de permisos tiene un formato desconocido.')
      if (request !== generation.current) return
      if (value.project_id !== projectId || value.root !== projectRoot) { setSnapshot(null); setState('unknown'); return }
      setSnapshot(value); setReadDirectories(value.read_directories); setWriteDirectories(value.write_directories)
      setState('ready')
    } catch (cause) {
      if (request !== generation.current) return
      setSnapshot(null); setState('error'); setError(cause instanceof Error ? cause.message : 'No se pudieron cargar los permisos.')
    }
  }, [projectId, projectRoot])

  useEffect(() => { void load(); return () => { generation.current++ } }, [load, refreshKey])

  const loadDirectory = useCallback(async (target: string) => {
    if (!snapshot || !projectId || snapshot.revision === null) return
    setLoadingDirectories(current => [...new Set([...current, target])]); setError('')
    try {
      const response = await fetch('/api/project-permissions/directories', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({expected_project_id: projectId, expected_binding: snapshot.binding, expected_revision: snapshot.revision, directory: target})})
      if (!response.ok) throw new Error(`No se pudo consultar el contenido de la carpeta (${response.status}).`)
      const value: unknown = await response.json()
      if (!isDirectoryListing(value) || value.project_id !== projectId || value.root !== snapshot.root || value.revision !== snapshot.revision || value.directory !== target || JSON.stringify(value.binding) !== JSON.stringify(snapshot.binding)) throw new Error('La carpeta activa cambió. Actualiza los permisos antes de continuar.')
      const nextEntries = value.entries ?? [...value.directories.map(item => ({...item, kind: 'directory' as const})), ...(value.files ?? []).map(item => ({...item, kind: 'file' as const}))]
      setEntriesByDirectory(current => ({...current, [target]: nextEntries}))
      setTruncatedDirectories(current => value.truncated ? [...new Set([...current, target])] : current.filter(path => path !== target))
      return nextEntries
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'No se pudo consultar el contenido de la carpeta.'); return [] }
    finally { setLoadingDirectories(current => current.filter(path => path !== target)) }
  }, [projectId, snapshot])

  useEffect(() => {
    if (!open || state !== 'ready' || !snapshot || snapshot.revision === null) return
    const key = `${projectId}:${snapshot.revision}`
    if (treeRevision.current === key) return
    treeRevision.current = key
    void loadDirectory('.')
  }, [open, state, snapshot, projectId, loadDirectory])

  const toggleDirectory = useCallback((target: string) => {
    const expanded = expandedDirectories.includes(target)
    setExpandedDirectories(current => expanded ? current.filter(path => path !== target) : [...current, target])
    if (!expanded && !Object.prototype.hasOwnProperty.call(entriesByDirectory, target)) void loadDirectory(target)
  }, [entriesByDirectory, expandedDirectories, loadDirectory])

  useEffect(() => {
    if (open) closeButton.current?.focus()
    else opener.current?.focus()
  }, [open])

  useEffect(() => {
    if (!open) return
    const keyboard = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { event.preventDefault(); setOpen(false); return }
      if (event.key !== 'Tab' || !dialog.current) return
      const controls = Array.from(dialog.current.querySelectorAll<HTMLElement>('button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex]:not([tabindex="-1"])'))
      if (!controls.length) { event.preventDefault(); return }
      const first = controls[0], last = controls[controls.length - 1]
      if (event.shiftKey && (document.activeElement === first || !dialog.current.contains(document.activeElement))) { event.preventDefault(); last.focus() }
      else if (!event.shiftKey && (document.activeElement === last || !dialog.current.contains(document.activeElement))) { event.preventDefault(); first.focus() }
    }
    document.addEventListener('keydown', keyboard)
    return () => document.removeEventListener('keydown', keyboard)
  }, [open])

  function toggle(kind: 'read' | 'write', path: string, enabled: boolean) {
    const update = (paths: string[]) => {
      if (!enabled) return paths.filter(item => item !== path)
      const prefix = path === '.' ? '' : `${path}/`
      return [...new Set([...paths.filter(item => item !== path && !(path === '.' ? item !== '.' : item.startsWith(prefix))), path])].sort((a,b) => a.localeCompare(b))
    }
    if (kind === 'read') setReadDirectories(update); else setWriteDirectories(update)
    setConfirmed(false)
  }

  async function save() {
    if (!snapshot || !projectId || snapshot.revision === null || !confirmed || busy || disabled) return
    setBusy(true); setError('')
    try {
      const response = await fetch('/api/project-permissions', {method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({expected_project_id: projectId, expected_binding: snapshot.binding, expected_revision: snapshot.revision, read_directories: readDirectories, write_directories: writeDirectories, confirmed: true})})
      if (!response.ok) throw new Error(`No se pudieron guardar los permisos (${response.status}).`)
      const value: unknown = await response.json()
      if (!isProjectPermissionSnapshot(value) || value.project_id !== projectId || value.root !== projectRoot) throw new Error('El servidor no confirmó los permisos del proyecto seleccionado.')
      setSnapshot(value); setReadDirectories(value.read_directories); setWriteDirectories(value.write_directories); setConfirmed(false); setState('ready'); setEntriesByDirectory({}); setExpandedDirectories([]); setTruncatedDirectories([]); treeRevision.current = ''
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'No se pudieron guardar los permisos.'); setConfirmed(false); await load() }
    finally { setBusy(false) }
  }

  async function revoke() {
    if (!snapshot || !projectId || snapshot.revision === null || !confirmed || busy || disabled) return
    setBusy(true); setError('')
    try {
      const response = await fetch('/api/project-permissions', {method: 'DELETE', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({expected_project_id: projectId, expected_binding: snapshot.binding, expected_revision: snapshot.revision, confirmed: true})})
      if (!response.ok) throw new Error(`No se pudieron revocar los permisos (${response.status}).`)
      const value: unknown = await response.json()
      if (!isProjectPermissionSnapshot(value) || value.project_id !== projectId || value.root !== projectRoot) throw new Error('El servidor no confirmó la revocación para este proyecto.')
      setSnapshot(value); setReadDirectories([]); setWriteDirectories([]); setConfirmed(false); setEntriesByDirectory({}); setExpandedDirectories([]); setTruncatedDirectories([]); treeRevision.current = ''
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'No se pudieron revocar los permisos.'); setConfirmed(false); await load() }
    finally { setBusy(false) }
  }

  const configured = snapshot?.state === 'configured' || snapshot?.state === 'active'
  const hasScopes = readDirectories.length > 0 || writeDirectories.length > 0

  return <>
    <section className="project-permissions" aria-label="Permisos del proyecto" aria-busy={state === 'loading' || busy}>
      <div className="project-permissions__summary">
        <div className="project-permissions__workspace-summary"><strong>Directorio de trabajo:</strong><code>{snapshot?.root ?? projectRoot ?? 'Sin carpeta seleccionada'}</code>{onBrowseWorkspace && <button type="button" onClick={onBrowseWorkspace} aria-label="Examinar carpeta de trabajo">Examinar</button>}</div>
        <div className="project-permissions__summary-actions">
          <button ref={opener} type="button" onClick={() => setOpen(true)} disabled={disabled} aria-haspopup="dialog" aria-expanded={open} aria-controls={dialogId}>Administrar acceso</button>
        </div>
      </div>
    </section>
    {open && createPortal(<div className="project-permissions__backdrop" onMouseDown={event => { if (event.target === event.currentTarget) setOpen(false) }}>
      <section ref={dialog} id={dialogId} role="dialog" aria-modal="true" aria-labelledby={titleId} className="project-permissions__dialog" onMouseDown={event => event.stopPropagation()}>
        <header className="project-permissions__dialog-header"><div><h2 id={titleId}>Permisos del proyecto</h2><code>{snapshot?.root ?? projectRoot ?? 'Directorio desconocido'}</code></div><button ref={closeButton} type="button" onClick={() => setOpen(false)}>Cerrar</button></header>
        <div className={`project-permissions__dialog-body${workspaceContent ? ' project-permissions__dialog-body--with-agent-tools' : ''}`}>
          <section aria-label="Permisos del proyecto" className="project-permissions__section">
            <h3>Permisos del proyecto</h3>
            <p>Estos permisos se guardan en el proyecto y se conservan entre conversaciones. Leer carpetas incluye su contenido; escribir no aplica planes automáticamente.</p>
            {state === 'loading' && <p role="status">Cargando permisos guardados.</p>}
            {state === 'unknown' && <p role="status">No se puede confirmar el proyecto o su política. No se ha concedido acceso.</p>}
            {state === 'error' && <p role="alert">{error || 'Estado de permisos desconocido.'}</p>}
            {state === 'ready' && snapshot && <>
              {snapshot.state === 'revoked' && <p className="project-permissions__revoked" role="status">Permisos revocados para este proyecto. Puedes definir una nueva política en el árbol.</p>}
              {!configured && snapshot.state !== 'revoked' && snapshot.state !== 'unconfigured' && <p role="status">Estado de permisos: {snapshot.state}. No se presupone acceso.</p>}
              <div className="project-permissions__scope-list" aria-label="Alcances guardados">
                <div><strong>Lectura</strong><div className="project-permissions__scope-items">{readDirectories.length ? readDirectories.map(path=><span className="project-permissions__scope" key={`read:${path}`}><code>{path}</code><button type="button" aria-label={`Quitar lectura en ${path}`} disabled={busy || disabled} onClick={()=>toggle('read',path,false)}>Quitar</button></span>) : <span>Sin accesos</span>}</div></div>
                <div><strong>Escritura</strong><div className="project-permissions__scope-items">{writeDirectories.length ? writeDirectories.map(path=><span className="project-permissions__scope" key={`write:${path}`}><code>{path}</code><button type="button" aria-label={`Quitar escritura en ${path}`} disabled={busy || disabled} onClick={()=>toggle('write',path,false)}>Quitar</button></span>) : <span>Sin accesos</span>}</div></div>
              </div>
              <ProjectPermissionTree entriesByDirectory={entriesByDirectory} loadingDirectories={loadingDirectories} truncatedDirectories={truncatedDirectories} expandedDirectories={expandedDirectories} readDirectories={readDirectories} writeDirectories={writeDirectories} onToggleDirectory={toggleDirectory} onToggle={toggle}/>
              {error && <p role="alert">{error}</p>}
              <label className="project-permissions__confirm"><input type="checkbox" checked={confirmed} disabled={busy || disabled || snapshot.revision === null} onChange={event => setConfirmed(event.target.checked)}/><span>He revisado este alcance y confirmo los permisos del proyecto.</span></label>
              <div className="project-permissions__actions"><button type="button" onClick={() => void save()} disabled={snapshot.revision === null || !confirmed || busy || disabled}>Guardar permisos</button><button type="button" onClick={() => void revoke()} disabled={!configured || !hasScopes || !confirmed || busy || disabled}>Revocar permisos</button></div>
            </>}
          </section>
          {workspaceContent && <section aria-label="Herramientas de trabajo del agente" className="project-permissions__section project-permissions__workspace">{workspaceContent}</section>}
        </div>
      </section>
    </div>, document.body)}
  </>
}
