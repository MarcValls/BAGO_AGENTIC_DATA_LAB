import './CognitionSettings.css'
import { useEffect, useState } from 'react'

export type CognitiveMode = 'baseline' | 'bago5'
const MODE_KEY = 'adl.chat.cognitive-mode.v1'
const PATHS_KEY = 'adl.chat.context-paths.v1'

export function readCognitiveMode(): CognitiveMode {
  try { return localStorage.getItem(MODE_KEY) === 'bago5' ? 'bago5' : 'baseline' }
  catch { return 'baseline' }
}

type ContextMetadata = {
  workspace_root: string
  cognition: { profile: string; capacity: number; max_hops: number; max_expansions: number }
  paths: Array<{ id: string; label: string; path: string; state: 'present' | 'absent'; purpose: string; kind?: 'file' | 'directory' | null }>
  memory: { kind: string; state: string; description: string }
}

function readPathOverrides(): Record<string, string> {
  try {
    const parsed = JSON.parse(localStorage.getItem(PATHS_KEY) ?? '{}')
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed as Record<string, string> : {}
  } catch { return {} }
}

export default function CognitionSettings({ mode, onModeChange }: { mode: CognitiveMode; onModeChange: (mode: CognitiveMode) => void }) {
  const [metadata, setMetadata] = useState<ContextMetadata | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [storageWarning, setStorageWarning] = useState('')
  const [modeNotice, setModeNotice] = useState('')
  const [pathDrafts, setPathDrafts] = useState<Record<string, string>>({})
  const [savingPath, setSavingPath] = useState<string | null>(null)
  const [pathNotice, setPathNotice] = useState('')
  const [pathError, setPathError] = useState('')
  const [request, setRequest] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    setError('')
    setMetadata(null)
    void fetch('/api/chat/context', { signal: controller.signal }).then(async (response) => {
      if (!response.ok) throw new Error(`Context locations are unavailable (${response.status}).`)
      const data = await response.json() as ContextMetadata
      if (typeof data.workspace_root !== 'string' || !Array.isArray(data.paths) || !data.cognition || !data.memory) throw new Error('Context metadata is incomplete.')
      const overrides = readPathOverrides()
      const paths = data.paths.map((item) => ({ ...item, path: overrides[item.id] || item.path }))
      setMetadata({ ...data, paths })
      setPathDrafts(Object.fromEntries(paths.map((item) => [item.id, item.path])))
      await Promise.all(paths.filter((item) => overrides[item.id]).map(async (item) => {
        try {
          const check = await fetch('/api/chat/context/check-path', {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ path: item.path }), signal: controller.signal,
          })
          if (!check.ok) return
          const result = await check.json() as { state: 'present' | 'absent'; kind?: 'file' | 'directory' | null }
          setMetadata((current) => current ? {
            ...current,
            paths: current.paths.map((path) => path.id === item.id ? { ...path, state: result.state, kind: result.kind } : path),
            memory: item.id === 'conversations' ? { ...current.memory, state: result.state } : current.memory,
          } : current)
        } catch { /* Keep the backend's last known presence state when a custom check fails. */ }
      }))
    }).catch((cause: unknown) => {
      if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : 'Context locations are unavailable.')
    }).finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [request])

  const changeMode = (next: CognitiveMode) => {
    onModeChange(next)
    setModeNotice(`${next === 'bago5' ? 'BAGO5 experimental' : 'Baseline'} is applied now and affects new messages.`)
    try { localStorage.setItem(MODE_KEY, next); setStorageWarning('') }
    catch { setStorageWarning('This browser cannot save preferences. The mode applies until this page is reloaded.') }
  }

  const savePath = async (id: string) => {
    const path = pathDrafts[id]?.trim()
    if (!path) { setPathError('Enter a path before saving.'); return }
    setSavingPath(id)
    setPathError('')
    setPathNotice('')
    try {
      const response = await fetch('/api/chat/context/check-path', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ path }),
      })
      if (!response.ok) throw new Error(`The path could not be checked (${response.status}).`)
      const result = await response.json() as { path: string; state: 'present' | 'absent'; kind?: 'file' | 'directory' | null }
      setMetadata((current) => current ? {
        ...current,
        paths: current.paths.map((item) => item.id === id ? { ...item, path: result.path, state: result.state, kind: result.kind } : item),
        memory: id === 'conversations' ? { ...current.memory, state: result.state } : current.memory,
      } : current)
      setPathDrafts((current) => ({ ...current, [id]: result.path }))
      try {
        const overrides = readPathOverrides()
        localStorage.setItem(PATHS_KEY, JSON.stringify({ ...overrides, [id]: result.path }))
      } catch { setStorageWarning('The path is applied for this session but this browser could not save it.') }
      setPathNotice('Path saved in this browser and checked for presence. Its contents are not loaded into chat by this setting.')
    } catch (cause) {
      setPathError(cause instanceof Error ? cause.message : 'The path could not be checked.')
    } finally { setSavingPath(null) }
  }

  return <div className="cognition-settings">
    <header><h3>Cognition & context</h3><p>Choose the prompt mode for model replies and inspect the backend locations used by chat.</p></header>
    <fieldset className="cognition-mode"><legend>Chat cognition mode</legend>
      <label><input type="radio" name="cognitive-mode" value="baseline" checked={mode === 'baseline'} onChange={() => changeMode('baseline')} /><span><strong>Baseline</strong><small>Use the normal assistant or agent prompt.</small></span></label>
      <label><input type="radio" name="cognitive-mode" value="bago5" checked={mode === 'bago5'} onChange={() => changeMode('bago5')} /><span><strong>BAGO5 experimental</strong><small>Add bounded cognitive focus to the model prompt. Responses show the applied focus and trace.</small></span></label>
    </fieldset>
    <p className="cognition-note">Changes apply immediately and are saved in this browser. They affect new messages; use a fresh conversation when comparing modes.</p>
    {modeNotice && <p className="cognition-status" role="status">{modeNotice}</p>}
    {storageWarning && <p role="status">{storageWarning}</p>}
    <details className="context-locations">
      <summary id="context-locations-title"><strong>Context & memory locations</strong><span>{metadata ? `${metadata.paths.length} locations` : 'Inspect paths and status'}</span></summary>
      <div className="context-locations-content">
      <p className="cognition-note">Edit and save a location to check whether it exists. This only records and checks the path; it does not load its contents into chat. Exact-file authorization stays in chat and is used once.</p>
      {loading && <p role="status">Loading backend context locations…</p>}
      {error && <div role="alert"><p>{error}</p><button type="button" onClick={() => setRequest((value) => value + 1)}>Retry loading locations</button></div>}
      {metadata && <><dl className="context-summary"><div><dt>Workspace</dt><dd><code>{metadata.workspace_root}</code></dd></div><div><dt>Cognitive profile</dt><dd><code>{metadata.cognition.profile}</code><small>Focus capacity {metadata.cognition.capacity} · {metadata.cognition.max_hops} hops · {metadata.cognition.max_expansions} expansions</small></dd></div><div><dt>Memory</dt><dd>{metadata.memory.kind} · {metadata.memory.state}<small>{metadata.memory.description}</small></dd></div></dl>
        {metadata.paths.length ? <ul className="context-paths">{metadata.paths.map((item) => <li key={item.id} className={`context-path-${item.state}`}><div><strong>{item.label}</strong><span>{item.state === 'present' ? 'Present' : 'Not present'}</span></div><label className="context-path-field">Path<input aria-label={`${item.label} path`} value={pathDrafts[item.id] ?? item.path} onChange={(event) => setPathDrafts((current) => ({ ...current, [item.id]: event.target.value }))} /></label><button type="button" onClick={() => void savePath(item.id)} disabled={savingPath === item.id}>{savingPath === item.id ? 'Checking…' : 'Save path'}</button><p>{item.purpose}</p></li>)}</ul> : <p role="status">The backend reports no configured context paths.</p>}
        {pathError && <p className="context-path-error" role="alert">{pathError}</p>}{pathNotice && <p className="cognition-status" role="status">{pathNotice}</p>}
      </>}
      </div>
    </details>
  </div>
}
