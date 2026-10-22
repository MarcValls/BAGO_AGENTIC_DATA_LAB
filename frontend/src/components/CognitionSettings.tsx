import './CognitionSettings.css'
import { useEffect, useState } from 'react'
import ProjectContextDocument from './ProjectContextDocument'
import type { ContextLocation } from './ProjectContextDocument'

export type CognitiveMode = 'baseline' | 'bago5'
const MODE_KEY = 'adl.chat.cognitive-mode.v1'
const PROJECT_DOCUMENT_LABELS: Record<string, string> = {
  'project-context': 'Contexto del proyecto',
  'project-state': 'Estado del proyecto',
  'active-handoff': 'Continuidad',
}

export function readCognitiveMode(): CognitiveMode {
  try { return localStorage.getItem(MODE_KEY) === 'bago5' ? 'bago5' : 'baseline' }
  catch { return 'baseline' }
}

type ContextMetadata = {
  workspace_root: string
  cognition: { profile: string; capacity: number; max_hops: number; max_expansions: number }
  paths: ContextLocation[]
  memory: { kind: string; state: string; description: string }
}

export default function CognitionSettings({ mode, onModeChange, workspaceOnly = false, showWorkspaceLocations = true }: {
  mode: CognitiveMode
  onModeChange: (mode: CognitiveMode) => void
  workspaceOnly?: boolean
  showWorkspaceLocations?: boolean
}) {
  const [metadata, setMetadata] = useState<ContextMetadata | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [modeNotice, setModeNotice] = useState('')
  const [pathDraft, setPathDraft] = useState('')
  const [workspaceBusy, setWorkspaceBusy] = useState(false)
  const [workspaceNotice, setWorkspaceNotice] = useState('')
  const [workspaceError, setWorkspaceError] = useState('')
  const [request, setRequest] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    setError('')
    void fetch('/api/chat/context', { signal: controller.signal }).then(async (response) => {
      if (!response.ok) throw new Error(`Context locations are unavailable (${response.status}).`)
      const data = await response.json() as ContextMetadata
      if (typeof data.workspace_root !== 'string' || !Array.isArray(data.paths) || !data.cognition || !data.memory) throw new Error('Context metadata is incomplete.')
      setMetadata(data)
      setPathDraft(data.workspace_root)
    }).catch((cause: unknown) => {
      if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : 'Context locations are unavailable.')
    }).finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [request])

  const changeMode = (next: CognitiveMode) => {
    onModeChange(next)
    setModeNotice(`${next === 'bago5' ? 'BAGO5 experimental' : 'Baseline'} applies to new messages.`)
    try { localStorage.setItem(MODE_KEY, next) } catch { setModeNotice('The mode applies until this page is reloaded.') }
  }

  const applyWorkspace = async (endpoint: '/api/workspace/select' | '/api/workspace/browse') => {
    setWorkspaceBusy(true)
    setWorkspaceError('')
    setWorkspaceNotice('')
    try {
      const response = await fetch(endpoint, endpoint.endsWith('/select') ? {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ path: pathDraft }),
      } : { method: 'POST' })
      const body = await response.json() as { workspace_root?: string; cancelled?: boolean; detail?: { message?: string } }
      if (!response.ok) throw new Error(body.detail?.message || 'The workspace folder could not be selected.')
      if (body.cancelled) { setWorkspaceNotice('Selección cancelada.'); return }
      if (!body.workspace_root) throw new Error('The selected folder was not returned by the server.')
      setPathDraft(body.workspace_root)
      setMetadata(null)
      setWorkspaceNotice('Carpeta seleccionada.')
      setRequest((value) => value + 1)
    } catch (cause) {
      setWorkspaceError(cause instanceof Error ? cause.message : 'The workspace folder could not be selected.')
    } finally { setWorkspaceBusy(false) }
  }

  const location = (id: string) => metadata?.paths.find((item) => item.id === id)
  const renderLocation = (item: ContextLocation | undefined) => item && (['project-context', 'project-state', 'active-handoff'].includes(item.id)
    ? <ProjectContextDocument key={`${metadata?.workspace_root}:${item.id}`} item={workspaceOnly ? { ...item, label: PROJECT_DOCUMENT_LABELS[item.id] } : item} workspaceRoot={metadata!.workspace_root} />
    : <div className={`workspace-source ${item.state}`} key={item.id}>
    <div><strong>{item.label}</strong><span>{item.state === 'present' ? 'Available' : 'Not found'}</span></div>
    <p>{item.purpose}</p>
    <code title={item.path}>{item.path}</code>
  </div>)

  return <div className={`cognition-settings${workspaceOnly ? ' workspace-settings' : ''}`}>
    {!workspaceOnly && <header><h3>Cognition & context</h3><p>Choose how the assistant handles new messages.</p></header>}
    {workspaceOnly && <header className="workspace-heading"><h3>Workspace</h3></header>}
    {!workspaceOnly && <fieldset className="cognition-mode"><legend>Chat cognition mode</legend>
      <label><input type="radio" name="cognitive-mode" value="baseline" checked={mode === 'baseline'} onChange={() => changeMode('baseline')} /><span><strong>Baseline</strong><small>Use the normal assistant or agent prompt.</small></span></label>
      <label><input type="radio" name="cognitive-mode" value="bago5" checked={mode === 'bago5'} onChange={() => changeMode('bago5')} /><span><strong>BAGO5 experimental</strong><small>Add bounded cognitive focus to the model prompt. Responses show the applied focus and trace.</small></span></label>
    </fieldset>}
    {!workspaceOnly && modeNotice && <p className="cognition-status" role="status">{modeNotice}</p>}
    {workspaceOnly && <section className="workspace-picker" aria-label="Carpeta del proyecto">
      <label htmlFor="workspace-path">Carpeta del proyecto</label>
      <div className="workspace-path-row"><input id="workspace-path" value={pathDraft} onChange={(event) => { setPathDraft(event.target.value); setWorkspaceNotice('') }} onKeyDown={(event) => { if (event.key === 'Enter' && !workspaceBusy && pathDraft.trim()) void applyWorkspace('/api/workspace/select') }} placeholder="Selecciona una carpeta" disabled={workspaceBusy} />
        <button type="button" className="workspace-browse" onClick={() => void applyWorkspace('/api/workspace/browse')} disabled={workspaceBusy}>{workspaceBusy ? 'Esperando…' : 'Examinar…'}</button>
        <button type="button" onClick={() => void applyWorkspace('/api/workspace/select')} disabled={workspaceBusy || !pathDraft.trim()}>Usar carpeta</button>
      </div>
      {workspaceNotice && <p className="cognition-status" role="status">{workspaceNotice}</p>}
      {workspaceError && <p className="context-path-error" role="alert">{workspaceError}</p>}
    </section>}
    {showWorkspaceLocations && (workspaceOnly ? <section className="context-locations workspace-context">
      {loading && <p role="status">Cargando…</p>}
      {error && <div role="alert"><p>{error}</p><button type="button" onClick={() => setRequest((value) => value + 1)}>Reintentar</button></div>}
      {metadata && <>
        <h4 className="workspace-section-title">Archivos del proyecto</h4>
        <div className="workspace-sources">{renderLocation(location('project-context'))}{renderLocation(location('project-state'))}{renderLocation(location('active-handoff'))}</div>
        <section className="workspace-memory" aria-labelledby="workspace-memory-title">
          <h4 id="workspace-memory-title" className="workspace-section-title">Memoria</h4>
          <dl><div><dt>General</dt><dd className="unavailable">Sin conectar</dd></div><div><dt>Conversación</dt><dd className={metadata.memory.state === 'present' ? 'available' : 'unavailable'}>{metadata.memory.state === 'present' ? 'Disponible' : 'No disponible'}</dd></div></dl>
        </section>
      </>}
    </section> : <details className="context-locations cognition-context" open>
      <summary id="context-locations-title"><strong>Context and workspace</strong><span>{metadata ? `${metadata.paths.length} project sources` : 'Loading project scope'}</span></summary>
      <div className="context-locations-content">
        {loading && <p role="status">Loading context sources…</p>}
        {error && <div role="alert"><p>{error}</p><button type="button" onClick={() => setRequest((value) => value + 1)}>Retry</button></div>}
        {metadata && <>
          <p className="cognition-context-intro">Live scope and context metadata used by ADL. Source presence is shown without loading file contents into chat.</p>
          <dl className="context-summary cognition-context-summary">
            <div><dt>Active workspace</dt><dd><code title={metadata.workspace_root}>{metadata.workspace_root}</code></dd></div>
            <div><dt>Cognition profile</dt><dd>{metadata.cognition.profile}</dd></div>
            <div><dt>Focus capacity</dt><dd>{metadata.cognition.capacity} units · {metadata.cognition.max_hops} hops · {metadata.cognition.max_expansions} expansions</dd></div>
            <div><dt>Conversation memory</dt><dd>{metadata.memory.kind} · {metadata.memory.state}<small>{metadata.memory.description}</small></dd></div>
          </dl>
          <div className="context-sources-heading"><h4>Project context sources</h4><span>Despliega un archivo para leerlo</span></div>
          <div className="context-source-grid">{metadata.paths.map((item) => renderLocation(item))}</div>
        </>}
      </div>
    </details>)}
  </div>
}
