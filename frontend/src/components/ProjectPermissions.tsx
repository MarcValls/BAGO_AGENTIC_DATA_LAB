import {useCallback, useEffect, useRef, useState} from 'react'
import ProjectPermissionTree from './ProjectPermissionTree'
import {isDirectoryListing, isProjectPermissionSnapshot, type ProjectPermissionSnapshot} from '../types/projectPermissions'
import './ProjectPermissions.css'

type Props = {projectId: string | null; projectRoot: string | null; refreshKey?: string | number; disabled?: boolean}
type ViewState = 'loading' | 'ready' | 'error' | 'unknown'

export default function ProjectPermissions({projectId, projectRoot, refreshKey = 0, disabled = false}: Props) {
  const [snapshot, setSnapshot] = useState<ProjectPermissionSnapshot | null>(null)
  const [state, setState] = useState<ViewState>('loading')
  const [error, setError] = useState('')
  const [directory, setDirectory] = useState('.')
  const [directories, setDirectories] = useState<Array<{name: string; path: string}>>([])
  const [treeLoading, setTreeLoading] = useState(false)
  const [treeTruncated, setTreeTruncated] = useState(false)
  const [readDirectories, setReadDirectories] = useState<string[]>([])
  const [writeDirectories, setWriteDirectories] = useState<string[]>([])
  const [confirmed, setConfirmed] = useState(false)
  const [busy, setBusy] = useState(false)
  const generation = useRef(0)

  const load = useCallback(async () => {
    const request = ++generation.current
    setState('loading'); setError(''); setConfirmed(false)
    if (!projectId || !projectRoot) { setSnapshot(null); setState('unknown'); return }
    try {
      const response = await fetch('/api/project-permissions')
      if (!response.ok) throw new Error(`No se pudieron cargar los permisos (${response.status}).`)
      const value: unknown = await response.json()
      if (!isProjectPermissionSnapshot(value)) throw new Error('La respuesta de permisos tiene un formato desconocido.')
      if (request !== generation.current) return
      if (value.project_id !== projectId || value.root !== projectRoot) { setSnapshot(null); setState('unknown'); return }
      setSnapshot(value); setReadDirectories(value.read_directories); setWriteDirectories(value.write_directories)
      setState('ready'); setDirectory('.')
    } catch (cause) {
      if (request !== generation.current) return
      setSnapshot(null); setState('error'); setError(cause instanceof Error ? cause.message : 'No se pudieron cargar los permisos.')
    }
  }, [projectId, projectRoot])

  useEffect(() => { void load(); return () => { generation.current++ } }, [load, refreshKey])

  const browse = useCallback(async (target: string) => {
    if (!snapshot || !projectId || snapshot.revision === null) return
    setTreeLoading(true); setError('')
    try {
      const response = await fetch('/api/project-permissions/directories', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({expected_project_id: projectId, expected_binding: snapshot.binding, expected_revision: snapshot.revision, directory: target})})
      if (!response.ok) throw new Error(`No se pudieron consultar las carpetas (${response.status}).`)
      const value: unknown = await response.json()
      if (!isDirectoryListing(value) || value.project_id !== projectId || value.root !== snapshot.root || value.revision !== snapshot.revision || JSON.stringify(value.binding) !== JSON.stringify(snapshot.binding)) throw new Error('La carpeta activa cambió. Actualiza los permisos antes de continuar.')
      setDirectory(value.directory); setDirectories(value.directories); setTreeTruncated(value.truncated)
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'No se pudieron consultar las carpetas.') }
    finally { setTreeLoading(false) }
  }, [projectId, snapshot])

  useEffect(() => { if (state === 'ready' && snapshot) void browse('.') }, [state, snapshot?.revision, browse])

  function toggle(kind: 'read' | 'write', path: string, enabled: boolean) {
    const update = (paths: string[]) => [...new Set(enabled ? [...paths, path] : paths.filter(item => item !== path))].sort((a,b) => a.localeCompare(b))
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
      setSnapshot(value); setReadDirectories(value.read_directories); setWriteDirectories(value.write_directories); setConfirmed(false); setState('ready')
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
      setSnapshot(value); setConfirmed(false)
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'No se pudieron revocar los permisos.'); setConfirmed(false); await load() }
    finally { setBusy(false) }
  }

  return <section className="project-permissions" aria-label="Permisos del proyecto" aria-busy={state === 'loading' || busy}>
    <header><div><h4>Permisos del proyecto</h4><p>Carpeta raíz seleccionada</p></div><button type="button" onClick={() => void load()} disabled={state === 'loading' || busy || disabled}>Actualizar</button></header>
    <code className="project-permissions__root">{snapshot?.root ?? projectRoot ?? 'Directorio desconocido'}</code>
    {state === 'loading' && <p role="status">Cargando permisos guardados…</p>}
    {state === 'unknown' && <p role="status">No se puede confirmar el proyecto o su política de permisos. No se ha concedido acceso.</p>}
    {state === 'error' && <p role="alert">{error || 'Estado de permisos desconocido.'}</p>}
    {state === 'ready' && snapshot && <>
      {snapshot.state === 'revoked' && <p className="project-permissions__revoked" role="status">Permisos revocados para este proyecto. Puedes definir una nueva política en el árbol.</p>}
      {snapshot.state !== 'active' && <p role="status">Estado de permisos: {snapshot.state}. No se presupone acceso.</p>}
      <>
        <dl><div><dt>Lectura</dt><dd>{readDirectories.length ? readDirectories.join(', ') : 'Sin carpetas autorizadas'}</dd></div><div><dt>Escritura</dt><dd>{writeDirectories.length ? writeDirectories.join(', ') : 'Sin carpetas autorizadas'}</dd></div></dl>
        <p>Se guardan en este proyecto y se comparten entre conversaciones. Los cambios de archivos requieren revisión y confirmación aparte.</p>
        <ProjectPermissionTree directory={directory} directories={directories} readCurrent={readDirectories.includes(directory || '.')} writeCurrent={writeDirectories.includes(directory || '.')} readDirectories={readDirectories} writeDirectories={writeDirectories} loading={treeLoading} truncated={treeTruncated} onOpen={path => void browse(path)} onToggle={toggle}/>
      </>
      {error && <p role="alert">{error}</p>}
      <label className="project-permissions__confirm"><input type="checkbox" checked={confirmed} disabled={busy || disabled || snapshot.revision === null} onChange={event => setConfirmed(event.target.checked)}/><span>He revisado este alcance y confirmo los permisos del proyecto.</span></label>
      <div className="project-permissions__actions"><button type="button" onClick={() => void save()} disabled={snapshot.revision === null || !confirmed || busy || disabled}>Guardar permisos</button><button type="button" onClick={() => void revoke()} disabled={snapshot.state !== 'active' || !confirmed || busy || disabled}>Revocar permisos</button></div>
    </>}
  </section>
}
