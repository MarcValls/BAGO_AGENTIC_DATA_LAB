import './ProviderSettings.css'
import { FormEvent, useCallback, useEffect, useState } from 'react'
import ModelAssignments from './ModelAssignments'

type AuthMode = 'api_key' | 'local_cli' | 'codex_cli'
type ProviderState = 'not_configured' | 'needs_authentication' | 'authenticated' | 'local_service_unavailable' | 'configured_unverified' | 'ready' | 'unsupported_runtime' | 'error'
type ProviderStatus = { provider_id: string; state: ProviderState; runtime_mode?: 'host' | 'container'; auth_mode: AuthMode | null; model_id: string | null; message?: string; last_verified_at?: string }
export type ProviderStatusSummary = Pick<ProviderStatus, 'state' | 'auth_mode'> & { model_id?: string | null }
type ProviderModel = { provider_id: string; model_id: string; display_name: string; source: string; availability_confidence: string }
type RegistrationMode = 'codex_cli' | 'copilot_cli' | 'token' | 'api_key' | 'local' | 'local_cli'
type Registration = { provider_id: string; state: string; auth_mode: RegistrationMode | null; model_id: string | null; base_url: string | null; has_credential: boolean; updated_at?: string; last_verified_at?: string; runtime_support?: string }
type ProviderId = 'ollama' | 'codex' | 'openai-platform' | 'github-copilot' | 'anthropic' | 'openrouter' | 'opencode'

type ProviderDefinition = {
  id: ProviderId
  label: string
  logo: string
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
    id: 'ollama', label: 'Ollama', logo: '/brand/ollama.svg', summary: 'Servicio local o acceso a Ollama Cloud.',
    registrationModes: ['local_cli', 'api_key'], defaultMode: 'api_key', modelPlaceholder: 'qwen3:8b',
    steps: {
      local_cli: ['Inicia Ollama en este equipo.', 'Guarda el modo local para que ADL consulte el servicio de loopback.', 'Carga los modelos y elige uno.'],
      api_key: ['Crea una clave desde tu cuenta de Ollama Cloud.', 'Guárdala en el almacén de credenciales del sistema.', 'Carga los modelos y comprueba su disponibilidad.']
    }
  },
  {
    id: 'codex', label: 'OpenAI Codex', logo: '/brand/openai.svg', summary: '',
    registrationModes: ['codex_cli'], defaultMode: 'codex_cli', modelPlaceholder: 'gpt-5-codex',
    steps: { codex_cli: ['Inicia sesión con ChatGPT en el navegador.', 'Elige un modelo disponible en tu sesión de Codex.', 'Guarda el modelo para usarlo en los agentes de ADL.'] }
  },
  {
    id: 'openai-platform', label: 'OpenAI Platform', logo: '/brand/openai.svg', summary: 'Conexión de API facturada en OpenAI Platform, separada de Codex CLI.',
    registrationModes: ['api_key'], defaultMode: 'api_key', modelPlaceholder: 'gpt-5.5',
    steps: { api_key: ['Crea una API key de proyecto en OpenAI Platform.', 'Pégala en este formulario seguro; ADL la guarda en el almacén del sistema.', 'Indica un modelo para completar el registro.'] }
  },
  {
    id: 'github-copilot', label: 'GitHub Copilot', logo: '/brand/github-copilot.svg', summary: 'Inicia sesión en GitHub con un código de dispositivo o usa un token compatible.',
    registrationModes: ['copilot_cli', 'token'], defaultMode: 'copilot_cli', modelPlaceholder: 'gpt-4.1',
    steps: {
      copilot_cli: ['Solicita el código de un solo uso desde ADL.', 'Abre github.com/login/device, introduce el código XXXX-XXXX y autoriza GitHub Copilot.', 'Vuelve a ADL, guarda el modelo y comprueba el acceso con una solicitud real.'],
      token: ['Crea un fine-grained personal access token con permiso Copilot Requests.', 'Pégalo aquí para guardarlo en el almacén de credenciales del sistema.', 'Indica un modelo y comprueba el acceso desde ADL.']
    }
  },
  {
    id: 'anthropic', label: 'Anthropic', logo: '/brand/anthropic.svg', summary: 'Conexión mediante API key de Anthropic.',
    registrationModes: ['api_key'], defaultMode: 'api_key', modelPlaceholder: 'claude-sonnet-4-5',
    steps: { api_key: ['Crea una API key en tu cuenta de Anthropic.', 'Pégala en este formulario seguro.', 'Indica el modelo que quieres asociar.'] }
  },
  {
    id: 'openrouter', label: 'OpenRouter', logo: '/brand/openrouter-official.svg', summary: 'Conexión mediante API key y nombre de modelo/ruta.',
    registrationModes: ['api_key'], defaultMode: 'api_key', modelPlaceholder: 'anthropic/claude-sonnet-4.5',
    steps: { api_key: ['Crea una API key en OpenRouter.', 'Pégala en este formulario seguro.', 'Indica el identificador de modelo o ruta.'] }
  },
  {
    id: 'opencode', label: 'OpenCode', logo: '/brand/opencode.svg', summary: 'Endpoint OpenCode local o remoto.',
    registrationModes: ['local', 'api_key'], defaultMode: 'local', modelPlaceholder: 'default',
    baseUrlLabel: 'URL base', baseUrlPlaceholder: 'http://127.0.0.1:3000',
    steps: {
      local: ['Inicia tu servidor OpenCode.', 'Indica el endpoint local o remoto.', 'Guarda el modelo publicado por el servidor.'],
      api_key: ['Configura el endpoint OpenCode.', 'Añade la API key si tu endpoint la requiere.', 'Guarda el modelo publicado por el servidor.']
    }
  }
]

const PROVIDER_TABS = PROVIDERS.filter(provider => provider.id !== 'openai-platform')
const OPENAI_PLATFORM = PROVIDERS.find(provider => provider.id === 'openai-platform')!

async function safeError(response: Response): Promise<string> {
  try {
    const body = await response.json()
    if (typeof body?.detail?.message === 'string') return body.detail.message
    if (typeof body?.detail === 'string') return body.detail
  } catch { /* use generic message */ }
  return `La solicitud falló (${response.status}).`
}

function statusLabel(state: string | undefined): string {
  if (state === 'ready') return 'Acceso comprobado'
  if (state === 'authenticated') return 'Sesión iniciada'
  if (state === 'configured_unverified') return 'Registrado · sin verificar'
  if (state === 'needs_authentication') return 'Falta credencial'
  if (state === 'credential_store_unavailable') return 'Almacén seguro no disponible'
  if (state === 'local_service_unavailable') return 'Servicio local no disponible'
  if (state === 'unsupported_runtime') return 'No disponible en este entorno'
  if (state === 'error') return 'Error de configuración'
  return 'Sin registrar'
}

function providerUsable(state: string | undefined): boolean {
  return state === 'ready' || state === 'configured_unverified'
}

export default function ProviderSettings({ onStatusChange }: { onStatusChange?: (status: ProviderStatusSummary) => void }) {
  const [settingsTab, setSettingsTab] = useState<'providers' | 'models'>('providers')
  const [selectedProvider, setSelectedProvider] = useState<ProviderId>('ollama')
  const [ollamaStatus, setOllamaStatus] = useState<ProviderStatusSummary | null>(null)
  const [codexStatus, setCodexStatus] = useState<ProviderStatusSummary | null>(null)
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
  const state = selectedProvider === 'ollama' ? ollamaStatus?.state : selectedProvider === 'codex' ? codexStatus?.state ?? registration?.state : registration?.state

  return (
    <section className="provider-settings" aria-label="Configuración de proveedores y modelos">
      <div className="provider-settings-tabs" role="tablist" aria-label="Configuración de proveedores y modelos">
        <button type="button" role="tab" id="provider-settings-tab-providers" aria-selected={settingsTab === 'providers'} aria-controls="provider-settings-panel-providers" tabIndex={settingsTab === 'providers' ? 0 : -1} className={settingsTab === 'providers' ? 'active' : ''} onClick={() => setSettingsTab('providers')}>Proveedores</button>
        <button type="button" role="tab" id="provider-settings-tab-models" aria-selected={settingsTab === 'models'} aria-controls="provider-settings-panel-models" tabIndex={settingsTab === 'models' ? 0 : -1} className={settingsTab === 'models' ? 'active' : ''} onClick={() => setSettingsTab('models')}>Modelos activos</button>
      </div>
      {settingsTab === 'models'
        ? <div role="tabpanel" id="provider-settings-panel-models" aria-labelledby="provider-settings-tab-models" className="provider-model-policy-panel"><ModelAssignments onExit={() => setSettingsTab('providers')} /></div>
        : <div role="tabpanel" id="provider-settings-panel-providers" aria-labelledby="provider-settings-tab-providers">
      <div className="provider-registration-layout">
        <div className="provider-tabs">
          <div className="provider-tabs-list" role="tablist" aria-label="Proveedores">
          {PROVIDER_TABS.map(provider => {
            const providerRegistration = registrations[provider.id]
            const providerState = provider.id === 'ollama' ? ollamaStatus?.state : provider.id === 'codex' ? codexStatus?.state ?? providerRegistration?.state : providerRegistration?.state
            const usable = providerUsable(providerState)
              || (provider.id === 'codex' && providerUsable(registrations['openai-platform']?.state))
            const providerIndex = PROVIDER_TABS.findIndex(item => item.id === provider.id)
            return <button
              key={provider.id}
              type="button"
              role="tab"
              id={`provider-tab-${provider.id}`}
              aria-selected={selectedProvider === provider.id}
              aria-controls={`provider-panel-${provider.id}`}
              tabIndex={selectedProvider === provider.id ? 0 : -1}
              className={`provider-tab ${usable ? 'usable' : 'unavailable'}${selectedProvider === provider.id ? ' active' : ''}`}
              onClick={() => setSelectedProvider(provider.id)}
              onKeyDown={event => {
                const direction = event.key === 'ArrowDown' || event.key === 'ArrowRight' ? 1 : event.key === 'ArrowUp' || event.key === 'ArrowLeft' ? -1 : 0
                if (event.key === 'Home' || event.key === 'End' || direction !== 0) {
                  event.preventDefault()
                  const nextIndex = event.key === 'Home' ? 0 : event.key === 'End' ? PROVIDER_TABS.length - 1 : (providerIndex + direction + PROVIDER_TABS.length) % PROVIDER_TABS.length
                  const nextProvider = PROVIDER_TABS[nextIndex]
                  setSelectedProvider(nextProvider.id)
                  document.getElementById(`provider-tab-${nextProvider.id}`)?.focus()
                }
              }}
            >
              <img className="provider-tab-logo" src={provider.logo} alt="" aria-hidden="true" />
              <span>{provider.id === 'codex' ? 'OpenAI' : provider.label}</span>
              <span className={`provider-tab-status sr-only ${usable ? 'usable' : 'unavailable'}`} role="status" aria-label={usable ? 'REGISTRADO · ACTIVADO' : 'NO REGISTRADO · NO DISPONIBLE'}>
                {usable ? 'REGISTRADO · ACTIVADO' : 'NO REGISTRADO · NO DISPONIBLE'}
              </span>
            </button>
          })}
          </div>
        </div>

        <section className="provider-pane" role="tabpanel" id={`provider-panel-${selectedProvider}`} aria-labelledby={`provider-tab-${selectedProvider}`}>
          {selectedProvider !== 'ollama' && <div className="provider-pane-heading">
            <div><h3>{selectedProvider === 'codex' ? 'OpenAI' : activeProvider.label}</h3>{selectedProvider !== 'codex' && <p>{activeProvider.summary}</p>}</div>
            {selectedProvider !== 'codex' && <span className={`provider-state ${state === 'ready' ? 'ready' : state === 'configured_unverified' ? 'pending' : 'neutral'}`} role="status">{statusLabel(state)}</span>}
          </div>}
          {selectedProvider === 'ollama'
            ? <OllamaProviderSettings onStatusChange={summary => { setOllamaStatus(summary); onStatusChange?.(summary) }} />
            : selectedProvider === 'codex'
              ? <div className="openai-provider-settings">
                <section className="provider-card openai-account" aria-labelledby="openai-chatgpt-title">
                  <div className="openai-account-heading"><h4 id="openai-chatgpt-title">ChatGPT / Codex</h4><span className="provider-state" role="status">{statusLabel(codexStatus?.state ?? registrations.codex?.state)}</span></div>
                  <CodexProviderSettings registration={registrations.codex} onStatusChange={setCodexStatus} onSaved={updated => setRegistrations(current => ({ ...current, codex: updated }))} />
                </section>
                <section className="provider-card openai-account" aria-labelledby="openai-platform-title">
                  <div className="openai-account-heading"><h4 id="openai-platform-title">OpenAI Platform</h4><span className="provider-state" role="status">{statusLabel(registrations['openai-platform']?.state)}</span></div>
                  <ProviderRegistrationForm compact provider={OPENAI_PLATFORM} registration={registrations['openai-platform']} onRefresh={refreshRegistry} onSaved={updated => setRegistrations(current => ({ ...current, 'openai-platform': updated }))} />
                </section>
              </div>
              : <ProviderRegistrationForm key={selectedProvider} provider={activeProvider} registration={registration} onRefresh={refreshRegistry} onSaved={updated => setRegistrations(current => ({ ...current, [selectedProvider]: updated }))} />}
          {registryError && <p className="provider-alert error" role="alert">{registryError}</p>}
          {loadingRegistry && <p className="provider-footnote" role="status">Cargando registros guardados…</p>}
        </section>
      </div>
      </div>}
    </section>
  )
}

type CodexSession = { authenticated: boolean; auth_mode?: 'chatgpt' | 'api_key' | null; plan_type?: string | null; models: Array<{ model_id: string; display_name: string; is_default: boolean }> }
type CodexLogin = { login_id?: string; auth_url?: string; state: 'pending' | 'completed' | 'failed' | 'expired'; registration?: Registration; error?: string | null }

function CodexProviderSettings({ registration, onSaved, onStatusChange }: {
  registration?: Registration
  onSaved: (registration: Registration) => void
  onStatusChange: (status: ProviderStatusSummary) => void
}) {
  const [session, setSession] = useState<CodexSession | null>(null)
  const [modelId, setModelId] = useState(registration?.model_id ?? '')
  const [loginId, setLoginId] = useState('')
  const [authUrl, setAuthUrl] = useState('')
  const [loginMode, setLoginMode] = useState<'chatgpt' | 'api_key'>('chatgpt')
  const [apiKey, setApiKey] = useState('')
  const [startingLogin, setStartingLogin] = useState(false)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [verifying, setVerifying] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  const loadSession = async (changed = false) => {
    const response = await fetch('/api/providers/codex/session')
    if (!response.ok) throw new Error(await safeError(response))
    const result = await response.json() as CodexSession
    setSession(result)
    if (result.auth_mode) setLoginMode(result.auth_mode)
    setModelId(current => result.models.some(item => item.model_id === current) ? current : result.models.find(item => item.is_default)?.model_id ?? result.models[0]?.model_id ?? '')
    onStatusChange({ state: result.authenticated ? registration?.model_id ? !changed && registration.state === 'ready' ? 'ready' : 'configured_unverified' : 'authenticated' : 'needs_authentication', auth_mode: result.authenticated ? 'codex_cli' : null })
  }

  useEffect(() => {
    void loadSession().catch(cause => setError(cause instanceof Error ? cause.message : 'No se pudo consultar la sesión de Codex.')).finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (!loginId) return
    let active = true
    const timer = window.setInterval(() => {
      void fetch(`/api/providers/codex/login/${encodeURIComponent(loginId)}`)
        .then(async response => {
          if (!response.ok) throw new Error(await safeError(response))
          return response.json() as Promise<{ state: string; error?: string | null }>
        })
        .then(async result => {
          if (!active || result.state === 'pending') return
          window.clearInterval(timer)
          setLoginId('')
          setAuthUrl('')
          if (result.state !== 'completed') {
            setError(result.error ?? 'Codex no completó el inicio de sesión.')
            return
          }
          await loadSession(true)
          setNotice('ChatGPT conectado.')
        })
        .catch(cause => {
          if (!active) return
          window.clearInterval(timer)
          setLoginId('')
          setError(cause instanceof Error ? cause.message : 'No se pudo confirmar el inicio de sesión.')
        })
    }, 1200)
    return () => { active = false; window.clearInterval(timer) }
  }, [loginId])

  const startLogin = async () => {
    setStartingLogin(true); setError(''); setNotice(''); setAuthUrl('')
    const authWindow = loginMode === 'chatgpt' ? window.open('about:blank', '_blank') : null
    if (authWindow) authWindow.opener = null
    try {
      const response = await fetch('/api/providers/codex/login', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ auth_mode: loginMode, ...(loginMode === 'api_key' ? { api_key: apiKey } : {}) }),
      })
      setApiKey('')
      if (!response.ok) throw new Error(await safeError(response))
      const result = await response.json() as CodexLogin
      if (result.registration) onSaved(result.registration)
      if (result.state === 'completed') {
        await loadSession(true)
        setNotice('API key conectada a Codex.')
      } else if (result.state === 'pending' && result.login_id && result.auth_url) {
        setLoginId(result.login_id)
        setAuthUrl(result.auth_url)
        if (authWindow) authWindow.location.href = result.auth_url
        else setNotice('Abre el enlace para autorizar ChatGPT.')
      } else throw new Error('Codex no devolvió un inicio de sesión válido.')
    } catch (cause) {
      authWindow?.close()
      setError(cause instanceof Error ? cause.message : 'No se pudo iniciar sesión con Codex.')
    } finally { setApiKey(''); setStartingLogin(false) }
  }

  const saveAndVerifyModel = async (event: FormEvent) => {
    event.preventDefault()
    setSaving(true); setError(''); setNotice('')
    try {
      const response = await fetch('/api/providers/registry/codex', {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ auth_mode: 'codex_cli', model_id: modelId }),
      })
      if (!response.ok) throw new Error(await safeError(response))
      const result = await response.json() as Registration
      onSaved(result)
      onStatusChange({ state: result.state as ProviderState, auth_mode: 'codex_cli' })
      setSaving(false)
      setVerifying(true)
      const verifyResponse = await fetch('/api/providers/registry/codex/verify', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model_id: modelId }),
      })
      if (!verifyResponse.ok) throw new Error(await safeError(verifyResponse))
      const verified = await verifyResponse.json() as Registration
      onSaved(verified)
      onStatusChange({ state: verified.state as ProviderState, auth_mode: 'codex_cli' })
      setNotice(`Acceso comprobado para ${modelId}. Codex completó una solicitud breve de verificación.`)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'El modelo se guardó, pero no se pudo comprobar el acceso. Revisa la conexión e inténtalo de nuevo.')
    } finally { setSaving(false); setVerifying(false) }
  }

  const authenticated = session?.authenticated === true
  return <div className="codex-provider-settings">
    <section className="provider-steps" aria-label="Inicio de sesión de Codex">
      <h4>{authenticated ? session.auth_mode === 'api_key' ? 'API key conectada' : 'ChatGPT conectado' : 'Conectar Codex'}</h4>
      <fieldset className="auth-choice-group" disabled={loading || startingLogin || Boolean(loginId) || saving || verifying}>
        <legend className="sr-only">Inicio de sesión de Codex</legend>
        <label className={`auth-choice ${loginMode === 'chatgpt' ? 'active' : ''}`}><input type="radio" name="codex-login-mode" value="chatgpt" checked={loginMode === 'chatgpt'} onChange={() => { setLoginMode('chatgpt'); setApiKey(''); setError(''); setNotice('') }} /><span><strong>ChatGPT</strong></span></label>
        <label className={`auth-choice ${loginMode === 'api_key' ? 'active' : ''}`}><input type="radio" name="codex-login-mode" value="api_key" checked={loginMode === 'api_key'} onChange={() => { setLoginMode('api_key'); setError(''); setNotice('') }} /><span><strong>API key</strong></span></label>
      </fieldset>
      <form className="provider-registration-form codex-login-form" onSubmit={event => { event.preventDefault(); void startLogin() }}>
        {loginMode === 'api_key' && <label className="provider-field" htmlFor="codex-api-key">API key de Codex<input id="codex-api-key" type="password" autoComplete="new-password" spellCheck={false} value={apiKey} onChange={event => setApiKey(event.target.value)} required disabled={startingLogin || saving || verifying} /></label>}
        <button className="provider-primary" type="submit" disabled={loading || startingLogin || Boolean(loginId) || saving || verifying || (loginMode === 'api_key' && !apiKey.trim())}>{startingLogin ? 'Conectando…' : loginId ? 'Esperando autorización…' : loginMode === 'api_key' ? 'Conectar API key a Codex' : 'Iniciar sesión con ChatGPT'}</button>
      </form>
      {loginId && authUrl && <p><a href={authUrl} target="_blank" rel="noreferrer">Abrir página de autorización de Codex</a></p>}
      {authenticated && session.plan_type && <p className="provider-footnote">Plan {session.plan_type}</p>}
    </section>
    {authenticated && <form className="provider-registration-form" onSubmit={event => void saveAndVerifyModel(event)}>
      <label className="provider-field" htmlFor="codex-model"><span>Modelo de Codex</span>
        <select id="codex-model" value={modelId} onChange={event => setModelId(event.target.value)} required disabled={!session.models.length || startingLogin || Boolean(loginId) || saving || verifying}>
          {session.models.length === 0 && <option value="">El catálogo de modelos no está disponible</option>}
          {session.models.map(model => <option key={model.model_id} value={model.model_id}>{model.display_name}{model.is_default ? ' · predeterminado' : ''}</option>)}
        </select>
      </label>
      <p className="provider-footnote">La prueba consume uso {session.auth_mode === 'api_key' ? 'facturable de API' : 'del plan'}.</p>
      <div className="provider-form-actions"><button className="provider-primary" type="submit" disabled={startingLogin || Boolean(loginId) || saving || verifying || !modelId}>{saving ? 'Guardando…' : verifying ? 'Comprobando acceso…' : 'Guardar y comprobar acceso'}</button></div>
    </form>}
    {loading && <p className="provider-footnote" role="status">Consultando Codex…</p>}
    {error && <p className="provider-alert error" role="alert">{error}</p>}
    {notice && <p className="provider-alert notice" role="status">{notice}</p>}
  </div>
}

function ProviderRegistrationForm({ provider, registration, onSaved, onRefresh, compact = false }: { provider: ProviderDefinition; registration?: Registration; onSaved: (registration: Registration) => void; onRefresh: () => Promise<void>; compact?: boolean }) {
  const initialMode = registration?.auth_mode && provider.registrationModes.includes(registration.auth_mode) ? registration.auth_mode : provider.defaultMode
  const [authMode, setAuthMode] = useState<RegistrationMode>(initialMode)
  const [apiKey, setApiKey] = useState('')
  const [modelId, setModelId] = useState(registration?.model_id ?? '')
  const [baseUrl, setBaseUrl] = useState(registration?.base_url ?? '')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [verifying, setVerifying] = useState(false)
  const [copilotAuthenticated, setCopilotAuthenticated] = useState<boolean | null>(null)
  const [checkingCopilotSession, setCheckingCopilotSession] = useState(false)
  const [startingCopilotLogin, setStartingCopilotLogin] = useState(false)
  const [copilotModels, setCopilotModels] = useState<ProviderModel[]>([])
  const [loadingCopilotModels, setLoadingCopilotModels] = useState(false)
  const [copilotLogin, setCopilotLogin] = useState<{ login_id: string; user_code?: string | null; verification_uri?: string | null } | null>(null)

  const loadCopilotModels = useCallback(async () => {
    if (provider.id !== 'github-copilot') return
    if (authMode === 'copilot_cli' && copilotAuthenticated !== true) {
      setError('Inicia sesión en GitHub antes de cargar los modelos disponibles.')
      return
    }
    if (authMode === 'token' && !apiKey && !registration?.has_credential) {
      setError('Introduce un token de GitHub antes de cargar los modelos disponibles.')
      return
    }
    setLoadingCopilotModels(true)
    setError('')
    setNotice('')
    try {
      const response = await fetch('/api/providers/github-copilot/models', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ auth_mode: authMode, ...(authMode === 'token' && apiKey ? { api_key: apiKey } : {}) }),
      })
      if (!response.ok) throw new Error(await safeError(response))
      const result = await response.json() as { models?: ProviderModel[] }
      const available = Array.isArray(result.models) ? result.models : []
      setCopilotModels(available)
      setModelId(current => available.some(model => model.model_id === current) ? current : available[0]?.model_id ?? '')
      setNotice(available.length
        ? `Se han cargado ${available.length} modelos disponibles en GitHub Copilot.`
        : 'GitHub Copilot no devolvió modelos disponibles para esta sesión.')
    } catch (cause) {
      setCopilotModels([])
      setError(cause instanceof Error ? cause.message : 'No se pudieron cargar los modelos de GitHub Copilot.')
    } finally { setLoadingCopilotModels(false) }
  }, [apiKey, authMode, copilotAuthenticated, provider.id, registration?.has_credential])

  useEffect(() => {
    if (registration?.auth_mode && provider.registrationModes.includes(registration.auth_mode)) setAuthMode(registration.auth_mode)
    setModelId(registration?.model_id ?? '')
    setBaseUrl(registration?.base_url ?? '')
  }, [provider.id, registration?.updated_at])

  useEffect(() => {
    if (provider.id !== 'github-copilot' || authMode !== 'copilot_cli') {
      setCopilotAuthenticated(null)
      return
    }
    let active = true
    setCheckingCopilotSession(true)
    void fetch('/api/providers/github-copilot/session')
      .then(async response => {
        if (!response.ok) throw new Error(await safeError(response))
        return response.json() as Promise<{ authenticated: boolean }>
      })
      .then(result => { if (active) setCopilotAuthenticated(result.authenticated) })
      .catch(cause => { if (active) setError(cause instanceof Error ? cause.message : 'No se pudo consultar la sesión de GitHub Copilot.') })
      .finally(() => { if (active) setCheckingCopilotSession(false) })
    return () => { active = false }
  }, [provider.id, authMode])

  useEffect(() => {
    if (provider.id === 'github-copilot' && authMode === 'copilot_cli' && copilotAuthenticated === true) {
      void loadCopilotModels()
    } else if (provider.id === 'github-copilot') {
      setCopilotModels([])
    }
  }, [provider.id, authMode, copilotAuthenticated, loadCopilotModels])

  useEffect(() => {
    if (!copilotLogin) return
    let active = true
    const timer = window.setInterval(() => {
      void fetch(`/api/providers/github-copilot/login/${encodeURIComponent(copilotLogin.login_id)}`)
        .then(async response => {
          if (!response.ok) throw new Error(await safeError(response))
          return response.json() as Promise<{ state: string; error?: string | null }>
        })
        .then(result => {
          if (!active || result.state === 'pending' || result.state === 'starting') return
          window.clearInterval(timer)
          setCopilotLogin(null)
          if (result.state === 'completed') {
            setCopilotAuthenticated(true)
            setNotice('Sesión de GitHub Copilot conectada. Ya puedes guardar y comprobar el modelo.')
          } else {
            setError(result.error ?? 'GitHub Copilot no completó el inicio de sesión del dispositivo.')
          }
        })
        .catch(cause => {
          if (!active) return
          window.clearInterval(timer)
          setCopilotLogin(null)
          setError(cause instanceof Error ? cause.message : 'No se pudo confirmar el inicio de sesión de GitHub Copilot.')
        })
    }, 1200)
    return () => { active = false; window.clearInterval(timer) }
  }, [copilotLogin?.login_id])

  const startCopilotLogin = async () => {
    setError(''); setNotice('')
    const authWindow = window.open('about:blank', '_blank')
    if (authWindow) authWindow.opener = null
    setStartingCopilotLogin(true)
    try {
      const response = await fetch('/api/providers/github-copilot/login', { method: 'POST' })
      if (!response.ok) throw new Error(await safeError(response))
      const result = await response.json() as { login_id: string; state: string; user_code?: string | null; verification_uri?: string | null }
      if (authWindow && result.verification_uri) authWindow.location.href = result.verification_uri
      else authWindow?.close()
      if (result.state === 'completed') {
        setCopilotAuthenticated(true)
        setNotice('Sesión de GitHub Copilot conectada.')
      } else {
        setCopilotLogin(result)
        if (!authWindow) setNotice('Abre GitHub en el enlace que aparece y escribe el código de un solo uso.')
      }
    } catch (cause) {
      authWindow?.close()
      setError(cause instanceof Error ? cause.message : 'No se pudo iniciar el acceso de GitHub Copilot.')
    } finally { setStartingCopilotLogin(false) }
  }

  const steps = provider.steps[authMode] ?? []
  const commands = provider.commands?.[authMode] ?? []
  const needsSecret = authMode === 'api_key' || authMode === 'token'
  const integrated = registration?.runtime_support === 'chat_and_agent_runner'
  const unsavedChanges = authMode !== registration?.auth_mode || modelId.trim() !== (registration?.model_id || '') || baseUrl.trim() !== (registration?.base_url || '') || Boolean(apiKey)

  const saveRegistration = async (event: FormEvent) => {
    event.preventDefault()
    setSaving(true)
    setError('')
    setNotice('')
    let savedRegistration: Registration | null = null
    try {
      const body: { auth_mode: RegistrationMode; model_id?: string; base_url?: string; api_key?: string } = { auth_mode: authMode }
      if (provider.id === 'github-copilot' && authMode === 'copilot_cli' && copilotAuthenticated !== true) {
        throw new Error('Inicia sesión en GitHub con el código de un solo uso antes de comprobar el modelo.')
      }
      if (modelId.trim()) body.model_id = modelId.trim()
      if (baseUrl.trim()) body.base_url = baseUrl.trim()
      if (apiKey) body.api_key = apiKey
      const response = await fetch(`/api/providers/registry/${provider.id}`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
      })
      if (!response.ok) throw new Error(await safeError(response))
      const result = await response.json() as Registration
      savedRegistration = result
      onSaved(result)
      setApiKey('')
      if (result.runtime_support === 'chat_and_agent_runner') {
        setSaving(false)
        setVerifying(true)
        const verifyResponse = await fetch(`/api/providers/registry/${provider.id}/verify`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ model_id: modelId.trim() }),
        })
        if (!verifyResponse.ok) throw new Error(await safeError(verifyResponse))
        const verified = await verifyResponse.json() as Registration
        onSaved({ ...result, ...verified, provider_id: provider.id, model_id: modelId.trim() })
        setNotice(`Acceso comprobado para ${provider.label} · ${modelId.trim()}. El proveedor completó una inferencia breve.`)
      } else {
        setNotice('Registro guardado. Este proveedor todavía no está integrado con el chat ni con Agent Runner.')
      }
    } catch (cause) {
      if (savedRegistration) {
        onSaved({ ...savedRegistration, state: 'configured_unverified', last_verified_at: undefined })
        await onRefresh()
      }
      setError(cause instanceof Error ? cause.message : 'No se pudo guardar el registro.')
    } finally { setSaving(false) }
  }

  return (
    <form className="provider-registration-form" onSubmit={event => void saveRegistration(event)}>
      {(!compact || provider.registrationModes.length > 1) && <div className="provider-method-tabs" role="tablist" aria-label={`Métodos de registro de ${provider.label}`}>
        {provider.registrationModes.map(mode => <button
          key={mode}
          type="button"
          role="tab"
          aria-selected={authMode === mode}
          aria-controls="provider-registration-panel"
          tabIndex={authMode === mode ? 0 : -1}
          id={`provider-method-${mode}`}
          className={`provider-method-tab${authMode === mode ? ' active' : ''}`}
          disabled={saving || verifying}
          onClick={() => { setAuthMode(mode); setError(''); setNotice(''); setApiKey(''); if (provider.id === 'github-copilot') { setCopilotModels([]); setModelId('') } }}
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
      </div>}

      <div id="provider-registration-panel" role={compact && provider.registrationModes.length === 1 ? undefined : 'tabpanel'} aria-label={`${provider.label}: ${modeLabel(authMode)}`}>
      {compact ? <details className="provider-compact-instructions"><summary>Pasos de registro</summary><ol>{steps.map(step => <li key={step}>{step}</li>)}</ol></details> : <section className="provider-steps" aria-label="Pasos de registro">
        <h4>Pasos de registro</h4>
        <ol>{steps.map(step => <li key={step}>{step}</li>)}</ol>
        {commands.length > 0 && <div className="provider-commands">{commands.map(command => <code key={command}>{command}</code>)}</div>}
      </section>}

      {provider.id === 'github-copilot' && authMode === 'copilot_cli' && <section className="provider-device-login" aria-label="Inicio de sesión de GitHub Copilot">
        <div><strong>{copilotAuthenticated ? 'Sesión de GitHub Copilot conectada' : 'Conecta tu cuenta de GitHub'}</strong><p>{copilotAuthenticated ? 'La sesión está disponible para comprobar el modelo.' : 'ADL solicitará un código de dispositivo de un solo uso. No necesitas pegar un token.'}</p></div>
        {!copilotAuthenticated && <button className="provider-secondary" type="button" onClick={() => void startCopilotLogin()} disabled={checkingCopilotSession || startingCopilotLogin || Boolean(copilotLogin)}>{checkingCopilotSession ? 'Consultando sesión…' : startingCopilotLogin ? 'Solicitando código…' : copilotLogin ? 'Esperando autorización…' : 'Iniciar sesión con GitHub'}</button>}
        {copilotLogin?.user_code && <div className="provider-device-code"><span>Código de un solo uso</span><strong>{copilotLogin.user_code}</strong><a href={copilotLogin.verification_uri ?? 'https://github.com/login/device'} target="_blank" rel="noreferrer">Abrir github.com/login/device</a></div>}
      </section>}

      {needsSecret && <div className="provider-field">
        <label htmlFor={`${provider.id}-credential`}>{authMode === 'token' ? 'Token de GitHub' : 'API key'} <span>(solo escritura)</span></label>
        <input id={`${provider.id}-credential`} type="password" autoComplete="new-password" value={apiKey} onChange={event => setApiKey(event.target.value)} placeholder={registration?.has_credential ? 'Hay una credencial guardada; deja vacío para conservarla' : 'Pega aquí la credencial'} spellCheck={false} disabled={saving || verifying} />
        <small>{compact ? 'La clave se guarda en el almacén seguro del sistema.' : 'ADL no muestra la credencial guardada. Se almacena en el almacén seguro del sistema.'}</small>
      </div>}

      {provider.baseUrlLabel && <div className="provider-field">
        <label htmlFor={`${provider.id}-base-url`}>{provider.baseUrlLabel}</label>
        <input id={`${provider.id}-base-url`} type="url" value={baseUrl} onChange={event => setBaseUrl(event.target.value)} placeholder={provider.baseUrlPlaceholder} autoComplete="url" disabled={saving || verifying} />
      </div>}

      {provider.id === 'github-copilot' ? <div className="provider-field">
        <label htmlFor="github-copilot-model">Modelo disponible de GitHub Copilot</label>
        <select id="github-copilot-model" required={integrated} disabled={saving || verifying || loadingCopilotModels} value={modelId} onChange={event => setModelId(event.target.value)}>
          <option value="">{copilotModels.length ? 'Selecciona un modelo…' : 'Carga los modelos disponibles…'}</option>
          {copilotModels.map(model => <option key={model.model_id} value={model.model_id}>{model.display_name}</option>)}
        </select>
        <button className="provider-secondary" type="button" onClick={() => void loadCopilotModels()} disabled={loadingCopilotModels || (authMode === 'copilot_cli' && copilotAuthenticated !== true) || (authMode === 'token' && !apiKey && !registration?.has_credential)}>{loadingCopilotModels ? 'Cargando modelos…' : 'Cargar modelos disponibles'}</button>
      </div> : <div className="provider-field">
        <label htmlFor={`${provider.id}-model`}>Modelo predeterminado {!integrated && <span>(opcional)</span>}</label>
        <input id={`${provider.id}-model`} type="text" required={integrated} disabled={saving || verifying} value={modelId} onChange={event => setModelId(event.target.value)} placeholder={provider.modelPlaceholder} spellCheck={false} />
      </div>}

      {integrated ? <div className={`provider-connection ${registration.state === 'ready' ? 'verified' : ''}`} role="note">
        <strong>Disponible para chat de agentes y Agent Runner</strong>
        <p>{compact ? 'Guarda y comprueba el modelo para confirmar el acceso.' : 'ADL puede usar este proveedor y modelo en el perfil del agente. Guarda el registro y comprueba el acceso para confirmar tus credenciales.'}{registration.last_verified_at ? ` Última respuesta comprobada: ${new Date(registration.last_verified_at).toLocaleString()}.` : ''}</p>
        <p>{compact ? 'La prueba puede consumir uso facturable.' : 'La comprobación envía una inferencia breve y puede consumir una pequeña cantidad de uso facturable.'}</p>
      </div> : <div className="provider-unverified" role="note">
        <strong>El registro no confirma acceso en vivo</strong>
        <p>Este formulario guarda la modalidad y los datos de registro. ADL aún no usa este proveedor en chat ni en ejecuciones de agentes.</p>
      </div>}

      {error && <p className="provider-alert error" role="alert">{error}</p>}
      {notice && <p className="provider-alert notice" role="status">{notice}</p>}
      {integrated && unsavedChanges && <p className="provider-footnote">Guarda los cambios para comprobar esta configuración.</p>}
      <div className="provider-form-actions"><button className="provider-primary" type="submit" disabled={saving || verifying || startingCopilotLogin || Boolean(copilotLogin) || (provider.id === 'github-copilot' && authMode === 'copilot_cli' && copilotAuthenticated !== true)}>{saving ? 'Guardando…' : verifying ? 'Comprobando acceso…' : integrated ? 'Guardar y comprobar acceso' : 'Guardar registro'}</button></div>
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
  const [activeSection, setActiveSection] = useState<'access' | 'model'>('access')
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
      setModelId(current => available.some(model => model.model_id === current) ? current : available.length === 1 ? available[0].model_id : '')
      if (!available.length) setNotice('Sin modelos. Revisa el acceso y recarga la lista.')
      else setNotice(`${available.length} modelos encontrados. Comprueba el acceso al elegido.`)
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
      setNotice('Acceso guardado.')
      await fetchModels()
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'No se pudo guardar la configuración de Ollama.')
    } finally {
      setApiKey('')
      setSaving(false)
    }
  }

  const verifyConfiguration = async () => {
    if (!modelId.trim()) { setError('Elige un modelo antes de comprobar su disponibilidad.'); return }
    if (status?.auth_mode !== authMode || apiKey.length > 0) {
      setError('Guarda primero los cambios en Acceso.')
      setActiveSection('access')
      return
    }
    setVerifying(true)
    setError('')
    setNotice('')
    setVerification('')
    try {
      if (status.model_id !== modelId.trim()) {
        const savedResponse = await fetch('/api/providers/ollama/config', {
          method: 'PUT', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ auth_mode: authMode, model_id: modelId.trim() }),
        })
        if (!savedResponse.ok) throw new Error(await safeError(savedResponse))
        const saved = await savedResponse.json() as ProviderStatus
        setStatus(saved)
        onStatusChange?.(saved)
      }
      const response = await fetch('/api/providers/ollama/verify', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ model_id: modelId.trim() }),
      })
      if (!response.ok) throw new Error(await safeError(response))
      const result = await response.json()
      setVerification(result.generation_performed ? `Acceso comprobado: ${result.model_id}.` : `Modelo no disponible: ${result.model_id ?? ''} (${result.state}).`)
      await loadStatus()
    } catch (cause) {
      await loadStatus()
      setError(cause instanceof Error ? cause.message : 'Falló la comprobación de Ollama.')
    } finally { setVerifying(false) }
  }

  return (
    <div className="ollama-provider-settings">
      <div className="provider-method-tabs" role="tablist" aria-label="Configuración de Ollama">
        {(['access', 'model'] as const).map(section => <button
          key={section}
          type="button"
          role="tab"
          id={`ollama-settings-tab-${section}`}
          aria-selected={activeSection === section}
          aria-controls={`ollama-settings-panel-${section}`}
          tabIndex={activeSection === section ? 0 : -1}
          className={`provider-method-tab${activeSection === section ? ' active' : ''}`}
          onClick={() => setActiveSection(section)}
          onKeyDown={event => {
            if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return
            event.preventDefault()
            const nextSection = event.key === 'Home' ? 'access' : event.key === 'End' ? 'model' : section === 'access' ? 'model' : 'access'
            setActiveSection(nextSection)
            document.getElementById(`ollama-settings-tab-${nextSection}`)?.focus()
          }}
        >{section === 'access' ? 'Acceso' : 'Modelo'}</button>)}
      </div>
      <form className="provider-card" role="tabpanel" id="ollama-settings-panel-access" aria-labelledby="ollama-settings-tab-access" hidden={activeSection !== 'access'} onSubmit={event => void saveConfiguration(event)}>
        <fieldset className="auth-choice-group" disabled={saving || verifying || status?.runtime_mode === 'container'}><legend className="sr-only">Método de autenticación de Ollama</legend>
          <label className={`auth-choice ${authMode === 'api_key' ? 'active' : ''}`}><input type="radio" name="ollama-auth-mode" value="api_key" checked={authMode === 'api_key'} onChange={() => { setAuthMode('api_key'); setModels([]); setModelId(''); setNotice(''); setError('') }} /><span><strong>Cloud · API key</strong></span></label>
          <label className={`auth-choice ${authMode === 'local_cli' ? 'active' : ''}`}><input type="radio" name="ollama-auth-mode" value="local_cli" checked={authMode === 'local_cli'} onChange={() => { setAuthMode('local_cli'); setApiKey(''); setModels([]); setModelId(''); setNotice(''); setError('') }} /><span><strong>Ollama local</strong></span></label>
        </fieldset>
        {authMode === 'api_key' ? <div className="provider-field"><label htmlFor="ollama-api-key">API key <span>(solo escritura)</span></label><input id="ollama-api-key" type="password" autoComplete="new-password" value={apiKey} onChange={event => setApiKey(event.target.value)} placeholder="Nueva clave para sustituir la guardada" spellCheck={false} disabled={saving || verifying} /></div> : <div className="cli-instructions"><p>Inicia Ollama en este equipo, guarda el acceso y carga los modelos.</p></div>}
        <button className="provider-primary" type="submit" disabled={saving || verifying || loading || status?.runtime_mode === 'container'}>{saving ? 'Guardando…' : 'Guardar acceso'}</button>
      </form>

      <section className="provider-card" role="tabpanel" id="ollama-settings-panel-model" aria-labelledby="ollama-settings-tab-model" hidden={activeSection !== 'model'}>
        <div className="model-controls">
          <label className="provider-field model-select-field" htmlFor="ollama-model"><span className="sr-only">Modelo</span><select id="ollama-model" value={modelId} onChange={event => setModelId(event.target.value)} disabled={saving || verifying || loading || status?.runtime_mode === 'container'}><option value="">Selecciona un modelo…</option>{models.map(model => <option key={`${model.provider_id}:${model.model_id}`} value={model.model_id}>{model.display_name}</option>)}</select></label>
          <button className="provider-secondary" type="button" onClick={() => void loadModels()} disabled={loadingModels || saving || verifying || status?.runtime_mode === 'container'}>{loadingModels ? 'Cargando…' : 'Cargar modelos'}</button>
        </div>
        {models.length === 0 && !loadingModels && <p className="provider-empty-models">Guarda el acceso y carga los modelos.</p>}
        <div className="model-actions"><button className="provider-secondary" type="button" onClick={() => void verifyConfiguration()} disabled={saving || verifying || loading || !modelId.trim() || status?.runtime_mode === 'container'}>{verifying ? 'Comprobando…' : 'Guardar y comprobar acceso'}</button></div>
        <p className="provider-footnote">La prueba puede consumir uso de Cloud.</p>
      </section>

      {error && <p className="provider-alert error" role="alert">{error}</p>}{notice && <p className="provider-alert notice" role="status">{notice}</p>}{verification && <p className="provider-alert notice" role="status">{verification}</p>}
      {status?.last_verified_at && <p className="provider-footnote">Última comprobación: {new Date(status.last_verified_at).toLocaleString()}</p>}
    </div>
  )
}
