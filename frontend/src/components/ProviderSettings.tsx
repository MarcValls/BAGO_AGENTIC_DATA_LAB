import type {TranslationKey} from '../i18n'
import {useI18n,t,localMessage,errorMessage,apiError,formatDate,formatNumber} from '../i18n'
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
    id: 'ollama', label: 'Ollama', logo: '/brand/ollama.svg', get summary(){return t("core.ProviderSettings.local_service_or_access_to_ollama_cloud_3ffab5")},
    registrationModes: ['local_cli', 'api_key'], defaultMode: 'api_key', modelPlaceholder: 'qwen3:8b',
    steps: {
      local_cli: ["commerce.providers.start_ollama_on_this_computer", "commerce.providers.save_local_mode_so_adl_can_query_the_loopback_service", "commerce.providers.load_the_models_and_choose_one"],
      api_key: ["commerce.providers.create_a_key_from_your_ollama_cloud_account", "commerce.providers.save_it_in_the_system_credential_store", "commerce.providers.load_the_models_and_check_their_availability"]
    }
  },
  {
    id: 'codex', label: 'OpenAI Codex', logo: '/brand/openai.svg', summary: '',
    registrationModes: ['codex_cli'], defaultMode: 'codex_cli', modelPlaceholder: 'gpt-5-codex',
    steps: { codex_cli: ["commerce.providers.sign_in_with_chatgpt_in_the_browser", "commerce.providers.choose_a_model_available_in_your_codex_session", "commerce.providers.save_the_model_to_use_it_in_adl_agents"] }
  },
  {
    id: 'openai-platform', label: 'OpenAI Platform', logo: '/brand/openai.svg', get summary(){return t("core.ProviderSettings.billed_api_connection_to_openai_platform_separate_9211e1")},
    registrationModes: ['api_key'], defaultMode: 'api_key', modelPlaceholder: 'gpt-5.5',
    steps: { api_key: ["commerce.providers.create_a_project_api_key_in_openai_platform", "commerce.providers.paste_it_into_this_secure_form_adl_saves_it_in_the_system_store", "commerce.providers.enter_a_model_to_complete_registration"] }
  },
  {
    id: 'github-copilot', label: 'GitHub Copilot', logo: '/brand/github-copilot.svg', get summary(){return t("core.ProviderSettings.sign_in_to_github_with_a_device_139d60")},
    registrationModes: ['copilot_cli', 'token'], defaultMode: 'copilot_cli', modelPlaceholder: 'gpt-4.1',
    steps: {
      copilot_cli: ["commerce.providers.request_the_one_time_code_from_adl", "commerce.providers.open_github_com_login_device_enter_code_xxxx_xxxx_and_authorize_github_copilot", "commerce.providers.return_to_adl_save_the_model_and_check_access_with_a_real_request"],
      token: ["commerce.providers.create_a_fine_grained_personal_access_token_with_copilot_requests_permission", "commerce.providers.paste_it_here_to_save_it_in_the_system_credential_store", "commerce.providers.enter_a_model_and_check_access_from_adl"]
    }
  },
  {
    id: 'anthropic', label: 'Anthropic', logo: '/brand/anthropic.svg', get summary(){return t("core.ProviderSettings.connection_using_an_anthropic_api_key_bed07d")},
    registrationModes: ['api_key'], defaultMode: 'api_key', modelPlaceholder: 'claude-sonnet-4-5',
    steps: { api_key: ["commerce.providers.create_an_api_key_in_your_anthropic_account", "commerce.providers.paste_it_into_this_secure_form", "commerce.providers.enter_the_model_you_want_to_associate"] }
  },
  {
    id: 'openrouter', label: 'OpenRouter', logo: '/brand/openrouter-official.svg', get summary(){return t("core.ProviderSettings.connection_using_an_api_key_and_model_2a2b0f")},
    registrationModes: ['api_key'], defaultMode: 'api_key', modelPlaceholder: 'anthropic/claude-sonnet-4.5',
    steps: { api_key: ["commerce.providers.create_an_api_key_in_openrouter", "commerce.providers.paste_it_into_this_secure_form", "commerce.providers.enter_the_model_identifier_or_route"] }
  },
  {
    id: 'opencode', label: 'OpenCode', logo: '/brand/opencode.svg', get summary(){return t("core.ProviderSettings.local_or_remote_opencode_endpoint_67eafc")},
    registrationModes: ['local', 'api_key'], defaultMode: 'local', modelPlaceholder: 'default',
    get baseUrlLabel(){return t('commerce.providers.base_url')}, baseUrlPlaceholder: 'http://127.0.0.1:3000',
    steps: {
      local: ["commerce.providers.start_your_opencode_server", "commerce.providers.enter_the_local_or_remote_service_endpoint", "commerce.providers.save_the_model_published_by_the_server"],
      api_key: ["commerce.providers.configure_the_opencode_endpoint", "commerce.providers.add_the_api_key_if_your_endpoint_requires_it", "commerce.providers.save_the_model_published_by_the_server"]
    }
  }
]

const PROVIDER_TABS = PROVIDERS.filter(provider => provider.id !== 'openai-platform')
const OPENAI_PLATFORM = PROVIDERS.find(provider => provider.id === 'openai-platform')!

async function safeError(response: Response): Promise<Error> {
 let body:unknown=null
 try {body=await response.json()}catch { /* preserve HTTP status */ }
 return apiError(body,response.status,'commerce')
}

function statusLabel(state: string | undefined): string {
  if (state === 'ready') return t("core.ProviderSettings.access_verified_9b1fe8")
  if (state === 'authenticated') return t("core.ProviderSettings.signed_in_573996")
  if (state === 'configured_unverified') return t("core.ProviderSettings.registered_unverified_0eca0e")
  if (state === 'needs_authentication') return t("core.ProviderSettings.credential_required_e3103d")
  if (state === 'credential_store_unavailable') return t("core.ProviderSettings.secure_storage_unavailable_6ebab4")
  if (state === 'local_service_unavailable') return t("core.ProviderSettings.local_service_unavailable_09dbdf")
  if (state === 'unsupported_runtime') return t("core.ProviderSettings.unavailable_in_this_environment_bcf740")
  if (state === 'error') return t("core.ProviderSettings.configuration_error_ef6123")
  if(!state||state==='not_configured')return t("core.ProviderSettings.not_registered_4bd4c1")
  return t('commerce.providers.unknown_state',{code:state})
}

function providerUsable(state: string | undefined): boolean {
  return state === 'ready' || state === 'configured_unverified'
}

export default function ProviderSettings({ onStatusChange, onExit }: { onStatusChange?: (status: ProviderStatusSummary) => void; onExit?: () => void }) {
  useI18n()

  const [settingsTab, setSettingsTab] = useState<'providers' | 'models'>('providers')
  const [selectedProvider, setSelectedProvider] = useState<ProviderId>('ollama')
  const [ollamaStatus, setOllamaStatus] = useState<ProviderStatusSummary | null>(null)
  const [codexStatus, setCodexStatus] = useState<ProviderStatusSummary | null>(null)
  const [registrations, setRegistrations] = useState<Record<string, Registration>>({})
  const [loadingRegistry, setLoadingRegistry] = useState(true)
  const [registryError, setRegistryError] = useState<any>('')

  const refreshRegistry = async () => {
    setLoadingRegistry(true)
    setRegistryError('')
    try {
      const response = await fetch('/api/providers/registry')
      if (!response.ok) throw await safeError(response)
      const data = await response.json() as { registrations?: Registration[] }
      const next: Record<string, Registration> = {}
      for (const registration of data.registrations ?? []) next[registration.provider_id] = registration
      setRegistrations(next)
    } catch (cause) {
      setRegistryError(cause instanceof Error ? cause : "commerce.providers.could_not_read_the_provider_registry")
    } finally { setLoadingRegistry(false) }
  }

  useEffect(() => { void refreshRegistry() }, [])

  const activeProvider = PROVIDERS.find(provider => provider.id === selectedProvider) ?? PROVIDERS[0]
  const registration = registrations[selectedProvider]
  const state = selectedProvider === 'ollama' ? ollamaStatus?.state : selectedProvider === 'codex' ? codexStatus?.state ?? registration?.state : registration?.state

  return (
    <section className="provider-settings" aria-label={t("core.ProviderSettings.provider_and_model_settings_6355bf")}>
      <div className="provider-settings-tabs" role="tablist" aria-label={t("core.ProviderSettings.provider_and_model_settings_6355bf")}>
        <button type="button" role="tab" id="provider-settings-tab-providers" aria-selected={settingsTab === 'providers'} aria-controls="provider-settings-panel-providers" tabIndex={settingsTab === 'providers' ? 0 : -1} className={settingsTab === 'providers' ? 'active' : ''} onClick={() => setSettingsTab('providers')}>{t("core.ProviderSettings.providers_bb1bb5")}</button>
        <button type="button" role="tab" id="provider-settings-tab-models" aria-selected={settingsTab === 'models'} aria-controls="provider-settings-panel-models" tabIndex={settingsTab === 'models' ? 0 : -1} className={settingsTab === 'models' ? 'active' : ''} onClick={() => setSettingsTab('models')}>{t("core.ProviderSettings.active_models_2fdf9d")}</button>
      </div>
      {settingsTab === 'models'
        ? <div role="tabpanel" id="provider-settings-panel-models" aria-labelledby="provider-settings-tab-models" className="provider-model-policy-panel"><ModelAssignments onExit={onExit ?? (() => setSettingsTab('providers'))} /></div>
        : <div role="tabpanel" id="provider-settings-panel-providers" aria-labelledby="provider-settings-tab-providers">
      <div className="provider-registration-layout">
        <div className="provider-tabs">
          <div className="provider-tabs-list" role="tablist" aria-label={t("core.ProviderSettings.providers_bb1bb5")}>
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
              <span className={`provider-tab-status sr-only ${usable ? 'usable' : 'unavailable'}`} role="status" aria-label={usable ? t("core.ProviderSettings.registered_enabled_222718") : t("core.ProviderSettings.not_registered_unavailable_7f29c0")}>
                {usable ? t("core.ProviderSettings.registered_enabled_222718") : t("core.ProviderSettings.not_registered_unavailable_7f29c0")}
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
          {registryError && <p className="provider-alert error" role="alert">{errorMessage(registryError)}</p>}
          {loadingRegistry && <p className="provider-footnote" role="status">{t("core.ProviderSettings.loading_saved_registrations_7621f4")}</p>}
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
  useI18n()

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
  const [error, setError] = useState<any>('')
  const [notice, setNotice] = useState<any>('')

  const loadSession = async (changed = false) => {
    const response = await fetch('/api/providers/codex/session')
    if (!response.ok) throw await safeError(response)
    const result = await response.json() as CodexSession
    setSession(result)
    if (result.auth_mode) setLoginMode(result.auth_mode)
    setModelId(current => result.models.some(item => item.model_id === current) ? current : result.models.find(item => item.is_default)?.model_id ?? result.models[0]?.model_id ?? '')
    onStatusChange({ state: result.authenticated ? registration?.model_id ? !changed && registration.state === 'ready' ? 'ready' : 'configured_unverified' : 'authenticated' : 'needs_authentication', auth_mode: result.authenticated ? 'codex_cli' : null })
  }

  useEffect(() => {
    void loadSession().catch(cause => setError(cause instanceof Error ? cause : "commerce.providers.could_not_query_the_codex_session")).finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (!loginId) return
    let active = true
    const timer = window.setInterval(() => {
      void fetch(`/api/providers/codex/login/${encodeURIComponent(loginId)}`)
        .then(async response => {
          if (!response.ok) throw await safeError(response)
          return response.json() as Promise<{ state: string; error?: string | null }>
        })
        .then(async result => {
          if (!active || result.state === 'pending') return
          window.clearInterval(timer)
          setLoginId('')
          setAuthUrl('')
          if (result.state !== 'completed') {
            setError(result.error ? apiError({detail:result.error},200,'commerce') : "commerce.providers.codex_did_not_complete_sign_in")
            return
          }
          await loadSession(true)
          setNotice("core.ProviderSettings.chatgpt_connected_d0d55c")
        })
        .catch(cause => {
          if (!active) return
          window.clearInterval(timer)
          setLoginId('')
          setError(cause instanceof Error ? cause : "commerce.providers.could_not_confirm_sign_in")
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
      if (!response.ok) throw await safeError(response)
      const result = await response.json() as CodexLogin
      if (result.registration) onSaved(result.registration)
      if (result.state === 'completed') {
        await loadSession(true)
        setNotice("core.ProviderSettings.api_key_connected_to_codex_a780d9")
      } else if (result.state === 'pending' && result.login_id && result.auth_url) {
        setLoginId(result.login_id)
        setAuthUrl(result.auth_url)
        if (authWindow) authWindow.location.href = result.auth_url
        else setNotice("core.ProviderSettings.open_the_link_to_authorize_chatgpt_0aae85")
      } else throw new Error("core.ProviderSettings.codex_did_not_return_a_valid_sign_ecf42c")
    } catch (cause) {
      authWindow?.close()
      setError(cause instanceof Error ? cause : "commerce.providers.could_not_sign_in_with_codex")
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
      if (!response.ok) throw await safeError(response)
      const result = await response.json() as Registration
      onSaved(result)
      onStatusChange({ state: result.state as ProviderState, auth_mode: 'codex_cli' })
      setSaving(false)
      setVerifying(true)
      const verifyResponse = await fetch('/api/providers/registry/codex/verify', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model_id: modelId }),
      })
      if (!verifyResponse.ok) throw await safeError(verifyResponse)
      const verified = await verifyResponse.json() as Registration
      onSaved(verified)
      onStatusChange({ state: verified.state as ProviderState, auth_mode: 'codex_cli' })
      setNotice(localMessage("core.ProviderSettings.access_verified_for_p0_codex_completed_a_ee2395",{p0:String(modelId)}))
    } catch (cause) {
      setError(cause instanceof Error ? cause : "commerce.providers.the_model_was_saved_but_access_could_not_be_checked_check_the_connection_and_try_again")
    } finally { setSaving(false); setVerifying(false) }
  }

  const authenticated = session?.authenticated === true
  return <div className="codex-provider-settings">
    <section className="provider-steps" aria-label={t("core.ProviderSettings.codex_sign_in_4d3c60")}>
      <h4>{authenticated ? session.auth_mode === 'api_key' ? t("core.ProviderSettings.api_key_connected_e03982") : t("core.ProviderSettings.chatgpt_connected_1c9aa0") : t("core.ProviderSettings.connect_codex_018035")}</h4>
      <fieldset className="auth-choice-group" disabled={loading || startingLogin || Boolean(loginId) || saving || verifying}>
        <legend className="sr-only">{t("core.ProviderSettings.codex_sign_in_4d3c60")}</legend>
        <label className={`auth-choice ${loginMode === 'chatgpt' ? 'active' : ''}`}><input type="radio" name="codex-login-mode" value="chatgpt" checked={loginMode === 'chatgpt'} onChange={() => { setLoginMode('chatgpt'); setApiKey(''); setError(''); setNotice('') }} /><span><strong>ChatGPT</strong></span></label>
        <label className={`auth-choice ${loginMode === 'api_key' ? 'active' : ''}`}><input type="radio" name="codex-login-mode" value="api_key" checked={loginMode === 'api_key'} onChange={() => { setLoginMode('api_key'); setError(''); setNotice('') }} /><span><strong>{t("core.ProviderSettings.api_key_16f0ee")}</strong></span></label>
      </fieldset>
      <form className="provider-registration-form codex-login-form" onSubmit={event => { event.preventDefault(); void startLogin() }}>
        {loginMode === 'api_key' && <label className="provider-field" htmlFor="codex-api-key">{t("core.ProviderSettings.codex_api_key_a90b27")}<input id="codex-api-key" type="password" autoComplete="new-password" spellCheck={false} value={apiKey} onChange={event => setApiKey(event.target.value)} required disabled={startingLogin || saving || verifying} /></label>}
        <button className="provider-primary" type="submit" disabled={loading || startingLogin || Boolean(loginId) || saving || verifying || (loginMode === 'api_key' && !apiKey.trim())}>{startingLogin ? t("core.ProviderSettings.connecting_cc190a") : loginId ? t("core.ProviderSettings.waiting_for_authorization_ef8195") : loginMode === 'api_key' ? t("core.ProviderSettings.connect_api_key_to_codex_bb57a7") : t("core.ProviderSettings.sign_in_with_chatgpt_0169ea")}</button>
      </form>
      {loginId && authUrl && <p><a href={authUrl} target="_blank" rel="noreferrer">{t("core.ProviderSettings.open_codex_authorization_page_46387d")}</a></p>}
      {authenticated && session.plan_type && <p className="provider-footnote">{t("core.ProviderSettings.plan_fa8ed0")}{' '}{session.plan_type}</p>}
    </section>
    {authenticated && <form className="provider-registration-form" onSubmit={event => void saveAndVerifyModel(event)}>
      <label className="provider-field" htmlFor="codex-model"><span>{t("core.ProviderSettings.codex_model_d11f32")}</span>
        <select id="codex-model" value={modelId} onChange={event => setModelId(event.target.value)} required disabled={!session.models.length || startingLogin || Boolean(loginId) || saving || verifying}>
          {session.models.length === 0 && <option value="">{t("core.ProviderSettings.the_model_catalog_is_unavailable_893ed1")}</option>}
          {session.models.map(model => <option key={model.model_id} value={model.model_id}>{model.display_name}{model.is_default ? t("core.ProviderSettings.default_cc78e4") : ''}</option>)}
        </select>
      </label>
      <p className="provider-footnote">{t("core.ProviderSettings.the_check_consumes_usage_0cd29a")}{' '}{session.auth_mode === 'api_key' ? t("core.ProviderSettings.billed_api_usage_b6f05a") : t("core.ProviderSettings.plan_usage_5aa5d6")}.</p>
      <div className="provider-form-actions"><button className="provider-primary" type="submit" disabled={startingLogin || Boolean(loginId) || saving || verifying || !modelId}>{saving ? t("core.ProviderSettings.saving_3c8dc4") : verifying ? t("core.ProviderSettings.checking_access_d445c7") : t("core.ProviderSettings.save_and_check_access_1a16f4")}</button></div>
    </form>}
    {loading && <p className="provider-footnote" role="status">{t("core.ProviderSettings.checking_codex_6b9d30")}</p>}
    {error && <p className="provider-alert error" role="alert">{errorMessage(error)}</p>}
    {notice && <p className="provider-alert notice" role="status">{errorMessage(notice)}</p>}
  </div>
}

function ProviderRegistrationForm({ provider, registration, onSaved, onRefresh, compact = false }: { provider: ProviderDefinition; registration?: Registration; onSaved: (registration: Registration) => void; onRefresh: () => Promise<void>; compact?: boolean }) {
  useI18n()

  const initialMode = registration?.auth_mode && provider.registrationModes.includes(registration.auth_mode) ? registration.auth_mode : provider.defaultMode
  const [authMode, setAuthMode] = useState<RegistrationMode>(initialMode)
  const [apiKey, setApiKey] = useState('')
  const [modelId, setModelId] = useState(registration?.model_id ?? '')
  const [baseUrl, setBaseUrl] = useState(registration?.base_url ?? '')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<any>('')
  const [notice, setNotice] = useState<any>('')
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
      setError("core.ProviderSettings.sign_in_to_github_before_loading_available_97ba85")
      return
    }
    if (authMode === 'token' && !apiKey && !registration?.has_credential) {
      setError("core.ProviderSettings.enter_a_github_token_before_loading_available_b98877")
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
      if (!response.ok) throw await safeError(response)
      const result = await response.json() as { models?: ProviderModel[] }
      const available = Array.isArray(result.models) ? result.models : []
      setCopilotModels(available)
      setModelId(current => available.some(model => model.model_id === current) ? current : available[0]?.model_id ?? '')
      setNotice(available.length
        ? localMessage('commerce.providers.copilot_model_count',{get count(){return formatNumber(available.length)}})
        : "commerce.providers.github_copilot_returned_no_available_models_for_this_session")
    } catch (cause) {
      setCopilotModels([])
      setError(cause instanceof Error ? cause : "commerce.providers.could_not_load_github_copilot_models")
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
        if (!response.ok) throw await safeError(response)
        return response.json() as Promise<{ authenticated: boolean }>
      })
      .then(result => { if (active) setCopilotAuthenticated(result.authenticated) })
      .catch(cause => { if (active) setError(cause instanceof Error ? cause : "commerce.providers.could_not_query_the_github_copilot_session") })
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
          if (!response.ok) throw await safeError(response)
          return response.json() as Promise<{ state: string; error?: string | null }>
        })
        .then(result => {
          if (!active || result.state === 'pending' || result.state === 'starting') return
          window.clearInterval(timer)
          setCopilotLogin(null)
          if (result.state === 'completed') {
            setCopilotAuthenticated(true)
            setNotice("core.ProviderSettings.github_copilot_session_connected_you_can_now_42017c")
          } else {
            setError(result.error ? apiError({detail:result.error},200,'commerce') : "commerce.providers.github_copilot_did_not_complete_device_sign_in")
          }
        })
        .catch(cause => {
          if (!active) return
          window.clearInterval(timer)
          setCopilotLogin(null)
          setError(cause instanceof Error ? cause : "commerce.providers.could_not_confirm_github_copilot_sign_in")
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
      if (!response.ok) throw await safeError(response)
      const result = await response.json() as { login_id: string; state: string; user_code?: string | null; verification_uri?: string | null }
      if (authWindow && result.verification_uri) authWindow.location.href = result.verification_uri
      else authWindow?.close()
      if (result.state === 'completed') {
        setCopilotAuthenticated(true)
        setNotice("core.ProviderSettings.github_copilot_session_connected_1d4ad4")
      } else {
        setCopilotLogin(result)
        if (!authWindow) setNotice("core.ProviderSettings.open_github_using_the_displayed_link_and_6d70d8")
      }
    } catch (cause) {
      authWindow?.close()
      setError(cause instanceof Error ? cause : "commerce.providers.could_not_start_github_copilot_access")
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
        throw new Error("core.ProviderSettings.sign_in_to_github_using_the_one_912b0f")
      }
      if (modelId.trim()) body.model_id = modelId.trim()
      if (baseUrl.trim()) body.base_url = baseUrl.trim()
      if (apiKey) body.api_key = apiKey
      const response = await fetch(`/api/providers/registry/${provider.id}`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
      })
      if (!response.ok) throw await safeError(response)
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
        if (!verifyResponse.ok) throw await safeError(verifyResponse)
        const verified = await verifyResponse.json() as Registration
        onSaved({ ...result, ...verified, provider_id: provider.id, model_id: modelId.trim() })
        setNotice(localMessage("core.ProviderSettings.access_verified_for_p0_p1_the_provider_9248bb",{p0:String(provider.label),p1:String(modelId.trim())}))
      } else {
        setNotice("core.ProviderSettings.registration_saved_this_provider_is_not_yet_0e714f")
      }
    } catch (cause) {
      if (savedRegistration) {
        onSaved({ ...savedRegistration, state: 'configured_unverified', last_verified_at: undefined })
        await onRefresh()
      }
      setError(cause instanceof Error ? cause : "commerce.providers.could_not_save_the_registration")
    } finally { setSaving(false) }
  }

  return (
    <form className="provider-registration-form" onSubmit={event => void saveRegistration(event)}>
      {(!compact || provider.registrationModes.length > 1) && <div className="provider-method-tabs" role="tablist" aria-label={t("core.ProviderSettings.registration_methods_for_p0_205cac",{p0:String(provider.label)})}>
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

      <div id="provider-registration-panel" role={compact && provider.registrationModes.length === 1 ? undefined : 'tabpanel'} aria-label={t("core.ProviderSettings.p0_p1_07e3a6",{p0:String(provider.label),p1:String(modeLabel(authMode))})}>
      {compact ? <details className="provider-compact-instructions"><summary>{t("core.ProviderSettings.registration_steps_9c8e7e")}</summary><ol>{steps.map(step => <li key={step}>{t(step as TranslationKey)}</li>)}</ol></details> : <section className="provider-steps" aria-label={t("core.ProviderSettings.registration_steps_9c8e7e")}>
        <h4>{t("core.ProviderSettings.registration_steps_9c8e7e")}</h4>
        <ol>{steps.map(step => <li key={step}>{t(step as TranslationKey)}</li>)}</ol>
        {commands.length > 0 && <div className="provider-commands">{commands.map(command => <code key={command}>{command}</code>)}</div>}
      </section>}

      {provider.id === 'github-copilot' && authMode === 'copilot_cli' && <section className="provider-device-login" aria-label={t("core.ProviderSettings.github_copilot_sign_in_3f7f47")}>
        <div><strong>{copilotAuthenticated ? t("core.ProviderSettings.github_copilot_session_connected_218ac5") : t("core.ProviderSettings.connect_your_github_account_2a2443")}</strong><p>{copilotAuthenticated ? t("core.ProviderSettings.the_session_is_available_to_check_the_508a35") : t("core.ProviderSettings.adl_will_request_a_one_time_device_856b44")}</p></div>
        {!copilotAuthenticated && <button className="provider-secondary" type="button" onClick={() => void startCopilotLogin()} disabled={checkingCopilotSession || startingCopilotLogin || Boolean(copilotLogin)}>{checkingCopilotSession ? t("core.ProviderSettings.checking_session_4cb4e3") : startingCopilotLogin ? t("core.ProviderSettings.requesting_code_88344f") : copilotLogin ? t("core.ProviderSettings.waiting_for_authorization_ef8195") : t("core.ProviderSettings.sign_in_with_github_35ab61")}</button>}
        {copilotLogin?.user_code && <div className="provider-device-code"><span>{t("core.ProviderSettings.one_time_code_b30966")}</span><strong>{copilotLogin.user_code}</strong><a href={copilotLogin.verification_uri ?? 'https://github.com/login/device'} target="_blank" rel="noreferrer">{t("core.ProviderSettings.open_github_com_login_device_9e21d8")}</a></div>}
      </section>}

      {needsSecret && <div className="provider-field">
        <label htmlFor={`${provider.id}-credential`}>{authMode === 'token' ? t("core.ProviderSettings.github_token_ccbbe2") : t("core.ProviderSettings.api_key_16f0ee")} <span>{t("core.ProviderSettings.write_only_d50a55")}</span></label>
        <input id={`${provider.id}-credential`} type="password" autoComplete="new-password" value={apiKey} onChange={event => setApiKey(event.target.value)} placeholder={registration?.has_credential ? t("core.ProviderSettings.a_credential_is_saved_leave_empty_to_d072eb") : t("core.ProviderSettings.paste_the_credential_here_a61633")} spellCheck={false} disabled={saving || verifying} />
        <small>{compact ? t("core.ProviderSettings.the_key_is_saved_in_the_system_c67aec") : t("core.ProviderSettings.adl_does_not_display_the_saved_credential_d978cc")}</small>
      </div>}

      {provider.baseUrlLabel && <div className="provider-field">
        <label htmlFor={`${provider.id}-base-url`}>{provider.baseUrlLabel}</label>
        <input id={`${provider.id}-base-url`} type="url" value={baseUrl} onChange={event => setBaseUrl(event.target.value)} placeholder={provider.baseUrlPlaceholder} autoComplete="url" disabled={saving || verifying} />
      </div>}

      {provider.id === 'github-copilot' ? <div className="provider-field">
        <label htmlFor="github-copilot-model">{t("core.ProviderSettings.available_github_copilot_model_f92fc7")}</label>
        <select id="github-copilot-model" required={integrated} disabled={saving || verifying || loadingCopilotModels} value={modelId} onChange={event => setModelId(event.target.value)}>
          <option value="">{copilotModels.length ? t("core.ProviderSettings.select_a_model_088d84") : t("core.ProviderSettings.load_the_available_models_695e3d")}</option>
          {copilotModels.map(model => <option key={model.model_id} value={model.model_id}>{model.display_name}</option>)}
        </select>
        <button className="provider-secondary" type="button" onClick={() => void loadCopilotModels()} disabled={loadingCopilotModels || (authMode === 'copilot_cli' && copilotAuthenticated !== true) || (authMode === 'token' && !apiKey && !registration?.has_credential)}>{loadingCopilotModels ? t("core.ProviderSettings.loading_models_172b28") : t("core.ProviderSettings.load_available_models_8b83fa")}</button>
      </div> : <div className="provider-field">
        <label htmlFor={`${provider.id}-model`}>{t("core.ProviderSettings.default_model_a1e90f")}{' '}{!integrated && <span>{t("core.ProviderSettings.optional_83eddb")}</span>}</label>
        <input id={`${provider.id}-model`} type="text" required={integrated} disabled={saving || verifying} value={modelId} onChange={event => setModelId(event.target.value)} placeholder={provider.modelPlaceholder} spellCheck={false} />
      </div>}

      {integrated ? <div className={`provider-connection ${registration.state === 'ready' ? 'verified' : ''}`} role="note">
        <strong>{t("core.ProviderSettings.available_for_agent_chat_and_agent_runs_b51079")}</strong>
        <p>{compact ? t("core.ProviderSettings.save_and_check_the_model_to_confirm_c02887") : t("core.ProviderSettings.adl_can_use_this_provider_and_model_1facef")}{registration.last_verified_at ? t('commerce.providers.last_verified_response',{date:formatDate(registration.last_verified_at)}) : ''}</p>
        <p>{compact ? t("core.ProviderSettings.the_check_may_consume_billed_usage_18f9e4") : t("core.ProviderSettings.the_check_sends_a_short_inference_and_e91c49")}</p>
      </div> : <div className="provider-unverified" role="note">
        <strong>{t("core.ProviderSettings.registration_does_not_confirm_live_access_a64b94")}</strong>
        <p>{t("core.ProviderSettings.this_form_saves_the_registration_method_and_b66119")}</p>
      </div>}

      {error && <p className="provider-alert error" role="alert">{errorMessage(error)}</p>}
      {notice && <p className="provider-alert notice" role="status">{errorMessage(notice)}</p>}
      {integrated && unsavedChanges && <p className="provider-footnote">{t("core.ProviderSettings.save_the_changes_to_check_this_configuration_c820e9")}</p>}
      <div className="provider-form-actions"><button className="provider-primary" type="submit" disabled={saving || verifying || startingCopilotLogin || Boolean(copilotLogin) || (provider.id === 'github-copilot' && authMode === 'copilot_cli' && copilotAuthenticated !== true)}>{saving ? t("core.ProviderSettings.saving_3c8dc4") : verifying ? t("core.ProviderSettings.checking_access_d445c7") : integrated ? t("core.ProviderSettings.save_and_check_access_1a16f4") : t("core.ProviderSettings.save_registration_73b38a")}</button></div>
      </div>
    </form>
  )
}

function modeLabel(mode: RegistrationMode): string {
  if (mode === 'codex_cli') return 'Codex CLI'
  if (mode === 'copilot_cli') return 'Copilot CLI'
  if (mode === 'token') return t('commerce.providers.access_token')
  if (mode === 'local_cli') return t("core.ProviderSettings.local_ollama_f69f95")
  if (mode === 'local') return t("core.ProviderSettings.local_endpoint_fb8ca1")
  return t("core.ProviderSettings.api_key_16f0ee")
}

function OllamaProviderSettings({ onStatusChange }: { onStatusChange?: (status: ProviderStatusSummary) => void }) {
  useI18n()

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
  const [error, setError] = useState<any>('')
  const [notice, setNotice] = useState<any>('')
  const [verification, setVerification] = useState<any>('')

  const fetchModels = async () => {
    setLoadingModels(true)
    setError('')
    try {
      const response = await fetch('/api/providers/ollama/models')
      if (!response.ok) throw await safeError(response)
      const data = await response.json()
      const available = Array.isArray(data.models) ? data.models as ProviderModel[] : []
      setModels(available)
      setModelId(current => available.some(model => model.model_id === current) ? current : available.length === 1 ? available[0].model_id : '')
      if (!available.length) setNotice("core.ProviderSettings.no_models_check_access_and_reload_the_483fcf")
      else setNotice(localMessage("core.ProviderSettings.found_p0_models_check_access_to_the_414012",{get p0(){return formatNumber(available.length)}}))
    } catch (cause) {
      setError(cause instanceof Error ? cause : "commerce.providers.could_not_load_the_model_list")
    } finally { setLoadingModels(false) }
  }

  const loadStatus = async () => {
    setLoading(true)
    setError('')
    try {
      const response = await fetch('/api/providers/ollama/status')
      if (!response.ok) throw await safeError(response)
      const data = await response.json() as ProviderStatus
      setStatus(data)
      onStatusChange?.(data)
      if (data.auth_mode) setAuthMode(data.auth_mode)
      setModelId(data.model_id ?? '')
      if (data.auth_mode && data.runtime_mode !== 'container' && data.state !== 'needs_authentication') await fetchModels()
    } catch (cause) {
      setError(cause instanceof Error ? cause : "commerce.providers.could_not_read_ollama_status")
    } finally { setLoading(false) }
  }

  const loadModels = async () => {
    if (status?.auth_mode !== authMode || (authMode === 'api_key' && apiKey.length > 0)) {
      setNotice("core.ProviderSettings.save_the_authentication_method_and_api_key_b9dbf2")
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
      if (!response.ok) throw await safeError(response)
      const data = await response.json() as ProviderStatus
      setStatus(data)
      onStatusChange?.(data)
      setModelId(data.model_id ?? '')
      setNotice("core.ProviderSettings.access_saved_aa539c")
      await fetchModels()
    } catch (cause) {
      setError(cause instanceof Error ? cause : "commerce.providers.could_not_save_ollama_configuration")
    } finally {
      setApiKey('')
      setSaving(false)
    }
  }

  const verifyConfiguration = async () => {
    if (!modelId.trim()) { setError("core.ProviderSettings.choose_a_model_before_checking_its_availability_09bc8e"); return }
    if (status?.auth_mode !== authMode || apiKey.length > 0) {
      setError("core.ProviderSettings.save_changes_in_access_first_9271ca")
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
        if (!savedResponse.ok) throw await safeError(savedResponse)
        const saved = await savedResponse.json() as ProviderStatus
        setStatus(saved)
        onStatusChange?.(saved)
      }
      const response = await fetch('/api/providers/ollama/verify', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ model_id: modelId.trim() }),
      })
      if (!response.ok) throw await safeError(response)
      const result = await response.json()
      setVerification(result.generation_performed ? localMessage('commerce.providers.model_access_verified',{model:result.model_id}) : localMessage('commerce.providers.model_unavailable',{model:result.model_id??'',get state(){return statusLabel(result.state)+' ('+result.state+')'}}))
      await loadStatus()
    } catch (cause) {
      await loadStatus()
      setError(cause instanceof Error ? cause : "commerce.providers.ollama_verification_failed")
    } finally { setVerifying(false) }
  }

  return (
    <div className="ollama-provider-settings">
      <div className="provider-method-tabs" role="tablist" aria-label={t("core.ProviderSettings.ollama_settings_6fd7c2")}>
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
        >{section === 'access' ? t("core.ProviderSettings.access_bf904a") : t("core.ProviderSettings.model_a5ab32")}</button>)}
      </div>
      <form className="provider-card" role="tabpanel" id="ollama-settings-panel-access" aria-labelledby="ollama-settings-tab-access" hidden={activeSection !== 'access'} onSubmit={event => void saveConfiguration(event)}>
        <fieldset className="auth-choice-group" disabled={saving || verifying || status?.runtime_mode === 'container'}><legend className="sr-only">{t("core.ProviderSettings.ollama_authentication_method_baa4c1")}</legend>
          <label className={`auth-choice ${authMode === 'api_key' ? 'active' : ''}`}><input type="radio" name="ollama-auth-mode" value="api_key" checked={authMode === 'api_key'} onChange={() => { setAuthMode('api_key'); setModels([]); setModelId(''); setNotice(''); setError('') }} /><span><strong>{t("core.ProviderSettings.cloud_api_key_4e553a")}</strong></span></label>
          <label className={`auth-choice ${authMode === 'local_cli' ? 'active' : ''}`}><input type="radio" name="ollama-auth-mode" value="local_cli" checked={authMode === 'local_cli'} onChange={() => { setAuthMode('local_cli'); setApiKey(''); setModels([]); setModelId(''); setNotice(''); setError('') }} /><span><strong>{t("core.ProviderSettings.local_ollama_f69f95")}</strong></span></label>
        </fieldset>
        {authMode === 'api_key' ? <div className="provider-field"><label htmlFor="ollama-api-key">{t("core.ProviderSettings.api_key_16f0ee")}{' '}<span>{t("core.ProviderSettings.write_only_d50a55")}</span></label><input id="ollama-api-key" type="password" autoComplete="new-password" value={apiKey} onChange={event => setApiKey(event.target.value)} placeholder={t("core.ProviderSettings.new_key_to_replace_the_saved_key_0f431f")} spellCheck={false} disabled={saving || verifying} /></div> : <div className="cli-instructions"><p>{t("core.ProviderSettings.start_ollama_on_this_computer_save_access_1b7e7c")}</p></div>}
        <button className="provider-primary" type="submit" disabled={saving || verifying || loading || status?.runtime_mode === 'container'}>{saving ? t("core.ProviderSettings.saving_3c8dc4") : t("core.ProviderSettings.save_access_4ed1bb")}</button>
      </form>

      <section className="provider-card" role="tabpanel" id="ollama-settings-panel-model" aria-labelledby="ollama-settings-tab-model" hidden={activeSection !== 'model'}>
        <div className="model-controls">
          <label className="provider-field model-select-field" htmlFor="ollama-model"><span className="sr-only">{t("core.ProviderSettings.model_a5ab32")}</span><select id="ollama-model" value={modelId} onChange={event => setModelId(event.target.value)} disabled={saving || verifying || loading || status?.runtime_mode === 'container'}><option value="">{t("core.ProviderSettings.select_a_model_088d84")}</option>{models.map(model => <option key={`${model.provider_id}:${model.model_id}`} value={model.model_id}>{model.display_name}</option>)}</select></label>
          <button className="provider-secondary" type="button" onClick={() => void loadModels()} disabled={loadingModels || saving || verifying || status?.runtime_mode === 'container'}>{loadingModels ? t("core.ProviderSettings.loading_205443") : t("core.ProviderSettings.load_models_00fe5e")}</button>
        </div>
        {models.length === 0 && !loadingModels && <p className="provider-empty-models">{t("core.ProviderSettings.save_access_and_load_the_models_6b5e3b")}</p>}
        <div className="model-actions"><button className="provider-secondary" type="button" onClick={() => void verifyConfiguration()} disabled={saving || verifying || loading || !modelId.trim() || status?.runtime_mode === 'container'}>{verifying ? t("core.ProviderSettings.checking_d2a709") : t("core.ProviderSettings.save_and_check_access_1a16f4")}</button></div>
        <p className="provider-footnote">{t("core.ProviderSettings.the_check_may_consume_cloud_usage_456f1f")}</p>
      </section>

      {error && <p className="provider-alert error" role="alert">{errorMessage(error)}</p>}{notice && <p className="provider-alert notice" role="status">{errorMessage(notice)}</p>}{verification && <p className="provider-alert notice" role="status">{errorMessage(verification)}</p>}
      {status?.last_verified_at && <p className="provider-footnote">{t("core.ProviderSettings.last_check_dd2bf8")}{' '}{formatDate(status.last_verified_at)}</p>}
    </div>
  )
}
