import './CognitionSettings.css'
import { useEffect, useState } from 'react'

export type CognitiveMode = 'baseline' | 'bago5'
const MODE_KEY = 'adl.chat.cognitive-mode.v1'

export function readCognitiveMode(): CognitiveMode {
  try { return localStorage.getItem(MODE_KEY) === 'bago5' ? 'bago5' : 'baseline' }
  catch { return 'baseline' }
}

type ContextMetadata = {
  workspace_root: string
  cognition: { profile: string; capacity: number; max_hops: number; max_expansions: number }
  paths: Array<{ id: string; label: string; path: string; state: 'present' | 'absent'; purpose: string }>
  memory: { kind: string; state: string; description: string }
}

export default function CognitionSettings({ mode, onModeChange }: { mode: CognitiveMode; onModeChange: (mode: CognitiveMode) => void }) {
  const [metadata, setMetadata] = useState<ContextMetadata | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [storageWarning, setStorageWarning] = useState('')
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
      setMetadata(data)
    }).catch((cause: unknown) => {
      if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : 'Context locations are unavailable.')
    }).finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [request])

  const changeMode = (next: CognitiveMode) => {
    onModeChange(next)
    try { localStorage.setItem(MODE_KEY, next); setStorageWarning('') }
    catch { setStorageWarning('This browser cannot save preferences. The mode applies until this page is reloaded.') }
  }

  return <div className="cognition-settings">
    <header><h3>Cognition & context</h3><p>Choose the prompt mode for model replies and inspect the backend locations used by chat.</p></header>
    <fieldset className="cognition-mode"><legend>Chat cognition mode</legend>
      <label><input type="radio" name="cognitive-mode" value="baseline" checked={mode === 'baseline'} onChange={() => changeMode('baseline')} /><span><strong>Baseline</strong><small>Use the normal assistant or agent prompt.</small></span></label>
      <label><input type="radio" name="cognitive-mode" value="bago5" checked={mode === 'bago5'} onChange={() => changeMode('bago5')} /><span><strong>BAGO5 experimental</strong><small>Add bounded cognitive focus to the model prompt. Responses show the applied focus and trace.</small></span></label>
    </fieldset>
    <p className="cognition-note">Applies to the app assistant and selected agents. Saved in this browser. Use fresh conversations when comparing modes; the visible focus describes prompt preparation.</p>
    {storageWarning && <p role="status">{storageWarning}</p>}
    <section className="context-locations" aria-labelledby="context-locations-title"><h3 id="context-locations-title">Context & memory locations</h3>
      <p className="cognition-note">These are read-only backend locations. Viewing them does not authorize sending file contents to a model. Exact-file authorization stays in chat and is used once.</p>
      {loading && <p role="status">Loading backend context locations…</p>}
      {error && <div role="alert"><p>{error}</p><button type="button" onClick={() => setRequest((value) => value + 1)}>Retry loading locations</button></div>}
      {metadata && <><dl className="context-summary"><div><dt>Workspace</dt><dd><code>{metadata.workspace_root}</code></dd></div><div><dt>Cognitive profile</dt><dd><code>{metadata.cognition.profile}</code><small>Focus capacity {metadata.cognition.capacity} · {metadata.cognition.max_hops} hops · {metadata.cognition.max_expansions} expansions</small></dd></div><div><dt>Memory</dt><dd>{metadata.memory.kind} · {metadata.memory.state}<small>{metadata.memory.description}</small></dd></div></dl>
        {metadata.paths.length ? <ul className="context-paths">{metadata.paths.map((item) => <li key={item.id}><div><strong>{item.label}</strong><span>{item.state}</span></div><code>{item.path}</code><p>{item.purpose}</p></li>)}</ul> : <p role="status">The backend reports no configured context paths.</p>}
      </>}
    </section>
  </div>
}
