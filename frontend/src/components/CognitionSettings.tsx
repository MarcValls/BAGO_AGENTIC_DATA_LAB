import './CognitionSettings.css'
import { useEffect, useState } from 'react'

export type CognitiveMode = 'baseline' | 'bago5'
const MODE_KEY = 'adl.chat.cognitive-mode.v1'

export function readCognitiveMode(): CognitiveMode {
  try { return localStorage.getItem(MODE_KEY) === 'bago5' ? 'bago5' : 'baseline' }
  catch { return 'baseline' }
}

type ContextLocation = { id: string; label: string; path: string; state: 'present' | 'absent'; purpose: string }
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
      if (body.cancelled) { setWorkspaceNotice('Folder selection cancelled.'); return }
      if (!body.workspace_root) throw new Error('The selected folder was not returned by the server.')
      setPathDraft(body.workspace_root)
      setWorkspaceNotice('Workspace selected. Project tools and context now use this folder.')
      setRequest((value) => value + 1)
    } catch (cause) {
      setWorkspaceError(cause instanceof Error ? cause.message : 'The workspace folder could not be selected.')
    } finally { setWorkspaceBusy(false) }
  }

  const location = (id: string) => metadata?.paths.find((item) => item.id === id)
  const renderLocation = (item: ContextLocation | undefined) => item && <div className={`workspace-source ${item.state}`} key={item.id}>
    <div><strong>{item.label}</strong><span>{item.state === 'present' ? 'Available' : 'Not found'}</span></div>
    <code title={item.path}>{item.path}</code>
  </div>

  return <div className={`cognition-settings${workspaceOnly ? ' workspace-settings' : ''}`}>
    {!workspaceOnly && <header><h3>Cognition & context</h3><p>Choose how the assistant handles new messages.</p></header>}
    {workspaceOnly && <header className="workspace-heading"><span>PROJECT SCOPE</span><h3>Workspace</h3></header>}
    {!workspaceOnly && <fieldset className="cognition-mode"><legend>Chat cognition mode</legend>
      <label><input type="radio" name="cognitive-mode" value="baseline" checked={mode === 'baseline'} onChange={() => changeMode('baseline')} /><span><strong>Baseline</strong><small>Use the normal assistant or agent prompt.</small></span></label>
      <label><input type="radio" name="cognitive-mode" value="bago5" checked={mode === 'bago5'} onChange={() => changeMode('bago5')} /><span><strong>BAGO5 experimental</strong><small>Add bounded cognitive focus to the model prompt. Responses show the applied focus and trace.</small></span></label>
    </fieldset>}
    {!workspaceOnly && modeNotice && <p className="cognition-status" role="status">{modeNotice}</p>}
    {workspaceOnly && <section className="workspace-picker" aria-label="Active workspace">
      <label htmlFor="workspace-path">Workspace path</label>
      <div className="workspace-path-row"><input id="workspace-path" value={pathDraft} onChange={(event) => setPathDraft(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter') void applyWorkspace('/api/workspace/select') }} placeholder="Select a project folder" disabled={workspaceBusy} />
        <button type="button" className="workspace-browse" onClick={() => void applyWorkspace('/api/workspace/browse')} disabled={workspaceBusy}>{workspaceBusy ? 'Waiting…' : 'Browse…'}</button>
        <button type="button" onClick={() => void applyWorkspace('/api/workspace/select')} disabled={workspaceBusy || !pathDraft.trim()}>Use folder</button>
      </div>
      <small>The path selected here scopes project files, scans and capabilities. Files are not read into chat automatically.</small>
      {workspaceNotice && <p className="cognition-status" role="status">{workspaceNotice}</p>}
      {workspaceError && <p className="context-path-error" role="alert">{workspaceError}</p>}
    </section>}
    {showWorkspaceLocations && (workspaceOnly ? <section className="context-locations workspace-context">
      {loading && <p role="status">Loading context sources…</p>}
      {error && <div role="alert"><p>{error}</p><button type="button" onClick={() => setRequest((value) => value + 1)}>Retry</button></div>}
      {metadata && <>
        <div className="workspace-context-intro"><h4>Context layers</h4><p>Each layer narrows or enriches the context below it. An unavailable source is shown clearly instead of being assumed.</p></div>
        <ol className="workspace-layers">
          <li className="workspace-layer layer-unavailable">
            <div className="workspace-layer-title"><span className="layer-number">01</span><div><h5>General memory</h5><span className="layer-state">Not connected</span></div></div>
            <p>Would hold preferences and knowledge shared across projects. It could guide project interpretation, but this chat has no general-memory source connected.</p>
          </li>
          <li className="workspace-layer">
            <div className="workspace-layer-title"><span className="layer-number">02</span><div><h5>Project context</h5><span className="layer-state">Listed · not auto-loaded</span></div></div>
            <p>Project canon and recorded state define the project’s terms and current status. They should constrain workspace interpretation; these files are currently shown as sources, not automatically added to the model prompt.</p>
            <div className="workspace-sources">{renderLocation(location('project-context'))}{renderLocation(location('project-state'))}{renderLocation(location('active-handoff'))}</div>
          </li>
          <li className="workspace-layer">
            <div className="workspace-layer-title"><span className="layer-number">03</span><div><h5>Workspace</h5><span className="layer-state">Active project boundary</span></div></div>
            <p>The selected folder tells project tools where relative paths start. It bounds approved file reads, duplicate scans and the capability catalog; it does not grant a read by itself.</p>
            <div className="workspace-source active"><div><strong>Selected folder</strong><span>Active</span></div><code title={metadata.workspace_root}>{metadata.workspace_root}</code></div>
          </li>
          <li className="workspace-layer">
            <div className="workspace-layer-title"><span className="layer-number">04</span><div><h5>Conversation memory</h5><span className="layer-state">{metadata.memory.state === 'present' ? 'Connected' : 'Not found'}</span></div></div>
            <p>The active conversation supplies its saved message history to the next turn. It gives immediate intent and recent decisions within this chat, subject to the project’s boundaries.</p>
            <div className="workspace-sources">{renderLocation(location('conversations'))}</div>
          </li>
        </ol>
      </>}
    </section> : <details className="context-locations"><summary id="context-locations-title"><strong>Context locations</strong><span>{metadata ? `${metadata.paths.length} locations` : 'Inspect paths and status'}</span></summary>
      <div className="context-locations-content">{loading && <p role="status">Loading context sources…</p>}{error && <div role="alert"><p>{error}</p><button type="button" onClick={() => setRequest((value) => value + 1)}>Retry</button></div>}
        {metadata && <dl className="context-summary"><div><dt>Project folder</dt><dd><code>{metadata.workspace_root}</code></dd></div><div><dt>Memory</dt><dd>{metadata.memory.kind === 'conversation_history' ? 'Saved conversations' : metadata.memory.kind} · {metadata.memory.state}</dd></div></dl>}
      </div>
    </details>)}
  </div>
}
