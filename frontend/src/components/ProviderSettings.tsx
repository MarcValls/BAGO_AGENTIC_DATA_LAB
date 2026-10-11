import { FormEvent, useEffect, useState } from 'react'
import './ProviderSettings.css'

type AuthMode = 'api_key' | 'local_cli'
type ProviderState = 'not_configured' | 'needs_authentication' | 'local_service_unavailable' | 'configured_unverified' | 'ready' | 'unsupported_runtime' | 'error'
type ProviderStatus = { provider_id: string; state: ProviderState; runtime_mode?: 'host' | 'container'; auth_mode: AuthMode | null; model_id: string | null; message?: string; last_verified_at?: string }
type ProviderModel = { provider_id: string; model_id: string; display_name: string; source: string; availability_confidence: string }

async function safeError(response: Response): Promise<string> {
  try {
    const body = await response.json()
    if (typeof body?.detail?.message === 'string') return body.detail.message
    if (typeof body?.detail === 'string') return body.detail
  } catch { /* use generic message */ }
  return `Request failed (${response.status}).`
}

const stateLabels: Record<ProviderState, string> = {
  not_configured: 'Not configured',
  needs_authentication: 'Authentication needed',
  local_service_unavailable: 'Local Ollama unavailable',
  configured_unverified: 'Configured · not verified',
  ready: 'Ready · live response verified',
  unsupported_runtime: 'Provider setup requires the host app',
  error: 'Provider error',
}

export default function ProviderSettings() {
  const [status, setStatus] = useState<ProviderStatus | null>(null)
  const [authMode, setAuthMode] = useState<AuthMode>('api_key')
  const [apiKey, setApiKey] = useState('')
  const [modelId, setModelId] = useState('')
  const [models, setModels] = useState<ProviderModel[]>([])
  const [loading, setLoading] = useState(true)
  const [loadingModels, setLoadingModels] = useState(false)
  const [saving, setSaving] = useState(false)
  const [verifying, setVerifying] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [verification, setVerification] = useState('')

  const loadStatus = async () => {
    setLoading(true)
    setError('')
    try {
      const response = await fetch('/api/providers/ollama/status')
      if (!response.ok) throw new Error(await safeError(response))
      const data = await response.json() as ProviderStatus
      setStatus(data)
      if (data.auth_mode) setAuthMode(data.auth_mode)
      setModelId(data.model_id ?? '')
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Provider status could not be loaded.')
    } finally { setLoading(false) }
  }

  const loadModels = async () => {
    if (status?.auth_mode !== authMode || (authMode === 'api_key' && apiKey.length > 0)) {
      setNotice('Save the selected authentication mode and API key before loading models.')
      return
    }
    setLoadingModels(true)
    setError('')
    try {
      const response = await fetch('/api/providers/ollama/models')
      if (!response.ok) throw new Error(await safeError(response))
      const data = await response.json()
      const available = Array.isArray(data.models) ? data.models as ProviderModel[] : []
      setModels(available)
      if (!modelId && available.length === 1) setModelId(available[0].model_id)
      if (!available.length) setNotice('No models were returned for this provider configuration. Check authentication and reload the list.')
      else setNotice(`Loaded ${available.length} model(s) from ${data.source ?? 'Ollama'}. Listing a model does not verify that your account can run it.`)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Model list could not be loaded.')
    } finally { setLoadingModels(false) }
  }

  useEffect(() => { void loadStatus() }, [])

  const saveConfiguration = async (event?: FormEvent) => {
    event?.preventDefault()
    setSaving(true)
    setError('')
    setNotice('')
    setVerification('')
    try {
      const body: { auth_mode: AuthMode; model_id?: string; api_key?: string } = { auth_mode: authMode }
      if (modelId.trim()) body.model_id = modelId.trim()
      if (authMode === 'api_key' && apiKey) body.api_key = apiKey
      const response = await fetch('/api/providers/ollama/config', {
        method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
      })
      if (!response.ok) throw new Error(await safeError(response))
      const data = await response.json() as ProviderStatus
      setStatus(data)
      setModelId(data.model_id ?? '')
      setNotice('Provider settings saved. The API key is write-only and has been cleared from this form.')
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Provider settings could not be saved.')
    } finally {
      setApiKey('')
      setSaving(false)
    }
  }

  const verifyConfiguration = async () => {
    if (!modelId.trim()) { setError('Choose a model before checking availability.'); return }
    setVerifying(true)
    setError('')
    setVerification('')
    try {
      const response = await fetch('/api/providers/ollama/verify', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ model_id: modelId.trim() }),
      })
      if (!response.ok) throw new Error(await safeError(response))
      const result = await response.json()
      setVerification(result.model_available ? `${result.model_id} is listed by the configured provider. This check did not generate a model response.` : `Model availability was not confirmed (${result.state}). This check did not generate a model response.`)
      await loadStatus()
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Provider check failed.')
    } finally { setVerifying(false) }
  }

  return (
    <main className="provider-settings">
      <header className="provider-page-heading"><div><p className="provider-eyebrow">Model connection</p><h1>Ollama provider</h1><p>Choose how this app connects to Ollama. Credentials stay on the backend.</p></div><button className="provider-secondary" type="button" onClick={() => void loadStatus()} disabled={loading}>Refresh status</button></header>
      <section className="provider-status-card" aria-live="polite"><div><span className={`provider-status-dot ${status?.state ?? 'unknown'}`} /><div><p className="provider-eyebrow">Current status</p><strong>{loading ? 'Loading status…' : status ? stateLabels[status.state] ?? status.state : 'Status unavailable'}</strong></div></div><div className="provider-status-meta"><span>Auth: {status?.auth_mode === 'api_key' ? 'API key' : status?.auth_mode === 'local_cli' ? 'Local CLI session' : 'Not selected'}</span><span>Model: {status?.model_id ?? 'Not selected'}</span></div>{status?.message && <p className="provider-inline-warning">{status.message}</p>}{status?.runtime_mode === 'container' && <p className="provider-inline-warning">This container cannot safely access the host credential store or host Ollama service. Start the app on this computer with <code>scripts/run-local-ui.ps1</code>.</p>}</section>

      <form className="provider-card" onSubmit={(event) => void saveConfiguration(event)}>
        <div className="provider-section-heading"><span className="provider-step">1</span><div><h2>Choose authentication</h2><p>The selected mode is saved by the local backend. Ollama API calls never originate in the browser.</p></div></div>
        <fieldset className="auth-choice-group" disabled={status?.runtime_mode === 'container'}><legend className="sr-only">Ollama authentication method</legend>
          <label className={`auth-choice ${authMode === 'api_key' ? 'active' : ''}`}><input type="radio" name="auth-mode" value="api_key" checked={authMode === 'api_key'} onChange={() => { setAuthMode('api_key'); setNotice(''); setError('') }} /><span><strong>Ollama Cloud API key</strong><small>Store a new key in the operating system credential store. It cannot be read back.</small></span></label>
          <label className={`auth-choice ${authMode === 'local_cli' ? 'active' : ''}`}><input type="radio" name="auth-mode" value="local_cli" checked={authMode === 'local_cli'} onChange={() => { setAuthMode('local_cli'); setApiKey(''); setNotice(''); setError('') }} /><span><strong>Local Ollama CLI session</strong><small>Use the local Ollama service and its own sign-in. This app does not read Ollama auth files.</small></span></label>
        </fieldset>
        {authMode === 'api_key' ? <div className="provider-field"><label htmlFor="ollama-api-key">API key <span>(write-only)</span></label><input id="ollama-api-key" type="password" autoComplete="new-password" value={apiKey} onChange={(event) => setApiKey(event.target.value)} placeholder="Enter a new key to replace the stored key" spellCheck={false} /><small>The field is cleared as soon as you save. It is not stored in browser storage or chat history.</small></div> : <div className="cli-instructions"><strong>Local CLI setup</strong><ol><li>Open your own Ollama app or terminal and sign in there if needed.</li><li>Keep the Ollama local service running on its standard loopback address.</li><li>Save this mode, then reload models to check whether the local service responds.</li></ol><p>A responding local service does not by itself prove that a Cloud model can run. This app will not start sign-in or inspect CLI credentials.</p></div>}
        <button className="provider-primary" type="submit" disabled={saving || status?.runtime_mode === 'container'}>{saving ? 'Saving…' : 'Save authentication settings'}</button>
      </form>

      <section className="provider-card"><div className="provider-section-heading"><span className="provider-step">2</span><div><h2>Select a model</h2><p>Load the models exposed by the saved provider. Availability is not confirmed until a user-initiated model response succeeds.</p></div></div><div className="model-controls"><label className="provider-field model-select-field" htmlFor="ollama-model">Model<select id="ollama-model" value={modelId} onChange={(event) => setModelId(event.target.value)} disabled={status?.runtime_mode === 'container'}><option value="">Select a model…</option>{models.map((model) => <option key={`${model.provider_id}:${model.model_id}`} value={model.model_id}>{model.display_name} · {model.source}</option>)}</select></label><button className="provider-secondary" type="button" onClick={() => void loadModels()} disabled={loadingModels || status?.runtime_mode === 'container'}>{loadingModels ? 'Loading…' : 'Load models'}</button></div>{models.length === 0 && !loadingModels && <p className="provider-empty-models">No model list loaded. Save authentication settings first, then load models.</p>}<div className="model-actions"><button className="provider-secondary" type="button" onClick={() => void saveConfiguration()} disabled={saving || !modelId.trim() || status?.runtime_mode === 'container'}>{saving ? 'Saving…' : 'Save selected model'}</button><button className="provider-secondary" type="button" onClick={() => void verifyConfiguration()} disabled={verifying || loading || !modelId.trim() || status?.runtime_mode === 'container'}>{verifying ? 'Checking…' : 'Check model listing'}</button></div><p className="provider-footnote">The check is non-generative. It does not consume inference tokens and does not mark the provider ready for live chat.</p></section>

      {error && <p className="provider-alert error" role="alert">{error}</p>}{notice && <p className="provider-alert notice" role="status">{notice}</p>}{verification && <p className="provider-alert notice" role="status">{verification}</p>}
      {status?.last_verified_at && <p className="provider-footnote">Last successful live model response: {new Date(status.last_verified_at).toLocaleString()}</p>}
    </main>
  )
}
