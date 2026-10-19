import './ProviderSettings.css'
import { FormEvent, useEffect, useState } from 'react'

type AuthMode = 'api_key' | 'local_cli'
type ProviderState = 'not_configured' | 'needs_authentication' | 'local_service_unavailable' | 'configured_unverified' | 'ready' | 'unsupported_runtime' | 'error'
type ProviderStatus = { provider_id: string; state: ProviderState; runtime_mode?: 'host' | 'container'; auth_mode: AuthMode | null; model_id: string | null; message?: string; last_verified_at?: string }
export type ProviderStatusSummary = Pick<ProviderStatus, 'state' | 'auth_mode'>
type ProviderModel = { provider_id: string; model_id: string; display_name: string; source: string; availability_confidence: string }
type RegistrationMode = 'codex_cli' | 'copilot_cli' | 'token' | 'api_key' | 'local' | 'local_cli'
type Registration = { provider_id: string; state: string; auth_mode: RegistrationMode | null; model_id: string | null; base_url: string | null; has_credential: boolean; updated_at?: string; runtime_support?: string }
type ProviderId = 'ollama' | 'codex' | 'openai-platform' | 'github-copilot' | 'anthropic' | 'openrouter' | 'opencode'

type ProviderDefinition = {
  id: ProviderId
  label: string
  summary: string
  registrationModes: RegistrationMode[]
  defaultMode: RegistrationMode
  modelPlaceholder: string
  baseUrlPlaceholder?: string
  baseUrlLabel?: string
  steps: Partial<Record<RegistrationMode, string[]>>
  commands?: Partial<Record<RegistrationMode, string[]>>
}

const PROVIDERS: ProviderDefinition[] = [
  {
    id: 'ollama', label: 'Ollama', summary: 'Servicio local o acceso a Ollama Cloud.',
    registrationModes: ['local_cli', 'api_key'], defaultMode: 'api_key', modelPlaceholder: 'qwen3:8b',
    steps: {
      local_cli: ['Inicia Ollama en este equipo.', 'Guarda el modo local para que ADL consulte el servicio de loopback.', 'Carga los modelos y elige uno.'],
      api_key: ['Crea una clave desde tu cuenta de Ollama Cloud.', 'Guárdala en el almacén de credenciales del sistema.', 'Carga los modelos y comprueba su disponibilidad.']
    }
  },
  {
    id: 'codex', label: 'OpenAI Codex', summary: 'Usa una sesión propia de Codex CLI; es distinta de OpenAI Platform.',
    registrationModes: ['codex_cli'], defaultMode: 'codex_cli', modelPlaceholder: 'gpt-5-codex',
    steps: { codex_cli: ['Instala Codex CLI desde la distribución oficial.', 'Inicia sesión con tu cuenta desde tu terminal.', 'Comprueba el estado y guarda el modelo que quieres asociar.'] },
    commands: { codex_cli: ['codex login', 'codex login status'] }
  },
  {
    id: 'openai-platform', label: 'OpenAI Platform', summary: 'Conexión de API facturada en OpenAI Platform, separada de Codex CLI.',
    registrationModes: ['api_key'], defaultMode: 'api_key', modelPlaceholder: 'gpt-5.5',
    steps: { api_key: ['Crea una API key de proyecto en OpenAI Platform.', 'Pégala en este formulario seguro; ADL la guarda en el almacén del sistema.', 'Indica un modelo para completar el registro.'] }
  },
  {
    id: 'github-copilot', label: 'GitHub Copilot', summary: 'Autenticación mediante Copilot CLI o token compatible.',
    registrationModes: ['copilot_cli', 'token'], defaultMode: 'copilot_cli', modelPlaceholder: 'gpt-4.1',
    steps: {
      copilot_cli: ['Instala GitHub Copilot CLI desde la guía oficial.', 'Inicia sesión en tu terminal y confirma que tu cuenta tenga acceso a Copilot.', 'Vuelve a ADL y guarda el registro.'],
      token: ['Crea un fine-grained personal access token con permiso Copilot Requests.', 'Pégalo aquí para guardarlo en el almacén de credenciales del sistema.', 'Indica un modelo para completar el registro.']
    },
    commands: { copilot_cli: ['copilot login'] }
  },
  {
    id: 'anthropic', label: 'Anthropic', summary: 'Conexión mediante API key de Anthropic.',
    registrationModes: ['api_key'], defaultMode: 'api_key', modelPlaceholder: 'claude-sonnet-4-5',
    steps: { api_key: ['Crea una API key en tu cuenta de Anthropic.', 'Pégala en este formulario seguro.', 'Indica el modelo que quieres asociar.'] }
  },
  {
    id: 'openrouter', label: 'OpenRouter', summary: 'Conexión mediante API key y nombre de modelo/ruta.',
    registrationModes: ['api_key'], defaultMode: 'api_key', modelPlaceholder: 'anthropic/claude-sonnet-4.5',
    steps: { api_key: ['Crea una API key en OpenRouter.', 'Pégala en este formulario seguro.', 'Indica el identificador de modelo o ruta.'] }
  },
  {
    id: 'opencode', label: 'OpenCode', summary: 'Endpoint OpenCode local o remoto.',
    registrationModes: ['local', 'api_key'], defaultMode: 'local', modelPlaceholder: 'default',
    baseUrlLabel: 'URL base', baseUrlPlaceholder: 'http://127.0.0.1:3000',
    steps: {
      local: ['Inicia tu servidor OpenCode.', 'Indica el endpoint local o remoto.', 'Guarda el modelo publicado por el servidor.'],
      api_key: ['Configura el endpoint OpenCode.', 'Añade la API key si tu endpoint la requiere.', 'Guarda el modelo publicado por el servidor.']
    }
  }
]

async function safeError(response: Response): Promise<string> {
  try {
    const body = await response.json()
    if (typeof body?.detail?.message === 'string') return body.detail.message
    if (typeof body?.detail === 'string') return body.detail
  } catch { /* use generic message */ }
  return `La solicitud falló (${response.status}).`
}

function statusLabel(state: string | undefined): string {
  if (state === 'ready') return 'Conectado'
  if (state === 'configured_unverified') return 'Registrado · sin verificar'
  if (state === 'needs_authentication') return 'Falta credencial'
  if (state === 'credential_store_unavailable') return 'Almacén seguro no disponible'
  if (state === 'local_service_unavailable') return 'Servicio local no disponible'
  if (state === 'unsupported_runtime') return 'No disponible en este entorno'
  if (state === 'error') return 'Error de configuración'
  return 'Sin registrar'
}

export default function ProviderSettings({ onStatusChange }: { onStatusChange?: (status: ProviderStatusSummary) => void }) {
  const [selectedProvider, setSelectedProvider] = useState<ProviderId>('ollama')
  const [ollamaStatus, setOllamaStatus] = useState<ProviderStatusSummary | null>(null)
  const [registrations, setRegistrations] = useState<Record<string, Registration>>({})
  const [loadingRegistry, setLoadingRegistry] = useState(true)
  const [registryError, setRegistryError] = useState('')

  const refreshRegistry = async () => {
    setLoadingRegistry(true)
    setRegistryError('')
    try {
      const response = await fetch('/api/providers/registry')
      if (!response.ok) throw new Error(await safeError(response))
      const data = await response.json() as { registrations?: Registration[] }
      const next: Record<string, Registration> = {}
      for (const registration of data.registrations ?? []) next[registration.provider_id] = registration
      setRegistrations(next)
    } catch (cause) {
      setRegistryError(cause instanceof Error ? cause.message : 'No se pudo leer el registro de proveedores.')
    } finally { setLoadingRegistry(false) }
  }

  useEffect(() => { void refreshRegistry() }, [])

  const activeProvider = PROVIDERS.find(provider => provider.id === selectedProvider) ?? PROVIDERS[0]
  const registration = registrations[selectedProvider]
  const state = selectedProvider === 'ollama' ? ollamaStatus?.state : registration?.state

  return (
    <section className="provider-settings" aria-labelledby="provider-settings-title">
      <header className="provider-settings-heading">
        <div><p className="provider-eyebrow">CONFIGURACIÓN · IA</p><h2 id="provider-settings-title">Proveedores y modelos</h2><p>Registra cada servicio, elige cómo iniciar sesión y revisa el estado de su conexión.</p></div>
        <button className="provider-secondary" type="button" onClick={() => void refreshRegistry()} disabled={loadingRegistry}>{loadingRegistry ? 'Actualizando…' : '↻  Actualizar registros'}</button>
      </header>

      <div className="provider-registration-layout">
        <nav className="provider-tabs" role="tablist" aria-label="Proveedores">
          <h3>Proveedores</h3>
          {PROVIDERS.map(provider => {
            const providerState = provider.id === 'ollama' ? ollamaStatus?.state : registrations[provider.id]?.state
            const providerIndex = PROVIDERS.findIndex(item => item.id === provider.id)
            return <button
              key={provider.id}
              type="button"
              role="tab"
              id={`provider-tab-${provider.id}`}
              aria-selected={selectedProvider === provider.id}
              aria-controls={`provider-panel-${provider.id}`}
              tabIndex={selectedProvider === provider.id ? 0 : -1}
              className={`provider-tab${selectedProvider === provider.id ? ' active' : ''}`}
              onClick={() => setSelectedProvider(provider.id)}
              onKeyDown={event => {
                const direction = event.key === 'ArrowDown' || event.key === 'ArrowRight' ? 1 : event.key === 'ArrowUp' || event.key === 'ArrowLeft' ? -1 : 0
                if (event.key === 'Home' || event.key === 'End' || direction !== 0) {
                  event.preventDefault()
                  const nextIndex = event.key === 'Home' ? 0 : event.key === 'End' ? PROVIDERS.length - 1 : (providerIndex + direction + PROVIDERS.length) % PROVIDERS.length
                  const nextProvider = PROVIDERS[nextIndex]
                  setSelectedProvider(nextProvider.id)
                  document.getElementById(`provider-tab-${nextProvider.id}`)?.focus()
                }
              }}
            >
              <span>{provider.label}</span><small>{statusLabel(providerState)}</small>
            </button>
          })}
        </nav>

        <section className="provider-pane" role="tabpanel" id={`provider-panel-${selectedProvider}`} aria-labelledby={`provider-tab-${selectedProvider}`}>
          <div className="provider-pane-heading">
            <div><h3>{activeProvider.label}</h3><p>{activeProvider.summary}</p></div>
            <span className={`provider-state ${state === 'ready' ? 'ready' : state === 'configured_unverified' ? 'pending' : 'neutral'}`} role="status">{statusLabel(state)}</span>
          </div>
          {selectedProvider === 'ollama'
            ? <OllamaProviderSettings onStatusChange={summary => { setOllamaStatus(summary); onStatusChange?.(summary) }} />
            : <ProviderRegistrationForm key={selectedProvider} provider={activeProvider} registration={registration} onSaved={updated => setRegistrations(current => ({ ...current, [selectedProvider]: updated }))} />}
          {registryError && <p className="provider-alert error" role="alert">{registryError}</p>}
          {loadingRegistry && <p className="provider-footnote" role="status">Cargando registros guardados…</p>}
        </section>
      </div>
    </section>
  )
}

function ProviderRegistrationForm({ provider, registration, onSaved }: { provider: ProviderDefinition; registration?: Registration; onSaved: (registration: Registration) => void }) {
  const initialMode = registration?.auth_mode && provider.registrationModes.includes(registration.auth_mode) ? registration.auth_mode : provider.defaultMode
  const [authMode, setAuthMode] = useState<RegistrationMode>(initialMode)
  const [apiKey, setApiKey] = useState('')
  const [modelId, setModelId] = useState(registration?.model_id ?? '')
  const [baseUrl, setBaseUrl] = useState(registration?.base_url ?? '')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  useEffect(() => {
    if (registration?.auth_mode && provider.registrationModes.includes(registration.auth_mode)) setAuthMode(registration.auth_mode)
    setModelId(registration?.model_id ?? '')
    setBaseUrl(registration?.base_url ?? '')
  }, [provider.id, registration?.updated_at])

  const steps = provider.steps[authMode] ?? []
  const commands = provider.commands?.[authMode] ?? []
  const needsSecret = authMode === 'api_key' || authMode === 'token'

  const saveRegistration = async (event: FormEvent) => {
    event.preventDefault()
    setSaving(true)
    setError('')
    setNotice('')
    try {
      const body: { auth_mode: RegistrationMode; model_id?: string; base_url?: string; api_key?: string } = { auth_mode: authMode }
      if (modelId.trim()) body.model_id = modelId.trim()
      if (baseUrl.trim()) body.base_url = baseUrl.trim()
      if (apiKey) body.api_key = apiKey
      const response = await fetch(`/api/providers/registry/${provider.id}`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
      })
      if (!response.ok) throw new Error(await safeError(response))
      const result = await response.json() as Registration
      onSaved(result)
      setApiKey('')
      setNotice('Registro guardado. La autenticación y el acceso al proveedor siguen sin verificarse.')
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'No se pudo guardar el registro.')
    } finally { setSaving(false) }
  }

  return (
    <form className="provider-registration-form" onSubmit={event => void saveRegistration(event)}>
      <div className="provider-method-tabs" role="tablist" aria-label={`Métodos de registro de ${provider.label}`}>
        {provider.registrationModes.map(mode => <button
          key={mode}
          type="button"
          role="tab"
          aria-selected={authMode === mode}
          aria-controls="provider-registration-panel"
          tabIndex={authMode === mode ? 0 : -1}
          id={`provider-method-${mode}`}
          className={`provider-method-tab${authMode === mode ? ' active' : ''}`}
          onClick={() => { setAuthMode(mode); setError(''); setNotice(''); setApiKey('') }}
          onKeyDown={event => {
            const direction = event.key === 'ArrowRight' || event.key === 'ArrowDown' ? 1 : event.key === 'ArrowLeft' || event.key === 'ArrowUp' ? -1 : 0
            if (direction !== 0 || event.key === 'Home' || event.key === 'End') {
              event.preventDefault()
              const currentIndex = provider.registrationModes.indexOf(authMode)
              const nextIndex = event.key === 'Home' ? 0 : event.key === 'End' ? provider.registrationModes.length - 1 : (currentIndex + direction + provider.registrationModes.length) % provider.registrationModes.length
              const nextMode = provider.registrationModes[nextIndex]
              setAuthMode(nextMode)
              document.getElementById(`provider-method-${nextMode}`)?.focus()
            }
          }}
        >{modeLabel(mode)}</button>)}
      </div>

      <div id="provider-registration-panel" role="tabpanel" aria-label={`${provider.label}: ${modeLabel(authMode)}`}>
      <section className="provider-steps" aria-label="Pasos de registro">
        <h4>Pasos de registro</h4>
        <ol>{steps.map(step => <li key={step}>{step}</li>)}</ol>
        {commands.length > 0 && <div className="provider-commands">{commands.map(command => <code key={command}>{command}</code>)}</div>}
      </section>

      {needsSecret && <div className="provider-field">
        <label htmlFor={`${provider.id}-credential`}>{authMode === 'token' ? 'Token de GitHub' : 'API key'} <span>(solo escritura)</span></label>
        <input id={`${provider.id}-credential`} type="password" autoComplete="new-password" value={apiKey} onChange={event => setApiKey(event.target.value)} placeholder={registration?.has_credential ? 'Hay una credencial guardada; deja vacío para conservarla' : 'Pega aquí la credencial'} spellCheck={false} />
        <small>ADL no muestra la credencial guardada. Se almacena en el almacén seguro del sistema.</small>
      </div>}

      {provider.baseUrlLabel && <div className="provider-field">
        <label htmlFor={`${provider.id}-base-url`}>{provider.baseUrlLabel}</label>
        <input id={`${provider.id}-base-url`} type="url" value={baseUrl} onChange={event => setBaseUrl(event.target.value)} placeholder={provider.baseUrlPlaceholder} autoComplete="url" />
      </div>}

      <div className="provider-field">
        <label htmlFor={`${provider.id}-model`}>Modelo predeterminado <span>(opcional)</span></label>
        <input id={`${provider.id}-model`} type="text" value={modelId} onChange={event => setModelId(event.target.value)} placeholder={provider.modelPlaceholder} spellCheck={false} />
      </div>

      <div className="provider-unverified" role="note">
        <strong>{registration?.state === 'configured_unverified' ? 'Registro guardado · pendiente de verificar' : 'El registro no confirma acceso en vivo'}</strong>
        <p>Este formulario guarda la modalidad y los datos de registro. En esta versión, ADL aún no usa este proveedor en chat ni en ejecuciones de agentes.</p>
      </div>

      {error && <p className="provider-alert error" role="alert">{error}</p>}
      {notice && <p className="provider-alert notice" role="status">{notice}</p>}
      <div className="provider-form-actions"><button className="provider-primary" type="submit" disabled={saving}>{saving ? 'Guardando…' : 'Guardar registro'}</button></div>
      </div>
    </form>
  )
}

function modeLabel(mode: RegistrationMode): string {
  if (mode === 'codex_cli') return 'Codex CLI'
  if (mode === 'copilot_cli') return 'Copilot CLI'
  if (mode === 'token') return 'Token'
  if (mode === 'local_cli') return 'Ollama local'
  if (mode === 'local') return 'Endpoint local'
  return 'API key'
}

function OllamaProviderSettings({ onStatusChange }: { onStatusChange?: (status: ProviderStatusSummary) => void }) {
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

  const fetchModels = async () => {
    setLoadingModels(true)
    setError('')
    try {
      const response = await fetch('/api/providers/ollama/models')
      if (!response.ok) throw new Error(await safeError(response))
      const data = await response.json()
      const available = Array.isArray(data.models) ? data.models as ProviderModel[] : []
      setModels(available)
      setModelId(current => current || (available.length === 1 ? available[0].model_id : ''))
      if (!available.length) setNotice('No se han devuelto modelos para esta configuración. Comprueba la autenticación y vuelve a cargar la lista.')
      else setNotice(`Se han cargado ${available.length} modelo(s). Que aparezca en la lista no confirma que tu cuenta pueda ejecutarlo.`)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'No se pudo cargar la lista de modelos.')
    } finally { setLoadingModels(false) }
  }

  const loadStatus = async () => {
    setLoading(true)
    setError('')
    try {
      const response = await fetch('/api/providers/ollama/status')
      if (!response.ok) throw new Error(await safeError(response))
      const data = await response.json() as ProviderStatus
      setStatus(data)
      onStatusChange?.(data)
      if (data.auth_mode) setAuthMode(data.auth_mode)
      setModelId(data.model_id ?? '')
      if (data.auth_mode && data.runtime_mode !== 'container' && data.state !== 'needs_authentication') await fetchModels()
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'No se pudo leer el estado de Ollama.')
    } finally { setLoading(false) }
  }

  const loadModels = async () => {
    if (status?.auth_mode !== authMode || (authMode === 'api_key' && apiKey.length > 0)) {
      setNotice('Guarda primero el método de autenticación y la API key antes de cargar modelos.')
      return
    }
    await fetchModels()
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
      onStatusChange?.(data)
      setModelId(data.model_id ?? '')
      setNotice('Configuración guardada. La API key solo escritura se ha borrado del formulario.')
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'No se pudo guardar la configuración de Ollama.')
    } finally {
      setApiKey('')
      setSaving(false)
    }
  }

  const verifyConfiguration = async () => {
    if (!modelId.trim()) { setError('Elige un modelo antes de comprobar su disponibilidad.'); return }
    setVerifying(true)
    setError('')
    setVerification('')
    try {
      const response = await fetch('/api/providers/ollama/verify', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ model_id: modelId.trim() }),
      })
      if (!response.ok) throw new Error(await safeError(response))
      const result = await response.json()
      setVerification(result.model_available ? `${result.model_id} aparece en el proveedor. Esta comprobación no generó una respuesta.` : `No se confirmó la disponibilidad del modelo (${result.state}). Esta comprobación no generó una respuesta.`)
      await loadStatus()
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Falló la comprobación de Ollama.')
    } finally { setVerifying(false) }
  }

  return (
    <div className="ollama-provider-settings">
      <form className="provider-card" onSubmit={event => void saveConfiguration(event)}>
        <div className="provider-section-heading"><span className="provider-step">1</span><div><h4>Elige cómo registrarte</h4><p>Selecciona una sesión local o una clave de Ollama Cloud.</p></div></div>
        <fieldset className="auth-choice-group" disabled={status?.runtime_mode === 'container'}><legend className="sr-only">Método de autenticación de Ollama</legend>
          <label className={`auth-choice ${authMode === 'api_key' ? 'active' : ''}`}><input type="radio" name="ollama-auth-mode" value="api_key" checked={authMode === 'api_key'} onChange={() => { setAuthMode('api_key'); setNotice(''); setError('') }} /><span><strong>Ollama Cloud · API key</strong><small>La clave se guarda en el almacén de credenciales del sistema y no se puede volver a leer.</small></span></label>
          <label className={`auth-choice ${authMode === 'local_cli' ? 'active' : ''}`}><input type="radio" name="ollama-auth-mode" value="local_cli" checked={authMode === 'local_cli'} onChange={() => { setAuthMode('local_cli'); setApiKey(''); setNotice(''); setError('') }} /><span><strong>Ollama local</strong><small>Usa el servicio local; ADL no lee archivos de credenciales de Ollama.</small></span></label>
        </fieldset>
        {authMode === 'api_key' ? <div className="provider-field"><label htmlFor="ollama-api-key">API key <span>(solo escritura)</span></label><input id="ollama-api-key" type="password" autoComplete="new-password" value={apiKey} onChange={event => setApiKey(event.target.value)} placeholder="Introduce una clave nueva para reemplazar la guardada" spellCheck={false} /></div> : <div className="cli-instructions"><strong>Configuración local</strong><ol><li>Abre Ollama en este equipo e inicia sesión si hace falta.</li><li>Mantén el servicio local en su dirección loopback estándar.</li><li>Guarda este modo y carga los modelos disponibles.</li></ol><p>Que responda el servicio local no confirma el acceso a Ollama Cloud.</p></div>}
        <button className="provider-primary" type="submit" disabled={saving || status?.runtime_mode === 'container'}>{saving ? 'Guardando…' : 'Guardar configuración de Ollama'}</button>
      </form>

      <section className="provider-card"><div className="provider-section-heading"><span className="provider-step">2</span><div><h4>Modelo y disponibilidad</h4><p>La lista del proveedor no confirma que el modelo pueda responder a una solicitud.</p></div></div><div className="model-controls"><label className="provider-field model-select-field" htmlFor="ollama-model">Modelo<select id="ollama-model" value={modelId} onChange={event => setModelId(event.target.value)} disabled={status?.runtime_mode === 'container'}><option value="">Selecciona un modelo…</option>{models.map(model => <option key={`${model.provider_id}:${model.model_id}`} value={model.model_id}>{model.display_name} · {model.source}</option>)}</select></label><button className="provider-secondary" type="button" onClick={() => void loadModels()} disabled={loadingModels || status?.runtime_mode === 'container'}>{loadingModels ? 'Cargando…' : 'Cargar modelos'}</button></div>{models.length === 0 && !loadingModels && <p className="provider-empty-models">Guarda primero la configuración y luego carga los modelos.</p>}<div className="model-actions"><button className="provider-secondary" type="button" onClick={() => void saveConfiguration()} disabled={saving || !modelId.trim() || status?.runtime_mode === 'container'}>{saving ? 'Guardando…' : 'Guardar modelo'}</button><button className="provider-secondary" type="button" onClick={() => void verifyConfiguration()} disabled={verifying || loading || !modelId.trim() || status?.runtime_mode === 'container'}>{verifying ? 'Comprobando…' : 'Comprobar disponibilidad'}</button></div><p className="provider-footnote">La comprobación es no generativa; no consume tokens de inferencia ni marca el proveedor como listo para chat.</p></section>

      {error && <p className="provider-alert error" role="alert">{error}</p>}{notice && <p className="provider-alert notice" role="status">{notice}</p>}{verification && <p className="provider-alert notice" role="status">{verification}</p>}
      {status?.last_verified_at && <p className="provider-footnote">Última respuesta satisfactoria del modelo: {new Date(status.last_verified_at).toLocaleString()}</p>}
    </div>
  )
}
